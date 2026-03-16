# ValiChord: Engineer Handover Document

**Version:** 1.5 — March 2026
**Author:** Ceri John
**Status:** Current — reflects codebase as of last commit

---

## Overview

This document is for any engineer picking up the ValiChord codebase. It covers what is built and tested, what is stubbed and why, known constraints and hard-won lessons, the build sequence, and decisions that have been deferred to Phase 1.

Read this before touching the code.

---

## What Is Built

ValiChord is a four-DNA Holochain hApp — four independent peer-to-peer networks running simultaneously on each participant's conductor, communicating via same-agent `call(OtherRole(...))` calls.

The infrastructure is complete in the sense that matters: it compiles, the four DNAs pack into a single `.happ` bundle, and 87 integration tests pass against live Holochain conductors via Tryorama. One test is skipped for hardware reasons (see below). As of 2026-03-14, all four DNAs have been reviewed and optimised — see the constraint list below for the key decisions made.

### DNA 1 — Researcher Repository
**Status: Complete**

Private, single-agent DNA. Stores all research artefacts locally — code, data, protocols, snapshots. Nothing leaves except a SHA-256 `ExternalHash` passed manually by the researcher when submitting a validation request.

All entry types are `visibility = "private"`. No DHT. No membrane proof required.

`PreRegisteredProtocol` is immutable after creation — updates and deletes are rejected in `validate()`. This is enforced and tested.

`compute_data_hash` uses `sha2::Sha256` and returns a 39-byte `ExternalHash` via `ExternalHash::from_raw_32()`.

`get_all_studies()` returns all `ResearchStudy` records from the local source chain using `query()` + deserialization filter. Same pattern as `get_all_tasks` in DNA 2.

---

### DNA 2 — Validator Workspace
**Status: Complete**

Private, single-agent DNA. The commit phase of the blind commit-reveal protocol lives here. Each validator runs one instance. The private assessment is sealed here as `ValidatorPrivateAttestation` and never leaves.

`ValidatorPrivateAttestation` is immutable after creation — tested.

**Critical:** `post_commit` fires `call(OtherRole("attestation"), "notify_commitment_sealed")` after a `ValidatorPrivateAttestation` is created. This is the only outward communication from DNA 2. The target attestation cell must be initialised before `post_commit` fires — see the deadlock section below.

`get_all_private_attestations()` returns all `ValidatorPrivateAttestation` records from the local source chain using `query()` + deserialization filter. Parallel to `get_all_tasks`.

---

### DNA 3 — Attestation
**Status: Complete**

Shared DHT, credentialed membrane. The most complex DNA. Manages the full commit-reveal protocol, phase transitions, and public attestation records.

**Membrane proof:** Real Ed25519 verification is implemented in the **coordinator** `init()`, not the integrity zome. The integrity zome does format-only checks (≥64 bytes). The coordinator queries the source chain for `AgentValidationPkg`, reads `authorized_joining_certificate_issuer` from DNA properties, and calls `verify_signature()`. Empty string in DNA properties = dev/test bypass.

**Phase transitions** are DHT-poll-driven, not signal-driven. `get_current_phase()` is the authoritative source of phase state. Signals are send-and-forget notifications only — do not use them as protocol gates.

`CommitmentAnchor`, `PhaseMarker`, and `ValidationAttestation` are all immutable after creation — enforced in `validate()` and tested.

`get_validation_request_for_data_hash(data_hash: ExternalHash)` is a public extern registered in `init()`. It resolves a `ValidationRequest` record from the `study.{data_hash}` path. Used by DNA 4 to identify the researcher (record author) when issuing a `ReproducibilityBadge`.

**`ValidationRequest` carries two new pointer fields** added 2026-03-14: `data_access_url: String` (URL where validators download the dataset — OSF, Zenodo, institutional repo, etc.) and `protocol_access_url: Option<String>` (DOI or URL of the pre-registered analysis plan). The actual data never touches the DHT — these are pointers only. The researcher fills these from their private DNA before calling `submit_validation_request`.

