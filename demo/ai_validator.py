#!/usr/bin/env python3
"""
ValiChord AI Validator Demo
============================
Executes a synthetic study, forms a verdict via Claude, and runs the full
commit-reveal protocol, producing a permanent HarmonyRecord on the DHT.

Prerequisites
-------------
1. Full demo stack running:
     bash demo/start.sh
2. HTTP Gateway running (in a second terminal):
     bash demo/start-gateway.sh
3. Flask backend running (in a third terminal):
     cd backend && flask run --host=0.0.0.0 --port=5000
4. Environment variables set:
     ANTHROPIC_API_KEY=<your key>
     HOLOCHAIN_GATEWAY_URL=http://localhost:8090          # or public URL
     HOLOCHAIN_GOVERNANCE_DNA_HASH=<from setup.mjs output>
     HOLOCHAIN_APP_ID=valichord-demo                      # default

Usage
-----
    python3 demo/ai_validator.py
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEMO_DIR    = Path(__file__).parent
STUDY_DIR   = DEMO_DIR / 'synthetic_study'

# Auto-load holochain-config.env (written by start_oracle.sh / documented in README).
# Uses setdefault so any var already in the environment takes precedence.
def _load_config_env():
    env_file = DEMO_DIR / 'holochain-config.env'
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())

_load_config_env()

BRIDGE_URL      = os.environ.get('VALICHORD_BRIDGE_URL', 'http://localhost:8888')
VALICHORD_KEY   = os.environ.get('VALICHORD_API_KEY', '')

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(n, total, msg):
    print(f'\n[{n}/{total}] {msg}')
    print('─' * 60)

def die(msg):
    print(f'\nFATAL: {msg}', file=sys.stderr)
    sys.exit(1)

# ── Step 1: Load study ────────────────────────────────────────────────────────

def load_study():
    banner(1, 7, 'Loading study deposit…')
    if not STUDY_DIR.exists():
        die(f'synthetic_study/ not found at {STUDY_DIR}')

    readme = (STUDY_DIR / 'README.md').read_text()

    # Package into a ZIP (exactly as a real researcher would submit)
    tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(STUDY_DIR.iterdir()):
            zf.write(f, f.name)

    # SHA-256 of the data file salted with a per-run UUID.
    # In production every real deposit is a unique file — the salt makes each
    # demo run behave the same way: a fresh study that has never been claimed.
    data_bytes = (STUDY_DIR / 'data.csv').read_bytes()
    run_id     = uuid.uuid4().bytes          # 16 random bytes, unique per run
    data_hash  = hashlib.sha256(data_bytes + run_id).hexdigest()

    print(f'  ZIP:       {tmp.name}')
    print(f'  Run ID:    {uuid.UUID(bytes=run_id)}')
    print(f'  Data hash: {data_hash[:24]}…  ({len(data_bytes)} bytes)')
    return readme, data_hash, tmp.name

# ── Step 2: Execute study code ────────────────────────────────────────────────

def execute_study():
    banner(2, 7, 'Executing study code…')
    script = STUDY_DIR / 'study.py'
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=60,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        die(f'Study script exited {result.returncode}:\n{result.stderr}')

    output = result.stdout.strip()
    print(f'  Output:\n    ' + output.replace('\n', '\n    '))
    print(f'  Elapsed: {elapsed:.2f}s')
    return output

# ── Step 3: Form verdict via Claude ───────────────────────────────────────────

def form_verdict(readme: str, actual_output: str) -> dict:
    banner(3, 7, 'Forming verdict via Claude…')

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        die('ANTHROPIC_API_KEY not set.')

    try:
        import anthropic
    except ImportError:
        die('anthropic package not installed. Run: pip install anthropic')

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

    message = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=256,
        messages=[{'role': 'user', 'content': prompt}],
    )

    raw = message.content[0].text.strip()
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        die(f'Claude returned non-JSON verdict:\n{raw}')

    print(f'  Outcome:    {verdict["outcome"]}')
    print(f'  Confidence: {verdict["confidence"]}')
    print(f'  Reasoning:  {verdict["reasoning"]}')
    return verdict

# ── Steps 4–6: Commit-reveal round via bridge ─────────────────────────────────

OUTCOME_TO_AGREEMENT = {
    'Reproduced':          'ExactMatch',
    'PartiallyReproduced': 'DirectionalMatch',
    'FailedToReproduce':   'Divergent',
    'UnableToAssess':      'UnableToAssess',
}

def run_commit_reveal(data_hash: str, verdict: dict) -> dict:
    banner(4, 7, 'Sealing commitment to DHT…')
    print('  Submitting validation round to Holochain bridge…')
    print('  (This runs the full 7-step commit-reveal protocol internally)')

    try:
        import urllib.request
        payload = json.dumps({
            'data_hash_hex':      data_hash,
            'outcome':            {'type': verdict['outcome']},
            'discipline':         {'type': 'ComputationalBiology'},
            'confidence':         verdict['confidence'],
            'deposit_access_type': 'PublicUrl',
            'data_access_url':    '',
        }).encode()

        headers = {'Content-Type': 'application/json'}
        if VALICHORD_KEY:
            headers['X-ValiChord-Key'] = VALICHORD_KEY

        req = urllib.request.Request(
            f'{BRIDGE_URL}/holochain/validate-round',
            data=payload,
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        die(f'Bridge returned {e.code}: {body}')
    except OSError as e:
        die(
            f'Cannot reach Holochain bridge at {BRIDGE_URL}.\n'
            f'  Is the demo stack running?  bash demo/start.sh\n'
            f'  Error: {e}'
        )

    if 'error' in result:
        die(f'Bridge error: {result["error"]}')

    print('  CommitmentAnchor written.')
    banner(5, 7, 'Attestation revealed and hash verified.')
    banner(6, 7, 'HarmonyRecord written to Governance DHT.')
    return result

# ── Step 7: Display permanent URL ─────────────────────────────────────────────

def display_result(result: dict):
    banner(7, 7, 'Permanent record.')

    harmony_hash    = result.get('harmony_record_hash')
    gateway_payload = result.get('gateway_payload')

    # Summary fields returned directly by the bridge (no msgpack decoding needed).
    outcome_type    = result.get('outcome_type',    'Unknown')
    confidence      = result.get('confidence',      'Unknown')
    discipline_type = result.get('discipline_type', 'Unknown')
    agreement_level = result.get('agreement_level', 'Unknown')
    validator_count = result.get('validator_count', 1)

    print(f'  Outcome:           {outcome_type}')
    print(f'  Agreement level:   {agreement_level}')
    print(f'  Confidence:        {confidence}')
    print(f'  Discipline:        {discipline_type}')
    print(f'  Validators:        {validator_count}')
    print(f'  HarmonyRecord:     {harmony_hash}')

    gateway_url = os.environ.get('HOLOCHAIN_GATEWAY_URL', '').rstrip('/')
    dna_hash    = os.environ.get('HOLOCHAIN_GOVERNANCE_DNA_HASH', '')
    app_id      = os.environ.get('HOLOCHAIN_APP_ID', 'valichord-demo')

    if gateway_url and dna_hash and gateway_payload:
        # URL-encode the payload: = padding must be %3D in query strings.
        encoded_payload = gateway_payload.replace('=', '%3D')
        url = (
            f'{gateway_url}/{dna_hash}/{app_id}'
            f'/governance_coordinator/get_harmony_record'
            f'?payload={encoded_payload}'
        )
        print(f'\n  Permanent URL:\n  {url}')

        # Verify the URL is live — proves the record is on the DHT.
        print('\n  Verifying record is readable via HTTP Gateway…')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ValiChord-Demo/1.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()   # consume body; 200 is sufficient proof
            print('  Record confirmed on DHT.')
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode('utf-8', errors='replace')
            print(f'  WARNING: Gateway returned HTTP {e.code}: {body_txt}')
        except OSError as e:
            print(f'  WARNING: Could not reach gateway: {e}')
    else:
        print(
            '\n  (Set HOLOCHAIN_GATEWAY_URL + HOLOCHAIN_GOVERNANCE_DNA_HASH'
            ' to generate the public URL)'
        )

    print('\n' + '═' * 60)
    print('  Demo complete. The protocol ran end-to-end.')
    print('═' * 60)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('╔══════════════════════════════════════════════════════════╗')
    print('║         ValiChord AI Validator Demo                     ║')
    print('╚══════════════════════════════════════════════════════════╝')

    readme, data_hash, _zip = load_study()
    actual_output            = execute_study()
    verdict                  = form_verdict(readme, actual_output)
    result                   = run_commit_reveal(data_hash, verdict)
    display_result(result)

if __name__ == '__main__':
    main()
