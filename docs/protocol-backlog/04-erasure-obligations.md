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

## ✅ THE CHECK — DONE 2026-08-22. Answer: **yes, conditionally, and the condition is a product decision.**

The question was whether any answer here changes what a `HarmonyRecord` or `ValidatorReputation`
*contains*. Traced through the code. Three separate answers, and they differ.

### 1. `person_key` — the sharpest exposure is already inert. 🟢 No action.

`ValidatorReputation.person_key` is constructed **`None` in both places it is written**
(`governance_coordinator/src/lib.rs:1057` and `:1126`) and **read nowhere in any DNA**. The
explicit agent→person link that looked like the worst of this is dead weight: written empty,
never consumed.

Nothing to do, and nothing to pay for. Removing the field would itself be an integrity change, so
**leave it as an always-`None` `Option` and document why.**

⚠️ **But there is a live footgun next door.** `ValidatorProfile.person_key` in DNA 1 *is*
settable, through `UpdateValidatorProfileInput`, and `ValidatorProfile` carries no
`visibility = "private"` attribute — so it is **public**. A validator can therefore publish a
permanent public link from their validator agent to a person key. Self-inflicted, but nothing warns
them. That is guidance and UI (🟢), not a schema problem.

### 2. `participating_validators` — 🔴 cannot be anonymised without redesigning two security guards

This is the finding. It is **not merely** an entry-shape change.

`governance_integrity/src/lib.rs:253` — the anti-forgery guard:

```rust
if !record.participating_validators.contains(action.author()) {
    return Invalid("HarmonyRecord author must be listed in participating_validators —
                    only validators who participated in the round may write the record");
}
```

**`validate()` compares the list against `action.author()`, the signed and unforgeable author of
the entry.** If the list held salted commitments, validate() could not perform this check *at all*
— it would need the salt, and the salt being private is the entire point. The guard does not get
harder; it becomes impossible.

Directly beneath it, the duplicate guard:

```rust
let unique_count = record.participating_validators.iter()
    .collect::<HashSet<_>>().len();
if unique_count < record.participating_validators.len() { return Invalid(...) }
```

Its stated purpose: *"a fabricated list cannot pad the validator count past a badge threshold by
repeating a single real key."* **Per-record salted commitments break this too** — one validator
could appear twice under two salts and the set would see two distinct values. A deterministic
commitment would preserve dedup, but a commitment everyone can recompute is not erasable, which
defeats the purpose.

**So anonymising validators in HarmonyRecords is 🟠 *and* a security redesign.** The two guards
would need replacing, not porting. That is a substantially bigger job than "change a field type",
and it is exactly the kind of thing that must not be discovered halfway through a rebuild.

*(The other two checks on this field — the parallel-length check on `validator_types` and the
quorum count — only use `.len()` and are indifferent to what the elements are.)*

### 3. `ValidatorReputation` — the real ongoing exposure, and it is a product decision. 🟠 or 🟢

`update_validator_reputation` is a live production coordinator function, so the profile
— `total_validations`, `successful_validations`, `agreement_rate`, `avg_time_secs`, `tier`,
keyed by `validator: AgentPubKey` — is being written for real.

- **Stop writing it:** coordinator-only, 🟢, no break needed. Costs you the reputation system.
- **Change its shape:** integrity change, 🟠, same break as 01 and 02.
- **Keep it as is:** free, and the exposure stands.

## ⭐ What this actually reduces to — one question, and it is not technical

> **Do you want validator identity on the permanent public record, yes or no?**

**If yes** — nothing here needs the window. Document the position honestly, fix the governance
document's erasure claim (04's original point), add the `ValidatorProfile.person_key` warning, and
move on. All 🟢.

**If no, or if unsure** — it needs the window, and it needs more than the window: two anti-forgery
guards must be redesigned before anything is written. **That work cannot start during a rebuild;
it has to be settled first.**

⚠️ The cost of deciding *late* is real: a second network break plus a security redesign under
time pressure.

