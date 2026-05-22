"""ValiChord demo runner — business logic for the public demo website."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

DEMO_DIR   = Path(__file__).parent
STUDY_DIR  = DEMO_DIR / 'synthetic_study'
MODEL      = 'claude-haiku-4-5-20251001'

RESEARCHER_URL = os.environ.get('VALICHORD_RESEARCHER_URL', 'http://132.145.34.27:3001')
VALIDATOR_URLS = [
    os.environ.get('VALICHORD_VALIDATOR_1_URL', 'http://132.145.34.27:3002'),
    os.environ.get('VALICHORD_VALIDATOR_2_URL', 'http://132.145.34.27:3003'),
    os.environ.get('VALICHORD_VALIDATOR_3_URL', 'http://132.145.34.27:3004'),
]

_EXPECTED_METRICS = {
    'slope':     '2.4086',
    'intercept': '1.1742',
    'r2':        '0.9991',
}


def load_study():
    """Return (readme_text, data_hash_hex, zip_path). Each call produces a unique hash via random salt."""
    readme = (STUDY_DIR / 'README.md').read_text()
    data_bytes = (STUDY_DIR / 'data.csv').read_bytes()
    run_id = uuid.uuid4().bytes
    data_hash = hashlib.sha256(data_bytes + run_id).hexdigest()
    tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(STUDY_DIR.iterdir()):
            zf.write(f, f.name)
    return readme, data_hash, tmp.name


def execute_study():
    """Run synthetic study.py and return stdout. Raises RuntimeError on non-zero exit."""
    script = STUDY_DIR / 'study.py'
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Study script failed (exit {result.returncode}): {result.stderr}')
    return result.stdout.strip()


def parse_metrics(output: str) -> list:
    """Extract structured MetricResult list from study.py stdout."""
    values = {}
    for line in output.splitlines():
        if m := re.match(r'Slope \(coefficient\):\s*([\d.]+)', line):
            values['slope'] = m.group(1)
        elif m := re.match(r'Intercept:\s*([\d.]+)', line):
            values['intercept'] = m.group(1)
        elif m := re.match(r'R[²2]:\s*([\d.]+)', line):
            values['r2'] = m.group(1)
    return [
        {
            'metric_name':      name,
            'produced_value':   values.get(name, 'N/A'),
            'expected_value':   expected,
            'within_tolerance': values.get(name, '') == expected,
        }
        for name, expected in _EXPECTED_METRICS.items()
    ]


def _parse_verdict(raw: str) -> dict:
    """Parse and validate a Claude verdict JSON string. Raises ValueError on bad input."""
    text = raw.strip()
    for prefix in ('```json', '```'):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    verdict = json.loads(text)
    missing = {'outcome', 'confidence', 'reasoning'} - verdict.keys()
    if missing:
        raise ValueError(f'Missing required keys: {sorted(missing)}')
    if verdict['outcome'] not in {'Reproduced', 'PartiallyReproduced', 'FailedToReproduce', 'UnableToAssess'}:
        raise ValueError(f'Invalid outcome {verdict["outcome"]!r}')
    if verdict['confidence'] not in {'High', 'Medium', 'Low'}:
        raise ValueError(f'Invalid confidence {verdict["confidence"]!r}')
    return verdict
