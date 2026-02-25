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

# ── in-memory job store ──────────────────────────────────────────────────────
# _jobs[job_id] = {'status': 'running'|'done'|'error', 'output_zip': Path|None, 'error': str|None}
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _process_job(job_id: str, upload_path: Path, work_dir: Path, original_filename: str):
    try:
        repo_dir = work_dir / 'repository'
        output_dir = work_dir / 'output'
        repo_dir.mkdir()
        output_dir.mkdir()
        (output_dir / 'proposed_corrections').mkdir()

        with zipfile.ZipFile(upload_path, 'r') as zf:
            zf.extractall(repo_dir)

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
            and f.name not in {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
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


@app.route('/analyse', methods=['POST'])
def analyse():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    if not f.filename.lower().endswith('.zip'):
        return jsonify({'error': 'File must be a .zip'}), 400

    work_dir = Path(tempfile.mkdtemp(prefix='valichord_'))
    upload_path = work_dir / 'upload.zip'
    f.save(str(upload_path))

    size_mb = upload_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify({'error': f'File too large ({size_mb:.0f}MB). Maximum is {MAX_SIZE_MB}MB.'}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {'status': 'running', 'output_zip': None, 'error': None, 'work_dir': work_dir}

    t = threading.Thread(
        target=_process_job,
        args=(job_id, upload_path, work_dir, f.filename),
        daemon=True
    )
    t.start()

    return jsonify({'job_id': job_id}), 202


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
    # Clean up after response is sent
    threading.Thread(target=cleanup, daemon=True).start()
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
