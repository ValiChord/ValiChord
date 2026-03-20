# ValiChord: Engineer Handover Document

**Version:** 2.0 — March 2026
**Author:** Ceri John
**Status:** Current — reflects codebase as of last commit

---

## Overview

This document is for any engineer picking up the ValiChord codebase. It covers what is built and tested, what is stubbed and why, known constraints and hard-won lessons, the build sequence, and decisions that have been deferred to Phase 1.

Read this before touching the code.

---

## What Is Built

ValiChord is a four-DNA Holochain hApp — four independent peer-to-peer networks running simultaneously on each participant's conductor, communicating via same-agent `call(OtherRole(...))` calls.

The infrastructure is complete in the sense that matters: it compiles, the four DNAs pack into a single `.happ` bundle, and 94 integration tests pass against live Holochain conductors via Tryorama. One test is skipped for hardware reasons (see below). As of 2026-03-20, all four DNAs have been reviewed and optimised, and the cryptographic commit-reveal protocol is fully implemented — see the constraint list below for the key decisions made.

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

**`seal_private_attestation` now generates and stores the cryptographic commitment** (2026-03-18). The function accepts `SealAttestationInput { task_hash, attestation: ValidationAttestation }` — the exact public attestation the validator intends to reveal. It:
1. Generates a 32-byte nonce via `random_bytes(32)` (HDK host function).
2. Serialises the `ValidationAttestation` to MessagePack via `SerializedBytes::try_from`.
3. Computes `commitment_hash = SHA-256(msgpack_bytes || nonce)` using the `sha2` crate.
4. Writes the private entry with all attestation fields plus `discipline`, `nonce`, and `commitment_hash`.

`ValidatorPrivateAttestation` now carries five generated/derived fields: `nonce: Vec<u8>`, `commitment_hash: Vec<u8>`, and `discipline: Discipline`. The caller must NOT supply these — they are computed by `seal_private_attestation`. The `discipline` field mirrors the public attestation's discipline so the full `ValidationAttestation` can be reconstructed at reveal time without a separate task lookup.

**Critical:** `post_commit` fires `call(OtherRole("attestation"), "notify_commitment_sealed")` after a `ValidatorPrivateAttestation` is created. The payload is now `CommitmentSealedInput { request_ref, commitment_hash }` — the commitment hash is forwarded to DNA 3 so the `CommitmentAnchor` on the shared DHT carries the cryptographic proof. The target attestation cell must be initialised before `post_commit` fires — see the deadlock section below.

`get_all_private_attestations()` returns all `ValidatorPrivateAttestation` records from the local source chain using `query()` + deserialization filter. Parallel to `get_all_tasks`.

**`get_private_attestation_for_task` uses `query()` for retrieval (2026-03-20).** The function follows a `TaskToPrivateAttestation` link to the target ActionHash, then uses `query(ChainQueryFilter::new().include_entries(true))` to find the matching record in the calling agent's source chain — `find(|r| r.action_address() == &target)`. This replaces the previous `get(target, GetOptions::local())` call. Reason: `query()` is strictly source-chain-local and cannot cross cell boundaries even when cells share the same conductor process (singleFork/test mode). `get()` with local options would find Alice's private entry from Bob's cell in a shared-conductor test, violating the privacy guarantee. In production the distinction is moot (private entries never leave the device), but the test suite verifies the structural privacy property.

---

### DNA 3 — Attestation
**Status: Complete**

Shared DHT, credentialed membrane. The most complex DNA. Manages the full commit-reveal protocol, phase transitions, and public attestation records.

**Membrane proof:** Real Ed25519 verification is implemented in the **coordinator** `init()`, not the integrity zome. The integrity zome does format-only checks (≥64 bytes). The coordinator queries the source chain for `AgentValidationPkg`, reads `authorized_joining_certificate_issuer` from DNA properties, and calls `verify_signature()`. Empty string in DNA properties = dev/test bypass.

**Phase transitions** are DHT-poll-driven, not signal-driven. `get_current_phase()` is the authoritative source of phase state. Signals are send-and-forget notifications only — do not use them as protocol gates.

`CommitmentAnchor`, `PhaseMarker`, `ValidationAttestation`, and `ResearcherResultCommitment` are all immutable after creation — enforced in `validate()` and tested.

