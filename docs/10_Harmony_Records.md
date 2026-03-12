<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Harmony%20Records.jpeg" width="800" alt="Harmony Record">
</div>

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
    outcome:                  AttestationOutcome, // the consensus finding
    agreement_level:          AgreementLevel,     // how closely validators agreed
    participating_validators: Vec<AgentPubKey>,   // who validated
    validation_duration_secs: u64,                // how long the round took
    discipline:               Discipline,         // scientific domain
    created_at_secs:          u64,                // timestamp
}
```

### Outcome

The consensus finding across all validators. One of:

| Outcome | Meaning |
|---|---|
| `Reproduced` | All or majority of validators successfully reproduced the results |
| `PartiallyReproduced` | Results partially matched — some findings confirmed, others not |
| `NotReproduced` | Validators could not reproduce the results |
| `FailedToReproduce` | Reproduction was attempted but failed conclusively |
| `UnableToAssess` | The study could not be assessed (e.g. inaccessible data, missing dependencies) |

### Agreement Level

How closely the validators agreed with each other — independent of whether the study reproduced:

| Agreement Level | Meaning |
|---|---|
| `ExactMatch` | All validators reached identical conclusions |
| `WithinTolerance` | Minor numerical differences within documented variation |
| `DirectionalMatch` | Validators agreed on direction but differed on magnitude |
| `Divergent` | Validators reached materially different conclusions |

This distinction matters. A study where three validators all independently failed to reproduce it (`Reproduced = false`, `AgreementLevel = ExactMatch`) is very different from a study where validators disagreed with each other (`Divergent`) — the first is a clear finding, the second suggests the study's reproducibility may depend on validator-specific factors (domain expertise, computational environment, interpretation of methods).

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
5. **Harmony Record assembled** — DNA 4's coordinator detects the completed round, retrieves all attestations, calculates the consensus outcome and agreement level, and writes the Harmony Record to the public DHT
6. **Badge issued** — depending on the outcome and validator count, a Reproducibility Badge may be issued alongside the Harmony Record

The entire process — from commitment to Harmony Record — is cryptographically enforced. No human administrator assembles or approves the record. The network does it.

---

## Reproducibility Badges

When a Harmony Record meets the threshold conditions, ValiChord automatically issues a Reproducibility Badge. Badges are permanent, publicly readable, and linked to the Harmony Record that generated them.

| Badge | Threshold | Requirement |
|---|---|---|
| 🥇 **Gold Reproducible** | ≥ 7 validators | ExactMatch or WithinTolerance |
| 🥈 **Silver Reproducible** | ≥ 5 validators | ExactMatch or WithinTolerance |
| 🥉 **Bronze Reproducible** | ≥ 3 validators | ExactMatch or WithinTolerance |
| ❌ **Failed Reproduction** | Any count | Majority Divergent or NotReproduced |

Badges are designed to be meaningful at scale — queryable by journals, funders, and institutions via the HTTP Gateway without requiring any Holochain infrastructure.

---

## Who Can Read a Harmony Record?

Anyone. No Holochain node required.

Harmony Records live on DNA 4's public DHT, which exposes an HTTP Gateway. A journal editor, a funder, a research institution, or a member of the public can query the status of any study directly via a standard web request. The data is structured, machine-readable, and permanent.

This is by design. ValiChord's public layer is not gated behind institutional membership, subscription fees, or specialist software. If a study has been validated, its Harmony Record is publicly accessible.

---

## Why Can't a Harmony Record Be Changed?

Three layers of protection make Harmony Records immutable:

**1. Holochain validation rules** — the integrity zome's `validate()` callback rejects all updates and deletes of `HarmonyRecord` entries. Every peer on the network independently validates every operation — there is no central server to compromise.

**2. Author key enforcement** — only the system's `harmony_record_creator_key` (baked into the DNA at deployment, cryptographically immutable) may write a Harmony Record. No other agent can create, modify, or delete one.

**3. Distributed storage** — the record exists across every peer on the Governance DHT simultaneously. There is no single copy to alter, no database to hack, no administrator to pressure.

A Harmony Record, once written, is as permanent as the network itself.

---

## What Harmony Records Are Not

**They are not peer review.** ValiChord validates computational reproducibility — whether the code and data produce the results as described. It does not assess whether the methodology is sound, whether the conclusions are justified, or whether the study is significant. That is peer review's job. ValiChord is a complement to peer review, not a replacement.

**They are not guarantees of correctness.** A study that reproduces is not necessarily correct — it may contain systematic errors that reproduce consistently. ValiChord confirms that independent validators, following the documented methods, obtained the same results. What those results mean scientifically is a separate question.

**They are not punitive.** A Failed Reproduction badge is not an accusation of fraud. Many studies fail to reproduce for reasons unrelated to the original researchers' conduct — undocumented dependencies, platform differences, incomplete environment specifications. ValiChord records what happened; it does not assign blame.

---

## Harmony Records in Context

Harmony Records are the public-facing output of a system designed to be structurally resistant to manipulation. The blind commit-reveal protocol ensures validators cannot see each other's findings before submitting their own. The credentialed membrane ensures only institutionally verified validators participate. The immutability guarantees ensure the record cannot be altered after the fact.

The result is a verification instrument that funders, journals, institutions, and the public can trust — not because they trust ValiChord's operators, but because the architecture makes corruption structurally difficult.

---

*For the full governance framework, including how the system resists institutional capture, see [ValiChord Governance Framework](2_ValiChord_Governance_Framework.md).*

*For the technical implementation of Harmony Records in DNA 4, see [Technical Architecture](7_ValiChord_4-DNA_architecture_technical.md).*

*Governance preprint: [10.5281/zenodo.18878108](https://doi.org/10.5281/zenodo.18878108)*
