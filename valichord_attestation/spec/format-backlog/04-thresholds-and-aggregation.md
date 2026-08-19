# Backlog: thresholds and aggregation

**Status:** Open. Additive.
**Raised by:** independently by the same three people as 02 and 03, same week.
**Related:** 02, 03, 06.

## Problem

A metric value is reported without the rule that produced it. Whether a sample counted as correct
may depend on a threshold; whether the headline number is a mean, a median, a pass@k or a
macro-average over subtasks is not recorded anywhere. Two bundles can report `accuracy: 0.847`
having computed it differently, and nothing in either says so.

This also blocks the one check the threat model asks for and the library still does not provide:
recomputing an aggregate from disclosed samples requires knowing how it was aggregated.

## v2 position

`Metric` carries `key`, `value`, optional `stderr` and optional `filter`. `filter` disambiguates
metrics from different filter passes — the closest existing field, and not the same thing.

## Proposed direction

Optional aggregation descriptor on `Metric`, and optional threshold where a scoring decision
depends on one. Naming the aggregation is likely enough; specifying it executably is a much larger
project and one the format has deliberately avoided.

## Open questions

1. A named enum (`mean`, `median`, `pass_at_k`, `macro_avg`) is tractable and will be incomplete
   within a year. A free string is honest and unverifiable. Neither is obviously right.
2. Does this interact with the unbuilt verifier-side metric recomputation helper? It is the
   missing input to it, so probably they should be designed together.
3. Per-metric or per-bundle? Multi-metric bundles can mix aggregation rules, which argues
   per-metric and adds weight to every `Metric`.
