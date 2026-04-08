import os
import sys
import uuid
import hashlib
import tempfile
import shutil
import zipfile
import threading
import functools
import time
from collections import defaultdict
from pathlib import Path
from flask import Flask, request, send_file, jsonify, Response
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

# ── API key auth (optional) ──────────────────────────────────────────────────
# Set VALICHORD_API_KEYS to a comma-separated list of valid keys.
# If unset or empty, the API is open (dev / local mode — current default).
# Integrators should set this before exposing the endpoint publicly.
_API_KEYS: set = {
    k.strip()
    for k in os.environ.get('VALICHORD_API_KEYS', '').split(',')
    if k.strip()
}

# ── Per-key rate limiting ─────────────────────────────────────────────────────
# VALICHORD_RATE_LIMIT — max requests per key per minute on write endpoints.
# Defaults to 10. Set to 0 to disable rate limiting.
# When the API is open (no keys configured) rate limiting uses the client IP.
_RATE_LIMIT = int(os.environ.get('VALICHORD_RATE_LIMIT', '10'))
_rate_buckets: dict = defaultdict(list)   # key/ip → [timestamp, ...]
_rate_lock = threading.Lock()


def _check_rate_limit(identity: str) -> bool:
    """Return True if the request is within the rate limit, False if exceeded.

    Uses a sliding 60-second window. Thread-safe.
    """
    if _RATE_LIMIT == 0:
        return True
    now = time.monotonic()
    window_start = now - 60.0
    with _rate_lock:
        timestamps = _rate_buckets[identity]
        # Evict timestamps older than the window
        _rate_buckets[identity] = [t for t in timestamps if t > window_start]
        if len(_rate_buckets[identity]) >= _RATE_LIMIT:
            return False
        _rate_buckets[identity].append(now)
        return True


def _require_api_key(f):
    """Decorator: enforce API key (when configured) and per-key rate limit."""
    @functools.wraps(f)
    def _decorated(*args, **kwargs):
        if not _API_KEYS:
            # Open mode — rate-limit by IP
            identity = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')
            if not _check_rate_limit(identity):
                return jsonify({
                    'error': 'Rate limit exceeded.',
                    'hint': f'Maximum {_RATE_LIMIT} requests per minute. Please wait before retrying.',
                }), 429
            return f(*args, **kwargs)

        key = (
            request.headers.get('X-ValiChord-Key')
            or request.form.get('api_key', '')
            or request.args.get('api_key', '')
        )
        if key not in _API_KEYS:
            return jsonify({
                'error': 'Invalid or missing API key.',
                'hint': 'Pass your key in the X-ValiChord-Key request header.',
            }), 401
        if not _check_rate_limit(key):
            return jsonify({
                'error': 'Rate limit exceeded.',
                'hint': f'Maximum {_RATE_LIMIT} requests per minute per API key. Please wait before retrying.',
            }), 429
        return f(*args, **kwargs)
    return _decorated


# ── job store ────────────────────────────────────────────────────────────────
_jobs: dict = {}
_jobs_lock = threading.Lock()

# ── in-progress uploads (chunked) ────────────────────────────────────────────
_uploads: dict = {}
_uploads_lock = threading.Lock()


def _fire_webhook(callback_url: str, job_id: str, payload: dict):
    """POST completed job result to callback_url. Fire-and-forget, one retry."""
    import requests as _req
    import time as _time
    headers = {
        'Content-Type': 'application/json',
        'X-ValiChord-Job-Id': job_id,
    }
    for attempt in range(2):
        try:
            _req.post(callback_url, json=payload, headers=headers, timeout=10)
            return
        except Exception:
            if attempt == 0:
                _time.sleep(5)


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


_VALID_VALIDATOR_OUTCOMES = {'Reproduced', 'PartiallyReproduced', 'FailedToReproduce'}


def _compute_harmony_draft(findings, data_hash_hex: str,
                           validator_outcome: str = None,
                           validator_notes: str = '') -> dict:
    """Build the HarmonyRecord draft that will be written to the Governance DHT.

    Two modes:

    1. Validator-attested (validator_outcome is supplied):
       A real validator (human or AI) actually ran the code and is submitting
       their genuine replication verdict.  Use it directly — this is what
       ValiChord is designed for.

    2. Proxy (validator_outcome is None):
       No one has run the code yet.  Derive a provisional outcome from the
       deposit quality findings as a stand-in.  This is replaced by a real
       attestation once a validator submits one.

       Proxy mapping:
         Any CRITICAL finding  → FailedToReproduce
         SIGNIFICANT only      → PartiallyReproduced
         No findings           → Reproduced
    """
    critical    = [f for f in findings if f.get('severity') == 'CRITICAL']
    significant = [f for f in findings if f.get('severity') == 'SIGNIFICANT']
    low         = [f for f in findings if f.get('severity') == 'LOW CONFIDENCE']

    attested = validator_outcome in _VALID_VALIDATOR_OUTCOMES

    if attested:
        if validator_outcome == 'Reproduced':
            outcome = {'type': 'Reproduced'}
        elif validator_outcome == 'PartiallyReproduced':
            outcome = {
                'type': 'PartiallyReproduced',
                'content': {'details': validator_notes or 'Validator reported partial reproduction'},
            }
        else:  # FailedToReproduce
            outcome = {
                'type': 'FailedToReproduce',
                'content': {'details': validator_notes or 'Validator reported failure to reproduce'},
            }
    else:
        # Proxy — derived from deposit quality, not actual execution.
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
        'validator_attested': attested,
        'data_hash': data_hash_hex,
        'findings_summary': {
            'critical':       len(critical),
            'significant':    len(significant),
            'low_confidence': len(low),
            'total':          len(findings),
        },
        'harmony_record_hash': None,
        'harmony_record_url':  None,
    }


