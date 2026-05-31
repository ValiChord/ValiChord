# CORE-Bench × ValiChord — CLI Demo Design

**Date:** 2026-05-31
**Status:** Design — approved in brainstorming, pending spec review
**Author:** Ceri John (with Claude)
**Related:** `docs/CORE_BENCH_INTEGRATION.md` (strategy/architecture), `PROJECT_STATUS.md` (§5 "CORE-Bench + ValiChord demo")

---

## 1. Goal

A **command-line, fully self-contained demo** that runs one real CORE-Bench
capsule through ValiChord's blind commit-reveal protocol with **three
mixed-model AI validators**, producing a tamper-evident `HarmonyRecord` whose
replication verdict is decided by **arithmetic, not LLM opinion**, and is
recomputable by any third party from the on-chain record.

This is the "gift you lead with" from the integration doc: it depends on
nothing from inspect_evals upstream and needs no positive response to any
outreach to exist. Web-demo integration (into `demo/app.py`) is explicitly
**out of scope** for this build and is a possible follow-on.

### Success criteria

1. `python3 demo/core_bench_runner.py --capsule <id>` runs end-to-end against a
   local 5-conductor stack and prints a shareable `HarmonyRecord` URL.
2. Three validators each reproduce the capsule with a **different model**
   (Claude + GPT-4o + Gemini), in isolated Inspect sandboxes, blind to the
   target and to each other.
3. The replication decision is **mechanical**: execution-success classification
   + a numeric interval comparison, with no adjudicator model in the trust path.
4. The numeric convergence is **independently recomputable** from the revealed
   record (`curl` the HarmonyRecord, redo the `≤` comparison).
5. Unit + fixture tests are CI-safe (no Docker, no keys, no network); the one
   real live run is a documented local step.

---

## 2. Decisions locked in brainstorming

| Decision | Choice | Rationale |
|---|---|---|
| Deliverable | CLI standalone proof (no web UI) | Doc's "lead with the gift"; de-risks fastest |
| Agent foundation | **inspect_evals** `core_bench` task (not the AutoGPT harness) | Model-agnostic `react()`+`bash`; runs *their actual eval*; aligns with the inspect_evals outreach |
| Independence | **Mixed models** (Claude + GPT-4o + Gemini) | Only config that earns the word "independent" without an asterisk (doc §"Where the independence actually comes from") |
| Capsule | Decide via a **test-run spike**, leaning deterministic | Capsule selection is empirical and on the critical path |
| Run target | **Fully local** docker-compose (5 conductors) + Inspect evals on same host | Self-contained artifact anyone can run |
| Integration approach | **A** — inspect_evals as a library, custom `Task` + **capture scorer** | Max reuse; clean commit-time / scoring separation |
| Outcome semantics | **Option 1** — committed outcome = execution success; match = post-reveal arithmetic | Faithful automation of the *original* protocol (validators committed their own verdict blind, checked against the researcher after reveal) |

---

## 3. Background: how CORE-Bench actually works (verified against source)

Verified against `topeuph-ai/core-bench` (original harness) and
`UKGovernmentBEIS/inspect_evals` `src/inspect_evals/core_bench/` (the
implementation we build on).

- **The inspect_evals task** `core_bench(difficulty, field, language, capsule_ids,
  exclude_capsule_ids, limit, filter_out_gpu, filter_out_vision, solver, …)`
  returns an Inspect `Task`. Its default solver is
  `react(tools=[bash(timeout=180), query_vision_language_model(...)])` and it is
  **model-agnostic** — the model is whatever you pass to `inspect_ai.eval(...)`.
- **The agent writes `report.json` into the sandbox** (`/capsule/report.json`);
  keys are the task questions, values are the answers. The stock scorer
  (`evaluate_task_questions`) reads it with `sandbox().read_file("report.json")`.
- **Ground truth lives only in `state.metadata["results"]`** (host-side, a JSON
  string of the *list of ground-truth runs*). It is **never** placed in the
  sandbox. In hard mode the sample's setup command deletes `results/`,
  `REPRODUCING.md`, `environment/`, and the run scripts — so the agent gets only
  code + data + README + the question list. **Blinding is structural.**
- **Scoring is the 95% prediction interval.** For numeric keys, the interval is
  `mean ± t_value · std · √(1 + 1/n)` with `t_value = t.ppf(0.975, n-1)` and
  `std` using `ddof=1`; an answer passes iff `lower ≤ reported ≤ upper`. Keys
  containing `fig` are vision questions; list/string keys use direct /
  case-insensitive equality. (`inspect_evals/core_bench/utils.py`,
  `scorer.py`.)
- **Edge case — deterministic capsules:** if the n ground-truth runs are
  identical, `std = 0`, the interval collapses to a single point, and the match
  is effectively exact.
