# ValiChord Public Demo Website — Session Handover Plan

**Written:** 2026-04-17
**Updated:** 2026-04-20
**Status:** Planning only — nothing built yet
**Read this before:** touching `backend/app.py`, creating any new Render service, or modifying Oracle

---

## What This Document Is

A complete handover for the next session building the ValiChord public demo website. The previous session designed the full architecture but wrote zero code. This document tells you exactly what to build, in what order, without breaking what already exists.

---

## What Already Exists — DO NOT BREAK

| Component | Location | Status | Notes |
|---|---|---|---|
| valichord_at_home analysis | `valichord_at_home/` | Live on Render | 80+ detectors, Claude semantic analysis |
| Flask API | `backend/app.py` | Live on Render | `/validate`, `/attest`, `/result`, `/download`, `/health` etc. |
| Holochain conductor | Oracle `132.145.34.27` | Always-on | 5 apps, 3-validator + single-validator |
| Node.js bridge | Oracle `demo/serve.mjs` | Always-on port 5000 | `/holochain/validate-round-multi`, `/record/<hash>` |
| HTTP Gateway | Oracle port 8090 | Always-on | Raw zome calls |
| ai_validator.py demo | `demo/ai_validator.py` | Working CLI | Runs from Codespace or Oracle SSH |
| Security tests | `valichord/tests/src/security.test.ts` | 96 tests passing | DO NOT regress |

**Hard rules:**
- All new routes go into `backend/app.py` as additions — never modify existing routes
- Oracle receives no changes — it stays as-is (new validator nodes are additive, not modifications)
- No new Render services — extend the existing `backend/app.py` deployment
- The `ANTHROPIC_API_KEY` lives on Render, NOT on Oracle
- Validator bridge URLs must be environment variables (`VALICHORD_VALIDATOR_N_URL`) — never hardcoded — so adding nodes later requires no code changes

---

## What We Are Building

A public-facing demo website accessible at the existing Render URL. Three entry points on one page.

### Entry Point 1: Demo Gallery
A curated list of 2–3 studies visitors can run with one click. Each runs the full commit-reveal protocol with 3 Claude Haiku validators and produces a permanent HarmonyRecord URL.

**Studies planned:**
- The existing synthetic linear regression study (guaranteed to work — this is the fallback)
- 1–2 real Zenodo deposits (to be sourced and pre-verified — see below)

**Key design decision:** Studies in the gallery are pre-run by us once to capture exact expected outputs. These outputs are baked into the deposit's README before it enters the gallery. No code execution happens at demo time for gallery studies.

### Entry Point 2: Structured Submission Form
A form that generates a standardised README automatically. Researchers fill in answers; the form produces the README. Based on the 12-point "perfect README" from `ValiChord_Repository_Cleaning_Specification_15.md` Section 2, Component 1.

**Critical form fields (what validators need):**
- What does your study claim to find? (plain language)
- Key numerical results (item 8 — expected outputs)
- What code runs and in what order? (item 6 — execution instructions)
- Dependencies (item 5 — installation)
- Definition of successful reproduction (item 9 — explicit statement)
- Upload: code + data ZIP

### Entry Point 3: Deposit Checker + Auto-Fix (Demo Mode)
Upload any deposit ZIP → valichord_at_home analysis → Claude auto-fixes using the spec → fixed deposit sent to validators.

**IMPORTANT — auto-fix is DEMO ONLY:**
- In the demo: AI fixes are applied automatically and sent straight to validators
- In the real product (future): researcher must review and approve every AI fix before validators see it
- This distinction must be clearly stated on the page for honesty

**What the auto-fixer does:**
- Uses `ValiChord_Repository_Cleaning_Specification_15.md` as its instruction manual (system prompt)
- Focuses primarily on items 8 and 9 of the README (expected outputs + definition of reproduction) — without these, validators cannot assess
- Reads the code to infer expected outputs (does NOT execute arbitrary code — see decision below)
- Generates/completes the README
- Fixes obvious issues (absolute paths → relative, missing licence placeholder, etc.)

**Code execution decision:**
Arbitrary researcher code is NOT executed during the demo. Reasons: no sandboxing on Render, security risk, complexity. Claude reads the code and infers expected outputs — good enough for simple analyses. Real execution is deferred to v2 with proper sandboxing (E2B or Modal). Gallery studies are pre-run once by us.

---

## The Full Demo Flow (Entry Point 3)