def _process_job(job_id: str, upload_path: Path, work_dir: Path, original_filename: str,
                 validator_outcome: str = None, validator_notes: str = '',
                 callback_url: str = None):
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
        harmony_draft = _compute_harmony_draft(findings, data_hash_hex,
                                               validator_outcome=validator_outcome,
                                               validator_notes=validator_notes)

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

        if callback_url:
            webhook_payload = {
                'job_id': job_id,
                'status': 'done',
                'harmony_record_draft': harmony_draft,
                'top_findings': top_findings,
                'download_url': f'/download/{job_id}',
            }
            threading.Thread(
                target=_fire_webhook,
                args=(callback_url, job_id, webhook_payload),
                daemon=True,
            ).start()

    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['error'] = str(e)
        if callback_url:
            threading.Thread(
                target=_fire_webhook,
                args=(callback_url, job_id, {'job_id': job_id, 'status': 'error', 'error': str(e)}),
                daemon=True,
            ).start()
        shutil.rmtree(work_dir, ignore_errors=True)


_OPENAPI_PATH = Path(__file__).parent / 'openapi.yaml'
_SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>ValiChord API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: '/openapi.yaml',
    dom_id: '#swagger-ui',
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: 'StandaloneLayout',
    deepLinking: true,
  });
</script>
</body>
</html>"""


@app.route('/openapi.yaml', methods=['GET'])
def openapi_spec():
    """Serve the OpenAPI 3.0 specification."""
    if not _OPENAPI_PATH.exists():
        return jsonify({'error': 'OpenAPI spec not found'}), 404
    return Response(_OPENAPI_PATH.read_text(encoding='utf-8'), mimetype='application/yaml')


@app.route('/docs', methods=['GET'])
def swagger_ui():
    """Swagger UI — interactive API documentation."""
    return Response(_SWAGGER_HTML, mimetype='text/html')


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
@_require_api_key
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


@app.route('/validate', methods=['POST'])
@_require_api_key
def validate():
    """Single-shot deposit validation.

    Accepts multipart/form-data with:
      file              (required) — ZIP of the research deposit, max 100 MB
      validator_outcome (optional) — "Reproduced" | "PartiallyReproduced" | "FailedToReproduce"
                                     Provide when a validator has actually run the code.
                                     If omitted, outcome is derived from deposit quality (proxy).
      validator_notes   (optional) — free-text description of what ran, what failed, max 2000 chars.
                                     Used as the details string in PartiallyReproduced /
                                     FailedToReproduce outcomes.
      callback_url      (optional) — HTTPS URL to POST the completed result to.
                                     ValiChord will call this URL once when the job finishes,
                                     with Content-Type: application/json and
                                     X-ValiChord-Job-Id header. One retry after 5 s on failure.

    Returns { "job_id": "..." } immediately (HTTP 202).
    Poll GET /result/<job_id> for structured JSON results including
    harmony_record_draft.validator_attested (true when validator_outcome was supplied).
    """
    file = request.files.get('file')
    if file is None:
        return jsonify({'error': 'Missing file field (multipart/form-data, field name: file)'}), 400

    validator_outcome = (request.form.get('validator_outcome') or '').strip() or None
    if validator_outcome and validator_outcome not in _VALID_VALIDATOR_OUTCOMES:
        return jsonify({
            'error': f'Invalid validator_outcome "{validator_outcome}". '
                     f'Must be one of: {", ".join(sorted(_VALID_VALIDATOR_OUTCOMES))}'
        }), 400
    validator_notes = (request.form.get('validator_notes') or '')[:2000]
    callback_url = (request.form.get('callback_url') or '').strip() or None

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
        kwargs={
            'validator_outcome': validator_outcome,
            'validator_notes': validator_notes,
            'callback_url': callback_url,
        },
        daemon=True,
    )
    worker.start()
    threading.Thread(target=_watchdog, args=(job_id, worker, work_dir), daemon=True).start()

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


@app.route('/result/<job_id>', methods=['GET'])
def result(job_id):
    """Structured JSON result for a completed validation job.

    Returns:
      { "status": "running" }
      { "status": "error", "error": "..." }
      { "status": "done",
        "prs": <float 0-1>,
        "harmony_record_draft": { outcome, data_hash, findings_summary, ... },
        "top_findings": [...],
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
        'prs': job.get('prs'),
        'harmony_record_draft': job.get('harmony_record_draft'),
        'download_url': f'/download/{job_id}',
        'top_findings': job.get('top_findings', []),
    })


