# ValiChord Live Demo — Public Web Interface

**Live at: [valichord-demo.onrender.com/demo](https://valichord-demo.onrender.com/demo)**

Built on **Holochain** — a peer-to-peer network where no single node is in charge. Every HarmonyRecord produced by the demo is content-addressed, independently fetchable, and tamper-evident. No blockchain. No tokens. No central authority.

---

## What it is

A browser interface to the full ValiChord commit-reveal protocol running on live Holochain nodes on Oracle Cloud. One demo runs on the page:

| Demo | Who pays | Validators | Hypothesis |
|---|---|---|---|
| **Your Hypothesis** | User (own Anthropic key) | 3 CMA agents with live web search | Any claim the user writes |

> **Note:** A server-funded "Free Demo" (3 Claude Haiku validators on a pre-loaded ecology study) was removed in June 2026 because every visitor run drew on the server's own Anthropic key. The page now runs exclusively on the visitor's own `sk-ant-` key — the server key is never used to serve demo traffic.

The page includes a skeptic-proof verify section after every run: the HarmonyRecord hash is unique to that run, generated on the Oracle DHT, and fetchable from any machine with a single `curl` command that has nothing to do with this website.

---

## Your Hypothesis demo

### What it does

The user enters a hypothesis and their own assessment of it. That assessment is cryptographically hashed and committed to the Holochain DHT **before** the three Claude CMA validators begin their independent research. The validators cannot see the user's answer or each other's. Once all three have committed, a flashing green Reveal button appears. The user clicks it; the answers unseal; an adjudicator Claude call compares the researcher's sealed answer against the three validator verdicts; a HarmonyRecord is written to the DHT.

### Two-phase protocol

**Phase 1 — Commit (background thread, ~5–8 minutes)**

1. `classify_discipline(claim, api_key)` — a short Haiku call classifies the claim into an academic discipline (e.g. "Social Psychology", "Exercise Science") and returns `{"type": "Other", "content": "<name>"}` for the DHT. This runs before anything is written to the network.
2. The user's answer is SHA-256 hashed with a random UUID salt → `POST /lock-result` on the researcher node.
3. `POST /submit-request` creates a `ValidationRequest` on the DHT with `num_validators_required: 3`.
4. 30-second sleep to let the `ValidationRequest` propagate via DHT gossip to all validator nodes.
5. Three CMA validator sessions run in parallel via `ThreadPoolExecutor`. Each validator:
   - Creates a dedicated Holochain CMA environment + agent + session
   - Receives a `user.message` with the hypothesis and its validator index
   - Works through 5 steps using `web_search`, `web_fetch`, and `write` tools
   - Writes its verdict to `/mnt/session/verdict.json` — `outcome`, `confidence`, `reasoning`
   - If the session goes idle without writing a verdict, a fresh session is created on the same env/agent (up to `_MAX_ATTEMPTS = 2` total attempts)
   - Calls `POST /commit` on its assigned validator node; retries up to 6 times (15 s apart) if the ValidationRequest hasn't propagated yet
6. Once all three have committed, `job["phase"]` is set to `"awaiting_reveal"`. The UI Reveal button starts pulsing green. If any validators fail after all retry attempts, a descriptive error names exactly which ones failed.

**Phase 2 — Reveal (triggered by user click)**

1. Polls `GET /phase` on the researcher node until `"RevealOpen"` (up to 240 s).
2. `POST /reveal` on the researcher node — unseals the researcher's commitment.
3. `POST /reveal` on each of the three validator nodes (15 s apart to avoid DHT write conflicts); each call retried up to 3 times on transient network errors.
4. `compare_answers(claim, user_answer, verdicts, api_key)` — a single non-CMA Claude call that reads all four sealed answers and returns a human-readable `summary` comparing the researcher's answer to the panel. (Its `outcome`/`agreement_level` are no longer used for display; a malformed-JSON reply falls back to a neutral summary so the HarmonyRecord is still written.) The displayed `outcome` and `agreement_level` are derived from the validator verdicts by `demo/agreement.py`, which mirrors the on-chain Rust logic (`shared_types::derive_majority_outcome` / `derive_agreement_level`) — so the label always matches the HarmonyRecord a skeptic fetches, and can never show "3/3 Reproduced" beside a contradictory agreement level.
5. `POST /create-harmony-record` → permanent HarmonyRecord on the DHT.
6. `job["phase"] = "done"` — UI renders the full result.

### CMA validator system prompt

Validators follow a structured 5-step protocol:

1. Identify the precise claim
2. Determine what evidence would support or refute it
3. Search using `web_search` and `web_fetch`
4. Assess the quality, consistency, and relevance of evidence
5. Write a verdict: `Reproduced` / `PartiallyReproduced` / `NotReproduced` with `High` / `Medium` / `Low` confidence and ≥3 sentences of reasoning

### Request flow

```
Browser → POST /demo/custom/run         { claim, user_answer, user_api_key }
        ← { job_id }                    202 — background thread starts Phase 1

Browser → GET /demo/custom/result/<id>  (polled every 2 s)
        ← { phase, validators_committed, status, result }
        # phase: starting → committing → awaiting_reveal → revealing → done

Browser → POST /demo/custom/reveal/<id> (user clicks Reveal button)
        ← { status: "revealing" }       202 — background thread starts Phase 2

Browser → GET /demo/custom/result/<id>  (resumes polling)
        ← { status: "done", result: { ... } }
```

Private fields (`_claim`, `_user_answer`, `_api_key`, `_started_at`) are stored in the job dict but never returned by the poll endpoint.

### Result object

```json
{
  "harmony_record_hash": "uhC8k…",
  "external_hash_b64": "…",
  "outcome": "Reproduced | PartiallyReproduced | FailedToReproduce | UnableToAssess",
  "agreement_level": "ExactMatch | WithinTolerance | DirectionalMatch | Divergent | UnableToAssess",
  "headline": "Refuted — validators unanimous (matches your sealed answer)",
  "comparison_summary": "…",
  "researcher_answer": "…",
  "validator_count": 3,
  "researcher_reveal_hash": "…",
  "record_url": "http://132.145.34.27:3001/record?hash=…",
  "validator_verdicts": [
    { "validator": 1, "outcome": "…", "confidence": "…", "reasoning": "…" },
    …
  ]
}
```

Note: `outcome` and `agreement_level` are derived from the validator verdicts with the same logic as the on-chain HarmonyRecord, so the displayed label always matches the record you can fetch yourself (validator-to-validator consensus). `comparison_summary` is the separate researcher-to-validator narrative from `compare_answers` — it explains how the panel's finding relates to the researcher's sealed answer, but does not drive the outcome label.

`headline` is a **display-only** field (`_claim_headline` in `custom_runner.py`) that translates the result into claim vocabulary for the badge. The reproducibility scale bottoms out at "UnableToAssess" for a unanimous *refutation* — technically correct (zero "reproduction") but confusing, because the validators clearly assessed the claim and agreed. The headline buckets the validator outcomes into **Supported / Partially supported / Refuted / Inconclusive**, notes unanimity (e.g. "validators unanimous", "2 of 3 validators agree", "validators split"), and appends whether the researcher's sealed answer aligned (from the `compare_answers` outcome: "matches / partly matches / diverges from your sealed answer"). The badge in `app.py` uses `headline` when present and falls back to the old `{outcome} — {agreement_level}` format. Nothing on-chain changes — the HarmonyRecord still records the reproducibility vocabulary, and `outcome`/`agreement_level` remain in the result dict for the raw-record view.

### Concurrency

One custom run at a time, enforced by `_custom_running` bool + `_custom_lock`. A second visitor during an active run gets a 409. The lock is held through both phases — it is not released between commit and reveal. A background watchdog thread releases it automatically if a job gets stuck in any non-terminal phase (starting, committing, or awaiting_reveal) for more than 30 minutes.

### Requires

- Anthropic API key beginning `sk-ant-` (CMA requires the Anthropic SDK, not OpenAI-compatible)
- Estimated cost: $0.50–1.50 per run depending on hypothesis complexity
- The key is used only for this run and never stored or logged

---

## Free demo (removed)

The server-funded free demo was removed in June 2026. It used the server's `ANTHROPIC_API_KEY` for every visitor run, so public traffic spent the operator's own quota — the cause of repeated rate-limit alerts. The `/demo/run` and `/demo/result/<id>` routes, their job state, and the per-IP/monthly-budget rate-limit logic are all gone from `app.py`.

`demo/demo_runner.py` (the old free-demo study logic) is **not** deleted — it is still imported by `core_bench_runner.py` for its node HTTP helpers (`_node_post`, `_node_get`, URL config) and is exercised by `tests/test_demo_runner.py`. It is simply no longer reachable from the website.

---

## Rate limiting

| Demo | Limit | Enforcement |
|---|---|---|
| Custom | 1 concurrent run (global) | `_custom_running` bool + 30-min watchdog |

The custom demo runs on the visitor's own key, so there is no server-cost budget to enforce — only the single-concurrent-run lock.

---

## UI design

- **No tabs** — linear scroll layout. Your Hypothesis is the single hero section at the top, followed by the explainer accordions.
- **Five expandable accordions** (`<details>`/`<summary>`) below the demo explain the protocol, why it's remarkable, why Holochain instead of a blockchain, why a centralised server can't provide the same trust layer, and why validator disagreement is a feature not a failure.
- **Holochain logo** in the header — "Built on / [logo]" badge links to holochain.org.
- **Google Fonts** — DM Sans (body) + Newsreader (headings) loaded from fonts.googleapis.com.
- **Reveal button** — greyed out until all 3 validators have committed, then turns green with a pulsing box-shadow animation (`readyPulse` keyframe).
- **Validator dots** — three animated dots update in real-time as each CMA validator finishes and commits.

---

## Files

| File | Purpose |
|---|---|
| `demo/app.py` | Flask server — all routes, job state, background threads, HTML |
| `demo/demo_runner.py` | Node HTTP helpers + Oracle URL config (reused by `core_bench_runner.py`). Formerly the free-demo study logic; no longer reachable from the website. |
| `demo/custom_runner.py` | Your Hypothesis logic — CMA sessions, classify_discipline, compare_answers, two-phase protocol |
| `demo/ai_validator_cma.py` | CMA session helpers — `_node_post`, `_node_get`, `BETAS`, `MODEL_CMA`, `detect_key_type` |
| `demo/synthetic_study/study.py` | The actual study code validators reproduce |
| `demo/static/valichord-logo.jpeg` | ValiChord logo in header |
| `demo/static/holochain-logo.png` | Holochain logo in header |
| `demo/requirements.txt` | `flask`, `flask-cors`, `anthropic`, `gunicorn` |
| `demo/Dockerfile` | Container — python:3.12-slim, non-root appuser, gunicorn |
| `render.yaml` | Render service configuration |

---

## Running locally

```bash
cd demo
pip install flask flask-cors anthropic gunicorn

export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004

python app.py
# opens at http://localhost:8080/demo
```

This runs against the live Oracle nodes — no local Docker setup needed. The Your Hypothesis demo runs entirely on the `sk-ant-` key the visitor pastes into the form. The server's `ANTHROPIC_API_KEY` is **no longer used to serve any demo traffic** — `export` it locally only if you also run CLI tools like `core_bench_runner.py`.

---

## Deploying to Render

1. Connect `topeuph-ai/ValiChord` to Render
2. Render picks up `render.yaml` and builds from `demo/Dockerfile` (context: repo root)
3. Every push to `main` triggers an automatic redeploy

The Oracle node URLs are set in `render.yaml` and are not secrets. **Do not set `ANTHROPIC_API_KEY` on the Render service** — the website no longer uses a server key, and setting one would expose the operator's quota to public traffic (the exact problem the free-demo removal fixed). The custom demo runs only on the key each visitor pastes in.

**Dockerfile notes:**
- `python:3.12-slim`, runs as non-root `appuser`
- COPY line includes all four Python modules: `app.py`, `demo_runner.py`, `custom_runner.py`, `ai_validator_cma.py`
- Gunicorn: `--workers 1 --threads 4 --timeout 180` (180 s covers the full protocol round-trip)
- Static files served from `demo/static/` — both logos are included
- Health check: `GET /health` → `{"status": "ok"}`

---

## Verifying the result independently

At the end of any run, the page shows a `curl` command:

```bash
curl "http://132.145.34.27:3001/record?hash=uhC8k…"
```

Run that from any machine. The response is raw HarmonyRecord JSON from the Oracle DHT — not served by this website. The hash is unique to the run (derived from a per-run UUID salt on the data hash) so it cannot be pre-computed or reused.

The **Fetch raw record from Oracle** button does the same thing live in the browser via `GET /demo/record/<hash>`, which proxies to the Oracle node and returns the JSON unmodified.
