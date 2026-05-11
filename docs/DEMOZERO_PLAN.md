# DemoZero — 9-Validator ZeroClaw Integration Plan

**Codename:** DemoZero  
**Goal:** Replace the current single-model `form_verdicts()` call with 9 independent ZeroClaw validator agents — 3 each of Claude, Mistral, and Llama — wired into the existing ValiChord commit-reveal protocol.

---

## Why this is compelling

The current demo calls Claude 3 times in `form_verdicts()` — three instances of the same model, same API key, sequential. With DemoZero:

- 9 genuinely independent LLM agents, each running in its own ZeroClaw process
- 3 provider groups with different model families — independence is architectural, not synthetic
- Gold badge (`ExactMatch` + `count ≥ 7`) becomes reachable in the demo for the first time
- ZeroClaw's AIEOS identity system gives each validator a distinct named persona
- Infrastructure is trivially cheap: 9 × ~5 MB binary, all on a single machine or spread across $10 boards

---

## What does NOT need to change in Holochain

The Rust aggregation is already N-agnostic. Verified in `valichord/shared_types/src/lib.rs`:

- `derive_majority_outcome()` — uses counts + max, works for any N
- `derive_agreement_level()` — percentage thresholds (90% / 70% / 50%), works for any N
- `evaluate_badge()` — thresholds at `count ≥ 7` (Gold), `≥ 5` (Silver), `≥ 3` (Bronze); N=9 unlocks Gold

**No coordinator or integrity zome changes needed. No DNA hash change.**

**`num_validators_required` — no zome changes needed.** Investigation confirmed (`attestation_integrity/src/lib.rs:70`) that `num_validators_required` is a field on the `ValidationRequest` entry type set per-request by the caller, not a hardcoded constant. To use 9 validators, simply pass `num_validators_required: 9` when creating the ValidationRequest. No integrity or coordinator zome edits required.

---

## Architecture

```
ValiChord ai_validator.py
    │
    ├─ POST /webhook → ZeroClaw A1 :8081  (Claude,   claude-sonnet-4-6)
    ├─ POST /webhook → ZeroClaw A2 :8082  (Claude,   claude-sonnet-4-6)
    ├─ POST /webhook → ZeroClaw A3 :8083  (Claude,   claude-sonnet-4-6)
    │
    ├─ POST /webhook → ZeroClaw B1 :8084  (OpenRouter, mistralai/mistral-large ⚠️ slug unconfirmed)
    ├─ POST /webhook → ZeroClaw B2 :8085  (OpenRouter, mistralai/mistral-large ⚠️ slug unconfirmed)
    ├─ POST /webhook → ZeroClaw B3 :8086  (OpenRouter, mistralai/mistral-large ⚠️ slug unconfirmed)
    │
    ├─ POST /webhook → ZeroClaw C1 :8087  (OpenRouter, meta-llama/llama-3.3-70b-instruct ⚠️ slug unconfirmed)
    ├─ POST /webhook → ZeroClaw C2 :8088  (OpenRouter, meta-llama/llama-3.3-70b-instruct ⚠️ slug unconfirmed)
    └─ POST /webhook → ZeroClaw C3 :8089  (OpenRouter, meta-llama/llama-3.3-70b-instruct ⚠️ slug unconfirmed)
```

All 9 calls are made in parallel (threads). Wall time ≈ slowest single call, not 9 × call.

**API keys required:**
- `ANTHROPIC_API_KEY` — already in use
- `OPENROUTER_API_KEY` — one key covers both Mistral and Llama via OpenRouter

---

## Step 1 — Build ZeroClaw

ZeroClaw is a Rust binary. Build once, reuse for all 9 instances.

```bash
git clone https://github.com/zeroclaw-labs/zeroclaw.git /opt/zeroclaw-src
cd /opt/zeroclaw-src
cargo build --release --locked
# Binary at: /opt/zeroclaw-src/target/release/zeroclaw
# Or install globally:
cargo install --path . --force --locked
```

