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


def form_verdicts(readme: str, actual_output: str) -> list:
    """Call Claude Haiku once per validator. Returns list of 3 verdict dicts."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY not set')

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a scientific validator. A researcher submitted a computational study and you have just executed their code.

STUDY BRIEF (from README):
{readme}

ACTUAL EXECUTION OUTPUT:
{actual_output}

Compare the actual output against what the README claims.
Reply with ONLY a JSON object — no markdown, no explanation:
{{
  "outcome": "Reproduced" | "PartiallyReproduced" | "FailedToReproduce" | "UnableToAssess",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "<one sentence>"
}}"""

    verdicts = []
    for i in range(3):
        messages: list = [{'role': 'user', 'content': prompt}]
        last_raw = ''
        for attempt in range(5):
            msg = client.messages.create(model=MODEL, max_tokens=256, messages=messages)
            last_raw = getattr(msg.content[0], 'text', '').strip()
            try:
                verdicts.append(_parse_verdict(last_raw))
                break
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                if attempt == 4:
                    raise RuntimeError(
                        f'Validator {i + 1} failed to return valid JSON after 5 attempts. '
                        f'Last response: {last_raw}'
                    )
                messages.append({'role': 'assistant', 'content': last_raw})
                messages.append({
                    'role': 'user',
                    'content': f'That response could not be parsed. Error: {exc}. Reply with ONLY the corrected JSON.',
                })
    return verdicts


def _node_post(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Node API {url} returned {e.code}: {body}')
    except OSError as e:
        raise RuntimeError(f'Cannot reach {url}: {e}')
    if 'error' in result:
        raise RuntimeError(f'Node API error from {url}: {result["error"]}')
    return result


def _node_get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'ValiChord-Demo/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Node API {url} returned {e.code}: {body}')
    except OSError as e:
        raise RuntimeError(f'Cannot reach {url}: {e}')


def run_protocol(data_hash: str, metrics: list, verdicts: list, job: dict) -> dict:
    """Run the decentralised commit-reveal protocol via Oracle node HTTP APIs."""
    disc = {'type': 'ComputationalBiology'}

    lock_resp = _node_post(f'{RESEARCHER_URL}/lock-result', {
        'data_hash_hex': data_hash, 'metrics': metrics,
    })
    external_hash_b64 = lock_resp['external_hash_b64']

    _node_post(f'{RESEARCHER_URL}/submit-request', {
        'external_hash_b64': external_hash_b64,
        'discipline': disc,
        'num_validators_required': 3,
    })

    time.sleep(20)  # let ValidationRequest propagate via DHT gossip

    for i, (vurl, verdict) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f'{vurl}/commit', {
            'external_hash_b64': external_hash_b64,
            'verdict': verdict,
            'metrics': metrics,
            'discipline': disc,
        })
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(30)

    job['step'] = 5

    phase_url = f'{RESEARCHER_URL}/phase?hash={urllib.parse.quote(external_hash_b64)}'
    for _ in range(120):
        phase_resp = _node_get(phase_url)
        if phase_resp.get('phase') == 'RevealOpen':
            break
        time.sleep(2)
    else:
        raise RuntimeError('Phase gate did not open after 240 seconds')

    reveal_resp = _node_post(f'{RESEARCHER_URL}/reveal', {
        'external_hash_b64': external_hash_b64, 'metrics': metrics,
    })
    researcher_reveal_hash = reveal_resp.get('researcher_reveal_hash')

    for i, (vurl, _) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f'{vurl}/reveal', {'external_hash_b64': external_hash_b64})
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(15)

    job['step'] = 6

    harmony_resp = _node_post(f'{VALIDATOR_URLS[0]}/create-harmony-record', {
        'external_hash_b64': external_hash_b64,
    })
    harmony_record_hash = harmony_resp.get('harmony_record_hash')
    if not harmony_record_hash:
        raise RuntimeError(
            f'HarmonyRecord was not written to the DHT after all gossip retries '
            f'(external_hash={external_hash_b64[:20]}…). '
            f'The commit-reveal round completed but the record is not yet retrievable.'
        )

    outcomes = [v['outcome'] for v in verdicts]
    n_reproduced = outcomes.count('Reproduced')
    n_partial    = outcomes.count('PartiallyReproduced')
    rate = (n_reproduced + n_partial) / len(outcomes)
    agreement_level = (
        'ExactMatch'       if rate >= 0.90 else
        'WithinTolerance'  if rate >= 0.70 else
        'DirectionalMatch' if rate >= 0.50 else
        'Divergent'        if n_reproduced + n_partial > 0 else
        'UnableToAssess'
    )
    majority_outcome = (
        'Reproduced'          if n_reproduced >= 2 else
        'PartiallyReproduced' if n_partial    >= 2 else
        'FailedToReproduce'   if outcomes.count('FailedToReproduce') >= 2 else
        'UnableToAssess'
    )

    return {
        'harmony_record_hash':    harmony_record_hash,
        'external_hash_b64':      external_hash_b64,
        'outcome':                majority_outcome,
        'agreement_level':        agreement_level,
        'validator_count':        3,
        'researcher_reveal_hash': researcher_reveal_hash,
        'record_url':             f'{RESEARCHER_URL}/record?hash={urllib.parse.quote(external_hash_b64)}',
        'validator_verdicts': [
            {
                'validator':  i + 1,
                'outcome':    v['outcome'],
                'confidence': v['confidence'],
                'reasoning':  v['reasoning'],
            }
            for i, v in enumerate(verdicts)
        ],
    }