**`CommitmentAnchor` now carries `commitment_hash: Vec<u8>`** (2026-03-18) — the SHA-256 of the validator's serialised `ValidationAttestation` concatenated with a private nonce. Written by `notify_commitment_sealed(input: CommitmentSealedInput)`. At reveal time, verifying `SHA-256(msgpack(attestation) || nonce) == commitment_hash` proves the revealed content matches what was committed without any honesty assumptions.

**`publish_researcher_commitment(input: ResearcherCommitmentInput)` is a new write function** (2026-03-18). The researcher calls this before the validation round opens to publish `ResearcherResultCommitment { request_ref, result_commitment_hash }` to the shared DHT. The actual result stays in the researcher's local DNA 1. This closes the other side of the blinding: validators cannot claim the researcher adjusted their result after seeing validator findings. The entry is indexed under `researcher_commitment.{request_ref}` via `RequestToResearcherCommitment` link type. **`get_researcher_commitment(request_ref)` is the companion read** — added to the unrestricted cap grant so any participant can verify the researcher committed before validators begin.

`notify_commitment_sealed` is intentionally NOT in the unrestricted cap grant — it is called under the author grant from DNA 2's `post_commit`.

`get_validation_request_for_data_hash(data_hash: ExternalHash)` is a public extern registered in `init()`. It resolves a `ValidationRequest` record from the `study.{data_hash}` path. Used by DNA 4 to identify the researcher (record author) when issuing a `ReproducibilityBadge`.

**`ValidationRequest` carries two new pointer fields** added 2026-03-14: `data_access_url: String` (URL where validators download the dataset — OSF, Zenodo, institutional repo, etc.) and `protocol_access_url: Option<String>` (DOI or URL of the pre-registered analysis plan). The actual data never touches the DHT — these are pointers only. The researcher fills these from their private DNA before calling `submit_validation_request`.

**Governance DNA is now fully decentralised** (2026-03-14): `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation` are no longer author-gated by a designated coordinator key. Any participant who was part of the round can trigger finalisation by calling `check_and_create_harmony_record`. The function enforces completeness (must have ≥ `num_validators_required` attestations before writing) and idempotency (a second call short-circuits if a record already exists). `submit_attestation` in the Attestation DNA now automatically fires a same-agent cross-DNA call to `check_and_create_harmony_record` — the last validator to submit their attestation triggers the HarmonyRecord write without any central coordinator node.

`GovernanceDecision` remains key-gated by `system_coordinator_key` — governance votes are human deliberation outcomes that require a designated recorder. `harmony_record_creator_key` has been removed from `DnaProperties` entirely.

**Known remaining limitation (Phase 1):** the Governance integrity zome's `validate()` cannot perform cross-DNA lookups to cryptographically verify that a HarmonyRecord's content is correct against the Attestation DHT. Content correctness is currently enforced at the coordinator layer (completeness check + algorithmic derivation) but not at the network validation layer. Making it trustless at the validation layer requires either moving HarmonyRecord creation into the Attestation DNA or embedding sufficient proof in the entry itself. A partial guard IS enforced (2026-03-20): `validate()` requires the HarmonyRecord author to be listed in `record.participating_validators` — prevents non-participants from anonymously forging a record and winning the first-write idempotency race.

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

### 12. get_private_attestation_for_task — use query(), not get()
Private entries retrieved by the owning agent must be looked up via `query()`, not `get(target, GetOptions::local())`. In singleFork Tryorama tests, all cells share the same conductor and local DB, so `get()` with local options crosses cell boundaries — Bob's cell can retrieve Alice's private entry. `query()` is strictly bound to the calling agent's source chain and cannot cross this boundary. Pattern: follow the link to get the target ActionHash, then `query(ChainQueryFilter::new().include_entries(true))?.into_iter().find(|r| *r.action_address() == target)`.

### 13. reveal_researcher_result — idempotency guard required before hash check
`reveal_researcher_result` checks for an existing `RequestToResearcherReveal` link **before** the SHA-256 hash verification step. Without this guard, a researcher could call the function multiple times, creating multiple `ResearcherReveal` entries linked from the same deterministic path. `get_researcher_reveal` uses `links.last()`, which is non-deterministic under concurrent DHT propagation, so duplicate entries introduce result ambiguity even though content is forced to match the commitment. Pattern mirrors `publish_researcher_commitment`: query the path's existing links at the top of the function and return an error immediately if any exist. Commitment hash for `metrics=[], nonce=[]` is `SHA256(0x90) = 9e076ceaf246b6003d9c2680a2b4cf0bffd069805902b0b5edeebf49039fe4bd` — used in S6 test fixture.

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

