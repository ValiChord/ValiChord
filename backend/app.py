import os
import sys
import uuid
import hashlib
import tempfile
import shutil
import zipfile
import threading
from pathlib import Path
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

# add valichord_at_home to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'valichord_at_home'))

from detectors.failure_modes_simple import run_simple_detectors
from detectors.claude_semantic import run_claude_analysis
from generators.report import generate_cleaning_report, compute_prs
from generators.drafts import generate_all_drafts
from generators.log import generate_valichord_log
from holochain_bridge import run_validation_round

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024   # 100 MB hard cap
CORS(app)

MAX_SIZE_MB = 100
JOB_TIMEOUT_SECONDS = 1200  # 20 minutes — enough for a 100 MB deposit

# Optional HTTP Gateway for public HarmonyRecord lookups.
# Gateway URL format: {HOLOCHAIN_GATEWAY_URL}/{HOLOCHAIN_GOVERNANCE_DNA_HASH}/{HOLOCHAIN_APP_ID}/
#                     governance_coordinator/get_harmony_record?payload=<base64url-json>
# When all three are set, harmony_record_url is populated in responses.
HOLOCHAIN_GATEWAY_URL        = os.environ.get('HOLOCHAIN_GATEWAY_URL', '').rstrip('/')
HOLOCHAIN_GOVERNANCE_DNA_HASH = os.environ.get('HOLOCHAIN_GOVERNANCE_DNA_HASH', '')
HOLOCHAIN_APP_ID             = os.environ.get('HOLOCHAIN_APP_ID', 'valichord-demo')

# ── job store ────────────────────────────────────────────────────────────────
_jobs: dict = {}
_jobs_lock = threading.Lock()

# ── in-progress uploads (chunked) ────────────────────────────────────────────
_uploads: dict = {}
_uploads_lock = threading.Lock()


def _watchdog(job_id: str, thread: threading.Thread, work_dir: Path):
    """Mark job as timed-out if the worker thread hasn't finished within JOB_TIMEOUT_SECONDS."""
    thread.join(timeout=JOB_TIMEOUT_SECONDS)
    if thread.is_alive():
        with _jobs_lock:
            job = _jobs.get(job_id, {})
            if job.get('status') == 'processing':
                job['status'] = 'error'
                job['error'] = f'Processing timed out after {JOB_TIMEOUT_SECONDS // 60} minutes.'
        shutil.rmtree(work_dir, ignore_errors=True)


