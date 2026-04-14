# AI Validator Demo — Single Agent, Live Oracle Deployment
### Technical guide for developers

---

## What this demo is

A fully automated end-to-end run of the ValiChord protocol, in which a Claude AI agent acts as the validator. It loads a synthetic study, executes the study code, forms a blind verdict using the Claude API, runs the full commit-reveal protocol against a live Holochain conductor on an Oracle Cloud server, and writes a permanent HarmonyRecord to the Governance DHT that is publicly readable via HTTP.

This is not a simulation. Every step involves real zome calls to real Holochain DNA cells running on a live conductor. The HarmonyRecord written at the end is stored on the DHT and readable at a public URL for as long as the Oracle server is running.

The current version uses one AI validator. The next iteration will use three, so the commit-reveal protocol does what it promises at scale: each validator commits blind before any reveals, and the agreement level is computed from genuinely independent verdicts.

---

## What the demo proves

- **The protocol runs end-to-end.** Deposit → execution → verdict → commit → reveal → HarmonyRecord. No manual steps.
- **The commit is genuine.** The validator's verdict is cryptographically sealed on the DHT before the reveal phase opens. It cannot be changed after sealing.
- **The record is permanent and publicly verifiable.** Anyone can fetch the HarmonyRecord at the shareable URL — no Holochain node required, no API key, no authentication.
- **AI validators are first-class citizens.** The protocol does not distinguish between human and AI validators. The same zome functions, the same commit-reveal guarantees.

---

## What the demo is not claiming

- This is a single-validator round. With one validator, `agreement_level` is computed from a single attestation — meaningful in the single-agent case but not the same as multi-validator consensus. That is the next step.
- The synthetic study is designed to reproduce perfectly. Claude will always return `Reproduced` for this data. Disagreement between validators requires real studies with real variance — or deliberately varied study parameters.
- The conductor is running in development mode with a local bootstrap server. This is not a deployed peer network.

---

## Architecture of this demo

```
ai_validator.py
    │
    ├─ [Step 1] Load synthetic study from demo/synthetic_study/
    │           Package as ZIP, compute SHA-256(data + run_id) as ExternalHash
    │
    ├─ [Step 2] Execute demo/synthetic_study/study.py
    │           Captures stdout (slope, intercept, R²)
    │
    ├─ [Step 3] Call Claude API (claude-opus-4-6)
    │           Prompt: README + actual output → JSON verdict
    │           { outcome, confidence, reasoning }
    │
    └─ [Step 4–6] POST /holochain/validate-round → demo/serve.mjs
                  │
                  └─ _runValidationRound() (7 internal steps):
                      │
                      ├─ 0. publish_validator_profile       (attestation DNA)
                      ├─ 1. submit_validation_request        (attestation DNA)
                      ├─ 2. claim_study                      (attestation DNA)
                      ├─ 3. receive_task                     (validator_workspace DNA)
                      ├─ 4. seal_private_attestation         (validator_workspace DNA)
                      │       └─ post_commit → notify_commitment_sealed
                      │                      → CommitmentAnchor on shared DHT
                      ├─ 5. poll get_current_phase until RevealOpen
                      ├─ 6. submit_attestation               (attestation DNA)
                      └─ 7. check_and_create_harmony_record  (governance DNA)
                              └─ HarmonyRecord written to public DHT
```

After the round completes, `serve.mjs` returns summary fields directly (outcome, agreement level, confidence, discipline, ExternalHash). The ExternalHash is used to construct the shareable URL.

---

## Infrastructure

| Component | Detail |
|---|---|
| Oracle Cloud server | VM.Standard.A1.Flex, Ubuntu 22.04, port 5000 open |
| Holochain conductor | 0.6.0, single conductor, local bootstrap server (port 9000) |
| Bootstrap/SBD | `kitsune2-bootstrap-srv` 0.3.2 — pre-compiled binary in `demo/bin/` |
| Node.js bridge | `demo/serve.mjs`, port 8888 (internal) |
| Public API | `demo/serve.mjs`, port 5000 — exposes `/holochain/validate-round` (authenticated) and `/record/<hash>` (unauthenticated) |
| HTTP Gateway | `hc-http-gw` 0.3.1, port 8090 — exposes raw zome calls via HTTP |
| Conductor config | `demo/conductor-config.yaml` — local bootstrap, `signalAllowPlainText: true` |

The `kitsune2-bootstrap-srv` binary is committed to `demo/bin/` because Oracle's GCC toolchain fails to compile `aws-lc-sys` (a transitive dependency). The binary was compiled in GitHub Codespaces and committed directly.

