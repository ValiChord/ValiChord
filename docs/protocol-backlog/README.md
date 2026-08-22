# Protocol backlog — known gaps in the ValiChord protocol

Candidate changes to the Holochain protocol (`valichord/`). Every item names **who raised it and
when**, so a claim here can be traced rather than inherited.

This is the protocol-side counterpart of `valichord_attestation/spec/format-backlog/`. That
directory exists so gaps in the *format* do not have to be remembered by one person; until
2026-08-22 the *protocol* had no equivalent, which is why the two items below surfaced in
conversation rather than from a list — and would have been lost again.

**Not version-named, on purpose.** `spec/v2-backlog/` closed when its items shipped and nine days
later there was nowhere to record what outside implementers had found. A version-named container
closes. This one does not.

---

## The only triage that matters

ValiChord is unfinished, so the list of missing things is long and always will be. Most of it can
wait indefinitely at no cost. **The question worth asking is not what is missing, but which
absences get more expensive the longer they are left.** Three categories:

| | Category | Cost of waiting |
|---|---|---|
| 🟢 | **Cheap forever** | None. Library fields, docs, tooling, adapters. Add when someone needs it. |
| 🟠 | **Expensive after the next network break** | Anything needing a new entry type or link type. Free if it rides a DNA-hash change that is happening anyway; costs a *second* break if it lands after one. |
| 🔴 | **Permanently uncorrectable** | Anything determining what an immutable record *says*. Records written before the fix stay wrong forever. No later version helps them. |

🟢 items do not belong here unless someone asks for them. **This backlog is for 🟠 and 🔴.**

## ⏳ The rebuild window — why 🟠 has a clock right now

Changing an integrity zome changes the DNA hash, which produces a **separate network**: published
HarmonyRecord URLs die and existing records do not carry over. That is the expensive change, and
it was paid deliberately once already on 2026-08-03 for the Holochain 0.7 migration.

**It is going to be paid again.** Oracle still runs 0.6.2 and needs a full rebuild with state
loss — already accepted, and the pre-0.7 published URLs are already gone (`PROJECT_STATUS.md`).

So there is a window. **A 🟠 item that lands before the Oracle rebuild costs nothing extra. The
same item afterwards costs a second network break.** That is the strongest argument for scoping
🟠 work now — not that any of it is urgent in itself, but that the expensive part is already
scheduled and paying for it twice would be careless.

## What an item here must say

1. Who raised it and when.
2. Its category, and whether it needs the rebuild window.
3. The evidence, with file and line — not a recollection.
4. What is genuinely open, separated from what is already decided.

An item that cannot cite evidence is a conversation, not a backlog item.

## The items

| | Item | Raised by | Category | Needs the window? |
|---|---|---|---|---|
| 01 | HarmonyRecord supersession — no mechanism exists | Ceri, 2026-08-22 | 🟠 | **Yes** |
| 02 | Hardware provenance for researcher and validator | Ceri, 2026-08-22 | 🟠 / 🔴 | **Yes** |
| 03 | Docs and code contradict each other on mutability | Found 2026-08-22 | 🟢 | No — **fixed 2026-08-22** |
| 04 | Erasure obligations — for **validators**, not research subjects | Found 2026-08-22 | 🔴 | ⏸️ **Checked. Deliberately parked** — the underlying question is Nondominium's as much as ours |
| 05 | Three public fields where typed content can expose a research subject | Found 2026-08-22 | 🟢 fix / 🔴 consequence | No |

**01 and 02 both need an integrity-zome change**, so they should be scoped together and land in
the same break rather than separately. **04's check is done and the item is parked on purpose** —
it joins them only if validator identity is to come off the public record, and that question
belongs partly to Nondominium, who will run human validators. Deciding it early, in their absence,
would be worse than paying for it later. 03 is done. 05 is
mostly coordinator-side and needs no break, though two of its stronger options (a numeric metric
type, a declared subject count) would ride the same one if wanted.

> ✅ **Where the erasure question actually landed — read this before worrying about it.**
> Research-subject data **never reaches the shared network**: it lives in a private, single-agent
> DNA, the institution holds and deletes it, and deleting it also settles the status of the hash on
> the network. That was established by listing every public entry type, prompted by Ceri asking
> directly about people named in medical research. **04 was over-scoped when first filed and is now
> narrowed to validators**, whose identity and performance history *are* on a public permanent
> store. 05 covers the residue that architecture cannot reach: what a person types into a free-text
> field.

> 🛑 **A note on urgency, added 2026-08-22.** The rebuild window is a real saving and it is
> worth using — but **"it is cheaper now" is not a reason to decide something badly.** Item 04 was
> written with a recommendation to decide before the rebuild; that recommendation was withdrawn the
> same day, because the question turns out to belong partly to a stakeholder who is not in the room.
> **An item may sit here indefinitely.** The window makes some things cheaper; it does not make any
> of them due.

## ⚠️ The pattern behind these items

**Three of the first four are things the documents describe and the code does not have** — supersession
(01), hardware and software metadata (02), and the temporal-integrity API with its four fields (03).
Item 04 is the same shape and worse: a capability promised that cannot be built by ordinary means.

That is not a criticism of the documents. They were written as design and they are mostly good
design. **But nothing was tracking the distance between them and the code**, so the distance grew
quietly and was only measured when someone asked a direct question. Closing individual gaps matters
less than the fact that this directory now exists to measure them.

🔴 **The practical consequence: do not quote these documents as descriptions of what
ValiChord does.** Several passages describe what it is meant to do. Where it matters — anything
said publicly, to a funder, or to an outside implementer — check the code.

## Also raised, not yet numbered

- **A `meta`-style trap on the protocol side.** The format has one documented case where an
  exclusion from a hash makes two different things compare as identical
  (`spec/format-backlog/README.md`). Nobody has asked whether the protocol has an equivalent —
  a field excluded from a commitment, or from a badge calculation, where the exclusion is
  load-bearing and undocumented. Worth one deliberate look rather than waiting to be surprised.