- **Sandbox** is Docker via `compose.yaml` with **`privileged: true`** on a
  `cruizba/ubuntu-dind` image. The host running the evals needs privileged
  Docker.
- **Dataset/capsule fetching** is handled by `read_core_bench_dataset` (HF
  download of `core_test.json.gpg` → `gpg` decrypt with passphrase
  `reproducibility` → per-capsule tarball download with SHA-256 verification via
  `CAPSULE_CHECKSUMS`).

### Candidate capsules (decrypted `core_test.json`, 45-task slice)

All Python, no vision, single numeric question:

| capsule_id | field | 3 ground-truth runs | character |
|---|---|---|---|
| `capsule-5507257` | Computer Science | 96.125 ×3 | deterministic → exact match |
| `capsule-9660931` | Computer Science | 0.999 ×3 | deterministic → exact match |
| `capsule-0851068` | Medical Sciences | 0.9158 ×3 | deterministic → exact match |
| `capsule-6003668` | Computer Science | 0.982 / **0.815** / 0.978 | wide real interval |

The Phase 0 spike confirms which reproduces clean in hard mode, < 5 min, no GPU.
Leaning deterministic for a crisp first-impression ("three different models all
converged on the identical number").

> **Note (Ceri's opinion — may prove incorrect):** the *demo-optimal* capsule
> and the *value-optimal* capsule are probably not the same. A **stochastic**
> capsule is likely the more representative use of ValiChord: when the result
> has genuine run-to-run variance, multiple independent validators do work a
> single run structurally cannot — they characterise the distribution and help
> "pin down" the likely-correct value, and blinding earns its keep (a validator
> can't tune their run toward a revealed target). A deterministic capsule still
> proves something real — reproduces-at-all (only ~21% of hard tasks do),
> robustness across diverse environments/agents, and no copying/fabrication —
> but the *marginal* value of extra validators and of the blinding is lower when
> there is no spread to triangulate. So we lead with deterministic for
> **legibility** (unambiguous, hard to nitpick in a 2-minute demo), and treat
> the stochastic capsule (`capsule-6003668`) as the **more representative
> follow-up** once the deterministic version has earned the first impression.
> This is a judgement call, not a settled fact — the live runs may show the
> stochastic capsule is too messy to be worth leading toward, or that
> deterministic carries more weight with the target audience than expected.

---

## 4. Architecture

Two phases: a one-time capsule-selection spike, then the repeatable demo run.

```
PHASE 0 — Capsule spike (one-time; no conductors needed)
  Run each candidate through inspect_evals core_bench (difficulty=hard,
  filter_out_gpu=True, filter_out_vision=True) with a real model.
  Confirm one reproduces clean in <5 min. Pick it; record its value.

PHASE 1 — Demo run (fully local)
  docker compose up  →  5 conductors (researcher + 3 validators + bootstrap)

  [Researcher]  runs the chosen capsule via Inspect eval (×N=3)
                → committed metrics + 95% interval (or value + explicit
                  tolerance if deterministic)
                → /lock-result + /submit-request   (SEALED on the DHT)

  [3 Validators in parallel — MIXED MODELS, blind]
        V1 = Claude     V2 = GPT-4o     V3 = Gemini
        each runs the SAME capsule, hard mode, its OWN isolated sandbox
        → report.json  → report_to_verdict()  → /commit  (sealed; none see another's)

  [All 3 committed]  → ValiChord opens reveal phase
  [Reveal]  researcher /reveal (value+interval) ; validators /reveal
  [Finalise]  /create-harmony-record → HarmonyRecord on DHT + shareable URL
  [Numeric panel]  each validator value vs committed interval — the verifiable headline
  [Optional overlay]  stock evaluate_task_questions() ground-truth score — POST-REVEAL only
```

The Inspect evals run on the orchestrator host (privileged Docker). ValiChord
"validators" are conductor identities that receive a verdict over the existing
HTTP node API — the same seam `demo_runner.run_protocol` uses today. **No
Docker-in-Docker inside the conductor containers.**

---

## 5. Components (all new files under `demo/`)

| File | Purpose | Depends on |
|---|---|---|
| `core_bench_capture_scorer.py` | Custom Inspect scorer: reads `report.json` from the sandbox and stores its raw contents in the eval log. **Never reads `state.metadata["results"]`.** | `inspect_ai` |
| `core_bench_validator.py` | Builds the Task (`read_core_bench_dataset` + `default_solver` + capture scorer), runs `inspect_ai.eval(task, model=…)` for one capsule/one model, returns the parsed `report.json` (or a failure marker). | `inspect_evals`, capture scorer |
| `report_to_verdict.py` | **Pure** adapter: `report.json` (+ researcher's committed interval, when matching) → ValiChord verdict `{outcome, confidence, reasoning}` + `metrics` list. | none |
| `core_bench_runner.py` | Orchestrator: researcher claim → 3 mixed-model validators (parallel) → commit-reveal via node HTTP APIs → HarmonyRecord → numeric panel. Mirrors `demo_runner.run_protocol`. | the above + `agreement.py` |
| `CORE_BENCH_DEMO.md` | Run instructions, capsule choice, model/key matrix, the honest independence claim, skeptic-proof verification section. | — |

**Reused unchanged:** `demo/docker-compose.yml` (5 conductors), the node HTTP
APIs (`/lock-result`, `/submit-request`, `/commit`, `/phase`, `/reveal`,
`/create-harmony-record`), and `demo/agreement.py`
(`derive_agreement_level` / `derive_majority_outcome`) so the displayed outcome
matches the on-chain record by construction.

---

## 6. Data flow

### 6.1 Binding the claim to the capsule

`data_hash = SHA-256(capsule_tarball ‖ run_salt)`. inspect_evals ships
per-capsule `CAPSULE_CHECKSUMS`, so the committed hash provably pins the exact
capsule. `run_salt` (16 random bytes) keeps each demo run a fresh DHT identity,
as today.

### 6.2 Researcher claim (sealed first)

Researcher runs the chosen capsule **N = 3** times via the same Inspect eval,
then derives, per numeric question:

- committed value = mean of the N runs
- committed interval = 95% PI `mean ± t·std·√(1+1/n)`

For a **deterministic** capsule the interval collapses to a point, so the
researcher instead commits the value **plus an explicit, on-chain tolerance**
(default ±0.1% relative) to absorb agent formatting (`96.12` vs `96.12499`).
Either way the interval/tolerance is part of the sealed commitment via
`/lock-result` — never a silent Python-side knob. (See `docs/CORE_BENCH_INTEGRATION.md`
§"Match criterion".)

### 6.3 Validator reproduction (blind, mixed models, parallel)

Each validator runs `core_bench` (hard, no-GPU, no-vision, `capsule_ids=[id]`)
with its own model. The capture scorer lifts `report.json` from the sandbox.
`report_to_verdict()` maps it to a committed verdict (§7). `/commit` seals it;
no validator sees another's, and none see the researcher's sealed value.

### 6.4 Reveal → finalise → verify

Researcher `/reveal`s value+interval; validators `/reveal`;
`/create-harmony-record` writes the HarmonyRecord. The runner then computes the
**numeric-convergence panel**: each validator's revealed value vs the
researcher's committed interval. Display agreement is routed through
`agreement.py` so it equals the on-chain record. The numeric panel is
recomputable by anyone from the DHT (`ResearcherReveal` value+interval +
validator attestation metrics).

**Optional overlay (post-reveal only):** the stock `evaluate_task_questions()`
ground-truth score, kept strictly separate and never available at commit time.

---

## 7. The outcome-semantics decision (Option 1)

**Verified protocol fact:** the validator's `AttestationOutcome` is sealed at
commit time and **immutable** (the reveal must replay the identical attestation
or the on-chain `SHA-256(msgpack(attestation) ‖ nonce)` check fails).
`derive_agreement_level` (shared_types/src/lib.rs) computes agreement **purely
from the committed `outcome` enums** — it never numerically compares metrics
against the researcher's reveal. So on-chain, "agreement" means *the validators
agree among themselves*; the researcher's sealed result is what lets a third
party verify, after reveal, that the consensus matches the claim.

This is exactly the **original protocol** (when validators were human): each
validator committed their own verdict blind, then checked it against the
researcher's result *after* reveal. We automate that faithfully:

| Original (human validators) | This demo (Option 1) |
|---|---|
| Validator commits "did I reproduce it?" blind | Committed outcome = code check on the eval result (below) |
| `agreement_level` = do the validators agree with each other | identical `derive_agreement_level` over committed outcomes |
| After reveal: validator eyeballs match vs researcher | After reveal: exact arithmetic, value vs committed interval — and **recomputable from the record** |

**Committed-outcome classification (mechanical, blind, no LLM judgement):**

- valid numeric `report.json` with all required keys present → `Reproduced`
- no `report.json` / invalid JSON / run errored → `FailedToReproduce`
- parsed but a required key missing or non-numeric → `UnableToAssess`

The "did it match the researcher?" decision is **not** in the committed outcome
(that would need the sealed target). It is the post-reveal numeric panel — `<`
and `>`, not a model call.

**Honest-labelling requirement:** the on-chain `agreement_level` is described as
*"independent execution agreement"* (the validators each independently produced
a result and agree they reproduced). The *numeric convergence* against the
researcher's claim is the separate, verifiable headline. For a vetted
deterministic capsule the two coincide in practice; any divergence is exposed
transparently in the numeric panel rather than hidden. `CORE_BENCH_DEMO.md`
states this precisely (no overclaiming to the inspect_evals audience).

---

## 8. Error handling & reliability

**Inspect eval failures (per validator).** Normalised by the capture scorer to
the three committed outcomes above. **One automatic retry with a fresh sandbox**
per validator (mirrors the `_MAX_ATTEMPTS=2` fresh-session pattern in
`custom_runner.py`). Because `num_validators_required = 3`, a validator that
still fails cannot be silently dropped — the round can't open reveal. So: retry
once; if still failing, **abort with a descriptive error naming which
validator/model failed and why** (mirrors the tolerant `as_completed` collection
in `demo_runner` / `ai_validator_cma`).

**Mixed-model keys.** Validate all required provider keys (Anthropic + OpenAI +
Google) up front; fail fast naming the missing one and which validator needs it.
Never start a partial round.

**Capsule / sandbox.** Capsule download (retry + SHA-256 verify) is inside
`read_core_bench_dataset` — surface its errors verbatim. If privileged Docker is
unavailable the sandbox build fails early; detect and give an actionable message
("this demo requires privileged Docker").

**Budget guards.** Respect the eval's `max_messages` / `token_limit` /
`bash(timeout=180)`. If the agent hits the message limit without a valid
`report.json`, that is `FailedToReproduce` (not a crash).

**Commit-reveal / DHT.** Reuse the existing patterns unchanged — DHT-propagation
sleeps, `_reveal_with_retry`, and the HarmonyRecord gossip-retry in
`demo_runner`. No new protocol plumbing.

**Two structural safety guards (tested):**

- **Blinding guard:** assert the validator Task is built with `difficulty="hard"`
  and that ground-truth `results` metadata is never threaded into the commit
  path.
- **Tolerance-is-committed guard:** the researcher's interval/tolerance must be
  sealed in `/lock-result`; the runner refuses to compute a match against any
  value not present in the committed claim.

---

## 9. Testing

**Unit (pure — no Docker/network/conductors/keys; CI-safe), test-driven:**

- `report_to_verdict.py` — fixtures: exact match (deterministic), inside
  interval, outside interval (→ numeric panel shows divergence), missing key,
  non-numeric value, extra keys, rounding (`96.12` vs `96.12499` under committed
  tolerance). Assert the interval arithmetic matches inspect_evals'
  `check_numeric_answer` / `calculate_prediction_intervals`.
- Capture scorer — stub `TaskState` + sandbox with a `report.json`; assert it
  captures the contents and **never** touches `state.metadata["results"]`
  (blinding guard).
- Claim derivation — N runs → mean+interval; degenerate (deterministic) → point
  + explicit committed tolerance.
- Outcome → agreement — assert the execution-success mappings flow through
  `agreement.py` consistently with the on-chain Rust.

**Fixture integration (no real capsule; mock the eval; CI-safe):**

- `core_bench_validator.py` with a stubbed eval returning a canned `report.json`
  — exercises the validator path without Docker.
- `core_bench_runner.py` against local conductors using **fixture `report.json`s**
  (skip the expensive evals) — validates the full commit-reveal wiring cheaply.

**Real end-to-end (manual/local, NOT CI — needs privileged Docker + 3 provider
keys + minutes):**

- Phase 0 capsule spike, then one full live Phase 1 run. This is the
  verification-before-completion evidence, gated behind capsule selection.

New tests sit beside `demo/test_agreement.py` (pytest). The heavy real run stays
a documented local step, consistent with how the project keeps Tryorama /
sweettest out of the fast path.

---

## 10. Dependencies

- `inspect_ai` and `inspect_evals` (pinned) added to `demo/requirements.txt`.
  Pin a known-good `inspect_evals` version since we import internal functions
  (`read_core_bench_dataset`, `default_solver`).
- Provider SDKs/keys for the three validator models (Anthropic, OpenAI, Google)
  — Inspect routes by model string; no extra adapter code.
- `gpg` and Docker (privileged) available on the orchestrator host.

---

## 11. Out of scope (explicit)

- Web-demo integration into `demo/app.py` (follow-on).
- The inspect_evals register schema fields (`valichord_attestation_uri` etc.) —
  the doc demotes these to a follow-on; the demo needs none of them.
- Oracle deployment — this build targets fully-local; node URLs stay env-var
  configurable so Oracle remains possible later.
- R capsules, GPU capsules, vision questions — filtered out.

---

## 12. Open items resolved during the live run (not blockers to building)

- **Which exact capsule** — settled by the Phase 0 spike.
- **Default tolerance for deterministic capsules** — start ±0.1% relative;
  confirm against the spike's observed agent formatting.
- **Per-validator model assignment** — default Claude / GPT-4o / Gemini;
  configurable via CLI flags.
