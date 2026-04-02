<div align="center">

<img src="Images/Valichord logo-standard v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">

**An Immune System for Science: Distributed Integrity Infrastructure for Scientific Research**

[![CI](https://github.com/topeuph-ai/ValiChord/actions/workflows/ci.yml/badge.svg)](https://github.com/topeuph-ai/ValiChord/actions/workflows/ci.yml)
[![Status](https://img.shields.io/badge/Status-Integration_Ready-brightgreen?style=for-the-badge)](https://topeuph-ai.github.io/ValiChord)
[![Language](https://img.shields.io/badge/Language-Rust-orange?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/)
[![Tests](https://img.shields.io/badge/Tests-94_pass_%7C_1_skipped-brightgreen?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/tests/)
[![Commit--Reveal](https://img.shields.io/badge/Commit--Reveal-Fully_Symmetric-blue?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/README.md#-the-blind-commit-reveal-protocol)
[![Grant](https://img.shields.io/badge/Grant-UKRI_Metascience_2-purple?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/5_ValiChord_Phase_0_proposal_ukri_etc.md)

---

## 📖 [**Primary Entry Point: Vision & Architecture**](https://github.com/topeuph-ai/ValiChord/blob/main/docs/1_ValiChord_Vision&Architecture.md)
*The core vision: Why ValiChord matters and how it solves the $200B verification gap.*

---

[ **[Project Website](https://topeuph-ai.github.io/ValiChord)** ] &nbsp;•&nbsp; [ **[Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md)** ] &nbsp;•&nbsp; [ **[4-DNA Architecture](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7_ValiChord_4-DNA_architecture_technical.md)** ] &nbsp;•&nbsp; [ **[ValiChord at Home](https://github.com/topeuph-ai/ValiChord/blob/main/docs/9_Valichord_at_Home.md)** ]

</div>

## 🧬 The Mission
Across every scientific discipline — computational, experimental, clinical, hardware — **70% of researchers** have failed to reproduce another scientist's work. This "Verification Gap" results in an estimated **$200 billion in wasted R&D annually**.

**ValiChord** is a distributed, agent-centric infrastructure designed to make scientific reproducibility verifiable, tamper-evident, and structurally resistant to corruption. The protocol is domain-agnostic: methodology and data go in, independent validators reproduce the work, and the result is a **Harmony Record** — a permanent, publicly queryable record that preserves the full texture of scientific agreement and disagreement. Computation is the first and most tractable instance. It is not the only one.

---

## 🏗️ 4-DNA Membrane Architecture

ValiChord is built as four distinct Holochain DNAs — four separate peer-to-peer networks — ensuring absolute data sovereignty and GDPR compliance by architecture, not policy.

| DNA | Purpose | Access Control |
| :--- | :--- | :--- |
| **DNA 1 — Researcher Repository** | Private storage of raw code, data, protocols, and snapshots. At submission, `lock_researcher_result` seals result metrics with a cryptographic nonce — only the hash leaves. | **Private** — single agent, never enters DHT |
| **DNA 2 — Validator Workspace** | Where the reproduction work happens. Private attestation sealed here during the commit phase. | **Private** — single agent, never enters DHT |
| **DNA 3 — Attestation** | Shared DHT for validation requests, blind commitment anchors, and public attestations. Credentialed membrane. | **Credentialed** — institutional membrane proof required |
| **DNA 4 — Governance & Harmony** | Public results, Harmony Records, Reproducibility Badges, and validator reputation. HTTP Gateway target. | **Open read** — no Holochain node required |

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
│   ├── attestation.test.ts          — 46 tests (1 skipped)
│   ├── governance.test.ts           — 24 tests
│   ├── researcher_repository.test.ts — 14 tests
│   ├── security.test.ts             — 7 tests
│   └── validator_workspace.test.ts   — 7 tests
└── happ.yaml               — all four DNA roles bundled
```

**94 integration tests passing (1 skipped — infrastructure limitation only).** The system is also integration-ready: a REST API (`POST /validate`, `GET /result/<job_id>`) connects the analysis pipeline to the live Holochain network, and a working HTTP Gateway exposes Harmony Records as publicly verifiable links. The API supports API key authentication, webhook callbacks, and a full [OpenAPI 3.0 spec](backend/openapi.yaml) with Swagger UI at `GET /docs`. Any tool that can POST a ZIP can integrate. The first external integration — [Feynman](https://github.com/getcompanion-ai/feynman), an AI research agent — is live. See [Integration Docs](#-integrations) below.

Test coverage includes:

> **ValiChord has been demonstrated running as a real multi-node network.** Integration tests launch up to 7 independent Holochain conductors — each with its own agent identity, source chain, and DHT participation — executing the full blind commit-reveal protocol and producing a Harmony Record on a shared live DHT. This is not a simulation: each conductor is an independent process with separate state, communicating over a real peer-to-peer network. The constraint is infrastructure RAM, not architecture.

- Real Ed25519 membrane proof verification — issuer-signed proofs accepted, forged signatures rejected at coordinator init
- Full blind commit-reveal protocol end-to-end across all four DNAs
- DHT-poll-driven phase transitions (CommitmentAnchor → PhaseMarker)
- Immutability enforcement on ValidationAttestation, CommitmentAnchor, PhaseMarker, ResearcherResultCommitment, ResearcherReveal, and PreRegisteredProtocol
- Author key enforcement on GovernanceDecision (HarmonyRecord/Badge/Reputation open to any participant — fully decentralised)
- Privacy across agents — private attestations are not readable by peers
- Reproducibility badge issuance (Bronze, Silver, Failed thresholds)
- Cross-DNA post_commit chain: DNA 2 seal (generates nonce + SHA-256 commitment_hash) → DNA 3 notify (CommitmentAnchor carries hash) → phase open
- Full symmetric commit-reveal: researcher `lock_researcher_result` (DNA 1) → `publish_researcher_commitment` (DNA 3 hash only) → `reveal_researcher_result` (DNA 3, hash-verified) → `ResearcherReveal` on DHT for comparison against validator outputs
- Mixed outcome HarmonyRecord assembly — Divergent agreement level from split validator results
- Validator discovery by discipline via real path index
- Difficulty assessment storage and retrieval via DifficultyPath link index
- Commit phase state detection — check_all_commitments_sealed verified at partial and full threshold
- Source-chain list queries (`get_all_studies`, `get_all_tasks`, `get_all_private_attestations`) using type-safe deserialization filter — no hardcoded ZomeIndex
- Governance decision creation, multi-record listing, and author enforcement
- BadgePath cross-study analytics index — written at badge issuance, queryable by type via `get_badges_by_type`
- Delete-immutability at API level — no delete functions exposed for HarmonyRecord, GovernanceDecision, or ReproducibilityBadge
- `get_validation_request_for_data_hash` — resolves ValidationRequest from study path anchor by data hash
- `InstitutionPath` index — validators indexed by institution for conflict-of-interest detection (`get_validators_for_institution`)
- `DisciplinePath` attestation index — attestations indexed by discipline for cross-study analytics (`get_attestations_for_discipline`)
- Validator self-assignment (`StudyClaim`) — validators claim studies from the queue via `claim_study(request_ref)`; coordinator enforces capacity and duplicate checks; integrity zome's `validate()` enforces conflict-of-interest (same institution as researcher → rejected); `release_claim` frees the slot while preserving the audit record
- Dropout recovery — `reclaim_abandoned_claim` frees a slot held by a validator who has gone dark (any participant, after configurable timeout); `force_finalize_round` closes a stuck round after 7 days subject to `min_attestations_for_finalization` (governance DNA property — set equal to panel size for ≤4-validator panels, one lower for larger panels), producing a normal HarmonyRecord identifiable as reduced-quorum by validator count
- Security protocol guards — duplicate attestation rejection, duplicate commitment rejection, researcher commitment idempotency, reclaim timeout floor enforcement, force_finalize_round conservative abort

---

## 🔐 The Blind Commit-Reveal Protocol — Fully Symmetric (March 2026)

> **This is the core anti-gaming guarantee that makes ValiChord different from every other reproducibility system.**
>
> For the first time, a computational reproducibility system provides cryptographic proof of three things simultaneously:
> - Validators could not see each other's findings before committing their own
> - The researcher could not change their claimed results after seeing any validator's findings
> - The comparison of researcher-declared values against validator-reproduced values is cryptographically genuine — not self-reported or trust-based
>
> Neither party can move the goalposts. The envelopes are sealed before anyone opens theirs.

The protocol is implemented across all four DNAs and is fully tested:

0. **Researcher seals result** *(at submission, months before validators begin)* — `lock_researcher_result` in DNA 1 generates a 32-byte random nonce, computes `commitment_hash = SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores the structured metrics and nonce as a private `LockedResult` entry that never leaves the researcher's device, and automatically publishes only the hash to DNA 3 as a `ResearcherResultCommitment`. Validators can verify this commitment exists before accepting a study — the researcher is bound to their result from day one.
1. **Validators commit** — each validator seals their private assessment as a `ValidatorPrivateAttestation` in their own DNA 2 workspace. `seal_private_attestation` generates a random nonce and computes `commitment_hash = SHA-256(msgpack(ValidationAttestation) || nonce)`. The entry — including the nonce — never leaves their machine.
2. **Anchors published** — DNA 2's `post_commit` automatically calls `notify_commitment_sealed()` in DNA 3, writing a public `CommitmentAnchor` to the shared DHT containing the `commitment_hash`. Everyone can verify the commitment happened and that it is cryptographically bound to a specific assessment — but the assessment content remains hidden.
3. **Phase opens** — when all expected `CommitmentAnchor` entries are present, DNA 3 writes a `PhaseMarker(RevealOpen)` to the DHT. Validators discover this by polling, not by signal — ensuring no validator is disadvantaged by network latency.
4. **Dual reveal** *(both parties simultaneously)* — validators submit their public `ValidationAttestation` entries to DNA 3 (immutable after publication). The researcher retrieves their private `LockedResult` from DNA 1 and calls `reveal_researcher_result` in DNA 3, which verifies `SHA-256(rmp_serde::to_vec_named(metrics) || nonce) == result_commitment_hash` **on-chain** and writes an immutable `ResearcherReveal` entry to the DHT. Neither party can see the other's content before committing to their own.
5. **Harmony** — once all attestations are present, DNA 4 assembles a `HarmonyRecord` on the public DHT, assesses agreement, and optionally issues a `ReproducibilityBadge`. The researcher's verified `ResearcherReveal` metrics and each validator's `produced_value` fields are both on the public DHT — the comparison is genuine and independently verifiable by anyone.

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

## 🗺️ Landscape: Where ValiChord Fits

ValiChord is not a replacement for existing reproducibility tools — it is the coordination, governance, and certification layer that those tools operate within.

| Project / Tool | Focus Area | Validation Model | Incentives | Governance | Integration | Tamper-Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ValiChord** | Distributed validation | Multi-party, Harmony Records | ✅ Yes | Transparent, anti-capture | Journals, Funders, Repos | ✅ Yes |
| Binder | Reproducible environments | Single execution | ❌ No | N/A | Repos | ❌ No |
| Code Ocean | Executable capsules | Single execution | ❌ No | Proprietary | Journals | ❌ No |
| FLINC | Reproducibility packaging | Single execution | ❌ No | N/A | Repos | ❌ No |
| PTU | Process tracing | Single execution | ❌ No | N/A | Repos | ❌ No |
| ReproZip | Packaging and portability | Single execution | ❌ No | N/A | Repos | ❌ No |
| RenkuLab | Collaborative science | Single/multi execution | ❌ No | N/A | Repos | ❌ No |
| Sciunit | Reproducibility packaging | Single execution | ❌ No | N/A | Repos | ❌ No |
| Whole Tale | Data-driven science | Single/multi execution | ❌ No | N/A | Repos | ❌ No |

*Landscape based on benchmarking by [Zenodo:15167233](https://zenodo.org/records/15167233) (2025), which evaluated these tools against 18 real computational experiments across multiple disciplines.*

Every existing tool facilitates reproducibility — making it easier to run code, package environments, or share data. None of them verify that independent validators reached the same conclusion, preserve disagreement as a first-class output, compensate validators for their work, or resist institutional pressure to soften findings. That is the gap ValiChord fills.

---

## 🛠️ Researcher Ecosystem: "ValiChord at Home"

We provide a full feedback pipeline to move research from "messy" to "validatable".

### 🏠 **ValiChord at Home (Self-Service)**
**Private, local pre-vetting for researchers.**
Before submitting for formal validation, researchers use this tool to scan their repositories privately.
- **Static Analysis:** Identifies documentation gaps and environment friction without code execution.
- **Difficulty Prediction:** Stage B (post-Phase 0) will use an empirically calibrated rubric to estimate validation labour. Stage A (current prototype) provides best-practice gap analysis without scoring.

👉 **[Launch ValiChord at Home](https://topeuph-ai.github.io/ValiChord/demo)**

### 🔍 **Assisted Correction**
**Automated reproducibility hygiene.**
ValiChord generates proposed corrections — drafted READMEs, pinned dependencies — for researcher review and approval.

---

## 📚 Document Library

### Understanding ValiChord

| Document | Description |
| :--- | :--- |
| [Vision & Architecture v13](https://github.com/topeuph-ai/ValiChord/blob/main/docs/1_ValiChord_Vision&Architecture.md) | What ValiChord is and why it matters |
| [Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md) | How the system resists corruption |
| [Harmony Records](https://github.com/topeuph-ai/ValiChord/blob/main/docs/10_Harmony_Records.md) | What a Harmony Record is and why it matters |
| [How a Validation Round Works](https://github.com/topeuph-ai/ValiChord/blob/main/docs/15_How_a_Validation_Round_Works.md) | Step-by-step narrative from submission to Harmony Record |
| [Validator Guide](https://github.com/topeuph-ai/ValiChord/blob/main/docs/16_ValiChord_Validator_Guide.md) | What it means to be a ValiChord validator |
| [Why Holochain?](https://github.com/topeuph-ai/ValiChord/blob/main/docs/11_Why_Holochain?.md) | Non-technical explanation of the architectural choice |
| [Other Potential Use Cases](https://github.com/topeuph-ai/ValiChord/blob/main/docs/12_Other_potential_use_cases.md) | Where else the ValiChord pattern applies |
| [ValiChord at Home](https://github.com/topeuph-ai/ValiChord/blob/main/docs/9_Valichord_at_Home.md) | Self-service reproducibility tool for researchers |

### Architecture

| Document | Description |
| :--- | :--- |
| [4-DNA Architecture — Technical](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7_ValiChord_4-DNA_architecture_technical.md) | Full technical architecture document for engineers |
| [4-DNA Architecture — Plain English](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7a_ValiChord_4-DNA_architecture_nontechnical.md) | Non-technical explanation of the four-membrane design |
| [Eight-Layer Infrastructure](https://github.com/topeuph-ai/ValiChord/blob/main/docs/8_ValiChord_8_Layer_Infrastructure_and_Harmony_Records.md) | The full eight-layer conceptual architecture |
| [Technical Reference v21](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md) | Full architectural narrative and engineering reference |
| [Architecture Scaffold v13 (Rust)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs) | Single-file representation of the four-DNA architecture |

### Integrations

| Document | Description |
| :--- | :--- |
| [Integration Guide](https://github.com/topeuph-ai/ValiChord/blob/main/docs/INTEGRATION_GUIDE.md) | REST API integration guide for any tool — curl, Python, TypeScript examples, webhooks |
| [OpenAPI 3.0 Spec](https://github.com/topeuph-ai/ValiChord/blob/main/backend/openapi.yaml) | Machine-readable API spec; served live at `GET /openapi.yaml` |
| [Feynman Integration Vision](https://github.com/topeuph-ai/ValiChord/blob/main/feynman_integration/INTEGRATION_VISION.md) | Full design: how Feynman AI agent uses ValiChord, what's live, open work and decisions |
| [Feynman Integration Status](https://github.com/topeuph-ai/ValiChord/blob/main/feynman_integration/README.md) | One-page status table |
| [Nondominium Integration Vision](https://github.com/topeuph-ai/ValiChord/blob/main/nondominium_integration/INTEGRATION_VISION.md) | Design for ValiChord × Nondominium (Sensorica) open-value accounting |
| [Nondominium Integration Status](https://github.com/topeuph-ai/ValiChord/blob/main/nondominium_integration/README.md) | Status and open design decisions |

### Funding & Research

| Document | Description |
| :--- | :--- |
| [Phase 0 Proposal v3.1](https://github.com/topeuph-ai/ValiChord/blob/main/docs/5_ValiChord_Phase_0_proposal_ukri_etc.md) | UKRI Metascience Round 2 funding proposal |
| [Open Design Questions](https://github.com/topeuph-ai/ValiChord/blob/main/docs/6_ValiChord_Open_Design_Questions.md) | Outstanding design decisions and open questions |

---

## 🔧 For Developers

The four-DNA Holochain infrastructure is built and integration-tested. The codebase is available for technical review.

| Resource | Link |
| :--- | :--- |
| Codebase (Rust / Holochain) | [`valichord/`](https://github.com/topeuph-ai/ValiChord/tree/main/valichord) |
| Test suite + build instructions | [`valichord/tests/README.md`](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/tests/README.md) |
| Architecture Scaffold v12 | [`docs/4_ValiChord_RUST_Scaffold.rs`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs) |
| Technical Architecture | [`docs/7_ValiChord_4-DNA_architecture_technical.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7_ValiChord_4-DNA_architecture_technical.md) |
| Technical Reference v21 | [`docs/3_ValiChord_Technical_Reference.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md) |
| Engineer Handover | [`docs/13_Valichord_Engineer_Handover.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/13_Valichord_Engineer_Handover.md) |

### ⚡ Quickstart — clone to passing tests

```bash
# 1. Prerequisites
rustup target add wasm32-unknown-unknown
cargo install holochain hc lair_keystore --locked

# 2. Clone and build
git clone https://github.com/topeuph-ai/ValiChord.git
cd ValiChord/valichord
cargo build --target wasm32-unknown-unknown --release

# 3. Pack the four DNAs and bundle the hApp
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna
hc app pack .                           -o workdir/valichord.happ

# 4. Run the integration tests
cd tests && npm install
pkill -f holochain; pkill -f lair-keystore; sleep 2
npm test
```

> For full build details, troubleshooting, and test architecture see the **[Developer Guide wiki](https://github.com/topeuph-ai/ValiChord/wiki/Developer-Guide)**.

> **Running the demo:** `bash demo/start.sh` starts the full stack — Holochain conductor, Node.js bridge, and Flask REST API on port 5000. `bash demo/start-gateway.sh` starts the HTTP Gateway on port 8090, making Harmony Record links publicly verifiable. See [`demo/`](https://github.com/topeuph-ai/ValiChord/tree/main/demo) for full instructions.

> **Note:** There is no end-user UI yet — that is Phase 1. The current interface is a developer demo and integration endpoint. If you are a Holochain engineer interested in contributing, please get in touch: [topeuph@gmail.com](mailto:topeuph@gmail.com)

---

## 📊 Roadmap

| Phase | Focus | Status |
| :--- | :--- | :--- |
| **Phase 0** | **Workload Discovery:** Empirical study to quantify the true cost of validation. ~£158K FEC, 12 months. | **Proposed — UKRI Metascience Round 2 (April 2026)** |
| **Phase 1** | **Full MVP:** UI layer, researcher and validator dashboards, live network deployment. | **Infrastructure and integration layer complete — awaiting Phase 0 funding** |
| **Phase 2** | **Integration at scale:** Always-on hosting, journal and funder API deployments, persistent AI validator nodes. | **Feynman integration live (demo). REST API open: API keys, webhooks, OpenAPI spec, Swagger UI. HTTP Gateway working. Nondominium integration in design.** |

---

ValiChord is built on Holochain — an end-to-end open-source agent-centric P2P application framework.

<a href="https://holochain.org">
<img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/holochain%20logo.png?raw=true" width="750" alt="Holochain Logo">
</a>

---

**Author:** Ceri John &nbsp;•&nbsp; **Contact:** [topeuph@gmail.com](mailto:topeuph@gmail.com)

**Technical Review:** Arthur Brock (Holochain co-founder), Paul D'Aoust (Holochain Foundation), Joel Marcey (Rust Foundation)

**License: ValiChord is open source under the Apache License 2.0. You are free to use, modify, and distribute this software, including in commercial products, provided you retain the copyright notice and license text.**
