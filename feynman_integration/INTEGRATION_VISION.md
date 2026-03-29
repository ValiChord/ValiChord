# ValiChord × Feynman — Integration Vision

**Author:** Ceri John
**Date:** March 2026

---

## What each system is

### ValiChord

A distributed peer-to-peer system for scientific reproducibility verification. It uses a blind commit-reveal protocol on a Holochain network: validators seal their findings before seeing anyone else's, then reveal — proving their assessment was independent. The cryptographic outcome is a **HarmonyRecord**, a tamper-evident entry on the Governance DHT.

ValiChord's analysis pipeline (the Python backend) checks research deposits — ZIP files containing code, data, and documentation — against a battery of reproducibility detectors. It produces structured findings (CRITICAL / SIGNIFICANT / LOW CONFIDENCE) and a full cleaning report. The REST API surface is the integration point for any external system.

### Feynman

An open-source AI research agent (CLI). Feynman can run `/replicate` to execute a replication attempt against a research study, and `/valichord` to package and submit those findings to ValiChord for cryptographic verification. It uses skill files (`SKILL.md`) and prompt templates (`prompts/`) to describe workflows to its underlying AI agents.

Feynman's role in the integration: it is an **AI validator**. ValiChord's protocol explicitly supports non-human validators — the commit-reveal protocol is neutral about who or what is doing the analysis. Feynman runs the analysis, ValiChord records the outcome.

---

## What has been built (Phase 1)

### ValiChord side

**REST API** — `backend/app.py`

Two new endpoints as of 2026-03-28:

```
POST /validate
  multipart/form-data, field: file (ZIP, max 100 MB)
  → 202 { "job_id": "uuid" }

GET /result/<job_id>
  → { "status": "done",
      "findings": [...],
      "harmony_record_draft": {
        "outcome": { "type": "PartiallyReproduced", "content": { "details": "..." } },
        "data_hash": "<sha256 hex>",
        "findings_summary": { "critical": 0, "significant": 2, "low_confidence": 3, "total": 5 },
        "harmony_record_hash": "<uhCkk... or null>",
        "harmony_record_url":  "<gateway URL or null>"
      },
      "download_url": "/download/<job_id>" }

GET /health
  → { "status": "ok", "version": "1.0", "conductor": "live"|"offline" }
```

`harmony_record_hash` is null when the Holochain conductor is not running — the analysis always completes either way. `harmony_record_url` is null until a public HTTP Gateway is deployed (see open work below).

**Outcome mapping** — findings severity → AttestationOutcome written to the Holochain DHT:

| Python findings | Holochain AttestationOutcome |
|---|---|
| Any CRITICAL finding | `FailedToReproduce` |
| SIGNIFICANT only | `PartiallyReproduced` |
| No findings | `Reproduced` |

**Holochain bridge** — `backend/holochain_bridge.py` + `demo/serve.mjs`

The Python backend cannot speak WebSocket/msgpack to the Holochain conductor directly (no mature Python Holochain client exists). Instead, `demo/serve.mjs` — the existing Node.js server — exposes two internal HTTP endpoints (localhost only):

- `POST /holochain/validate-round` — runs the full 7-step blind commit-reveal round
- `POST /holochain/call` — generic single zome call

`holochain_bridge.py` wraps these in Python with a 120 s timeout and graceful degradation (returns `None` on connection error). This means the analysis pipeline always completes, regardless of whether a conductor is running.

### Feynman side

**PR #13** — merged, cherry-picked into Feynman 0.2.15 by @advaitpaliwal.

Added two files to the Feynman repository:
- `skills/valichord-validation/SKILL.md` — registers the `/valichord` skill
- `prompts/valichord.md` — full workflow prompt for Feynman agents

**PR #14** — open, 2026-03-28.

Updated `prompts/valichord.md` to use the new single-shot API (`POST /validate` + `GET /result/<job_id>`) instead of the old chunked upload flow. Documents `harmony_record_draft` so Feynman can surface the Harmony Record hash and URL to the user.

---

## Current end-to-end flow

```
User runs /valichord in Feynman
    │
    │  1. ZIP the research deposit
    │
    │  POST /validate  (multipart, field: file)
    ▼
ValiChord Flask backend  (/workspaces/ValiChord/backend/app.py)
    │
    │  2. Run analysis pipeline
    │     - Structural detectors (100+ checks)
    │     - Claude semantic analysis
    │     - Generate cleaning report + drafts
    │
    │  3. Compute SHA-256 of deposit ZIP
    │
    │  POST localhost:8888/holochain/validate-round
    ▼
serve.mjs Holochain bridge  (/workspaces/ValiChord/demo/serve.mjs)
    │
    │  4. Run 7-step commit-reveal:
    │     submit_validation_request → claim_study → receive_task
    │     → seal_private_attestation → poll RevealOpen
    │     → submit_attestation → check_and_create_harmony_record
    ▼
Holochain conductor (Governance DNA)
    │
    │  5. HarmonyRecord written to DHT
    │     harmony_record_hash: "uhCkk..."
    │
    ◀─────────────────────────────────────────────────────
    │
    │  GET /result/<job_id>
    ▼
Feynman receives:
    - outcome: Reproduced / PartiallyReproduced / FailedToReproduce
    - findings summary (counts by severity)
    - harmony_record_hash (cryptographic proof on DHT)
    - download_url (full report ZIP)
    │
    │  6. Feynman presents summary to user
    ▼
User sees verdict + Harmony Record hash
```

