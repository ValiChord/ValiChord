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
import re
import subprocess
import sys
import time
import uuid
import zipfile
import tempfile
import urllib.error
import urllib.parse
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
# Public-facing server (port 5000) — used for shareable /record/ URLs.
# Set automatically by start_oracle.sh; falls back to BRIDGE_URL for remote runs
# where VALICHORD_BRIDGE_URL already points to the public server.
PUBLIC_URL      = os.environ.get('VALICHORD_PUBLIC_URL', BRIDGE_URL)

# ── Decentralised mode node URLs ──────────────────────────────────────────────
# Defaults align with docker-compose.yml port mappings (host-side).
RESEARCHER_URL   = os.environ.get('VALICHORD_RESEARCHER_URL',  'http://localhost:3001')
VALIDATOR_1_URL  = os.environ.get('VALICHORD_VALIDATOR_1_URL', 'http://localhost:3002')
VALIDATOR_2_URL  = os.environ.get('VALICHORD_VALIDATOR_2_URL', 'http://localhost:3003')
VALIDATOR_3_URL  = os.environ.get('VALICHORD_VALIDATOR_3_URL', 'http://localhost:3004')

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

# ── Step 2b: Parse metrics from study output ──────────────────────────────────

# Expected values for the synthetic study — compared against actual output
# to populate MetricResult.within_tolerance.
_EXPECTED = {
    'slope':     '2.4086',
    'intercept': '1.1742',
    'r2':        '0.9991',
}

def parse_metrics(output: str) -> list:
    """Extract structured MetricResult objects from study.py stdout."""
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
        for name, expected in _EXPECTED.items()
    ]


# ── Step 3: Form 3 independent verdicts via Claude ────────────────────────────

