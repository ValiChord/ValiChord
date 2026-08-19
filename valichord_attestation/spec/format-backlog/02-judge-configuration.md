# Backlog: judge-model configuration

**Status:** Open. Additive.
**Raised by:** independently, within one week, by three people with no contact with each other —
Seekers2001 (`future-agi#1368`, 2026-08-16), Hawthorn (`future-agi#1368`, 2026-08-17),
KeilerHirsch (`lm-evaluation-harness#3749`, 2026-08-19).
**Related:** 03, 04. Same convergence, same `meta` trap (see `README.md`).

## Problem

LLM-as-judge evaluation is now common and the format has nowhere to record the judge. Which model
graded, at what temperature, with what system prompt, at what version. Two runs of the same task
over the same samples, graded by different judges, produce different numbers for reasons the
bundle cannot express.

Three people building against this format named it in the same week, without seeing each other's
comments. That is the strongest evidence available that this is a real gap rather than one
reviewer's taste.

## v2 position

Nothing. A judge is a model, and the bundle has one `model_id`, which is the model under test.

## Proposed direction

An optional judge block. The specific fields matter less than the decision in the open questions
below, and BRONCO has offered to specify this layer (see `README.md`).

## Open questions

1. **`content_hash` or `meta`?** This is the load-bearing question and it is not close: a
   different judge can change the score, so it belongs where `content_hash` can see it. Putting
   it in `meta` would make two runs with different judges compare as equivalent.
2. Is a judge one model or a pipeline? Rubric-plus-model-plus-aggregation is common, which makes
   this overlap 03 and 04. They may be one field set rather than three.
3. Does a judge configuration want its own hash, so a long prompt need not be carried inline?