**Governance DNA is now fully decentralised** (2026-03-14): `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation` are no longer author-gated by a designated coordinator key. Any participant who was part of the round can trigger finalisation by calling `check_and_create_harmony_record`. The function enforces completeness (must have ≥ `num_validators_required` attestations before writing) and idempotency (a second call short-circuits if a record already exists). `submit_attestation` in the Attestation DNA now automatically fires a same-agent cross-DNA call to `check_and_create_harmony_record` — the last validator to submit their attestation triggers the HarmonyRecord write without any central coordinator node.

`GovernanceDecision` remains key-gated by `system_coordinator_key` — governance votes are human deliberation outcomes that require a designated recorder. `harmony_record_creator_key` has been removed from `DnaProperties` entirely.

**Known remaining limitation (Phase 1):** the Governance integrity zome's `validate()` cannot perform cross-DNA lookups to cryptographically verify that a HarmonyRecord's content is correct against the Attestation DHT. Content correctness is currently enforced at the coordinator layer (completeness check + algorithmic derivation) but not at the network validation layer. Making it trustless at the validation layer requires either moving HarmonyRecord creation into the Attestation DNA or embedding sufficient proof in the entry itself.

`required_validations = 7` is set on `ValidationAttestation`. This is a Holochain DHT validation parameter — it means 7 peers must validate the entry before it is considered fully integrated.

**Validator self-assignment (`StudyClaim`)** — implemented 2026-03-14. Validators discover studies via `get_pending_requests_for_discipline` and call `claim_study(request_ref: ExternalHash)` to self-assign without any central matchmaker. The coordinator resolves the `ValidationRequest` ActionHash via the `StudyToValidation` path, reads the validator's institution from their `ValidatorProfile`, enforces capacity (no more than `num_validators_required` claims per study) and duplicate (no double-claiming) at the coordinator layer, then writes a `StudyClaim` entry plus two link indexes — `RequestToClaim` (base = request_ref, for `get_claims_for_request`) and `ValidatorToClaim` (base = agent pubkey, for `get_my_claimed_studies`). The integrity zome's `validate()` enforces conflict-of-interest at the network layer: if both `validator_institution` and `researcher_institution` are non-empty and equal, the claim is rejected. `release_claim(request_ref)` deletes both links (freeing the slot for another validator); the `StudyClaim` entry remains permanently as an audit record. Empty institution on either side bypasses the COI check (dev mode / researcher did not declare institution). `ValidationRequest` now also carries `researcher_institution: String` alongside the pointer fields `data_access_url` and `protocol_access_url`.

**Dropout recovery** — implemented 2026-03-14. `reclaim_abandoned_claim(input: { request_ref, claim_hash, timeout_secs })` is callable by any participant. It verifies the claim is older than `timeout_secs` AND the absent validator has not attested, then deletes both link indexes to free the slot. Use `timeout_secs = 604800` (7 days) in production; `0` in tests. The companion function `force_finalize_round(request_ref)` in DNA 4 closes a round still stuck after `ROUND_TIMEOUT_SECS` (7 days, hardcoded constant) with whatever attestations are present, subject to `min_attestations_for_finalization` (see governance `DnaProperties`). Neither function requires special keys — both are open to any participant, consistent with the decentralised governance model.

**`check_all_commitments_sealed_inner` fix** — 2026-03-16. Previously used `props.minimum_validators` (network-wide DNA property) to decide when to open the reveal window. Now calls `get_num_validators_required(request_ref)` which reads `num_validators_required` from the actual `ValidationRequest` entry. The phase transition now opens when the correct number of validators *for that specific study* have committed, not the network minimum.

---

### DNA 4 — Governance & Harmony Records
**Status: Complete**

Public DHT, HTTP Gateway target. Stores final outcomes — Harmony Records, Reproducibility Badges, validator reputation, governance decisions.

Write access is decentralised: `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation` are open to any participant — no author key required. `GovernanceDecision` is the sole exception, gated by `system_coordinator_key` in `validate()` (human deliberation outcomes need a designated recorder). Empty string = dev/test bypass. `harmony_record_creator_key` has been removed from `DnaProperties` entirely.