No Docker image is published; build from source. The `Dockerfile` in the repo is for sandboxed runtime mode, not needed here — all validators run in `runtime.kind = "native"`.

---

## Step 2 — The ValiChord Validation Skill

Each ZeroClaw instance loads this skill from its workspace. The skill enforces JSON output so `ai_validator.py` can parse the response reliably.

**Skill injection risk** (investigation, `skills/mod.rs:882`): in ZeroClaw's default `Full` mode, all SKILL.md content is injected into every LLM call as part of the system prompt. There is no priority ordering — a conflicting instruction in any installed skill could override the JSON format requirement. Keep each instance's workspace clean: the `valichord-validation` skill must be the only skill present, and the SKILL.md must not contain any instruction that contradicts JSON-only output.

**File:** `demo/zeroclaw/skills/valichord-validation/SKILL.md`

```markdown
# valichord-validation

You are an independent scientific validator in the ValiChord reproducibility protocol.

Your task: assess whether an independent researcher following the described method
would arrive at the same result as the original researcher.

**Return ONLY a single JSON object — no prose, no fences, no explanation outside it:**

{
  "outcome": "Reproduced" | "PartiallyReproduced" | "FailedToReproduce" | "UnableToAssess",
  "confidence": "Low" | "Medium" | "High",
  "reasoning": "<2–3 sentences explaining your assessment>"
}

Definitions:
- "Reproduced": the method would predictably yield the same result
- "PartiallyReproduced": the method yields a qualitatively similar but not identical result
- "FailedToReproduce": the method would not yield the same result
- "UnableToAssess": insufficient information to make a determination

Critical rule: ValiChord assesses reproducibility ONLY — not correctness.
A study can be reproducible and scientifically wrong. Do not conflate them.
```

---

## Step 3 — ZeroClaw Config Files

Create one config file per group (A, B, C). Instances within a group share the same config
(they are identical). Mount or symlink as needed per instance.

**`demo/zeroclaw/config-a.toml`** (Claude — Group A)

```toml
api_key = "${ANTHROPIC_API_KEY}"
default_provider = "anthropic"
default_model = "claude-sonnet-4-6"
default_temperature = 0.7

[memory]
backend = "none"

[gateway]
require_pairing = false
allow_public_bind = false

[autonomy]
level = "readonly"
workspace_only = true
allowed_commands = []

[runtime]
kind = "native"

[secrets]
encrypt = false

[identity]
format = "aieos"
aieos_inline = '''
{"identity":{"names":{"first":"Aura","nickname":"A"}},
 "psychology":{"neural_matrix":{"logic":0.9,"creativity":0.6}},
 "motivations":{"core_drive":"Verify scientific claims with rigour"}}
'''
```

**`demo/zeroclaw/config-b.toml`** (Mistral — Group B)

```toml
api_key = "${OPENROUTER_API_KEY}"
default_provider = "openrouter"
default_model = "mistralai/mistral-large"  # ⚠️ slug unconfirmed — verify at https://openrouter.ai/models
default_temperature = 0.7

[memory]
backend = "none"

[gateway]
require_pairing = false
allow_public_bind = false

[autonomy]
level = "readonly"
workspace_only = true
allowed_commands = []

[runtime]
kind = "native"

[secrets]
encrypt = false

[identity]
format = "aieos"
aieos_inline = '''
{"identity":{"names":{"first":"Boreas","nickname":"B"}},
 "psychology":{"neural_matrix":{"logic":0.85,"creativity":0.7}},
 "motivations":{"core_drive":"Cross-check research claims independently"}}
'''
```

**`demo/zeroclaw/config-c.toml`** (Llama — Group C)

