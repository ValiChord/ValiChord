# ValiChord — Current Project Status

**Last updated:** 2026-04-14 (end-to-end demo working; output cleaned up)
**Phase:** Demo runs end-to-end on Oracle. Three cleanup items before sharing with Advait.

---

## What ValiChord does (one paragraph)

ValiChord is a scientific reproducibility verification system. Researchers submit a deposit (ZIP of code + data + docs). ValiChord runs 100+ automated checks plus Claude semantic analysis, maps the findings to a reproducibility verdict (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`), and writes that verdict as a tamper-evident **HarmonyRecord** to a Holochain DHT using a blind commit-reveal protocol. The record is cryptographically permanent — no central party can alter it after the fact.

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
| Holochain conductor | **Live on Oracle** | Governance + Attestation + Workspace + Researcher DNAs — always-on at 132.145.34.27 |
| Node.js bridge (`demo/serve.mjs`) | **Live on Oracle** | Runs 7-step commit-reveal round; exposes `POST /holochain/validate-round` |
| HTTP Gateway (`hc-http-gw`) | **Live on Oracle** | Port 8090 — started by `start_oracle.sh` via `start-gateway.sh` |
| AI validator demo (`demo/ai_validator.py`) | **Working end-to-end** | Load study → execute → Claude verdict → commit-reveal → HarmonyRecord written + URL verified |
| Permanent HarmonyRecord URL | **Working** | `ai_validator.py` auto-loads `demo/holochain-config.env` (written by `start_oracle.sh`), constructs URL, verifies 200 from gateway |
| Demo output | **Clean** | Step 7 shows outcome/agreement/confidence/discipline fields — no more raw byte arrays |
| Feynman skill (was PR #13) | **Merged** | Cherry-picked into Feynman 0.2.15 by @advaitpaliwal; Feynman now at 0.2.16, ValiChord tracked as PR #23 |

**Demo endpoint (Codespace, sleeps when inactive):**
`https://improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev`

---

## How the demo runs end-to-end

```
bash demo/start_oracle.sh
  1. Starts Holochain conductor (admin port 4444)
  2. Waits 30s for tx5/WebRTC relay registration to complete
  3. Runs setup.mjs — installs app, creates app-config.json
  4. Extracts governance DNA hash → writes demo/holochain-config.env
  5. Starts Node.js bridge (port 8888) — serve.mjs
  6. Starts hc-http-gw (port 8090) — start-gateway.sh

python3 demo/ai_validator.py
  Step 1: Load synthetic study (ZIP + SHA-256 hash)
  Step 2: Execute study.py → deterministic output
  Step 3: Claude verdict (claude-opus-4-6) → {outcome, confidence, reasoning}
  Step 4-6: Bridge runs full 7-step commit-reveal:
    publish_validator_profile → submit_validation_request → claim_study
    → receive_task → seal_private_attestation → poll phase → submit_attestation
    → check_and_create_harmony_record
  Step 7: Display permanent URL + verify 200 from gateway
```

**Demo output (step 7):**
```
[7/7] Permanent record.
────────────────────────────────────────────────────────────
  Outcome:           Reproduced
  Agreement level:   ExactMatch
  Confidence:        High
  Discipline:        ComputationalBiology
  Validators:        1
  HarmonyRecord:     uhCkk...

  Permanent URL:
  http://132.145.34.27:8090/uhC0k.../governance_coordinator/get_harmony_record?payload=...

  Verifying record is readable via HTTP Gateway…
  Record confirmed on DHT.

════════════════════════════════════════════════════════════
  Demo complete. The protocol ran end-to-end.
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

## What is NOT done yet (next session priority order)

### 1. `ANTHROPIC_API_KEY` persistent on Oracle — HIGH, 2 min fix
Currently must be manually exported each SSH session. Blocks unattended demo runs.
```bash
# SSH into Oracle and add to ~/.bashrc:
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
```

### 2. Port 5000 external access — MEDIUM, needs investigation
`iptables` rule exists for port 5000. Oracle Security List has port 5000 open.
But `curl http://132.145.34.27:5000/health` from external times out.
Flask is bound to `0.0.0.0:5000` on the server.
Hypothesis: Oracle Security List rule may have a different protocol/port entry, or
Flask isn't actually running. Check:
```bash
ss -tlnp | grep 5000        # is Flask listening?
sudo iptables -L INPUT -n   # is the iptables rule right?
# Oracle Console → VCN → Security Lists → Ingress Rules → check TCP 5000 entry
```
This matters for the Feynman REST integration (remote call to `POST /validate`).
The Holochain gateway (port 8090) IS accessible from external — only port 5000 fails.

### 3. `hc-http-gw` PATH on Oracle — LOW, may already be working
Previous check showed `which hc-http-gw` returned nothing (not in PATH).
`start_oracle.sh` calls `bash demo/start-gateway.sh` — check whether that script
handles the PATH correctly or hardcodes the binary location.
```bash
ls ~/.cargo/bin/hc-http-gw   # is it installed?
# If yes, start-gateway.sh just needs: export PATH="$HOME/.cargo/bin:$PATH"
```
The gateway IS serving port 8090 correctly during demo runs (URL verifies 200),
so this may be resolved already or `start-gateway.sh` sets PATH internally.

### 4. Feynman PR #23 — MEDIUM, needs read before integration work
ValiChord is PR #23 in the Feynman repo. Before doing any more Feynman integration
work, read what PR #23 actually contains. PRs #14 and #15 may have been folded in
or superseded.

### 5. Rate limiting — LOW
API keys are in. No per-key rate limiting yet.

### 6. Multi-agent rounds — LONG TERM
Currently `minimum_validators=1` (dev bypass). Production needs multiple validators.

---

## Key technical facts for the next session

### tx5 timing fix (why the 30s wait exists)
Holochain 0.6.0 uses tx5/WebRTC transport via the external SBD relay at
`dev-test-bootstrap2.holochain.org`. The relay registration takes ~30s after
conductor startup. `get_links` in `claim_study` propagates any tx5 send error
as a fatal WasmError — no local fallback. Two mitigations:
1. `start_oracle.sh` waits 30s after admin port ready before running setup
2. `serve.mjs` wraps `claim_study` in `_retryOnTx5()` (5 retries × 4s)

### hc-http-gw URL format (verified from source)
```
http://<host>:8090/<dna_hash>/<app_id>/<zome_name>/<fn_name>?payload=<base64url-padded>
```
- Payload = BASE64_URL_SAFE **with** `=` padding of JSON-encoded input
- `%3D` in URL query string is URL-decoded to `=` by axum before base64 decode
- For `get_harmony_record`: payload = base64url(JSON.stringify(externalHashB64))
- Response is msgpack-decoded — HoloHash fields are byte arrays, not strings
  (the Python demo no longer dumps the raw response; just checks HTTP 200)

### Bridge returns human-readable summary fields
`POST /holochain/validate-round` response now includes:
```json
{
  "harmony_record_hash": "uhCkk...",
  "gateway_payload": "...",
  "outcome_type": "Reproduced",
  "confidence": "High",
  "discipline_type": "ComputationalBiology",
  "agreement_level": "ExactMatch",
  "validator_count": 1
}
```

### NetworkConfig — test-utils only
`mem_bootstrap`, `disable_bootstrap`, `disable_gossip` are `#[cfg(feature = "test-utils")]`
and are NOT available in the production `holochain` binary.
`conductor-config.yaml` must use `network.bootstrap_url` + `network.signal_url`.

---

## Key files to read for context

| File | What it contains |
|---|---|
| `PROJECT_STATUS.md` | **This file** — current status, open work, technical facts |
| `docs/Holochain_complete.md` | Complete Holochain build guide + section 25 (tx5 timing, hc-http-gw URL format, ExternalHash JS, NetworkConfig test-utils gating) |
| `demo/serve.mjs` | Node.js bridge — full commit-reveal round, `_retryOnTx5`, gateway payload encoding |
| `demo/start_oracle.sh` | Oracle startup script — conductor, setup, DNS hash extraction, bridge + gateway |
| `demo/ai_validator.py` | End-to-end AI validator demo |
| `demo/conductor-config.yaml` | Conductor config (uses external bootstrap + signal URLs) |
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
| HTTP Gateway | `http://132.145.34.27:8090` (open — working) |
| Flask API | `http://132.145.34.27:5000` (open in Security List, but external access times out — see issue #2 above) |
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
bash demo/start_oracle.sh        # starts everything; wait for "Stack is up"
# In a second terminal:
python3 demo/ai_validator.py
```

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
