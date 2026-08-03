# Honest-record scoping — should `HarmonyRecord` say how many validators were *asked*?

**Status: SCOPING ONLY. Nothing here is implemented.** Written 2026-08-03 so the decision in
`PROJECT_STATUS.md` → "THE NEXT STEP" item 3 can be taken on facts rather than on a summary.

**The decision is one thing:** take this now, while the 0.7 migration is already breaking every
DNA hash, or accept that taking it later costs a *second* break. It is not a question of whether
the change is desirable.

---

## 1. The problem, plainly

A `HarmonyRecord` is the protocol's permanent public output. Today it records **who took part**
and nothing about **how many were asked**:

```rust
pub struct HarmonyRecord {
    pub request_ref:              ExternalHash,
    pub outcome:                  AttestationOutcome,
    pub agreement_level:          AgreementLevel,
    pub participating_validators: Vec<AgentPubKey>,   // ← who reported
    pub validator_types:          Vec<Option<ValidatorAgentType>>,
    pub validation_duration_secs: u64,
    pub discipline:               Discipline,
}
```

The requested cohort size (`num_validators_required`) lives on the `ValidationRequest`, in a
**different DNA**. So a record reading *"Reproduced / ExactMatch / 5 validators"* is ambiguous:

| What actually happened | What the record says |
|---|---|
| 5 validators asked, 5 reported — **complete** | Reproduced / ExactMatch / 5 |
| 7 validators asked, 5 reported — **incomplete** | Reproduced / ExactMatch / 5 |

Identical. And because a `HarmonyRecord` is immutable, the second case is wrong **forever**.

## 2. How a short record gets written at all

`check_and_create_harmony_record` **cannot** write one — its gate requires the full requested
count. `force_finalize_round` is the only lower-threshold path, and the scheduled hourly sweep is
its only automatic caller.

⚠️ **This is not theoretical.** It is exactly what produced `left: 5, right: 7` on the `v0.7.0`
head, and `left: 6, right: 7` before that.

`fd56cc41` (the liveness gate, on this branch) narrowed the window — force-finalisation now
refuses while any claim on the study is still live. **It did not close it.** A round whose
validators claimed and then released, or never claimed at all, can still finalise short.

## 3. The proposed change — one field

```rust
    /// How many validators the ValidationRequest asked for, captured at
    /// finalisation. `0` = unknown (records written before this field existed).
    #[serde(default)]
    pub validators_requested: u32,
```

That is the whole change to the entry. A reader can then see **5 of 7** rather than **5**.

`#[serde(default)]` is the pattern already used for `validator_types`, so old records still
deserialise — though in practice the 0.7 hash break destroys all existing records anyway.

## 4. ⚠️ What this does NOT do — read before deciding

**It is a disclosure improvement, not an enforcement one.** `validate()` cannot make cross-DNA
calls, which the integrity zome already documents at `governance_integrity/src/lib.rs:229` as the
reason `participating_validators` "cannot be cryptographically checked here". The same limit
applies to the new field: **the author asserts it, and the integrity zome cannot verify it.**

A dishonest finaliser could write `validators_requested: 5` for a 7-validator study and the guard
would accept it.

Three things make that less bad than it sounds, and they should be weighed rather than waved away:

1. **The authoritative source stays public and immutable.** The `ValidationRequest` in DNA 3
   carries the real `num_validators_required`. Anyone can check. The new field makes incompleteness
   visible *by default* instead of only to someone who goes looking.
2. **The coordinator *can* verify it**, because coordinators may make cross-DNA calls. That check
   would be advisory rather than enforced — but it closes the accidental case, which is the one
   that actually happens. The malicious case is not currently addressed for
   `participating_validators` either.
3. **The badge is already honest.** `badge_ceiling()` keys on the number who *participated*, so a
   7-validator round that finalises with 5 yields Silver, not Gold. The badge already degrades
   correctly. **The dishonesty is in the record's narrative, not in the award.** This materially
   shrinks the problem — and is the strongest argument for deferring.

## 5. Cost

| Piece | Hash-breaking? | Notes |
|---|---|---|
| The `HarmonyRecord` field | 🔴 **YES** | Integrity zome — this is the whole reason to ride the 0.7 break |
| Populating it in `write_harmony_record` / `force_finalize_round` | 🟢 No | Coordinator — hot-swaps onto live nodes |
| Optional coordinator cross-check against DNA 3 | 🟢 No | Coordinator |
| UI display ("5 of 7") | 🟢 No | Frontend |

**Only the first row is expensive, and it is expensive only once.** Taken now it is free — the
0.7 migration already changes every DNA hash and kills every published record URL. Taken later it
costs a second break, and a second round of dead URLs.

This is the same reasoning already applied to `DataLocalityMode` in `171b7042`, which was banked
as unreachable groundwork for exactly this purpose.

## 6. Work involved

Small, and mostly mechanical:

- `governance_integrity` — one field, plus a validation rule if we want
  `participating_validators.len() <= validators_requested` enforced (cheap, catches the accidental
  case, and needs no cross-DNA call).
- `governance_coordinator` — populate at both write sites; `force_finalize_round` already fetches
  the `ValidationRequest`, so the value is in hand.
- **Consumers to update** (all found by grep, none surprising):
  `valichord-ui/src/lib/types.ts:212`, `GovernanceView.svelte:83,253`,
  `demo/researcher-node.mjs:292`, and the governance sweettests that construct or read a record.
- **Repack + rerun**: the governance sweettest suite (~130 min in CI) and the tripwires.

## 7. Options

| | Take it now | Defer it |
|---|---|---|
| **Cost** | Delays the merge by roughly a day of work and a CI cycle | Free today |
| **Later cost** | None | A second DNA-hash break, killing every published record URL a second time |
| **Risk** | New protocol code on a branch that is otherwise finished — the sequencing rule says get green first, *then* build on top | The record stays ambiguous for as long as it takes |

**Recommendation: take it now, but only after this branch is green and merged into `v0.7.0`.**
The branch's own history is the argument — Phase A was made green *before* the bundle binding went
on top, precisely so a failure could be attributed to one or the other. Landing this on a red or
unverified branch throws that away.

**The honest counter-argument, which is not weak:** the badge already degrades correctly
(§4.3), so the practical harm is a misleading *narrative* rather than a wrong *award* — and
`fd56cc41` has already narrowed how often a short record can be written at all. If the merge
matters more than the field, deferring is defensible. It is a second hash break, not a broken
protocol.

## 8. What I would need from you

Only the choice. If it is "take it now", the sequencing is: finish verifying this branch → merge
to `v0.7.0` → implement there as its own commit → rerun governance + tripwires → then the merge
decision for `main`.