**`DnaProperties`** (governance) contains two fields: `system_coordinator_key: String` (gates GovernanceDecision writes) and `min_attestations_for_finalization: u32` (minimum attestations required before `force_finalize_round` will write a HarmonyRecord). Policy: set equal to `minimum_validators` for panels of ≤4 validators (no dropout tolerated — governance decides); set to `minimum_validators - 1` for larger panels (one dropout tolerated, auto-finalises after timeout). Value `0` falls back to requiring at least one attestation (safe dev/test default).

`HarmonyRecord`, `ReproducibilityBadge`, and `GovernanceDecision` are immutable. `ValidatorReputation` allows updates (no key gate — updated automatically during round finalisation).

**No self-reported timestamps.** `HarmonyRecord`, `ValidatorReputation`, and `ReproducibilityBadge` do not store `created_at_secs`, `last_updated_secs`, or `issued_at_secs` fields. These were removed because Holochain Actions carry an authoritative, tamper-evident timestamp — self-reported timestamps in entry content are falsifiable and redundant. Do not add them back.

**Badge recipient is the researcher, not the first validator.** `ReproducibilityBadge.issued_to` is resolved via a cross-DNA call: `call(OtherRole("attestation"), "get_validation_request_for_data_hash", data_hash)`. The record's `action().author()` is the researcher who submitted the study. Falls back to the first participating validator if the cross-DNA call fails.

`check_and_create_harmony_record` is idempotent and decentralised — any participant may call it. It checks for an existing record first, then verifies that enough attestations exist (`attestation_records.len() >= num_validators_required`) before writing. `submit_attestation` in DNA 3 automatically fires this call on the governance role after writing each attestation — the last validator to reveal triggers HarmonyRecord creation without any central coordinator node. When a badge is issued it is linked twice: via `StudyToBadge` (per-study lookup) and via `BadgePath` (cross-study type-based analytics).

`create_governance_decision(input: GovernanceDecision)` writes a `GovernanceDecision` entry and indexes it under the `decisions.all` path anchor via `AllDecisions` link type. Gated by `system_coordinator_key` in `validate()`.

`get_all_governance_decisions()` reads via `AllDecisions` links from the path anchor. Network-strategy get.

`get_validators_for_institution(institution: String)` reads via `InstitutionPath` links from "institution.{institution}" anchor. `publish_validator_profile` now writes both `ValidatorTierPath` (discipline) and `InstitutionPath` (institution) links.

`get_attestations_for_discipline(discipline: Discipline)` reads via `DisciplinePath` links from "attestations.{discipline_tag}" anchor. Written by `submit_attestation`.

`get_badges_by_type(badge_type: BadgeType)` reads all badges of a given type via the `BadgePath` link index. Accepts a plain string enum variant (e.g. `"BronzeReproducible"`).

---

## What Is Stubbed

These functions exist and compile but return placeholder values. They are designed to be filled in during Phase 1 without touching any other part of the system.

| Function | Location | Current behaviour | What it needs |
|---|---|---|---|
| `select_validators` | DNA 3 coordinator | Returns empty `Vec` — **validator self-assignment via `claim_study` is now implemented and tested** (replaces central assignment for Phase 0) | Full reputation-weighted constrained randomisation with institutional balance caps for Phase 1 |
| `detect_gaming_patterns` | DNA 3 coordinator | Returns empty `Vec` | Pattern detection logic — flag definitions exist in shared_types |
| `get_difficulty_assessment` (retrieval) | DNA 3 coordinator | **Now implemented** — returns `None` only when no assessment exists | The `assess_difficulty` function stores real entries; retrieval works via `DifficultyPath` |
| Cumulative reputation | DNA 4 coordinator | Single-round reputation only | Multi-round cumulative tier progression |
| Real membrane proof issuance | Outside codebase | Not implemented | A credential issuance service that signs joining agents' pubkeys with the issuer keypair |
| Researcher identity blinding | Outside codebase | Not enforced — `ValidationRequest.data_access_url` is visible to validators in full; if the URL contains researcher identity it defeats the blinding | A blinding proxy service that serves dataset access via opaque URLs, stripping researcher identity before the `ValidationRequest` is visible to validators. Until built, double-blinding is an operational convention, not an architectural guarantee |

