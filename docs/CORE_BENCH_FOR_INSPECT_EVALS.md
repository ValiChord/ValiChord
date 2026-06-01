# CORE-Bench × ValiChord — an independent-verification layer for reproduction evals

> For the inspect_evals maintainers. This describes a working demo that runs the
> existing `core_bench` task and adds a multi-party, blinded, tamper-evident
> verification layer on top. Composition, not competition — Inspect runs the
> reproduction; this makes the result independently checkable.
>
> Related (internal) docs in this repo: `demo/CORE_BENCH_DEMO.md` (run guide),
> `docs/CORE_BENCH_INTEGRATION.md` (architecture & rationale).

## The gap this fills

A CORE-Bench `.eval` log is **single-author and self-attested**. Nothing in it
proves a *second* party would get the same output, nothing stops the producer
re-running until the number looks right, and there is no multi-party, blinded,
tamper-evident record of who got what. That is a real gap in the eval-framework
space, and it is not a feature Inspect built worse — it is a category Inspect has
no mechanism for. Inspect **runs** the reproduction; ValiChord makes the
reproduction's result **independently checkable** by a third party who wasn't in
the room. The two compose; neither replaces the other.

## What you'd actually see

The demo runs the `core_bench` task on a single deterministic capsule,
`capsule-0851068` (Medical Sciences, Python — an MLP COVID/skin classifier with
one question: *"Report the final AUC after training."*). A researcher runs the
capsule and seals the result; three validators each reproduce it blind in isolated
sandboxes; all commit, then reveal simultaneously; a HarmonyRecord is written.

The headline output is a per-validator numeric panel: each validator's produced
value against the researcher's **committed** interval — pure arithmetic, not a
model's opinion. For this capsule every faithful run lands on the same value
(`0.9157952669235003`), so the agreement is `ExactMatch`.

The record is public and recomputable. One from a real run:

```bash
curl "http://<researcher-node>/record?hash=uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT"
```

It returns the outcome, the agreement level, the participating validators, and —
on a node running the current code — a `numeric_convergence` panel like:

```json
{
  "outcome": "Reproduced",
  "agreement_level": "ExactMatch",
  "validator_count": 3,
  "numeric_convergence": [
    {"validator": 1, "metric": "AUC", "value": "0.9157952669235003",
     "lower": 0.9148, "upper": 0.9167, "match": true}
  ]
}
```

> Honest note: the public record linked above is from the run that first proved
> the protocol end-to-end; it predates the `numeric_convergence` panel, so a
> `curl` of *that* record shows the base fields without the panel. The JSON above
> is the panel's shape as produced by the current node code (see "Reproduce it
> yourself").

## What it does

- **N agents reproduce the same capsule, blind and isolated.** Each validator runs
  the `core_bench` hard-difficulty agent in its own Docker sandbox. Hard mode
  deletes `results/`, `REPRODUCING.md`, and the run scripts, so the agent gets only
  code + data + README + the question — it cannot read the target.
- **A pre-round blinding gate proves the answer isn't readable from retained
  files.** Deletion is necessary but not sufficient (a README could quote the
  number). Before any validator runs, the gate scans every retained file for the
  committed answer and **hard-aborts the round** if it leaks — turning "the agent
  can't see the target" from an assumption into a per-round, tested check.
- **The verdict is arithmetic, not opinion.** A validator's committed outcome is
  execution-success only; the *match* against the researcher's claim is computed at
  reveal as `lower ≤ value ≤ upper` (inclusive) against the researcher's
  **committed** interval. No adjudicator model sits in the trust path.
- **Commit-reveal removes last-mover advantage.** Each validator seals its
  `report.json` before any other reveals; copying would require predicting the
  others' outputs.
- **The record is recomputable.** The outcome, agreement level, and the per-metric
  numeric panel are derivable from a single `curl` — you don't have to trust the
  demo, the researcher, or any validator.

## What it doesn't do yet

Stated plainly, because this audience is equipped to notice an overclaim:

- **One capsule.** The demo uses a single, pre-verified, deterministic capsule.
  The more representative case — a *stochastic* capsule where multiple validators
  triangulate a noisy quantity — is not yet wired in.
- **Validators self-assign.** There is no assignment engine, conflict-of-interest
  detection, or institutional balancing yet (Phase 0); validators claim a study
  directly.
- **Reputation is `Provisional` in production.** Badge tiers currently reflect
  participant count and agreement only, not an earned validator track record.
- **No automated handoff** from a `.eval` log to the protocol — running the demo is
  a manual sequence today.
- **The `/record` numeric panel + the gossip-free outcome echo are unit-tested and
  syntax-checked, but have not yet been exercised against a live conductor.** The
  most recent *full* run used hosted nodes for the commit-reveal half; a clean
  local end-to-end with the current node code is a pending verification step (see
  "What still needs doing").

## How it fills the gap

| | CORE-Bench alone | ValiChord alone | Combined |
|---|---|---|---|
| Reproduction is computational | ✅ agent runs real code | ❌ (web-search demo) | ✅ |
| Verdict is objective | ✅ code output matches or not | ❌ agent forms an opinion | ✅ |
| Multiple independent parties | ❌ one agent, one result | ✅ N validators | ✅ |
| Structural independence | ❌ a second runner can see the first's result | ✅ commit-reveal | ✅ |
| Permanent verifiable record | ❌ a log file | ✅ HarmonyRecord | ✅ |
| No post-hoc adjustment | ❌ re-run and pick the best | ✅ commit-reveal | ✅ |

**What N independent runs actually prove** (stated narrowly, because precision
matters here): for deterministic code with pinned dependencies, N correct runs
produce the same output — so commit-reveal's guarantee is **prevented result-copying
and fabrication**, not *prevented opinion-anchoring*. Concretely, N hard-mode runs
show: (1) the capsule executes from scratch with no hints; (2) the result is robust
across independent environments; (3) no agent fabricated or copied a result.

Two precision rules we hold to, and ask you to hold us to:

- **Claim the right guarantee.** For deterministic code the value is anti-copying
  and anti-fabrication — not anti-anchoring. We state it that narrowly.
- **Don't overclaim independence.** N runs of the *same* model by the *same*
  operator are correlated, not independent. Genuine independence comes from
  diversity across the validator set (different models / operators / environments).
  The demo defaults to mixed models for exactly this reason; an all-one-model run
  is labelled honestly as same-model.

## Reproduce it yourself

<!-- written in a later task -->

## What still needs doing

<!-- written in a later task -->

## In one sentence

Several agents ran the code in isolated environments. None could see the others'
results before they committed. The record, on a network no single party controls,
shows what each one got — and you can verify it yourself with a single `curl`. A
CORE-Bench *score* becomes a CORE-Bench *attestation*.
