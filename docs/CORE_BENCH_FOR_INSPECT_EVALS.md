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

<!-- written in a later task -->

## What it doesn't do yet

<!-- written in a later task -->

## How it fills the gap

<!-- written in a later task -->

## Reproduce it yourself

<!-- written in a later task -->

## What still needs doing

<!-- written in a later task -->

## In one sentence

Several agents ran the code in isolated environments. None could see the others'
results before they committed. The record, on a network no single party controls,
shows what each one got — and you can verify it yourself with a single `curl`. A
CORE-Bench *score* becomes a CORE-Bench *attestation*.
