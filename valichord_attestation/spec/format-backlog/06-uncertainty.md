# Backlog: uncertainty beyond `stderr`

**Status:** Open. Additive.
**Raised by:** KeilerHirsch (BRONCO), `lm-evaluation-harness#3749`, 2026-08-19.
**Related:** 04, 07.

## Problem

`Metric.stderr` is the only uncertainty the format expresses, and it is a single number with no
stated meaning. Standard error of what, computed how, over which population, under what
assumption? A bootstrap CI, an analytic binomial interval and a naive sample standard error are
all reported identically today.

For a benchmark result this is mostly untidy. For a metrology audience it is the difference
between a measurement and a number.

## v2 position

`Metric.stderr: Optional[float]`, pre-rounded to six decimal places, undefined as to method.

## Proposed direction

Optional interval and method alongside the existing field. `stderr` stays exactly as it is —
every existing bundle keeps its meaning and its hash.

## Open questions

1. Is naming the method sufficient, or does it need parameters — bootstrap resamples, confidence
   level, seed?
2. Does uncertainty belong on `Metric` or on the run? Sampling uncertainty is per-metric;
   judge-variance and provider-nondeterminism are per-run and interact with 05.
3. Should the format say what `stderr` means for bundles that only have it? Retrofitting a
   definition to existing bundles is not possible, but silence is what caused this.
