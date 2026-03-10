[README(2).md](https://github.com/user-attachments/files/25872700/README.2.md)
<div align="center">

<img src="Valichord logo-standard v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">

**An Immune System for Science: Distributed Integrity Infrastructure for Computational Research**

[![Status](https://img.shields.io/badge/Status-Infrastructure_Built-brightgreen?style=for-the-badge)](https://topeuph-ai.github.io/ValiChord)
[![Language](https://img.shields.io/badge/Language-Rust-orange?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/)
[![Tests](https://img.shields.io/badge/Tests-50_pass_%7C_1_skipped-brightgreen?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/tests/)
[![Grant](https://img.shields.io/badge/Grant-UKRI_Metascience_2-purple?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/5_ValiChord_Phase_0_proposal_ukri_etc.md)

---

## 📖 [**Primary Entry Point: Vision & Architecture**](https://github.com/topeuph-ai/ValiChord/blob/main/docs/1_ValiChord_Vision&Architecture.md)
*The core vision: Why ValiChord matters and how it solves the $200B verification gap.*

---

[ **[Project Website](https://topeuph-ai.github.io/ValiChord)** ] &nbsp;•&nbsp; [ **[Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md)** ] &nbsp;•&nbsp; [ **[4-DNA Architecture](https://github.com/topeuph-ai/ValiChord/blob/main/docs/8_ValiChord_4-DNA_Membrane_architecture.md)** ] &nbsp;•&nbsp; [ **[ValiChord at Home](https://github.com/topeuph-ai/ValiChord/blob/main/docs/9_Valichord_at_Home.md)** ]

</div>

## 🧬 The Mission
Computational methods now underpin virtually every scientific discipline, yet **70% of researchers** have failed to reproduce another scientist's experiments. This "Verification Gap" results in an estimated **$200 billion in wasted R&D annually**.

**ValiChord** is a distributed, agent-centric infrastructure designed to make computational reproducibility verifiable, tamper-evident, and structurally resistant to corruption. It replaces binary "Pass/Fail" verdicts with **Harmony Records** — permanent, publicly queryable records that preserve the full texture of scientific agreement and disagreement.

---

## 🏗️ 4-DNA Membrane Architecture

ValiChord is built as four distinct Holochain DNAs — four separate peer-to-peer networks — ensuring absolute data sovereignty and GDPR compliance by architecture, not policy.

| DNA | Purpose | Access Control |
| :--- | :--- | :--- |
| **DNA 1 — Researcher Repository** | Private storage of raw code, data, protocols, and snapshots. Nothing leaves except a SHA-256 hash. | **Private** — single agent, never enters DHT |
| **DNA 2 — Validator Workspace** | Where the reproduction work happens. Private attestation sealed here during the commit phase. | **Private** — single agent, never enters DHT |
| **DNA 3 — Attestation** | Shared DHT for validation requests, blind commitment anchors, and public attestations. Credentialed membrane. | **Credentialed** — institutional membrane proof required |
| **DNA 4 — Governance & Harmony** | Public results, Harmony Records, Reproducibility Badges, and validator reputation. HTTP Gateway target. | **Open read** — no Holochain node required |

📖 <strong>For more detail, see</strong><br>
<a href="https://github.com/topeuph-ai/ValiChord/blob/main/docs/7_ValiChord_4-DNA_architecture_technical.md">ValiChord: Technical Architecture — Four-DNA Membrane Design </a>

</div>

---

## ✅ Implementation Status

The four-DNA infrastructure is **built and tested**. This is not a whitepaper or a design document — it is working Rust/Holochain code with a passing integration test suite.

```
valichord/
├── shared_types/           — cross-DNA types (pure rlib)
├── dnas/
│   ├── attestation/        — DNA 3: shared DHT, credentialed membrane
│   ├── researcher_repository/ — DNA 1: private, single-agent
│   ├── validator_workspace/   — DNA 2: private, single-agent  
│   └── governance/         — DNA 4: public DHT, HTTP Gateway
├── tests/
│   ├── attestation.test.ts     — 17 tests
│   ├── governance.test.ts      — 11 tests
│   ├── researcher_repository.test.ts — 11 tests
│   └── validator_workspace.test.ts   — 5 tests
└── happ.yaml               — all four DNA roles bundled
```

**54 integration tests passing (1 skipped — infrastructure limitation only)**, covering:
- Membrane proof acceptance and rejection
- Full blind commit-reveal protocol end-to-end across all four DNAs
- DHT-poll-driven phase transitions (CommitmentAnchor → PhaseMarker)
- Immutability enforcement on ValidationAttestation, CommitmentAnchor, and PhaseMarker
- Author key enforcement on HarmonyRecord and GovernanceDecision
- Privacy across agents — private attestations are not readable by peers
- Reproducibility badge issuance (Bronze, Silver, Failed thresholds)
- Cross-DNA post_commit chain: DNA 2 seal → DNA 3 notify → phase open

---

## 🔐 The Blind Commit-Reveal Protocol

To prevent last-mover advantage, ValiChord implements a blind commit-reveal protocol across DNA 2 and DNA 3:

1. **Commit** — each validator seals their private assessment as a `ValidatorPrivateAttestation` in their own DNA 2 workspace. The entry never leaves their machine.
2. **Anchor** — DNA 2's `post_commit` automatically calls `notify_commitment_sealed()` in DNA 3, writing a public `CommitmentAnchor` to the shared DHT. Everyone can see the commitment happened, but not the outcome.
3. **Phase open** — when all expected `CommitmentAnchor` entries are present, DNA 3 writes a `PhaseMarker(RevealOpen)` to the DHT. Validators discover this by polling, not by signal — ensuring no validator is disadvantaged by network latency.
4. **Reveal** — validators submit their public `ValidationAttestation` entries to DNA 3. These are immutable after publication.
5. **Harmony** — once all attestations are present, DNA 4 assembles a `HarmonyRecord` on the public DHT, assesses agreement, and optionally issues a `ReproducibilityBadge`.

---

## ⚖️ Governance Philosophy: Designing Against Domestication

Most validation systems fail not because of bad technology but because of institutional capture — funders, publishers, or powerful research groups gradually bend the rules in their favour. ValiChord's governance framework is designed from the ground up to resist this.

The core principle is **structural independence**: no single institution, funder, or validator cohort can control outcomes. This is achieved through:

- **Blind commitment** — validators cannot see each other's findings before revealing their own, preventing social conformity and last-mover advantage
- **Credentialed membranes** — only institutionally verified validators can participate; anonymous or self-certified participation is architecturally impossible
- **Immutable public records** — Harmony Records on the public DHT cannot be altered or deleted by anyone, including ValiChord's own operators
- **Distributed governance** — no central server, no single point of control; the network is the authority
- **Transparent disagreement** — where validators diverge, the disagreement is recorded in full, not averaged away

The governance framework explicitly addresses what happens when ValiChord itself comes under pressure — from funders seeking favourable results, from institutions protecting reputations, or from validators gaming the system for reputation scores. The answer in each case is the same: the architecture makes corruption structurally difficult rather than relying on policy or goodwill.

📄 **[Read the full Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md)** — published as a Zenodo preprint: [10.5281/zenodo.18878108](https://doi.org/10.5281/zenodo.18878108)

---

## 🛠️ Researcher Ecosystem: "ValiChord at Home"

We provide a full feedback pipeline to move research from "messy" to "validatable".

### 🏠 **ValiChord at Home (Self-Service)**
**Private, local pre-vetting for researchers.**
Before submitting for formal validation, researchers use this tool to scan their repositories privately.
- **Static Analysis:** Identifies documentation gaps and environment friction without code execution.
- **Difficulty Prediction:** Uses a weighted rubric to estimate validation labour based on Phase 0 empirical data.

👉 **[Launch ValiChord at Home](https://topeuph-ai.github.io/ValiChord/at-home.html)**

### 🔍 **Assisted Correction**
**Automated reproducibility hygiene.**
ValiChord generates proposed corrections — drafted READMEs, pinned dependencies — for researcher review and approval.

---

## 📚 Technical Documents

| Document | Description |
| :--- | :--- |
| [Vision & Architecture v11](https://github.com/topeuph-ai/ValiChord/blob/main/docs/1_ValiChord_Vision&Architecture.md) | What ValiChord is and why it matters |
| [Technical Reference v16](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md) | Full architectural narrative and engineering reference |
| [Architecture Scaffold v12 (Rust)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs) | Single-file representation of the four-DNA architecture |
| [Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md) | How the system resists corruption |
| [Holochain Scaffolding Plan](https://github.com/topeuph-ai/ValiChord/blob/main/docs/SCAFFOLDING_PLAN.md) | Engineering plan produced by Claude Code |
| [Why Holochain?](https://github.com/topeuph-ai/ValiChord/blob/main/docs/a_Why_Holochain?.md) | Non-technical explanation of the architectural choice |

---

## 🔧 For Developers

The four-DNA Holochain infrastructure is built and integration-tested. The codebase is available for technical review.

| Resource | Link |
| :--- | :--- |
| Codebase (Rust / Holochain) | [`valichord/`](https://github.com/topeuph-ai/ValiChord/tree/main/valichord) |
| Test suite + build instructions | [`valichord/tests/README.md`](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/tests/README.md) |
| Architecture Scaffold v12 | [`docs/4_ValiChord_RUST_Scaffold.rs`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs) |
| Technical Architecture | [`docs/8_ValiChord_4-DNA_Membrane_architecture.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/8_ValiChord_4-DNA_Membrane_architecture.md) |
| Technical Reference v16 | [`docs/3_ValiChord_Technical_Reference.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md) |

> **Note:** This is infrastructure-stage code — four compiled, tested Holochain DNAs with no UI layer yet. There is no application to run as a standalone tool. The codebase is here for technical review and collaboration. If you are a Holochain engineer interested in contributing, please get in touch: [topeuph@gmail.com](mailto:topeuph@gmail.com)

---

## 📊 Roadmap

| Phase | Focus | Status |
| :--- | :--- | :--- |
| **Phase 0** | **Workload Discovery:** Empirical study to quantify the true cost of validation. ~£150K FEC, 12 months. | **Proposed — UKRI Metascience Round 2 (April 2026)** |
| **Phase 1** | **Full MVP:** UI layer, researcher and validator dashboards, live network deployment. | **Infrastructure complete — awaiting Phase 0 funding** |
| **Phase 2** | **Integration:** Journal and funder API deployments via HTTP Gateway. | **In planning** |

---

ValiChord is built on Holochain — an end-to-end open-source agent-centric P2P application framework.

<a href="https://holochain.org">
<img src="https://github.com/topeuph-ai/ValiChord/blob/main/holochain%20logo.png?raw=true" width="750" alt="Holochain Logo">
</a>

---

**Author:** Ceri John &nbsp;•&nbsp; **Contact:** [topeuph@gmail.com](mailto:topeuph@gmail.com)

**Technical Review:** Arthur Brock (Holochain co-founder), Paul D'Aoust (Holochain Foundation), Joel Marcey (Rust Foundation)

**© 2026 Ceri John. All Rights Reserved.**
