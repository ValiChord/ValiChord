<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# The Two-Round Protocol: A Proposed Extension to Human Validation

**Status: Design Proposal — Not Yet Implemented**

**Author:** Ceri John
**Date:** April 2026

**© 2026 Ceri John. All Rights Reserved.**
**Contact:** topeuph@gmail.com

---

## What This Document Is

This document describes a proposed enhancement to ValiChord's human validation process: a **two-round protocol** that restructures when validators make their reproducibility verdict, ensuring that verdict is made in light of the researcher's formally committed values rather than solely from reading the paper. It is a design proposal — the idea is fully thought through and ready to build, but has not yet been implemented in the codebase.

The proposal is recorded here so that funders, collaborators, and future engineers can understand its purpose, its scope, and exactly how it would fit into the existing system. Nothing in the current codebase needs to change to read this document.

---

## A Gap in the Current Protocol

ValiChord's current validation round works like this: each validator runs the study independently, records their findings privately, seals them with a cryptographic fingerprint, and then — once all validators have sealed — the reveal window opens. All findings become public simultaneously, the researcher's committed values are revealed at the same moment, and the Harmony Record is assembled.

This is strong. No validator can adjust their finding after seeing anyone else's. No validator can see anyone else's finding before sealing their own.

But there is a subtle gap worth examining.

In the current protocol, validators decide **Reproduced / Partially Reproduced / Failed to Reproduce** at the point of sealing — before the reveal window opens, and therefore before they have formally seen the researcher's committed values. They make this judgment based on running the code and comparing their output to what the researcher's **published paper** claims. The researcher's `ResearcherReveal` — the formally committed values that can be cryptographically proven not to have changed since submission — arrives on the network at the same moment the validators reveal their attestations. The formal comparison between what each validator produced and what the researcher formally committed to happens in the background, not as a structured decision step.

In practice, for most straightforward studies, this makes no difference. A validator who has read the paper knows what the study claims; running the code and finding matching numbers is a clear verdict. But for complex studies — where the paper's description is ambiguous, where tolerances are unclear, where partial results are open to interpretation — there is genuine value in making the formal verdict **after** the researcher's committed values are on the table for comparison, rather than before.

---

## The Proposed Solution

The two-round protocol restructures the sequence so that the reproducibility verdict is made at the right moment: after validators have run the study and after the researcher's formally committed values are visible, but still blind to what other validators concluded.

**Round 1 — Raw Findings**

Validators run the study independently, record what their execution produced — the numbers, the outputs, the time taken, the difficulties encountered — and seal that record privately. No verdict yet. The question this round answers is simply: *"What did I get when I ran this code with this data?"*

Once all validators have sealed their raw findings, the researcher reveals their committed values — the metrics they locked at submission, now formally proven against the hash that has been on the network since before any validator started work.

**Round 2 — The Verdict**

Validators now have everything they need to make a proper judgment: their own produced results, and the researcher's formally committed values side by side. Each validator independently and privately seals a verdict: **Reproduced / Partially Reproduced / Failed to Reproduce / Unable to Assess** — the same outcomes as today. The crucial difference is that this verdict is made in formal comparison to the researcher's committed values, not just from reading the paper.

The second round preserves the same blind structure as the first: each validator seals their verdict before anyone else's is visible. Only once all verdict seals are present does the reveal window open. Only once all verdicts are revealed does the Harmony Record get produced.

---

## Walking Through the Protocol

Here is the full sequence for a two-round study, following the same validators from document 15.

### Round 1: Raw Findings

James, Fatima, and Marcus each run Sarah's protein folding study independently. Each records what their execution produced — the specific output values, the time invested, any barriers encountered — and seals that record privately in their Validator Workspace. A public commitment anchor appears on the network for each of them: proof they have committed, with no indication of what they found.

Once all three anchors are present, the reveal window opens. James, Fatima, and Marcus each publish their raw findings. At the same moment, Sarah reveals her committed values — the metrics she locked at submission, now proven against the hash that has sat on the network since before any validator began work.

Everything is now on the table:
- James produced: *value A*
- Fatima produced: *value B*
- Marcus produced: *value C*
- Sarah committed to: *value X*

