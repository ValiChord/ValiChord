# ValiChord × CORE-Bench — CLI Demo

> Maintainer-facing summary (external, respectful): `docs/CORE_BENCH_FOR_INSPECT_EVALS.md`.

A fully-local command-line demo that runs one real [CORE-Bench](https://arxiv.org/abs/2409.11363)
capsule through ValiChord's blind commit-reveal protocol with three AI
validators, producing a tamper-evident **HarmonyRecord** whose replication
verdict is decided by **recomputable arithmetic, not LLM opinion**.

Design spec: `docs/superpowers/specs/2026-05-31-core-bench-demo-design.md`
Implementation plan: `docs/superpowers/plans/2026-05-31-core-bench-demo.md`
Strategy/architecture: `docs/CORE_BENCH_INTEGRATION.md`
Review-hardening (3 units, landed 2026-06-01): `docs/superpowers/specs/2026-05-31-core-bench-review-hardening-design.md` + `docs/superpowers/plans/2026-05-31-core-bench-review-hardening.md` — see "Review-hardening" below.

---

## What it shows

Three independent AI agents each reproduce a published paper's computational
result — in isolated Docker sandboxes, blind to the answer and to each other —
then commit-reveal their findings. The verdict is **what the code produces**
(objective), the runs are **blinded** (no agent can copy another's
`report.json`), and the outcome is recorded on a network no single party
controls and is **independently recomputable** (`curl` the record and redo the
arithmetic yourself).

## The gap it fills

A CORE-Bench `.eval` log is **single-author and self-attested**. Nothing in it
proves a second party would get the same output, stops the producer re-running
until the number looks right, or provides a multi-party, blinded, tamper-evident
record. ValiChord adds exactly that layer — and *only* that layer. Inspect
**runs** the reproduction; ValiChord makes the result **independently
checkable**. Composition, not competition.

---

## How it works

```
Researcher runs the capsule -> committed metrics + interval (SEALED on the DHT)
        |
3 validators (mixed models) each run the SAME capsule, hard mode, isolated sandbox
        | run sequentially (inspect_ai allows one eval at a time), each blind to
        | the sealed answer and to each other; each writes its own report.json
        v
All commit -> reveal phase opens -> simultaneous reveal -> HarmonyRecord
        |
Numeric panel: each validator's value vs the researcher's committed interval
        (pure arithmetic; recomputable from the on-chain record)
```

- **Foundation:** the [`inspect_evals`](https://github.com/UKGovernmentBEIS/inspect_evals)
  `core_bench` task (model-agnostic `react`+`bash` agent), pinned to a verified
  `main` commit. We supply a **custom capture scorer** that lifts each
  validator's `report.json` out of its sandbox **without ever reading the sealed
  ground truth** — blinding is structural, enforced by a test.
- **Blinding:** in *hard* mode the sample setup deletes `results/`,
  `REPRODUCING.md`, and run scripts, so the agent gets only code + data + README
  + the question list. It cannot see the target.
- **The verdict is arithmetic, not opinion.** The committed validator outcome is
  *execution-success only* (`Reproduced` = produced a valid numeric
  `report.json`; `FailedToReproduce`; `UnableToAssess`). The
  *researcher-relative match* is computed at reveal — `lower ≤ value ≤ upper`
  against the researcher's **committed** interval. No adjudicator model is in
  the trust path.
- **Display == on-chain:** the demo's agreement label is derived only through
  `agreement.py`, which mirrors the Rust `derive_agreement_level`, so what's
  printed can never diverge from the HarmonyRecord.

See `docs/CORE_BENCH_INTEGRATION.md` §"Where the independence actually comes
from" and §"The outcome-semantics decision" (spec §7) for the full rationale.

---

## Review-hardening (landed 2026-06-01)

Three independent units from an external review, built TDD and merged to `main`.
**None touch an integrity zome or change a DNA hash.**

1. **Capsule blinding gate** (`capsule_blinding_gate.py`). The structural blinding
   (hard-mode file deletion) is now also *proven per round*: after the researcher
   seals the claim and **before any validator runs**, the gate scans every
   *retained* file (those not removed in hard mode, classified prefix-aware
   against `CAPSULE_PATHS_TO_REMOVE["hard"]`) for the committed answer. Two
   signals — rounded-form match on all files, interval-membership on doc files
   only. If the answer leaks, the round **hard-aborts with `CapsuleLeakError`**
   instead of letting "independent execution" reduce to "read the number". The
   spike prints a non-fatal leak report.
2. **`/record` numeric-convergence panel.** `GET /record` now returns a numeric
   panel — each validator's value vs the researcher's committed interval — with
   explicit degradation states (full panel when revealed, `"pending"` pre-reveal,
   base-fields-only on any enrichment error; it never 500s). The match arithmetic
   lives in pure JS helpers in `node-lib.mjs` (`numericMatch` is a faithful port
   of Python `match_value`, inclusive bounds, empty/whitespace → non-match),
   tested with `node --test`. Base fields stay back-compatible with `ai_validator.py`.
3. **Agreement parity.** `derive_agreement_level` / `derive_majority_outcome` are
   pinned to a shared fixture `valichord/shared_types/tests/agreement_golden.json`
   asserted by **both** `demo/test_agreement.py` (Python) and a Rust `#[test]` in
   `shared_types` — a cross-language guard against threshold drift. The runner now
   **echoes the authoritative on-chain `outcome`/`agreement_level`** read
   gossip-free on the authoring node (`/create-harmony-record` returns them),
   falling back to a local recompute only if absent and flagging it
   (`agreement_recomputed`, labelled in the printed output).

---

## The honest independence claim

Three runs of the *same* model by the *same* operator are **correlated, not
independent** — they prove determinism + no result-copying, a real but narrow
guarantee. Genuine independence comes from **diversity across the validator
set**. So:

- **Mixed models** (Claude + GPT-4o + Gemini) is the configuration that earns
  the word "independent" without an asterisk — a shared model blind-spot can't
  pass undetected through all three.
- The on-chain `agreement_level` is described as **"independent execution
  agreement"** (the validators each independently produced a result and agree
  they reproduced). The **numeric convergence** against the researcher's claim
  is the separate, verifiable headline.
- An **all-Claude** run is a perfectly good "does the whole protocol work?"
  demonstration — it just must be labelled honestly as *same-model* (no
  cross-model independence claim).

---

## Prerequisites

- **Privileged Docker** (the inspect sandbox `compose.yaml` runs `privileged: true`).
- `pip install -r requirements-core-bench.txt` (installs `inspect_ai`,
  `inspect_evals` pinned to a verified `main` commit, `scipy`, `google-genai`,
  plus the base `requirements.txt`). Needs `git` on the host (the `inspect_evals`
  pin is a `git+` URL). These are kept **out** of `requirements.txt` so the
  public web demo's Render build (no `git`) is unaffected.
- **Provider API keys** for the validator models. Mixed-model needs all three;
  all-Claude needs only Anthropic:
  - `ANTHROPIC_API_KEY` — Claude (and the researcher's runs)
  - `OPENAI_API_KEY` — GPT-4o
  - `GOOGLE_API_KEY` — Gemini-2.5-pro
  - Note: **free tiers are not enough.** CORE-Bench reproduction is genuinely
    agentic, so it needs a capable model: OpenAI has no usable free API tier
    (`insufficient_quota`), and the Google free tier excludes `gemini-2.5-pro`
    (`free_tier_requests, limit: 0`). Use paid keys, or run all-Claude/all-Sonnet.
- **Disk:** each sandbox grows to **~14 GB** (the agent installs heavy ML
  stacks). Validators run **sequentially** (one sandbox at a time), so the full
  run needs only ~14 GB for the active sandbox plus the conductors — budget
  ~30 GB free. See "Known constraints" below.
- The 5-conductor stack (`demo/docker-compose.yml`) for the commit-reveal half —
  pack `valichord.happ` first if needed (`hc app pack valichord -o valichord/workdir/valichord.happ`).

## Run

```bash
cd demo
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...          # mixed-model only
export GOOGLE_API_KEY=...             # mixed-model only

# (optional) confirm a capsule reproduces before a full run:
python3 core_bench_spike.py --capsule capsule-0851068 --model anthropic/claude-opus-4-8

# The commit-reveal half targets the node HTTP APIs from demo_runner, which
# default to the permanently-live Oracle nodes (132.145.34.27:3001-3004). To run
# the DHT half on a LOCAL stack instead, bring it up and point the runner at it:
docker compose -f docker-compose.yml up --build -d
until [ "$(docker compose -f docker-compose.yml logs 2>/dev/null | grep -c 'node API ->')" -ge 4 ]; do sleep 3; done && echo Ready
export VALICHORD_RESEARCHER_URL=http://localhost:3001
export VALICHORD_VALIDATOR_1_URL=http://localhost:3002
export VALICHORD_VALIDATOR_2_URL=http://localhost:3003
export VALICHORD_VALIDATOR_3_URL=http://localhost:3004
# (omit the four exports to record on the public Oracle DHT instead — no local stack needed)

# full protocol run (mixed-model default: claude-opus-4-8 / gpt-4o / gemini-2.5-pro):
python3 core_bench_runner.py --capsule capsule-0851068

# all-Sonnet variant (one key, cheapest; same-model label):
python3 core_bench_runner.py --capsule capsule-0851068 --researcher-runs 1 \
    --researcher-model anthropic/claude-sonnet-4-6 \
    --validator-models anthropic/claude-sonnet-4-6 anthropic/claude-sonnet-4-6 anthropic/claude-sonnet-4-6

docker compose -f docker-compose.yml down -v   # between runs (only if you used a local stack)
```

Flags: `--researcher-runs` (default 3; use `1` for a deterministic capsule),
`--tolerance` (default `0.001` = ±0.1%, the committed band for deterministic
capsules), `--researcher-model`, `--validator-models` (three model strings).

## Chosen capsule

**`capsule-0851068`** (Medical Sciences, Python, MLP COVID/skin classification).
Single question: *"Report the final AUC after training."* Ground truth (all
three benchmark runs): **`0.9157952669235003`** — deterministic.

**Verified 2026-05-31:** both Claude **Opus 4.8** (~9 min) and Claude
**Sonnet 4.6** (~11 min) reproduced it **exactly** (`0.9157952669235003`, to 16
digits). Because it's deterministic, the researcher commits the value plus an
explicit ±0.1% tolerance (sealed on-chain), and faithful validator runs converge
on the same value → `ExactMatch`.

> **More-representative follow-up:** a deterministic capsule gives the crispest
> first impression, but a *stochastic* capsule (e.g. `capsule-6003668`) is
> arguably the more representative use of ValiChord — multiple validators
> triangulate a noisy quantity, which a single run cannot. See the spec §3 note.

## Skeptic-proof verification

The match is **recomputable from the record** — you don't have to trust the
demo, the researcher, or any validator:

```bash
# researcher node URL — the public Oracle by default, or localhost:3001 if you
# set the VALICHORD_*_URL exports above to run on a local stack:
curl "http://132.145.34.27:3001/record?hash=<external_hash>"
```

The researcher's committed value + interval live in the `ResearcherReveal`
metrics, and each validator's revealed value lives in its attestation metrics.
Redo `lower ≤ value ≤ upper` by hand (inclusive bounds) — it's `≤` comparisons, not a model call.

---

## Files

| File | Responsibility |
|---|---|
| `report_to_verdict.py` | **pure**: committed-claim derivation (95% interval / tolerance), interval match, blind validator verdict, reveal-time numeric panel |
| `core_bench_capture_scorer.py` | Inspect scorer that captures `report.json`; never reads ground truth (blinding guard tested) |
| `core_bench_validator.py` | builds the hard-mode blind Task, runs one eval/model, extracts the captured report, derives the researcher's N-run claim |
| `core_bench_runner.py` | orchestrator + CLI: key validation → researcher claim → 3 validators → commit-reveal (reuses `demo_runner` node APIs) → HarmonyRecord → numeric panel |
| `core_bench_spike.py` | Phase-0 capsule-selection helper (one capsule / one model, prints value + timing); now also prints a non-fatal blinding-leak report |
| `capsule_blinding_gate.py` | **pure** (+ tarball loader): pre-round blinding gate — retained/deleted classifier, leak detection, `assert_capsule_blind` (raises `CapsuleLeakError`) |
| `node-lib.mjs` (helpers) | `numericMatch` (port of Python `match_value`), `parseCommittedInterval`, `buildNumericConvergence`, `executionAgreementNote` for the `/record` panel |

Tests: `test_report_to_verdict.py`, `test_core_bench_capture_scorer.py`,
`test_core_bench_validator.py`, `test_core_bench_runner.py`,
`test_core_bench_imports.py` (34 tests), plus the review-hardening tests
`test_capsule_blinding_gate.py` (7) + `test_agreement.py` golden parity (3) +
`test_record_helpers.mjs` (5, `node --test`) + a Rust golden test in
`shared_types` (`cargo test -p valichord_shared_types`, 27). The pure adapter
tests always run; the inspect-dependent ones `importorskip`.

---

## Verification status (2026-05-31)

**Full commit-reveal run DONE (Codespace, 128 GB disk):**
- ✅ End-to-end all-Sonnet run (researcher + 3 validators all `claude-sonnet-4-6`,
  `--researcher-runs 1`) → clean **`Reproduced` / `ExactMatch`** HarmonyRecord;
  all 3 validators independently produced `0.9157952669235003` → MATCH.
- ✅ Record is public and recomputable on the Oracle DHT:
  `curl "http://132.145.34.27:3001/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"`
- ✅ Full validator path: dataset download → privileged Docker sandbox →
  model-as-agent installs deps + runs the paper's code → `report.json` captured →
  `extract_report_from_log` pulls the value out of the real `EvalLog`.
- ✅ Both Opus 4.8 and Sonnet 4.6 reproduce `capsule-0851068` **exactly**.
- ✅ 31 unit/integration tests pass.

**Found and fixed during live verification:**
- `filter_out_gpu` disabled — inspect_evals' `requires_gpu()` substring-matches
  `REPRODUCING.md`, which contains the boilerplate `docker run --gpus all` line
  in nearly every capsule, so `filter_out_gpu=True` empties the dataset.
- `anthropic` bumped to `>=0.105.0` (inspect_ai's anthropic provider requires it).
- **Validators made sequential** — they ran in a `ThreadPoolExecutor`, but
  inspect_ai forbids concurrent `eval_async` ("Multiple concurrent calls … not
  allowed"). Blinding is structural (isolated sandboxes), not timing-dependent.
- **`google-genai` added** to `requirements-core-bench.txt` — the Gemini provider
  imports it lazily and errors at call time if absent.
- **`gemini-1.5-pro` → `gemini-2.5-pro`** — 1.5-pro was retired from the Google API.
- **Infra failures no longer mint bogus verdicts** — a rate-limited / quota'd /
  interrupted validator yields a non-`success` `EvalLog` with no samples;
  `run_validator_eval` now raises on that so the round **aborts with the real
  error** instead of recording a false `FailedToReproduce` on a HarmonyRecord.

## Known constraints

- **Disk:** ~14 GB per sandbox, but validators run **sequentially** (one sandbox
  at a time), so budget ~30 GB free (active sandbox + conductors), not 3×.
- **Speed:** hard-mode reproduction is agentic (install → run → debug → report),
  ~6–9 min per run on Opus, ~11 min on Sonnet. Sequential validators mean the
  full 4-run round (1 researcher + 3 validators) is ~30–45 min wall-clock.
- **Cost:** ~$1 per agent run on Opus (mostly cheap cache reads); ~5× less on
  Sonnet — **confirmed to reproduce the capsule** (2026-05-31).
- **inspect_evals pin:** the published PyPI release lags `main` and uses a
  different CORE-Bench API (no `react`, no `filter_out_vision`, no
  `CAPSULE_CHECKSUMS`). The `requirements-core-bench.txt` git+SHA pin is deliberate.