```
1. User uploads ZIP (or picks Zenodo study)
         ↓
2. valichord_at_home detectors run
   → identifies gaps (missing README sections, no expected outputs, etc.)
         ↓
3. Claude Haiku (fixer call) reads:
   - The deposit contents
   - valichord_at_home findings
   - ValiChord_Repository_Cleaning_Specification_15.md as system prompt
   → produces fixed/completed README with items 8+9 filled in
   → produces list of what was changed (shown to user)
         ↓
4. "Before / After" shown to user:
   - Before: valichord_at_home findings (what was wrong)
   - After: what the AI fixed (clearly labelled as AI-generated, not researcher-verified)
         ↓
5. Fixed deposit → POST Oracle:5000/holochain/validate-round-multi
   with 3 Claude Haiku validator calls (ANTHROPIC_API_KEY on Render)
         ↓
6. Progress display (live steps, ~90 seconds)
         ↓
7. HarmonyRecord written to DHT
   → Permanent shareable URL displayed
   → Note on page: "AI fixes were applied automatically for this demo.
     In production, researchers review all changes before validation."
```

---

## Architecture

```
Render (backend/app.py)
  ├── ANTHROPIC_API_KEY        ← Claude Haiku calls happen here
  ├── VALICHORD_ORACLE_URL     ← http://132.145.34.27:5000
  ├── VALICHORD_ORACLE_KEY     ← API key for Oracle bridge
  │
  ├── GET  /demo               ← new: the public demo page (HTML)
  ├── POST /demo/run           ← new: starts a demo job (gallery study)
  ├── POST /demo/analyse       ← new: upload → fix → validate flow
  ├── GET  /demo/result/<id>   ← new: poll for job status + progress steps
  └── GET  /demo/record/<hash> ← new: proxy to Oracle /record/<hash> (CORS fix)

Oracle (unchanged)
  └── serve.mjs + Holochain conductor — accepts calls, knows nothing about Render
```

**New environment variables needed on Render:**
- `ANTHROPIC_API_KEY` — for Haiku fixer + validator calls
- `VALICHORD_ORACLE_URL` — `http://132.145.34.27:5000`
- `VALICHORD_ORACLE_KEY` — `valichord-demo-2026` (the existing Oracle API key)

---

## Concurrency / Demo Lock

The Oracle conductor handles concurrent rounds fine (each run has a unique salted data hash). However `serve.mjs` is single-threaded Node.js — concurrent POSTs will queue at the bridge. For the demo, implement a simple in-memory lock in `backend/app.py`:

- If a demo job is already running: return `{"status": "busy", "message": "Demo in progress — check back in ~2 minutes"}`
- This prevents Oracle being hammered and makes the demo feel more real ("live system")
- Lock releases when the job completes or errors

---

## Claude Model

Use `claude-haiku-4-5-20251001` for BOTH:
1. The fixer call (reads deposit, writes improved README)
2. The 3 validator calls (assess the fixed deposit)

The current `demo/ai_validator.py` uses `claude-opus-4-6` — change this to Haiku for the web flow. The CLI demo can keep Opus if desired.

The validator prompt in `demo/ai_validator.py` `form_verdicts()` is already written and tested. Reuse it exactly.

---

## Progress Display

The ~90 second Oracle round needs a progress display. Use async job pattern (like existing `/validate`):

- `POST /demo/run` returns `{"job_id": "..."}` immediately
- Client polls `GET /demo/result/<id>` every 2 seconds
- Response includes a `step` field (1–7) so the UI can animate progress stages
- No SSE/websockets needed — simple polling is sufficient

Steps to display:
1. Loading study deposit
2. Running pre-submission check
3. Applying AI fixes
4. Forming 3 independent validator verdicts
5. Running commit-reveal protocol
6. All commitments sealed and revealed
7. HarmonyRecord written — done

---

## The Curated Gallery — Status

**Synthetic study (existing):** `demo/synthetic_study/` — linear regression, slope/intercept/R², deterministic, always works. This is the guaranteed fallback.

**Real Zenodo studies:** NOT YET SOURCED. This is the main open task before building Entry Point 1.

Requirements for a gallery study:
- Freely downloadable from Zenodo (open licence, public DOI)
- Pure Python with standard deps (pandas, numpy, scipy, matplotlib only)
- Small dataset (< 5 MB, fits in memory)
- Deterministic output (no randomness, or seeded)
- Runs in < 30 seconds
- README states (or can be amended to state) explicit numerical results
- Interesting to a general audience (climate, ecology, social science, economics preferred)

