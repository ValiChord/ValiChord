# Backlog: requested vs observed model identity

**Status:** Open. Additive.
**Raised by:** KeilerHirsch (BRONCO), `EleutherAI/lm-evaluation-harness#3749`, 2026-08-19.
**Related:** the unnumbered dataset/row identity item in `README.md`.

## Problem

`Bundle.model_id` is a single string, and it quietly assumes the model you asked for is the model
you got. For a local weights file that holds. For a hosted endpoint it does not: providers route,
alias, silently upgrade point releases, and fall back under load. A bundle can therefore be
faithful about everything it records and still attribute a result to the wrong model.

This is worse than a missing field, because nothing signals its absence. The bundle looks
complete.

## v2 position

One field, `model_id: str`. No distinction between requested and observed, and no place to record
what the provider actually reported.

## Proposed direction

An optional observed-identity field alongside `model_id`, carrying whatever the provider returned
— response model string, system fingerprint, deployment id — without prescribing which, since it
varies by provider and prescribing one would date badly.

`model_id` keeps its meaning: what was requested. That preserves every existing bundle.

## Open questions

1. Does the observed identity belong in `content_hash`? It should — two runs against different
   actual models are not scientifically equivalent, whatever was requested. But that makes a
   provider's silent upgrade produce a different `content_hash` for a rerun, which is arguably
   correct and definitely surprising.
2. Should the format say anything when observed is absent? Absent means "not captured", not
   "same as requested", and conflating those is how the current single field misleads.
3. Is one field enough, or does this want a small struct? A struct is more honest and harder to
   agree on.