def _compute_harmony_draft(findings, data_hash_hex: str) -> dict:
    """Derive a would-be HarmonyRecord from analysis findings.

    NOTE: This is a PROXY. It maps deposit quality findings to an
    AttestationOutcome as a stand-in for Phase 0 single-validator mode.
    In the full protocol, AttestationOutcome comes from a validator
    (human or AI) actually running the code — not from deposit analysis.
    See feynman_integration/INTEGRATION_VISION.md for the intended design.

    Outcome mapping (proxy only):
      Any CRITICAL finding  → FailedToReproduce
      SIGNIFICANT only      → PartiallyReproduced
      No findings           → Reproduced
    """
    critical   = [f for f in findings if f.get('severity') == 'CRITICAL']
    significant = [f for f in findings if f.get('severity') == 'SIGNIFICANT']
    low        = [f for f in findings if f.get('severity') == 'LOW CONFIDENCE']

    if critical:
        outcome = {
            'type': 'FailedToReproduce',
            'content': {'details': f'{len(critical)} critical issue(s) prevent reproduction'},
        }
    elif significant:
        outcome = {
            'type': 'PartiallyReproduced',
            'content': {'details': f'{len(significant)} significant issue(s) require attention'},
        }
    else:
        outcome = {'type': 'Reproduced'}

    return {
        'outcome': outcome,
        'data_hash': data_hash_hex,
        'findings_summary': {
            'critical':      len(critical),
            'significant':   len(significant),
            'low_confidence': len(low),
            'total':         len(findings),
        },
        # Populated in a later phase when the Holochain bridge is wired up.
        'harmony_record_hash': None,
        'harmony_record_url':  None,
    }


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
        _nested_archive_records = []
        for _af in repo_dir.rglob('*'):
            if not (_af.is_file() and _af.suffix.lower() in _archive_exts
                    and _af.stat().st_size <= 100 * 1024 * 1024):
                continue
            _rec = {'path': str(_af.relative_to(repo_dir)), 'size': _af.stat().st_size}
            if _af.suffix.lower() == '.zip':
                try:
                    with zipfile.ZipFile(_af, 'r') as _z:
                        _znames = [n for n in _z.namelist() if not n.endswith('/')]
                        _zcount = len(_znames)
                        _zexts = sorted({Path(n).suffix.lower().lstrip('.')
                                         for n in _znames if Path(n).suffix})[:3]
                        _rec['contents_note'] = (
                            f' — {_zcount} files'
                            + (f' ({", ".join(_zexts)})' if _zexts else '')
                        )
                except Exception:
                    pass
            _nested_archive_records.append(_rec)
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

        all_files = sorted(
            (
                f for f in repo_dir.rglob('*')
                if f.is_file()
                and '.git' not in f.parts
                and '__pycache__' not in f.parts
                and '__MACOSX' not in f.parts
                and not f.name.startswith('._')
                and f.name not in {'.DS_Store', 'Thumbs.db', 'desktop.ini',
                                    '.valichord_nested_archives.json'}
                # Exclude ValiChord-generated output files so they don't confuse
                # detectors when a previous output zip is re-uploaded as input.
                and f.name not in {'ASSESSMENT.md', 'CLEANING_REPORT.md'}
                and not (f.name.endswith('_DRAFT.md') or f.name.endswith('_DRAFT.txt'))
            ),
            key=lambda f: str(f),
        )

        findings = run_simple_detectors(repo_dir, all_files, zip_name=original_filename)
        claude_findings, enhanced_details = run_claude_analysis(
            repo_dir, all_files, findings
        )
        if claude_findings:
            findings = findings + claude_findings
        top_findings = [
            {'mode': f.get('mode', ''), 'severity': f.get('severity', ''), 'title': f.get('title', '')}
            for f in findings
            if f.get('severity') in ('BLOCKER', 'CRITICAL', 'SIGNIFICANT')
        ][:6]
        prs = compute_prs(findings)
        generate_all_drafts(repo_dir, all_files, findings, output_dir)
        generate_cleaning_report(original_filename, repo_dir, all_files, findings, output_dir,
                                 enhanced_details=enhanced_details)
        generate_valichord_log(original_filename, repo_dir, all_files, findings, output_dir)

        stem = Path(original_filename).stem
        output_zip = work_dir / f'valichord_output_{stem}.zip'
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in output_dir.rglob('*'):
                if file.is_file():
                    zf.write(file, file.relative_to(output_dir))

        data_hash_hex = hashlib.sha256(upload_path.read_bytes()).hexdigest()
        harmony_draft = _compute_harmony_draft(findings, data_hash_hex)

        # Attempt to write a real HarmonyRecord to the Governance DHT.
        # Requires demo/serve.mjs to be running with a live conductor.
        # Degrades gracefully — analysis always completes even if bridge is down.
        holochain_result = run_validation_round(
            data_hash_hex=data_hash_hex,
            outcome=harmony_draft['outcome'],
        )
        if holochain_result:
            harmony_draft['harmony_record_hash'] = holochain_result.get('harmony_record_hash')
            gateway_payload = holochain_result.get('gateway_payload')
            if (harmony_draft['harmony_record_hash']
                    and HOLOCHAIN_GATEWAY_URL
                    and HOLOCHAIN_GOVERNANCE_DNA_HASH
                    and gateway_payload):
                harmony_draft['harmony_record_url'] = (
                    f"{HOLOCHAIN_GATEWAY_URL}"
                    f"/{HOLOCHAIN_GOVERNANCE_DNA_HASH}"
                    f"/{HOLOCHAIN_APP_ID}"
                    f"/governance_coordinator"
                    f"/get_harmony_record"
                    f"?payload={gateway_payload}"
                )

        with _jobs_lock:
            _jobs[job_id]['status'] = 'done'
            _jobs[job_id]['output_zip'] = output_zip
            _jobs[job_id]['stem'] = stem
            _jobs[job_id]['prs'] = prs
            _jobs[job_id]['harmony_record_draft'] = harmony_draft
            _jobs[job_id]['top_findings'] = top_findings

    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['error'] = str(e)
        shutil.rmtree(work_dir, ignore_errors=True)


