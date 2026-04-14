# ValiChord — Current Project Status

**Last updated:** 2026-04-14
**Phase:** Full protocol live on Oracle. 3-validator + researcher reveal + production-grade commit-reveal running end-to-end. v0.3.0 released.

---

## What ValiChord does (one paragraph)

ValiChord is a scientific reproducibility verification system. Researchers submit a deposit (ZIP of code + data + docs). ValiChord runs 100+ automated checks plus Claude semantic analysis, maps the findings to a reproducibility verdict (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`), and writes that verdict as a tamper-evident **HarmonyRecord** to a Holochain DHT using a fully symmetric blind commit-reveal protocol. The record is cryptographically permanent — no central party can alter it after the fact.

---

## What is live right now

| Component | Status | Detail |
|---|---|---|
| Flask REST API | **Live** | `POST /validate`, `GET /result/<job_id>`, `GET /download/<job_id>`, `GET /health` |
| Analysis pipeline | **Live** | 100+ detectors + Claude semantic analysis |
| `validator_outcome` / `validator_notes` | **Live** | Validators submit real replication verdicts; `validator_attested: true` in result |
| API key authentication | **Live** | `VALICHORD_API_KEYS` env var; `X-ValiChord-Key` header on write endpoints |
| Webhook callbacks | **Live** | `callback_url` form field; fires once on completion with one retry |
| OpenAPI 3.0 spec | **Live** | `GET /openapi.yaml` — machine-readable spec for any HTTP client |
| Swagger UI | **Live** | `GET /docs` — interactive API explorer |
| Holochain conductor | **Live on Oracle** | 5 apps: `valichord-demo` (single-validator) + `valichord-researcher/validator-1/2/3` (3-validator) |
| Node.js bridge (`demo/serve.mjs`) | **Live on Oracle** | `POST /holochain/validate-round-multi` (3-validator) + `POST /holochain/validate-round` (single-validator) |
| Public API (`demo/serve.mjs`, port 5000) | **Live on Oracle** | Authenticated endpoints + unauthenticated `GET /record/<hash>` |
| HTTP Gateway (`hc-http-gw`) | **Live on Oracle** | Port 8090 — started by `start_oracle.sh` |
| AI validator demo (`demo/ai_validator.py`) | **Working end-to-end** | 3 Claude validators + researcher reveal + fully verified commit-reveal → HarmonyRecord + shareable URL |
| Permanent HarmonyRecord URL | **Working** | `GET /record/<hash>` — no auth, any browser, returns clean JSON |
| Feynman skill (was PR #13) | **Merged** | Cherry-picked into Feynman 0.2.15 by @advaitpaliwal; Feynman now at 0.2.16, ValiChord tracked as PR #23 |

---

## How the demo runs end-to-end

```
bash demo/start_oracle.sh --fresh
  1. Clears conductor_data/ (--fresh)
  2. Starts Holochain conductor (admin port 4444)
  3. Starts local kitsune2 bootstrap server (port 9000)
  4. Runs setup.mjs — installs 5 apps, creates app-config.json
  5. Extracts governance DNA hash → writes demo/holochain-config.env
  6. Starts Node.js bridge (port 8888 internal, port 5000 public)
  7. Starts hc-http-gw (port 8090)

python3 demo/ai_validator.py
  [1/7] Load synthetic study (ZIP + per-run UUID salt → SHA-256 ExternalHash)
  [2/7] Execute study.py → slope 2.4086 / intercept 1.1742 / R² 0.9991
  [3/7] 3 independent Claude API calls (claude-opus-4-6) → verdicts
  [4/7] POST /holochain/validate-round-multi → serve.mjs _runFullProtocolRound():
    (0) lock_researcher_result       — SHA-256(msgpack(metrics) || nonce) sealed privately
        publish_researcher_commitment — hash only on shared DHT
    (1) submit_validation_request     — num_validators_required=3
    (2-4) each validator: profile → claim → receive_task → seal_private_attestation
          post_commit → CommitmentAnchor on shared DHT
    (5) poll get_current_phase until RevealOpen
    (6a) reveal_researcher_result     — SHA-256 verified on-chain
    (6b) each validator: get_private_attestation_for_task → extract nonce
         submit_attestation            — SHA-256(msgpack(attestation) || nonce) verified on-chain
    (7) check_and_create_harmony_record → HarmonyRecord on public Governance DHT
  [5/7] All commitments sealed and revealed.
  [6/7] Researcher result verified + 3 validator attestations on DHT.
  [7/7] Display outcome + shareable URL + verify record is readable in browser
```

**Demo output (step 7):**
```
[7/7] Permanent record.
────────────────────────────────────────────────────────────
  Outcome:           Reproduced (3/3 validators)
  Agreement level:   ExactMatch
  Discipline:        ComputationalBiology
  HarmonyRecord:     uhC8k…
  Researcher reveal: uhCkk…

  Validator 1: Reproduced (High) — …
  Validator 2: Reproduced (High) — …
  Validator 3: Reproduced (High) — …

  Shareable URL:
  http://132.145.34.27:5000/record/uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: {'type': 'Reproduced'}  Agreement: ExactMatch  Validators: 3

════════════════════════════════════════════════════════════
  Demo complete. The full ValiChord protocol ran end-to-end.
  Researcher and 3 validators all commit-revealed simultaneously.
════════════════════════════════════════════════════════════
```

---

## How Feynman uses ValiChord

Feynman is an AI research agent CLI. It is an **API client**, not a Holochain peer. The integration is entirely via the REST API. Two flows:

**Validator flow (Feynman actually runs the code):**
```
1. User runs /valichord in Feynman — selects "validator" role
2. Feynman runs /replicate — executes the research code, forms a verdict
3. Feynman ZIPs the research deposit
4. POST /validate  (multipart: file + validator_outcome + validator_notes)
   → 202 { "job_id": "uuid" }
5. Poll GET /result/<job_id> until status == "done"
6. Response includes harmony_record_draft.validator_attested = true
```

**Researcher flow (submitting own deposit):**
```
1. User runs /valichord in Feynman — selects "researcher" role
2. Feynman ZIPs the research deposit
3. POST /validate  (multipart: file only)
4. Poll GET /result/<job_id> until status == "done"
5. Response includes harmony_record_draft.validator_attested = false
```

---

## What is NOT done yet

### 1. `ANTHROPIC_API_KEY` persistent on Oracle — HIGH, 2 min fix
Currently must be manually exported each SSH session. Blocks unattended demo runs.
```bash
# SSH into Oracle and add to ~/.bashrc:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```

### 2. Feynman PR #23 — MEDIUM, needs read before integration work
ValiChord is PR #23 in the Feynman repo. Before doing any more Feynman integration
work, read what PR #23 actually contains. PRs #14 and #15 may have been folded in
or superseded.

### 3. Rate limiting — LOW
API keys are in. No per-key rate limiting yet.

---

## Key technical facts for the next session

### tx5 / kitsune2 bootstrap
Holochain 0.6.0 uses tx5/WebRTC transport. Oracle uses a local `kitsune2-bootstrap-srv`
(pre-compiled binary in `demo/bin/`) on port 9000 — avoids dependency on the external
`dev-test-bootstrap2.holochain.org` relay which caused intermittent peer-discovery timeouts.
`serve.mjs` wraps `claim_study` in `_retryOnTx5()` (10 retries × 6s).

### Per-run UUID salt
`ai_validator.py` salts the data hash: `SHA-256(data_bytes + run_id)` where `run_id` is
16 random bytes. Ensures each run presents a fresh `ExternalHash` and avoids DHT
"already claimed" capacity errors on repeated runs against the same conductor.
Use `--fresh` with `start_oracle.sh` between runs to clear conductor state if needed.

### hc-http-gw URL format (verified from source)
```
http://<host>:8090/<dna_hash>/<app_id>/<zome_name>/<fn_name>?payload=<base64url-padded>
```
- Payload = BASE64_URL_SAFE **with** `=` padding of JSON-encoded input
- For `get_harmony_record`: payload = base64url(JSON.stringify(externalHashB64))
- Response is msgpack-decoded — HoloHash fields are byte arrays, not strings

### Multi-app conductor setup
Five apps on one conductor:

| App | Network seed | `minimum_validators` | Role |
|---|---|---|---|
| `valichord-demo` | `valichord-demo` | 1 | Legacy single-validator |
| `valichord-researcher` | `valichord-demo-multi` | 3 | Researcher identity |
| `valichord-validator-1/2/3` | `valichord-demo-multi` | 3 | Validators |

Separate network seeds are required — multi-validator integrity zome rejects
`num_validators_required=1` ValidationRequest entries.

### Validator reveal — production-grade (as of 2026-04-14)
After `seal_private_attestation`, `serve.mjs` calls `get_private_attestation_for_task`
on DNA 2 to retrieve the real 32-byte nonce. This is passed to `submit_attestation`,
which verifies `SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash`
on DNA 3. Both sides of the commit-reveal are now fully hash-verified.

---

## Key files to read for context

| File | What it contains |
|---|---|
| `PROJECT_STATUS.md` | **This file** — current status, open work, technical facts |
| `docs/Holochain_complete.md` | Complete Holochain build guide + tx5 timing, hc-http-gw URL format, ExternalHash JS, NetworkConfig |
| `demo/AI_VALIDATOR_DEMO.md` | Full technical guide for the Oracle demo — architecture, expected output, commit-reveal table |
| `demo/serve.mjs` | Node.js bridge — full commit-reveal round, `_retryOnTx5`, gateway payload encoding |
| `demo/start_oracle.sh` | Oracle startup script — conductor, setup, DNS hash extraction, bridge + gateway |
| `demo/ai_validator.py` | End-to-end AI validator demo |
| `demo/conductor-config.yaml` | Conductor config (uses local bootstrap + signal URLs) |
| `backend/app.py` | Flask REST API |
| `docs/INTEGRATION_GUIDE.md` | REST API integration guide |
| `feynman_integration/INTEGRATION_VISION.md` | Feynman integration architecture |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Four-DNA architecture |

---

## Oracle server reference

| Detail | Value |
|---|---|
| IP | 132.145.34.27 |
| SSH key | `ssh-key-2026-04-13.key` (in `IMPORTANT FILES HERE\oracle cloud key`) |
| SSH user | `ubuntu` |
| Public API | `http://132.145.34.27:5000` (authenticated endpoints + `/record/<hash>` unauthenticated) |
| HTTP Gateway | `http://132.145.34.27:8090` |
| Bridge | `http://localhost:8888` (internal only) |
| Admin socket | `localhost:4444` |
| Repo path | `~/valichord` |
| Logs | `~/valichord/demo/conductor.log`, `demo/serve.log` |
| Startup script | `demo/start_oracle.sh` |

**To run demo on Oracle:**
```bash
ssh -i ssh-key-2026-04-13.key ubuntu@132.145.34.27
cd ~/valichord && git pull
export ANTHROPIC_API_KEY=sk-ant-...
bash demo/start_oracle.sh --fresh   # wait for "=== Stack is up ==="
python3 demo/ai_validator.py
```

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
