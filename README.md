<div align="center">

<img src="Images/Valichord logo-standard v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">

**An Immune System for Science: Distributed Integrity Infrastructure for Scientific Research**

[![CI](https://github.com/topeuph-ai/ValiChord/actions/workflows/ci.yml/badge.svg)](https://github.com/topeuph-ai/ValiChord/actions/workflows/ci.yml)
[![Status](https://img.shields.io/badge/Status-Integration_Ready-brightgreen?style=for-the-badge)](https://topeuph-ai.github.io/ValiChord)
[![Language](https://img.shields.io/badge/Language-Rust-orange?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/)
[![Tests](https://img.shields.io/badge/Tests-158_pass_%7C_1_skipped-brightgreen?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/valichord/tests/)
[![Commit--Reveal](https://img.shields.io/badge/Commit--Reveal-Fully_Symmetric-blue?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/README.md#-the-blind-commit-reveal-protocol)
[![Grant](https://img.shields.io/badge/Grant-UKRI_Metascience_2-purple?style=for-the-badge)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/5_ValiChord_Phase_0_proposal_ukri_etc.md)

---

## 🎬 **[▶ Watch the demo on YouTube](https://www.youtube.com/watch?v=DinSdR-U114&feature=youtu.be)**
**3 AI validators + researcher commit blind, reveal simultaneously — both sides hash-verified on the live Holochain network. Permanent public record. No auth required.**

**[Full technical walkthrough →](https://github.com/topeuph-ai/ValiChord/blob/main/demo/DECENTRALISED_DEMO.md)**

---

## 🐳 **New: Decentralised Demo — 5 Isolated Conductors (April 2026)**

> **The full protocol now runs across genuinely isolated nodes with no shared state.**

Five Docker containers — one researcher, three validators, one kitsune2 bootstrap server — each run their own Holochain conductor with their own keypair and their own SQLite database. The only communication channel is the DHT. This is the closest a single-machine setup can get to a real multi-party deployment.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
docker compose -f demo/docker-compose.yml up --build -d
python3 demo/ai_validator.py --mode decentralised
```

**[Decentralised demo guide →](https://github.com/topeuph-ai/ValiChord/blob/main/demo/DECENTRALISED_DEMO.md)**

---

## 📖 [**Primary Entry Point: Vision & Architecture**](https://github.com/topeuph-ai/ValiChord/blob/main/docs/1_ValiChord_Vision&Architecture.md)
*The core vision: Why ValiChord matters and how it solves the $200B verification gap.*

---

[ **[Project Website](https://topeuph-ai.github.io/ValiChord)** ] &nbsp;•&nbsp; [ **[Governance Framework](https://github.com/topeuph-ai/ValiChord/blob/main/docs/2_ValiChord_Governance_Framework.md)** ] &nbsp;•&nbsp; [ **[4-DNA Architecture](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7_ValiChord_4-DNA_architecture_technical.md)** ] &nbsp;•&nbsp; [ **[ValiChord at Home](https://github.com/topeuph-ai/valichord_at_home)** ]

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

## 🔐 Trust & Identity Model

ValiChord's security model is **institutional, not algorithmic**. Sybil resistance is not achieved through staking, proof-of-work, or token economics. It is achieved through **membrane proofs**: every validator must present a cryptographically signed joining certificate issued by a trusted credentialing authority before their attestations are accepted by the network.

This means:

- The validator set is **permissioned** — open participation is deliberately excluded
- Real-world identity is bound to on-chain agent keys at the membrane boundary
- A validator cannot meaningfully multiply their influence by creating additional identities, because each identity requires a new institutional credential
- All commit-reveal commitments and attestations are therefore attributable to a verified real-world entity

ValiChord does not attempt to solve Sybil resistance in an open network. It delegates identity assurance to institutional credentialing — the appropriate mechanism for high-integrity scientific and regulatory validation contexts.

### Credential Issuance & Governance

The credentialing authority is set via the `authorized_joining_certificate_issuer` DNA property at network instantiation.

**Phase 0 (current):** Certificate issuance is operated by ValiChord as a single trusted authority. This is a deliberate bootstrap choice — establishing a known, accountable issuer before governance infrastructure matures — rather than an architectural limitation.

**Phase 1 roadmap:** Credential issuance will be extended to support multiple issuers (e.g. journals, funders, professional bodies) and governance-controlled issuer rotation, allowing institutional participants to federate trust without depending on a single point of authority. Issuer compromise in Phase 0 is mitigated by the fact that issued certificates are agent-key-bound and cannot be transferred; a compromised issuer can mint new certificates but cannot retroactively alter existing attestation records on the DHT.

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
│   ├── security.test.ts             — 9 tests
│   └── validator_workspace.test.ts   — 7 tests
└── happ.yaml               — all four DNA roles bundled
```

**158 integration tests passing across two suites (94 Tryorama, 64 Rust sweettest), 1 skipped.** The system is also integration-ready: a REST API (`POST /validate`, `GET /result/<job_id>`) connects the analysis pipeline to the live Holochain network, and a working HTTP Gateway exposes Harmony Records as publicly verifiable links. The API supports API key authentication, webhook callbacks, and a full [OpenAPI 3.0 spec](backend/openapi.yaml) with Swagger UI at `GET /docs`. Any tool that can make an HTTP request can integrate.
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
- Security protocol guards — duplicate attestation rejection, duplicate commitment rejection, researcher commitment idempotency, reclaim timeout floor enforcement, force_finalize_round conservative abort, self-claim prevention (researcher cannot validate own study — no dev bypass), researcher reveal authorisation, PhaseMarker write idempotency (TOCTOU-safe), deterministic link resolution (all `links.last()` → `max_by_key(timestamp)`), O(N) DHT round-trip elimination in claim functions
- Conductor-free unit tests for pure outcome functions (`derive_majority_outcome`, `derive_agreement_level`) in `shared_types` — run in < 1 s with `cargo test -p valichord_shared_types`
- Native Rust sweettest suite (`valichord/sweettest_integration/`) in 5 parallel CI matrix jobs alongside Tryorama

---

## 🔐 The Blind Commit-Reveal Protocol — Fully Symmetric (March 2026)

> **This is the core anti-gaming guarantee that makes ValiChord different from every other reproducibility system.**
>
> For the first time, a computational reproducibility system provides cryptographic proof of four things simultaneously:
> - Validators could not see each other's findings before committing their own
> - Validators could not see the researcher's claimed values before forming their own verdict — only the commitment hash is visible during the commit phase, preventing anchoring or bias
> - The researcher could not change their claimed results after seeing any validator's findings
> - The comparison of researcher-declared values against validator-reproduced values is cryptographically genuine — not self-reported or trust-based
>
> Neither party can move the goalposts. The envelopes are sealed before anyone opens theirs.

The protocol is implemented across all four DNAs and is fully tested:

0. **Researcher seals result** *(at submission, months before validators begin)* — `lock_researcher_result` in DNA 1 generates a 32-byte random nonce, computes `commitment_hash = SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores the structured metrics and nonce as a private `LockedResult` entry that never leaves the researcher's device, and automatically publishes only the hash to DNA 3 as a `ResearcherResultCommitment`. Validators can verify this commitment exists before accepting a study — the researcher is bound to their result from day one. Critically, only the hash is published: validators cannot see the actual metric values until after they have committed their own verdicts, preventing anchoring bias.
1. **Validators commit** — each validator seals their private assessment as a `ValidatorPrivateAttestation` in their own DNA 2 workspace. `seal_private_attestation` generates a random nonce and computes `commitment_hash = SHA-256(msgpack(ValidationAttestation) || nonce)`. The entry — including the nonce — never leaves their machine.
2. **Anchors published** — DNA 2's `post_commit` automatically calls `notify_commitment_sealed()` in DNA 3, writing a public `CommitmentAnchor` to the shared DHT containing the `commitment_hash`. Everyone can verify the commitment happened and that it is cryptographically bound to a specific assessment — but the assessment content remains hidden.
3. **Phase opens** — when all expected `CommitmentAnchor` entries are present, DNA 3 writes a `PhaseMarker(RevealOpen)` to the DHT. Validators discover this by polling, not by signal — ensuring no validator is disadvantaged by network latency.
4. **Dual reveal** *(both parties simultaneously)* — the researcher calls `reveal_researcher_result` in DNA 3, which verifies `SHA-256(rmp_serde::to_vec_named(metrics) || nonce) == result_commitment_hash` **on-chain** and writes an immutable `ResearcherReveal` to the DHT. Each validator retrieves their sealed nonce from DNA 2 via `get_private_attestation_for_task` and calls `submit_attestation` in DNA 3, which verifies `SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash` **on-chain**. Neither party can reveal different values than they committed to, and neither could see the other's committed content before committing their own.
5. **Harmony** — once all attestations are present, DNA 4 assembles a `HarmonyRecord` on the public DHT, assesses agreement, and optionally issues a `ReproducibilityBadge`. The researcher's verified `ResearcherReveal` metrics and each validator's `produced_value` fields are both on the public DHT — the comparison is genuine and independently verifiable by anyone. Badge tiers (Gold ≥ 7, Silver ≥ 5, Bronze ≥ 3 validators) reflect agreement level and participant count. **Phase 0 note:** validator experience is not yet tracked in production — see the Architecture doc for the Phase 0 badge caveat.

---

## 🤖 Live Demo — AI Validators Running the Full Protocol

> **This is not a simulation.** Every step involves real zome calls to real Holochain DNA cells. The HarmonyRecord is stored on a live distributed network and readable at a public URL — no Holochain node, no API key, no authentication required.
>
The demo runs the complete ValiChord protocol end-to-end, with Claude AI agents as the validators:

1. A **synthetic study** is loaded — a real linear regression on 20 data points (temperature variability vs species richness index). The mathematics are genuine: `study.py` computes the OLS slope, intercept, and R² from first principles in pure Python with no external dependencies. The numbers it produces — slope 2.4086, intercept 1.1742, R² 0.9991 — are deterministic and independently verifiable.
2. The **researcher seals a cryptographic commitment** to their result metrics before any validator has seen them. Only the hash leaves their private DNA. They are bound to their claim from this point forward.
3. **Three independent Claude AI agents** each receive the study README and the actual execution output and form their own verdict — `Reproduced`, `PartiallyReproduced`, `FailedToReproduce`, or `UnableToAssess` — with confidence level and one-sentence reasoning. Each call is made separately; the agents do not see each other's verdicts.
4. All three validators **seal their verdicts blind** to the shared DHT as commitment anchors. The actual content remains hidden.
5. A **phase gate** opens automatically when all three commitment anchors are confirmed on the DHT.
6. **Both sides reveal simultaneously, both hash-verified on the Holochain network**: `reveal_researcher_result` verifies the researcher's metrics against their sealed commitment hash. Each validator's `submit_attestation` verifies their attestation against their `CommitmentAnchor` hash. Neither side can reveal different values than they committed to.
7. A **HarmonyRecord** is written to the public Governance DHT. It is immediately readable at a shareable URL — clean JSON, no credentials required.

The result of a recent run:

```json
{
  "harmony_record_hash": "uhC8keNXEqhp2moKLAgREgood7hy-V4vRl9U4pqFpJenMfVOFtOsr",
  "outcome":         { "type": "Reproduced" },
  "agreement_level": "ExactMatch",
  "discipline":      { "type": "ComputationalBiology" },
  "validator_count": 3
}
```

The whole run takes about 4–5 minutes.

📄 **[Full demo guide →](https://github.com/topeuph-ai/ValiChord/blob/main/demo/DECENTRALISED_DEMO.md)**

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

## 🔑 Configurable Trust

ValiChord's trust model is set by the deployment, not by the protocol. The membrane proof system is a dial: operators configure the credential threshold appropriate to their context, and the protocol runs identically regardless of where that dial is set.

Some contexts demand high bars. Scientific reproducibility validation requires credentialed evaluators — you cannot allow unverified agents to attest whether a genomics workflow reproduces correctly, or whether an AI system's capability claim holds. The integrity of the record depends on the institutional standing of those who sign it.

Other contexts call for openness. Community fact-checking, citizen science, and decentralised forecasting may configure minimal credential requirements or none at all — broad participation is a feature, not a liability.

As ValiChord is adopted across domains, each deployment will calibrate this dial to its own trust requirements. The protocol — blind commit, DHT-anchored reveal, immutable Harmony Record — is the same in every case. Only the membrane configuration changes.

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

## 🛠️ Researcher Ecosystem: ValiChord at Home

Before submitting for formal validation, researchers use **[ValiChord at Home](https://github.com/topeuph-ai/valichord_at_home)** to scan their deposit privately — 100+ automated checks for documentation gaps, hardcoded paths, missing dependencies, absent data dictionaries, and more. It generates proposed corrections (drafted READMEs, pinned requirements) for researcher review.

ValiChord at Home is a standalone tool in its own repository. It does not run the commit-reveal protocol — it is a pre-flight check that helps researchers make their deposits validatable.

👉 **[ValiChord at Home →](https://github.com/topeuph-ai/valichord_at_home)**

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
| [ValiChord at Home](https://github.com/topeuph-ai/valichord_at_home) | Self-service deposit quality checker — 100+ automated checks, draft generation |

### Architecture

| Document | Description |
| :--- | :--- |
| [4-DNA Architecture — Technical](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7_ValiChord_4-DNA_architecture_technical.md) | Full technical architecture document for engineers |
| [4-DNA Architecture — Plain English](https://github.com/topeuph-ai/ValiChord/blob/main/docs/7a_ValiChord_4-DNA_architecture_nontechnical.md) | Non-technical explanation of the four-membrane design |
| [Eight-Layer Infrastructure](https://github.com/topeuph-ai/ValiChord/blob/main/docs/8_ValiChord_8_Layer_Infrastructure_and_Harmony_Records.md) | The full eight-layer conceptual architecture |
| [Technical Reference v27](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md) | Full architectural narrative and engineering reference |
| [Architecture Scaffold v13 (Rust)](https://github.com/topeuph-ai/ValiChord/blob/main/docs/4_ValiChord_RUST_Scaffold.rs) | Single-file representation of the four-DNA architecture |

### Integrations

| Document | Description |
| :--- | :--- |
| [Deployment Checklist](https://github.com/topeuph-ai/ValiChord/blob/main/docs/DEPLOYMENT_CHECKLIST.md) | All DNA properties, dev/test bypass values, production requirements, and misconfiguration failure modes |
| [Integration Guide](https://github.com/topeuph-ai/ValiChord/blob/main/docs/INTEGRATION_GUIDE.md) | REST API integration guide for any tool — curl, Python, TypeScript examples, webhooks |
| [OpenAPI 3.0 Spec](https://github.com/topeuph-ai/ValiChord/blob/main/backend/openapi.yaml) | Machine-readable API spec; served live at `GET /openapi.yaml` |
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
| Technical Reference v27 | [`docs/3_ValiChord_Technical_Reference.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/3_ValiChord_Technical_Reference.md) |
| Deployment Checklist | [`docs/DEPLOYMENT_CHECKLIST.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/DEPLOYMENT_CHECKLIST.md) |
| Engineer Handover | [`docs/13_Valichord_Engineer_Handover.md`](https://github.com/topeuph-ai/ValiChord/blob/main/docs/13_Valichord_Engineer_Handover.md) |

Integration partners, domain validators (HPC, clinical, environmental), and frontend contributors are equally welcome — the protocol is language-agnostic and the REST API is the entry point for non-Rust contributors.

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

> **Running the demo:** See [`demo/DECENTRALISED_DEMO.md`](https://github.com/topeuph-ai/ValiChord/blob/main/demo/DECENTRALISED_DEMO.md) for full instructions.

> **Note:** There is no end-user UI yet — that is Phase 1. The current interface is a developer demo and integration endpoint. If you are a Holochain engineer interested in contributing, please get in touch: [topeuph@gmail.com](mailto:topeuph@gmail.com)

---

## 📊 Roadmap

| Phase | Focus | Status |
| :--- | :--- | :--- |
| **Phase 0** | **Workload Discovery:** Empirical study to quantify the true cost of validation. ~£158K FEC, 12 months. | **Proposed — UKRI Metascience Round 2 (April 2026)** |
| **Phase 1** | **Full MVP:** UI layer, researcher and validator dashboards, live network deployment. | **Infrastructure and integration layer complete — awaiting Phase 0 funding** |
| **Phase 2** | **Integration at scale:** Always-on hosting, journal and funder API deployments, persistent AI validator nodes. | **REST API open: API keys, webhooks, OpenAPI spec, Swagger UI. HTTP Gateway working. Nondominium integration in design.** |

---

ValiChord is built on Holochain — an end-to-end open-source agent-centric P2P application framework.

<a href="https://holochain.org">
<img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/holochain%20logo.png?raw=true" width="750" alt="Holochain Logo">
</a>

---

**Author:** Ceri John &nbsp;•&nbsp; **Contact:** [topeuph@gmail.com](mailto:topeuph@gmail.com)

**Technical Review:** Arthur Brock (Holochain co-founder), Paul D'Aoust (Holochain Foundation), Joel Marcey (Rust Foundation)

**License: ValiChord is open source under the Apache License 2.0. You are free to use, modify, and distribute this software, including in commercial products, provided you retain the copyright notice and license text.**
