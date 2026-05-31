# ValiChord × CORE-Bench — CLI Demo

A fully-local command-line demo that runs one real [CORE-Bench](https://arxiv.org/abs/2409.11363)
capsule through ValiChord's blind commit-reveal protocol with three AI
validators, producing a tamper-evident **HarmonyRecord** whose replication
verdict is decided by **recomputable arithmetic, not LLM opinion**.

Design spec: `docs/superpowers/specs/2026-05-31-core-bench-demo-design.md`
Implementation plan: `docs/superpowers/plans/2026-05-31-core-bench-demo.md`
Strategy/architecture: `docs/CORE_BENCH_INTEGRATION.md`

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
        | each writes report.json, blind to the sealed answer and to each other
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
- `pip install -r requirements.txt` (installs `inspect_ai`, `inspect_evals`
  pinned to a verified `main` commit, `scipy`, and `anthropic>=0.105.0`).
- **Provider API keys** for the validator models. Mixed-model needs all three;
  all-Claude needs only Anthropic:
  - `ANTHROPIC_API_KEY` — Claude (and the researcher's runs)
  - `OPENAI_API_KEY` — GPT-4o
  - `GOOGLE_API_KEY` — Gemini (a free Google AI Studio key works)
- **Disk:** each sandbox grows to **~14 GB** (the agent installs heavy ML
  stacks). A 32 GB machine cannot fit three parallel sandboxes — use a
  **64 GB+** machine for the full run. See "Known constraints" below.
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

# bring up the conductor stack:
docker compose -f docker-compose.yml up --build -d
until [ "$(docker compose -f docker-compose.yml logs 2>/dev/null | grep -c 'node API ->')" -ge 4 ]; do sleep 3; done && echo Ready

# full protocol run (mixed-model default):
python3 core_bench_runner.py --capsule capsule-0851068

# all-Claude variant (one key, same-model label):
python3 core_bench_runner.py --capsule capsule-0851068 \
    --validator-models anthropic/claude-opus-4-8 anthropic/claude-opus-4-8 anthropic/claude-opus-4-8

docker compose -f docker-compose.yml down -v   # between runs
```

Flags: `--researcher-runs` (default 3; use `1` for a deterministic capsule),
`--tolerance` (default `0.001` = ±0.1%, the committed band for deterministic
capsules), `--researcher-model`, `--validator-models` (three model strings).

## Chosen capsule

**`capsule-0851068`** (Medical Sciences, Python, MLP COVID/skin classification).
Single question: *"Report the final AUC after training."* Ground truth (all
three benchmark runs): **`0.9157952669235003`** — deterministic.

**Verified 2026-05-31:** Claude Opus 4.8 reproduced it **exactly**
(`0.9157952669235003`, to 16 digits) in ~9 min. Because it's deterministic, the
researcher commits the value plus an explicit ±0.1% tolerance (sealed on-chain),
and faithful validator runs converge on the same value → `ExactMatch`.

> **More-representative follow-up:** a deterministic capsule gives the crispest
> first impression, but a *stochastic* capsule (e.g. `capsule-6003668`) is
> arguably the more representative use of ValiChord — multiple validators
> triangulate a noisy quantity, which a single run cannot. See the spec §3 note.

## Skeptic-proof verification

The match is **recomputable from the record** — you don't have to trust the
demo, the researcher, or any validator:

```bash
curl "http://localhost:3001/record?hash=<external_hash>"
```

The researcher's committed value + interval live in the `ResearcherReveal`
metrics, and each validator's revealed value lives in its attestation metrics.
Redo `lower ≤ value ≤ upper` by hand — it's `<` and `>`, not a model call.

---

## Files

| File | Responsibility |
|---|---|
| `report_to_verdict.py` | **pure**: committed-claim derivation (95% interval / tolerance), interval match, blind validator verdict, reveal-time numeric panel |
| `core_bench_capture_scorer.py` | Inspect scorer that captures `report.json`; never reads ground truth (blinding guard tested) |
| `core_bench_validator.py` | builds the hard-mode blind Task, runs one eval/model, extracts the captured report, derives the researcher's N-run claim |
| `core_bench_runner.py` | orchestrator + CLI: key validation → researcher claim → 3 validators → commit-reveal (reuses `demo_runner` node APIs) → HarmonyRecord → numeric panel |
| `core_bench_spike.py` | Phase-0 capsule-selection helper (one capsule / one model, prints value + timing) |

Tests: `test_report_to_verdict.py`, `test_core_bench_capture_scorer.py`,
`test_core_bench_validator.py`, `test_core_bench_runner.py`,
`test_core_bench_imports.py` (28 tests; the pure adapter tests always run, the
inspect-dependent ones `importorskip`).

---

## Verification status (2026-05-31)

**Verified live (Codespace, Claude Opus 4.8):**
- ✅ Full validator path end-to-end: dataset download → privileged Docker
  sandbox → Claude-as-agent installs deps + runs the paper's code → `report.json`
  captured → `extract_report_from_log` pulls the value out of the real `EvalLog`.
- ✅ `capsule-0851068` reproduces **exactly** (`0.9157952669235003`).
- ✅ 28 unit/integration tests pass.

**Found and fixed during live verification:**
- `filter_out_gpu` disabled — inspect_evals' `requires_gpu()` substring-matches
  `REPRODUCING.md`, which contains the boilerplate `docker run --gpus all` line
  in nearly every capsule, so `filter_out_gpu=True` empties the dataset.
- `anthropic` bumped to `>=0.105.0` (inspect_ai's anthropic provider requires it).

**Pending (needs a larger machine):**
- The full commit-reveal run to a HarmonyRecord. It reuses the already-proven
  node-API commit-reveal path the live Oracle demo runs daily, so it is the
  lowest-risk remaining step — but each sandbox is ~14 GB, so a full
  (3-validator) run needs a **64 GB+** machine. On a 32 GB box, a single sandbox
  plus the conductor stack already exceeds free disk.

## Known constraints

- **Disk:** ~14 GB per sandbox; budget ~50 GB for a 3-parallel run plus
  conductors. Point Docker's `data-root` at the largest available disk if
  needed.
- **Speed:** hard-mode reproduction is agentic (install → run → debug → report),
  ~6–9 min per run. The `<5 min` target is optimistic for real capsules.
- **Cost:** ~$1 per agent run on Opus (mostly cheap cache reads); ~5× less on
  Sonnet if it reproduces the capsule (untested as of this writing).
- **inspect_evals pin:** the published PyPI release lags `main` and uses a
  different CORE-Bench API (no `react`, no `filter_out_vision`, no
  `CAPSULE_CHECKSUMS`). The `requirements.txt` git+SHA pin is deliberate.
