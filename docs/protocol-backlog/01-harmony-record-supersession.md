# Backlog: HarmonyRecord supersession — the docs promise it, the code has no mechanism

**Status:** Open. **Category: 🟠 expensive after the next network break.** **Needs the rebuild window: yes.**
**Raised by:** Ceri, 2026-08-22, asking why a researcher who fixes their methodology and is then
successfully reproduced cannot have that reflected.
**Related:** 02 (same integrity-zome change, should be scoped together), 03 (the doc contradiction
this sits underneath).

## Problem

A researcher fails validation. They revise their methodology. Independent validators now reproduce
the work. **There is currently no way to connect the second outcome to the first.**

The two HarmonyRecords exist as unrelated entries. Nothing says one supersedes the other, nothing
points from the failure to the correction, and a reader arriving at the first record has no way to
discover that the story continued.

## The design question is already settled, and correctly

The obvious-looking fix is to make HarmonyRecords updatable. **It must not be done that way.**

If a HarmonyRecord can be edited, the fact that the first attempt failed can be made to disappear.
That is precisely the power the commit-reveal protocol removes at the validation layer, handed
back at the governance layer. The value of the whole system is that no party can change their
claim after the fact.

**Ceri's own framing, 2026-08-22, and it is the right one:** the failed attempt *"shouldn't be
deleted, but part of the progress from failure to success"*. That is a chain of immutable entries
read as one record — not a mutable entry.

## What the code actually does

`governance_integrity/src/lib.rs:433`:

```rust
// --- Immutability: block updates to HarmonyRecord ---
FlatOp::Update(OpUpdate::Entry {
    app_entry: EntryTypes::HarmonyRecord(_), ..
}) => Ok(ValidateCallbackResult::Invalid(
    "HarmonyRecord is immutable — the public record cannot be changed".into(),
)),
```

No production coordinator exposes any update or delete for it. The only delete in the governance
coordinator is `test_force_delete_entry` (`:1371`), compiled solely under `--features test_utils`
and scanned for by `check-no-test-hooks.sh` in CI so it cannot ship.

**The code is right. Do not weaken this guard.**

## What is missing

The governance DNA has three link types (`governance_integrity/src/lib.rs:195`):
`RequestToHarmonyRecord`, `StudyToBadge`, `AllDecisions`.

**There is no supersession link**, and `grep -i "supersed|annotat|retract"` across all four DNAs
returns nothing for HarmonyRecord. The mechanism the docs describe was never built.

## What the docs already say — and they are ahead of the code

`docs/1_ValiChord_Vision&Architecture.md:125`:

> *"…the Harmony Record can be annotated and, if necessary, **superseded**. **The original record
> remains visible; corrections are appended.**"*

That is append-only supersession, and it is compatible with immutability — it *requires* it.
`docs/2_ValiChord_Governance_Framework.md:456` sets out the legitimate grounds for superseding.

So this is not a new idea needing justification. It is a designed feature that was documented and
never implemented.

## ⭐ Ceri's position, 2026-08-22 — and the one place it needs a guard

> *"Logically, a researcher whose research failed to replicate would likely name his updated attempt
> as a new experiment with a new Harmony record, which is absolutely fine. It would be his/her
> responsibility to point people to the more up to date Harmony record."*

**The first half is right and simplifies this considerably.** A revised methodology genuinely *is*
a new experiment. Forcing every re-attempt into a formal chain would assert a continuity that often
is not there, and the protocol should not invent structure the science does not have.

**The second half is the assumption ValiChord exists to remove.** *"It would be his/her
responsibility to point people to the more up to date record"* relies on the interested party
volunteering information. A researcher whose first attempt failed has the **weakest possible
incentive** to point anyone at that failure.

And note which direction actually matters. The problem is **not** someone failing to advertise
their success — they have every reason to. The problem is someone arriving at the successful
record with **no way to learn there was an earlier failure**. So:

| Direction | Who wants it recorded | Survives bad incentives? |
|---|---|---|
| old → new (*"a better version exists"*) | The person who wants the old one forgotten | ❌ No |
| **new → old** (*"this supersedes that"*) | Nobody, voluntarily | ✅ Only if a third party can assert it |

**This narrows the design question to one thing: who may assert supersession?** If only the
researcher may, the link exists precisely when it does not matter. If validators or governance may
also assert it, it survives the incentive that would otherwise suppress it. Note this cannot be
*enforced* either way — like everything else crossing this boundary it is **asserted, not
observed** (`spec/conformance.md` §3.17–18). What the protocol can offer is that once asserted,
it is permanent and cannot be quietly withdrawn.

## Open

- **Link direction and shape.** A `SupersededBy` link from old to new, a `Supersedes` link from
  new to old, or both? One direction is cheaper; two make both reads O(1).
- **Should the reason be on-chain?** Grounds for supersession are enumerated in the governance
  framework. A typed reason makes the record self-describing; a free-text one repeats the `meta`
  trap in a new place.
- **Should supersession be authorised, and by whom?** A researcher superseding their own failure
  unilaterally is not obviously right. The governance framework has decision machinery
  (`GovernanceDecision`) that may already be the answer.
- **What does a reader see?** If "the record" becomes the chain, the read path and any published
  URL need to return the chain, not the head. This is the part that makes the feature real, and it
  is coordinator-side, so it is cheap.

## Not open

- HarmonyRecord entries stay immutable. Not negotiable — see above.
- The failed attempt stays visible. It is evidence, and its disappearance is the failure mode.