94 tests across 5 files, 1 skipped.

| File | Tests | Coverage |
|---|---|---|
| `attestation.test.ts` | 40 (1 skipped) | Membrane proof, commit-reveal, phase poll, immutability, profiles, requests, discipline query, cross-DNA post_commit, real Ed25519 verification, badge thresholds (Bronze/Silver/Gold), `get_validation_request_for_data_hash`, `get_validators_for_institution`, `get_attestations_for_discipline`, validator self-assignment (StudyClaim), dropout recovery (`reclaim_abandoned_claim`) — too-recent guard, eligible reclaim + slot freed, attested validator guard |
| `governance.test.ts` | 24 | Idempotency, author enforcement, end-to-end round, reputation, read queries, Bronze/Silver/Failed badges, mixed outcomes, `GovernanceDecision` CRUD, `get_badges_by_type`, delete-immutability guards, `force_finalize_round` — not-yet-timed-out guard, no-attestations guard |
| `researcher_repository.test.ts` | 14 | All coordinator functions, immutability enforcement, `get_all_studies` |
| `validator_workspace.test.ts` | 7 | All coordinator functions, multi-task retrieval, `get_all_private_attestations` |
| `security.test.ts` | 7 | S1 duplicate attestation, S2 duplicate commitment, S3 researcher commitment idempotency, S4.1 reclaim timeout floor enforced, S4.2 zero floor allows immediate reclaim, S5 force_finalize_round conservative abort on missing VR, S6 reveal_researcher_result idempotency |

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

**Cryptographic commitment verification — FULLY RESOLVED 2026-03-18/20.**