```toml
api_key = "${OPENROUTER_API_KEY}"
default_provider = "openrouter"
default_model = "meta-llama/llama-3.3-70b-instruct"  # ⚠️ slug unconfirmed — verify at https://openrouter.ai/models
default_temperature = 0.7

[memory]
backend = "none"

[gateway]
require_pairing = false
allow_public_bind = false

[autonomy]
level = "readonly"
workspace_only = true
allowed_commands = []

[runtime]
kind = "native"

[secrets]
encrypt = false

[identity]
format = "aieos"
aieos_inline = '''
{"identity":{"names":{"first":"Callux","nickname":"C"}},
 "psychology":{"neural_matrix":{"logic":0.8,"creativity":0.75}},
 "motivations":{"core_drive":"Assess reproducibility with open scrutiny"}}
'''
```

**Note on `require_pairing = false`:** The gateways are bound to `127.0.0.1` (default), so they are
not publicly reachable. Disabling pairing is safe for local demo use.

---

## Step 4 — Startup Script

**`demo/start-zeroclaw-validators.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

ZEROCLAW=${ZEROCLAW_BIN:-zeroclaw}
SKILL_DIR="$(cd "$(dirname "$0")/zeroclaw/skills" && pwd)"
CONFIG_DIR="$(cd "$(dirname "$0")/zeroclaw" && pwd)"

# Expand env vars in config files at runtime
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?Need ANTHROPIC_API_KEY}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:?Need OPENROUTER_API_KEY}"

start_validator() {
    local name=$1 config=$2 port=$3
    local workspace="/tmp/zeroclaw-$name"
    mkdir -p "$workspace/skills/valichord-validation"
    cp "$SKILL_DIR/valichord-validation/SKILL.md" "$workspace/skills/valichord-validation/"
    # Substitute env vars into config
    envsubst < "$CONFIG_DIR/$config" > "$workspace/config.toml"
    ZEROCLAW_CONFIG_DIR="$workspace" \
    ZEROCLAW_WORKSPACE="$workspace" \
    "$ZEROCLAW" gateway --port "$port" &
    echo "Started $name on port $port (PID $!)"
}

# Group A — Claude
start_validator zeroclaw-a1 config-a.toml 8081
start_validator zeroclaw-a2 config-a.toml 8082
start_validator zeroclaw-a3 config-a.toml 8083

# Group B — Mistral
start_validator zeroclaw-b1 config-b.toml 8084
start_validator zeroclaw-b2 config-b.toml 8085
start_validator zeroclaw-b3 config-b.toml 8086

# Group C — Llama
start_validator zeroclaw-c1 config-c.toml 8087
start_validator zeroclaw-c2 config-c.toml 8088
start_validator zeroclaw-c3 config-c.toml 8089

echo "All 9 ZeroClaw validators started."
wait
```

**Env vars confirmed** (investigation, `crates/zeroclaw-config/src/schema.rs:9714` and `:69`):
`ZEROCLAW_CONFIG_DIR` sets the config directory (ZeroClaw reads `config.toml` from it);
`ZEROCLAW_WORKSPACE` sets the workspace directory. Both are used above.

---

## Step 5 — `demo/ai_validator.py` Changes

### 5a — Validator URL list

Replace the three-URL block (lines ~69–72) with:

```python
# ── DemoZero: 9 ZeroClaw validator gateways ───────────────────────────────────
# Group A — Claude (ports 8081–8083)
# Group B — Mistral via OpenRouter (ports 8084–8086)
# Group C — Llama via OpenRouter (ports 8087–8089)
_DEFAULT_VALIDATOR_PORTS = range(8081, 8090)
VALIDATOR_URLS = [
    os.environ.get(f'VALICHORD_VALIDATOR_{i}_URL', f'http://localhost:{p}')
    for i, p in enumerate(_DEFAULT_VALIDATOR_PORTS, 1)
]
VALIDATOR_GROUPS = [
    ('Claude',   VALIDATOR_URLS[0:3]),
    ('Mistral',  VALIDATOR_URLS[3:6]),
    ('Llama',    VALIDATOR_URLS[6:9]),
]
```

### 5b — Replace `form_verdicts()`

