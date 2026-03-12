<div align="center">
  <img src="../Valichord logo-standard v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord — Open Design Questions
## Precedents, Likely Approaches, and Resolution Phases

**Author:** Ceri John
**Date:** February 2026

**© 2026 Ceri John. All Rights Reserved.**

**Contact:** topeuph@gmail.com

---

## Purpose

The following fourteen questions do not have complete answers yet. They are documented because they are the questions that funders, ethics boards, journal editors, and institutional partners will ask first — and because honest acknowledgment of open problems is more credible than silence.

Each question includes: the problem, precedents from existing reproducibility initiatives that inform the design space, ValiChord's likely approach, and which phase resolves it.

These questions are listed in the Vision & Architecture companion document. This document provides the full treatment.

---

## The Questions

**1. Do original authors need to consent to validation?** ValiChord's likely model is dual-path: author-initiated submission as the primary route, with third-party submission permitted for published work where code and data are already public, subject to notification and right of reply. This mirrors the approach used by the Reproducibility Projects (Psychology and Cancer Biology), which contacted original authors for materials and clarifications but did not require permission to proceed, and cascad, which verifies papers without requiring author consent when materials are public. The exact balance between openness and procedural fairness is a Phase 1 governance question informed by the PI and ethics review.

**2. Who pays for compute?** The validator fee covers intellectual labour, but computational reproduction can require significant infrastructure — cloud computing, GPU hours, HPC access. ValiChord's likely model separates validator compensation (for time) from compute provision (as infrastructure): lightweight studies use the validator's own resources; high-compute studies require the submitting institution to provide access or a central bursary. Precedents include the Reproducibility Project: Cancer Biology (centrally funded, averaging ~$52K per replication) and AEA/cascad economics replications (journal-funded). Phase 0 captures compute requirements as a data dimension to inform Phase 1 costing. Some studies may prove unvalidatable at current funding levels — that is an honest finding, not a system failure.

**3. What happens after a negative Harmony Record?** The likely process mirrors established precedents (Reproducibility Projects, cascad, Registered Reports): original author notified before publication, given a defined response window, their response embedded in the Harmony Record as part of the permanent record. No automatic downstream action — no forced retraction, no funder notification. The Harmony Record is information, not a verdict. Journals and funders query the integration layer and decide their own responses. The exact notification timeline and escalation process are Phase 1 governance questions.

**4. Original author's right of reply.** If a study doesn't reproduce, the original author may have a legitimate explanation — a missing dependency, an undocumented configuration, a known hardware sensitivity. The Harmony Record format already preserves multiple perspectives; extending this to include the author's response as a permanent, visible part of the record is architecturally natural. Readers see the full picture: what the validators found, what the author says, and the unresolved questions.

**5. How are Phase 0 studies selected?** Study selection should be governed by the PI with documented rationale, transparent inclusion and exclusion criteria, and deliberate recruitment across the difficulty spectrum — including studies expected not to reproduce cleanly. Precedents (the Reproducibility Projects used steering committees with external advisors) show that documented selection processes are standard. The selection rationale should be published alongside results.

**6. Restricted and sensitive research.** ValiChord's likely approach is tiered: open-data studies validated normally; restricted-data studies validated through secure access arrangements (NDA, institutional agreements, secure enclaves) where feasible; fully embargoed studies excluded or limited to open pipeline components. Precedents include cascad (temporary access via secure enclaves), epidemiology initiatives (federated analysis, simulated data), and 3ie development economics (de-identified data, restricted-access protocols). Phase 0 focuses on openly available studies; the restricted/excluded boundary is a Phase 2+ question.

**7. Holochain platform dependency.** If Holochain stalls or fails to reach production maturity, ValiChord's core concepts — content-addressed storage, cryptographic commitments, distributed validation, tamper-evident audit trails — are established distributed systems patterns implementable on other platforms. What Holochain provides is an unusually clean fit (agent-centric GDPR compliance, no global consensus requirement, native behavioural analysis). The mitigation is architectural awareness: maintaining clear separation between the conceptual model and the implementation platform so that governance, evidence, and institutional relationships transfer even if the engineering needs rebuilding.