@app.route('/attest', methods=['POST'])
@_require_api_key
def attest():
    """Validator attestation — fast path for AI/human validators.

    Takes a deposit ZIP, hashes it, runs the Holochain commit-reveal protocol
    with the supplied outcome, and returns the HarmonyRecord synchronously
    (no polling required).

    Unlike POST /validate, this endpoint does NOT run the structural analysis
    (valichord_at_home detectors).  It is intended for validators who have
    already executed the research code and are submitting a real replication
    verdict.

    Accepts multipart/form-data:
      file        (required) — deposit ZIP, max 100 MB
      outcome     (required) — Reproduced | PartiallyReproduced | FailedToReproduce
      notes       (optional) — replication notes, max 2000 chars
      discipline  (optional) — JSON discipline object; default {"type":"ComputationalBiology"}
      confidence  (optional) — High | Medium | Low; default Medium

    Returns:
      {
        "data_hash": "<64-char hex SHA-256 of deposit ZIP>",
        "outcome": "Reproduced",
        "validator_attested": true,
        "harmony_record_hash": "<uhCkk... ActionHash or null>",
        "harmony_record_url":  "<gateway URL or null>"
      }

    harmony_record_hash is null when the Holochain conductor is offline;
    the response still succeeds so the caller knows the hash was computed
    but not yet recorded.
    """
    import json as _json

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Missing file field (multipart/form-data, field name: file)'}), 400

    outcome_str = (request.form.get('outcome') or '').strip()
    if outcome_str not in _VALID_VALIDATOR_OUTCOMES:
        return jsonify({
            'error': (
                f'outcome is required and must be one of: '
                f'{", ".join(sorted(_VALID_VALIDATOR_OUTCOMES))}'
            )
        }), 400

    notes      = (request.form.get('notes')      or '')[:2000]
    confidence = (request.form.get('confidence') or 'Medium').strip()

    discipline_raw = (request.form.get('discipline') or '').strip()
    if discipline_raw:
        try:
            discipline = _json.loads(discipline_raw)
        except Exception:
            return jsonify({'error': 'discipline must be valid JSON, e.g. {"type":"ComputationalBiology"}'}), 400
    else:
        discipline = {'type': 'ComputationalBiology'}

    if outcome_str == 'Reproduced':
        outcome = {'type': 'Reproduced'}
    elif outcome_str == 'PartiallyReproduced':
        outcome = {'type': 'PartiallyReproduced',
                   'content': {'details': notes or 'Partial reproduction reported by validator'}}
    else:
        outcome = {'type': 'FailedToReproduce',
                   'content': {'details': notes or 'Failed to reproduce — reported by validator'}}

    work_dir = Path(tempfile.mkdtemp(prefix='valichord_attest_'))
    upload_path = work_dir / 'deposit.zip'
    try:
        file.save(str(upload_path))

        size_mb = upload_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_SIZE_MB:
            return jsonify({
                'error': f'File too large ({size_mb:.0f} MB). Maximum is {MAX_SIZE_MB} MB.'
            }), 400

        data_hash_hex = hashlib.sha256(upload_path.read_bytes()).hexdigest()

        holochain_result = run_validation_round(
            data_hash_hex=data_hash_hex,
            outcome=outcome,
            discipline=discipline,
            confidence=confidence,
        )

        harmony_record_hash = None
        harmony_record_url  = None
        if holochain_result:
            harmony_record_hash = holochain_result.get('harmony_record_hash')
            gateway_payload     = holochain_result.get('gateway_payload')
            if (harmony_record_hash
                    and HOLOCHAIN_GATEWAY_URL
                    and HOLOCHAIN_GOVERNANCE_DNA_HASH
                    and gateway_payload):
                harmony_record_url = (
                    f"{HOLOCHAIN_GATEWAY_URL}"
                    f"/{HOLOCHAIN_GOVERNANCE_DNA_HASH}"
                    f"/{HOLOCHAIN_APP_ID}"
                    f"/governance_coordinator"
                    f"/get_harmony_record"
                    f"?payload={gateway_payload}"
                )

        return jsonify({
            'data_hash':          data_hash_hex,
            'outcome':            outcome_str,
            'validator_attested': True,
            'harmony_record_hash': harmony_record_hash,
            'harmony_record_url':  harmony_record_url,
        })

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