---

## What is not done yet

### 1. Always-on deployment (High priority)

**Problem:** The Codespace URL (`improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev`) sleeps when inactive. Render's free tier can't handle the Holochain conductor's memory requirements. There is currently no always-on ValiChord endpoint.

**What's needed:**
- A server (VPS, cloud instance) with ~2 GB RAM to run the Holochain conductor + Flask backend
- Or a Render paid plan / alternative PaaS that can handle the memory
- The Docker setup in `demo/Dockerfile` and `render.yaml` is already written — just needs a viable host

**Impact on Feynman:** Without this, Feynman can only call ValiChord in a developer's Codespace. Not usable in production.

---

### 2. HTTP Gateway for HarmonyRecord URLs (High priority)

**Problem:** `harmony_record_url` in every response is currently `null`. ValiChord writes the HarmonyRecord to the local conductor's DHT, but there is no public HTTP endpoint where anyone can look it up by hash.

**What's needed:**
- An always-on Holochain node (the same one from item 1, or a separate one)
- The Holochain HTTP Gateway deployed alongside it (Holochain Foundation provides this — it's a standard component)
- `HOLOCHAIN_GATEWAY_URL` env var set to the gateway's base URL

**What Feynman gets:** A clickable URL like `https://gateway.valichord.org/valichord/governance/get_harmony_record?hash=uhCkk...` that anyone can verify independently — journals, funders, other researchers.

**Impact:** This is what makes the Harmony Record meaningful to an end user. Without it, the hash exists on the DHT but can't be easily shared or verified without running a node.

---

### 3. API authentication (Medium priority)

**Problem:** `POST /validate` is currently open — no API keys, no rate limiting. Anyone who discovers the URL can submit jobs.

**What's needed:**
- Simple API key header (`X-ValiChord-Key`) checked in Flask
- Rate limiting per key (Flask-Limiter or similar)
- Key issuance mechanism (could be as simple as a manual process for now)

**Feynman's side:** Store the API key in Feynman's config or as a user-supplied secret. Pass it in the request header.

---

### 4. Deposit size for large studies (Medium priority)

**Problem:** `POST /validate` has a 100 MB limit. Some research deposits (neuroimaging, genomics, large simulation outputs) are larger.

**What's needed:**
- Either raise the limit on a paid hosting plan
- Or keep the chunked upload flow (`POST /upload-chunk`) as the path for large files and have Feynman's prompt select the right path based on deposit size

The chunked upload API is still present and working — the prompt update in PR #14 simplified the default path but didn't remove it.

---

### 5. Webhook / push notification (Low priority)

**Problem:** Feynman currently polls `GET /result/<job_id>` in a loop. For large deposits (20–30 min analysis), this means many HTTP requests and a long-running Feynman session.

**What's needed:**
- A `callback_url` parameter on `POST /validate`
- Flask calls the URL with the completed result when the job finishes
- Feynman registers a local listener and waits for the push

**Impact:** Cleaner for long-running jobs. Not critical for the current scale.

---

### 6. Feynman as a persistent AI validator (Long-term)

**Current state:** Feynman is a **user-driven validator** — a human runs `/valichord`, Feynman submits one job, done.

**The longer vision:** Feynman running as a **persistent AI validator node** — automatically monitoring the ValiChord Attestation DHT for open validation requests, picking them up, running `/replicate` autonomously, and submitting attestations — without a human initiating each round.

**What's needed:**
- Feynman holds a Holochain membrane proof credential (an Ed25519 institutional key issued to Feynman as an AI validator)
- Feynman connects directly to the ValiChord Attestation DNA (DNA 3) — not via the REST API
- Feynman runs `get_validation_requests()` on a schedule, filters for studies matching its capabilities, claims them, runs the analysis, and submits
- ValiChord's DNA 3 `AuthorizedJoiningCertificateIssuer` is populated (currently empty string = dev bypass) and issues credentials to registered AI validators

**Why this matters:** The vision for ValiChord is a network of validators — human and AI — running independently and producing consensus outcomes. Feynman participating as an autonomous agent (not just a one-shot tool) is the fuller realisation of this.

This requires agreement between Advait and Ceri on:
- What institutional identity Feynman holds on the ValiChord network
- How Feynman's validator profile and reputation are maintained across sessions
- Whether Feynman's attestations carry different weight than human attestations (currently the protocol treats them identically)

---

### 7. Multi-agent validation rounds (Long-term)

**Current state:** `minimum_validators=1` (dev bypass). One validator (Feynman) completes a round alone.

**Production state:** Multiple validators — some human, some AI — must all commit before any can reveal. Feynman is one participant in a multi-agent round, not the sole validator.

**What this changes for Feynman:**
- `POST /validate` kicks off a round that won't complete until other validators also commit
- The `GET /result/<job_id>` response would return `status: waiting_for_validators` rather than `done` immediately
- Feynman's result is one input into a consensus outcome, not the outcome itself

This is a design question as much as an implementation one — how Feynman's prompt handles the non-immediate completion case.

---

### 8. Multi-model AI validation (Speculative idea, not a decision)

AI validators are fast and cheap compared to human validators, which opens up a different model: instead of waiting for a small number of human validators to independently assess a study over days or weeks, you could run 10+ different AI models simultaneously as validators. Each seals its attestation independently, then reveals. Consensus across diverse models reduces the hallucination risk that any single AI carries.

This suggests a possible two-tier HarmonyRecord approach:
- A **provisional record** — fast AI round, returned to the researcher quickly, with failure detail ("here's what 3 of 10 models couldn't reproduce and why"). The researcher fixes the issues and resubmits.
- A **verified record** — once the deposit passes, a permanent HarmonyRecord is published.

This would turn ValiChord from a one-shot stamp into an iterative improvement loop — closer to how code review actually works in practice.

The original HarmonyRecord was designed for a slower, human-validator world. AI changes the economics. Whether this is the right direction is an open question — noted here as a possibility worth exploring with Advait.

---

## Open decisions

### Decision 1 — Permanent validator identity for Feynman

Should Feynman have a stable `AgentPubKey` on the ValiChord network, or generate a fresh key per session?

**Stable key:** Feynman accumulates a `ValidatorReputation` on DNA 4. Its track record is visible. Institutional credential holders can vouch for it. More credible outcomes.

**Ephemeral key:** Simpler operationally. No key management. No reputation continuity. Fine for Phase 1 one-shot use; not viable for a persistent validator.

The answer depends on whether Advait wants Feynman to be a recognised participant in the ValiChord network or just an anonymous API caller.

---

### Decision 2 — Who operates the always-on infrastructure

The Holochain conductor + HTTP Gateway require a server with ~2 GB RAM running continuously. This is ValiChord infrastructure, not Feynman infrastructure. But the deployment and cost question is open:

- **Option A:** Ceri/ValiChord operates the server. Feynman points at a public ValiChord endpoint. Clean separation.
- **Option B:** Advait/Feynman co-hosts or funds a shared instance. More coupled.
- **Option C:** Grant/institutional funding covers a dedicated server (most appropriate given the academic infrastructure angle).

---

### Decision 3 — Feynman's prompt: breadth vs depth

The current prompt (PR #14) is a general workflow. A richer version could:

- Parse the `findings` array from `GET /result/<job_id>` and explain each finding to the user
- Use the `download_url` to fetch the full report ZIP and surface the cleaning drafts
- Integrate with `/replicate` — running a replication first, then packaging and submitting those specific findings rather than submitting raw source files

The tradeoff is complexity vs. usability. A deeper prompt gives users more value but couples Feynman's behaviour more tightly to ValiChord's output format.

---

## What Feynman + ValiChord looks like at full realisation

A researcher publishes a study. Feynman — running as an autonomous validator — detects the new `ValidationRequest` on the ValiChord DHT. It fetches the deposit, runs a full replication attempt, and seals its findings without seeing any other validator's assessment. Human validators do the same in parallel. When all validators have committed, the reveal phase opens. Each reveals their sealed attestation. ValiChord's governance DNA produces a consensus `HarmonyRecord`.

The researcher receives:
- A `harmony_record_url` — a permanent, publicly verifiable link to the consensus outcome
- A `ReproducibilityBadge` on DNA 4 — queryable by journals, funders, and institutions via the HTTP Gateway
- Per-validator attestations — including one from Feynman, identified by its institutional key

No central authority mediated any of this. No single party could have manipulated the outcome. The Feynman attestation carries the same cryptographic weight as any human validator's.

---

## Further reading

- [How a Validation Round Works](../docs/15_How_a_Validation_Round_Works.md) — step-by-step commit-reveal protocol
- [4-DNA Architecture](../docs/7_ValiChord_4-DNA_architecture_technical.md) — the four-DNA sovereignty model
- [Engineer Handover](../docs/13_Valichord_Engineer_Handover.md) — integration API reference, serve.mjs bridge, key files
- [Feynman repository](https://github.com/getcompanion-ai/feynman) — Feynman open-source CLI
- [ValiChord × Feynman PR #13](https://github.com/getcompanion-ai/feynman/pull/13) — original skill integration
- [ValiChord × Feynman PR #14](https://github.com/getcompanion-ai/feynman/pull/14) — prompt update to single-shot API

---

*This document was written based on the codebase state as of 2026-03-28. All API shapes, function names, and integration decisions reflect the current implementation.*