**8. Validator training and calibration.** Even computationally skilled researchers need structured onboarding to ValiChord's specific process — environment documentation, reproduction standards, time recording, commit-reveal mechanics. Precedents range from cascad (supervised practice validations) to Cochrane (structured reviewer training modules) to the Reproducibility Project: Psychology (detailed protocols with coordinator check-ins). ValiChord's likely model is a practice validation on a known study, process documentation, and coordinator support. Phase 0 itself will reveal what validators found unclear, directly informing training design.

**9. Correcting a flawed Harmony Record.** If a validator commits fraud or a systematic error is discovered in the validation process, the append-only architecture means the record cannot be deleted — but it can be annotated and superseded. This mirrors established practice: journals issue corrections and expressions of concern, Retraction Watch maintains public records, and the principle throughout is that flawed work is marked rather than erased. The original Harmony Record stays; a correction notice is appended with rationale. The annotation format and governance trigger are Phase 1 questions.

**10. Long-term record preservation.** Harmony Records live on Holochain's DHT, which requires active nodes. If ValiChord ceases to exist, records become inaccessible. Precedents for academic preservation are mature: LOCKSS/CLOCKSS, Crossref DOI persistence, Portico, Internet Archive. ValiChord's likely approach is dual — active use on the DHT plus periodic export in a standard archival format (structured JSON or XML with published schema) to institutional repositories or preservation services. The archival format and partnerships are Phase 2 questions.

**11. Validator identity verification.** At Phase 0 scale, identity is trivial — known individuals recruited through the host institution. At Phase 3 with thousands of global validators, fake identities and sockpuppet accounts become real risks. Precedents centre on institutional identity linking (ORCID, institutional email verification, clinical trial registry sign-off). ValiChord's likely model ties registration to ORCID or institutional email, with the social distance mapping already in the architecture (co-authorship graphs, institutional caps) detecting coordinated fakes. Exact verification processes are Phase 1 questions.

**12. Submission-side cherry-picking.** Voluntary submission means researchers disproportionately submit work they're confident will reproduce, biasing ValiChord's record toward success — the publication bias problem applied to validation. The precedent is instructive: Registered Reports solved publication bias by committing to publish regardless of outcome; ValiChord's parallel is funder mandates or journal integration (Phase 2 goals). During voluntary adoption, the limitation should be stated clearly in aggregate reporting: "these results reflect voluntarily submitted studies and may not be representative of the broader literature."

**13. Cross-border data jurisdiction.** Phase 0 is UK-based; Phase 3 is global. Cross-border validation involving sensitive data creates jurisdictional complexity — GDPR adequacy decisions, data transfer agreements, ethics reciprocity. Precedents include international clinical trials, CERN's global collaborations, and the GDPR's own Standard Contractual Clauses. ValiChord's architecture provides a partial technical solution: patient data stays local, only cryptographic proofs are distributed. For restricted data, institutional data transfer agreements would be required — standard practice in international research. The specific legal frameworks are Phase 2+ questions requiring legal expertise.

**14. Who pays for persistently indeterminate validation outcomes?**

This is the most critical unresolved economic question in ValiChord's design. When three validators produce divergent results — one success, one failure, one indeterminate — the system has generated valuable information (genuine ambiguity in the work) but no clean badge for the author. The researcher has paid for validation. The validators have done real work. The outcome is honest uncertainty.

The tension: validator labour must be compensated regardless of outcome, or validators cannot be asked to take on assignments where indeterminacy is possible. But researchers may resist paying full fees for a finding of "we don't know." This creates an incentive for researchers to submit only studies they're confident will reproduce cleanly — exactly the selection bias ValiChord is designed to prevent.

ValiChord's current thinking: the validation fee covers validator labour regardless of outcome, analogous to paying for negative results in clinical trials. A Persistently Indeterminate Harmony Record is not a failure — it reveals genuine brittleness in the computational methods, documentation gaps, or hardware dependencies that the field did not previously have evidence of. The system produces knowledge, not just badges, and indeterminate results are a form of knowledge.

The harder sub-question is what happens when indeterminacy is caused by a recoverable documentation gap — a missing dependency, an undocumented configuration — that the author could fix. Current thinking: a structured re-submission pathway at reduced cost, analogous to a major revision in peer review, would allow the author to address identified gaps and re-enter the queue. This prevents indeterminacy from being a dead end while preserving the epistemic integrity of the original record.