---

## Shared Types

All cross-DNA types live in `valichord/shared_types/` — a pure `rlib` crate imported by all four DNAs.

**Do not move shared types into an integrity zome.** Integrity zomes compile as `cdylib`. If a type is defined in a `cdylib` and re-exported across crates, you get duplicate symbol errors at link time. The `rlib` pattern is the correct solution.

Key shared types: `Discipline`, `AttestationOutcome`, `AttestationConfidence`, `ComputationalResources`, `TimeBreakdown`, `UndeclaredDeviation`, `ValidationPhase`, `OutcomeSummary`, `MetricResult`, `AgreementLevel`, `CertificationTier`, `discipline_tag()`.

---

## Hard-Won Engineering Constraints

These are things that took significant debugging time to establish. Do not re-learn them.

### 1. post_commit cannot write data directly
`post_commit` is called after the source chain has been committed. Writing new entries from inside `post_commit` causes a re-entrant deadlock on the cell's operation queue. Cross-DNA `call(OtherRole(...))` IS permitted from `post_commit` — but only to write to a **different** cell, never back to the same one.

### 2. Target cell must be initialised before post_commit fires
`post_commit` in DNA 2 calls `notify_commitment_sealed` in DNA 3. If DNA 3's cell has never been initialised (i.e. `init()` has never run), the `call()` triggers `init()`, which the conductor serialises — deadlock. In production, the UI layer should initialise all cells on startup. In tests, always make a warm-up read call to the attestation cell before calling `seal_private_attestation`.

### 3. Add a pause after seal_private_attestation in tests
`post_commit` is asynchronous. If you call `dhtSync` immediately after `seal_private_attestation`, the `CommitmentAnchor` may not yet be written. Add a `pause(500)` between the seal call and the sync.

### 4. DnaProperties fields must be String, not AgentPubKey
The conductor passes DNA properties as msgpack-encoded YAML strings. Declaring a property as `AgentPubKey` in the struct causes a deserialisation error at startup. Always use `String` and parse to `AgentPubKey` inside the coordinator when needed.

### 5. Enum serialisation — two patterns in use
- `Discipline` and `AttestationOutcome` use `#[serde(tag="type", content="content")]` (adjacent tagging) → serialises as `{ type: "ComputationalBiology" }` on the JS side
- All other enums (`ValidationPhase`, `AgreementLevel`, etc.) use no tag → plain strings

Do not mix these up when writing test fixtures.

### 6. ExternalHash construction in TypeScript tests
Always construct `ExternalHash` using `hashFrom32AndType(core32, HoloHashType.External)`. Never use `new Uint8Array(39).fill(byte)` — the DHT location bytes (last 4 bytes) must be a valid blake2b checksum. Using a flat fill produces hashes that fail DHT validation silently.

### 7. do NOT use pack_dna.py
There is a `pack_dna.py` script in the repo. It has a bug that embeds the attestation DNA bytes for all four roles, meaning every cell requires the attestation membrane proof. Always use `hc dna pack` and `hc app pack` directly.

### 8. Deadlock: DNA 4 calling back into DNA 3
`check_and_create_harmony_record` (DNA 4) calls `get_attestations_for_request` (DNA 3) to retrieve attestations. This is safe because it is a read-only call. Do not add any write calls from DNA 4 back into DNA 3 — this creates a cycle with the pending write operation and deadlocks.

### 9. verify_signature is HDK-only — not available in integrity zomes
Integrity zomes run in a restricted WASM environment without host function access to the keystore. `verify_signature` is an HDK function. All cryptographic verification must go in coordinator zomes, not integrity zomes. The validate() callback in an integrity zome cannot call it.