def form_verdicts(readme: str, actual_output: str) -> list:
    """Make 3 separate Claude calls — each is an independent validator."""
    banner(3, 7, 'Forming 3 independent verdicts via Claude…')

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

    verdicts = []
    for i in range(3):
        print(f'  Calling Claude (validator {i + 1}/3)…', end=' ', flush=True)
        message = client.messages.create(
            model='claude-opus-4-6',
            max_tokens=256,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            verdict = json.loads(raw)
        except json.JSONDecodeError:
            die(f'Claude (validator {i + 1}) returned non-JSON:\n{raw}')
        print(f'{verdict["outcome"]} — {verdict["confidence"]} confidence')
        verdicts.append(verdict)

    print()
    for i, v in enumerate(verdicts, 1):
        print(f'  Validator {i}: {v["outcome"]} ({v["confidence"]}) — {v["reasoning"]}')
    return verdicts

# ── Decentralised protocol helpers ───────────────────────────────────────────

def _node_post(url, payload, timeout=600):
    """POST JSON to a node API endpoint; raise on HTTP error."""
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        die(f'Node API {url} returned {e.code}: {body}')
    except OSError as e:
        die(f'Cannot reach {url}: {e}')
    if 'error' in result:
        die(f'Node API error from {url}: {result["error"]}')
    return result


def _node_get(url, timeout=30):
    """GET a node API endpoint; raise on HTTP error."""
    req = urllib.request.Request(url, headers={'User-Agent': 'ValiChord-Demo/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        die(f'Node API {url} returned {e.code}: {body}')
    except OSError as e:
        die(f'Cannot reach {url}: {e}')


def _wait_for_nodes():
    """Poll /health on all four node APIs until they respond."""
    urls = [
        (RESEARCHER_URL, 'researcher'),
        (VALIDATOR_1_URL, 'validator-1'),
        (VALIDATOR_2_URL, 'validator-2'),
        (VALIDATOR_3_URL, 'validator-3'),
    ]
    print('  Waiting for node APIs to be ready…')
    for base_url, label in urls:
        health_url = f'{base_url}/health'
        for attempt in range(120):
            try:
                result = _node_get(health_url, timeout=5)
                if result.get('status') == 'ok':
                    break
            except SystemExit:
                pass
            if attempt == 119:
                die(f'{label} node API not ready after 120 attempts: {health_url}')
            time.sleep(2)
            if attempt == 0:
                print(f'    Waiting for {label}…', end=' ', flush=True)
            else:
                print('.', end='', flush=True)
        print(f' {label} ready.')


def run_decentralised_protocol(data_hash: str, metrics: list, verdicts: list) -> dict:
    """
    Run the commit-reveal protocol across four separate node APIs.

    Each node API talks only to its local Holochain conductor; the conductors
    communicate through the shared DHT.  This mirrors a real multi-party
    deployment where researcher and validators run on separate machines.

    Protocol steps:
      (0) Researcher locks result (DNA 1 → commitment hash on DNA 3)
      (1) Researcher submits ValidationRequest (DNA 3)
      (2–4) Each validator commits blind (DNA 2 post_commit → CommitmentAnchor DNA 3)
      (5) Poll phase gate until RevealOpen
      (6a) Researcher reveals (SHA-256 verified on-chain, DNA 3)
      (6b) Validators reveal (SHA-256 verified on-chain, DNA 3)
      (7) Validator-1 creates HarmonyRecord (DNA 4)
    """
    banner(4, 7, 'Running decentralised commit-reveal protocol…')
    print('  Mode: DECENTRALISED — 5 separate conductors communicating via DHT')
    print(f'  Researcher : {RESEARCHER_URL}')
    print(f'  Validator 1: {VALIDATOR_1_URL}')
    print(f'  Validator 2: {VALIDATOR_2_URL}')
    print(f'  Validator 3: {VALIDATOR_3_URL}')
    print()

    _wait_for_nodes()

    disc = {'type': 'ComputationalBiology'}
    validator_urls = [VALIDATOR_1_URL, VALIDATOR_2_URL, VALIDATOR_3_URL]

    # (0) Researcher locks result
    print('  (0) Researcher locking result…')
    lock_resp = _node_post(f'{RESEARCHER_URL}/lock-result', {
        'data_hash_hex': data_hash,
        'metrics':       metrics,
    })
    external_hash_b64 = lock_resp['external_hash_b64']
    print(f'      Commitment sealed: {external_hash_b64[:24]}…')

    # (1) Submit ValidationRequest
    print('  (1) Submitting ValidationRequest (num_validators_required=3)…')
    _node_post(f'{RESEARCHER_URL}/submit-request', {
        'external_hash_b64':      external_hash_b64,
        'discipline':             disc,
        'num_validators_required': 3,
    })

    # Let ValidationRequest gossip to all validator conductors before any
    # validator commits — avoids Guard 1 (Local lookup) missing the VR entry.
    print('  (1b) Waiting 20s for ValidationRequest to propagate via DHT…', flush=True)
    time.sleep(20)

    # (2–4) Validators commit blind — staggered to avoid simultaneous DHT
    # gossip spikes on single-machine deployments.
    for i, (vurl, verdict) in enumerate(zip(validator_urls, verdicts)):
        print(f'  ({2 + i}) Validator {i + 1} committing blind…')
        _node_post(f'{vurl}/commit', {
            'external_hash_b64': external_hash_b64,
            'verdict':           verdict,
            'metrics':           metrics,
            'discipline':        disc,
        })
        if i < len(validator_urls) - 1:
            time.sleep(30)  # let DHT gossip settle before next commit

    # (5) Phase gate — poll until RevealOpen
    print('  (5) Polling phase gate…', end=' ', flush=True)
    phase_url = f'{RESEARCHER_URL}/phase?hash={urllib.parse.quote(external_hash_b64)}'
    for attempt in range(120):
        phase_resp = _node_get(phase_url)
        if phase_resp.get('phase') is not None:
            print(f'RevealOpen (after {attempt + 1} poll{"s" if attempt else ""}).')
            break
        time.sleep(2)
        print('.', end='', flush=True)
    else:
        die('Phase gate did not open after 240 seconds.')

    # (6a) Researcher reveals
    print('  (6a) Researcher revealing metrics (SHA-256 verified on-chain)…')
    reveal_resp = _node_post(f'{RESEARCHER_URL}/reveal', {
        'external_hash_b64': external_hash_b64,
        'metrics':           metrics,
    })
    researcher_reveal_hash = reveal_resp.get('researcher_reveal_hash')

    # (6b) Validators reveal — staggered to avoid concurrent DHT write spikes.
    for i, vurl in enumerate(validator_urls):
        print(f'  (6b) Validator {i + 1} revealing attestation…')
        _node_post(f'{vurl}/reveal', {'external_hash_b64': external_hash_b64})
        if i < len(validator_urls) - 1:
            time.sleep(15)

    # (7) Create HarmonyRecord (via validator-1 — must be a participating validator)
    print('  (7)  Creating HarmonyRecord on Governance DHT…')
    harmony_resp = _node_post(f'{VALIDATOR_1_URL}/create-harmony-record', {
        'external_hash_b64': external_hash_b64,
    })
    harmony_record_hash = harmony_resp.get('harmony_record_hash')

    # Derive majority outcome + agreement level from the 3 verdicts.
    outcomes    = [v['outcome'] for v in verdicts]
    n_reproduced = outcomes.count('Reproduced')
    n_partial    = outcomes.count('PartiallyReproduced')
    rate         = (n_reproduced + n_partial) / len(outcomes)
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
        'outcome_type':           majority_outcome,
        'agreement_level':        agreement_level,
        'discipline_type':        disc['type'],
        'validator_count':        3,
        'researcher_reveal_hash': researcher_reveal_hash,
        'validator_verdicts': [
            {'validator': i + 1, 'outcome': v['outcome'],
             'confidence': v['confidence'], 'reasoning': v['reasoning']}
            for i, v in enumerate(verdicts)
        ],
        '_decentralised': True,
    }


# ── Steps 4–6: Full commit-reveal round via bridge ────────────────────────────
#
# Protocol sequence sent to /holochain/validate-round-multi:
#   (0) Researcher seals result commitment (DNA 1 → hash published to DNA 3)
#   (1) ValidationRequest submitted to shared DHT (num_validators_required=3)
#   (2–4) Each validator seals their verdict blind (CommitmentAnchors on DNA 3)
#   (5) Phase gate opens when all 3 CommitmentAnchors are on the DHT
#   (6a) Researcher reveal — SHA-256(msgpack(metrics) || nonce) verified on-chain
#   (6b) All 3 validators reveal their attestations
#   (7) HarmonyRecord written to Governance DHT (DNA 4)

def run_full_protocol(data_hash: str, metrics: list, verdicts: list) -> dict:
    banner(4, 7, 'Running commit-reveal protocol (researcher + 3 validators)…')
    print('  (0) Researcher sealing result commitment — blind, before any reveal')
    print('  (1) ValidationRequest published to shared DHT')
    print('  (2–4) 3 validators sealing blind commitments to DHT')
    print('  (5) Phase gate opens when all 3 CommitmentAnchors confirmed')
    print('  (6) Dual reveal: researcher + all 3 validators simultaneously')
    print('  (7) HarmonyRecord written to Governance DHT')
    print()
    print('  Submitting to Holochain bridge (may take 60–120 seconds)…')

    try:
        payload = json.dumps({
            'data_hash_hex': data_hash,
            'metrics':       metrics,
            'verdicts':      verdicts,
            'discipline':    {'type': 'ComputationalBiology'},
            'deposit_access_type': 'PublicUrl',
            'data_access_url':     '',
        }).encode()

        headers = {'Content-Type': 'application/json'}
        if VALICHORD_KEY:
            headers['X-ValiChord-Key'] = VALICHORD_KEY

        req = urllib.request.Request(
            f'{BRIDGE_URL}/holochain/validate-round-multi',
            data=payload,
            headers=headers,
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read())

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        die(f'Bridge returned {e.code}: {body}')
    except OSError as e:
        die(
            f'Cannot reach Holochain bridge at {BRIDGE_URL}.\n'
            f'  Is the demo stack running?  bash demo/start_oracle.sh --fresh\n'
            f'  Error: {e}'
        )

    if 'error' in result:
        die(f'Bridge error: {result["error"]}')

    banner(5, 7, 'All commitments sealed and revealed.')
    banner(6, 7, 'Researcher result verified + 3 validator attestations on DHT.')
    return result

# ── Step 7: Display permanent URL ─────────────────────────────────────────────

def display_result(result: dict):
    banner(7, 7, 'Permanent record.')

    harmony_hash       = result.get('harmony_record_hash')
    external_hash_b64  = result.get('external_hash_b64')
    gateway_payload    = result.get('gateway_payload')
    outcome_type       = result.get('outcome_type',    'Unknown')
    discipline_type    = result.get('discipline_type', 'Unknown')
    agreement_level    = result.get('agreement_level', 'Unknown')
    validator_count    = result.get('validator_count', 3)
    researcher_reveal  = result.get('researcher_reveal_hash')
    validator_verdicts = result.get('validator_verdicts', [])

    print(f'  Outcome:           {outcome_type} ({validator_count}/3 validators)')
    print(f'  Agreement level:   {agreement_level}')
    print(f'  Discipline:        {discipline_type}')
    print(f'  HarmonyRecord:     {harmony_hash}')

    if researcher_reveal:
        print(f'  Researcher reveal: {researcher_reveal}')

    if validator_verdicts:
        print()
        for v in validator_verdicts:
            print(f'  Validator {v["validator"]}: {v["outcome"]} ({v["confidence"]}) — {v["reasoning"]}')

    # ── Shareable viewer URL ────────────────────────────────────────────────────
    # In decentralised mode the public API is the researcher node.
    is_decentralised = result.get('_decentralised', False)
    public_base = RESEARCHER_URL if is_decentralised else PUBLIC_URL

    lookup_hash = external_hash_b64 or harmony_hash
    if lookup_hash:
        if is_decentralised:
            viewer_url = f'{public_base}/record?hash={urllib.parse.quote(lookup_hash)}'
        else:
            viewer_url = f'{public_base}/record/{lookup_hash}'
        print(f'\n  Shareable URL:\n  {viewer_url}')

        print('\n  Verifying record is readable…')
        try:
            req = urllib.request.Request(
                viewer_url, headers={'User-Agent': 'ValiChord-Demo/1.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                record_body = json.loads(resp.read())
            print(f'  Record confirmed. Outcome: {record_body.get("outcome")}  '
                  f'Agreement: {record_body.get("agreement_level")}  '
                  f'Validators: {record_body.get("validator_count")}')
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode('utf-8', errors='replace')
            print(f'  WARNING: Viewer returned HTTP {e.code}: {body_txt}')
        except OSError as e:
            print(f'  WARNING: Could not reach viewer: {e}')

    # ── Raw gateway URL (debugging only) ────────────────────────────────────────
    gateway_url = os.environ.get('HOLOCHAIN_GATEWAY_URL', '').rstrip('/')
    dna_hash    = os.environ.get('HOLOCHAIN_GOVERNANCE_DNA_HASH', '')
    app_id      = os.environ.get('HOLOCHAIN_APP_ID', 'valichord-researcher')

    if gateway_url and dna_hash and gateway_payload:
        raw_url = (
            f'{gateway_url}/{dna_hash}/{app_id}'
            f'/governance_coordinator/get_harmony_record'
            f'?payload={gateway_payload}'
        )
        print(f'\n  Raw gateway URL (curl-only):\n  {raw_url}')

    print('\n' + '═' * 60)
    print('  Demo complete. The full ValiChord protocol ran end-to-end.')
    print('  Researcher and 3 validators all commit-revealed simultaneously.')
    print('═' * 60)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # ── Mode selection ────────────────────────────────────────────────────────
    # --mode decentralised  : call four separate node APIs (docker-compose stack)
    # --mode centralised    : call single serve.mjs bridge (Oracle / legacy)
    # default               : decentralised if VALICHORD_RESEARCHER_URL is set,
    #                         otherwise centralised.
    args = sys.argv[1:]
    if '--mode' in args:
        idx  = args.index('--mode')
        mode = args[idx + 1] if idx + 1 < len(args) else 'centralised'
    elif os.environ.get('VALICHORD_RESEARCHER_URL'):
        mode = 'decentralised'
    else:
        mode = 'centralised'

    if mode not in ('centralised', 'decentralised'):
        die(f'Unknown mode: {mode!r}.  Use --mode centralised or --mode decentralised')

    print('╔══════════════════════════════════════════════════════════╗')
    print('║    ValiChord AI Validator Demo — 3 Validators           ║')
    print('╚══════════════════════════════════════════════════════════╝')
    print('  Researcher + 3 independent Claude validators.')
    print('  Both sides commit-reveal symmetrically — neither can change')
    print('  their result after the other has committed.')
    print(f'  Mode: {mode.upper()}')
    print()

    readme, data_hash, _zip = load_study()
    actual_output            = execute_study()
    metrics                  = parse_metrics(actual_output)
    verdicts                 = form_verdicts(readme, actual_output)

    if mode == 'decentralised':
        result = run_decentralised_protocol(data_hash, metrics, verdicts)
    else:
        result = run_full_protocol(data_hash, metrics, verdicts)

    display_result(result)

if __name__ == '__main__':
    main()