---

## Running the demo on Oracle

### One-time setup

SSH to the Oracle server, then:

```bash
cd ~/valichord
git pull

# Install Node.js dependencies (first time only)
cd demo && npm install && cd ..

# Install Python dependencies (first time only)
pip install anthropic
```

### Starting the stack

```bash
export ANTHROPIC_API_KEY=sk-ant-...
bash demo/start_oracle.sh --fresh
```

`--fresh` clears `demo/conductor_data/` before starting. Required if Holochain WASM has changed since the last run, or if the previous run left a stale study claim. Without `--fresh`, a stale claim produces: *"Study is at capacity (1/1 validators already claimed)"*.

Wait for:
```
=== Stack is up ===
  HTTP Gateway:  http://<IP>:8090
  Public API:    http://<IP>:5000
```

### Running the demo

In the same terminal (or a new one):

```bash
python3 demo/ai_validator.py
```

### Expected output

```
[1/7] Loading study deposit…
  Data hash: <sha256>…

[2/7] Executing study code…
  Output:
    Slope (coefficient): 2.4086
    Intercept:           1.1742
    R²:                  0.9991

[3/7] Forming verdict via Claude…
  Outcome:    Reproduced
  Confidence: High
  Reasoning:  The actual output exactly matches the expected output…

[4/7] Sealing commitment to DHT…
  CommitmentAnchor written.

[5/7] Attestation revealed and hash verified.

[6/7] HarmonyRecord written to Governance DHT.

[7/7] Permanent record.
  Outcome:           Reproduced
  Agreement level:   ExactMatch
  HarmonyRecord:     uhCkk…

  Shareable URL:
  http://<IP>:5000/record/uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: {'type': 'Reproduced'}  Agreement: ExactMatch
```

### Running it remotely (no Oracle SSH required)

If the Oracle stack is already running, `ai_validator.py` can be run from any machine — including this Codespace — by pointing it at the public API:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_BRIDGE_URL=http://132.145.34.27:5000
export VALICHORD_API_KEY=valichord-demo-2026
python3 demo/ai_validator.py
```

The `VALICHORD_PUBLIC_URL` is derived automatically from `VALICHORD_BRIDGE_URL` when running remotely, so the shareable URL will be correct.

---

## The shareable URL

After a successful run, the demo prints a URL of the form:

```
http://132.145.34.27:5000/record/uhC8k<hash>
```

This endpoint (`GET /record/<external-hash-b64>`) is served by `demo/serve.mjs` on port 5000. It:

- Requires no authentication
- Decodes the ExternalHash (stripping the multibase `u` prefix before base64url-decoding)
- Calls `get_harmony_record(ExternalHash)` on the Governance DNA via the Holochain conductor
- Decodes the entry bytes with `@msgpack/msgpack` to extract `HarmonyRecord` struct fields
- Returns clean JSON: `{ harmony_record_hash, outcome, agreement_level, discipline, validator_count }`

The ExternalHash in the URL is the study's data hash (SHA-256 of `data.csv` + run UUID, promoted to a 39-byte Holochain ExternalHash via `hashFrom32AndType`). It is the lookup key for `get_harmony_record` — distinct from the ActionHash of the HarmonyRecord entry itself.

---

## Key files

| File | Role |
|---|---|
| `demo/ai_validator.py` | Python orchestrator — 7-step demo runner |
| `demo/serve.mjs` | Node.js bridge — AppWebsocket client + public API server |
| `demo/start_oracle.sh` | Stack startup script for Oracle (bootstrap + conductor + bridge + gateway) |
| `demo/conductor-config.yaml` | Holochain conductor config — local bootstrap, dev mode |
| `demo/synthetic_study/` | Minimal reproducible study (README, data.csv, study.py) |
| `demo/bin/kitsune2-bootstrap-srv` | Pre-compiled local bootstrap/SBD server binary |
| `demo/holochain-config.env` | Written by `start_oracle.sh` — env vars for current run (gitignored) |

---

## What's next: 3-validator version

The single-validator version shows the protocol working. The 3-validator version will show it doing what it promises:

- Three separate Claude calls, each forming an independent verdict
- All three commit before any reveal — enforced by the phase gate in DNA 3
- Agreement level computed from three independent attestations
- HarmonyRecord with `validator_count: 3`

Because the synthetic study is basic arithmetic, all three validators will reach `Reproduced`. That is the point: the code demonstrates that the commit-reveal protocol ran correctly, not that disagreement is possible. Real disagreement requires real studies with real variance.
