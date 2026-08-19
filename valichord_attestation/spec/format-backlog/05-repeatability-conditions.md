# Backlog: repeatability vs reproducibility conditions

**Status:** Open. Additive.
**Raised by:** KeilerHirsch (BRONCO), `lm-evaluation-harness#3749`, 2026-08-17 and 2026-08-19.
**Related:** the whole protocol. This is the vocabulary ValiChord has been missing.

## Problem

ValiChord's core claim is that an independent party got the same result. Metrology has had
precise words for this for decades, and ISO 5725 distinguishes **repeatability** (same operator,
same equipment, same conditions, short interval) from **reproducibility** (different operator,
different equipment, different conditions). They are different quantities and conflating them
overstates what a record establishes.

KeilerHirsch's correction on first raising it is the useful framing and worth preserving verbatim
in spirit: *"same result again" can mean either depending on which conditions changed, so encode
the conditions rather than using either word as a synonym for rerun consistency.* Encoding the
conditions is strictly more useful than picking the right label, because a reader can then decide
which quantity they are looking at.

## v2 position

Nothing. The bundle records a run; it does not record what was held constant or varied relative
to any other run. Neither word appears in the spec.

## Proposed direction

Optional conditions block describing what varied — operator or agent, hardware, provider,
software versions, time separation. Then repeatability and reproducibility are *derivable* from
comparing two bundles rather than asserted by either.

## Open questions

1. Is this a bundle field or a property of a comparison between bundles? Probably the latter,
   which would make it the first thing in the format that is not about a single run.
2. How much can be captured automatically? Hardware and versions yes; "different operator" needs
   an identity notion the format does not have.
3. Does adopting ISO 5725 vocabulary in the spec help or overclaim? Using the words correctly is
   free; implying conformance to the standard is not.