A secondary tension: if funders or journals use Harmony Records as pass/fail signals, Persistently Indeterminate outcomes may be treated as failures regardless of ValiChord's framing. This is a governance and communication challenge, not a technical one. The Governance Framework's anti-domestication mechanics — particularly the prohibition on forcing a verdict where the evidence doesn't support one — are the primary defence. Phase 0 should collect data on how often validation attempts result in indeterminate outcomes and what study features are associated with them. This evidence will ground Phase 1 decisions about fee structure, re-submission pathways, and communication norms around uncertain results.

*Resolution phase: Phase 0 generates the empirical foundation (frequency, correlates of indeterminacy). Phase 1 resolves fee structure and re-submission pathway design. Governance communication norms are an ongoing concern from Phase 1 onward.*

**15. How should validator reputation scale — and how do you prevent it becoming permanent authority?**

This is one of the most difficult unsolved design problems in ValiChord's governance model, and one that has no clean precedent in existing reproducibility infrastructure.

The tension is this: validator reputation is necessary. A system that treats a first-time validator identically to someone with a hundred completed rounds and a consistent agreement record is epistemically indefensible. Quality signals must exist. But any reputation system that allows accumulated credibility to become permanent authority replicates the very gatekeeping structures ValiChord is designed to resist. The validators who got in early, did good work, and accumulated high scores become a de facto priesthood — and new validators face a catch-22: you need a track record to gain influence, but you need assignments to build a track record.

A third model is emerging in distributed systems that may fit ValiChord better than either fully open or fully credentialed validation:

- Permissionless entry — anyone with an institutional credential can join
- Earned credibility through demonstrated track record — influence grows with quality
- Transparent validator history — all validation records are publicly auditable
- Credibility must never become permanent authority — the hardest constraint to design

The architecture already has the scaffolding for this: `ValidatorReputation` in DNA 4 tracks agreement rates, tier progression, and discipline coverage. The membrane proof handles entry credentialing. What does not yet exist is the feedback loop connecting reputation back to validator assignment — and a mechanism preventing reputation calcification.

**Three partial approaches, each with known failure modes:**

*Reputation decay* — scores drift toward baseline over time without continued activity. Prevents permanent authority accumulates, but creates perverse incentives: validators are rewarded for quantity of validations rather than quality, and may rush assignments to maintain scores.

*Lottery weighting* — high-reputation validators receive higher probability of assignment, but not certainty. New validators always have a non-zero chance. Influence is probabilistic, not deterministic. This is more defensible than deterministic assignment but still rewards early entrants disproportionately at scale.

*Discipline rotation* — reputation in one discipline does not transfer to another. A validator who is Gold tier in computational biology starts fresh in climate modelling. This prevents cross-domain authority accumulation but may be too restrictive for validators who legitimately work across fields.

**The deeper problem** is that "demonstrated validation quality" requires comparing your findings against ground truth — but in science, ground truth is often exactly what is in dispute. Agreement with the majority is not the same as being correct. A validator who consistently agrees with peers in a field where the field is systematically wrong accumulates high reputation for the wrong reason. This is not a problem ValiChord can solve alone; it reflects a fundamental epistemological limit on peer validation systems.

**ValiChord's current thinking:** The Phase 0 data will reveal how often validators agree with each other and what factors are associated with agreement. This is the empirical foundation the reputation model needs before any weighting scheme can be responsibly designed. The architecture is deliberately agnostic on reputation weighting at this stage — `ValidatorReputation` stores the data, but the function that converts reputation into assignment probability does not yet exist. Designing it without Phase 0 evidence would be premature and potentially harmful.

The governance principle that must be preserved regardless of implementation: **no validator cohort, however experienced, should be able to prevent a credentialed newcomer from receiving assignments.** The entry credential is the floor; reputation is a signal, not a gate.

This question is also a candidate for interdisciplinary collaboration — the mechanism design and political science literature on reputation systems in distributed governance has directly relevant insights. A collaborator from those fields could contribute meaningfully to Phase 1 governance design.

*Resolution phase: Phase 0 generates the empirical foundation (agreement rates, validator consistency, discipline variation). Phase 1 designs the assignment weighting function informed by that data. The anti-calcification constraint is a governance principle applicable from Phase 1 onward.*
---

**Companion Documents:**
- *ValiChord Vision & Architecture* — The source document from which this is drawn
- *ValiChord Technical Reference* — Architecture sketches for engineering discussion
- *ValiChord Governance Framework* — How the system resists corruption and capture
- *ValiChord Phase 0 Proposal* — Workload Discovery Pilot (£69K, 6 months)

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**
