# Backlog: the governance framework promises erasure the architecture cannot perform

**Status:** Open. **Category: 🔴 permanently uncorrectable, in the most literal sense** — anything already written cannot be unwritten.
**Needs the rebuild window: unclear, and that is part of the problem.**
**Found:** 2026-08-22, while fixing item 03. Not raised by anyone; surfaced from reading
`2_ValiChord_Governance_Framework.md` §456 against the code.
**⚠️ Not legal advice.** This records a mismatch between two of our own documents and our own code.

## Problem

`docs/2_ValiChord_Governance_Framework.md` lists three legitimate grounds for retracting or
superseding a HarmonyRecord. The third:

> *"**Legal obligation:** a court order or GDPR right-to-erasure claim… This is a data minimisation
> action, not a retraction of the record."*

**The system cannot do this.**

- `governance_integrity` rejects every update to a `HarmonyRecord`, and no production coordinator
  exposes a delete.
- Even with the guard removed, **a delete on a DHT is a tombstone, not an erasure.** It marks the
  data as deleted for peers who honour the marker. Peers already holding it are not compelled to
  forget, and there is no mechanism to make them.
- DNA 4 is public. The set of peers holding a record is not enumerable, so compliance is not even
  measurable.

So the document commits, in writing, to a capability that does not exist and cannot be added by
ordinary means.

## Why this is not simply a bug to fix

This is a real and contested problem for immutable distributed records in general, not a ValiChord
oversight. Every append-only public system faces it. There is no consensus answer, and inventing
one in a footnote would be worse than naming the gap.

It also interacts with something ValiChord otherwise does *well*: `researcher_repository` is
private and single-agent precisely so personal data never reaches the shared network — the claim
that data locality is *"an architectural guarantee, not a policy commitment"*
(`1_ValiChord_Vision&Architecture.md`). That claim holds for research data. **The question is
whether a HarmonyRecord itself can contain personal data**, and today it can: it carries
`participating_validators`, a list of agent public keys.

## What actually needs deciding

- **Does a HarmonyRecord contain personal data at all?** An agent public key is a pseudonymous
  identifier. Whether that is personal data depends on whether it is linkable to a person —
  and ValiChord's credentialing deliberately links validators to real institutions. This is the
  question everything else depends on and it is not a technical one.
- **If it does, what is the honest commitment?** Options run from *design so that no personal data
  ever enters DNA 4* (the architectural answer, consistent with the rest of the project) through to
  *state plainly that records are permanent and that this is a known limitation* (the honest answer
  if the first is not achievable).
- **What does the governance document say in the meantime?** Currently it promises something
  undeliverable. That is the immediate exposure and it is worse than saying nothing.
- ⚠️ **Does this interact with the rebuild window?** If the answer involves changing what a
  HarmonyRecord *contains* — for example holding validator identity as a salted commitment rather
  than a raw public key — then it is 🟠 and belongs in the same break as 01 and 02. **Nobody has
  checked.** That check is cheap and should happen before the rebuild is scheduled.

## What was done on 2026-08-22

Only the flag. The governance document now carries a note beside the claim saying the capability is
unmet, with a pointer here. **The claim was not deleted**, because the intent may be right and
deleting it would hide the problem rather than record it.

## Not decided

Everything. This item exists to stop the gap being forgotten, not to propose an answer.
