# Backlog: comparison validity

**Status:** Open. Probably additive; may be guidance rather than schema.
**Raised by:** KeilerHirsch (BRONCO), `lm-evaluation-harness#3749`, 2026-08-19.
**Related:** 01, 03, 04, 05. Arguably the item all of those serve.

## Problem

Two bundles can be individually valid, mutually incomparable, and offer no signal of it. Different
rubric revision, different judge, different aggregation, different dataset slice, different
provider routing — each recorded faithfully, each making the comparison meaningless, none
preventing someone from putting the two numbers side by side.

`content_hash` was built for the comparison case: it excludes `meta` so reruns differing only in
provenance compare equal. But it answers "are these the same claim", not "may these two claims be
compared", and the second question is the one people actually ask.

## v2 position

`content_hash` equality, which is a strict identity test. Anything short of identical yields no
guidance at all.

## Proposed direction

Unclear, deliberately. Options span a comparability key derived from the fields that must match,
guidance in the spec with no schema change, or a verifier-side helper that reports *why* two
bundles differ rather than merely that they do. The third is the most useful and the least
specified.

## Open questions

1. Is this a format concern or a tooling concern? A helper that diffs two bundles and names the
   comparison-invalidating differences may deliver everything without touching the schema.
2. Which differences invalidate a comparison, and which are merely notable? That is a scientific
   judgement the format probably should not make on the reader's behalf.
3. Does this need 01–05 to land first? Most of it cannot be computed until the fields exist, so
   this is likely the last item rather than the first.
