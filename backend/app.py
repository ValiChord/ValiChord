import os
import sys
import uuid
import tempfile
import shutil
import zipfile
import threading
from pathlib import Path
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

# add autogenerate to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'autogenerate'))

from detectors.failure_modes_simple import run_simple_detectors
from generators.report import generate_cleaning_report
from generators.drafts import generate_all_drafts

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024   # 100 MB hard cap
CORS(app)

MAX_SIZE_MB = 100

# ── job store ────────────────────────────────────────────────────────────────
_jobs: dict = {}
_jobs_lock = threading.Lock()

# ── in-progress uploads (chunked) ────────────────────────────────────────────
_uploads: dict = {}
_uploads_lock = threading.Lock()


def _process_job(job_id: str, upload_path: Path, work_dir: Path, original_filename: str):
    try:
        repo_dir = work_dir / 'repository'
        output_dir = work_dir / 'output'
        repo_dir.mkdir()
        output_dir.mkdir()
        (output_dir / 'proposed_corrections').mkdir()

        with zipfile.ZipFile(upload_path, 'r') as zf:
            zf.extractall(repo_dir)

        # Record nested archives BEFORE extraction (zips will be deleted).
        import json as _json
        _archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2'}
        _nested_archive_records = [
            {'path': str(f.relative_to(repo_dir)), 'size': f.stat().st_size}
            for f in repo_dir.rglob('*')
            if f.is_file()
            and f.suffix.lower() in _archive_exts
            and f.stat().st_size <= 100 * 1024 * 1024
        ]
        if _nested_archive_records:
            (repo_dir / '.valichord_nested_archives.json').write_text(
                _json.dumps(_nested_archive_records), encoding='utf-8'
            )

        def extract_nested(directory, depth=0):
            if depth > 3:
                return
            for nested in list(directory.rglob('*.zip')):
                if nested.stat().st_size > 100 * 1024 * 1024:
                    continue
                try:
                    dest = nested.parent / nested.stem
                    dest.mkdir(exist_ok=True)
                    with zipfile.ZipFile(nested, 'r') as zf:
                        zf.extractall(dest)
                    nested.unlink()
                    extract_nested(dest, depth + 1)
                except Exception:
                    pass

        extract_nested(repo_dir)

        all_files = [
            f for f in repo_dir.rglob('*')
            if f.is_file()
            and '.git' not in f.parts
            and '__pycache__' not in f.parts
            and '__MACOSX' not in f.parts
            and not f.name.startswith('._')
            and f.name not in {'.DS_Store', 'Thumbs.db', 'desktop.ini',
                                '.valichord_nested_archives.json'}
        ]

        findings = run_simple_detectors(repo_dir, all_files)
        generate_all_drafts(repo_dir, all_files, findings, output_dir)
        generate_cleaning_report(original_filename, repo_dir, all_files, findings, output_dir)

        stem = Path(original_filename).stem
        output_zip = work_dir / f'valichord_output_{stem}.zip'
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in output_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(output_dir))

        with _jobs_lock:
            _jobs[job_id]['status'] = 'done'
            _jobs[job_id]['output_zip'] = output_zip
            _jobs[job_id]['stem'] = stem

    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['error'] = str(e)
        shutil.rmtree(work_dir, ignore_errors=True)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'version': '1.0'})


@app.route('/upload-chunk', methods=['POST'])
def upload_chunk():
    """Receive one chunk of a multi-part upload.

    Form fields:
      upload_id    – client-generated UUID for this upload session
      chunk_index  – 0-based index of this chunk
      total_chunks – total number of chunks
      chunk        – the binary chunk (file field)

    Returns:
      { "status": "received" }              – chunk stored, more to come
      { "status": "processing", "job_id" }  – all chunks received, job started
    """
    upload_id = request.form.get('upload_id')
    chunk_index = int(request.form.get('chunk_index', 0))
    total_chunks = int(request.form.get('total_chunks', 1))
    chunk_file = request.files.get('chunk')

    if not upload_id or chunk_file is None:
        return jsonify({'error': 'Missing upload_id or chunk'}), 400

    filename = chunk_file.filename or 'upload.zip'

    with _uploads_lock:
        if upload_id not in _uploads:
            work_dir = Path(tempfile.mkdtemp(prefix='valichord_'))
            (work_dir / 'chunks').mkdir()
            _uploads[upload_id] = {
                'work_dir': work_dir,
                'received': set(),
                'total': total_chunks,
                'filename': filename,
            }
        info = _uploads[upload_id]

    # save this chunk (outside the lock so we don't block other requests)
    chunk_path = info['work_dir'] / 'chunks' / f'chunk_{chunk_index:06d}'
    chunk_file.save(str(chunk_path))

    with _uploads_lock:
        info['received'].add(chunk_index)
        all_received = len(info['received']) == info['total']

    if not all_received:
        return jsonify({'status': 'received', 'chunk': chunk_index}), 200

    # ── all chunks received — assemble and start job ──────────────────────
    work_dir = info['work_dir']
    upload_path = work_dir / 'upload.zip'

    with open(upload_path, 'wb') as out:
        for i in range(total_chunks):
            cp = work_dir / 'chunks' / f'chunk_{i:06d}'
            with open(cp, 'rb') as cf:
                out.write(cf.read())

    size_mb = upload_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        shutil.rmtree(work_dir, ignore_errors=True)
        with _uploads_lock:
            _uploads.pop(upload_id, None)
        return jsonify({'error': f'File too large ({size_mb:.0f} MB). Maximum is {MAX_SIZE_MB} MB.'}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'status': 'running',
            'output_zip': None,
            'error': None,
            'work_dir': work_dir,
        }
    with _uploads_lock:
        _uploads.pop(upload_id, None)

    threading.Thread(
        target=_process_job,
        args=(job_id, upload_path, work_dir, filename),
        daemon=True
    ).start()

    return jsonify({'status': 'processing', 'job_id': job_id}), 202


@app.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({'error': 'Unknown job'}), 404
    if job['status'] == 'running':
        return jsonify({'status': 'running'})
    if job['status'] == 'error':
        return jsonify({'status': 'error', 'error': job['error']})
    return jsonify({'status': 'done'})


@app.route('/download/<job_id>', methods=['GET'])
def download(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({'error': 'Unknown job'}), 404
    if job['status'] != 'done':
        return jsonify({'error': 'Job not ready'}), 409

    output_zip = job['output_zip']
    stem = job.get('stem', 'output')
    download_name = f'valichord_output_{stem}.zip'

    def cleanup():
        work_dir = job.get('work_dir')
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        with _jobs_lock:
            _jobs.pop(job_id, None)

    response = send_file(
        str(output_zip),
        as_attachment=True,
        download_name=download_name,
        mimetype='application/zip'
    )
    threading.Thread(target=cleanup, daemon=True).start()
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