At this point — if this were a standard single-round study — the Harmony Record would be assembled. Under the two-round protocol, the process continues.

### Round 2: The Verdict

James can now formally compare his produced value against Sarah's committed value. He seals his verdict: *Reproduced* — his output matched Sarah's committed values within documented tolerance. He cannot see what Fatima or Marcus decided; they have committed but not yet revealed.

Fatima seals her verdict. Marcus seals his.

Once all three verdict anchors are present, the Verdict Reveal window opens. Each validator publishes their verdict. The protocol verifies each one against its commitment anchor — confirming that nobody adjusted their verdict after seeing the others.

The Governance layer assembles the Harmony Record from the Round 2 verdicts.

---

## What Changes in the Harmony Record

Under the two-round protocol, the Harmony Record contains two layers of information:

**Round 1 findings (per validator) — what each execution produced**
- James produced: *value A* (with full output detail and timing)
- Fatima produced: *value B*
- Marcus produced: *value C*
- Sarah's committed values: *value X* (formally verified against submission-time hash)

**Round 2 verdicts (per validator) — the formal comparison judgment**
- James: *Reproduced* — "Output matched committed values within documented computational tolerance."
- Fatima: *Reproduced* — "Exact match confirmed."
- Marcus: *Partially Reproduced* — "Output C diverges from committed value X on metric 3; all other metrics match. Divergence consistent with known floating point variance on AMD hardware."

**Harmony Record outcome (from Round 2 majority)**
- Outcome: *Reproduced*
- Agreement Level: *Within Tolerance*
- Badge: *Silver Reproducible*

A reader looking at this record sees not just the headline verdict but the full evidential basis for it: what each validator produced, what the researcher originally committed to, and how each validator judged the comparison. Marcus's partial reproduction and his reasoning are fully visible — not averaged away. The comparison between produced values and committed values is a formal, traceable part of the record, not a background inference.

---

## Transparency as a Deterrent

There is a deeper accountability mechanism built into the two-round protocol that is worth making explicit.

The Harmony Record publishes both layers of the process: the raw findings from Round 1 — what each validator's execution actually produced — alongside each validator's Round 2 verdict. This means the record does not just show *what validators concluded*. It shows *what they found and what they concluded*. Those two things sit side by side, permanently, on the public record, visible to anyone who queries the study.

This matters because it creates a very direct form of professional accountability. A validator who produced values that clearly diverge from the researcher's committed values but still returned a verdict of *Reproduced* would have that contradiction permanently visible to the world: their numbers, the researcher's numbers, and their verdict, all in the same record. No committee needs to investigate. No governance process needs to be triggered. The record speaks for itself.

This is, in many ways, a more natural deterrent than cryptographic enforcement. Science has always relied on professional reputation — the knowledge that your peers will see your work and judge it. The two-round protocol makes that accountability concrete and immediate: your findings are public, your verdict is public, and any gap between them is public. The question a validator must answer is not just *"is this reproduced?"* but *"am I comfortable with the world seeing my findings and my verdict in the same place?"*

It is worth being honest that the whole commit-reveal architecture rests on a degree of designed distrust — an acknowledgment that human nature, professional courtesy, and the quiet pressure to be encouraging can all pull a validator toward a softer verdict than their findings strictly support. That discomfort is real. But framed differently: this is not distrust of validators as people. It is respect for the pressures they operate under, and a commitment to giving them a structure that protects them from those pressures as much as it protects the record. A validator who genuinely believes a study reproduced can say so with confidence, knowing their findings back them up. A validator who feels pressure to be kind is given a reason — a public, permanent, professional reason — to be honest instead.

The longitudinal audit already in ValiChord's design catches the pattern of a validator who is *consistently* generous across many rounds. The two-round protocol's transparency closes the gap at the individual study level: the contradiction between findings and verdict is visible immediately, in the same record, without needing to wait for a pattern to accumulate.

---

## Why Opt-In, Not Universal

The two-round protocol is proposed as an **opt-in feature**, not a replacement for the current process. There are good reasons for this.

