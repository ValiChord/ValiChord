# ValiChord — Current Project Status

**Last updated:** 2026-04-14
**Phase:** Full protocol live on Oracle. 3-validator + researcher reveal + production-grade commit-reveal running end-to-end. v0.3.0 released.

---

## What ValiChord does (one paragraph)

ValiChord is a scientific reproducibility verification system. Researchers submit a research deposit. ValiChord runs 100+ automated checks plus Claude semantic analysis, maps the findings to a reproducibility verdict (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`), and writes that verdict as a tamper-evident **HarmonyRecord** to a Holochain DHT using a fully symmetric blind commit-reveal protocol. The record is cryptographically permanent — no central party can alter it after the fact.

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
| Decentralised demo | **Working end-to-end** | 4 isolated Docker conductors (researcher + 3 validators) communicating only via DHT — `docker compose up` + `python3 demo/ai_validator.py --mode decentralised` |
| Node.js bridges | **Working** | `researcher-node.mjs` (port 3001) + `validator-node.mjs` (ports 3002–3004) — HTTP APIs over each conductor |
| HarmonyRecord URL | **Working** | `GET /record?hash=<hash>` on researcher node — no auth, returns clean JSON |
| Feynman skill (was PR #13) | **Historical** | Feynman is no longer operational (April 2026). Superseded by `demo/ai_validator.py` (direct Claude API). |

---

## How the demo runs end-to-end

Five Docker containers — researcher + 3 validators + kitsune2 bootstrap server — each with their own Holochain conductor, keystore, and SQLite database. The only communication between containers is the DHT.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose -f demo/docker-compose.yml up --build -d
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
python3 demo/ai_validator.py --mode decentralised
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
  http://localhost:3001/record?hash=uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: Reproduced  Agreement: ExactMatch  Validators: 3

════════════════════════════════════════════════════════════
  Demo complete. The full ValiChord protocol ran end-to-end.
  Researcher and 3 validators all commit-revealed simultaneously.
════════════════════════════════════════════════════════════
```

Full architecture, retry design, and commit-reveal table: **`demo/DECENTRALISED_DEMO.md`**

---

---

## What is NOT done yet

### 1. `ANTHROPIC_API_KEY` persistent on Oracle — HIGH, 2 min fix
Currently must be manually exported each SSH session. Blocks unattended demo runs.
```bash
# SSH into Oracle and add to ~/.bashrc:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```

### 2. ~~Feynman PR #23~~ — CLOSED
Feynman is no longer operational (April 2026). AI validator functionality has been rebuilt
directly against the Claude API (`demo/ai_validator.py`). No further Feynman integration work.

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
Use `docker compose -f demo/docker-compose.yml down -v` between runs to clear conductor state if needed.

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
| `demo/DECENTRALISED_DEMO.md` | Full technical guide for the decentralised demo — architecture, retry design, commit-reveal table |
| `demo/ai_validator.py` | Python orchestrator — `--mode decentralised` calls the five node APIs |
| `demo/docker-compose.yml` | 5-container stack definition |
| `demo/researcher-node.mjs` | Node.js HTTP API for researcher conductor |
| `demo/validator-node.mjs` | Node.js HTTP API for each validator conductor |
| `demo/node-lib.mjs` | Shared helpers: `withSession`, `retryOnTx5`, `loadHcClient`, `externalHashFromB64` |
| `backend/app.py` | Flask REST API |
| `docs/INTEGRATION_GUIDE.md` | REST API integration guide |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Four-DNA architecture |

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