@app.route('/health', methods=['GET'])
def health():
    """Liveness check. Includes conductor status so integrators know whether
    Harmony Records will be written on this deployment."""
    import requests as _req
    conductor = 'offline'
    try:
        r = _req.get('http://localhost:8888/app-config.json', timeout=2)
        if r.status_code == 200:
            conductor = 'live'
    except Exception:
        pass
    return jsonify({'status': 'ok', 'version': '1.0', 'conductor': conductor})


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
            if chunk_index > 0:
                # Session not found for a mid-upload chunk — server must have
                # restarted since the upload began.  Tell the client explicitly
                # so it shows a proper "retry" message instead of hanging.
                return jsonify({
                    'error': 'Upload session not found — the server restarted '
                             'during your upload. Please try uploading again.'
                }), 400
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

    worker = threading.Thread(
        target=_process_job,
        args=(job_id, upload_path, work_dir, filename),
        daemon=True
    )
    worker.start()
    threading.Thread(target=_watchdog, args=(job_id, worker, work_dir), daemon=True).start()

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
    return jsonify({
        'status': 'done',
        'prs': job.get('prs'),
        'harmony_record_draft': job.get('harmony_record_draft'),
    })


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


@app.route('/validate', methods=['POST'])
def validate():
    """Single-shot deposit validation.

    Accepts multipart/form-data with a 'file' field (ZIP, max 100 MB).
    Returns { "job_id": "..." } immediately.
    Poll GET /result/<job_id> for structured JSON results.
    """
    file = request.files.get('file')
    if file is None:
        return jsonify({'error': 'Missing file field (multipart/form-data, field name: file)'}), 400

    filename = file.filename or 'deposit.zip'
    work_dir = Path(tempfile.mkdtemp(prefix='valichord_'))
    upload_path = work_dir / 'upload.zip'
    file.save(str(upload_path))

    size_mb = upload_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify({'error': f'File too large ({size_mb:.0f} MB). Maximum is {MAX_SIZE_MB} MB.'}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            'status': 'running',
            'output_zip': None,
            'error': None,
            'work_dir': work_dir,
        }

    worker = threading.Thread(
        target=_process_job,
        args=(job_id, upload_path, work_dir, filename),
        daemon=True,
    )
    worker.start()
    threading.Thread(target=_watchdog, args=(job_id, worker, work_dir), daemon=True).start()

    return jsonify({'job_id': job_id}), 202


@app.route('/result/<job_id>', methods=['GET'])
def result(job_id):
    """Structured JSON result for a completed validation job.

    Returns:
      { "status": "running" }
      { "status": "error", "error": "..." }
      { "status": "done",
        "findings": [...],
        "harmony_record_draft": { outcome, data_hash, findings_summary, ... },
        "download_url": "/download/<job_id>" }
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({'error': 'Unknown job'}), 404
    if job['status'] == 'running':
        return jsonify({'status': 'running'})
    if job['status'] == 'error':
        return jsonify({'status': 'error', 'error': job['error']})
    return jsonify({
        'status': 'done',
        'findings': job.get('prs'),
        'harmony_record_draft': job.get('harmony_record_draft'),
        'download_url': f'/download/{job_id}',
        'top_findings': job.get('top_findings', []),
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