**It takes longer.** A standard validation round already requires validators to find time across days or weeks of real work. Adding a second commit-reveal cycle means validators must return to the system after Round 1 concludes to seal and then reveal their verdict. For straightforward studies where the numbers either match or they don't, this additional loop may not be worth it.

**It is not always necessary.** If all three validators ran the code, got the same numbers Sarah committed to, and the comparison is unambiguous, a second round adds coordination overhead without adding information. The two-round protocol earns its cost when the comparison is genuinely complex — partial matches, tolerance questions, interpretation of what "the same result" means for this type of study.

**AI validators should not use it.** An automated tool produces a factual output. The formal comparison between produced values and committed values can be computed mechanically; there is no deliberative act. The two-round protocol is designed for human judgment where that judgment is meaningful.

The researcher decides at submission time whether to request the two-round protocol. The choice is locked into the study record and cannot be changed — a researcher cannot switch from single-round to two-round mid-process.

---

## When Would a Researcher Choose This?

The two-round protocol is most appropriate when:

- The study involves **complex or partial results** where the difference between "reproduced" and "sufficiently reproduced" requires judgment against the formally committed values, not just a read of the paper
- The researcher is submitting for **high-stakes purposes** — grant renewal, regulatory review, publication in a journal that places weight on the rigour of the comparison process
- The study is in a discipline where **tolerance and equivalence thresholds** are contested and having the formal comparison as a documented step in the record matters
- There are **known computational sensitivities** — stochastic algorithms, hardware-dependent outputs — where the formal comparison step provides a clear record of which deviations were judged acceptable and why

For standard computational studies with unambiguous expected outputs, the current single-round process remains the right default. It is faster, simpler, and the comparison between produced and committed values is self-evident.

---

## What Would Need to Be Built

This section is written for engineers and technical reviewers. It describes the precise changes required to implement the two-round protocol against the existing codebase. Nothing here changes existing behaviour — all additions are new entry types and new protocol paths, activated only when `two_round_protocol = true` on a given study.

### Shared Types (`valichord/shared_types/src/lib.rs`)

**Updated `ValidationPhase` enum** — two new phase states:
```
VerdictCommitOpen    (Round 2 commit window: all Round 1 reveals and ResearcherReveal are present)
VerdictRevealOpen    (Round 2 reveal window: all verdict anchors sealed)
```

No new outcome types are needed. The verdict uses the existing `AttestationOutcome` enum:
`Reproduced | PartiallyReproduced { details } | FailedToReproduce { details } | UnableToAssess { reason }`

### Attestation DNA — Integrity (`attestation_integrity`)

**New `ValidationRequest` field:**
```
two_round_protocol: bool   (default: false — backwards compatible with all existing entries)
```

**New entry type: `ValidatorRawFindings`** — the Round 1 sealed record. Contains the validator's produced values and execution metadata, but no verdict. This is the private commit in DNA 2 that is analogous to `ValidatorPrivateAttestation` in the single-round flow — except it carries no `AttestationOutcome`.

**New entry type: `VerdictAnchor`** — the Round 2 commitment anchor, equivalent to `CommitmentAnchor` in the single-round flow. Carries:
- `request_ref` — the study
- `validator` — the validator's identity
- `verdict_commitment_hash` — SHA-256 of the sealed verdict content and nonce

**Round 2 reveal** uses the existing `ValidationAttestation` structure — the full entry with `AttestationOutcome`, `OutcomeSummary`, and `MetricResult` entries where `expected_value` is now populated from `ResearcherReveal.metrics` rather than from the paper. This means the Round 2 reveal produces exactly the same type of permanent record as the single-round reveal does today. No new public entry type is needed for the verdict — only the timing and gating change.

**New link types**: `RequestToRawFindings`, `RequestToVerdictAnchor` — for indexing and phase-gate queries.

**Immutability rules**: `ValidatorRawFindings` and `VerdictAnchor` are immutable after creation, identical to their single-round equivalents.

### Attestation DNA — Coordinator (`attestation_coordinator`)

**New `seal_raw_findings` function** — creates a `ValidatorRawFindings` entry in DNA 2 and fires a `RawFindingsAnchor` to the shared DHT (equivalent to `seal_private_attestation` today).

