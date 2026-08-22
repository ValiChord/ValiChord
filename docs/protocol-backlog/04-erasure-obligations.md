# Backlog: the governance framework promises erasure the architecture cannot perform — for validators

**Status:** Open. **Category: 🔴** — anything already written cannot be unwritten.
**Needs the rebuild window: possibly.** One cheap check settles it; see the end.
**Found:** 2026-08-22, while fixing item 03.
**⚠️ Not legal advice.** This records a mismatch between our own documents and our own code.

> ### 📌 Corrected 2026-08-22, same day it was filed
>
> The first version of this item did not say **whose** personal data was at issue, which made it
> read as though research subjects were exposed. **They are not.** Ceri asked the direct question —
> what about people named in the research, in medical studies — and checking the entry types
> settled it. The scope below is **validators**, and only validators.

## What is NOT a problem — established by reading every public entry type

**Research-subject data never reaches the shared network.** Every public entry in the attestation
DNA was listed and checked. About the research itself, the shared network holds a hash of the data,
a URL pointing at it, aggregate metric values, institution names and timings. **No patient records,
no per-subject rows, no identifiers.**

The data lives in `researcher_repository` — private, single-agent. A hospital or university holds
it and can delete it, which is exactly the GDPR answer, and it holds *by architecture rather than
policy* as `1_ValiChord_Vision&Architecture.md` claims.

🆕 **And deletion at the source resolves the hash too.** A hash of personal data is generally
treated as *pseudonymised* while the source exists, because it could be re-linked. Once the source
is deleted there is nothing left to link to, and the hash becomes a value with no route back to a
person. So the institution's own deletion settles both halves.

*(A hash is still a confirmation oracle — someone holding a candidate dataset can test whether it
matches. For a research dataset that requires already having the data, so it is not a realistic
route to a subject.)*

## What IS the problem: validators

DNA 4 is public and permanent, and it carries this about each validator:

| Field | Where |
|---|---|
| `participating_validators: Vec<AgentPubKey>` | `HarmonyRecord` |
| `validator: AgentPubKey` | `ValidatorReputation` |
| **`person_key: Option<AgentPubKey>`** | `ValidatorReputation`, and `ValidatorProfile` in DNA 1 |
| `total_validations`, `successful_validations`, `agreement_rate`, `avg_time_secs`, `tier` | `ValidatorReputation` |
| `issued_to: AgentPubKey` | `ReproducibilityBadge` |

Read together that is a **permanent, public, longitudinal performance profile of an identified
individual** — how much work they have done, how often they agreed with peers, how fast they work,
and an explicit link from agent to person. Every field has an honest purpose. The aggregate is
personal data, and arguably profiling.

**So the erasure question is a validator question.** The governance framework
(`2_ValiChord_Governance_Framework.md`) lists a GDPR right-to-erasure claim or court order as
legitimate grounds for retracting a HarmonyRecord, and the system cannot honour it:
`validate()` rejects every delete, and even without the guard a DHT delete is a **tombstone, not an
erasure** — peers already holding the data are not compelled to forget, and on a public DHT the set
of holders is not enumerable, so compliance is not even measurable.

## Options, weakest first

**Delete the link rather than the entry — de-indexing.** Makes a record hard to find while leaving
it intact on every peer holding it. Roughly the search-engine "right to be forgotten" shape: real,
sometimes accepted, definitively weaker than erasure. The guard forbids it today, and lifting the
guard would not compel anyone to forget. **Helps discoverability, not existence.**

**Do not put the identity there in the first place — a salted commitment.** Write a value proving
*a specific validator* took part without naming them; hold the salt in the validator's own private
space; **destroy the salt to make the commitment permanently unlinkable.** The public record keeps
the science, the outcome, the count of distinct validators and the badge arithmetic. What
disappears is the ability to say *who*.

This is an established technique for getting erasure semantics from an append-only store. ⚠️
Whether a commitment counts as anonymised or merely pseudonymised is a legal judgement, not a
technical one, and is not settled here.

## ⚠️ The trade-off that cannot be engineered away

**A longitudinal reputation system and erasability are in direct tension.**

*"40 validations, 92% agreement"* requires linking a validator across rounds. And a persistent
pseudonym plus enough rounds is re-identifying anyway — agreement patterns and timing are
distinctive.

So this is partly a product decision, not an architecture problem: **how much reputation depth is
worth how much permanence of an individual's record.** No cleverer design removes it. That question
is Ceri's.

## The cheap check that decides the window

**Does the answer change what a HarmonyRecord or ValidatorReputation *contains*?** If validator
identity becomes a commitment rather than a raw `AgentPubKey`, that is an integrity-zome change —
🟠, and it belongs in the same break as 01 and 02. If the answer is guidance and read-path changes
only, it is 🟢 and can happen any time.

**Nobody has checked. It is an hour's work and it should happen before the rebuild is scheduled.**

## What was done on 2026-08-22

The flag only. The governance document carries a note beside the claim saying the capability is
unmet, pointing here. **The claim was not deleted** — the intent may be right, and deleting it
would hide the problem rather than record it.
