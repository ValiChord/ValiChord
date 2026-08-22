# Backlog: the docs and the code contradict each other on whether HarmonyRecords can change

**Status:** Open. **Category: 🟢 cheap forever** — prose only, no DNA change. **Needs the rebuild window: no.**
**Found:** 2026-08-22, when Ceri said he was *"pretty sure that harmony records can be updated"*
and the code turned out to say the opposite. He was right that the docs say so. **Both were right
about different documents.**
**Related:** 01 — the supersession gap sits underneath this and is the reason the contradiction
went unnoticed.

## Problem

Four passages describe HarmonyRecords as mutable. One describes them as immutable. **The code
enforces immutable.** A reader picks up whichever they open first.

**Saying mutable:**

- `docs/1_ValiChord_Vision&Architecture.md:369` — *"the affected Harmony Record is **updated** to
  reflect that finding. Harmony Records are **living documents, versioned and timestamped**"*
- `docs/2_ValiChord_Governance_Framework.md:585` — *"Harmony Records are **living documents**…
  including any post-publication validations, **updates**, or new disagreements"*
- `docs/2_ValiChord_Governance_Framework.md:594` — *"Any display of a Harmony Record that omits the
  **`last_updated` field** violates the API licence."*
- `docs/2_ValiChord_Governance_Framework.md:456` — *"The only legitimate grounds for retracting or
  superseding a HarmonyRecord are…"* (this one is defensible — see below)

**Saying immutable:**

- `docs/10_Harmony_Records.md:144` — *"the integrity zome's `validate()` callback rejects all
  updates and deletes of `HarmonyRecord` entries"*

**The code:** `governance_integrity/src/lib.rs:433` rejects updates with
*"HarmonyRecord is immutable — the public record cannot be changed"*.

## 🆕 There is no `last_updated` field

`HarmonyRecord` has eight fields and that is not one of them. **A licence condition requires
displaying a field that has never existed**, which means any integrator who implemented the licence
literally could not comply, and any who did comply were displaying something invented.

This is the sharpest part of the finding and the easiest to fix.

## The resolution: "record" means two different things

The contradiction is largely linguistic, and naming it fixes most of the prose.

| | Meaning | Mutable? |
|---|---|---|
| **The entry** | One thing written to the DHT | **Never.** Enforced by `validate()`. |
| **The record** | What a reader is shown — potentially a *chain* of entries | **Yes**, by appending. |

*"Harmony Records are living documents"* is **false of the entry** and **true of the record**.
Both statements in the docs are defensible; neither says which sense it means.

`1_ValiChord_Vision&Architecture.md:125` already has the careful version:

> *"…the Harmony Record can be annotated and, if necessary, superseded. **The original record
> remains visible; corrections are appended.**"*

That is append-only supersession, it is compatible with immutability, and it is what the rest of
the prose should be aligned to.

## Why this is worth fixing rather than shrugging at

Two reasons beyond tidiness.

**It nearly produced a wrong decision.** The conversation that surfaced it was heading toward
"make HarmonyRecords updatable" — which would hand back, at the governance layer, exactly the
power commit-reveal removes at the validation layer. The docs were the evidence for that direction.

**It is the project's own failure mode.** A claim recorded once, repeated until repetition made it
authoritative, contradicted by the artefact it described. That is the pattern `feedback_verify_ai_facts`
exists for, and this instance is about ValiChord's own record rather than someone else's.

## The fix

1. Define the two senses of "record" once, in `docs/10_Harmony_Records.md`, and cross-reference it
   from the other two documents.
2. Rewrite the four mutable-sounding passages in terms of supersession — the entry never changes;
   the record grows.
3. Either add `last_updated` to the licence-relevant API response as a derived value (the timestamp
   of the newest entry in the chain), or **remove the licence clause**. Requiring a field that does
   not exist is worse than requiring nothing.
4. State plainly, next to the immutability guard, *why* it is not a limitation — because a record
   that could be edited could have its failures removed.

## Blocked on nothing

None of this needs a DNA change or the rebuild window. It is prose plus, possibly, one derived
field in a read path.

⚠️ **But do not "fix" the docs by describing supersession as though it works.** It does not — see
01. Until the mechanism exists, the honest wording is that supersession is the intended design and
is not yet implemented.