**Researcher side (fully implemented, 2026-03-18):** The full symmetric researcher commit-reveal is complete:
- DNA 1 `lock_researcher_result(LockResultInput { request_ref, metrics: Vec<MetricResult> })` — generates nonce, computes `SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores private `LockedResult { request_ref, metrics, nonce, commitment_hash }` (immutable, private, never leaves device), calls `publish_researcher_commitment` in DNA 3.
- DNA 1 `get_locked_result(request_ref)` — retrieves the private entry at reveal time.
- DNA 3 `reveal_researcher_result(ResearcherRevealInput { request_ref, metrics, nonce })` — gates on `check_all_commitments_sealed`, verifies hash on-chain against `ResearcherResultCommitment`, writes immutable `ResearcherReveal { request_ref, metrics }` to DHT.
- DNA 3 `get_researcher_reveal(request_ref)` — unrestricted read.
- `ResearcherReveal` is immutable — update + delete both rejected by `validate()`.

**Validator reveal-side (RESOLVED 2026-03-20):** `submit_attestation` now takes `AttestationRevealInput { attestation: ValidationAttestation, nonce: Vec<u8> }`. It recomputes `SHA-256(msgpack(attestation) || nonce)` and compares against the `CommitmentAnchor.commitment_hash` written during the commit phase. A hash mismatch or missing anchor is rejected with a hard error. This closes the adaptive-reveal attack — a validator cannot reveal a different attestation than they committed to.

**Commit-phase guards (RESOLVED 2026-03-20):** `notify_commitment_sealed` now enforces two guards before writing a `CommitmentAnchor`:
1. The caller must hold a live `StudyClaim` for the study (prevents non-claimants from inflating the commitment quorum).
2. Each validator may only submit one commitment per study (prevents a single agent satisfying the quorum alone).

**Researcher identity blinding proxy.** Double-blind validation (validators cannot see researcher identity) is a design goal but is not architecturally enforced in the current implementation. `ValidationRequest.data_access_url` is visible to validators in full — if it contains researcher-identifying information (e.g. `osf.io/jsmith/my-study`), the blinding is defeated. `researcher_institution` is used server-side only for COI enforcement and is not displayed to validators, but this is a convention not a structural constraint. The fix is a blinding proxy service that replaces the original URL with an opaque token before the `ValidationRequest` is written to the DHT. Until built, double-blinding is an operational convention enforced by the ValiChord team. The commit-reveal blindness (validators cannot see *each other's findings*) is fully implemented and architecturally enforced — these are two distinct properties and only the latter is guaranteed today.

---

## Security Audit Summary (March 2026)

Four LLM red-team audits (ChatGPT, Gemini, Grok ×2) and one systematic self-audit were run against the full codebase. Findings and dispositions are recorded here for future auditors.

### Implemented fixes

| Fix | Finding source | Severity | What was done |
|---|---|---|---|
| `ValidationRequest` immutability | Gemini | High | `validate()` now rejects updates and deletes — researchers cannot silently lower `num_validators_required` after submission |
| `get_num_validators_required` safe default | Gemini | High | `unwrap_or(1)` removed; function now returns `Err` if the ValidationRequest is not found, preventing a single attestation from finalising any study |
| `force_finalize_round` removed from Unrestricted cap grant | Gemini | Medium | Write function was previously callable by anonymous HTTP Gateway clients |
| Conservative quorum fallback in governance | Gemini | Medium | `Err(_) => return Ok(None)` instead of `unwrap_or(1u8)` — a decode failure no longer allows premature finalisation |
| Validator reveal binding (`submit_attestation`) | ChatGPT | Critical | Now takes `AttestationRevealInput { attestation, nonce }`; verifies `SHA-256(msgpack(attestation) \|\| nonce) == CommitmentAnchor.commitment_hash` before writing |
| Commitment uniqueness + claim binding (`notify_commitment_sealed`) | ChatGPT | High | Two new guards: (1) caller must hold a live `StudyClaim`; (2) one commitment per validator per study |
| HarmonyRecord author guard | Grok | High | `validate()` in governance_integrity now requires `action.author ∈ record.participating_validators` — prevents outsider forgery winning the idempotency race |
| `num_validators_required` minimum enforcement | Gemini (second audit) | High | New `validate()` arm for `ValidationRequest` create checks `vr.num_validators_required >= props.minimum_validators`; `minimum_validators = 0` is the dev/test bypass |
| Membrane proof comment corrected | Grok (first) | Low | Comment incorrectly said `rmp_serde` encodes `Vec<u8>` as "msgpack array of unsigned integers" — it encodes as msgpack **bin** format. JS issuer must use `Buffer.from`/`Uint8Array`, not `Array.from` |
| `ValidatorReputation` write gate | Grok (second) | High | `validate()` arms for `ValidatorReputation` create and update were `Valid` unconditionally — anyone could mint or alter reputation scores. Both now check `action.author == system_coordinator_key` (empty = dev/test bypass) |
| `get_harmony_record` uses `.last()` | Grok (second) | Low | Was `.first()` — defensive: idempotency guard should prevent duplicates, but `.last()` is consistent with `get_validator_reputation` and more robust if gossip delivers links out of order |
| Stale `harmony_record_creator_key` removed | Grok (second) | Low | Key was present in `governance/dna.yaml` and `happ.yaml` but absent from `DnaProperties` struct (silently ignored). Removed to eliminate confusion; doc comments updated |
| `reclaim_abandoned_claim` timeout bypass | Self-audit | High | `timeout_secs` was fully caller-controlled — anyone could pass `0` to instantly reclaim any live claim. Added `min_claim_timeout_secs` DNA property (`#[serde(default)]` preserves test behaviour; `0` = bypass). |
| `publish_researcher_commitment` idempotency | Self-audit | High | Researcher could publish multiple commitments, changing their locked prediction after validators started work. Guard now rejects a second commitment for the same `request_ref`. |
| `submit_attestation` double-vote | Self-audit | High | Validator could submit the same attestation+nonce multiple times (one CommitmentAnchor, N identical reveals), gaining N-fold vote weight in the HarmonyRecord plurality tally. Guard prevents duplicate reveals. |
| `force_finalize_round` timeout bypass when VR absent | Self-audit | High | When `get_validation_request_for_data_hash` returned `None`, the `if let` fell through silently and immediately finalised the round without checking the 7-day timeout. Replaced with `match`; `None` → `return Ok(None)` conservatively. |
| `RequestToCommitment` link deletion griefing | Self-audit | High | No validate() guard blocked validators from deleting their own commitment links, dropping the commitment count below the reveal-phase threshold and blocking `reveal_researcher_result` indefinitely. `RegisterDeleteLink` guard added. |
| `ReproducibilityBadge` open create | Self-audit | High | Any credentialed participant could issue a fake badge for any study. `validate()` now requires: (a) `harmony_record_ref` points to a live `HarmonyRecord`, (b) `badge.study_ref == HarmonyRecord.request_ref`, (c) badge author is in `participating_validators`. |
| `RequestToHarmonyRecord` / `StudyToBadge` / `AllDecisions` link deletion | Self-audit | High | A validator who triggered finalisation could delete these index links, hiding outcomes and badges from all future queries (entries themselves are immutable, but their index links were not). `RegisterDeleteLink` guards added in governance_integrity. |
| Badge recipient fallback to wrong agent | Self-audit | Medium | If the researcher's pubkey could not be resolved, `write_harmony_record` issued the badge to the first participating validator. Badge issuance is now skipped entirely if researcher identity is unknown. |
| Automatic reputation update silently fails in production | Self-audit | Medium | `_update_reputation_internal` is called from `write_harmony_record` but always fails if `system_coordinator_key` is set (validate() rejects non-coordinator creates). Wrapped in `system_coordinator_key.is_empty()` guard; production uses `update_validator_reputation` explicitly. |
| `StudyClaim.request_ref` ↔ `ValidationRequest.data_hash` cross-check | Self-audit | Low (defence-in-depth) | validate() now confirms these two fields reference the same study, closing a theoretical COI-bypass where a crafted claim references a benign `ValidationRequest` for the COI check while targeting a different study. |

