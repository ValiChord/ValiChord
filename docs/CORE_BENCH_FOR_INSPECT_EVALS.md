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

<!-- written in a later task -->

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