**Search strategy:** Use Zenodo's API/search. Look for deposits with `requirements.txt`, `README.md`, Python scripts, and small CSV files. Target domains: bibliometrics, ecology, social science. Verify by downloading and actually running.

**Self-citations study** (`zenodo.org/records/14844342`) was identified as a potential candidate — interesting topic, Python + pandas/scipy, 2.5 MB CSV. README is tiny (588 bytes) so item 8/9 would need adding. Not yet verified to run.

---

## The Specification File

`ValiChord_Repository_Cleaning_Specification_15.md` (root of repo, 1445 lines) is Ceri's v15 spec from February 2026. It defines all failure modes (A–BL) and what a perfect repository looks like.

**How to use it as a fixer prompt:**
- Pass the full spec as the system prompt to Claude Haiku
- Pass the deposit contents + valichord_at_home findings as the user message
- Ask Claude to: (1) identify which failure modes apply, (2) produce a fixed README with items 8+9 completed, (3) list what was changed and what the researcher must still verify
- The spec is long (~1500 lines) — use prompt caching (Anthropic SDK `cache_control`) to avoid re-sending it on every call

**Note on spec version:** v15 is from February 2026. valichord_at_home has been extended since (Pattern Q, T, R, U, V, S, J, H, I, E, L, M, N, K, etc. from memory). The spec does not cover all current detectors. This is fine for the fixer — the spec covers the structural/conceptual gaps; valichord_at_home covers the detailed pattern checks. They complement each other.

---

## UI Design

Inherit the visual style from `valichord-at-home.html` (uploaded to repo root — this is the old deposit checker UI):
- Dark theme: `#07070f` background, `#c8c4bc` text
- `Newsreader` serif for headings, `DM Sans` for body
- Blue accent: `#4a90d9`
- Card style: `#0b0b18` background, `#141424` border, `14px` radius

The new demo page should be a single HTML file served by Flask at `GET /demo`, or a separate static page on Render pointing to the Flask API.

---

## Build Order (Recommended)

Do these in sequence. Each step is independently testable before moving to the next.

### Step 1: Backend scaffold (no UI)
- Add `GET /demo/ping` to `backend/app.py` — confirms new routes work on Render
- Add the demo job store (separate from `_jobs` to avoid confusion)
- Add the demo lock mechanism
- Deploy to Render, verify ping works

### Step 2: Gallery flow (Entry Point 1)
- Port `demo/ai_validator.py` logic into a new `backend/demo_runner.py` module
- Change model to `claude-haiku-4-5-20251001`
- Add `POST /demo/run` (takes `study_id`, runs the synthetic study)
- Add `GET /demo/result/<id>` with step progress
- Test end-to-end from Codespace against Oracle: synthetic study → HarmonyRecord
- Add `GET /demo/record/<hash>` proxy

### Step 3: Simple UI for gallery
- Build the demo HTML page (inheriting valichord-at-home.html style)
- Three sections visible but Entry Points 2 and 3 show "coming soon"
- Gallery: synthetic study card + "Run Demo" button + progress display + result
- Deploy and test publicly

### Step 4: Find and add real Zenodo studies
- Download and verify candidates
- Pre-run to capture exact outputs
- Add `claimed_results` to README
- Add as gallery entries (study_id = `zenodo_<record_id>`)

### Step 5: Structured form (Entry Point 2)
- Build the 12-field form (Section 2 of spec)
- Form → README generator (Python function in `demo_runner.py`)
- Generated README + uploaded ZIP → same validator flow as gallery
- Add to demo page

### Step 6: Auto-fix flow (Entry Point 3)
- Add the fixer Claude call using spec as system prompt (with prompt caching)
- Wire valichord_at_home findings → fixer → fixed deposit
- Add "before/after" display (what was broken, what was fixed)
- Add the "AI fixes not researcher-verified" disclaimer
- Test with the self-citations Zenodo deposit or similar

---

---

## Decentralisation Strategy

### Why this matters

The Oracle at `132.145.34.27` currently runs **all** app instances (researcher + validator-1/2/3) on one machine. This means the demo is effectively centralised — the commit-reveal protocol is cryptographically correct, but the DHT is not actually distributed. A centralised database with SHA-256 hashing would produce an identical demo experience.

ValiChord's core claim — that **neither the researcher, nor the validators, nor ValiChord itself can manipulate the outcome** — is a cryptographic guarantee in production but only a policy promise in the current demo. The demo needs to at least gesture toward genuine distribution to make this claim credible.

