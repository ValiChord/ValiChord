"""
ValiChord Protocol API — backend/app_protocol.py

Standalone Flask application for the ValiChord commit-reveal protocol.
This is the integration point for AI validators (PI, Feynman) and human validators.

Does NOT include the valichord_at_home structural analysis pipeline.
For the valichord_at_home researcher tool, see backend/app.py (run by Render).

Endpoints:
  GET  /health         — liveness + Holochain conductor status
  POST /attest         — submit a validator verdict; runs commit-reveal; returns HarmonyRecord
  GET  /openapi.yaml   — OpenAPI spec (protocol endpoints only)
  GET  /docs           — Swagger UI

Run (Codespace):
  cd /workspaces/ValiChord && python backend/app_protocol.py
  Default port: 5001  (to avoid conflict with app.py on 5000)
  Override: PORT=5001 python backend/app_protocol.py

Requires:
  - demo/serve.mjs running on port 8888 (Holochain bridge)
  - Holochain conductor running (start.sh / setup.mjs)

Environment variables (all optional):
  PORT                         — listen port (default 5001)
  VALICHORD_API_KEYS           — comma-separated valid keys; empty = open mode
  VALICHORD_RATE_LIMIT         — max requests/key/minute (default 10; 0 = disabled)
  HOLOCHAIN_GATEWAY_URL        — public HTTP gateway base URL for HarmonyRecord links
  HOLOCHAIN_GOVERNANCE_DNA_HASH— governance DNA hash (for gateway URL)
  HOLOCHAIN_APP_ID             — installed app ID (default valichord-demo)
"""

import os
import re
import hashlib
import tempfile
import shutil
import functools
import threading
import time
from collections import defaultdict
from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from holochain_bridge import run_validation_round

app = Flask(__name__)
CORS(app)

# No hard content-length cap — data_hash path sends only a tiny form.
# The file fallback is rare; callers who use it are responsible for size.

HOLOCHAIN_GATEWAY_URL         = os.environ.get('HOLOCHAIN_GATEWAY_URL', '').rstrip('/')
HOLOCHAIN_GOVERNANCE_DNA_HASH = os.environ.get('HOLOCHAIN_GOVERNANCE_DNA_HASH', '')
HOLOCHAIN_APP_ID              = os.environ.get('HOLOCHAIN_APP_ID', 'valichord-demo')

# ── API key auth (optional) ──────────────────────────────────────────────────
_API_KEYS: set = {
    k.strip()
    for k in os.environ.get('VALICHORD_API_KEYS', '').split(',')
    if k.strip()
}

# ── Per-key rate limiting ─────────────────────────────────────────────────────
_RATE_LIMIT = int(os.environ.get('VALICHORD_RATE_LIMIT', '10'))
_rate_buckets: dict = defaultdict(list)
_rate_lock = threading.Lock()


def _check_rate_limit(identity: str) -> bool:
    if _RATE_LIMIT == 0:
        return True
    now = time.monotonic()
    window_start = now - 60.0
    with _rate_lock:
        _rate_buckets[identity] = [t for t in _rate_buckets[identity] if t > window_start]
        if len(_rate_buckets[identity]) >= _RATE_LIMIT:
            return False
        _rate_buckets[identity].append(now)
        return True


def _require_api_key(f):
    """Enforce API key (when configured) and per-key rate limit."""
    @functools.wraps(f)
    def _decorated(*args, **kwargs):
        if not _API_KEYS:
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


_VALID_VALIDATOR_OUTCOMES = {'Reproduced', 'PartiallyReproduced', 'FailedToReproduce'}

# ── OpenAPI / Swagger ─────────────────────────────────────────────────────────

_OPENAPI_PATH = Path(__file__).parent / 'openapi_protocol.yaml'
_SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>ValiChord Protocol API</title>
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
    if not _OPENAPI_PATH.exists():
        return jsonify({'error': 'OpenAPI spec not found'}), 404
    return Response(_OPENAPI_PATH.read_text(encoding='utf-8'), mimetype='application/yaml')


@app.route('/docs', methods=['GET'])
def swagger_ui():
    return Response(_SWAGGER_HTML, mimetype='text/html')


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Liveness check.  Includes conductor status so integrators know whether
    HarmonyRecords will be written on this deployment."""
    import requests as _req
    conductor = 'offline'
    try:
        r = _req.get('http://localhost:8888/app-config.json', timeout=2)
        if r.status_code == 200:
            conductor = 'live'
    except Exception:
        pass
    return jsonify({'status': 'ok', 'version': '1.0', 'conductor': conductor})


@app.route('/attest', methods=['POST'])
@_require_api_key
def attest():
    """Validator attestation — synchronous Holochain commit-reveal (~60 s).

    Accepts multipart/form-data:
      data_hash   (required*) — 64-char hex SHA-256 of the deposit.
                                Preferred: compute locally; no upload needed.
      file        (optional*) — deposit ZIP; used to compute data_hash when the
                                caller cannot do it locally.  One of data_hash or
                                file must be supplied.
      outcome     (required)  — Reproduced | PartiallyReproduced | FailedToReproduce
      notes       (optional)  — replication notes, max 2000 chars
      discipline  (optional)  — JSON, e.g. {"type":"ComputationalBiology"}
      confidence  (optional)  — High | Medium | Low; default Medium

    Returns:
      {
        "data_hash": "<64-char hex SHA-256>",
        "outcome": "Reproduced",
        "validator_attested": true,
        "harmony_record_hash": "<uhCkk... ActionHash or null>",
        "harmony_record_url":  "<gateway URL or null>"
      }

    harmony_record_hash is null when the Holochain conductor is offline.
    The response still succeeds — the caller knows the hash was computed but
    not yet written to the DHT.
    """
    import json as _json

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

    # Resolve data_hash: accept direct hex (preferred) or compute from file (fallback).
    data_hash_hex = (request.form.get('data_hash') or '').strip().lower()
    file = request.files.get('file')
    work_dir = None

    if data_hash_hex:
        if not re.fullmatch(r'[0-9a-f]{64}', data_hash_hex):
            return jsonify({'error': 'data_hash must be a 64-character lowercase hex SHA-256 string'}), 400
    elif file:
        work_dir = Path(tempfile.mkdtemp(prefix='valichord_attest_'))
        upload_path = work_dir / 'deposit.zip'
        file.save(str(upload_path))
        data_hash_hex = hashlib.sha256(upload_path.read_bytes()).hexdigest()
    else:
        return jsonify({
            'error': 'Either data_hash (preferred) or file must be supplied. '
                     'Compute the SHA-256 hex of your deposit ZIP locally and pass it as data_hash.'
        }), 400

    if outcome_str == 'Reproduced':
        outcome = {'type': 'Reproduced'}
    elif outcome_str == 'PartiallyReproduced':
        outcome = {'type': 'PartiallyReproduced',
                   'content': {'details': notes or 'Partial reproduction reported by validator'}}
    else:
        outcome = {'type': 'FailedToReproduce',
                   'content': {'details': notes or 'Failed to reproduce — reported by validator'}}

    try:
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
            'data_hash':           data_hash_hex,
            'outcome':             outcome_str,
            'validator_attested':  True,
            'harmony_record_hash': harmony_record_hash,
            'harmony_record_url':  harmony_record_url,
        })

    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
