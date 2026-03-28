# ValiChord — Current Project Status

**Last updated:** 2026-03-28
**Phase:** Integration-ready. Core demo complete. Feynman integration live.

---

## What ValiChord does (one paragraph)

ValiChord is a scientific reproducibility verification system. Researchers submit a deposit (ZIP of code + data + docs). ValiChord runs 100+ automated checks plus Claude semantic analysis, maps the findings to a reproducibility verdict (`Reproduced` / `PartiallyReproduced` / `FailedToReproduce`), and writes that verdict as a tamper-evident **HarmonyRecord** to a Holochain DHT using a blind commit-reveal protocol. The record is cryptographically permanent — no central party can alter it after the fact.

---

## What is live right now

| Component | Status | Detail |
|---|---|---|
| Flask REST API | **Live** | `POST /validate`, `GET /result/<job_id>`, `GET /health` |
| Analysis pipeline | **Live** | 100+ detectors + Claude semantic analysis |
| Holochain conductor | **Live in Codespace** | Governance + Attestation + Workspace + Researcher DNAs |
| Node.js bridge (`demo/serve.mjs`) | **Live in Codespace** | Runs 7-step commit-reveal round; exposes `POST /holochain/validate-round` |
| `harmony_record_hash` | **Working** | Returns `uhCkk...` canonical string in every result |
| `harmony_record_url` | **Working in Codespace** | Full gateway URL, publicly clickable when Codespace is running |
| HTTP Gateway (`hc-http-gw`) | **Live in Codespace** | Port 8090, exposes `get_harmony_record` and `get_harmony_records_by_discipline` |
| Feynman skill (PR #13) | **Merged** | Cherry-picked into Feynman 0.2.15 by @advaitpaliwal |
| Feynman prompt update (PR #14) | **Open** | Migrates to single-shot API, documents `harmony_record_draft` |

**Demo endpoint (Codespace, sleeps when inactive):**
`https://improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev`

---

## How Feynman uses ValiChord

Feynman is an AI research agent CLI. It is an **API client**, not a Holochain peer. The integration is entirely via the REST API:

```
1. User runs /valichord in Feynman
2. Feynman ZIPs the research deposit
3. POST /validate  (multipart, field: file, max 100 MB)
   → 202 { "job_id": "uuid" }
4. Poll GET /result/<job_id> until status == "done"
5. Response includes:
   {
     "status": "done",
     "findings": { "band": "...", "critical": N, "significant": N, ... },
     "harmony_record_draft": {
       "outcome": { "type": "Reproduced" },        ← or PartiallyReproduced / FailedToReproduce
       "data_hash": "<sha256 hex>",
       "findings_summary": { "critical": 0, "significant": 2, ... },
       "harmony_record_hash": "uhCkk...",           ← permanent cryptographic record
       "harmony_record_url": "https://..."          ← public verifiable link (when gateway running)
     },
     "download_url": "/download/<job_id>"           ← full report ZIP
   }
6. Feynman presents verdict + Harmony Record hash/URL to user
```

**Key point for Advait:** ValiChord provides the integrity layer. Feynman provides the AI replication agent. They are independent — ValiChord works with any client that can POST a ZIP.

---

## What the Harmony Record URL looks like

```
https://<codespace>-8090.app.github.dev
  /uhC0kdW4dc3_nWr50fp7PgDT2xR0PSwbaAMUgcp8cUKDDyr8On1lF   ← governance DNA hash
  /valichord-demo                                             ← app ID
  /governance_coordinator
  /get_harmony_record
  ?payload=<base64url-encoded JSON of the data ExternalHash>
```

Anyone with this URL can independently verify the outcome on the DHT — no account, no login.

---

## What is NOT done yet (priority order)

| Item | Priority | What's needed |
|---|---|---|
| Always-on hosting | **High** | Codespace sleeps. Need ~2 GB RAM VPS (Render free tier can't handle the conductor). Docker setup in `demo/Dockerfile` + `render.yaml` is ready. |
| HTTP Gateway permanent deployment | **High** | Currently only runs in Codespace. Needs a permanent server alongside the conductor. |
| API authentication | **Medium** | `POST /validate` is open — no API keys or rate limiting yet. |
| Feynman as persistent AI validator | **Long-term** | Feynman joining the Holochain network directly (not via REST), holding an Ed25519 validator identity, autonomously picking up validation requests. |
| Multi-agent rounds | **Long-term** | Currently `minimum_validators=1` (dev bypass). Production needs multiple validators to commit before reveal. |

---

## Key files to read for context

| File | What it contains |
|---|---|
| `feynman_integration/INTEGRATION_VISION.md` | Full architecture, end-to-end flow diagram, all open work items, open decisions |
| `feynman_integration/README.md` | One-page status table |
| `nondominium_integration/INTEGRATION_VISION.md` | Nondominium (Sensorica) integration plan |
| `backend/app.py` | Flask REST API — `/validate`, `/result`, `/health` |
| `demo/serve.mjs` | Node.js Holochain bridge — commit-reveal round, gateway payload |
| `demo/start.sh` | How to start the full demo stack |
| `demo/start-gateway.sh` | How to start the HTTP Gateway alongside the conductor |
| `docs/13_Valichord_Engineer_Handover.md` | Engineer-level integration reference |

---

## Open decisions that involve Advait

1. **Feynman's validator identity** — stable `AgentPubKey` (builds reputation on DHT) vs ephemeral key per session. Stable is better long-term but requires key management on Feynman's side.
2. **Who runs the always-on infrastructure** — ValiChord's responsibility, but Advait may have hosting contacts or funding that could help. ~£10–20/month VPS would suffice.
3. **Prompt depth (PR #14)** — current prompt is a general workflow. A richer version could parse findings in detail and integrate with Feynman's `/replicate` command.

---

## How to start the demo stack (if Advait wants a live demo)

```bash
# Terminal 1 — Holochain conductor + Node bridge
bash demo/start.sh

# Terminal 2 — HTTP Gateway (after start.sh completes)
bash demo/start-gateway.sh

# Terminal 3 — Flask backend (set gateway env vars)
export HOLOCHAIN_GATEWAY_URL="https://improved-space-couscous-5gjwpp546jrg27p5q-8090.app.github.dev"
export HOLOCHAIN_GOVERNANCE_DNA_HASH="uhC0kdW4dc3_nWr50fp7PgDT2xR0PSwbaAMUgcp8cUKDDyr8On1lF"
cd backend && flask run --host=0.0.0.0 --port=5000
```

Make sure Codespace ports 5000, 8888, and 8090 are set to **Public**.

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