Replace the entire function with:

```python
import concurrent.futures

def form_verdicts(readme: str, actual_output: str) -> list:
    """Call all 9 ZeroClaw validator gateways in parallel; return list of verdict dicts."""
    n = len(VALIDATOR_URLS)
    banner(3, 7, f'Forming {n} independent verdicts via ZeroClaw (parallel)…')

    prompt = (
        f"Research deposit README:\n\n{readme}\n\n"
        f"Claimed output:\n\n{actual_output}\n\n"
        "Assess reproducibility and return your verdict as JSON."
    )

    _REQUIRED_KEYS    = {'outcome', 'confidence', 'reasoning'}
    _VALID_OUTCOMES   = {
        'Reproduced', 'PartiallyReproduced', 'FailedToReproduce', 'UnableToAssess',
    }
    _VALID_CONFIDENCE = {'Low', 'Medium', 'High'}

    def _parse_verdict(raw: str) -> dict:
        text = raw.strip()
        # Strip ```json fences if present
        if text.startswith('```'):
            text = re.sub(r'^```[a-z]*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        verdict = json.loads(text)
        missing = _REQUIRED_KEYS - verdict.keys()
        if missing:
            raise ValueError(f'Missing keys: {missing}')
        if verdict['outcome'] not in _VALID_OUTCOMES:
            raise ValueError(f'Invalid outcome: {verdict["outcome"]!r}')
        if verdict['confidence'] not in _VALID_CONFIDENCE:
            raise ValueError(f'Invalid confidence: {verdict["confidence"]!r}')
        return verdict

    def _call_validator(url: str, idx: int) -> dict:
        payload = json.dumps({'message': prompt}).encode()
        req = urllib.request.Request(
            f'{url}/webhook',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        last_error = None
        for attempt in range(1, 6):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = json.loads(resp.read())
                    # Confirmed: ZeroClaw gateway returns {"response": "...", "model": "..."}
                    # (crates/zeroclaw-gateway/src/lib.rs:~1516)
                    raw = body.get('response') or str(body)
                return _parse_verdict(raw)
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                print(f'  Validator {idx} attempt {attempt} parse error: {e}')
            except Exception as e:
                last_error = e
                print(f'  Validator {idx} attempt {attempt} HTTP error: {e}')
        raise RuntimeError(f'Validator {idx} failed after 5 attempts: {last_error}')

    verdicts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
        futures = {
            pool.submit(_call_validator, url, i): i
            for i, url in enumerate(VALIDATOR_URLS, 1)
        }
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                verdict = future.result()
                verdicts.append((idx, verdict))
                print(f'  Validator {idx}: {verdict["outcome"]} — {verdict["confidence"]} confidence')
            except Exception as e:
                print(f'  Validator {idx} FAILED: {e}')
                verdicts.append((idx, {
                    'outcome': 'UnableToAssess',
                    'confidence': 'Low',
                    'reasoning': f'Validator unreachable: {e}',
                }))

    # Sort by original index so downstream code sees validators 1–9 in order
    verdicts.sort(key=lambda x: x[0])
    verdicts = [v for _, v in verdicts]

    print()
    for group_name, group_urls in VALIDATOR_GROUPS:
        start = VALIDATOR_URLS.index(group_urls[0])
        group_verdicts = verdicts[start:start + 3]
        outcomes = [v['outcome'] for v in group_verdicts]
        print(f'  {group_name}: {outcomes}')

    return verdicts
```

### 5c — Fix the Python-side aggregation display (lines ~430–445)

The current hardcoded `>= 2` majority threshold is wrong for N=9. Replace:

```python
# OLD (hardcoded for N=3):
majority_outcome = (
    'FailedToReproduce' if outcomes.count('FailedToReproduce') >= 2 else ...
)

# NEW (N-agnostic):
from collections import Counter
majority_outcome = Counter(outcomes).most_common(1)[0][0]
```

This is display-only — the canonical aggregation runs in the Rust coordinator.
The percentage-based `agreement_level` calculation (rate = success_count / len) is already N-agnostic.

---

## Step 6 — Set `num_validators_required: 9` in the ValidationRequest

No zome changes needed. `num_validators_required` is a field on the `ValidationRequest` entry
type (`attestation_integrity/src/lib.rs:70`), set per-request by the caller. In `ai_validator.py`
(or whatever creates the request), pass `num_validators_required: 9`. The integrity zome enforces
`>= 1` and `>= props.minimum_validators` — verify `minimum_validators` in the DNA properties is
not set above 9, but no code changes are required.

---

## Step 7 — Expected Badge Outcomes for N=9

With `derive_agreement_level` thresholds (verified in `shared_types/src/lib.rs`):

| Reproduced count | full_rate | Outcome         | Badge              |
|---|---|---|---|
| 9/9              | 100%      | ExactMatch      | **Gold** ✨        |
| 8/9              | 88.8%     | WithinTolerance | **Silver**         |
| 7/9              | 77.7%     | WithinTolerance | **Silver**         |
| 6/9              | 66.6%     | DirectionalMatch| Bronze             |
| ≤4/9             | ≤44.4%    | Divergent       | FailedReproduction |

Gold is now reachable. For the demo's synthetic study (designed to reproduce cleanly),
all 9 validators should agree → Gold badge.

---

## Step 8 — Testing the Integration

Before wiring into the full Holochain protocol, test ZeroClaw in isolation:

```bash
# 1. Start one validator
./demo/start-zeroclaw-validators.sh   # or just one instance for smoke test

# 2. Hit it manually — response key is "response" (confirmed)
curl -s -X POST http://localhost:8081/webhook \
  -H 'Content-Type: application/json' \
  -d '{"message": "The study runs linear_regression.py on data.csv and reports R²=0.92. The output matches. Assess reproducibility and return JSON verdict."}' \
  | python3 -m json.tool
# Expected: {"response": "{\"outcome\": ..., \"confidence\": ..., \"reasoning\": ...}", "model": "..."}

# 3. Run full demo
python3 demo/ai_validator.py
```

---

## Step 9 — File Layout Summary

```
demo/
  zeroclaw/
    config-a.toml          # Claude config (shared by A1, A2, A3)
    config-b.toml          # Mistral config (shared by B1, B2, B3)
    config-c.toml          # Llama config (shared by C1, C2, C3)
    skills/
      valichord-validation/
        SKILL.md           # Verdict schema + reproducibility framing
  start-zeroclaw-validators.sh   # Launches all 9 instances
  ai_validator.py                # Modified (Steps 5a–5c above)
```

No new Holochain files. No new Rust. No DNA hash change.

---

## Hard Constraints (from CLAUDE.md — do not violate)

1. **Never use `pack_dna.py`** — always `hc dna pack` + `hc app pack`
2. **Holochain ≠ blockchain** — ZeroClaw validators are "independent agents on a peer-to-peer network", not "nodes on a blockchain"
3. **Before running tests:** `pkill -f holochain; pkill -f lair-keystore; sleep 2`
4. **Coordinator-only changes** (no integrity zome edits) keep the DNA hash stable
5. **`num_validators_required` requires no zome change** — it is a per-request field, not a constant; see Step 6

---

## Open Questions for the Implementing Session

All operational questions from the original plan are now resolved (see `docs/zeroclaw_investigation.md`). One remains:

1. **OpenRouter model slugs** — `mistralai/mistral-large` and `meta-llama/llama-3.3-70b-instruct`
   were not confirmed as valid slugs as of 2026-05-11 (investigation checked `/api/v1/models`).
   Available Mistral models at that time: `mistralai/mistral-medium-3.5`, `mistralai/mistral-small-2603`.
   **Before implementing:** verify current slugs at https://openrouter.ai/models and update
   `config-b.toml`, `config-c.toml`, and the architecture diagram above.
