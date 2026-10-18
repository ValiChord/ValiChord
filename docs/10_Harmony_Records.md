<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Harmony%20Records.jpeg" width="800" alt="Harmony Record">
</div>

> ⚠️ **The image above is an illustrative mock-up**, not a real record (real Holochain hashes start `uhC…`, and the duration field is the longest single validator's time, not a total). How a record is actually created and checked: [one round](DIAGRAMS.md#2-one-validation-round-end-to-end) and [what enforces what](DIAGRAMS.md#3-what-enforces-what).

# Harmony Records: The Permanent Verdict of Science

**ValiChord's core output — and why it matters**

---

## What Is a Harmony Record?

A Harmony Record is the permanent, tamper-proof output of a completed ValiChord validation round. It is the answer to the question: *"Did independent validators agree on whether this computational study reproduces?"*

But it is more than a simple yes or no. A Harmony Record preserves the **full texture** of what happened — who validated, what they found, how closely they agreed, and how long it took. It replaces the binary "Pass/Fail" verdict with a structured, permanent, publicly readable account of the validation event.

Once written to the public DHT (Distributed Hash Table), a Harmony Record **cannot be altered or deleted** — not by the researchers whose work was validated, not by the validators who participated, and not by ValiChord's own operators. It is carved in stone.

---

## What Does a Harmony Record Contain?

```rust
HarmonyRecord {
    request_ref:              ExternalHash,       // identifies the study validated
    outcome:                  AttestationOutcome, // the majority finding
    agreement_level:          AgreementLevel,     // how many validators reproduced it (see below)
    participating_validators: Vec<AgentPubKey>,   // who validated
    validator_types:          Vec<Option<ValidatorAgentType>>, // person / institution / automated tool
    validation_duration_secs: u64,                // longest time any one validator spent
    discipline:               Discipline,         // scientific domain
    validators_requested:     u32,                // how many were asked for — so "5 of 7" is visible
    attestation_evidence:     Vec<AttestationEvidence>, // each validator's own signed findings
}
// No timestamp field: the time the record was written comes from Holochain's own action timestamp.
```

(Checked against `governance_integrity` and `shared_types` on 2026-10-18.)

### Outcome

The majority finding across all validators (the most common answer; a tie goes to the more positive outcome). One of:

| Outcome | Meaning |
|---|---|
| `Reproduced` | Validators got the same result as the researcher. This does **not** mean the result is correct. |
| `PartiallyReproduced` | Results partially matched — some findings confirmed, others not |
| `FailedToReproduce` | Reproduction was attempted but did not give the researcher's result |
| `UnableToAssess` | The study could not be assessed (e.g. inaccessible data, missing dependencies) |

### Agreement Level

Despite its name, the agreement level in the code measures **what share of validators reproduced the result** (`derive_agreement_level` in `shared_types`):

| Agreement Level | Rule in the code today |
|---|---|
| `ExactMatch` | At least 90% of validators fully reproduced it |
| `WithinTolerance` | At least 70% reproduced it fully or partially |
| `DirectionalMatch` | At least 50% reproduced it fully or partially |
| `Divergent` | Some, but fewer than half, reproduced it |
| `UnableToAssess` | None reproduced it, fully or partially |

These cutoffs (90% / 70% / 50%) are placeholders, to be calibrated with real data.

> **Design intention, not yet built.** The original idea was an agreement level that is *independent* of whether the study reproduced: three validators who all independently fail to reproduce a study have agreed perfectly, and that is a clear finding — very different from validators who disagree with each other, which suggests reproducibility depends on validator-specific factors (domain expertise, computational environment, interpretation of methods). **The code does not do this yet.** Today, three unanimous failures give `UnableToAssess`, and a split gives `Divergent` or `DirectionalMatch`. Each validator's own signed finding is carried in the record, so the true pattern can still be read from it.

---

## Why "Harmony"?

The name is deliberate. A Harmony Record does not demand unanimity — it documents the actual pattern of agreement and disagreement among validators, the way musical harmony captures the relationship between voices rather than requiring them to sing in unison.

Where validators diverge, the divergence is recorded in full. Where they agree, the agreement is documented with precision. The record replaces the false binary of "reproducible / not reproducible" with an honest account of what a group of independent experts actually found.

This matters because reproducibility is not always a clean binary. A computational study might:
- Reproduce exactly on one platform but not another
- Produce results directionally consistent with the paper but numerically different
- Partially reproduce — some figures confirmed, others not
- Be impossible to assess due to missing dependencies, not due to errors in the work

A Harmony Record captures all of these situations accurately. A simple pass/fail verdict does not.

---

## How Is a Harmony Record Created?

Harmony Records are assembled automatically by ValiChord's Governance DNA (DNA 4) once all validators in a round have submitted their public attestations. The process is:

1. **Validation request submitted** — a researcher submits a study for validation via DNA 3 (Attestation)
2. **Validators commit** — each assigned validator seals their private assessment in their own DNA 2 (Validator Workspace). A cryptographic commitment anchor is written to the shared network — proving the commitment happened without revealing the outcome
3. **Phase opens** — once all validators have committed, a PhaseMarker is written to the network, opening the reveal window simultaneously for all validators
4. **Validators reveal** — each validator publishes their full public attestation to DNA 3. These are permanent and immutable once submitted
5. **Harmony Record assembled** — DNA 4's coordinator detects the completed round, retrieves all attestations, calculates the majority outcome and agreement level, and writes the Harmony Record to the public DHT. If some validators never reveal, the round can be closed after a timeout (7 days by default) with fewer attestations — but not while any validator still holds a claim on the study — and the record then shows "k of n"
6. **Badge issued** — depending on the outcome and validator count, a Reproducibility Badge may be issued alongside the Harmony Record

The entire process — from commitment to Harmony Record — is cryptographically enforced. No human administrator assembles or approves the record. The network does it.

---

## Reproducibility Badges

When a Harmony Record meets the threshold conditions, ValiChord automatically issues a Reproducibility Badge. Badges are permanent, publicly readable, and linked to the Harmony Record that generated them.

| Badge | Threshold | Requirement |
|---|---|---|
| 🥇 **Gold Reproducible** | ≥ 7 validators | ExactMatch |
| 🥈 **Silver Reproducible** | ≥ 5 validators | ExactMatch or WithinTolerance |
| 🥉 **Bronze Reproducible** | ≥ 3 validators | ExactMatch, WithinTolerance or DirectionalMatch |
| ❌ **Failed Reproduction** | ≥ 3 validators | Divergent or UnableToAssess |

(From `evaluate_badge` in `shared_types`, checked 2026-10-18. The validator count is the number who actually took part. The numbers 7 / 5 / 3 are placeholders, to be calibrated with real data — they are not statistically justified.)

Badges are designed to be meaningful at scale — queryable by journals, funders, and institutions via an HTTP Gateway without requiring any Holochain infrastructure. *(The gateway is not deployed today; the public demo serves records through its own web bridge.)*

### Tier semantics — preferred direction (deferred to v2 or later)

The Gold/Silver/Bronze tier definitions above are working placeholders. The intended evolution is toward a **statistical-confidence interpretation**: the tier reflects both the number of validators that participated *and* the strength of their convergence, gated by confidence-interval (or Bayesian credible-interval) bounds on the underlying reproduction rate.

Sketch of the intended logic (numbers indicative, not final):

| Tier | Criterion sketch |
|---|---|
| **Gold** | N ≥ 20, agreement ≥ 95%, 95% CI lower bound ≥ 0.80 |
| **Silver** | N ≥ 12, agreement ≥ 90%, 95% CI lower bound ≥ 0.65 |
| **Bronze** | N ≥ 5, agreement ≥ 75%, 95% CI lower bound ≥ 0.40 |
| **Sub-tier outcomes** *(proposed — none of these exist in the code)* | InsufficientData (CI too wide), PartialAgreement (diffuse split), InformativeSplit (bimodal — distinct clusters detected) |

Rationale: a study with N=20 and 19/20 agreement carries materially more statistical weight than N=5 and 5/5 agreement, even though the second is "unanimous". Tier should communicate the strength of the evidence, not just one input to it.

Implementation deferred pending:
- Adapter work surfacing real validator-count distributions
- Statistical-method choice (Wilson, Clopper-Pearson, or Bayesian Beta-Binomial)
- Decision on whether HarmonyRecord schema exposes CI bounds directly to consumers

Tracked as an open design question for v2 or later.

---

## Who Can Read a Harmony Record?

Anyone. No Holochain node required.

Harmony Records live on DNA 4's public DHT, which is designed to be served through an HTTP Gateway. *(That gateway is not deployed today; the public demo serves records through its own web bridge.)* A journal editor, a funder, a research institution, or a member of the public can query the status of any study directly via a standard web request. The data is structured, machine-readable, and permanent.

This is by design. ValiChord's public layer is not gated behind institutional membership, subscription fees, or specialist software. If a study has been validated, its Harmony Record is publicly accessible.

---

## Why Can't a Harmony Record Be Changed?

Three layers of protection make Harmony Records immutable:

**1. Holochain validation rules** — the integrity zome's `validate()` callback rejects all updates and deletes of `HarmonyRecord` entries.

### 📌 "Harmony Record" means two different things — read this before the rest

Most of the confusion in this project's own documents comes from one word doing two jobs.

| | What it is | Can it change? |
|---|---|---|
| **The entry** | One thing written to the network by `write_harmony_record` | **Never.** `validate()` rejects every update and delete. |
| **The record** | What a reader is shown, which may be a **chain** of entries | **Yes — by appending.** Nothing is edited; new entries are added and linked. |

*"Harmony Records are living documents"* is **false of the entry** and **true of the record**.
Both claims appear in these docs and neither says which sense it means.

**Immutability is not a limitation to be worked around — it is the guarantee.** A record whose
entries could be edited is a record whose failures could be removed, which hands back at the
governance layer exactly the power commit-reveal removes at the validation layer. A researcher
whose first attempt failed has the weakest possible incentive to keep that visible.

⚠️ **The chain does not exist yet.** Supersession is the intended design and is **not
implemented**: the governance DNA has six link types and none of them connects one HarmonyRecord
to another. Until it is built, each entry stands alone. See
[`protocol-backlog/01-harmony-record-supersession.md`](protocol-backlog/01-harmony-record-supersession.md).

> ⚠️ **This sentence is correct and two other documents contradict it.** `1_ValiChord_Vision&Architecture.md` and `2_ValiChord_Governance_Framework.md` describe Harmony Records as *"living documents"* that are *"updated"*, and one makes displaying a `last_updated` field a licence condition — a field that does not exist. The entry is immutable; the *record* grows by supersession, and the supersession mechanism is **not yet built**. Full account and fix in [`protocol-backlog/03-docs-contradict-code-on-mutability.md`](protocol-backlog/03-docs-contradict-code-on-mutability.md). Every peer on the network independently validates every operation — there is no central server to compromise.

**2. Evidence checked by every peer** — only a validator who took part in the round can write its Harmony Record, and the record must carry every listed validator's own signed attestation. Every peer checks those signatures and recomputes the outcome, agreement level and cohort size from them (since PR #47, October 2026). So nobody can list validators who never took part, or state a result their attestations do not support. (An earlier design used a single `harmony_record_creator_key`; it was removed.) What this cannot catch: validators who collude and each sign a false finding.

**3. Distributed storage** — the record exists across every peer on the Governance DHT simultaneously. There is no single copy to alter, no database to hack, no administrator to pressure.

A Harmony Record, once written, is as permanent as the network itself.

---

## What Harmony Records Are Not

**They are not peer review.** ValiChord validates computational reproducibility — whether the code and data produce the results as described. It does not assess whether the methodology is sound, whether the conclusions are justified, or whether the study is significant. That is peer review's job. ValiChord is a complement to peer review, not a replacement.

**They are not guarantees of correctness.** A study that reproduces is not necessarily correct — it may contain systematic errors that reproduce consistently. ValiChord confirms that independent validators, following the documented methods, obtained the same results. What those results mean scientifically is a separate question.

**They are not punitive.** A Failed Reproduction badge is not an accusation of fraud. Many studies fail to reproduce for reasons unrelated to the original researchers' conduct — undocumented dependencies, platform differences, incomplete environment specifications. ValiChord records what happened; it does not assign blame.

---

## Harmony Records in Context

Harmony Records are the public-facing output of a system designed to be structurally resistant to manipulation. The blind commit-reveal protocol ensures validators cannot see each other's findings before submitting their own. The credentialed membrane, checked by every peer, ensures only validators holding a credential from an authorised issuer participate. The immutability guarantees ensure the record cannot be altered after the fact.

The result is a verification instrument that funders, journals, institutions, and the public can trust — not because they trust ValiChord's operators, but because the architecture makes corruption structurally difficult.

---

*For the full governance framework, including how the system resists institutional capture, see [ValiChord Governance Framework](2_ValiChord_Governance_Framework.md).*

*For the technical implementation of Harmony Records in DNA 4, see [Technical Architecture](7_ValiChord_4-DNA_architecture_technical.md).*

*Governance preprint: [10.5281/zenodo.18878108](https://doi.org/10.5281/zenodo.18878108)*