### 10. Do not use hardcoded ZomeIndex or EntryDefIndex
`get_all_tasks` and `post_commit` in DNA 2 previously filtered entries using hardcoded `ZomeIndex(0)` and `EntryDefIndex(0/1)`. These indices break silently if the order of entry type declarations ever changes. The correct pattern is to filter by attempting deserialization: `r.entry().to_app_option::<MyType>().ok().flatten().is_some()`. Any coordinator function that needs to identify a specific entry type from the source chain must use this pattern.

### 11. dhtSync with 7+ conductors exhausts websocket connections in Codespaces
The Gold badge test (7 validators) is skipped because spinning up 7 simultaneous Holochain conductors exhausts available websocket connections in resource-constrained environments (Codespaces, CI with <16GB RAM). The test logic is correct. Run it on hardware with ≥16GB RAM or a GitHub Actions runner with a large instance.

---

## Build Sequence

```bash
# 1. Rust WASM toolchain
rustup target add wasm32-unknown-unknown

# 2. Holochain CLI
cargo install holochain hc --locked

# 3. Node dependencies
cd tests && npm install && cd ..

# 4. Set PATH (Codespaces / CI)
export PATH="/home/codespace/.cargo/bin:$PATH"

# 5. Compile all four WASM zomes
cargo build --target wasm32-unknown-unknown --release

# 6. Pack each DNA — always use hc directly
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna

# 7. Pack the hApp bundle
hc app pack . -o workdir/valichord.happ

# 8. Run targeted tests (preferred)
cd tests && npm test -- -t "Membrane proof"
cd tests && npm test -- -t "governance"

# 9. Full suite (takes ~90 minutes in Codespaces — only when needed)
cd tests && npm test
```

---

## Test Inventory Summary

87 tests across 4 files, 1 skipped.

| File | Tests | Coverage |
|---|---|---|
| `attestation.test.ts` | 40 (1 skipped) | Membrane proof, commit-reveal, phase poll, immutability, profiles, requests, discipline query, cross-DNA post_commit, real Ed25519 verification, badge thresholds (Bronze/Silver/Gold), `get_validation_request_for_data_hash`, `get_validators_for_institution`, `get_attestations_for_discipline`, validator self-assignment (StudyClaim), dropout recovery (`reclaim_abandoned_claim`) — too-recent guard, eligible reclaim + slot freed, attested validator guard |
| `governance.test.ts` | 24 | Idempotency, author enforcement, end-to-end round, reputation, read queries, Bronze/Silver/Failed badges, mixed outcomes, `GovernanceDecision` CRUD, `get_badges_by_type`, delete-immutability guards, `force_finalize_round` — not-yet-timed-out guard, no-attestations guard |
| `researcher_repository.test.ts` | 14 | All coordinator functions, immutability enforcement, `get_all_studies` |
| `validator_workspace.test.ts` | 7 | All coordinator functions, multi-task retrieval, `get_all_private_attestations` |

Full test inventory: `valichord/tests/README.md`

---

## Deferred Decisions

These are architectural questions that have been explicitly deferred to Phase 1. They are not oversights — they require Phase 0 empirical data or real operational experience before they can be answered well.

**Countersigning for simultaneous reveal.** The current design uses DHT-poll-driven sequential reveals. CommitmentAnchor already prevents last-mover advantage — a validator cannot see others' outcomes before committing their own. True Holochain countersigning would enforce mathematical simultaneity but requires all validators online at the same moment, which is operationally inappropriate for Phase 0. Revisit in Phase 2.

**Validator assignment.** Validator self-assignment via `claim_study` is now implemented — validators discover studies via `get_pending_requests_for_discipline` and self-select, with COI enforcement (same institution as researcher) and capacity limits enforced at the protocol level. `select_validators()` (central algorithmic assignment with reputation-weighted constrained randomisation, institutional balance caps, and co-authorship detection) remains a stub — the data to calibrate it comes from Phase 0.

**Compensation tiers.** `CompensationTier` is defined in shared_types. The actual tier values are placeholders. Phase 0 empirical workload data determines real compensation rates.