**New `submit_raw_findings` function** — the Round 1 reveal. Gated on all raw findings anchors being present. Writes the produced values to the shared DHT. Fires `reveal_researcher_result` automatically once all Round 1 reveals are present (researcher reveal is triggered by the protocol, not separately by the researcher in this flow variant).

**New `seal_verdict` function** — creates a `VerdictAnchor`. Gated: only callable after all Round 1 reveals are present AND `ResearcherReveal` is on the DHT.

**New `submit_verdict` function** — the Round 2 reveal. Takes `AttestationRevealInput` (same struct as today). Verifies the hash against the `VerdictAnchor`, writes the `ValidationAttestation` (same type as single-round), triggers governance finalisation once all verdicts are present.

**Modified `submit_attestation`** — currently triggers governance finalisation after the last reveal. Under two-round protocol, this step is skipped; finalisation is triggered by `submit_verdict` instead.

### Governance DNA

**No structural changes required.** The `HarmonyRecord` entry type does not change. Round 2 produces `ValidationAttestation` entries in exactly the same form as the single-round flow, so `check_and_create_harmony_record` and `derive_majority_outcome` work without modification.

The Round 1 raw findings are readable on the Attestation DHT for anyone who wants the full evidential picture, but the Harmony Record itself is assembled from the Round 2 verdicts — which are standard `ValidationAttestation` entries. Journals, funders, and badge systems see the same data shape regardless of which protocol was used.

---

## Open Questions Before Implementation

A few questions remain for governance and research design, not engineering:

1. **Who triggers the researcher reveal in the two-round flow?** In the current single-round protocol, the researcher is notified when all validators have committed and calls `reveal_researcher_result` themselves. In the two-round protocol, it may make more sense for the protocol to trigger the researcher reveal automatically once all Round 1 raw findings are present — so there is no delay between Round 1 reveals and the opening of the Round 2 window. Whether the researcher should have the option to delay their reveal (and for how long) is a governance question.

2. **What is the maximum time between Round 1 and Round 2?** Validators who have finished Round 1 should not be held waiting indefinitely for the Round 2 window to open because one validator has not yet revealed their raw findings. A `force_finalize_round` equivalent for Round 1 (advancing to the verdict phase with partial reveals) may be needed, equivalent to the existing `force_finalize_round` for the single-round flow.

3. **Should Round 2 carry separate compensation?** Validators are compensated for the reproduction work (Round 1). The Round 2 verdict step is shorter — a careful review of the formal comparison rather than hours of execution. A separate, smaller fee for the verdict round is worth considering. This is a Phase 1 governance question.

4. **How are Round 1 raw findings displayed publicly?** In the single-round flow, the `ValidationAttestation` is the definitive public record of what each validator found. In the two-round flow, the Round 1 `ValidatorRawFindings` entries are a distinct earlier record. The public display layer (journals, the verification gateway) should present both layers clearly — so a reader can see what each validator produced in Round 1 and how each validator judged the comparison against the researcher's committed values in Round 2.

---

## Summary

The two-round protocol closes a genuine gap in the current design: right now, validators make their reproducibility verdict before formally seeing the researcher's committed values — they rely on the paper's published claims. The two-round protocol makes the formal comparison between produced values and committed values a structured protocol step, with the verdict sealed and revealed under the same blind conditions as everything else.

The verdict itself is unchanged — Reproduced / Partially Reproduced / Failed to Reproduce / Unable to Assess, the same outcomes as today. No new vocabulary is introduced. The Harmony Record format is unchanged. The only thing that changes is the sequence: raw findings first, researcher reveal, then the formal verdict — blind to the other validators throughout.

The core principle is unchanged: no validator can see another validator's verdict before they seal their own. The blind structure that makes ValiChord credible applies to both rounds equally.

Implementation is moderate in scope — a new entry type for Round 1 raw findings, new phase states, new coordinator functions for the Round 2 flow, and a flag on `ValidationRequest`. The governance, badge, and integration infrastructure require no structural changes.

The proposal is ready for engineering work when the decision to proceed is made.

---

*This document was produced in dialogue between Ceri John and Claude Code (Anthropic), April 2026.*