### Dismissed findings (with reasoning)

| Finding | Source | Why dismissed |
|---|---|---|
| PhaseMarker forgery / anchor_proof | Grok (first/second) | PhaseMarker is explicitly UI-only; `validate()` cannot gate creates without also blocking the coordinator. Protocol gates on commitment count only. Adding `anchor_proof` would change the DNA hash (breaking change). |
| Phase-marker race condition | Gemini (second) | Multiple simultaneous PhaseMarkers for RevealOpen are harmless — all identical, `get_current_phase` returns last link. Not a protocol gate. |
| Researcher early-reveal breaks blind reveal | Grok (first/second) | Validators already committed their outcomes (bound by SHA-256 hash); researcher revealing first cannot influence committed validators. |
| CommitmentSealedInput accidental leakage | Gemini (second) | Hypothetical future dev error, not a current vulnerability. Addressed with a doc comment on the struct (see `attestation_integrity/src/lib.rs`). |
| Nonce entropy weakness | Gemini (second) | `random_bytes(32)` uses OS RNG — 256-bit entropy. No WASM-specific entropy degradation in Holochain conductors. |
| StudyClaim delete/recreate resets timeout | Gemini (second) | `force_finalize_round` computes age from `ValidationRequest.action().timestamp()` — immutable. StudyClaim timestamps are irrelevant. |
| Assessment spam (`assess_difficulty`) | Gemini (second) | `DifficultyAssessment` is a scaffold stub (all hardcoded values). It does not gate any protocol step. Add per-agent guard when real assessment logic is implemented. |
| post_commit cross-DNA call deadlock | Gemini (second) | Cross-DNA `call(OtherRole(...))` from `post_commit` is the intended Holochain pattern. "Must not write data" means local source chain only. Error is already non-fatal. |
| Empty issuer bypass | Gemini (second) | Already documented as dev/test bypass — same pattern as governance `system_coordinator_key`. Not new. |
| Credential revocation gap | Grok / Gemini (second) | Fundamental Holochain DHT architecture limitation. No CRL mechanism possible without significant additional infrastructure. Phase 2. |
| Self-assignment collusion | Grok (first/second) | Acknowledged architectural trade-off. Requires trusted randomness oracle for Phase 1 `select_validators`. |
| HarmonyRecord full content forgery | Grok (second) | Partial fix (author ∈ participants) is in place. Full content verification requires cross-DNA calls in `validate()`, which is architecturally impossible in Holochain HDI. Phase 2. |
| Cross-link deletion by non-author | Grok (second) | Not real in Holochain — only the link author can delete their own links. Any agent who creates a link owns it; non-authors cannot delete it. |

### Known architectural gaps (Phase 1 / Phase 2)

- **Full HarmonyRecord content verification at validate() layer** — cross-DNA calls unavailable in HDI; content correctness is coordinator-layer only. The partial fix (author ∈ participating_validators) is in place.
- **Credential revocation** — once an agent joins the Attestation DHT, they cannot be removed retroactively without governance intervention.
- **Validator self-assignment collusion** — COI institution check enforced; cartel from distinct institutions is not preventable without random assignment (Phase 1 `select_validators`).
- **`get_current_phase` not authoritative** — clients must not treat `PhaseMarker` as a protocol gate; always verify via `check_all_commitments_sealed`. Any credentialed agent can write a `PhaseMarker` (validate() cannot gate creates without also blocking the coordinator). Protocol itself is unaffected — only UIs that trust `get_current_phase` blindly are at risk.

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