> ### 🛑 But do not decide early to avoid that. Ceri, 2026-08-22.
>
> **"There is no rush to solve this."** And the reason is better than the urgency argument above,
> which was mine and which I withdraw as a recommendation.
>
> **This is not ValiChord's decision to take alone.** Nondominium will likely run **human**
> validators, and when they do, the answer is substantially theirs. Taking it now, in their absence,
> would be deciding for a stakeholder who is not in the room — and **deciding early and wrong is
> worse than deciding late.** The whole cost of getting it wrong is that it cannot be changed.
>
> His honest position, in his own words, and it is the correct one to hold: **"I don't know."**

## 📍 OPEN QUESTIONS — recorded, not answered

The question underneath everything above, as Ceri put it on 2026-08-22:

> **"Does being a Validator mean that you, by definition, lose the right of anonymity?"**

Nobody here has answered it and nothing below is an answer. This section exists so the shape of
the question survives the conversation that produced it.

### The reframe that makes it tractable

**The check and the publication are already separate layers**, and conflating them is what makes
the question feel forced.

- **Independence is verified at claim time**, in the attestation DNA — the conflict-of-interest
  guard, the credential, the institution comparison. That machinery *needs* to know who someone is.
- **The HarmonyRecord is a publication**, in the governance DNA, written afterwards.

So *"identity is needed to check independence"* does **not** imply *"identity must appear in the
published record."* The real question is narrower: **must the publication name them, given the
checks happen elsewhere?**

### Arguments that it must

- **Auditability.** *"Trust us, N independent people agreed"* is precisely the kind of
  unverifiable claim ValiChord exists to eliminate. A third party who cannot see who validated is
  taking the protocol's word for it.
- **Accountability.** Warrants and reputation have to attach to someone. Fabricated attestations
  need a bearer.
- **Collusion detection.** The longitudinal audit works by looking at patterns across rounds, which
  needs continuity of identity.

### Arguments that it must not

- **Traditional peer review is anonymous.** Reviewers are overwhelmingly not named. **ValiChord is
  currently more exposing than the system it sets out to improve on**, which is worth sitting with.
- **Retaliation and chilling effects.** A junior researcher validating a senior figure's work and
  finding it does not reproduce is *exactly* the case where naming them suppresses the finding —
  and exactly the case the protocol most needs to work.
- **What the record needs to establish** is that N independent parties agreed, not who they were.
  Independence can be attested by a credential issuer without publishing identity.

### Questions nobody has asked yet

- **Is anonymity even achievable here, or only pseudonymity?** Agreement patterns and timing are
  distinctive. A persistent pseudonym across enough rounds may re-identify regardless of what the
  field contains — which would make the whole question partly moot, and that is worth establishing
  *before* paying for a redesign.
- **Is this one answer or many?** 🆕 Different deployments may answer differently and reasonably.
  A Nondominium commons, whose whole model is transparent contribution accounting, may **want**
  named validators. A medical-research network may need the opposite. ValiChord already runs
  separate networks per deployment, so this could be a **DNA property** like
  `min_attestations_for_finalization` rather than a global answer.
  ⚠️ This does not dodge the cost — supporting both modes still means the security redesign in
  §2 above. But it removes the need for one universal answer, which is the part currently blocked.
- **Who decides for a given network — and can validators consent?** If a validator knows at
  credentialing time that their participation is permanently public, that is a materially different
  proposition from discovering it later.

### What to do meanwhile

Nothing, deliberately. The two 🟢 items stand on their own and need no answer here: fix the
governance document's unmet erasure claim (the original point of this item), and warn about
`ValidatorProfile.person_key`.

**Raise it with Nondominium when the time comes**, since human validators make it concrete for
them, and it is more their decision than ours.

## What was done on 2026-08-22

The flag only. The governance document carries a note beside the claim saying the capability is
unmet, pointing here. **The claim was not deleted** — the intent may be right, and deleting it
would hide the problem rather than record it.