The three options below were evaluated on 2026-04-20. **Option A is the chosen next step.**

---

### Option A — Geographic spread via Fly.io (CHOSEN — build this next)

Run each validator conductor on a **separate cheap cloud VM** in a different geographic region. Fly.io supports Docker deployment globally with a free tier.

```
Oracle (US-East)      → researcher node + validator-1 (existing, no changes)
Fly.io (EU-West)      → validator-2 conductor only
Fly.io (Asia-Pacific) → validator-3 conductor only
```

The DHT gossip between the three machines is real. If Oracle dies, the EU and AP nodes still hold the HarmonyRecord. The Render backend calls each VM's bridge endpoint independently rather than one monolithic Oracle endpoint.

**What the demo UI can honestly say:** *"Validator 1: US-East | Validator 2: Frankfurt | Validator 3: Singapore"* — and that's true. Different administrative domains, real network gossip, different failure modes.

**Effort:** Medium — one session.
- Build a Docker image for a standalone validator conductor + bridge
- Deploy to Fly.io in two regions
- Update `serve.mjs` or create a new multi-endpoint coordinator in `backend/app.py`
- Update the UI to show validator locations

**What to preserve:** Oracle stays unchanged. The new validator nodes just join the same app network. Validator bridge URLs become environment variables on Render (`VALICHORD_VALIDATOR_1_URL`, etc.) so adding more nodes later is just adding an env var.

**Key design rule for Option A:** Make the validator URL list configurable from the start (env vars or a small config). This means upgrading to Option B later is just adding more entries, not refactoring.

---

### Option B — "Run your own validator" pool (future — the real product vision)

Publish a Docker image that anyone can run:

```bash
docker run valichord/validator --bootstrap wss://bootstrap.valichord.org
```

It starts a conductor, connects to ValiChord's bootstrap server, and registers as an available validator. When a study comes in, the protocol picks N live validators from the pool automatically.

This means **ValiChord the company cannot control the validator set**. If independent researchers, journals, or institutions run nodes, the outcome is genuinely beyond any single party's control. This is the correct production architecture.

**What needs building beyond Option A:**
- A validator registry service (tracks live validator endpoints)
- Bootstrap server (or use Holochain's public bootstrap)
- Dynamic validator selection at job-start time (pick N from live pool)
- A simple "join as validator" onboarding page

**Effort:** Large — multiple sessions. Not a demo task; this is the v1 product architecture.

**Note:** Option A's configurable validator URL list is the bridge to Option B. When the registry exists, `backend/app.py` queries it instead of reading static env vars.

---

### Option C — Researcher's machine as a node (future — most honest expression)

The person submitting a study runs a lightweight client (browser app or tiny desktop app). Their node writes the researcher's commitment to their own source chain before validators see anything. They literally watch their own entry appear.

This is the purest expression of Holochain's agent-centric model: the researcher owns their claim on their own chain, not on ValiChord's server.

**Blocker:** Requires a browser-compatible Holochain runtime (Holochain Launcher or web-happ). Maturity of browser runtime is the gating dependency — revisit when Holochain's web-happ story is stable.

**Effort:** Large — depends on Holochain upstream. Not actionable until browser runtime is ready.

---

## Open Questions (Decide at Session Start)

1. **Zenodo gallery studies** — which real studies? Needs sourcing + testing before Step 4.
2. **Demo page URL** — served at `GET /demo` from Flask, or a separate static page?
3. **"Submit your research" vs "Check your deposit"** — are Entry Points 2 and 3 one flow or two separate paths? (Currently designed as two: form = 2, upload+fix = 3)
4. **Disclaimer wording** — for the auto-fix path, needs to be honest without undermining the demo
5. **Rate limiting on demo runs** — one at a time (busy lock) is decided; should there also be a per-IP daily limit?

---

## Key Files to Read at Next Session Start

1. `PROJECT_STATUS.md` — current live state
2. `backend/app.py` — existing Flask routes (understand before adding new ones)
3. `demo/ai_validator.py` — the validator logic to port into the web flow
4. `demo/serve.mjs` — Oracle bridge (understand `/holochain/validate-round-multi` contract)
5. `ValiChord_Repository_Cleaning_Specification_15.md` — the fixer's instruction manual
6. This file (`docs/DEMO_WEBSITE_PLAN.md`)

---

*This plan was designed in the session of 2026-04-17. No code has been written yet. The existing system is fully intact.*
