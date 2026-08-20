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

Shape proposed by KeilerHirsch, `lm-evaluation-harness#3749`, 2026-08-20, and adopted here as the
working design:

- `requested_model_id`
- `observed_model_id`
- routing / fallback evidence
- `identity_observation_method`
- provider / runtime identity where available
- **`unknown` / `not_exposed` as a legitimate state**, rather than silently copying requested into
  observed

His constraint is the load-bearing part, and is stronger than "record what came back":

> "observed" must mean evidence actually exposed by the serving system or an auditable runtime
> field, not what the client assumes it received.

That is the same doctrine as the ValiChord gate rule — do not decide from the summary the
interested party wrote, fetch what the system actually asserted — and as ADR-012 on the Nondominium
side, where a reader re-derives a clone address rather than trusting the anchor that names it.
Four independent arrivals at the same principle now. It is worth stating once in the spec rather
than rediscovering per field.

`model_id` keeps its current meaning for every existing bundle. Whether it becomes an alias for
`requested_model_id` or is retained unchanged alongside the new pair is an open question below.

## Open questions

1. **Which of these does `content_hash` cover?** The unresolved one, and the reason the field set
   either works or does not. If `observed_model_id` is inside, a provider's silent upgrade changes
   the hash of an otherwise identical rerun — correct, and surprising. If it is outside, two runs
   against genuinely different models compare as scientifically equivalent, which is the exact
   failure the field exists to prevent. The second is clearly worse; the first still needs saying
   out loud in the spec.
2. What shape is "routing / fallback evidence"? The one item that could balloon. A provider-opaque
   blob is honest and unverifiable; a schema will not survive contact with the next provider.
3. Does `model_id` survive as an alias, or is it retained unchanged and the new fields sit
   alongside? Aliasing is tidier and changes the meaning of a shipped field, which §7 would treat
   as breaking rather than additive.

## Resolved by that proposal

- *Is one field enough, or does this want a small struct?* — A struct. Answered.
- *Should the format say anything when observed is absent?* — Yes: `unknown` / `not_exposed` as an
  explicit state. Absent must not be read as "same as requested", which is precisely how the
  current single field misleads.
