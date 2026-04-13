# ValiChord — Current Project Status

**Last updated:** 2026-04-13 (Oracle server provisioned; AI validator demo running end-to-end)
**Phase:** Always-on infrastructure live. AI validator demo complete. One task to finish: wire up the public HarmonyRecord URL.

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
| HTTP Gateway (`hc-http-gw`) | **Live on Oracle** | Port 8090 — always-on |
| AI validator demo (`demo/ai_validator.py`) | **Working** | End-to-end: executes study, Claude verdict, full commit-reveal, HarmonyRecord written |
| `harmony_record_hash` | **Working** | Returns `uhCkk...` canonical string |
| `harmony_record_url` | **NOT YET wired** | Gateway running but `HOLOCHAIN_GATEWAY_URL` + `HOLOCHAIN_GOVERNANCE_DNA_HASH` not set in start_oracle.sh — see next steps |
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
| **Wire up public HarmonyRecord URL** | **HIGH — next task** | HTTP Gateway is live on Oracle at port 8090. Need to: (1) read governance DNA hash from `~/valichord/demo/app-config.json` on Oracle, (2) add `export HOLOCHAIN_GATEWAY_URL=http://132.145.34.27:8090` and `export HOLOCHAIN_GOVERNANCE_DNA_HASH=<hash>` to `demo/start_oracle.sh` before the demo runs. Then the demo will print the full public URL. |
| **Make ANTHROPIC_API_KEY persistent on Oracle** | **High** | Currently must be manually exported each SSH session. Add to `~/.bashrc` on Oracle: `export ANTHROPIC_API_KEY=sk-ant-...` |
| Rate limiting | **Medium** | API keys are in (auth done). No per-key rate limiting yet. |
| Feynman PR #23 | **Medium** | ValiChord is now PR #23 in the Feynman repo. Verify what it contains and whether PRs #14/#15 were folded in before doing more integration work. |
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
| `demo/start_oracle.sh` | How to start the full stack on Oracle (conductor + bridge + gateway) |
| `demo/ai_validator.py` | End-to-end AI validator demo (synthetic study → Claude verdict → HarmonyRecord) |
| `demo/synthetic_study/` | Synthetic study: `study.py`, `data.csv`, `README.md` (linear regression, deterministic output) |
| `demo/start.sh` | How to start the full demo stack in Codespace (sleeps) |
| `demo/start-gateway.sh` | How to start the HTTP Gateway |
| `docs/13_Valichord_Engineer_Handover.md` | Engineer-level integration reference |

---

## Open decisions that involve Advait

1. **Feynman 0.2.16 / PR #23** — Feynman has advanced to 0.2.16. ValiChord integration is now PR #23 in the Feynman repo. Verify what PR #23 contains and whether PRs #14 / #15 were folded in, superseded, or are still open before doing any integration work.
2. **Feynman's validator identity** — stable `AgentPubKey` (builds reputation on DHT) vs ephemeral key per session. Stable is better long-term but requires key management on Feynman's side.
3. **Always-on infrastructure** — ✅ resolved. Oracle VM.Standard.E5.Flex (12 GB RAM, 2 OCPU) is provisioned and running at 132.145.34.27. Free tier Oracle Cloud.

---

## How to run the AI validator demo (Oracle — always-on)

The Oracle server at **132.145.34.27** runs the Holochain stack permanently. To run a demo:

```bash
# SSH into Oracle
ssh -i /path/to/ssh-key-2026-04-13.key ubuntu@132.145.34.27

# If the stack is not already running (check with: ps aux | grep holochain)
cd ~/valichord
export ANTHROPIC_API_KEY=sk-ant-...    # your key
bash demo/start_oracle.sh              # starts conductor + bridge + HTTP Gateway

# In a second terminal (or after start_oracle.sh is up), run the demo
export ANTHROPIC_API_KEY=sk-ant-...
python3 demo/ai_validator.py
```

The demo runs 7 steps: load synthetic study → execute it → Claude verdict → commit-reveal → HarmonyRecord written.

Last successful run: HarmonyRecord hash `uhCkk9Jfk0qk4cONXQDv5vWxiaT1sHVk66tIj03kryHbiR_LzsiZe`
Verdict: `Reproduced`, Confidence: `High`

**Note:** The full public HarmonyRecord URL is not yet generated (see "What is NOT done yet" above).

---

## Oracle server reference

| Detail | Value |
|---|---|
| IP | 132.145.34.27 |
| SSH key | `ssh-key-2026-04-13.key` (in `IMPORTANT FILES HERE\oracle cloud key`) |
| SSH user | `ubuntu` |
| HTTP Gateway | `http://132.145.34.27:8090` (open on Oracle Security List + iptables) |
| Bridge | `http://localhost:8888` (internal only) |
| Admin socket | `localhost:4444` |
| Repo path | `~/valichord` |
| Logs | `~/valichord/demo/conductor.log`, `demo/serve.log` |
| Startup script | `demo/start_oracle.sh` |

Ports 5000 and 8090 are open in Oracle Security List and iptables.

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
