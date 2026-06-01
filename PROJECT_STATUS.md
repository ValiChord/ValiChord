# ValiChord — Current Project Status

**Last updated:** 2026-06-01
**Phase:** Full protocol running end-to-end on Oracle. Public web demo live at valichord-demo.onrender.com/demo. Svelte/TS frontend wired to live conductor, end-to-end tested. **v0.5.7** — Demo website redesign: Your Hypothesis demo (CMA validators, user's own key, user-triggered reveal) is now the primary hero section; five accordion explainers sell the protocol; Holochain logo in header; discipline classification via Claude (no more hardcoded ComputationalBiology); DEMO_WEBSITE.md fully rewritten. v0.5.5: CMA upgrade — AI validators use Claude Managed Agents (web search, multi-step reasoning); users bring their own Anthropic key; rate limiting on server key. Holochain 0.6.1 (hdk/hdi/holo_hash/holochain_serialized_bytes; iroh/QUIC transport; full test suite green). `valichord_attestation` at v1.2 (Metric.filter, Bundle.meta, dual content_hash) with three adapters (InspectAI, InspectEvals, PiSession) and a `ValiChordLogger` PR in flight for lm-evaluation-harness. 326 valichord_attestation tests, 99% line coverage.

---

## What ValiChord does (one paragraph)

ValiChord is a scientific reproducibility verification system built on Holochain. A researcher deposits a hash of their data and result claim. Independent validators each reproduce the analysis blindly, seal their verdict using a commit-reveal protocol, then reveal simultaneously — removing any last-mover advantage. Outcomes are aggregated into a tamper-evident **HarmonyRecord** on a public DHT. No central party can alter it after the fact.

**valichord_at_home** (separate tool, live on Render) runs 100+ automated deposit-quality checks and Claude semantic analysis to help researchers prepare a clean, reproducible deposit before the protocol begins. It does not produce the validation verdict — validators do.

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
| Decentralised demo | **Permanently live on Oracle** | 5 isolated Docker containers (bootstrap + researcher + 3 validators) on Oracle server (132.145.34.27); `restart: unless-stopped` survives reboots. Run locally: `docker compose up` + `python3 demo/ai_validator.py --mode decentralised`. Oracle: containers already up. |
| Public web demo | **Live on Render** | Flask app at `valichord-demo.onrender.com/demo`. **Two demos on one page:** (1) *Your Hypothesis* — user enters any claim + their own sealed answer + Anthropic key; 3 CMA validators research it blind in parallel; user clicks a pulsing green Reveal button once all 3 commit; adjudicator Claude call compares answers; HarmonyRecord written to DHT. (2) *Free Demo* — pre-loaded ecology study, server pays, once/day per IP. No tabs — linear scroll layout with five expandable accordion explainers (how it works, why remarkable, why Holochain not blockchain, why not central server, why disagreement is fine). Holochain logo in header. |
| Node.js bridges | **Working** | `researcher-node.mjs` (port 3001) + `validator-node.mjs` (ports 3002–3004) — HTTP APIs over each conductor |
| HarmonyRecord URL | **Working** | `GET /record?hash=<hash>` on researcher node — no auth, returns clean JSON. On Oracle: `http://132.145.34.27:3001/record?hash=<hash>` (port 3001 must be open in Oracle Security List). |
| Feynman skill (was PR #13) | **Historical** | Feynman is no longer operational (April 2026). Superseded by `demo/ai_validator.py` (direct Claude API). |
| valichord-ui (Svelte/TS frontend) | **Working end-to-end** | Full UI for all three roles (researcher, validator, governance). Wired to a live local conductor: `bash dev.sh` starts conductor + installs app + writes auth token; `npm run dev` serves at `:5173`. `submit_validation_request` → DHT → `get_validation_request_for_data_hash` verified. See `valichord-ui/README.md` and `FRONTEND.md`. |

---

## How the demo runs end-to-end

Five Docker containers — researcher + 3 validators + kitsune2 bootstrap server — each with their own Holochain conductor, keystore, and SQLite database. The only communication between containers is the DHT. **Neither the researcher nor any validator can see each other's results before committing.** Validators do not know what other validators concluded. The researcher cannot know what validators will say. The commit-reveal protocol enforces this structurally — not by policy.

**Run locally:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose -f demo/docker-compose.yml up --build -d
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
python3 demo/ai_validator.py --mode decentralised
```

**Run against Oracle (already running — no Docker setup needed):**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004
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
  http://132.145.34.27:3001/record?hash=uhC8k…

  Verifying record is readable…
  Record confirmed. Outcome: Reproduced  Agreement: ExactMatch  Validators: 3

════════════════════════════════════════════════════════════
  Demo complete. The full ValiChord protocol ran end-to-end.
  Researcher and 3 validators all commit-revealed simultaneously.
════════════════════════════════════════════════════════════
```

Full architecture, retry design, and commit-reveal table: **`demo/DECENTRALISED_DEMO.md`**

---

## Recently completed

### CORE-Bench demo review-hardening — 2026-06-01 ✓

Three review-hardening units merged to `main` (fast-forward; **local — not yet pushed at the time of writing**). Built TDD via subagent-driven-development (fresh implementer + spec-compliance + code-quality review per task) in an isolated worktree. **No integrity-zome or DNA-hash change.** All green: Python 44 / JS 5 / Rust 27 (incl. a cross-language agreement golden test). Full detail in `demo/CORE_BENCH_DEMO.md` → "Review-hardening"; spec/plan under `docs/superpowers/`.

1. **Capsule blinding gate** (`demo/capsule_blinding_gate.py`) — after the researcher seals the claim and before any validator runs, scans every *retained* (hard-mode-surviving, prefix-aware) capsule file for the committed answer (rounded-form on all files; interval-membership on doc files only). Hard-aborts the round with `CapsuleLeakError` if the answer leaks, so "independent execution" can't reduce to "read the number". Wired into `core_bench_runner`; spike prints a non-fatal leak report.
2. **`/record` numeric-convergence panel** — `GET /record` now returns a per-validator value-vs-committed-interval panel with explicit degradation states (full / `"pending"` / base-only; never 500s). Pure JS helpers in `node-lib.mjs` (`numericMatch` is a faithful port of Python `match_value`, inclusive bounds, empty/whitespace → non-match); base fields stay back-compatible with `ai_validator.py`.
3. **Agreement parity** — `derive_agreement_level`/`derive_majority_outcome` pinned to a shared `valichord/shared_types/tests/agreement_golden.json` asserted by **both** Python and a new Rust `#[test]` (cross-language drift guard). The runner echoes the **authoritative on-chain `outcome`/`agreement_level`** read gossip-free on the authoring node (`/create-harmony-record` returns them), with a labelled recompute fallback (`agreement_recomputed`).

Two review-caught bugs fixed during the run: `numericMatch('')` returned `true` in JS (diverged from Python) → guarded; the echoed adjacent-tagged `outcome` printed as `{'type': 'Reproduced'}` → normalized to a bare string. Known follow-up: `researcher-node.mjs` `/record` still returns the raw `{type:…}` outcome dict in its base fields — worth normalizing in the JS layer if a UI consumes it.

### CORE-Bench integration strategy — 2026-05-29 ✓

Strategic analysis and integration doc for combining ValiChord with CORE-Bench (the inspect_evals benchmark for AI computational reproducibility). Full doc at `docs/CORE_BENCH_INTEGRATION.md`.

**Key insights:**

- **The capsule is the input layer.** A CodeOcean capsule already contains everything ValiChord needs as structured input: code + data (the claim, operationally defined), `README.md` / `REPRODUCING.md` (instructions any independent party can follow), and specific numerical outputs (the pre-defined metrics validators check against). A researcher with an existing capsule has already done ValiChord's hardest UX work without knowing it.

- **Automatic metric extraction closes the loop.** CORE-Bench's agent can be run once by the researcher to extract key numerical outputs. Those outputs become the committed metrics. The researcher didn't manually define metrics — their code defined them.

- **Validator count is a parameter, not a constant.** The current demo uses three validators for illustration; the protocol places no architectural limit. The optimal number for any given claim (routine benchmark vs regulatory submission) is an open empirical question — analogous to statistical power analysis in clinical trial design.

- **What N independent computational runs actually prove.** For deterministic code, commit-reveal protects against result copying (validator B copying validator A's `report.json` instead of running the code), not opinion anchoring. This is a real and defensible guarantee — stated precisely it is hard to poke. N runs prove: (a) the capsule executes from scratch without hints, (b) the result is robust to independent environments, (c) no agent fabricated or copied a result.

- **Design constraint: ground-truth vs committed claim.** Validators commit their raw `report.json` before the researcher reveals. ValiChord agreement is researcher-claim-relative. CORE-Bench ground truth (the official benchmark answers) is a separate optional overlay and must not be available at commit time — doing so would defeat blinding.

- **`FailedToReproduce` not `NotReproduced`.** The valid `AttestationOutcome` enum values are `Reproduced | PartiallyReproduced | FailedToReproduce | UnableToAssess`.

- **Tolerance function must be pinned.** Numeric tolerance (e.g. "within 0.5% counts as a match") is currently client-side in the Python adapter before becoming an outcome enum. For "no trust required at any layer" to hold, the tolerance configuration should be committed alongside the researcher's metrics.

**Demo spec:** three validators (illustrative), hard difficulty, Python capsule, no GPU, <5 min, numeric outputs. Build estimate ~6–8 days with capsule selection on the critical path. See `docs/CORE_BENCH_INTEGRATION.md` for full architecture, demo output, and infrastructure requirements.

**inspect_evals outreach context:** `docs/inspect_evals_issue_and_pr.md` contains a draft issue (target: 2026-06-02) and PR proposing two optional YAML fields (`valichord_attestation_uri`, `valichord_harmony_record_uri`) in the register schema. CORE-Bench is named in the issue as the most direct example. The integration doc and demo are held for follow-up once the issue gets a positive response.

---

### Release v0.5.7 — Demo reliability hardening — 2026-05-29 ✓

10-commit reliability overhaul of the public demo, driven by user reports of "validator 1/2/3 ended without giving a verdict." Root cause: the custom demo path (`custom_runner.py`) had never received the hardening applied to the free path (`ai_validator_cma.py`) in v0.5.5/v0.5.6.

**Fixes shipped (custom_runner.py):**
- **Hardened system prompt** — ported the "REQUIRED FINAL ACTION — YOU MUST DO THIS" block and "Do not put your verdict in a text response" instruction to `VALIDATOR_CLAIM_SYSTEM`
- **Fresh-session retry** — replaced the weak in-session reminder with a `_MAX_ATTEMPTS = 2` loop that creates a fully fresh CMA session on retry (mirrors `_run_cma_session` in the free path); `json.JSONDecodeError` also triggers a retry
- **`compare_answers` fallback** — wrapped JSON parse in try/except; a malformed Claude reply no longer marks the job as error after the HarmonyRecord is already on-chain
- **Reveal retry** — `_reveal_with_retry` helper retries each validator `/reveal` call up to 3 times with 5 s back-off
- **Tolerant error collection** — parallel validator futures are now all awaited before raising; a single failure produces a descriptive error naming which validators failed rather than aborting silently

**Fixes shipped (ai_validator_cma.py):**
- **Commit DHT retry** — ported the 6-attempt "No ValidationRequest found" retry from the custom path to the free path's `_run_cma_session`
- **Reveal retry** — same `_reveal_with_retry` helper applied to `_finish_protocol`
- **Tolerant error collection** — same tolerant `as_completed` loop applied to `form_verdicts_cma`

**Fixes shipped (app.py):**
- **Watchdog expanded** — background watchdog now releases `_custom_running` for any non-terminal phase (starting, committing, awaiting_reveal), not only `awaiting_reveal`; prevents permanent lock if the commit thread crashes mid-run
- **Rate limit on success only** — `_ip_last_free[ip]` and `_free_run_count` now recorded only after a successful free run, not on failure; failed runs no longer burn the user's daily quota or the monthly budget
- **Client-side poll timeout** — 8-minute `MAX_POLL_MS` hard stop added to both `doPoll` and `pollCustom`; `customPollStart` is reset in `triggerReveal()` so the reveal phase gets its own 8-minute window

Verified by Opus 4.8 code review; one regression (false timeout on reveal) caught and fixed before deploy.

---

### Three minor correctness fixes — 2026-05-28 ✓

Identified by an independent code review (Claude Opus 4.8).

- **Researcher msgpack call site** (`researcher_repository_coordinator/src/lib.rs`): `lock_researcher_result` now hashes metrics via the shared `metric_results_msgpack_bytes()` helper, matching the reveal-side verification path exactly. Previously used an inline `rmps::to_vec_named` call — identical bytes today, but a latent drift risk if the encoding ever changed. Unused `rmp_serde` import removed.
- **Python agreement level bug** (`demo/ai_validator.py`): `ExactMatch` threshold now uses `full_rate` (Reproduced-only count / total), matching `shared_types::derive_agreement_level`. Previously used the combined reproduced+partial rate for all tiers, which would display `ExactMatch` for an all-`PartiallyReproduced` round where the chain record correctly holds `WithinTolerance`. Display-only (the on-chain `HarmonyRecord` is authoritative), but now accurate.
- **Model ID** (`demo/ai_validator.py`): non-CMA validator path updated from `claude-opus-4-6` to `claude-opus-4-7`.

Also posted the wandb GitHub issue ([Feature]: Independent run attestation) — no responses yet as of 2026-05-28.

---

### Release v0.5.6 — Demo website redesign + discipline classification — 2026-05-26 ✓

**Discipline classification:** `classify_discipline(claim, api_key)` added to `demo/custom_runner.py`. A short Haiku call at the start of `start_commit_phase` classifies the hypothesis into an academic discipline (e.g. "Social Psychology", "Exercise Science") and returns `{"type": "Other", "content": "<name>"}` for the DHT. Replaces the hardcoded `{"type": "ComputationalBiology"}` that appeared on every HarmonyRecord regardless of subject matter.

**Demo website redesign (`demo/app.py`):**
- **No tabs** — linear scroll layout replaces the Free/Your Hypothesis tab bar
- **Your Hypothesis is the primary hero section** — full-width card with gradient border at the top of the page
- **Five expandable accordions** (`<details>`/`<summary>`) between the two demos explain the protocol, why it's remarkable, why Holochain and not a blockchain, why a central server lacks the trust layer, and why validator disagreement is a feature not a failure
- **Free demo** demoted to a secondary section below a visual `— Free demo — no API key needed —` divider
- **Holochain logo** (`demo/static/holochain-logo.png`) added to the header as a "Built on / [logo]" badge linking to holochain.org
- **Google Fonts** — DM Sans + Newsreader loaded from fonts.googleapis.com
- **Copy** — hero tagline, accordion text, and the blockchain explainer all give Holochain explicit credit and explain the agent-centric DHT architecture

**`demo/DEMO_WEBSITE.md`** fully rewritten: covers both demos, CMA 5-step system prompt, two-phase protocol, `classify_discipline`, `compare_answers`, request flow, result schema, rate limiting, UI design, updated files table, and Holochain credit.

---

### Release v0.5.5 — CMA validator upgrade — 2026-05-26 ✓

AI validators upgraded from one-shot Claude calls to **Claude Managed Agents** (CMA). Each validator now runs as a proper agent that searches the web, reasons step-by-step, and writes its verdict to a file — all before committing to the DHT.

**New file: `demo/ai_validator_cma.py`** — replaces `ai_validator.py` as the orchestrator for CMA and simple (non-Anthropic) modes. Key features:
- 3 validator agents run **in parallel**, each in their own CMA environment + session
- Each agent uses `web_search`, `web_fetch`, `write` tools to do real research before verdicting
- Verdict written to `/mnt/session/verdict.json`; Python reads from event log after `session.status_idle`
- **User API key support**: user can provide any provider key — `sk-ant-` → CMA mode; `sk-proj-`/`sk-` → OpenAI via litellm; `AIzaSy` → Google; `gsk_` → Groq
- **Rate limiting** on server key: 1 run/hour per IP, $20/month cap
- **`AttestationOutcome` serde fix** in `validator-node.mjs`: struct variants (`PartiallyReproduced`, `FailedToReproduce`, `UnableToAssess`) now correctly serialised with `content: { details }` field — previously caused 502 crashes

**`demo/app.py`** updated: accepts `user_api_key` + `user_model` in POST body; routes to CMA/simple/original mode based on key type.

**Run against Oracle:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004
python3 demo/ai_validator_cma.py --mode decentralised
```

Verified end-to-end: 3 validators (36s/6 calls, 88s/17 calls, 123s/32 calls), all Reproduced (High), HarmonyRecord written to Oracle DHT.

---

### Release v0.5.4 — security hardening sweep — 2026-05-24 ✓

**Warrant gate coverage (attestation_coordinator):** Four coordinator entry points that previously let warranted (banned) agents write state are now closed — `submit_validation_request`, `publish_validator_profile`, `assess_difficulty`, `link_agent_identity`. All call `reject_if_warranted(&agent)?` at the start of the handler, matching the existing pattern on `notify_commitment_sealed`, `submit_attestation`, and `claim_study`.

**Integrity validation gaps (attestation_integrity + governance_integrity):** Two entry types had no `validate()` coverage:
- `ResearcherResultCommitment` — `result_commitment_hash` must be exactly 32 bytes (SHA-256). A malformed hash would permanently block the researcher's reveal with no visible error.
- `HarmonyRecord` — `validator_types` (position-parallel to `participating_validators`) must be empty or the same length. A length mismatch causes out-of-bounds panics in UI lookups. The field is `#[serde(default)]` for backwards-compat with pre-existing records.

**TypeScript serde fix (valichord-ui/src/lib/types.ts):** `BadgeType` used wrong string names (`"Gold"`, `"Silver"`, `"Bronze"`, `"Failed"`). Rust serialises to `"GoldReproducible"`, `"SilverReproducible"`, `"BronzeReproducible"`, `"FailedReproduction"`. `get_badges_by_type` calls from the UI now match DHT records.

**Earlier fixes (also in this release):** claim release authorisation (only original claimant or study submitter may release); warrant filter in `get_all_validators`; cross-DNA error handling in `call_attestation_zome_opt`; timeout cast safety in `reclaim_abandoned_claim`; atomic badge issuance hardening in governance.

**New sweettest tests:**

| File | # | Test | What it covers |
|---|---|---|---|
| `attestation.rs` | 16 | `update_validator_profile_merges_fields` | `Some` fields overwrite, `None` fields preserved |
| `attestation.rs` | 17 | `check_all_commitments_sealed_lifecycle` | false before quorum, true after both validators commit |
| `attestation.rs` | 18 | `get_researcher_reveal_none_then_some` | `None` before reveal, `Some(Record)` after |
| `attestation.rs` | 19 | `revoke_agent_identity_link_removes_from_linked_agents` | deleted entry filtered from `get_linked_agents` |
| `attestation.rs` | 20 | `get_my_claimed_studies_filtered_by_release` | released claim excluded from `Vec<Record>` result |
| `governance.rs` | 17 | `get_pending_request_refs_includes_other_discipline_studies` | `Discipline::Other("custom")` study appears in refs; `force_finalize_round` works end-to-end |

Total sweettest coverage: **20 attestation + 17 governance** tests.

---

### Public web demo live on Render — 2026-05-22 ✓

**[valichord-demo.onrender.com/demo](https://valichord-demo.onrender.com/demo)** — one-click browser interface to the full commit-reveal protocol. Runs against the permanently live Oracle nodes (no local setup).

**What it does:** Click Run Protocol → 7-step progress bar shows the full protocol in ~2 minutes (real network time). At the end: outcome, per-validator verdicts, a permanent shareable HarmonyRecord URL, and a `curl` command to fetch the raw record directly from the Oracle DHT — proving the result was not generated by the page itself.

**Architecture:** Flask app (`demo/app.py`) deployed on Render from `demo/Dockerfile`. Background job per run (`threading.Thread`); job state in process-level dict; `threading.Lock()` + `_demo_running` bool enforces one run at a time. `gunicorn --workers 1 --threads 4` so all threads share the same process. Three Claude Haiku agents form independent verdicts. Each run salted with a UUID so the data hash is unique and HarmonyRecord hashes can't be pre-computed.

**Docs:** `demo/DEMO_WEBSITE.md` — full technical guide (request flow, protocol steps table, concurrency design, local run instructions, Render deployment, skeptic-proof verification section).

**ValiChordLogger fixes shipped alongside:** `log_eval_result()` made an explicit no-op (was silently calling `build_bundle(samples=[])` → always raised `MalformedBundleError`); `finish()` added to `run.py`; 28 tests updated. Pushed to `topeuph-ai/lm-evaluation-harness` fork.

---

### `PiSessionAdapter` + `ValiChordLogger` for lm-evaluation-harness — 2026-05-20 ✓

**PiSessionAdapter** (`valichord_attestation/adapters/pi_session_adapter.py`) — reads pi coding agent session v3 JSONL files and converts them to canonical Valichord bundles. Resolves the active branch via parentId walk (mirrors `_buildIndex()`), applies compaction filtering (`firstKeptEntryId`), extracts 8 metrics (turns, tool calls, error rate, tokens, cost, compaction count, stop reason), and builds a full Merkle tree over all branch entries. 67 tests, 99% coverage.

**ValiChordLogger** (`topeuph-ai/lm-evaluation-harness`, fork) — optional logger for lm-evaluation-harness following the `wandb`/`trackio` pattern. Hooks into `post_init` → `log_eval_result` → `log_eval_samples`, builds a `valichord_attestation` bundle (Merkle tree over per-sample `filtered_resps`, stable SHA-256 commitment via RFC 8785), and saves it alongside the `results_*.json` artifact. Wired via `--valichord_args output_path=./results` CLI flag and `pip install lm_eval[valichord]` optional extra. 28 tests, all mocked (no GPU/network required in CI).

**Engagement:** comment posted on [EleutherAI/lm-evaluation-harness#3752](https://github.com/EleutherAI/lm-evaluation-harness/pull/3752) asking if a companion PR is welcome. FazeelUsmani (PR author) previously engaged positively on that thread when v1.2 shipped.

---

### falsify-cookbook Pattern 13 merged — 2026-05-20 ✓

ValiChord is now officially referenced in the [falsify-cookbook](https://github.com/studio-11-co/falsify-cookbook) as Pattern 13 — co-authored with Cüneyt Öztürk (Studio 11).

**PR:** [studio-11-co/falsify-cookbook#3](https://github.com/studio-11-co/falsify-cookbook/pull/3) — merged, reviewed and approved by sk8ordie84 (Cüneyt).

**What the pattern covers:**

Three-layer stack for AI evaluation independence attestation:

| Layer | Tool | What it commits |
|---|---|---|
| Pre-registration | PRML / falsify | metric, comparator, threshold, dataset hash, seed |
| Eval attestation | valichord_attestation | Merkle root over per-sample outputs |
| Independence attestation | ValiChord | blind multi-party verdicts; HarmonyRecord on public DHT |

Pattern 13 fills the gap Pattern 11 (Sigstore) leaves open: Sigstore proves *who* ran the eval and *when*; ValiChord proves validators couldn't coordinate post-hoc. The pattern explicitly cross-references Pattern 10's auditor-layer gap (v0.3 roadmap: centralised consortium registry) as the structural problem ValiChord's DHT solves.

**Honest about limits (documented in the pattern):**
- Validator withdrawal: commitment is visible on DHT but protocol can't compel reveal
- Validators don't yet commit to their own reproduction bundle hash (planned extension)
- Integration is manual today — no single command wires all three layers

**Strategic significance:** ValiChord is now a named, documented component of the falsify/PRML ecosystem. The `attestation_uri` field (P-02) pointing to a HarmonyRecord URL is the concrete integration hook. Future: automate the handoff between `valichord_attestation` and the Holochain protocol.

---

### Holochain 0.6.1 upgrade — 2026-05-13 ✓

Full upgrade of the Holochain toolchain from 0.6.0 to 0.6.1. Transport switches from tx5/WebRTC to iroh/QUIC.

**Binary stack upgraded:**
- `holochain 0.6.1` — `cargo install holochain --version 0.6.1 --locked --force`
- `hc 0.6.1` (holochain_cli) — `cargo install holochain_cli --version 0.6.1 --locked --force`
- `kitsune2-bootstrap-srv 0.4.1` — required for iroh/QUIC peer discovery (0.3.x is protocol-incompatible)
- `@holochain/tryorama 0.19.1` — iroh/QUIC transport; `dhtSync` signature: `(players, dnaHash, intervalMs?, timeoutMs?)`

**Cargo.toml workspace pins bumped:**
- `hdk = "=0.6.1"` (was `"=0.6.0"`)
- `hdi = "=0.7.1"` (was `"=0.7.0"`)
- `holochain_serialized_bytes = "=0.0.57"` (was `"=0.0.56"`)
- `attestation_integrity/Cargo.toml` migrated from local pin to `{ workspace = true }`

**Zome code changes:**
- `reject_if_warranted` (attestation_coordinator): `get_agent_activity` now requires a 4th `GetOptions` parameter — added `GetOptions::network()`
- Governance coordinator warrant filter: same `GetOptions::network()` 4th arg added
- `recv_remote_signal` (attestation_coordinator): 0.6.1 conductor delivers remote signal payload directly as a msgpack map (no outer bin8 wrapper); removed the double-decode workaround; now decodes directly as `RevealOpenWire` in one step
- `Warrant` → `SignedWarrant` type rename in `AgentActivityResponse`: handled automatically by HDK version bump (code only uses `.warrants.is_empty()`)

**Kangaroo-electron prerequisite:** Holochain 0.6.1 upgrade is now ✓ done. Remaining pre-requisites: browser UI ✓, dedicated bootstrap/signal/relay servers.

---

### Release v0.5.21 — 2026-05-17 ✓

Committed and tagged. GitHub release at `v0.5.21`. Covers `InspectAILogAdapter`, `eval_yaml_metadata` enrichment, `generate-attestation-bundle` skill, and package export plumbing. 259 valichord_attestation tests. README updated (version blurb, stale "New:" labels removed, adapters section updated).

---

### `valichord_attestation` InspectAILogAdapter + eval_yaml_metadata — 2026-05-15 ✓

Three additions driven by analysis of the Generality-Labs/inspect-evals-template:

**`InspectAILogAdapter`** — new adapter that reads inspect_ai `.eval` / `.json` log files
directly using the inspect_ai Python API, requiring no pre-parsing step.

Field mapping: `EvalSpec.model` → `model_id`, `EvalSpec.task` → `task_id`,
`EvalSpec.created` → `generated_at`, `EvalSpec.revision.commit` → `repo_commit`
(auto-extracted), `EvalResults.scores` → `metrics` (all scorers combined; scorer-name
prefix on key collision), `EvalLog.samples` → `outputs_merkle_root` (per-sample dicts
`{id, epoch, output, scores}`).

Per-sample dict captures `ModelOutput.completion` + all `Score.value/answer` entries.
`score_name=` restricts to a single scorer. `meta_extras=` merges extra provenance.
`inspect_ai` is an optional dependency; passing a pre-loaded duck-type works without it.

**`InspectEvalsAdapter.to_bundle(..., eval_yaml_metadata=)`** — optional enrichment from
the top-level `eval.yaml` metadata block (not the `evaluation_report` block).
Folds into `Bundle.meta`: `arxiv` → `paper_arxiv`, `group` → `eval_group`,
`version` → `task_version`, `tasks[*].human_baseline` → `human_baseline`,
`state: floating` external assets → `dataset_reproducibility_warning`,
`metadata.requires_internet` → `requires_internet`.

**`generate-attestation-bundle` Claude Code skill** — at `.claude/skills/generate-attestation-bundle/SKILL.md`.
Step-by-step workflow for adding attestation as the final step after an inspect_evals
eval report. Covers both `InspectAILogAdapter` (file path) and `InspectEvalsAdapter`
(eval.yaml evaluation_report) paths, plus challenge-response verification.

Tests: 183 → 259 (+76). 100% line coverage maintained. `inspect-ai` added as an
optional dependency group in `pyproject.toml`.

---

### `valichord_attestation` format v1.2 — 2026-05-09 ✓

Two additive, backward-compatible changes to the attestation bundle format, informed by FazeelUsmani's lm-evaluation-harness PR #3752.

**`Metric.filter` (optional str):** disambiguates metrics sharing the same key produced by different filter passes (e.g. strict-match vs flexible-extract). `None`/absent → omitted from canonical encoding entirely; existing bundles unaffected.

**`Bundle.meta` + `content_hash`:** `meta: Optional[dict]` is a free-form provenance block (harness version, commit, command, timestamp, n_shot, etc.). It is included in `bundle_hash` (byte identity) but excluded from `content_hash` (scientific equivalence). v1.1 bundles with no `meta` have `content_hash == bundle_hash`. `content_hash()` added to `canonical.py` and exported from `__init__.py`.

`build_bundle()` default `format_version` bumped to `"v1.2"`. All v1/v1.1 bundles remain valid — no existing hash values change.

Tests: 142 → 183 (+41 new). 100% line coverage maintained. Spec updated with §2a (meta block), dual-hash §4, filter in Metric schema, and changelog entry referencing the upstream PR.

---

### Governance badge idempotency fix — 2026-05-09 ✓

The auto-call chain `submit_attestation` (DNA 3) → `check_and_create_harmony_record` (DNA 4) → `get_validation_request_for_data_hash` (DNA 3) silently fails: Holochain blocks the re-entrant call back into DNA 3 while `submit_attestation` is still executing. `call_attestation_zome_opt` returns `Ok(None)`, `maybe_researcher` is `None`, and badge issuance is skipped without error.

When a subsequent explicit `check_and_create_harmony_record` call hit the idempotency guard, it returned the existing `HarmonyRecord` hash without retrying badge issuance — leaving the badge permanently absent. The silver badge sweettest exposed this: on a loaded CI runner governance gossip propagated the `RequestToHarmonyRecord` link before the explicit call, so the idempotency path fired every time.

**Fix:** `issue_badge_if_missing()` is now called from the idempotency return path. It network-queries for existing badge links, reads the `HarmonyRecord` for `agreement_level` and `validator_count`, then calls `try_issue_badge()` — the same logic extracted from `write_harmony_record`. The retry runs from a direct governance call where DNA 3 is free, so `get_validation_request_for_data_hash` succeeds.

Silver badge sweettest (`silver_badge_issued_with_five_validators`) updated to sync governance cells before the explicit call, deterministically exercising the idempotency+retry path.

---

### `valichord_attestation` inspect_ai popularity demo — 2026-05-07 ✓

Second real-data example under `valichord_attestation/examples/inspect_ai_popularity_demo/`. Parses an inspect_ai `.eval` log (popularity task, GPT-4o-mini, match scorer) via EveryEvalEver's `InspectAIAdapter`, then builds and challenge-response-verifies a v1.1 bundle.

- **`download_eval.sh`** — fetches the 21 KB real log from inspect_ai's test suite
- **`build_bundle.py`** — EEE-based parsing path + `--fixture` mode (committed `bundle.json`)
- **`challenge_response_demo.py`** — k=20 challenge-response with tamper detection

Strategic context: demonstrates ValiChord format compatibility with the EvalEval Coalition aggregate schema (inspect_evals#910).

---

### Wind-Tunnel performance scenarios — 2026-05-06 ✓

Three load-testing scenarios under `valichord/wind-tunnel/` (commit `fcf8ced`).
Separate Cargo workspace — intentionally outside `valichord/Cargo.toml` (same isolation pattern as `sweettest_integration`; native `holochain` deps can't compile to `wasm32`).
All three compile clean (`cargo check --workspace`).

| Scenario | What it measures | Default invocation |
|---|---|---|
| `validation_request_throughput` | Concurrent CommitmentAnchor write throughput — N agents loop `submit_validation_request` + `notify_commitment_sealed`; reports `commits_sent` counter | `--agents 4 --duration 60` |
| `phase_observation_latency` | Time from `notify_commitment_sealed` returning to first `RevealOpen` observation via polling — uses `num_validators_required=1`; reports `phase_observation_ms`, `poll_count`, `phase_timeout_count` | `--agents 2 --duration 60` |
| `concurrent_reveal_throughput` | Full commit-reveal cycle under N-agent concurrent load; tests `ChainTopOrdering::Relaxed` under 3 sequential source-chain writes; reports `round_total_ms`, `reveal_count`, `reveal_timeout_count` | `--agents 4 --duration 90` |

Pre-requisite: pack `valichord.happ` first. Override path with `VALICHORD_HAPP_PATH` env var.

```bash
cd valichord/wind-tunnel
cargo run -p validation_request_throughput -- --agents 4 --duration 60
cargo run -p phase_observation_latency    -- --agents 2 --duration 60
cargo run -p concurrent_reveal_throughput -- --agents 4 --duration 90
```

---

### `valichord_attestation` real-data example — 2026-05-06 ✓

Real-data demo of the v1.1 protocol under `valichord_attestation/examples/mistral_7b_gsm8k_demo/`:

- **`run_eval.sh`** — lm-evaluation-harness v0.5.0, Mistral-7B-Instruct-v0.3, GSM8K 100-sample subset, fully pinned; ~10 min on a 4090, ~£1.50
- **`build_bundle.py`** — parses lm-eval output (glob-based, robust to directory structure) OR `--fixture` for no-GPU demo. `samples_total=100` passed explicitly (exercises threat-model §10(d) sample-omission defence). Merkle round-trip validated on every run.
- **`challenge_response_demo.py`** — loads `bundle.json`, k=20 challenge with documented fixed nonce, verifies all 20 Merkle paths, demonstrates tamper detection
- **`bundle.json`** — committed bundle (simulated fixture, `random.Random(42)`, 35% accuracy); replace with real eval output by running the two scripts on a GPU
- **`examples/README.md`** — new index pointing at both synthetic and real-data examples

No library code changed. All 142 tests pass.

---

### `valichord_attestation` explicit `samples_total` — 2026-05-05 ✓

Closes sample-omission gap (threat model §10 attack surface (d)). `build_bundle` now accepts `samples_total: Optional[int]`; when provided and larger than `len(samples)`, `bundle.samples_total > bundle.samples_completed` is directly visible in the bundle without out-of-band context. Raises `ValueError` if `samples_total < len(samples)`. 4 new tests (boundary: omitted, equal, larger, smaller); 142 tests total, 100% line coverage. Spec §2 field descriptions tightened; §10 (d) updated to note that explicit declaration shifts detection in-bundle, and that federation remains the backstop against a lying adapter.

---

### `valichord_attestation` probabilistic challenge-response — 2026-05-05 ✓

Additive extension on top of v1 Merkle structure. Verifier-controlled randomness: challenged indices derived deterministically from `HMAC-SHA256(nonce, bundle_hash)` + SHA-256 counter-mode PRNG, so the holder cannot predict which samples will be challenged.

**New modules:**
- `challenge.py` — `Challenge` dataclass, `derive_seed`, `generate_indices`, `compute_challenge_hash`
- `response.py` — `ResponseSample`, `ChallengeResponse`, `build_response`, `verify_response`

**Protocol properties:**
- Seed: `HMAC-SHA256(key=verifier_nonce, msg=bundle_hash_ascii)`
- Indices: SHA-256 counter-mode (`SHA256(seed || counter_u64_be)` mod `total_samples`, rejection-sampled for distinctness)
- Response contains only hashes + proof paths — no raw sample content
- `challenge_hash` = `SHA-256(JCS({"bundle_hash", "k", "verifier_nonce_hex"}))` binds response to challenge
- `merkle_path` reuses existing `list[{"position","sibling"}]` format from `merkle_proof`
- `_leaf_hash` promoted to public `leaf_hash` (protocol-defining)

**Test coverage:** 57 new tests (38 challenge + 35 response, 4 pre-existing overlap removed). 138 tests at this point; 142 total after subsequent `samples_total` additions. 100% line coverage maintained.

**Fixed test vector:** `bundle_hash='a'*64`, `nonce=bytes(range(16))`, `k=5`, `total=100` → indices `[9, 69, 33, 74, 38]`

**No breaking changes** — v1 bundle format unchanged. No new dependencies.

---

### `valichord_attestation` v0.1.0 — 2026-05-05 ✓

Python library for canonical, cryptographically verifiable attestation bundles for AI evaluation runs. Applies ValiChord's commit-hash-reveal principle to AI benchmarks: a published accuracy score becomes traceable to the run that produced it.

**Key properties:**
- **Deterministic hash** — RFC 8785 (JCS) encoding; `SHA-256(JCS(bundle))` is stable across implementations
- **Merkle root** — SHA-256 tree over per-sample outputs; selective disclosure without the full log
- **Harness-agnostic** — `AdapterBase` ABC; Inspect AI stub included

**What's in the package:**
- `builder.py` — `build_bundle(...)`, `MalformedBundleError` on NaN/missing fields
- `canonical.py` — JCS encoding + `hash_bundle()`
- `merkle.py` — `merkle_root`, `merkle_proof`, `verify_faithfulness`
- `spec/attestation_format_v1.md` — canonical spec
- 81 tests, 100% line coverage

**Not in v1:** cryptographic signing (v2), ZK proofs, Holochain DHT integration (post-format-stabilisation).

**Motivation:** Scott Simmons's review of `UKGovernmentBEIS/inspect_evals#1610` — canonical attestation spec belongs in ValiChord, not in each harness.

---

### UI bug fixes + backend signal hardening — 2026-05-04 ✓

**UI fixes (both are live-demo killers):**
- **Signal handler leak** (`App.svelte`) — `onSignal` return value was never captured. Each component remount stacked another handler; validators received duplicate `RevealOpen` notifications. Fixed with `onDestroy` + captured unsubscribe.
- **`checkPendingReveals` race** (`ValidatorView.svelte`) — the reactive `$:` fired `checkPendingReveals()` unawaited; multiple concurrent invocations could race to set `revealTaskHash`/`revealPrivateAttestation`/`screen`. Fixed with a `checkingReveals` boolean guard.
- **Signal format mismatch** (`types.ts`, `App.svelte`) — `Signal` enum uses adjacent-tag serde (`#[serde(tag = "type", content = "content")]`), delivering `{ type: "RevealOpen", content: { ... } }` over the WebSocket. `types.ts` and the previous `"RevealOpen" in payload` check assumed external-tag format and never fired. Fixed throughout.

**Backend fixes (attestation + governance coordinators):**
- **`FinalizationFailed` signal** — `call_governance_fire_and_forget` now returns `bool`. When the cross-DNA call to `check_and_create_harmony_record` fails after a successful `submit_attestation`, the attestation coordinator emits `Signal::FinalizationFailed { request_ref }` locally. The UI displays an actionable error pointing to `force_finalize_round`.
- **Warrant-check asymmetry comment** — `unwrap_or(true)` in the HarmonyRecord warrant filter is intentionally asymmetric with `reject_if_warranted()` (claim time). At finalisation time there is no automatic retry trigger, so excluding a legitimate validator on a transient network error would permanently strand a completed round. Comment updated to explain this explicitly.
- **TOCTOU comment** — updated to note that `write_harmony_record` already sorts `participating_validators` by key bytes, making the same-set race benign via content-addressing. Only the N vs N+1 case remains as documented Phase 1 work.

**Docs updated:** `FRONTEND.md` (signal format, handler cleanup pattern), `docs/7_ValiChord_4-DNA_architecture_technical.md` (signals table, commit-reveal flow).

---

### valichord-ui wired to live conductor — 2026-04-27 ✓
Full browser UI connected to a real Holochain conductor for the first time.

**What was built:**
- `dev.sh` — start script: launches conductor via `dev-conductor.yaml` (in-process lair, admin `:4444`), then runs `dev-setup.mjs`
- `dev-setup.mjs` — Node.js bootstrap: installs hApp with membrane-proof bypass (`0x42×64` + `authorized_joining_certificate_issuer: ''`), enables app, attaches app interface on `:8888`, issues no-expiry auth token, calls `admin.authorizeSigningCredentials()` for all 4 cells, writes `VITE_HC_TOKEN` + `VITE_HC_SIGNING_CREDENTIALS` to `.env.local`
- `holochain.ts` — reads `VITE_HC_TOKEN` (base64 → `number[]`) and `VITE_HC_SIGNING_CREDENTIALS` (base64 JSON) from Vite env; calls `setSigningCredentials` before `AppWebsocket.connect` (required by `@holochain/client` 0.20.x)
- `types.ts` → `entryFromRecord` — now msgpack-decodes the raw entry bytes returned by `@holochain/client` 0.20.x (entry is not auto-decoded; must call `decode()` from `@msgpack/msgpack`)
- Fixed two TypeScript narrowing errors in `GovernanceView.svelte` (Discipline union cast)

**Verified:** `submit_validation_request` writes to attestation DHT; `get_validation_request_for_data_hash` reads back with all fields correctly decoded. Idempotency guard (duplicate data_hash rejection) working.

**Not yet tested in a real browser:** the Node.js verification script uses the same code path as the UI. A human clicking through the form is the remaining manual step.

---

### Reputation/certification system — 2026-04-24 ✓
**4-tier `CertificationTier`**: `Provisional` → `Standard` (≥5 rounds) → `Advanced` (≥20 + rate ≥60%) → `Certified` (≥50 + rate ≥80%).
**Badge thresholds**: use raw validator count (7/5/3/3) — tier-weighted thresholds were attempted but reverted (too complex for now; revisit post-Phase 1 when real validator tiers exist).
**Production implication**: all validators stay `Provisional` until Phase 1 oracle is wired — Gold and Silver cannot be issued in production yet. Bronze remains fully functional.
**DNA hash changed**: `CertificationTier` is in `ValidatorReputation` (governance integrity) and `ValidatorProfile` (attestation integrity). Dev-only — no live network impact.
**Tests**: sweettest tests 12 + 13 in `governance.rs` verify Provisional→Standard promotion boundary.

---

## What is NOT done yet

### ~~1. `ANTHROPIC_API_KEY` persistent on Oracle~~ — DONE (2026-05-21)
Added to `~/.bashrc` on Oracle. Survives reboots.

### ~~2. Port 3001 in Oracle Security List~~ — DONE
Port 3001 is open and responding (`{"status":"ok","role":"researcher"}` confirmed from outside Oracle). Shareable HarmonyRecord URLs work.

### 3. ~~Feynman PR #23~~ — CLOSED
Feynman is no longer operational (April 2026). AI validator functionality has been rebuilt
directly against the Claude API (`demo/ai_validator.py`). No further Feynman integration work.

### 4. Rate limiting — LOW
API keys are in. No per-key rate limiting yet.

### 5. CORE-Bench + ValiChord demo — ✓ FULL RUN DONE (2026-05-31); ✓ REVIEW-HARDENING LANDED (2026-06-01)
Live CLI demo combining ValiChord's commit-reveal protocol with the inspect_evals CORE-Bench task — AI agents that actually run research-paper code in isolated Docker sandboxes. On `main` (demo + 3-unit review-hardening); see `demo/CORE_BENCH_DEMO.md`. Hardening detail in "Recently completed" above.

**Full commit-reveal run complete (2026-05-31, 128 GB Codespace):** end-to-end all-Sonnet run (researcher + 3 validators all `claude-sonnet-4-6`, `--researcher-runs 1`) produced a clean **`Reproduced` / `ExactMatch`** HarmonyRecord — all 3 validators independently got `0.9157952669235003`. Public + recomputable on the Oracle DHT: `curl "http://132.145.34.27:3001/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"`. Both Opus 4.8 and Sonnet 4.6 reproduce the capsule exactly. **31 tests pass.**

**Four bugs fixed live (each only surfaces with 3 real validators):** (1) validators ran in a `ThreadPoolExecutor` but inspect_ai forbids concurrent `eval_async` → made sequential; (2) `google-genai` missing from `requirements.txt` → added; (3) `gemini-1.5-pro` retired by Google → `gemini-2.5-pro`; (4) infra failure (rate-limit/quota/auth/interrupt → empty `EvalLog` → `None` report) was minting a bogus `FailedToReproduce` HarmonyRecord → `run_validator_eval` now raises on non-`success` status so the round aborts with the real error. (Earlier: `filter_out_gpu` empties the dataset; `anthropic>=0.105.0`.)

**Gotcha:** the commit-reveal half defaults to the **Oracle** nodes (`demo_runner` `RESEARCHER_URL`/`VALIDATOR_URLS`) unless `VALICHORD_*_URL` is exported to localhost — so the inspect sandboxes run locally but the DHT half hits the live Oracle. **Keys:** mixed-model needs paid keys (OpenAI free = `insufficient_quota`, Gemini free = `limit:0` for 2.5-pro); all-Sonnet is the cheap working default.

**Trigger CORRECTED:** the earlier "hold until the inspect_evals issue responds" gating is **reversed** (per `docs/CORE_BENCH_INTEGRATION.md` 2026-05-30, "lead with the demo"). There is no inspect_evals issue — outreach to Scott Simmons was a **direct LinkedIn message** (no response required). The demo is the gift you lead with, not a follow-up.

---

## New Codespace setup (2026-05-26)

Run this from the terminal — installs everything in one go (~25 min):
```bash
cd /workspaces/ValiChord && bash setup_holochain.sh
```
Installs: Claude Code, Rust, Holochain 0.6.1, hc CLI, kitsune2-bootstrap-srv, holochain-dev skill, compiles all 4 DNA zomes and packs the hApp.

Then inside Claude Code chat: `/plugin install superpowers`

Skill files are committed to `skills/holochain-dev/` in the repo — the setup script copies them to `~/.claude/skills/holochain-dev/`.

---

## Installed tools and skills (2026-04-24)

### holochain/ai-tools — `holochain-dev` Claude Code skill
Installed at `~/.claude/skills/holochain-dev/` (12 files). Activates automatically on any Holochain task.
- DNA-hash tripwire: refuses/warns on integrity changes that break the DNA hash
- Verifies every HDK/HDI API call against docs.rs at the project-pinned version (never training data)
- Serialization-boundary inversion: check stale WASM before msgpack version pins
- Sweettest-only test generation; lazy-load reference files in `references/`

Source: https://github.com/holochain/ai-tools (branch: main)

### holochain/kangaroo-electron — future desktop packaging path
Template for packaging ValiChord as a cross-platform Electron app. **Not started yet.**
Pre-requisites before we can use it: (1) ~~browser UI for ValiChord~~ **done** (`valichord-ui/` wired end-to-end), (2) Holochain 0.6.1 upgrade, (3) dedicated bootstrap/signal/relay servers (`holochain/network-services` Pulumi repo).
Branch to use: `main-0.6` (Holochain 0.6.x). Enables: validators install desktop app and run their own conductor.

Source: https://github.com/holochain/kangaroo-electron (branch: main-0.6)

### Other tools noted but not installed
- **hc-spin** (https://github.com/holochain/hc-spin) — run `.happ` files locally with multiple agents, single CLI. Potential replacement for Docker demo once 0.6.1 lands.
- **chisel** (https://github.com/holochain/chisel) — demux interleaved multi-conductor logs: `cat logs.txt | chisel tryorama demux`
- **network-services** (https://github.com/holochain/network-services) — Pulumi IaC for self-hosted Holochain bootstrap + relay servers on DigitalOcean. Needed before production kangaroo packaging.
- **hc-cooperative-content** (https://github.com/holochain/hc-cooperative-content) — multi-agent governance zomes, applicable to DNA 4.

### Unyt ecosystem tools — evaluated 2026-04-24
Three tools from https://github.com/orgs/unytco/repositories worth knowing for ValiChord's operational roadmap:
- **joining-service** — REST API for issuing membrane proofs + hApp bundles on join (`GET /.well-known/holo-joining` → `POST /v1/join`). Reference impl of ValiChord's `authorized_joining_certificate_issuer` pattern, done properly as a service. **Use when designing institutional validator onboarding for a live network.**
- **heart** — DigitalOcean + Pulumi conductor provisioning with Telegraf/InfluxDB monitoring. Goes further than network-services (bootstrap/relay only) — provisions the conductor itself. **Use when setting up production conductor nodes.**
- **tauri-plugin-holochain** — Lighter/faster Electron alternative for the desktop validator installer (Rust-based, not Chromium). Not fully open source yet (Open Collective fundraise in progress). **Revisit before building the installer; for now, kangaroo-electron remains safer.** See `memory/reference_unyt_tools.md` for full detail on each + not-relevant tools.

---

## Key technical facts for the next session

### iroh/QUIC bootstrap (Holochain 0.6.1+)
Holochain 0.6.1 replaced tx5/WebRTC with iroh/QUIC transport. The bootstrap server binary
must be `kitsune2-bootstrap-srv 0.4.1` (version 0.3.x is protocol-incompatible with 0.6.1
conductors). Tryorama 0.19.1 spawns `kitsune2-bootstrap-srv` automatically for tests.
`_retryOnTx5()` / `retryOnTx5` renamed to `_retryOnNetworkError` / `retryOnNetworkError`
in `serve.mjs`, `node-lib.mjs`, `validator-node.mjs` — tx5-specific error strings removed,
now catches generic timeout/channel-drop errors. `advanced.tx5Transport` removed from all
three conductor YAMLs (dead config under iroh). Oracle demo bootstrap binary in `demo/bin/`
should be updated to 0.4.1 before the next Oracle demo run.

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
| `docs/Holochain_complete.md` | Complete Holochain build guide — iroh/QUIC NetworkConfig, hc-http-gw URL format, ExternalHash JS |
| `demo/DECENTRALISED_DEMO.md` | Full technical guide for the decentralised demo — architecture, retry design, commit-reveal table |
| `demo/DEMO_WEBSITE.md` | Technical guide for the public Render web demo — Flask architecture, request flow, concurrency design, Render deployment |
| `demo/ai_validator.py` | Python orchestrator — `--mode decentralised` calls the five node APIs |
| `demo/docker-compose.yml` | 5-container stack definition |
| `demo/researcher-node.mjs` | Node.js HTTP API for researcher conductor |
| `demo/validator-node.mjs` | Node.js HTTP API for each validator conductor |
| `demo/node-lib.mjs` | Shared helpers: `withSession`, `retryOnNetworkError`, `loadHcClient`, `externalHashFromB64` |
| `backend/app.py` | Flask REST API |
| `docs/INTEGRATION_GUIDE.md` | REST API integration guide |
| `valichord-ui/FRONTEND.md` | Screen-by-screen UI walkthrough — all three roles |
| `valichord-ui/src/lib/` | Svelte components: ResearcherView, ValidatorView, GovernanceView, types.ts, holochain.ts |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Four-DNA architecture |
| `valichord/wind-tunnel/` | Wind-Tunnel load-test workspace — 3 performance scenarios (write throughput, phase latency, reveal throughput) |

---

*This file is the single catch-up document for new Claude sessions. Read it before responding to any questions about project status, Feynman integration, or what to demo.*