**Difficulty assessment prediction.** `assess_difficulty()` stores a `DifficultyAssessment` entry. The retrieval works. The prediction model — whether surface features (code quality, documentation, dependency count) actually predict validation workload — is Phase 0's primary research question. Do not hard-code a prediction model until Phase 0 data exists.

**Membrane proof issuance service.** The credential verification is implemented and tested. What does not exist yet is the external service that issues credentials — signs a joining agent's pubkey with the authorised issuer keypair and returns the 64-byte proof. This is a Phase 1 infrastructure component. In dev/test mode, set `authorized_joining_certificate_issuer = ""` to bypass.

**HTTP Gateway deployment.** DNA 4 is designed as an HTTP Gateway target — publicly readable without a Holochain node. The gateway configuration is not yet deployed. Phase 1.

**Cryptographic attestations (Gap 4 / Phase 1 design direction).** `ValidationAttestation` currently contains fully readable plaintext — outcome, key metrics, deviation flags, confidence. A validator with direct DHT access (bypassing the UX) could query `get_attestations_for_request` before the reveal window opens and read another validator's result. The UX does not expose this and the attack requires Holochain API knowledge, a running conductor, and a valid membrane proof — so it is not a practical concern for Phase 0. The long-term design direction is to move toward cryptographic proofs: `CommitmentAnchor` should carry a commitment hash (`sha256(assessment_bytes + nonce)`) so that the reveal can be verified against it, and `ValidationAttestation` content should be verified as the genuine preimage. This would close the gap architecturally rather than relying on UX convention. Phase 1 fix: add a coordinator-level guard in `submit_attestation` that checks a `CommitmentAnchor` exists for the calling agent before allowing the write.

**Researcher identity blinding proxy.** Double-blind validation (validators cannot see researcher identity) is a design goal but is not architecturally enforced in the current implementation. `ValidationRequest.data_access_url` is visible to validators in full — if it contains researcher-identifying information (e.g. `osf.io/jsmith/my-study`), the blinding is defeated. `researcher_institution` is used server-side only for COI enforcement and is not displayed to validators, but this is a convention not a structural constraint. The fix is a blinding proxy service that replaces the original URL with an opaque token before the `ValidationRequest` is written to the DHT. Until built, double-blinding is an operational convention enforced by the ValiChord team. The commit-reveal blindness (validators cannot see *each other's findings*) is fully implemented and architecturally enforced — these are two distinct properties and only the latter is guaranteed today.

---

## Key Files

| File | Description |
|---|---|
| `valichord/shared_types/src/lib.rs` | All cross-DNA types |
| `valichord/dnas/attestation/zomes/attestation_integrity/src/lib.rs` | DNA 3 entry types, link types, validate() |
| `valichord/dnas/attestation/zomes/attestation_coordinator/src/lib.rs` | DNA 3 coordinator functions including init() membrane verification |
| `valichord/dnas/governance/zomes/governance_integrity/src/lib.rs` | DNA 4 entry types, validate() with author key enforcement |
| `valichord/dnas/governance/zomes/governance_coordinator/src/lib.rs` | DNA 4 including check_and_create_harmony_record |
| `valichord/happ.yaml` | Role definitions, DNA property defaults |
| `valichord/tests/src/attestation.test.ts` | DNA 3 integration tests including membrane proof |
| `valichord/tests/README.md` | Full test inventory, build instructions, architecture notes |
| `docs/3_ValiChord_Technical_Reference.md` | Full architectural narrative — read before modifying architecture |
| `docs/4_ValiChord_RUST_Scaffold.rs` | Single-file scaffold v12 — useful reference for overall structure |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Technical architecture document |

---

## Contact

**Ceri John** — [topeuph@gmail.com](mailto:topeuph@gmail.com)

Technical review: Arthur Brock (Holochain co-founder), Paul D'Aoust (Holochain Foundation)

For Holochain-specific questions, the Holochain developer Discord is the fastest route to answers. Paul D'Aoust is active there and familiar with this codebase.
