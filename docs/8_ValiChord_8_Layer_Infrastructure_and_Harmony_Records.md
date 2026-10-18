![ValiChord 8-Layer Architecture and Harmony Record](https://github.com/ValiChord/ValiChord/blob/main/Images/8%20layer%20infrastructure.jpeg)


# ValiChord: Eight-Layer Infrastructure and Harmony Records

ValiChord is an end-to-end system designed to address the reproducibility crisis by providing a tamper-evident, distributed engine for validating computational research. The core infrastructure is **built and integration-tested**: four Holochain DNAs (Holochain 0.7.1), compiled to WebAssembly, with Rust sweettest integration tests that run many validator agents against each other (see CI for the current count).

---

## The Eight-Layer Infrastructure (Conceptual Framework)

The system is organised into eight functional layers describing the lifecycle of a research study from intake to public certification. These layers are a conceptual map — see the note at the bottom for how they relate to the actual engineering structure.

---

### L0 — Content-Addressed Storage

The foundation. Research artefacts — code, data, protocols — are identified by unique cryptographic fingerprints (SHA-256 hashes). Every validator works from materials anchored to the same fingerprint. If a single byte changes, the fingerprint changes, making tampering immediately detectable.

In the engineering implementation: hashes are computed in DNA 1 (Researcher Repository) and are the only thing that travels outward to the shared network before the reveal. At the reveal, the researcher publishes their summary result metrics; the data itself never leaves.

---

### L1 — Data Integrity and Access Control

Manages structured intake and pre-registration. Research questions and analysis plans are committed before results are known — and locked immutably at that point. A researcher cannot revise their pre-registered protocol after submission.

In the engineering implementation: `PreRegisteredProtocol` entries in DNA 1 are immutable after creation, enforced in `validate()` and integration-tested.

---

### L2 — Validation Execution Engine

The core layer where independent, **credentialed** validators re-run computational code within their own isolated environments to verify the original findings. Every validator holds a credential signed by an authorised issuer (an institution for human validators; the ValiChord operator for AI validators) — anonymous or self-certified participation is architecturally impossible. Each validator works without knowledge of what other validators are finding.

In the engineering implementation: DNA 2 (Validator Workspace) provides each validator with a private, single-agent environment. The blind commit-reveal protocol ensures independence. DNA 3 (Attestation) requires a cryptographic credential (membrane proof) to join, and every peer checks it for themselves (since PR #47, October 2026).

---

### L3 — Harmony Record Aggregation

Transforms individual validation results into structured, permanent trust signals. Once all validators have revealed their findings, this layer assembles them into a unified Harmony Record — capturing not just the outcome but the full pattern of agreement and disagreement.

In the engineering implementation: `check_and_create_harmony_record` in DNA 4 (Governance) retrieves all attestations and calculates the majority outcome and agreement level. The resulting `HarmonyRecord` carries every validator's signed attestation, every peer checks that its summary matches them, and it is immutable once written.

---

### L4 — Epistemic Integrity Commitments

The non-negotiable principles that protect the validity of validation outcomes. These are not policies — they are architectural constraints:

- **Blind commit-reveal** — validators seal their findings before anyone else's are visible. The commitment is cryptographically locked and cannot be changed after the reveal window opens.
- **Forced disagreement visibility** — where validators diverge, the divergence is recorded in full. The system cannot average away meaningful scientific disagreement.
- **Immutability** — published attestations and Harmony Records cannot be altered or deleted by anyone, including ValiChord's operators.

In the engineering implementation: `CommitmentAnchor`, `PhaseMarker`, `ValidationAttestation`, and `HarmonyRecord` are all immutable after creation, enforced by validation rules on every peer in the network independently.

---

### L5 — Incentive and Reputation Mechanism

Manages multi-dimensional reputation scores for validators, rewarding quality, consistency, and honesty over time. Validator contributions are attributed using the CRediT taxonomy, creating a legitimate career record for validation work. This layer is designed to make validation a recognised professional activity, not an invisible service.

In the engineering implementation: `ValidatorReputation` in DNA 4 tracks validation history, agreement rates, and discipline coverage. Full cumulative reputation progression is deferred to Phase 1 (who writes reputation records in production is still undecided). CRediT attribution is a design intention, not yet built.

---

### L6 — Governance and Protocol Evolution

Oversees system-wide standards, disciplinary rules, and the evolution of the protocol over time. This layer is explicitly designed to resist institutional capture — the gradual bending of rules by funders, publishers, or powerful research groups. Governance decisions are recorded permanently and publicly.

The full governance philosophy — including explicit mechanisms against domestication — is documented in the [Governance Framework](2_ValiChord_Governance_Framework.md), published as a Zenodo preprint: [10.5281/zenodo.18878108](https://doi.org/10.5281/zenodo.18878108).

In the engineering implementation: `GovernanceDecision` entries in DNA 4 are immutable and gated by `system_coordinator_key` in DNA properties — governance decisions represent human deliberation outcomes and require a designated recorder. `ValidatorReputation` is gated by the same key. `HarmonyRecord` and `ReproducibilityBadge` need no designated key: any validator who took part in a round can write them, and every peer checks them against the validators' own signed attestations. This means finalisation does not depend on a central coordinator node.

---

### L7 — API and External Interface

The public face of ValiChord. Journals, funders, research offices, and the public can query validation statuses and Harmony Records via standard HTTP requests — no Holochain node required, no institutional membership, no specialist software.

In the engineering implementation: DNA 4 (Governance & Harmony Records) is designed as an HTTP Gateway target. The gateway configuration is a Phase 1 deployment task; the architecture is ready.

---

## The Harmony Record: Preserving the Full Texture of Science

Unlike traditional binary "pass/fail" metrics, a Harmony Record preserves the full texture of what validators actually found.

**"Harmony" does not mean unanimity.** It means the honest documentation of agreement and disagreement — the same way musical harmony captures the relationship between voices rather than requiring them all to sing the same note. A record with divergent findings is often more informative than a forced consensus.

A completed Harmony Record contains:

- **Study reference** — a cryptographic hash anchoring the record to the exact materials that were validated
- **Outcome** — the majority finding (Reproduced, PartiallyReproduced, FailedToReproduce, UnableToAssess)
- **Agreement level** — how closely validators agreed (ExactMatch, WithinTolerance, DirectionalMatch, Divergent, UnableToAssess)
- **Participating validators** — who validated, identified by their public keys (each one admitted by a verified credential), and how many validators were requested
- **Validation duration** — the longest time any one validator spent
- **Each validator's own findings** — carried in the record with their signature, so where validators reached different conclusions it is visible, never averaged away
- **Reproducibility Badge** — Gold, Silver, Bronze, or Failed, a separate entry issued automatically from validator count and agreement level (the thresholds are placeholders, to be calibrated with real data)

The record is permanent and immutable the moment it is written to the public DHT. It cannot be altered or deleted by anyone.

📄 **[Full Harmony Records explanation](10_Harmony_Records.md)**
📖 **[Follow a complete validation round from submission to Harmony Record](15_How_a_Validation_Round_Works.md)**

---

## Note on Structure

The eight layers above are a **conceptual framework** — they describe what ValiChord does in functional terms, and they communicate the system's responsibilities clearly to non-technical audiences.

The actual engineering structure is the **four-DNA membrane architecture**: Researcher Repository (DNA 1), Validator Workspace (DNA 2), Attestation (DNA 3), and Governance & Harmony Records (DNA 4). The functional layers map across those four DNAs rather than sitting in a single application stack.

The layer framework is retained here because it is useful for explaining responsibilities. It is not an implementation plan.

📐 **[Technical Architecture — Four-DNA Membrane Design](7_ValiChord_4-DNA_architecture_technical.md)** — for engineers
📘 **[Four-DNA Architecture — Plain English](7a_ValiChord_4-DNA_architecture_nontechnical.md)** — for everyone else

---

*© 2026 Ceri John. All Rights Reserved.*
