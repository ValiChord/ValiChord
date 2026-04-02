# ValiChord — Current Project Status

**Last updated:** 2026-03-31 (Feynman version updated: 0.2.16, PR #23)
**Phase:** Integration-ready. Core demo complete. Feynman integration live (0.2.16, PR #23). REST API fully open for external tools.

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
| Holochain conductor | **Live in Codespace** | Governance + Attestation + Workspace + Researcher DNAs |
| Node.js bridge (`demo/serve.mjs`) | **Live in Codespace** | Runs 7-step commit-reveal round; exposes `POST /holochain/validate-round` |
| `harmony_record_hash` | **Working** | Returns `uhCkk...` canonical string in every result |
| `harmony_record_url` | **Working in Codespace** | Full gateway URL, publicly clickable when Codespace is running |
| HTTP Gateway (`hc-http-gw`) | **Live in Codespace** | Port 8090, exposes `get_harmony_record` and `get_harmony_records_by_discipline` |
| Feynman skill (was PR #13) | **Merged** | Cherry-picked into Feynman 0.2.15 by @advaitpaliwal; Feynman now at 0.2.16, ValiChord tracked as PR #23 |
| Feynman prompt update (PR #14) | **Rejected** | Rejected by @advaitpaliwal; content superseded by PR #23 |
| Feynman validator flow (PR #15) | **Never pushed** | Local draft only (`valichord_prompt_v2.md`); was never submitted to Feynman repo |

**Demo endpoint (Codespace, sleeps when inactive):**
`https://improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev`

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
   (real verdict, not a proxy)
```

**Researcher flow (submitting own deposit):**
```
1. User runs /valichord in Feynman — selects "researcher" role
2. Feynman ZIPs the research deposit
3. POST /validate  (multipart: file only)
   → 202 { "job_id": "uuid" }
4. Poll GET /result/<job_id> until status == "done"
5. Response includes harmony_record_draft.validator_attested = false
   (structural assessment, not a full replication verdict)
```

Both flows return the same response shape:
```json
{
  "status": "done",
  "harmony_record_draft": {
    "outcome": { "type": "Reproduced" },
    "validator_attested": true,
    "data_hash": "<sha256 hex>",
    "findings_summary": { "critical": 0, "significant": 2, ... },
    "harmony_record_hash": "uhCkk...",
    "harmony_record_url": "https://..."
  },
  "download_url": "/download/<job_id>"
}
```

**Key point:** ValiChord provides the integrity layer. Feynman provides the AI replication agent. They are independent — ValiChord works with any client that can POST a ZIP.

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
| Rate limiting | **Medium** | API keys are in (auth done). No per-key rate limiting yet. |
| Feynman PR #14 / PR #15 acceptance | **Medium** | PRs open at Feynman repo. Waiting on @advaitpaliwal review. |
| Feynman as persistent AI validator | **Long-term** | Feynman joining the Holochain network directly (not via REST), holding an Ed25519 validator identity, autonomously picking up validation requests. |
| Multi-agent rounds | **Long-term** | Currently `minimum_validators=1` (dev bypass). Production needs multiple validators to commit before reveal. |

---

## Key files to read for context

| File | What it contains |
|---|---|
| `docs/INTEGRATION_GUIDE.md` | Tool-agnostic REST API integration guide (curl, Python, TypeScript examples) |
| `backend/openapi.yaml` | OpenAPI 3.0 spec — served at `GET /openapi.yaml`, rendered at `GET /docs` |
| `feynman_integration/INTEGRATION_VISION.md` | Full architecture, end-to-end flow diagram, all open work items, open decisions |
| `feynman_integration/README.md` | One-page status table |
| `feynman_integration/valichord_prompt_v2.md` | Feynman PR #15 prompt — validator flow with `/replicate` as first step |
| `nondominium_integration/INTEGRATION_VISION.md` | Nondominium (Sensorica) integration plan |
| `backend/app.py` | Flask REST API — `/validate` (with `validator_outcome`), `/result`, `/download`, `/health`, `/docs`, `/openapi.yaml` |
| `demo/serve.mjs` | Node.js Holochain bridge — commit-reveal round, gateway payload |
| `demo/start.sh` | How to start the full demo stack |
| `demo/start-gateway.sh` | How to start the HTTP Gateway alongside the conductor |
| `docs/13_Valichord_Engineer_Handover.md` | Engineer-level integration reference |

---

## Open decisions that involve Advait

1. **Feynman 0.2.16 / PR #23** — Feynman has advanced to 0.2.16. ValiChord integration is now PR #23 in the Feynman repo. Verify what PR #23 contains and whether PRs #14 / #15 were folded in, superseded, or are still open before doing any integration work.
2. **Feynman's validator identity** — stable `AgentPubKey` (builds reputation on DHT) vs ephemeral key per session. Stable is better long-term but requires key management on Feynman's side.
3. **Who runs the always-on infrastructure** — ValiChord's responsibility, but Advait may have hosting contacts or funding that could help. ~£10–20/month VPS would suffice.

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
