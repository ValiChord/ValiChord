
<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord Complete — Technical Reference
## Illustrative Architecture Sketches for Engineering Discussion

**Author:** Ceri John
**Date:** April 2026
**Version:** 29

**© 2026 Ceri John. All Rights Reserved.**

**Contact:** topeuph@gmail.com

---

## Important Note on Status

**Implementation is complete.** The four-DNA hApp described in this document has been fully implemented, integration-tested, and connected to a REST API layer. 158 integration tests pass across two suites (94 Tryorama, 64 Rust sweettest), 1 skipped.

The Rust structures and functions in this document describe the *shape* of ValiChord's architecture — data models, system flows, and component interactions. They were illustrative sketches developed during twelve months of architectural design. The system is now built. For the authoritative implementation, see:
- Source files under `valichord/dnas/`
- Engineering handover: `docs/13_Valichord_Engineer_Handover.md`
- REST API spec: `backend/openapi.yaml`
- Integration guide: `docs/INTEGRATION_GUIDE.md`

**What this document is still useful for:** Understanding *why* the architecture was designed the way it was, what problems each DNA membrane solves, and how the data flow is intended to work. It also records all key divergences from the original design.

The specific structs in this document were the design starting point — the actual implementation may differ in field names and structure. Key divergences from this document:

- Self-reported timestamp fields were removed from `HarmonyRecord`, `ValidatorReputation`, and `ReproducibilityBadge` — Holochain Action timestamps are authoritative and tamper-evident; do not add them back.
- `ReproducibilityBadge.issued_to` resolves the researcher via cross-DNA lookup, not the first validator.
- `GovernanceDecision` write/list API and `get_badges_by_type` `BadgePath` index are implemented and tested.
- Validator self-assignment (`StudyClaim`) is implemented — validators claim studies directly with COI enforcement in the integrity zome's `validate()`.
- `ValidationRequest` carries `researcher_institution`, `data_access_url`, and `protocol_access_url` fields. Two additional fields were added April 2026: `deposit_access_type: DepositAccessType` (default `PublicUrl`; `TokenGated` for institutional private deployments) and `deposit_token: Option<String>` (bearer credential for `TokenGated` deposits, protected by the Attestation DHT membrane). Both fields use `#[serde(default)]` — existing entries on the DHT without these fields deserialise correctly.
- Governance `DnaProperties` includes `min_attestations_for_finalization: u32`.
- `check_all_commitments_sealed_inner` uses `num_validators_required` from the per-study `ValidationRequest`, not the network-wide `minimum_validators` DNA property.
- The reveal step is automatic — the frontend detects `RevealOpen` phase and calls `submit_attestation` without user action.
- **Cryptographic commit-reveal is now implemented (March 2026):** `CommitmentAnchor` carries `commitment_hash: Vec<u8>` — `SHA-256(msgpack(ValidationAttestation) || nonce)` — computed by `seal_private_attestation` in DNA 2 and forwarded to DNA 3 via `CommitmentSealedInput`. The `CommitmentAnchor` struct in this document predates this and is missing the `commitment_hash` field — see updated struct below. `ValidatorPrivateAttestation` now includes `nonce: Vec<u8>`, `commitment_hash: Vec<u8>`, and `discipline: Discipline` (to allow full `ValidationAttestation` reconstruction at reveal time). `SealAttestationInput` takes a `ValidationAttestation` (the public form to be revealed), not a raw `ValidatorPrivateAttestation`.
- **Full symmetric researcher commit-reveal implemented (March 2026):** The researcher side of the commit-reveal protocol is now complete and mirrors the validator side. DNA 1 has a new private entry `LockedResult { request_ref, metrics: Vec<MetricResult>, nonce: Vec<u8>, commitment_hash: Vec<u8> }` and a new link type `RequestToLockedResult`. New coordinator functions in DNA 1: `lock_researcher_result(LockResultInput { request_ref, metrics })` — generates nonce, computes `SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores the private `LockedResult`, and calls `publish_researcher_commitment` in DNA 3; `get_locked_result(request_ref)` — retrieves the private entry at reveal time. DNA 3 has a new immutable public entry `ResearcherReveal { request_ref, metrics: Vec<MetricResult> }` and link type `RequestToResearcherReveal`. New coordinator functions in DNA 3: `reveal_researcher_result(ResearcherRevealInput { request_ref, metrics, nonce })` — gates on all validators having committed (`check_all_commitments_sealed`), verifies the hash on-chain, writes `ResearcherReveal` to DHT; `get_researcher_reveal(request_ref)` — unrestricted read. The `ResearcherResultCommitment` entry (previously noted) records only the hash; `ResearcherReveal` is the verified structured reveal that lands on the DHT after all validators have committed. Both sides use `rmp_serde::to_vec_named` for consistent msgpack serialisation. `ResearcherReveal` is immutable — update and delete are both rejected by `validate()`.
- The "countersigning session" design described in this document (simultaneous atomic reveal) has been **deferred to Phase 2**. The implemented approach uses SHA-256 hash commitments on a DHT-poll-driven protocol, which provides equivalent anti-manipulation guarantees without the operational constraint of requiring all validators online simultaneously.
- **Validator reveal-time hash verification implemented (March 2026):** `submit_attestation` no longer accepts a bare `ValidationAttestation`. It takes `AttestationRevealInput { attestation: ValidationAttestation, nonce: Vec<u8> }`. The function recomputes `SHA-256(msgpack(attestation) || nonce)` and compares it against the `CommitmentAnchor.commitment_hash` written during the commit phase. A mismatch or missing anchor is a hard rejection. This closes the adaptive-reveal attack surface — a validator cannot reveal a different assessment than they committed to.
- **`notify_commitment_sealed` commit-phase guards implemented (March 2026):** Two guards added before a `CommitmentAnchor` is written: (1) the calling agent must hold a live `StudyClaim` for the study — prevents non-claimants from inflating the commitment quorum and triggering `RevealOpen` with phantom commits; (2) one commitment per validator per study — prevents a single agent satisfying the quorum alone. Both guards query the DHT before writing.
- **`HarmonyRecord` create guard implemented (March 2026):** `governance_integrity::validate()` now requires `action.author ∈ record.participating_validators`. An agent who was not part of the round cannot forge a record and win the first-write idempotency race that would permanently block legitimate finalisation. Full content verification against the Attestation DHT remains a Phase 2 goal (cross-DNA calls are not available in integrity zomes).
- **`ValidationRequest` quorum minimum enforced at validate() layer (March 2026):** `attestation_integrity::validate()` now rejects `ValidationRequest` creates where `num_validators_required < minimum_validators` (the DNA property). Previously `minimum_validators` existed in DNA properties but was never checked against what a researcher submitted — a researcher could declare `num_validators_required = 1` and bypass the multi-party protocol. `minimum_validators = 0` is the dev/test bypass (same pattern as the empty issuer key).
- **`PhaseMarker` is UI-only — not a protocol gate (design clarification March 2026):** The `validate()` callback cannot gate `PhaseMarker` creates without also blocking the coordinator's own writes. Any credentialed agent can write a `PhaseMarker` for any phase. Clients must NOT treat `get_current_phase()` as authoritative — always verify against `check_all_commitments_sealed` for protocol decisions. The protocol itself never gates on `PhaseMarker` existence; it is purely a UI polling convenience. Three independent adversarial security audits (Gemini, ChatGPT, Grok — March 2026) confirmed this is the correct design.
- **`CommitmentSealedInput` is a membrane boundary (design note March 2026):** This struct crosses from the private Validator Workspace DNA to the shared Attestation DHT. Fields must never include assessment content, scores, or any data derived from the private `ValidatorPrivateAttestation`. Only public identifiers (`request_ref`) and opaque hashes (`commitment_hash`) are safe to carry across this boundary.
- **`get_private_attestation_for_task` (DNA 2) privacy fix (March 2026):** The function now uses `query()` instead of `get(target, GetOptions::local())` to retrieve the private attestation record. `query()` is strictly source-chain-local — it cannot cross agent cell boundaries even when cells share a conductor (singleFork Tryorama mode). The previous `get()` with local options would return another agent's private entry from the shared conductor DB. This is the Holochain-idiomatic pattern for private entry lookup. The public `TaskToPrivateAttestation` link remains in place for metadata indexing; only the retrieval method changed.
- **Security protocol guards (March 2026):** 11 protocol gaps identified and closed via three-model self-red-team audit (Gemini, ChatGPT, Grok). Guards added: duplicate attestation rejection (one attestation per validator per study), duplicate commitment rejection (one `CommitmentAnchor` per validator per study), researcher commitment idempotency (one `ResearcherResultCommitment` per study), reclaim timeout floor (`min_claim_timeout_secs` DNA property prevents trivially short reclaim windows), `force_finalize_round` conservative abort (returns `None` when no `ValidationRequest` exists), `reveal_researcher_result` idempotency guard (one reveal per study — prevents link-table bloat and non-determinism in `get_researcher_reveal`), `HarmonyRecord` author guard (author must be in `participating_validators`), `ValidationRequest` quorum minimum enforced in `validate()` (`num_validators_required ≥ minimum_validators`).
- **Multi-device identity field added (March 2026):** `ValidatorReputation` (DNA 4) and `ValidatorProfile` (DNA 3) both now carry `person_key: Option<AgentPubKey>` — an optional field for a stable person-level identity that spans device keys. `#[serde(default)]` makes it backwards-compatible; all existing records and tests deserialise it as `None`. `UpdateValidatorProfileInput` carries the corresponding `person_key: Option<Option<AgentPubKey>>` field. The `ValidatorReputation` struct in this document is updated to reflect this — remove the stale `last_updated_secs: u64` field (Action timestamp is authoritative; that field was never implemented). Population and aggregation logic are Phase 1 work; see engineer handover Known Gaps for detail.
- **`AgentToProfile` link-tag ordering (March 2026):** `publish_validator_profile` now writes an 8-byte big-endian `i64` microsecond timestamp as the `LinkTag` on each `AgentToProfile` link. All profile reads (`get_validator_profile`, `update_validator_profile`, `get_validator_agent_type`, `claim_study`) use `.max_by_key(|l| profile_link_ts(l))` to select the most recent profile deterministically. `get_validator_profile` previously used `.first()`, which returned the *oldest* profile — a correctness bug. The pattern mirrors the `ValidatorToReputation` link-tag scheme in the governance coordinator. Old links without a tag return `i64::MIN` and always lose — backwards-compatible.
- **Native multi-device agent linking implemented (March 2026):** `AgentIdentityAttestation` is now a live entry type in `attestation_integrity`. The protocol: both devices sign a canonical 78-byte payload (the two raw `AgentPubKey` bytes in lexicographic order, produced by `sorted_agent_pair_bytes()`); each agent calls `sign_for_identity_link(other_pubkey)` to produce its half; one agent then calls `link_agent_identity({ other_agent, my_signature, other_signature })` — the coordinator verifies both Ed25519 signatures before committing the entry. Symmetric `AgentToIdentityAttestation` links are written from both pubkeys so either agent can call `get_linked_agents()`. Revocation is via `revoke_agent_identity_link(hash)`, restricted to one of the two named agents (enforced in both coordinator and integrity validate()). `get_linked_agents` uses `get_details()` to filter deleted entries so revoked attestations do not appear. The integrity zome enforces two guards: (1) `agent_a ≠ agent_b` (self-link rejection), (2) `action.author ∈ {agent_a, agent_b}` (authorship — no third party can forge an identity link between two other agents). Immutability on updates is also enforced. Full dual-signature verification runs in the coordinator (`verify_signature` is HDK-only). **This change modified `attestation_integrity` — the DNA hash changed; treat as a deliberate network reset.** Future: populate `person_key` in `ValidatorProfile` and `ValidatorReputation` from `get_linked_agents` to enable stable-key reputation aggregation across device rotations. Future integration note: Flowsta's `agent_linking` zome implements the identical protocol and could replace ValiChord's native version if a shared cross-application identity graph becomes useful later.
- **`assess_difficulty` now accepts real input (March 2026):** The function signature changed from `(request_ref: ExternalHash)` to `(input: AssessDifficultyInput)`. The caller supplies all assessment fields; the coordinator validates that `predicted_min_secs ≤ predicted_max_secs` and stores the entry verbatim. The previous implementation hardcoded all fields (e.g. `code_volume = 3`) making the function useless for real data collection. Phase 0 uses the collected entries to determine whether surface features predict validation workload; a prediction model is Phase 1.
- **Typed signal enum + cross-agent push notifications (April 2026):** `PhaseSignal { phase: String }` replaced with a proper `Signal` enum using `#[serde(tag="type", content="content")]`. `notify_commitment_sealed` now calls both `emit_signal` (local subscriber) and `send_remote_signal` (fire-and-forget push to all other committed validators) when the reveal window opens. `recv_remote_signal(signal: Signal)` re-emits the typed payload locally. Pattern from UNYt (Arthur Brock's Holochain accounting app). Signals are best-effort — DHT polling via `get_current_phase()` remains the authoritative fallback.
- **ad4m-inspired shared_types refactoring (April 2026):** `ValiChordError` / `ValiChordResult<T>` added to `shared_types` — a `thiserror::Error` domain enum with `#[from]` for `WasmError` and `SerializedBytesError` and a `From<ValiChordError> for WasmError` impl. `verify_membrane_proof` in DNA 3 was the first caller refactored from `Result<(), String>` to `ValiChordResult<()>`. `ValidationAttestation::msgpack_bytes()` is now a shared method used by both DNA 2 (`seal_private_attestation`) and DNA 3 (`submit_attestation`) for byte-for-byte consistent commit/reveal serialisation. `derive_majority_outcome` and `derive_agreement_level` moved from `governance_coordinator` to `shared_types` as pure functions — the governance coordinator imports them rather than defining them locally. `call_governance_fire_and_forget` extracted as a private helper in DNA 3's attestation coordinator, wrapping the cross-DNA `call()` in a `let _ = ...` to make fire-and-forget intent explicit. 11 conductor-free unit tests added in `shared_types/src/lib.rs` (`cargo test -p valichord_shared_types`, completes in < 1 s). CI sweettest suite split into 5 parallel GitHub Actions matrix jobs to stay under job time limits.
- **Inductive validation chain enforced at DHT layer (March 2026):** `CommitmentAnchor` and `ValidationAttestation` now carry back-references that `attestation_integrity::validate()` verifies via `must_get_valid_record`. `CommitmentAnchor` gains `validation_request_hash: ActionHash` — `notify_commitment_sealed` resolves this via the `study.{request_ref}` path; `validate()` confirms `vr.data_hash == anchor.request_ref` and `anchor.validator == action.author`. `ValidationAttestation` gains `commitment_anchor_hash: Option<ActionHash>` — the attestation coordinator injects it after the commit-reveal hash check, so the hash is verified over the original struct before the field is set; `validate()` confirms `anchor.validator == att_author` and `anchor.request_ref == att.request_ref`. Full cryptographic chain: ValidationAttestation → CommitmentAnchor → ValidationRequest. `commitment_anchor_hash` is `Option` with `#[serde(default)]` for backwards compatibility; always `Some` on entries created after 2026-03-25.
- **N+1 DHT call pattern eliminated (April 2026):** `claim_study`, `get_claims_for_request`, and `get_my_claimed_studies` previously fetched a `ClaimToRelease` link per claim in a loop — N claims = N DHT round-trips. Fixed by two new index link types: `RequestToRelease` (base = study path anchor; tag = 39-byte `ActionHash` of the released claim) and `ValidatorToRelease` (base = validator pubkey; same tag scheme). `release_claim` and `reclaim_abandoned_claim` now write both index links, and all claim-list functions load all release hashes in a single `get_links` call, then `O(1)` set-membership test per claim. DHT round-trips drop from O(N) to O(1) for any study with N validators.
- **Non-deterministic `links.last()` replaced (April 2026):** Five call sites across `attestation_coordinator` and `governance_coordinator` used `links.last()` to retrieve the most-recently-written link. `last()` on a DHT `Vec<Link>` is gossip-order-dependent — agents receive links in different orders depending on network timing. All five sites now use `links.iter().max_by_key(|l| l.timestamp)` which is deterministic regardless of gossip order. Affected functions: `get_difficulty_assessment`, `get_current_phase`, `get_researcher_commitment`, `get_researcher_reveal`, `get_harmony_record`.
- **Additional security guards (April 2026):** Three further protocol gaps closed. (1) *Self-claim prevention at integrity layer:* `StudyClaim validate()` now compares `create_action.author` against the author of the linked `ValidationRequest` via `must_get_valid_record` — the researcher cannot be their own validator even in dev/test mode (no bypass pathway). (2) *Researcher reveal authorisation:* `reveal_researcher_result` in production mode (non-empty `authorized_joining_certificate_issuer`) now fetches the `ValidationRequest` and confirms `action.author == request.author`; an impersonator cannot publish a researcher's reveal. The dev/test bypass (empty issuer key) skips this check to keep local tests simple. (3) *PhaseMarker write idempotency:* `notify_commitment_sealed` now checks for an existing `RequestToPhaseMarker` link before writing a new `PhaseMarker`. In a concurrent quorum completion (two validators both see the threshold met simultaneously), the second writer's check finds the existing marker and skips the write — preventing duplicate `PhaseMarker` entries that would confuse `get_current_phase`.
- **Production reputation gap surfaced (April 2026):** `_update_reputation_internal` is gated behind `system_coordinator_key.is_empty()` so it is a no-op in production — the write would fail `validate()`. `get_validator_reputation` therefore returns nothing in production and every validator's effective `CertificationTier` is `Provisional`. This is the intended Phase 0/Phase 1 boundary — Phase 1 wires in a trusted `update_validator_reputation` caller (oracle or on-chain coordinator key). See Engineer Handover Known Architectural Gaps for full remediation plan.
- **4-tier certification system (April 2026):** `CertificationTier` has four levels: `Provisional` (default) → `Standard` (≥5 completed rounds) → `Advanced` (≥20 rounds + agreement rate ≥60%) → `Certified` (≥50 rounds + rate ≥80%). `cert_tier()` in `governance_coordinator` computes the tier after each `update_validator_reputation` call. Tiers are stored in `ValidatorReputation` entries and used for reputation scoring. Thresholds are placeholder values to be calibrated from real validation data in Phase 0.
- **Badge thresholds use raw participant count (April 2026, revised April 2026):** `evaluate_badge()` in `governance_coordinator` and `badge_ceiling()` in `governance_integrity` both use the same raw-count formula: Gold ≥7 ExactMatch, Silver ≥5 ExactMatch/WithinTolerance, Bronze ≥3 any positive agreement, FailedReproduction ≥3 Divergent/UnableToAssess. Validator tier does not affect which badge is issued — an integrator with 5 validators earns Silver regardless of whether those validators are Provisional or Standard. The integrity zome enforces an **upper-bound check**: the coordinator may issue a lower badge tier than the ceiling (permitted — e.g. Bronze when the network is small), but may never issue a higher tier than raw count warrants. This design keeps badge issuance predictable for integrators and keeps coordinator and integrity logic identical, while reserving tier data for future governance and assignment priority use.
- **AI validator credential path (April 2026):** `ai_validator_issuer: String` added to the attestation `DnaProperties` (default `""` — single-key or bypass). Human validators join via a certificate signed by `authorized_joining_certificate_issuer` (institutional credential). AI validators present a `JoiningCertificate` with `validator_type: AI` signed by `ai_validator_issuer` — the ValiChord operator is the trust anchor rather than an institution. `verify_membrane_proof` in the coordinator parses the certificate's `validator_type` and routes to the correct signing key. When `ai_validator_issuer` is empty, AI certs fall back to the human issuer key (single-key deployments). See `docs/DEPLOYMENT_CHECKLIST.md` for production configuration.
- **Decentralised multi-conductor demo verified working (April 2026):** The full commit-reveal protocol has been demonstrated running across five isolated Docker containers — one researcher conductor, three validator conductors, and one kitsune2 bootstrap server — with no shared memory, no shared filesystem, and communication exclusively through the Holochain DHT. This is the closest a single-machine setup can get to a real multi-party deployment. See `demo/DECENTRALISED_DEMO.md` for full technical details and run instructions.
- **DHT gossip propagation — `get()` after `get_links()` can return `None` (April 2026):** When one conductor writes a record and a second conductor immediately follows a link to it, `get(target, GetOptions::network())` can return `None` even though the link is visible — the link gossips faster than the record body. All coordinator functions that resolve links to records must handle `None` as a retryable miss, not a hard error. `get_current_phase` now returns `Ok(None)` (not `Err`) when the PhaseMarker record body hasn't propagated yet. Callers in JavaScript retry with a loop rather than surfacing a 502. The general rule: any `get()` call that follows a just-written link must be inside a retry loop or return `Option<T>`.
- **`claim_study` return type changed to `Option<ActionHash>` (April 2026):** The function now returns `ExternResult<Option<ActionHash>>`. `None` means "the `ValidationRequest` hasn't gossiped to this conductor yet — retry". `Some(hash)` means success. This is the correct Holochain idiom for functions that query the DHT for data written by another agent: a missing record is a transient gossip-lag condition, not a permanent error. The JavaScript commit loop retries up to 12 times (5s apart) before giving up.
- **Idempotency functions must return the existing value, not `None` (April 2026):** `check_and_create_harmony_record` previously returned `Ok(None)` when a `HarmonyRecord` already existed — treating "already done" as "nothing to return". Fixed: it now returns `Ok(Some(existing_hash))`. Any idempotency guard that short-circuits on "already exists" must return the existing entry hash so callers can proceed rather than interpreting `None` as a failure.
- **`call_attestation_zome_opt` decode failures are soft (April 2026):** In `governance_coordinator`, the `call_attestation_zome_opt` helper that calls across to the Attestation DNA now returns `Ok(None)` on decode failure rather than propagating the error. Under DHT gossip lag, attestation entries may not yet be deserializable on the governance conductor. Returning `None` allows `check_and_create_harmony_record` to retry; a hard error would surface a 502 to the caller and abort the round. The general rule: cross-DNA calls that retrieve data published by another conductor should treat decode failures as soft misses during the propagation window.
- **`reveal_researcher_result` trusts `PhaseMarker` — does not re-query links (April 2026):** The previous implementation called `check_all_commitments_sealed_inner` inside `reveal_researcher_result` as a safety check, re-querying `RequestToCommitment` links to count how many validators had committed. Under DHT gossip lag, this count could be lower than the true number even after `PhaseMarker(RevealOpen)` was written — because some validators' `CommitmentAnchor` links hadn't yet propagated to the researcher's conductor. The fix: `reveal_researcher_result` now calls `get_current_phase` instead. If the phase is `RevealOpen`, it proceeds. The PhaseMarker is the authoritative record of quorum completion — it was written by a validator after all anchors were visible to that validator. Re-querying links after the fact races with gossip and produces false negatives.
- **Red-team security hardening — third round (April 2026):** Six further protocol gaps closed across attestation and governance DNAs. (1) *HarmonyRecord duplicate-validator padding + quorum floor (CRITICAL):* `governance_integrity validate()` for `HarmonyRecord` creates now checks `participating_validators` contains no duplicate `AgentPubKey` entries (HashSet dedup) and that `len >= max(1, min_attestations_for_finalization)`. A colluding validator who fabricated a single-participant `HarmonyRecord` padded with repeated keys to pass count checks is now blocked at the DHT layer. (2) *Retroactive oracle attack (CRITICAL):* `notify_commitment_sealed` (DNA 3) now requires the `ResearcherResultCommitment` to exist on the DHT before any validator may write a `CommitmentAnchor` (production mode only; empty-issuer dev bypass). Without this, a researcher could observe all validator reveals before publishing their "pre-registered" commitment. (3) *Badge type not enforced at integrity layer (HIGH):* `governance_integrity` now contains `evaluate_badge_type()` (mirrors `evaluate_badge()` in coordinator; same thresholds). The `ReproducibilityBadge` validate arm uses `std::mem::discriminant` to reject any badge whose type does not match what the `agreement_level` + `validator_count` would produce. (4) *`FailedReproduction` minimum threshold (HIGH):* `evaluate_badge()` and `evaluate_badge_type()` now both require `validator_count >= 3` for `FailedReproduction` — matching the Bronze threshold. One validator calling `force_finalize_round` with `UnableToAssess` can no longer permanently brand a study as failed. (5) *`ValidationAttestation.discipline` cross-checked against `ValidationRequest` (MEDIUM):* The inductive validation chain in `attestation_integrity` now walks one step further — from `CommitmentAnchor.validation_request_hash` to the `ValidationRequest` — and rejects attestations whose `discipline` field does not match the study's declared discipline. (6) *Duplicate `ValidationRequest` guard (MEDIUM):* `submit_validation_request` now checks the `StudyToValidation` path links before `create_entry`; a second request for the same `data_hash` is rejected at the coordinator layer, preventing non-determinism in COI checks, DHT queries, and badge issuance.
- **Red-team security hardening — second round (April 2026):** Seven further protocol gaps closed across all four DNAs. (1) *Adaptive-reveal via re-sealing (CRITICAL):* `seal_private_attestation` (DNA 2) now checks for an existing `TaskToPrivateAttestation` link before proceeding. A validator who lets `post_commit` fail (leaving no `CommitmentAnchor` on DNA 3) can no longer re-seal with a different verdict after observing others' reveals — the first seal is permanent regardless of whether the notify call succeeded. (2) *Late commit after RevealOpen (MEDIUM):* `notify_commitment_sealed` (DNA 3) now checks `get_current_phase` at the very top and rejects with an error if the phase is already `RevealOpen`. A validator who had not committed before the reveal window opened cannot slip a new `CommitmentAnchor` onto the DHT with knowledge of what others found. (3) *`lock_researcher_result` double-lock (MEDIUM):* The researcher side mirrors the validator duplicate-seal guard — `lock_researcher_result` (DNA 1) checks for an existing `RequestToLockedResult` link and fails if one exists. Without this, a second call with a different nonce would create a new `LockedResult` while the commitment on DNA 3 was fixed to the first nonce, causing a permanent hash mismatch at reveal time and stalling the round. (4) *`CommitmentAnchor.commitment_hash` length unvalidated (MEDIUM):* `attestation_integrity validate()` now rejects any `CommitmentAnchor` where `commitment_hash.len() != 32`. A truncated or padded hash would cause the SHA-256 verification at reveal time to always fail, blocking a round permanently. (5) *`discipline_tag` dot-injection (LOW):* `Discipline::Other("foo.bar")` serialised via `discipline_tag()` produced `"other_foo.bar"` — a DHT path segment with an embedded dot that silently splits the `attestations.{tag}` path anchor into two nodes, losing all attestations for that discipline. Fixed: `.replace('.', "_")` applied after `.to_lowercase()`. (6) *Reputation zip mismatch (MEDIUM — correctness):* `write_harmony_record` (DNA 4) zipped `attestation_records` (gossip-delivery order) with `attestations` (sorted by validator key bytes from the deterministic `pairs` sort). In dev/test mode, when reputation updates run, validators were credited for the wrong discipline/outcome. Fixed: loop now zips `participating_validators` with `attestations`, both derived from the same sorted `pairs` tuples. (7) *`get_locked_result` non-deterministic (LOW):* `get_locked_result` (DNA 1) used `links.last()` — gossip-order-dependent, inconsistent with every other link-selection site in the codebase. Fixed to `links.iter().max_by_key(|l| l.timestamp)`, consistent with the DNA 3 / DNA 4 fixes noted above.
- **Multi-round code audit — efficiency, correctness, error handling, data integrity, API surface (April 2026):** Five independent code audits applied sequentially against the 0.3.2 codebase. Changes: (1) *N+1 elimination in `get_attestations_for_request` (HIGH):* The function previously called `get(anchor_hash)` for every validator in the round — N DHT round-trips. It now reads `link.author` directly from the already-fetched `CommitmentAnchor` link, cutting N round-trips to zero for the attestation list. (2) *Redundant `path.ensure()` removed from `submit_validation_request` (HIGH):* A duplicate `study_path.ensure()` call appeared after the idempotency check that exits early for already-registered studies. The ensure now runs once, before the check. (3) *Hard DoS cap added to `get_attestations_for_discipline` (HIGH):* The function now returns at most 500 records. Without the cap a study with many validators could produce an unbounded allocation on every DHT peer holding that path. (4) *Guard 3 moved before Guard 1 in `notify_commitment_sealed` (HIGH):* The O(1) duplicate-anchor check (Guard 3, link-existence) now runs before Guard 1 (O(n) claim scan). A second commit from the same validator exits immediately rather than scanning all claims. (5) *Tag-based duplicate check for `link_agent_identity` (HIGH):* The identity-link duplicate check now uses a tag-indexed `get_links` query with the other agent's 39 raw bytes as the tag, rather than fetching and deserialising all existing `AgentIdentityAttestation` entries. (6) *`metric_results_msgpack_bytes()` added to `shared_types` (MEDIUM):* Researcher and validator metric hashes previously had independent serialisation paths. A new shared function `metric_results_msgpack_bytes(metrics: &[MetricResult])` uses `rmp_serde::to_vec_named` consistently in both DNA 1 (`lock_researcher_result`) and DNA 3 (`reveal_researcher_result`), guaranteeing byte-for-byte agreement. `rmp-serde` added to `shared_types/Cargo.toml`. (7) *`ValidationPhase::Complete` dead-code annotation (LOW):* The variant is reserved for a future UI indicator but has no protocol role today. Annotated with `#[allow(dead_code)]` and an explanatory comment to prevent confusion. (8) *PRODUCTION bypass warning added (MEDIUM):* `reveal_researcher_result` now emits a `warn!` when the dev/test bypass (empty `authorized_joining_certificate_issuer`) is active, to prevent accidentally deploying with auth disabled. (9) *`CommitmentNotifyFailed` signal added to DNA 2 (HIGH):* DNA 2 now defines a typed `Signal` enum with a `CommitmentNotifyFailed { request_ref, error }` variant. `post_commit` emits this signal when the cross-DNA `notify_commitment_sealed` call fails — replacing the previous silent `debug!` log. The UI must surface this and prompt the validator to retry; without it the validator's slot appears uncommitted and the round stalls. (10) *Fire-and-forget log levels upgraded (HIGH):* `call_governance_fire_and_forget` (DNA 3) now logs at `warn!` on all failure arms. `call_attestation_zome_opt` failure arms in DNA 4 similarly upgraded from `debug!` to `warn!`. Errors that block reputation writes or governance calls must not disappear into debug output. (11) *Validator-type fetch atomicity (MEDIUM):* `check_and_create_harmony_record` in DNA 4 previously used `collect::<ExternResult<Vec<_>>>().unwrap_or_default()` for the validator-type fetch — masking individual fetch failures. The call now propagates errors via `collect::<ExternResult<Vec<_>>>()?`, distinguishing a missing-but-expected validator type (logic error) from a DHT miss (transient). (12) *`check_and_create_harmony_record` deserialization error surfaced (MEDIUM):* The function previously used an `all_match` boolean that silently dropped entries that failed to deserialise as `ValidationAttestation`. It now returns `Err` on the first deserialization failure so the caller can distinguish a genuine agreement-check from one that silently excluded data. (13) *Released claims excluded from Guard 1 (CRITICAL — data integrity):* `notify_commitment_sealed` Guard 1 previously allowed any validator holding a `StudyClaim` link to pass, even if that claim had been released (soft-deleted via `StudyClaimRelease`). A validator who released their claim could still satisfy the commitment quorum. The guard now fetches all `ValidatorToRelease` links for the calling agent, builds a `HashSet<ActionHash>` of released claim hashes, and excludes any released claim from the live-claim check. (14) *TOCTOU races documented (MEDIUM — data integrity):* Two benign TOCTOU windows are now documented in the code: the phase-marker write in `notify_commitment_sealed` (concurrent quorum completion; second writer finds existing marker and skips — content-addressed, safe) and the harmony-record write in `check_and_create_harmony_record` (concurrent finalisation; second writer's entry is identical — content-addressed, idempotent). (15) *`publish_researcher_commitment` authorship guard (HIGH — API surface):* The function now verifies that the caller is the author of the `ValidationRequest`. An impersonator could previously publish a fake researcher commitment under any request hash. Dev bypass (empty issuer key) skips the check for local test conductors. (16) *`assess_difficulty` per-(assessor, study) idempotency guard (HIGH — API surface):* The function now checks for an existing `DifficultyPath` link authored by the caller before writing. A validator cannot inflate difficulty estimates by calling `assess_difficulty` multiple times for the same study.

- **Wind-tunnel expert patterns applied to all four integrity zomes (April 2026):** Two coding patterns from the Holochain Foundation's wind-tunnel performance benchmark repository were applied. (1) `#[derive(Serialize, Deserialize)]` + `#[serde(tag = "type")]` added before `#[hdk_entry_types]` on all four `EntryTypes` enums — gives the outer enum a sensible internally-tagged representation if it is ever serialized directly (signals, link tags, cross-zome payloads). Safe because `to_app_option::<T>()` deserializes from the raw inner entry bytes, not through the outer enum. (2) `handle_error!` macro added to `governance_integrity` and `attestation_integrity` validate() callbacks. All `map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?` + `.ok_or_else(|| wasm_error!(...))?` chains replaced with soft `ValidateCallbackResult::Invalid` returns. Previously a deserialization error in validate() hard-crashed the WASM host (non-recoverable — same error class as out-of-memory); it now cleanly rejects the entry with an informative message, which is semantically correct — a malformed entry is invalid, not a system error. Five sites updated: badge→HarmonyRecord (governance), StudyClaim→ValidationRequest, CommitmentAnchor→ValidationRequest (×2), and ValidationAttestation→CommitmentAnchor (attestation). The `commitment_anchor_hash` missing-field path converted by the same logic.

**What this document is for:** An engineer reading this should understand what ValiChord needs to do, what data it handles, how components interact, and where the hard problems are. It should save weeks of explanation and allow technical discussion to begin at the right level.

**What this document is not:** Production code, a specification that can be implemented without modification, or evidence of technical progress beyond architectural design.

**Technical feasibility confirmed:** Paul D'Aoust (Documentation and Developer Community Lead, Holochain Foundation) reviewed the architectural approach and confirmed it is implementable with the current Holochain framework (January 2026). Shin Sakamoto, an independent Holochain application developer, also reviewed the architecture. Arthur Brock (co-founder and architect, Holochain) conducted a solution engineering review and provided detailed implementation guidance, including the multi-DNA membrane architecture (February 2026). Joel Marcey (Tech Director, Rust Foundation) reviewed both this document and the MVP Specification and confirmed the approach is sound (February 2026). This confirms the *approach* is sound, not that these specific structs are final.

---

## Architecture Overview

### Four-DNA Membrane Architecture (the real structure)

ValiChord is built as four distinct Holochain DNA membranes. This is the actual engineering structure — not a logical model but the literal organisation of code, data, and network boundaries. Each DNA is a separate peer-to-peer network with its own membrane governing who can join and what data is shared within it.

```
┌──────────────────────────────────────────────────────────────────┐
│ DNA 4 — Governance & Harmony Records                             │
│ Public DHT. Harmony Records, badges, reputation, governance.     │
│ What journals, funders, and institutions query via HTTP Gateway. │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ DNA 3 — Attestation                                              │
│ Shared DHT, credentialed membrane.                               │
│ The act of validation: requests, attestations, warrants.         │
│ All inter-validator coordination happens here.                   │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ DNA 2 — Validator Workspace           (private, per validator)   │
│ Local only. Where reproduction work happens.                     │
│ Private attestation sealed here before the reveal session.       │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ DNA 1 — Researcher Repository         (private, researcher only) │
│ Local only. Code, data, protocols under researcher control.      │
│ Only a cryptographic hash travels outward. GDPR by architecture. │
└──────────────────────────────────────────────────────────────────┘
```

The detailed specification of each DNA — entry types, link types, validate callbacks, and coordinator zome functions — is in the Holochain Architecture Notes section below.

### Conceptual Layer Map

The eight-layer framework below describes ValiChord's functional responsibilities. It is a conceptual map, not the engineering structure — the responsibilities are distributed across the four DNAs above, not stacked in a single application. The diagram is retained because it communicates *what* ValiChord does clearly; the DNA architecture above is *how* it is built.

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 8: Access & Presentation (Human Interface)        │
│ Dashboards for researchers, validators, funders, public │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 7: Integration & Interface (Ecosystem)            │
│ How external systems query/submit to ValiChord          │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 6: Incentive & Reputation (Participation)         │
│ Why validators validate, why researchers participate    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 5: Output & Certification (Trust Signals)         │
│ What the world sees: Harmony Records, badges, reports   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 4: Audit & Provenance (Memory)                    │
│ Tamper-evident record of every action, complete traceability │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: Governance & Policy (Rules)                    │
│ Who decides standards, how disputes resolve             │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: Validation Engine (Orchestration)              │
│ Validator selection, gaming detection, agreement analysis │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: Intake & Pre-Commitment (Claims Entry)         │
│ Protocol registration, pre-commitment, deviation tracking│
└─────────────────────────────────────────────────────────┘
┌═════════════════════════════════════════════════════════╗
║ LAYER 0: Data & Integrity (Foundation)                  ║
║ Content-addressed storage, cryptographic integrity      ║
╚═════════════════════════════════════════════════════════╝
```

### Layer Interactions & Data Flow

The eight layers describe functional responsibilities, not a central stack. In the multi-DNA architecture, these responsibilities are distributed across separate networked organisms — what looks like a vertical stack in the diagram maps onto coordinated, peer-to-peer participants. The flows below describe the logical sequence of events across that distributed system.

**Registration Flow (Layers 1 → 0 → 4):**
1. Researcher submits protocol via Layer 1 (Intake)
2. Data uploaded to Layer 0 (Integrity)
3. Registration recorded in Layer 4 (Audit)

**Validation Flow (Layers 2 → 0 → 4 → 5):**
1. Validators assigned via Layer 2 (Engine)
2. Fetch data from Layer 0 (Integrity)
3. Attestations logged to Layer 4 (Audit)
4. Harmony Record generated in Layer 5 (Output)

**Reputation Flow (Layers 2 → 4 → 6):**
1. Validation behaviour tracked in Layer 2
2. Historical data from Layer 4
3. Scores updated in Layer 6 (Reputation)

**Governance Flow (Layers 3 → 1, 2, 6):**
1. Policy bodies (Layer 3) set standards
2. Enforced in Intake (Layer 1), Engine (Layer 2), Reputation (Layer 6)

**Access Flow (Layers 8 → 7 → 5, 6):**
1. Users access via Layer 8 (Presentation)
2. Integrations via Layer 7 (Interface)
3. Query Output (Layer 5) and Reputation (Layer 6)

---

### Multi-DNA Architecture and Membranes

ValiChord is designed as a set of distinct, composable Holochain applications (DNAs) rather than a single monolithic application. Each DNA creates its own encrypted peer-to-peer network with its own **membrane** — the boundary that governs who can join that network and what data is shared within it.

This is the recommended pattern for Holochain applications where different participants need different data spaces. Multiple small, focused apps communicating through bridges is architecturally cleaner, easier to update, and more stable than a single large application managing access internally. In distributed software, updates to an integrity zome change the DNA's identity, creating a new separate network — participants do not need to upgrade simultaneously, but must eventually upgrade to enter the new shared space. Keeping each DNA small and stable minimises how often this migration is necessary. (Note: Holochain is actively developing features to ease version continuity, but these are not yet fully implemented.)

Each DNA creates a distinct networked organism: even where two DNAs share identical code, small configuration differences — including a **network seed**, a unique property baked into each instance — make them separate organisms that will only synchronise among their own nodes. This is the mechanism that makes the privacy separation absolute: the Researcher Repository DNA and the Attestation DNA are not the same network with different access rules applied; they are genuinely different networks that happen to share some code patterns.

**DNA 1 — Researcher Repository App** *(private membrane)*
Runs locally on the researcher's or institution's machine. Holds code, data, and methods. Only the researcher and their institution can join. Nothing sensitive ever enters the shared network — the researcher publishes only a cryptographic commitment (metadata and hash) outward to the Attestation DNA. GDPR compliance is architecturally enforced, not just policy: data cannot enter the shared DHT because it lives in a separate, private DNA.

**DNA 2 — Validator Workspace App** *(private membrane, per validator)*
Each validator runs this locally — the "Repro Witnessing hApp." Their private reproduction environment: where they run the analysis, where working results are held. Only this validator can join. Because the local app controls exactly how data is serialised before producing a hash, outputs are consistent regardless of database query ordering or other non-deterministic operations. Only a signed attestation — never raw reproduction results — leaves this space.

**DNA 3 — Attestation App** *(shared DHT, credentialed participants)*
The core shared layer. Records the *act* of validation: protocol registered, attestation signed, warrant issued on disagreement. Not the content of the validation — only the signed outcome summary. Agreement detection operates on structured outcome summaries, not raw result hashes. This resolves the fundamental problem that computational reproduction almost never produces bit-identical outputs: two validators can agree without their results being identical to the byte.

**DNA 4 — Governance and Harmony Records App** *(public DHT)*
Harmony Records, badges, and public validation status — what journals, funders, and institutions query. Governance-controlled writing, publicly readable. Anti-domestication mechanics live here: default salience rules, anti-delay constraints, funding concentration tripwires.

The eight-layer framework below remains the correct conceptual description of what ValiChord does. The layers now map across these four DNAs rather than sitting in one application. Where a layer's primary home in the DNA structure is relevant, it is noted.

**Precedent:** This four-DNA membrane pattern is independently validated by the holo-health project, a Holochain-based architecture for person-centric healthcare ecosystems designed by Steve Melville (https://github.com/evomimic/holo-health/blob/master/holo-health-app-architecture.md). The holo-health architecture uses an identical structure for an analogous problem: a private Personal Health Vault (equivalent to ValiChord's Researcher Repository DNA) holds sensitive personal data under the individual's control; a Health Market hApp (equivalent to ValiChord's Attestation DNA) provides the shared public space where parties find each other under agreed terms; and a Health Service Delivery hApp (equivalent to ValiChord's per-validation private channel) creates a private, audited space for each individual transaction, recording the *act* of data sharing without storing the sensitive data itself. Two independent teams reached the same membrane architecture for the same class of problem — sensitive personal data that must remain under individual control while participating in a shared verification ecosystem.

---

### How a Researcher Experiences This

The eight layers below are architectural components, not sequential steps. A researcher doesn't navigate them one by one — they interact with ValiChord through a single submission process, and the layers work together behind the scenes. Here's the chronological experience:

1. **Researcher submits study** (data, code, protocol — one submission). Layer 0 fingerprints and stores the materials. Layer 1 registers the protocol claims. Layer 2 assesses difficulty.
2. **Validators are anonymously assigned** based on expertise matching and conflict-of-interest screening (Layer 3 governance, Layer 2 engine).
3. **Validators download materials** from Layer 0 — the fingerprint guarantees every validator works from identical data.
4. **Validators independently attempt reproduction** and submit their findings (Layer 2).
5. **Results are recorded** as a Harmony Record — preserving agreement, disagreement, and uncertainty (Layer 5), with full provenance (Layer 4).
6. **Gaming detection** runs continuously in the background (Layer 2, Layer 6).
7. **The Harmony Record is published** and accessible to researchers, journals, funders, and the public (Layer 7, Layer 8).

The layers interleave — they don't stack sequentially. What follows is the engineering breakdown of each layer.

The eight layers divide ValiChord's responsibilities as follows. **Layer 0** is the cryptographic foundation: content-addressed storage ensuring every validator works from provably identical materials. Without it, no validation claim can be trusted. **Layer 1** handles protocol intake and pre-commitment: structured pre-registration, deviation tracking, and epistemic impact assessment — the front-end guarantee that research questions were honestly specified before results were known. **Layer 2** is the validation engine: validator selection, blind commitment protocols (private source chain entries sealed before simultaneous countersigned reveal), gaming detection, agreement analysis, and the warrant mechanism that flags and records bad actors without requiring central enforcement. **Layer 3** is governance: the discipline-specific standards, anti-capture mechanics, and accountability structures that define the rules of the system and resist institutional pressure to soften them. **Layer 4** is the audit and provenance layer: a tamper-evident record of every action, distributed across Holochain's participant network, providing the accountability chain that external parties rely on. **Layer 5** produces outputs: Harmony Records, badges, and certification signals that journals, funders, and institutions consume. **Layer 6** handles incentives and reputation: the multi-dimensional scoring and career credit mechanisms that make sustained participation rational for working researchers. **Layers 7 and 8** handle integration and presentation: the HTTP Gateway, REST APIs, and user interfaces that connect ValiChord to the wider ecosystem without requiring institutional partners to replace existing systems. Each layer maps to one or more of the four Holochain DNAs described above — the engineering breakdown notes the primary DNA home where relevant.

---

## LAYER 0: Data & Integrity Foundation

**Purpose:** Ensure all validators work from provably identical materials, and that those materials remain available and verifiable long-term.

**Why this is critical:** ValiChord's core claim is that multiple independent validators assessed the same study. For that claim to be verifiable — not just asserted — every validator must provably have worked from the same data, code, and protocol. Content-addressed verification guarantees this: each participant's local node generates a cryptographic fingerprint of every submitted file. For research files (data, code, protocol documents), SHA-256 is used — the standard for academic repositories and broadly supported by verification tools. Holochain's own internal addressing uses BLAKE2b, a faster algorithm, for its records and attestations. These are separate layers: the SHA-256 fingerprint identifies the research materials; Holochain's BLAKE2b addressing identifies the validation actions performed on them. Change a single bit and the fingerprint changes. Anyone can verify, at any time, that their copy matches every other copy. Arthur Brock describes this property as **intrinsic data integrity**: the data is self-validating — you can tell if it has been tampered with because the tampering breaks the packaging. The data itself can be stored on any reliable provider — academic repositories, cloud storage, or institutional systems. What matters is the fingerprint recorded on Holochain, not where the files live. Redundant storage across multiple providers ensures the materials outlive any single institution.

### Core Data Structure

> **Type conventions:** Throughout this document, the following type aliases are assumed: `ExternalHash` = `[u8; 32]` (SHA-256 digest for research file fingerprints; Holochain internally uses BLAKE2b for its own addressing), `DateTime` = UTC timestamp, `AgentId` = Holochain `AgentPubKey` (unique cryptographic identity per participant).
>
> **Important on AgentPubKey size:** `AgentPubKey` in Holochain is **39 bytes, not 32**. It carries a multihash protocol prefix and a DHT location suffix in addition to the 32-byte key material. Using `[u8; 32]` as an `AgentId` type alias in a scaffold is structurally incorrect — replace with the HDK's native `AgentPubKey` type at implementation time.
>
> Other aliases: `ValidatorId` = `AgentId` (alias for readability when the agent is acting as a validator), `Discipline` = enum of scientific fields, `Signature` = cryptographic signature (illustrative alias; in implementation use `Option<Vec<u8>>` — raw signature bytes — as in the scaffold). These are illustrative — final type definitions depend on Holochain SDK version and engineering decisions.

```rust
/// Content-addressed, tamper-evident data snapshot.
///
/// Note: created_at, creator_id, and a separate content_id are deliberately
/// omitted — Holochain Actions carry author key, timestamp, and sequence number
/// natively. Duplicating them inside entry structs is both redundant and
/// unreliable (the author can set them to anything).
pub struct VerifiedDataSnapshot {
    /// SHA-256 fingerprint of the research files (data, code, protocol).
    /// This is the integrity guarantee — the storage location is secondary.
    pub sha256_hash: ExternalHash,
    
    /// Where the files can be downloaded. Any provider is acceptable;
    /// the hash — not the location — is the integrity proof.
    pub storage_locations: Vec<StorageLocation>,
    
    pub size_bytes: u64,
}

/// Storage location is deliberately agnostic — the fingerprint matters, not where the data lives.
/// Academic repositories (Zenodo, Figshare, institutional repositories) are the natural first choice
/// for research data. Cloud storage (S3, Azure Blob) is also viable. Decentralised storage (IPFS,
/// Arweave, Filecoin) remains an option but is not required.
pub enum StorageLocation {
    Zenodo { deposit_id: String },
    Figshare { article_id: String },
    InstitutionalRepository { url: String },
    S3 { bucket: String, region: String },
    Other { provider: String, location: String },
}
```

> **Engineering note:** The choice of storage provider is an implementation decision, not an architectural one. The integrity guarantee comes from the content hash recorded on Holochain, not from the storage system itself. Any provider that allows validators to download the original files and verify the hash is sufficient. Academic repositories are preferred for familiarity, trust, and long-term sustainability. Storage costs and provider longevity are operational concerns that need addressing in Phase 1/2 planning.

### Large Dataset Handling

**Problem:** Terabyte datasets are slow to download but validators need the complete dataset to run the code.

**Solution:** Standard SHA-256 hash verification. Validators download the full dataset from the storage provider, hash it locally, and compare against the fingerprint recorded on Holochain. Match means identical data. This works for any file size.

> **Engineering note:** At Phase 3 scale, if bandwidth from source repositories becomes a bottleneck, peer-to-peer chunk distribution between validators could reduce load. This is a future performance optimisation, not a current architectural requirement.

### GDPR Compliance: Data/Proof Separation

**Challenge:** ValiChord processes personal data (researcher identities, institutional affiliations, validation records). EU data subjects have rights under GDPR including rights of access, rectification, and erasure. The architecture must handle these without undermining the integrity of the validation record.

**A note on Article 17 ("right to be forgotten"):** This right is frequently cited in distributed systems discussions but is more nuanced than commonly understood. Article 17(3)(d) provides a research exemption: the right to erasure does not apply where compliance would render scientific research objectives impossible or seriously impaired (subject to Article 89 safeguards). For most ValiChord validation records, this exemption is likely to apply — a validator cannot retrospectively erase their attestation without undermining the integrity of the entire record. The more substantive privacy concern for ValiChord is not erasure rights but the principle of data minimisation: sensitive data should not enter the shared DHT in the first place.

**Solution:** In the multi-DNA architecture, privacy is structurally enforced: sensitive data lives in the private Researcher Repository DNA and cannot enter the shared Attestation DHT by design. The membrane is the primary protection — not a policy overlay on top of a shared system, but a genuine architectural separation. The hash approach below provides an additional layer for any data summary properties that do need to travel to the Attestation layer.

```rust
/// Hash research data with a salt for privacy protection.
///
/// Note: This salting is specifically for research DATA hashes — it prevents
/// re-identification of sensitive datasets by an attacker who might otherwise
/// brute-force the hash. It is NOT needed for Holochain Actions, which carry
/// their own cryptographic uniqueness natively via author key, sequence number,
/// and timestamp. Apply this function only when hashing raw research content,
/// not when referencing Holochain entries.
pub fn hash_dataset_with_salt(data: &[u8], salt: &[u8]) -> ExternalHash {
    let salted = [data, salt].concat();
    ExternalHash::digest(&salted)
}

// Validator receives salt from data custodian off-DHT
// DHT stores only salted hash
// Attacker cannot compute same hash without salt
// Re-identification prevented
```

> **Engineering note:** Holochain Actions already contain unique properties that differentiate hashes — explicit random salting of Action/Record hashes is therefore unnecessary, as the Action itself provides equivalent uniqueness. For data hashes specifically (where the content being hashed is research data rather than a Holochain Action), the serialisation approach remains the more fundamental question: the Validator Workspace DNA must ensure data is serialised identically before hashing. The salt distribution mechanism is a secondary concern once the membrane architecture guarantees data locality.

A further privacy property follows from how Holochain records actions: a researcher can share a history of **headers** — each containing a timestamp, sequence number, and hash of the entry below it — without ever sharing the data those headers refer to. This means a researcher can prove to an external party that a particular dataset existed at a particular time, and that it has not been modified since, without the data itself ever leaving the private Researcher Repository DNA. For GDPR-sensitive studies, this header-only provenance path allows the Attestation layer to carry full chronological accountability while the underlying data remains under the researcher's control.

---

## LAYER 1: Intake & Pre-Commitment

**Purpose:** Bring research into ValiChord in structured, machine-legible form with pre-commitment enforcement. This is the front-end protection that complements back-end validation.

### Pre-Registered Protocol

```rust
/// Pre-registered protocol with committed analysis plan.
///
/// Note: protocol_id and registered_at are deliberately omitted.
/// The Holochain ActionHash IS the protocol identifier, and the Action
/// carries the timestamp natively. To record a modification, call
/// update_entry() and create a linked DeclaredDeviation entry —
/// Holochain preserves the full update chain automatically.
/// No application-level TimeLocked wrapper is needed or appropriate.
pub struct PreRegisteredProtocol {
    /// Plain analysis plan description — Holochain immutability enforces
    /// the commitment without any wrapper struct.
    pub analysis_plan_description: String,
    
    /// Pre-specified hypotheses
    pub hypotheses: Vec<Hypothesis>,
    
    /// Confirmatory vs exploratory declaration
    pub analysis_type: AnalysisType,
    
    /// Pre-specified outcome measures
    pub primary_outcomes: Vec<OutcomeMeasure>,
    pub secondary_outcomes: Vec<OutcomeMeasure>,
    
    /// Stopping rules (when to end data collection)
    pub stopping_rules: StoppingRules,
    
    /// Sample size justification
    pub sample_size: SampleSizeSpec,
    
    /// Deviation allowances (structured)
    pub allowed_deviation_types: Vec<DeviationType>,
    
    /// Institutional signature
    pub institutional_approval: Option<Vec<u8>>,
}

/// **Note on protocol immutability:** A `TimeLocked<T>` wrapper struct is
/// **not needed in Holochain** and should not appear in the implementation.
///
/// In Holochain, all entries on the source chain are immutable by architecture —
/// there is no mutable state to lock. "Modifications" in Holochain create new,
/// immutable entries that mark the previous record as updated, preserving the
/// complete chronological history automatically. A `TimeLocked` wrapper adds
/// application-level complexity to enforce something the architecture already
/// guarantees.
///
/// The correct Holochain pattern:
///   1. Researcher creates `PreRegisteredProtocol` entry → source chain records it
///      with author key, timestamp, and sequence number
///   2. If protocol must be modified → researcher calls `update_entry(original_hash, new_protocol)`
///      → Holochain creates a new immutable record pointing back to the original
///   3. Any peer can retrieve the full chain of updates via `get_details(original_hash)`
///   4. Any peer can verify nothing was backdated — source chain sequence enforces
///      chronological ordering cryptographically
///
/// For explicit deviation tracking (where the reason for the change matters),
/// create a separate `DeclaredDeviation` entry linked to the original protocol.
/// This gives you a structured, queryable deviation record without needing a wrapper.
pub struct PreRegisteredProtocolNote; // See struct definition above
```

### Deviation Typology

Not all deviations are equal. The system must distinguish between them.

```rust
pub enum DeviationType {
    /// Data access issues (ethical, logistical)
    DataAccess {
        reason: String,
        impact: EpistemicImpact,
    },
    
    /// Ethical concerns requiring protocol change
    EthicalConcern {
        review_board: String,
        decision_date: DateTime,
    },
    
    /// Statistical model didn't converge as planned
    ModelFailure {
        attempted_model: String,
        fallback_model: String,
        justification: String,
    },
    
    /// Computational constraints
    ComputationalLimit {
        planned_method: String,
        actual_method: String,
        reason: String,
    },
    
    /// Sample size adjustment
    SampleSizeAdjustment {
        original_n: usize,
        revised_n: usize,
        power_analysis: String,
    },
}

pub enum EpistemicImpact {
    /// No impact on inference
    Minimal,
    
    /// May affect confidence bounds
    Moderate,
    
    /// Changes interpretation — triggers governance review
    Substantial,
}
```

### Verifiable Claim Structure

```rust
/// Explicit, versioned, testable claim
pub struct VerifiableClaim {
    pub claim_id: Hash,
    
    /// Natural language statement
    pub statement: String,
    
    /// Formal specification
    pub formal_spec: FormalClaim,
    
    /// Dependencies on other claims
    pub depends_on: Vec<Hash>,
    
    /// Evidence requirements
    pub evidence_threshold: EvidenceThreshold,
    
    /// Claim hierarchy position
    pub claim_type: ClaimType,
}

pub enum ClaimType {
    Primary,
    Secondary,
    Exploratory { disclosed: bool },
    Robustness,
}

pub struct FormalClaim {
    pub null_hypothesis: String,
    pub alternative_hypothesis: String,
    pub significance_threshold: f64,
    pub test_statistic: String,
    pub direction: Direction,
}
```

### External Linking

```rust
pub struct ExternalLinks {
    pub osf_project: Option<String>,
    pub github_repo: Option<String>,
    pub preregistration_doi: Option<String>,
    pub trial_registry: Option<String>,
}
```

### Submission Workflow

```
Researcher submits protocol
         ↓
Protocol normalised to ClaimObject
         ↓
Pre-commitment validation rules check:
  • Hypotheses testable?
  • Outcome measures specified?
  • Stopping rules clear?
  • Sample size justified?
         ↓
Time-lock applied (sealed after 24h)
         ↓
Protocol hash posted to DHT
         ↓
Institutional signature required
         ↓
Protocol registered → can begin data collection
```

> **Engineering question:** The "normalised to ClaimObject" step is hand-waved here. In practice, converting free-text research protocols into structured, machine-legible claims is a significant NLP/UX challenge. This likely needs a structured submission form rather than automated parsing. The exact form design is a Phase 1 task.

---

## LAYER 2: Validation Engine

**Purpose:** Coordinate distributed validation with gaming detection and collusion resistance. This is ValiChord's core.

### Validation Request

```rust
pub struct ValidationRequest {
    /// References Layer 1 pre-registered protocol
    pub protocol_ref: Hash,
    
    /// Or external protocol if pre-registration not required
    pub protocol: Option<Protocol>,
    
    /// SHA-256 hash of study data — the ONLY thing from the private
    /// Researcher Repository DNA that crosses into this shared network.
    /// The full VerifiedDataSnapshot stays in DNA 1; only the hash travels.
    pub data_hash: ExternalHash,
    
    /// Validation parameters
    pub num_validators_required: u8,
    pub validation_tier: ValidationTier,
}

pub enum ValidationTier {
    /// Simple computational reproducibility
    Basic,
    
    /// Includes robustness checks
    Enhanced,
    
    /// Full methodological review
    Comprehensive,
}
```

### Automated Difficulty Assessment

**Purpose:** Predict validation difficulty from observable surface features before a validator begins work. This determines compensation bands, triage routing, time estimates, and exclusion recommendations.

**Why this matters:** Without difficulty prediction, every study entering ValiChord is a guess — you can't quote a time to a journal, set fair compensation for a validator, or tell a funder what validation costs per study. The difficulty assessment system is what makes ValiChord operationally viable.

**Phase 0 provides the training data.** By recording surface features alongside actual validation time and difficulty, Phase 0 produces the first empirical link between what a study looks like from the outside and what validation actually involves. This evidence underpins every stage of the assessment system.

#### Stage 1: Rule-Based Scoring (Phase 1, early)

A weighted rubric derived directly from Phase 0 correlations. When a study enters ValiChord, the system scores observable features:

```rust
pub struct DifficultyAssessment {
    /// Surface feature scores (each 1-5)
    pub code_volume: u8,           // Lines of code, number of scripts
    pub dependency_count: u8,       // External packages, libraries, APIs
    pub documentation_quality: u8,  // README presence, inline comments, method description
    pub data_accessibility: u8,     // Public download, request-access, proprietary
    pub environment_complexity: u8,  // Standard languages vs proprietary software, containers
    pub study_age: u8,             // Years since publication (older = more dependency rot)
    
    /// Weighted composite score → predicted difficulty tier
    pub predicted_tier: DifficultyTier,
    pub predicted_min_secs: u64,   // u64 seconds throughout — avoids WASM Duration serialisation
    pub predicted_max_secs: u64,
    pub confidence: AssessmentConfidence,
}

pub enum DifficultyTier {
    Standard,     // ~4-8 hours predicted
    Moderate,     // ~8-16 hours predicted
    Complex,      // ~16-30 hours predicted
    Extreme,      // ~30+ hours predicted — flagged for triage review
    Excluded,     // Fails minimum criteria — not accepted into system
}
```

Weights are set from Phase 0 data. If Phase 0 shows documentation quality is the strongest predictor and study age barely matters, the rubric reflects that. A researcher submitting a study or a journal integrating with ValiChord receives an immediate difficulty estimate.

This is straightforward engineering. The scoring rubric could be a simple web form initially, or — better — a script that analyses a code repository automatically.

#### Stage 2: Semi-Automated Analysis (Phase 1, later)

A tool that pulls a study's code repository and automatically generates surface feature scores:

- Count lines of code across all scripts
- Identify and count external dependencies (from requirements.txt, DESCRIPTION, package.json, etc.)
- Check for README, documentation files, inline comment density
- Test whether data URLs resolve and data files are downloadable
- Detect proprietary software requirements
- Check for Docker/container definitions
- Assess age of last commit and dependency versions

Output: automated difficulty estimate with confidence level, flagging studies that need human triage review.

**Precedent:** This type of automated assessment is well-established in adjacent domains:

- **Ripeta / RipetaScore** (Digital Science): Uses NLP and machine learning to automatically score scientific papers on reproducibility trust markers — data availability, code availability, methodology transparency, ethical approvals. Integrated into Dimensions database (33 million papers) and the Editorial Manager submission system. Produces a weighted composite score (0–30) combining professionalism and reproducibility indicators. Published in *Frontiers in Research Metrics and Analytics* (2021). Ripeta assesses *reporting quality* from the manuscript; ValiChord's system would assess *validation difficulty* from the code and data — a complementary but distinct prediction target.

- **SonarQube / Code Climate**: Industry-standard automated code quality platforms used by millions of developers. Score code on cyclomatic complexity, duplication, dependency health, test coverage, and maintainability. These metrics overlap substantially with what predicts validation difficulty — complex, poorly-tested, heavily-dependent code is harder to validate. ValiChord could integrate or adapt these scoring engines rather than building from scratch.

- **CODECHECK** (Cambridge/Münster): An open-science initiative where independent codecheckers attempt to reproduce computational results and issue certificates. 25+ checks completed across multiple journals. CODECHECK demonstrates the manual version of what ValiChord automates — and its experience confirms that documentation quality and environment specification are key determinants of reproducibility success.

- **FAIRER-Aware Reproducibility Assessment**: A government-backed checklist tool scoring data assets and code on findability, accessibility, interoperability, reusability, ethics, and reproducibility. Discipline-agnostic. Demonstrates that structured, automated reproducibility scoring is both feasible and institutionally accepted.

**What none of these tools do** is predict how long validation will actually take, or link surface features to empirical time data. That is the specific gap Phase 0 fills, and the specific capability the ValiChord difficulty assessment system provides.

#### Stage 3: Statistical Model (Phase 2+, with volume)

Once Phase 1 generates 200+ validations with linked surface features and actual time data, a regression model can be trained:

- Input: surface feature scores (automated from Stage 2)
- Output: predicted validation time, difficulty tier, and confidence interval
- Model improves as data accumulates — each completed validation is a new training example
- Can eventually identify non-obvious predictors that rule-based systems miss

This requires volume that Phase 0 and early Phase 1 cannot provide. 60–75 validation events from Phase 0 establish which features matter; 200+ from Phase 1 start making statistical prediction viable; Phase 2's scale makes it reliable.

> **Engineering note:** The three stages are not replacements but layers. Stage 1 provides the initial rubric. Stage 2 automates data collection for the rubric. Stage 3 learns from accumulated evidence to refine predictions beyond what any rubric captures. All three can coexist — the rule-based system provides explainable baseline scores while the statistical model flags cases where its predictions diverge from the rubric, indicating non-obvious difficulty.

#### Improvement Feedback (Phase 1+)

Studies that fail triage or score poorly on the difficulty assessment should not simply be rejected. The assessment system already knows *why* a study scored poorly — the same surface feature scores that determine difficulty can generate actionable improvement recommendations.

```rust
pub struct ImprovementReport {
    pub study_ref: Hash,
    pub overall_assessment: DifficultyTier,
    pub feature_scores: DifficultyAssessment,
    
    /// Specific, actionable recommendations per low-scoring feature
    pub recommendations: Vec<ImprovementRecommendation>,
    
    /// Estimated tier after improvements applied
    pub projected_tier_if_improved: DifficultyTier,
}

pub struct ImprovementRecommendation {
    pub feature: SurfaceFeature,
    pub current_score: u8,
    pub target_score: u8,
    pub action: String,         // e.g., "Pin dependency versions in requirements.txt"
    pub guidance_link: String,   // Link to best-practice documentation
    pub estimated_effort: String, // e.g., "~2 hours"
}
```

**Why this matters beyond ValiChord:** Every study that improves its documentation, pins its dependencies, or makes its data accessible in response to ValiChord feedback becomes more reproducible for *everyone* — not just for ValiChord validators. The feedback system turns ValiChord from a verification service into an active driver of better computational research practices. Over time, studies arriving at ValiChord get cleaner because researchers learn what validatable research looks like.

**Equity dimension:** The researchers who produce the most meticulously documented code repositories tend to be those in well-funded labs with dedicated research software engineers and institutional support. Early-career researchers, those in under-resourced institutions, and interdisciplinary thinkers who learned to code independently may produce groundbreaking science with poorly organised materials. Without feedback, ValiChord's triage filters them out — validating the studies that were already most likely to be reproducible. With feedback, ValiChord ensures that validation accessibility isn't determined by institutional resources.

#### Assisted Correction (Phase 2+)

Beyond diagnostic feedback, ValiChord can generate *proposed corrections* — a drafted README, pinned dependencies, restructured file organisation, clearer method descriptions — that the researcher reviews and approves before resubmission.

```rust
pub struct AssistedCorrection {
    pub study_ref: Hash,
    pub original_materials: MaterialsSnapshot,
    
    /// Proposed corrected versions of low-scoring materials
    pub proposed_corrections: Vec<CorrectionProposal>,
    
    /// Status: always requires explicit author approval
    pub status: CorrectionStatus,
}

pub enum CorrectionStatus {
    /// Corrections generated, awaiting author review
    PendingAuthorReview,
    
    /// Author has reviewed and approved all corrections
    AuthorApproved { approved_at: Timestamp, author_id: AuthorId },
    
    /// Author has edited corrections before approving
    AuthorModified { modified_at: Timestamp, author_id: AuthorId },
    
    /// Author has rejected corrections (with reason)
    AuthorRejected { reason: String },
}
```

**Critical constraint: ValiChord never modifies or submits research materials without explicit author approval.** Automated corrections might pin wrong dependency versions, mischaracterise methods, or restructure code in ways that subtly change its behaviour. Only the author knows whether the corrected version faithfully represents their work. A clean-looking README that misrepresents the analysis is worse than a messy one that's honest. The author's name is on the research; the author retains control.

**Workflow:** Submit study → triage scores it → study doesn't meet threshold → ValiChord generates proposed corrections → author reviews → author approves, edits, or rejects → approved version enters validation pipeline.

**Precedent:** Ripeta already does this for manuscript reporting quality — it scores papers and tells authors what's missing before peer review. SonarQube does it for code quality in software engineering. ValiChord would do it for *validatability* — a dimension nobody currently assesses or provides feedback on. The assisted correction step goes further than any existing tool by proposing fixes rather than just identifying problems.

#### Self-Service Pre-Vetting Tool (Phase 2+)

The feedback and assisted correction systems are reactive — they operate after submission. The self-service tool moves assessment upstream: researchers run ValiChord's scoring rubric locally, on their own machine, before ever interacting with ValiChord's infrastructure.

```rust
pub struct PreVetReport {
    /// Generated locally — never transmitted unless researcher opts in
    pub repository_path: String,
    pub scan_timestamp: Timestamp,
    
    /// Same scoring rubric as ValiChord triage
    pub feature_scores: DifficultyAssessment,
    pub predicted_tier: DifficultyTier,
    
    /// Actionable feedback per low-scoring feature
    pub recommendations: Vec<ImprovementRecommendation>,
    
    /// Overall readiness signal
    pub triage_prediction: TriagePrediction,
}

pub enum TriagePrediction {
    /// Likely to pass ValiChord triage as-is
    Ready,
    
    /// Likely to pass after addressing listed recommendations
    NearReady { blocking_issues: Vec<SurfaceFeature> },
    
    /// Significant work needed before submission
    NotReady { major_gaps: Vec<SurfaceFeature> },
}
```

**What the tool does:**

- Scans the local repository for documentation (README, method descriptions)
- Checks whether dependencies are pinned (requirements.txt, environment.yml, Dockerfile)
- Tests whether data URLs resolve (HTTP HEAD requests only — no downloads)
- Counts code volume, identifies languages and frameworks
- Checks for containerisation (Docker, Singularity)
- Assesses repository age and commit recency
- Produces a `PreVetReport` with scores, recommendations, and predicted triage outcome

**What the tool does NOT do:**

- Execute any research code (static analysis only — prevents malicious repository exploitation)
- Transmit any data without explicit opt-in (works fully offline by default)
- Confer any status within ValiChord's pipeline (pre-vetting carries zero authority; ValiChord runs its own triage regardless)
- Hide its scoring logic (the rubric is public by design — transparency about standards is the feature, not a vulnerability)

**Security model:**

| Concern | Mitigation |
|---|---|
| Malicious repository exploits scanning | Static analysis only; no code execution; sandboxed file reads |
| Gaming the rubric to pass triage | Tool checks form, not substance; ValiChord triage includes human review above complexity threshold |
| Spoofed pre-vetting certificates | Tool output has zero authority in ValiChord pipeline; no fast-track for pre-vetted submissions |
| Analytics data exfiltration | Opt-in only; anonymised before transmission; tool fully functional offline |
| Reverse-engineering scoring algorithm | Rubric is intentionally public; understanding what ValiChord expects is the point |

**Anonymous analytics (opt-in only):**

If researchers consent to anonymous usage reporting, ValiChord aggregates data on:

- Most common failure points across disciplines (e.g., "73% of psychology submissions lack pinned dependencies")
- Distribution of readiness scores by field
- Which recommendations are most acted on
- Improvement trajectories (do researchers who use the tool repeatedly produce cleaner repositories?)

This generates a dataset on computational research practices that nobody else has — covering the full ecosystem, not just the studies that reach formal validation.

**Strategic value:** The tool extends ValiChord's impact beyond the studies it formally validates. Every researcher who uses the tool produces more reproducible work, whether or not they submit to ValiChord. This positions ValiChord not just as verification infrastructure but as an active driver of better research practices across the entire ecosystem. It also functions as a natural adoption pipeline: researchers who use the free tool become familiar with ValiChord's standards and are more likely to submit studies for formal validation.

**Timeline:** This is the Stage B tool — Phase 2, once Phase 0's evidence has established which surface features predict difficulty and Phase 1's operational data has calibrated the scoring weights. The rubric must be empirically grounded before the tool can be built — otherwise it would be enforcing assumptions rather than evidence-based standards. A simpler Stage A version — *ValiChord at Home* (working name), a best-practice checklist that doesn't predict difficulty or estimate time — can be released alongside Phase 0 results as ValiChord's first public-facing product (see Phase 0 Deliverable 8). *ValiChord at Home* builds the community and generates ecosystem data. Stage B replaces it with empirically calibrated precision.

### Pre-Commitment Integration

```rust
impl ValidationEngine {
    /// When validating pre-registered protocol
    pub fn validate_with_precommitment(
        &self,
        protocol_ref: Hash,
        actual_execution: ExecutionReport,
    ) -> Result<ValidationTask, Error> {
        // Fetch pre-registered protocol from Layer 1
        let preregistered = self.fetch_preregistration(protocol_ref)?;
        
        // Compare planned vs actual
        let deviations = self.detect_deviations(
            &preregistered,
            &actual_execution,
        );
        
        // Assign validators with deviation context
        let validators = self.select_validators(
            &preregistered,
            deviations.epistemic_impact_level(),
        )?;
        
        // Validators receive:
        // 1. What should have happened (pre-registration)
        // 2. What actually happened (execution report)
        // 3. Declared deviations and justifications
        
        Ok(ValidationTask {
            protocol_ref,
            preregistered_plan: preregistered,
            actual_execution,
            declared_deviations: deviations,
            assigned_validators: validators,
            validation_focus: ValidationFocus::PreCommitmentAdherence,
        })
    }
}

pub enum ValidationFocus {
    /// Just check if code reproduces
    ComputationalReproducibility,
    
    /// Check adherence to pre-registered plan
    PreCommitmentAdherence,
    
    /// Check methodological soundness
    MethodologicalReview,
}
```

### Validator Assignment

**Phase 0 implementation (self-assignment — implemented and tested):** Validators discover open studies via `get_pending_requests_for_discipline` and call `claim_study(request_ref)` to self-assign. The coordinator enforces capacity (no more than `num_validators_required` claims per study) and duplicate prevention. The integrity zome's `validate()` enforces conflict-of-interest at the network layer: if the validator's institution matches the researcher's institution (stored in `ValidationRequest.researcher_institution`), the claim is rejected before it reaches the DHT. `release_claim` frees the slot while preserving the `StudyClaim` entry as an audit record.

**Phase 1 target (reputation-weighted central assignment):** Reputation-weighted constrained randomness with safeguards:
- Institutional caps (max 40% from one institution)
- Inverse size weighting (smaller institutions get proportionally more slots)
- **Double-blind by default.** Validators do not see author names, institutional affiliations, or funding sources. They receive the study protocol, code, data, and methodology — nothing that identifies who produced it. This prevents career deference: a junior validator who sees a Nobel laureate's name on a protocol may unconsciously look for reasons to confirm rather than critically assess. The commit-reveal protocol prevents validators from adjusting results after seeing others' findings, but only double-blinding prevents the subtler bias of knowing whose work you are assessing. Author identity is revealed only in the published Harmony Record, after all validators have submitted their final attestations.
- Blind commitment protocol prevents coordination between validators: findings are sealed as private source chain entries with a SHA-256 hash commitment published before any reveal
- Validators do not know who else is validating the same study

> **Engineering question:** How much domain expertise do validators actually need? ValiChord validates computation, not scientific methodology. A chemist who can set up a Python environment and run a script can check whether a climate model produces the claimed outputs just as well as a climate scientist — the numbers either match or they don't. This suggests the validator pool could be much larger than domain-matched selection implies. However, a domain expert might notice that code ran successfully but produced intermediate values that are physically impossible (e.g. negative absolute temperature, impossible protein structure) — something a non-expert would miss. A possible model: "find three computationally competent researchers, at least one with domain familiarity" rather than "find three domain specialists." This would significantly ease panel assembly and reduce queue times, but the trade-off between computational-only and domain-informed validation needs empirical evidence. This is a question for the PI and should be explored in Phase 0 study design.

### Validator Attestation with Deviation Flagging

```rust
/// THE COMMIT PHASE — stored as a private entry in the Validator Workspace DNA.
/// Invisible to all peers and the shared DHT. Its existence is verifiable
/// on the validator's source chain; its contents are not visible until reveal.
/// validator_id and validation_id are omitted — the Holochain Action carries
/// author key and ActionHash natively.
///
/// Implementation note (March 2026): `nonce`, `commitment_hash`, and `discipline`
/// have been added to the actual implementation (see validator_workspace_integrity).
/// `nonce` and `commitment_hash` are GENERATED by `seal_private_attestation` —
/// the caller supplies only the `ValidationAttestation` to be revealed.
/// `discipline` is stored here so the full `ValidationAttestation` can be
/// reconstructed at reveal time without a separate task lookup.
/// `SealAttestationInput` takes `ValidationAttestation`, not this struct directly.
pub struct ValidatorPrivateAttestation {
    pub request_ref:             ExternalHash,
    pub outcome:                 AttestationOutcome,
    pub outcome_summary:         OutcomeSummary,
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub confidence:              AttestationConfidence,
    pub deviation_flags:         Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
    pub discipline:              Discipline,     // mirrored from public form for reconstruction
    pub nonce:                   Vec<u8>,        // 32-byte random nonce, generated at seal time
    pub commitment_hash:         Vec<u8>,        // SHA-256(msgpack(ValidationAttestation) || nonce)
}

/// THE REVEAL PHASE — written to the shared Attestation DNA once all validators
/// have sealed private attestations and the reveal window opens.
/// IMMUTABLE after publication — enforced by validate() callback.
/// detailed_report is deliberately omitted: only the structured outcome summary
/// crosses the membrane boundary, not the full narrative.
pub struct ValidationAttestation {
    pub request_ref:             ExternalHash,
    pub outcome:                 AttestationOutcome,
    pub outcome_summary:         OutcomeSummary,  // structured for agreement detection
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub confidence:              AttestationConfidence,
    pub deviation_flags:         Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
    pub discipline:              Discipline,
    /// ActionHash of the CommitmentAnchor this validator published during the commit phase.
    /// Inductive chain: ValidationAttestation → CommitmentAnchor → ValidationRequest.
    /// Set by the attestation coordinator (not the caller); None only for pre-2026-03-25 entries.
    #[serde(default)]
    pub commitment_anchor_hash:  Option<ActionHash>,
}

pub struct UndeclaredDeviation {
    pub deviation_type: DeviationType,
    pub severity:       Severity,
    pub evidence:       String,
    // flagged_by omitted — the Holochain Action author field carries this natively
}
```

### Commit-Phase Entries: CommitmentAnchor and PhaseMarker

Two entry types were added to the Attestation DNA in scaffold v12 to resolve the commit-reveal phase detection problem.

```rust
/// Public, cryptographically binding proof that a specific validator has sealed
/// their private attestation for a specific study. Written to the shared DHT
/// at commit time — everyone can see the commitment happened, which study it is
/// for, and the hash that binds the reveal to the declared content. The actual
/// assessment remains in the private ValidatorPrivateAttestation in DNA 2.
///
/// `commitment_hash = SHA-256(msgpack(ValidationAttestation) || nonce)`
/// computed in DNA 2 before any content leaves the validator's device.
/// At reveal time, verifying this hash against the submitted attestation + nonce
/// proves the validator did not adjust their assessment after committing.
///
/// IMMUTABLE after publication — enforced by validate() callback.
#[entry_type(required_validations = 5)]
pub struct CommitmentAnchor {
    pub request_ref:             ExternalHash,  // which study this commitment is for
    pub validator:               AgentPubKey,   // which validator committed
    pub commitment_hash:         Vec<u8>,       // SHA-256(msgpack(ValidationAttestation) || nonce)
    /// ActionHash of the ValidationRequest this commitment is for.
    /// Inductive chain: CommitmentAnchor → ValidationRequest.
    /// Resolved by notify_commitment_sealed via the study.{request_ref} path.
    pub validation_request_hash: ActionHash,
}

/// DHT-persistent record of the current phase for a validation round.
/// Written by the coordinator when all expected CommitmentAnchors are present.
/// When phase flips to RevealOpen, notify_commitment_sealed emits Signal::RevealOpen
/// locally (emit_signal) and pushes it to all other committed validators via
/// send_remote_signal (fire-and-forget). Agents who miss the signal discover
/// the open window by polling get_current_phase(), which queries the link.
///
/// IMMUTABLE after publication — enforced by validate() callback.
pub struct PhaseMarker {
    pub request_ref: ExternalHash,
    pub phase:       ValidationPhase,
}

pub enum ValidationPhase {
    CommitOpen,   // accepting commitments (default — no PhaseMarker entry needed)
    RevealOpen,   // all validators committed; reveal window open
    Closed,       // HarmonyRecord created; round complete
}
```

Both `CommitmentAnchor` and `PhaseMarker` are immutable after creation — the validate() callback blocks all updates and deletes, enforcing the same immutability guarantee as `ValidationAttestation`. `ResearcherResultCommitment` (records the researcher's pre-declared hash before validators begin), `ResearcherReveal` (the verified structured metrics published at reveal time, March 2026), and `LockedResult` (private DNA 1 entry holding metrics + nonce) are also immutable. `ResearcherReveal` is the public-facing complement to `ResearcherResultCommitment`: once the hash is verified on-chain, the structured per-metric results land on the shared DHT where validators' `produced_value` fields can be compared against the researcher's `metrics[i].produced_value`.

### Gaming & Collusion Detection Mechanisms

**Blind commitment via private source chain entries and SHA-256 hash commitments (commit-reveal) — now fully symmetric:** The protocol covers both validators and the researcher. **Validator side:** Each validator records their findings as a *private entry* (`ValidatorPrivateAttestation`) on their own Holochain source chain — visible only to them, cryptographically sealed by their signing key, and immutable from the moment of recording. `seal_private_attestation` generates a 32-byte random nonce and computes `commitment_hash = SHA-256(msgpack(ValidationAttestation) || nonce)`. This hash is forwarded to the shared Attestation DNA via `notify_commitment_sealed`, where it is stored in a `CommitmentAnchor` entry visible to all participants. Once all validators have sealed private entries (detected by polling `check_all_commitments_sealed`), a `PhaseMarker(RevealOpen)` entry is written to the DHT. Validators discover the open reveal window by polling `check_all_commitments_sealed` — `get_current_phase()` provides a UI hint but is not a protocol gate (see implementation notes). Validators then call `submit_attestation(AttestationRevealInput { attestation, nonce })`, which recomputes the SHA-256 hash on-chain and rejects the reveal if it does not match the `CommitmentAnchor` — making post-commit manipulation impossible at the network layer. **Researcher side:** At study submission, the researcher calls `lock_researcher_result` in DNA 1: this generates a nonce, computes `SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores a private `LockedResult { request_ref, metrics, nonce, commitment_hash }` (never leaves their device), and calls `publish_researcher_commitment` in DNA 3, recording only the hash as `ResearcherResultCommitment`. At reveal time the researcher retrieves the private `LockedResult` via `get_locked_result` and calls `reveal_researcher_result` in DNA 3, which verifies `SHA-256(rmp_serde::to_vec_named(metrics) || nonce) == result_commitment_hash` on-chain and writes an immutable `ResearcherReveal { request_ref, metrics }` to the DHT. **Result:** both parties' ground truth (researcher's declared expected values, validator's independently reproduced values) are on the public DHT in the same reveal phase, enabling a cryptographically verifiable comparison without either party being able to adjust after seeing the other's findings. Serialisation uses `rmp_serde::to_vec_named` on both sides for consistent msgpack encoding.

> **Countersigning deferred to Phase 2.** The original design called for Holochain's native countersigning — a mathematically enforced simultaneous atomic reveal where all validators must be online together. This is operationally inappropriate for Phase 0/1 (validators work asynchronously across time zones). The SHA-256 hash-commitment approach provides equivalent anti-manipulation guarantees — a validator cannot change a committed assessment — without requiring synchronous participation. Countersigning remains on the Phase 2 roadmap as a stronger variant for high-stakes validation panels.

> **In plain terms:** Each validator privately records their findings in a sealed, tamper-proof log and posts a cryptographic hash of those findings to the shared network. Only once every validator has posted their hash does the reveal window open — at which point validators publish their actual findings. Anyone can verify that each validator's published finding matches their pre-committed hash. No validator can adjust their position after seeing others' results, because their hash was already posted before the reveal window opened.

**Result comparison and agreement detection:** Validators submit structured outcome summaries from their private Workspace DNA to the shared Attestation DNA. Agreement detection operates on these summaries — not by comparing raw result hashes. This is architecturally necessary: computational reproduction almost never produces bit-identical outputs due to floating point differences, non-deterministic operations, and hardware variation. Requiring exact hash matches would flag every validation as a disagreement. Instead, the Attestation DNA compares structured outcome summaries (key metrics, direction of effect, confidence intervals) and assesses whether results are within acceptable margins. What constitutes agreement is defined by discipline-specific standards in the Governance DNA.

**Detection patterns:**
- Collusion pattern detection (cross-institutional agreement >90% over 20+ validations)
- Access pattern clustering (validators accessing data at suspiciously similar times)
- Statistical outlier detection (MAD — Median Absolute Deviation)
- Time analysis (unrealistically fast or slow validations)
- Social distance mapping (co-authorship graph analysis)

**Warrants — Holochain's native enforcement mechanism:** When a participant publishes data that violates the DNA's validation rules, any peer that detects the violation creates and signs a **warrant** — a cryptographic proof of the bad action — and publishes it to the network. Warrants propagate automatically to the agent activity authorities responsible for tracking that participant's history. Once received, a warrant is permanent and discoverable by any node via `get_agent_activity`. Any node can check a validator's warrant status before interacting with them — for example, before accepting a commitment in the commit-reveal protocol. Automatic network-level blocking of warranted agents is on Holochain's roadmap; the current behaviour is that warrants are created, persisted, and queryable, with network block enforcement following. For ValiChord, this means a validator who submits fraudulent attestations can be warranted by peers and their status checked by any participant, without a governance committee needing to investigate and act first. Warrants were stabilised as a core feature in Holochain 0.7 (previously behind an experimental flag) — this enforcement mechanism is production-ready, not experimental.

> **Phase 2 addition — `Warrant` entry in Governance DNA:** Holochain's native warrant mechanism records that a violation occurred. For ValiChord's governance commitments, a structured `Warrant` entry in DNA 4 will eventually be needed to attach a narrative justification — which validator raised it, what the evidence was, and what the governance panel decided. This makes warrant decisions permanently and publicly queryable with full context, not just a flag against an agent's activity chain. The native warrant mechanism is sufficient for Phase 1; the structured entry is a Phase 2 governance addition.

> **Engineering question:** The specific thresholds for gaming detection (e.g., >90% agreement triggering investigation) need empirical calibration. Phase 0 data on natural agreement rates would inform these. Setting thresholds too low creates false positives; too high misses real collusion.

---

## LAYER 3: Governance & Policy

**Purpose:** Transparent, auditable rule-setting that resists institutional capture.

**Precedent for governance-enforced principles:** The holo-health project demonstrates that marketplace principles can be enforced at the membrane level — the conditions for joining the shared DHT can include commitment to specific principles, making them structurally binding rather than merely stated policy. ValiChord's Governance DNA applies the same pattern: disciplinary standards, anti-capture commitments, and epistemic integrity rules are enforced by the membrane function governing participation in the Attestation and Governance DNAs, not merely written into governance documents that can be quietly ignored.

The governance layer is specified in detail in the companion *Governance Framework* document. The technical implementation involves:

```rust
pub struct PreCommitmentGovernance {
    /// Standards for what requires pre-registration
    pub pre_registration_requirements: RequirementMatrix,
    
    /// Deviation approval authority
    pub deviation_review_board: ReviewBoard,
    
    /// Epistemic impact assessment guidelines
    pub impact_guidelines: ImpactGuidelines,
    
    /// Disciplinary standards
    pub discipline_standards: HashMap<Discipline, Standards>,
}

pub enum PreRegRequirement {
    Mandatory,
    Recommended,
    Optional,
    NotApplicable,
}
```

### Deviation Review Process

```
Researcher declares deviation with justification
         ↓
Automated impact assessment
         ↓
If Substantial impact → Review Board
         ↓
Board decision:
  - Approve with note
  - Require additional validation
  - Require re-registration
         ↓
Decision logged to tamper-evident record (Layer 4)
```

### Disciplinary Standards

Each discipline defines its own pre-registration standards. Example:

```yaml
discipline: computational_biology
pre_commitment_standards:
  hypotheses:
    - must_specify_model_architecture: true
    - must_specify_hyperparameters: true
    - must_specify_training_stopping_criteria: true
  
  acceptable_deviations:
    - model_convergence_issues: moderate_impact
    - hardware_constraints: minimal_impact
    - dataset_quality_issues: substantial_impact
  
  outcome_measures:
    - prediction_accuracy: required
    - confidence_intervals: required
    - cross_validation_method: required
```

> **Engineering question:** Who writes these disciplinary standards initially? They require genuine domain expertise. The current plan assumes Disciplinary Standards Committees (7–10 members per field), but recruiting these before the system has credibility is a chicken-and-egg problem. Phase 1 might need to start with 2–3 disciplines where advisory relationships already exist.

---

## LAYER 4: Audit & Provenance

**Purpose:** Tamper-evident record of every significant action — the system's memory.

### Audit Event Types

```rust
/// Every action creates a tamper-evident, append-only log entry
pub enum AuditEvent {
    /// Layer 1 events
    ProtocolRegistered {
        protocol_id: Hash,
        registered_by: AgentId,
        registered_at: DateTime,
        protocol_hash: Hash,
    },
    ProtocolModificationRequested {
        protocol_id: Hash,
        modification: Modification,
        justification: String,
        impact: EpistemicImpact,
    },
    DeviationDeclared {
        protocol_id: Hash,
        deviation: DeviationType,
        declared_at: DateTime,
        declared_by: AgentId,
    },
    
    /// Layer 2 events
    ValidationRequested {
        protocol_id: Hash,
        requester: AgentId,
    },
    ValidatorAssigned {
        validation_id: Hash,
        validator_id: ValidatorId,
        assigned_at: DateTime,
    },
    AttestationSubmitted {
        validation_id: Hash,
        validator_id: ValidatorId,
        outcome: AttestationOutcome,
        submitted_at: DateTime,
    },
    
    /// Layer 5 events
    HarmonyRecordGenerated {
        protocol_id: Hash,
        harmony_record_hash: Hash,
        generated_at: DateTime,
    },
    
    /// Layer 6 events
    ReputationUpdated {
        validator_id: ValidatorId,
        old_score: f64,
        new_score: f64,
        reason: String,
    },
    
    /// Layer 3 events
    GovernanceDecision {
        decision_type: DecisionType,
        made_by: GovernanceBody,
        rationale: String,
        made_at: DateTime,
    },
}
```

### Provenance Graph

```rust
/// Complete lineage from hypothesis → validation
pub struct ProvenanceGraph {
    /// Root: Pre-registered protocol
    pub root: Hash,
    
    /// Nodes: All related entities
    pub nodes: Vec<ProvenanceNode>,
    
    /// Edges: Relationships
    pub edges: Vec<ProvenanceEdge>,
}

pub enum ProvenanceNode {
    PreRegistration(Hash),
    Modification(Hash),
    Deviation(Hash),
    DataSnapshot(Hash),
    ValidationRequest(Hash),
    Attestation(Hash),
    HarmonyRecord(Hash),
    Publication(Hash),
}

pub enum ProvenanceEdge {
    ModifiedFrom,
    DeviatedFrom,
    ValidatedUsing,
    GeneratedFrom,
    PublishedAs,
    CitedBy,
}
```

### Provenance Queries

```rust
impl ProvenanceGraph {
    /// "Show me everything that happened to this protocol"
    pub fn full_history(&self, protocol_id: Hash) -> FullHistory;
    
    /// "Did this protocol have substantial deviations?"
    pub fn check_deviations(&self, protocol_id: Hash) -> DeviationReport;
    
    /// "What validators worked on this?"
    pub fn validator_history(&self, protocol_id: Hash) -> Vec<ValidatorId>;
    
    /// "Has anyone cited this validation?"
    pub fn citation_network(&self, protocol_id: Hash) -> CitationGraph;
}
```

### Holochain Implementation

In the multi-DNA architecture, audit events are distributed across DNAs according to where they originate: registration events live on the Researcher Repository and Attestation DNAs; validation events on the Validator Workspace and Attestation DNAs; governance decisions on the Governance DNA. Every action is recorded within its respective DNA on Holochain. The provenance graph is built from queries across DNAs via bridges. Tamper-evidence is guaranteed by Holochain's architecture — every participant's record is append-only and any modification is detectable by peers. No central audit database exists or is required.

Crucially, Holochain's header structure creates a provenance path that does not require data disclosure. A researcher or validator can present the chain of headers — each containing a timestamp, sequence number, author signature, and hash of the entry it covers — to demonstrate when data was first committed and that it has remained unchanged, without ever sharing the data below those headers. External parties (journals, funders, regulators) can verify the chain's integrity from the headers alone. Note that Holochain Actions already contain author key, signature, and timestamp natively — these fields do not need to be duplicated inside entry structs.

**Precedent for audit trail value:** The holo-health project identifies an identical problem in healthcare: physicians are reluctant to trust health records held in patient custody because they cannot verify the records are complete and unaltered. The holo-health solution — an immutable, non-forgeable, non-repudiable audit trail in the shared DHT — gives practitioners confidence that records are unchanged. ValiChord's Attestation DNA provides the same guarantee to journals and funders: a validation attestation recorded on the DHT cannot have been altered after submission, which is exactly the assurance needed to make Harmony Records trustworthy to external parties.

### Public vs Private Views

```rust
pub struct AuditRecord {
    /// Public (always visible)
    pub public_summary: PublicSummary,
    
    /// Internal (Research Integrity Office only)
    pub internal_details: Option<InternalDetails>,
    
    /// Validator-visible (can see own details)
    pub validator_view: Option<ValidatorDetails>,
}
```

---

## LAYER 5: Output & Certification

**Purpose:** Transform internal processes into externally usable trust signals. This is what journals, funders, and institutions consume.

### Harmony Record

The canonical output of ValiChord. Preserves the full texture of agreement and disagreement rather than producing a single verdict.

```rust
/// Note: record_id and issued_at are deliberately omitted — the Holochain
/// ActionHash IS the record identifier, and the Action carries the timestamp
/// natively. valid_until is stored as seconds (u64) to avoid DateTime
/// serialisation complexity in WASM.
pub struct HarmonyRecord {
    /// Links back to the ValidationRequest in the Attestation DNA.
    pub request_ref: ExternalHash,
    
    /// Validation summary
    pub validation_summary: ValidationSummary,
    
    /// Validator details (respecting attribution rules)
    pub validators: Vec<ValidatorSummary>,
    
    /// Disagreement visibility (forced, per Governance commitments)
    pub disagreements: Vec<Disagreement>,
    
    /// Epistemic confidence
    pub confidence_level: ConfidenceLevel,
    
    /// Reproducibility status
    pub status: ReproducibilityStatus,
    
    /// 24-month minimum validity per governance policy (Unix timestamp seconds).
    pub valid_until_secs: u64,
    
    /// Link to full provenance chain in Attestation DNA.
    pub provenance_link: String,
}

pub struct ValidationSummary {
    pub total_validators: u8,
    pub successful_validations: u8,
    pub partial_validations: u8,
    pub failed_validations: u8,
    pub inconclusive_validations: u8,
    
    pub agreement_level: f64,
    pub outlier_count: u8,
    pub variance_explained: Option<VarianceReport>,
}

pub enum ConfidenceLevel {
    High {
        agreement: f64,
        reasoning: String,
    },
    Medium {
        concerns: Vec<String>,
        reasoning: String,
    },
    Low {
        substantial_disagreement: bool,
        reasoning: String,
    },
}

pub enum ReproducibilityStatus {
    ExactMatch { validator_count: u8 },
    DirectionalMatch { 
        validator_count: u8,
        variance_explanation: String,
    },
    PartialMatch {
        successful_aspects: Vec<String>,
        failed_aspects: Vec<String>,
    },
    Failed {
        failure_reasons: Vec<String>,
        validator_count: u8,
    },
    Inconclusive {
        reasons: Vec<String>,
    },
    /// The system refuses to force a verdict where evidence doesn't support one
    PersistentlyIndeterminate {
        time_elapsed_secs: u64,  // u64 seconds — avoids WASM Duration serialisation
        validator_count: u8,
        disagreement_summary: String,
    },
}
```

### Reproducibility Badges

Domain-specific, not gamified. Cannot be reduced to a single numerical score.

```rust
pub enum ReproducibilityBadge {
    ComputationalReproducible {
        level: BadgeLevel,
        discipline: Discipline,
    },
    PreRegisteredAndValidated {
        adherence_score: f64,
    },
    OpenDataValidated {
        data_availability: DataAvailability,
    },
    MultiLabValidated {
        lab_count: u8,
        geographic_diversity: f64,
    },
}

pub enum BadgeLevel {
    Bronze,  // Basic validation passed (≥3 validators, ≥60% success)
    Silver,  // Enhanced + good practices (≥5 validators, ≥70%, pre-registered)
    Gold,    // Comprehensive + exemplary (≥7 validators, ≥80%, multi-institutional)
}
```

### Narrative Reports

Human-readable summaries tailored for different audiences.

```rust
pub struct NarrativeReport {
    pub executive_summary: String,
    pub protocol_description: String,
    pub validation_process: String,
    pub findings: String,
    pub limitations: Vec<String>,  // Always included
    pub recommendations: Vec<String>,
    pub generated_at: DateTime,
}

impl NarrativeReport {
    /// Auto-generate from Harmony Record
    pub fn from_harmony_record(record: &HarmonyRecord) -> Self {
        // Template-based generation with discipline-specific language
        // Explicitly flags disagreements (per Governance commitments)
        // Avoids overconfident language
        // Includes appropriate caveats
    }
}
```

### External API

```rust
pub trait ValiChordAPI {
    async fn get_validation_status(
        &self, protocol_id: Hash,
    ) -> Result<HarmonyRecord, Error>;
    
    async fn check_funder_requirements(
        &self, protocol_id: Hash, funder_id: String,
    ) -> Result<ComplianceReport, Error>;
    
    async fn get_researcher_portfolio(
        &self, researcher_id: String,
    ) -> Result<ResearcherPortfolio, Error>;
    
    async fn get_institutional_metrics(
        &self, institution_id: String,
    ) -> Result<InstitutionalMetrics, Error>;
    
    async fn query_by_external_id(
        &self, external_id: String,
    ) -> Result<Vec<HarmonyRecord>, Error>;
}
```

---

## LAYER 6: Incentive & Reputation

**Purpose:** Align behaviour with system goals — make doing the right thing the easiest thing.

### Reputation System

Multi-dimensional scoring. No single number that can be gamed.

> **Identity caveat:** Reputation is currently keyed by `AgentPubKey`, which is a Holochain device key — one per conductor instance. A validator who joins from a second device, or who replaces a lost device, receives a new `AgentPubKey` and their prior reputation is stranded on the old key. For Phase 0 (institutional validators on single institutional machines) this is acceptable. For Phase 1, where reputation becomes an operational signal for validator assignment and compensation, continuity must be preserved. The ecosystem solution is the Flowsta `agent_linking` zome, which creates mutual-consent pairwise identity records allowing any key lookup to resolve all keys belonging to one person. This should be designed into Phase 1 alongside the Holochain 1.0 Deepkey key-rotation infrastructure — see the engineer handover for details.

```rust
pub struct UnifiedReputation {
    /// Validation track record
    pub validation_score: ReputationScore,
    
    /// Pre-registration quality
    pub preregistration_score: ReputationScore,
    
    /// Deviation handling quality
    pub deviation_score: ReputationScore,
    
    /// Time invested (quality signal)
    pub time_investment: TimeMetrics,
    
    /// Peer ratings
    pub peer_endorsements: u32,
    
    /// Disciplinary expertise
    pub expertise_areas: HashMap<Discipline, ExpertiseLevel>,
    
    /// Institutional affiliation
    pub institution: InstitutionId,
    
    /// Overall reputation (weighted)
    pub total_score: f64,
}
```

### Incentive Structure

```rust
pub enum ValidatorIncentive {
    /// CRediT taxonomy recognition
    CoAuthorshipCredit {
        credit_type: CreditType,
        weight: f64,
    },
    
    /// Career advancement
    CVRecognition {
        validation_count: u32,
        quality_score: f64,
    },
    
    /// Direct compensation (amount in minor currency units, e.g. pence)
    DirectPayment {
        amount_minor_units: u64,
        currency: String,
    },
    
    /// Reputation building
    ReputationGain {
        reputation_increase: f64,
        visibility_boost: f64,
    },
}

pub enum CreditType {
    ValidationExecution,
    MethodologyReview,
    FormalAnalysis,
    Software,
    WritingOriginalDraft,
}
```

### Tiered Credit

```rust
pub enum ValidationCreditTier {
    /// Quick check (1-2 hours): £50-100
    Tier1 { credit: f64, compensation_pence: u64 },
    
    /// Standard validation (4-8 hours): £200-400
    Tier2 { credit: f64, compensation_pence: u64 },
    
    /// Comprehensive review (16+ hours): £800-1600
    Tier3 { credit: f64, compensation_pence: u64 },
}
```

> **Engineering question:** These compensation tiers are illustrative. Phase 0 exists specifically to generate empirical data on what validation actually costs in time, which then determines what fair compensation looks like. The tiers above are placeholders pending Phase 0 evidence. Note: compensation is stored as integer pence rather than floating-point pounds — a standard practice to avoid rounding errors in financial calculations.

### Time Tracking & Audit Sampling

```rust
pub struct TimeTracking {
    pub reported_hours: f64,
    pub system_tracked_time_secs: u64,  // u64 seconds throughout
    pub expected_time_range: (f64, f64),
    pub audit_flags: Vec<AuditFlag>,
}

pub enum AuditFlag {
    TooFast { expected_min: f64, actual: f64 },
    TooSlow { expected_max: f64, actual: f64 },
    InactivityPeriods { gaps: Vec<u64> },  // gap durations in seconds
}

/// 10% random audit sampling (stratified)
impl AuditSystem {
    pub fn sample_for_audit(&self) -> Vec<ValidationId> {
        // 40% from new validators (< 10 validations)
        // 60% random from all validators
        // Flags take priority
    }
}
```

### Anti-Gaming Measures

```rust
pub struct IncentiveConstraints {
    /// No "validation count" races
    no_quantity_incentives: bool,
    
    /// Quality over speed — no bonuses for finishing fast
    quality_multiplier: f64,
    
    /// Diversity bonuses (not volume)
    diversity_bonus: DiversityBonus,
    
    /// Penalise homophily (>90% agreement with single institution)
    homophily_penalty: f64,
}

/// Diversity is an architectural requirement, not a policy preference. Credible validation
/// requires genuinely independent validators — different institutions, different geographies,
/// no co-authorship networks. This creates structural demand for distributed capability:
/// ValiChord needs qualified validators across regions to produce epistemically valid results.
/// Participation provides under-resourced labs with funded opportunities to build credibility
/// and methodological skills. Both sides need each other — this is mutual, not charitable.
pub struct DiversityBonus {
    /// Bonus for validating across disciplines
    cross_discipline: f64,
    
    /// Bonus for validating novel methods
    novel_methods: f64,
    
    /// Bonus for finding legitimate disagreement
    disagreement_discovery: f64,
    
    /// Bonus for geographic and institutional diversity in validator panels
    geographic_institutional: f64,
}
```

---

## LAYER 7: Integration & Interface

**Purpose:** How external systems plug into ValiChord. Journals, funders, and institutions query ValiChord; ValiChord is infrastructure, not a silo.

**Design rationale:** Most journals, funders, and universities already have existing editorial, grant management, and research information systems. Requiring them to adopt native Holochain applications as a condition of participation would be a significant barrier to entry. An API-first approach is therefore correct: institutions participate via standard REST APIs and webhooks, with Holochain handling the integrity guarantees behind the interface. This reasoning is directly validated by the holo-health project (Melville), which reached the same conclusion for healthcare providers: *"To require them to adopt a pure holochain-native application architecture for their internal systems would pose a significant barrier to entry... an API-based approach will be followed initially."* The parallel is exact.

**The HTTP Gateway — this is built:** Holochain released an HTTP Gateway in March 2025 (version 0.2 in July 2025) that provides exactly this bridge — standard HTTP requests routed to a running Holochain application. External systems can query ValiChord's Governance and Harmony Records DNA via ordinary HTTP without running a Holochain node. This means the core integration challenge for Layer 7 is largely solved infrastructure rather than custom development work. The REST API endpoints below represent the interface surface; the HTTP Gateway handles the translation to Holochain behind it.

### Integration Traits

```rust
pub trait JournalIntegration {
    async fn check_validation_status(
        &self, manuscript_id: String,
    ) -> Result<ValidationStatus, Error>;
    
    async fn require_validation(
        &self, article_type: ArticleType, minimum_tier: ValidationTier,
    ) -> Result<ValidationRequirement, Error>;
    
    async fn get_reproducibility_badge(
        &self, doi: String,
    ) -> Result<BadgeDisplay, Error>;
}

pub trait FunderIntegration {
    async fn check_grant_compliance(
        &self, grant_id: String,
    ) -> Result<ComplianceReport, Error>;
    
    async fn portfolio_risk_dashboard(
        &self, funder_id: String,
    ) -> Result<PortfolioDashboard, Error>;
}

pub trait RepositoryIntegration {
    async fn link_osf_project(
        &self, osf_id: String, protocol_id: Hash,
    ) -> Result<(), Error>;
    
    async fn link_github_commits(
        &self, repo: String, commits: Vec<String>, protocol_id: Hash,
    ) -> Result<(), Error>;
    
    async fn get_repo_validation_badge(
        &self, repo: String,
    ) -> Result<BadgeMarkup, Error>;
}
```

### REST API Endpoints

```text
// Core endpoints
POST   /api/v1/protocols                    // Submit new protocol
GET    /api/v1/protocols/{id}               // Get protocol details
PUT    /api/v1/protocols/{id}/deviations    // Declare deviation

POST   /api/v1/validations                  // Request validation
GET    /api/v1/validations/{id}             // Get validation status
GET    /api/v1/validations/{id}/harmony     // Get Harmony Record

GET    /api/v1/researchers/{orcid}          // Researcher portfolio
GET    /api/v1/institutions/{id}/metrics    // Institutional metrics
GET    /api/v1/funders/{id}/portfolio       // Funder portfolio

// Query by external identifier
GET    /api/v1/query/doi/{doi}
GET    /api/v1/query/osf/{osf_id}
GET    /api/v1/query/github/{repo}

// Webhook support
POST   /api/v1/webhooks/register
POST   /webhooks/{subscriber}
```

### Integration Flows

**Journal submission:**
```
Author submits manuscript
→ Journal system queries ValiChord: GET /api/v1/validation/{doi}
→ If validated: Display badge, proceed
→ If not validated: Prompt author, offer validation
→ Editor sees validation status in review interface
→ Reviewers see Harmony Record, can query details
```

**Funder review:**
```
PI submits grant application
→ Funder system queries: GET /api/v1/portfolio/{pi_orcid}
→ Displays PI's validation track record
→ Reviewer sees reproducibility history
→ Funding decision informed by validation quality
```

### Implemented Integration API (as of 2026-03-28)

The following endpoints are live in `backend/app.py` (Flask). They form the actual integration surface available to external systems today — distinct from the aspirational `/api/v1/` plan above, which remains a future design intent.

**New single-shot endpoints (2026-03-28):**

```
POST /validate
  multipart/form-data, field: file (ZIP, max 100 MB)
  → 202 { "job_id": "uuid" }

GET /result/<job_id>
  → { "status": "running" }
  → { "status": "error", "error": "..." }
  → { "status": "done",
      "findings": [...],
      "harmony_record_draft": { ... },
      "download_url": "/download/<job_id>" }
```

**Existing endpoints (unchanged, backwards-compatible):**

```
POST /upload-chunk          chunked upload (1 MB chunks), returns job_id
GET  /status/<job_id>       returns harmony_record_draft in done response
GET  /download/<job_id>     returns ZIP file with full report
GET  /health                { "status": "ok", "version": "1.0",
                              "conductor": "live"|"offline" }
```

**`harmony_record_draft` schema:**

```json
{
  "outcome": { "type": "PartiallyReproduced", "content": { "details": "..." } },
  "data_hash": "<sha256 hex of deposit>",
  "findings_summary": {
    "critical": 0, "significant": 2, "low_confidence": 3, "total": 5
  },
  "harmony_record_hash": "<uhCkk... ActionHash string, or null>",
  "harmony_record_url":  "<gateway URL, or null>"
}
```

`harmony_record_hash` is null when `demo/serve.mjs` (and the Holochain conductor) is not running — graceful degradation. `harmony_record_url` is null until `HOLOCHAIN_GATEWAY_URL`, `HOLOCHAIN_GOVERNANCE_DNA_HASH`, and `HOLOCHAIN_APP_ID` env vars are set on the Flask server. **Both fields are fully populated in the Codespace demo as of 2026-03-28.**

**Outcome mapping (Python findings → Holochain AttestationOutcome) — heuristic proxy only:**

> **Important:** This mapping is a heuristic approximation, not an actual validation run. The Python analysis checks deposit quality (missing files, broken paths, undocumented data, etc.) — it does not attempt to reproduce the research. `FailedToReproduce` here means "the deposit has critical quality problems that would prevent reproduction", not "a validator tried and failed". Consumers of this endpoint must not treat the resulting `AttestationOutcome` as equivalent to a human validator's `ValidationAttestation`.

| Python analysis result | AttestationOutcome |
|---|---|
| Any CRITICAL finding | `FailedToReproduce` |
| SIGNIFICANT only | `PartiallyReproduced` |
| No findings | `Reproduced` |

**Internal Holochain bridge endpoints on `demo/serve.mjs` (localhost only):**

These are not public — the Python backend calls them via `http://localhost:8888`. External callers are rejected with HTTP 403.

```
POST /holochain/call
  { "role_name": "...", "zome_name": "...", "fn_name": "...", "payload": {...} }
  → { "result": <serialized zome return value> }

POST /holochain/validate-round
  { "data_hash_hex": "<64-char hex>", "outcome": {...},
    "discipline": {...}, "confidence": "Medium" }
  → { "harmony_record_hash": "<uhCkk... string or null>",
      "gateway_payload": "<base64url-encoded JSON of ExternalHash>" }
```

The `__bytes` convention: Uint8Array values crossing the Node/Python boundary are serialized as `{ "__bytes": "<base64>" }` in JSON. The bridge uses `encodeHashToBase64` to convert ActionHash results to canonical `uhCkk...` strings before returning them to Python.

**Environment variables:**

| Variable | Default | Effect |
|---|---|---|
| `HOLOCHAIN_GATEWAY_URL` | (empty) | Gateway base URL — required for `harmony_record_url` |
| `HOLOCHAIN_GOVERNANCE_DNA_HASH` | (empty) | Governance DNA hash (printed by `demo/start-gateway.sh`) |
| `HOLOCHAIN_APP_ID` | `valichord-demo` | Installed app ID on the conductor |
| `PORT` | 5000 (Flask) / 8888 (serve.mjs) | HTTP port override |

`harmony_record_url` format (when all three gateway vars are set):
`{HOLOCHAIN_GATEWAY_URL}/{HOLOCHAIN_GOVERNANCE_DNA_HASH}/{HOLOCHAIN_APP_ID}/governance_coordinator/get_harmony_record?payload={gateway_payload}`

**Status (2026-03-28):** `harmony_record_url` is now fully populated end-to-end in the Codespace demo. The HTTP Gateway (`hc-http-gw` v0.3.1) runs on port 8090 alongside the conductor. `demo/start-gateway.sh` starts it and prints the governance DNA hash. Always-on permanent deployment (outside the Codespace) remains Phase 1.

**New file: `backend/holochain_bridge.py`** — Python wrapper for `POST /holochain/validate-round`. Uses `requests` with a 120 s timeout (WASM JIT + DHT operations). All functions return `None` on connection error, so the analysis pipeline always completes without a live conductor.

---

## LAYER 8: Access & Presentation

**Purpose:** Make the system legible to different audiences with appropriate views.

### Researcher Dashboard

```rust
pub struct ResearcherDashboard {
    active_protocols: Vec<ProtocolCard>,
    validation_queue: Vec<ValidationStatus>,
    completed_validations: Vec<HarmonyRecordSummary>,
    researcher_reputation: ReputationDisplay,
    portfolio_summary: PortfolioSummary,
    notifications: Vec<Notification>,
}

pub enum ProtocolStatus {
    PreRegistration { locked: bool },
    DataCollection { completion: f64 },
    ValidationRequested { queue_position: u32 },
    ValidationInProgress { 
        validators_assigned: u8,
        attestations_received: u8,
    },
    Validated { harmony_record: Hash },
    DeviationReview { pending_count: u8 },
}
```

### Validator Console

```rust
pub struct ValidatorConsole {
    assigned_validations: Vec<ValidationTask>,
    validation_tools: ValidationToolkit,
    upcoming_deadlines: Vec<Deadline>,
    researcher_communication: Vec<Message>,
    validator_reputation: ReputationDisplay,
    completed_validations: Vec<CompletedValidation>,
}

pub struct ValidationTask {
    pub task_id: Hash,
    pub protocol_summary: ProtocolSummary,
    pub pre_commitment: Option<PreRegisteredProtocol>,
    pub data_access_instructions: DataAccessInstructions,
    pub validation_tier: ValidationTier,
    pub deadline: DateTime,
    pub estimated_time_secs: u64,  // u64 seconds
    pub compensation: Compensation,
}

pub struct ValidationToolkit {
    pub data_fetcher: DataFetchTool,
    pub execution_environment: ExecutionEnv,
    pub attestation_form: AttestationForm,
    pub issue_reporter: IssueReporter,
    pub researcher_contact: ContactTool,
}
```

### Funder Dashboard

```rust
pub struct FunderDashboard {
    portfolio_summary: PortfolioSummary,
    risk_dashboard: RiskDashboard,
    compliance_status: ComplianceTracker,
    reproducibility_trends: TrendAnalysis,
    institutional_performance: HashMap<InstitutionId, Performance>,
}

pub struct PortfolioSummary {
    pub total_grants: u32,
    pub validated_outputs: u32,
    pub validation_in_progress: u32,
    pub pending_validation: u32,
    pub validation_rate: f64,
    pub average_confidence: f64,
}
```

> **Engineering question:** The UX design for these dashboards is entirely unspecified. The structs above describe what data each audience needs, but the actual interface design — information hierarchy, interaction patterns, accessibility — is a significant piece of work requiring UX expertise. This is a Phase 1–2 concern.

---

## Holochain Architecture Notes

### Why Holochain, Not Blockchain

Holochain is agent-centric rather than data-centric. Each participant maintains their own source chain of actions; only cryptographic proofs are shared to a Distributed Hash Table (DHT). This solves the three problems that killed blockchain-based reproducibility systems:

**GDPR compliance:** Sensitive data stays local and never enters the shared DHT — data minimisation is architecturally enforced, not just policy. Where erasure rights do apply, they can be exercised against the private DNA without touching the shared attestation record.

**Cost:** No mining, no proof-of-work, no transaction fees. Universities run lightweight nodes. Estimated implementation cost: £50–100K vs. £500K–2M for blockchain equivalents.

**Performance:** No global consensus requirement. Validation happens locally; proofs are shared globally. Scales with participants rather than bottlenecking on consensus.

### Holochain DNA Structure and Update Strategy

ValiChord is implemented as four Holochain DNAs (see Multi-DNA Architecture section above). Within each DNA, Holochain distinguishes two kinds of code modules with critically different update properties:

**Integrity zomes** define data types and validation rules. Any change to an integrity zome changes the DNA's identity — creating a new, separate network. Every participant must migrate to the new DNA to continue participating. These should be kept small and stable, changed as rarely as possible.

**Coordinator zomes** implement application logic and the DNA's public API. They can be swapped out on a running network without forcing migration. Participants do not need to re-join.

For ValiChord, this distinction shapes the phase strategy directly. The core data structures and membrane rules belong in integrity zomes — they define the ground rules and should not change frequently. But governance standards, disciplinary thresholds, anti-domestication rules, and the application logic for agreement detection belong in coordinator zomes where possible, so that governance decisions in Phase 2 and beyond can update the system's behaviour without requiring every researcher and validator to re-install from scratch. Getting this split right during MVP and Phase 1 design is important: moving logic from coordinator to integrity zomes later is disruptive; moving it the other way is straightforward.

Holochain 0.8 (currently in planning) includes "Coordinator Updates: a new feature to allow updates of an application's business logic" as an explicit roadmap item, further strengthening this separation.

### Link Types, Anchors, and Paths: Making Data Queryable

Holochain has no global query. Every piece of data is content-addressed — you can only retrieve it if you already know its hash. This creates a discovery problem: how do you find "all studies from Cardiff University" or "all validations by this validator" without a central index?

The solution is a graph database built from **links**, **anchors**, and **paths**. A link connects a known address (the base) to an unknown one (the target), turning the DHT into a traversable graph. An anchor is simply a small string entry whose address is easy to calculate from its content — you hash the string and retrieve whatever is attached to that address. Links and anchors together solve the discovery problem: you pre-compute the anchor address from a known string, then follow links from it to find all the data hanging off it.

**Link types** are defined in the integrity zome alongside entry types, using the `hdk_link_types` macro on an enum. Each link type is named and validated separately. Coordinator zomes then use `create_link(base, target, link_type, tag)` to create links and `get_links(base, link_type_filter)` to retrieve them. ValiChord's integrity zomes need the following link type definitions:

Each DNA has its own integrity zome with its own `#[hdk_link_types]` enum — these are not shared across DNAs.

```rust
// --- Attestation DNA integrity zome ---
#[hdk_link_types]
pub enum LinkTypes {
    StudyToValidation,      // study entry → validation entries for that study
    ValidatorToValidation,  // agent pubkey → validation entries they authored
    ValidatorToAttestation, // agent pubkey → ValidationAttestation entries they authored
    StudyToHarmonyRecord,   // study entry → resulting harmony record
    StudyStatusPath,        // path anchor → study entry (for status-based queries)
    InstitutionPath,        // path anchor → study entry (for institution-based queries)
    DisciplinePath,         // path anchor → validation entry (for discipline queries)
    AgentToProfile,         // agent pubkey → ValidatorProfile entry  [device key, not person-stable — see multi-device identity note in engineer handover]
    /// Links the ValidationRequest to the validator's public commitment proof.
    /// Added in v12: replaces the broken get_agent_activity() private-action-counting
    /// approach. CommitmentAnchor is a public, zero-content DHT entry — everyone
    /// can see a commitment happened for this study, but not the outcome.
    RequestToCommitment,    // ValidationRequest ActionHash → CommitmentAnchor ActionHash
    /// Links the ValidationRequest to the current phase state.
    /// Validators who miss the reveal-open signal discover the phase by polling
    /// get_current_phase() which traverses this link.
    RequestToPhaseMarker,   // ValidationRequest ActionHash → PhaseMarker ActionHash
}

// --- Governance DNA integrity zome ---
#[hdk_link_types]
pub enum LinkTypes {
    ValidatorToReputation,  // agent pubkey → their reputation record  [device key, not person-stable — see multi-device identity note in engineer handover]
    RequestToHarmonyRecord, // ValidationRequest ref → HarmonyRecord
    DisciplinePath,         // path anchor → HarmonyRecord (for discipline queries)
    BadgePath,              // path anchor → ReproducibilityBadge (queryable by badge type)
}

// --- Researcher Repository DNA integrity zome (private membrane) ---
#[hdk_link_types]
pub enum LinkTypes {
    StudyToDataset,         // study entry → dataset entries (never leaves private DNA)
    ProtocolToDeviation,    // protocol entry → declared deviation entries
}

// --- Validator Workspace DNA integrity zome (private membrane) ---
#[hdk_link_types]
pub enum LinkTypes {
    TaskToPrivateAttestation, // task entry → sealed private attestation
}
```

**Paths** extend anchors into hierarchies. `Path::from("studies\0cardiff_university")` creates a two-component path where each component is linked to the next, forming a tree. The HDK ensures intermediate nodes exist before the leaf is created, so you can traverse from `"studies"` down to `"studies\0cardiff_university"` and find all studies registered under that branch. ValiChord's principal query paths are:

| Query | Path |
|---|---|
| All studies by institution | `studies\0{institution_id}` |
| All validations by discipline | `validations\0{discipline_slug}` |
| Studies by status | `studies\0status\0{active\|completed\|retracted}` |
| Validators by certification level | `validators\0{tier}` |

**Hotspot prevention with path sharding.** When a single anchor accumulates thousands of links, the DHT nodes responsible for that address become overloaded — this is the hotspot problem. Holochain's Path struct includes a built-in sharding DSL: prefix a path component with `<width>:<depth>#` to distribute load across multiple nodes. For example, `"2:1#cardiff_university"` takes the first 2 characters at depth 1, creating intermediate nodes `"ca"`, `"cb"` etc. that spread links across different parts of the hash space.

For ValiChord at Phase 1 scale (hundreds of studies), simple paths without sharding are adequate. At Phase 2 scale (thousands of studies, multiple institutions), the institution paths should be sharded by the first two characters of the institution identifier. The path sharding strategy belongs in the coordinator zome logic — it does not affect the integrity zome definitions and can be updated without forcing a network migration.

> **Engineering note:** The Holochain scaffolding tool asks explicit questions about collections and link structures. The link type enum above and the path table should be treated as the answer to those questions. Each `Path` also needs a corresponding `TypedPath` (via `path.typed(LinkTypes::InstitutionPath)`) so the HDK knows which link type to use when creating and querying path-based links.

---

### Data Validation Rules in Integrity Zomes

In Holochain, "validation" has two distinct meanings. Scientific validation — whether a study's methodology was sound — is ValiChord's subject matter. Holochain-level data validation is something different: it is the code that decides whether any given DHT operation is structurally and logically permitted, enforced by every peer independently before they store or serve data.

Every integrity zome must implement a `validate(op: Op)` callback. Holochain calls this function twice: first when an agent authors a record (before it is committed to their source chain), and again when a peer receives the corresponding DHT operations for storage. Because every node runs the same code, there is no trusted authority — invalid data simply cannot propagate. The function must be purely deterministic: no random numbers, no system clock, no mutable state. Dependencies are retrieved using `must_get_*` functions rather than live DHT queries.

The `Op` enum covers all seven DHT operation types: `StoreRecord`, `StoreEntry`, `RegisterUpdate`, `RegisterDelete`, `RegisterCreateLink`, `RegisterDeleteLink`, and `RegisterAgentActivity`. Each operation carries the relevant action and entry data. The validation function pattern-matches on these to enforce rules appropriate to each operation type.

**ValiChord's required validation rules by DNA:**

*Attestation DNA (shared, public):*

```rust
#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // Validation attestations FIRST — guarded arms must precede the
        // catch-all arms below, otherwise Rust's match ordering means the
        // unguarded RegisterUpdate/RegisterDelete arms will always fire first
        // and the immutability guarantee will never be enforced.
        FlatOp::RegisterUpdate(OpUpdate { original_action, .. })
            if matches!(
                must_get_action(original_action.clone())?.action().entry_type(),
                Some(EntryType::App(app)) if app.id() == EntryTypesId::ValidationAttestation
            ) =>
        {
            Ok(ValidateCallbackResult::Invalid(
                "Validation attestations cannot be updated after publication".into()
            ))
        }

        FlatOp::RegisterDelete(OpDelete { original_action, .. })
            if matches!(
                must_get_action(original_action.clone())?.action().entry_type(),
                Some(EntryType::App(app)) if app.id() == EntryTypesId::ValidationAttestation
            ) =>
        {
            Ok(ValidateCallbackResult::Invalid(
                "Validation attestations cannot be deleted — the record is permanent".into()
            ))
        }

        // Study entries: only the original researcher may update or delete
        FlatOp::RegisterUpdate(OpUpdate { original_action, .. }) => {
            let original = must_get_action(original_action)?;
            if op.action().author() != original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update a study entry".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        FlatOp::RegisterDelete(OpDelete { original_action, .. }) => {
            let original = must_get_action(original_action)?;
            if op.action().author() != original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete a study entry".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // Harmony Records: countersignature check (all assigned validators must have signed)
        // Uses validation_summary fields from the actual HarmonyRecord struct —
        // successful + partial + failed + inconclusive must equal total_validators.
        FlatOp::StoreEntry(OpEntry::CreateEntry { entry_type: EntryTypes::HarmonyRecord(record), .. }) => {
            let summary = &record.validation_summary;
            let signed_count = summary.successful_validations
                + summary.partial_validations
                + summary.failed_validations
                + summary.inconclusive_validations;
            if signed_count < summary.total_validators {
                return Ok(ValidateCallbackResult::Invalid(
                    "Harmony Record requires attestations from all assigned validators".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        _ => Ok(ValidateCallbackResult::Valid),
    }
}
```

*Governance DNA:*

- HarmonyRecord, ReproducibilityBadge, and ValidatorReputation writes: open to any participant. Any validator who participated in the round may trigger finalisation by calling `check_and_create_harmony_record`. No designated coordinator node is required. Content correctness is enforced by a completeness check (must have ≥ `num_validators_required` attestations) and idempotency guard in the coordinator layer.
- GovernanceDecision writes: only the `system_coordinator_key` agent may create these entries. Governance decisions represent human deliberation outcomes and require a designated recorder. `harmony_record_creator_key` has been removed — it no longer exists.

```yaml
# DNA 4 dna.yaml properties
properties:
  system_coordinator_key: "uhCAk..."  # may write GovernanceDecision only
  # Empty string = dev/test bypass (skips the key check entirely)
```
- Warrant records: any peer may create a warrant for another agent, but the warrant must reference a valid action hash pointing to the violation.

*Researcher Repository DNA (private membrane):*

- Within the private DNA, the researcher is the only participant — standard Holochain source chain integrity (sequence numbers, signatures) is sufficient. No custom validation rules are needed beyond the system defaults.

**The relationship to scientific validation:** These rules are enforced before data reaches the DHT. They are not about whether the science was done correctly — that is ValiChord's purpose. They are about whether the *record of that science* was written by the right agent, at the right time, in the right form. Getting them right during integrity zome design is critical: they cannot be relaxed after deployment without migrating to a new DNA. The rule that attestations are immutable is particularly important — it is the technical guarantee underpinning ValiChord's core promise that validation records cannot be retroactively altered.

> **Engineering note:** The scaffolding tool generates stub validation functions that return `ValidateCallbackResult::Valid` for all operations. These stubs must be replaced with the rules above before any production deployment. Leaving stubs in place means the system accepts any action from any agent — the scientific fraud prevention the document describes would not actually be enforced at the protocol level.

---

### Phase 0 Pragmatism

*(Update March 2026: This section was written before the Holochain infrastructure existed. The four-DNA hApp has since been fully implemented and integration-tested — 158 tests pass across two suites (94 Tryorama, 64 Rust sweettest), 1 skipped. The Phase 0 workload discovery study uses simple operational tools (time tracking, structured surveys) for its specific data collection purpose, which remains appropriate. The Holochain infrastructure exists in parallel and is ready for Phase 1 deployment; there is no PostgreSQL-to-Holochain migration required.)*

---

## Known Risks and Scope Limitations

The following risks have been identified through adversarial review and are documented here for transparency. Some have mitigations; others are honest boundaries.

### Computation, Not Provenance

ValiChord validates computation — it verifies that provided code, run on provided data, produces the claimed results. It does not validate data provenance. If raw data is fabricated but internally consistent, validators would successfully reproduce the computational results and the study could receive a high confidence rating for science built on false foundations.

This is not a design flaw. It is a boundary. No computational validation system can verify that a researcher actually observed what they claim to have observed in the laboratory, the field, or the clinic. ValiChord catches coding errors, analytical mistakes, undocumented dependencies, statistical misapplication, and post-hoc data manipulation. It does not catch well-executed fraud at the data generation stage.

**Mitigation:** Harmony Records and all ValiChord communications must be explicit about this boundary. A validated study is one whose computation reproduces — not one whose underlying data is guaranteed to be truthful. Complementary systems (data provenance tools, laboratory audit trails, statistical anomaly detection for fabrication patterns) address the data generation stage. ValiChord should integrate with these where possible but must not claim to replace them.

### Career Deference Bias

Even with commit-reveal protocols (which prevent validators from adjusting results after seeing others' findings), a subtler bias exists: a junior validator who knows they are assessing work by a senior figure at a prestigious institution may unconsciously look for reasons to confirm rather than critically assess.

**Mitigation:** Double-blind validation by default — **Phase 1 target, not yet technically enforced.** The design intent is that validators do not see author names, institutional affiliations, or funding sources. Author identity is revealed only in the published Harmony Record, after all validators have submitted final attestations. This removes the most direct trigger for deference bias.

**Current state:** `ValidationRequest` carries `data_access_url` and `protocol_access_url` fields that validators receive in full. If those URLs contain researcher-identifying information (e.g. `osf.io/jsmith/my-study`), the blinding is defeated. Enforcing it technically requires a **blinding proxy** — a service that serves dataset access via opaque URLs, stripping researcher identity before validators see the request. `researcher_institution` is already used server-side only (for COI enforcement in `validate()`) and is not intended to be displayed to validators, but this is a convention, not an architectural constraint in the current implementation.

**Phase 1 engineering task:** Build a blinding proxy layer. Until then, the double-blind guarantee is an operational convention enforced by the ValiChord team, not a structural property of the network.

### Early-Phase Fragility

In the early months of Phase 1, a single high-profile failure — where a ValiChord "Gold" study is later found to be based on fabricated data — could be reputationally fatal before the system has established credibility.

**Mitigation:** Manual audit of the first 100 studies receiving Gold-level certification. Higher scrutiny thresholds during Phase 1, including additional validators and extended review periods. Explicit public messaging that "validated" means "computation reproduces" and not "data is guaranteed truthful" — set expectations before a failure forces the conversation.

### Gold Badge Misrepresentation

Related to the computation/provenance boundary: a ValiChord Gold badge could be used — deliberately or through misunderstanding — as a general-purpose quality stamp, obscuring the fact that it certifies only computational reproducibility. A university press office writing "ValiChord-verified study shows..." without qualification, or a fraudster pointing to their Gold badge as evidence of data integrity, would misrepresent what ValiChord actually assessed. In the worst case, ValiChord could inadvertently "launder" fabricated data by giving it a stamp of computational success.

However, even when this happens, the validation record has forensic value. Without ValiChord, a retracted paper could have failed at any point — bad data, bad code, bad analysis, undocumented dependencies, post-hoc manipulation. With a Gold badge on a later-retracted study, investigators know the fraud was at data generation, not computation. That narrows the search considerably.

**Mitigation:** The badge format itself must make the boundary visible. Gold means "computation verified by independent validators" — never "study confirmed" or "data verified." Harmony Records should include a standard statement: "This record certifies computational reproducibility. Data provenance was not assessed." Public communications guidelines in the Governance Framework should provide explicit language for press offices, funders, and journals to prevent scope creep in how the badge is described. When misrepresentation occurs — and it will — rapid, public correction is a governance obligation, not an option.

### Functional De-Anonymisation in Niche Fields

Double-blind validation works well in large fields where many labs use similar methods. In niche computational fields — where only three labs worldwide work on a specific climate model, or a particular genomic pipeline has a single originating group — the data, code, or methodology itself is the researcher's signature. A validator working in that field will likely recognise whose work they are assessing regardless of whether names are removed from the submission. Double-blind is functionally impossible when the methods are the identity.

**Mitigation:** Double-blind remains the default because it works in most fields and removes the most direct trigger for deference bias. In niche fields where blinding fails, the other protective layers carry the weight. The blind commitment mechanism still prevents result adjustment — even if a validator recognises the Zurich lab's climate model, they have already sealed their findings as a private source chain entry before the countersigning reveal session begins. That seal is immutable. Validator-to-validator blinding still holds — validators do not know who else is assessing the same study, preventing coordination. Statistical detection mechanisms identify patterns of systematic leniency toward identifiable work across many validations, even when individual cases cannot be blinded. The system degrades gracefully rather than failing completely: full double-blind in large fields, commit-reveal and statistical detection in niche ones. The honest position is that de-anonymisation is a limitation in specialised domains, not that ValiChord has solved it.

### Semantic Gaming of AI Triage (Phase 2+ Risk)

If ValiChord introduces AI-assisted triage or difficulty assessment in later phases, adversarial techniques (paraphrasing documentation to manipulate automated scoring) could game difficulty ratings or confidence assessments.

**Mitigation:** Human-in-the-loop review for all AI-assisted triage decisions during initial deployment. Red-team testing of any AI triage tools before operational use. AI assistance as recommendation, never as final decision.

### DHT Growth at Scale (Phase 3 Risk)

As the network scales globally, the cumulative data burden of Harmony Records, Living Documents, and provenance chains grows. While Holochain's architecture distributes DHT storage across nodes (each node stores a neighbourhood, not the full dataset), sustained global growth requires monitoring to ensure that participation costs don't gradually favour well-resourced institutions — recreating centralisation pressure.

**Mitigation:** Monitor node participation costs as the network grows. Implement data archiving strategies for older records (moving completed, stable Harmony Records to cheaper storage while maintaining integrity verification). Design participation requirements so that lightweight nodes remain viable.

### Geopolitical Fragmentation (Phase 3+ Risk)

Different regions have varying regulatory obligations for data integrity and software validation. Governments could block ValiChord's DHT at the firewall level, creating epistemic silos where science is validated in some regions but inaccessible in others.

**Mitigation:** This is a political problem, not a technical one, and ValiChord cannot solve it unilaterally. The architecture should support federation — regional instances that can interoperate when political conditions permit — rather than assuming a single unified global network. Acknowledged as an open challenge for Phase 3 design.

### Validator Burnout and Dropout

The documents assume that if compensation is calibrated correctly, validators will participate sustainably. This may not hold. Postdocs face grant deadlines. Faculty have teaching commitments. Research software engineers have project cycles. Even well-compensated validation work competes with career-advancing activities (publishing, grant writing, supervising students). Validation may be treated as "service work" — valued in principle, deprioritised in practice — leading to high attrition after a small number of assignments.

**Mitigation:** Phase 0 should explicitly gather data on sustainable participation: not just "how long did this take?" but "would you do this regularly? How often? What would make you stop?" Longitudinal retention modelling should inform Phase 1 design. If sustainable individual participation is low (e.g. 2–3 validations per year per person), the validator pool must be sized accordingly. Longer-term, dedicated professional validator roles (paid full-time or part-time positions, not per-task freelancing) may be necessary for system reliability.

### Proprietary Tooling Dependencies

Many computational fields rely on licensed software (MATLAB, SAS, proprietary sequencing pipelines, commercial cloud configurations). If a study's workflow depends on software a validator cannot legally or practically access, reproduction is impossible regardless of data quality or documentation.

**Mitigation:** Proprietary dependencies must be captured as a specific dimension of the difficulty assessment in Phase 0. Some studies may be classified as unvalidatable specifically because of licensing barriers — that is an honest finding, not a system failure. For Phase 1+, options include: institutional licence-sharing agreements for validation purposes, containerised environments that include licensed software under institutional agreements, or explicit categorisation in Harmony Records noting that validation was conducted under specific tooling constraints. The long-term trajectory favours open-source scientific computing, but ValiChord must deal with the field as it is, not as it should be.

### Reproducibility Theatre

A researcher could invest heavily in making their repository look clean for ValiChord at Home assessment and triage while the actual scientific workflow involved undocumented manual steps, private scripts, one-off tweaks, or unreported decisions. The polished artifact passes triage; the real process remains irreproducible in practice. This is the validation equivalent of teaching to the test.

The Researcher Support auto-generate feature could inadvertently worsen this: if the system drafts a clean README, a researcher might accept it even though it doesn't accurately reflect what they actually did. A clean-looking README that misrepresents the analysis is worse than a messy one that's honest.

**Mitigation:** Validators should be trained to look for signs of over-polished submissions that lack the normal rough edges of genuine research workflows. Phase 0 qualitative data should capture instances where validators suspect undocumented steps. Longer-term, requiring computation environment snapshots (containerised environments capturing the full state at time of analysis) rather than reconstructed repositories would reduce the gap between the submitted artifact and the actual workflow. The Researcher Support document already warns that auto-generated content must be reviewed carefully by the author — but the risk of rubber-stamping remains and should be monitored.

### Adverse Selection in Early Adopters

The first wave of submissions will come disproportionately from reproducibility enthusiasts, open-science advocates, and labs already producing high-quality computational work. Early Harmony Records will therefore look unrealistically positive — high success rates, clean reproductions, few disagreements. This creates a honeymoon effect: inflated expectations of what "normal" validation looks like, followed by disappointment when ordinary messy science enters the pipeline and failure rates increase.

**Mitigation:** Explicit messaging from Phase 1 launch that early results reflect self-selected, high-quality submissions and are not representative of the broader scientific landscape. Phase 0 should deliberately recruit across a difficulty spectrum, including studies the researchers themselves suspect may not reproduce cleanly. Tracking and publishing submission demographics (career stage, institution type, field, self-reported confidence) from day one allows the community to contextualise early results honestly rather than treating them as baselines.

---

## Implemented Integration API (March 2026)

The REST API layer connects the Python analysis pipeline to the live Holochain network. It is live and fully operational in the Codespace demo.

### Endpoints

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/validate` | When keys set | Submit deposit ZIP; returns `job_id` immediately (202) |
| `GET` | `/result/<job_id>` | Never | Poll for results |
| `GET` | `/download/<job_id>` | Never | Download full report ZIP (cleans up job) |
| `GET` | `/health` | Never | Liveness check; includes `conductor: live\|offline` |
| `GET` | `/openapi.yaml` | Never | OpenAPI 3.0.3 spec |
| `GET` | `/docs` | Never | Swagger UI |
| `POST` | `/upload-chunk` | When keys set | Chunked upload for deposits > 100 MB |

### POST /validate — extended form fields

```
file            required  ZIP of the research deposit (max 100 MB)
validator_outcome  optional  Reproduced | PartiallyReproduced | FailedToReproduce
validator_notes    optional  Free text — what ran, what failed, specific errors
callback_url       optional  HTTPS URL to POST the completed result to
```

When `validator_outcome` is supplied, `harmony_record_draft.validator_attested` is `true` — the outcome is a genuine replication verdict. When omitted, `validator_attested` is `false` and the outcome is derived from deposit quality analysis (proxy mode).

### harmony_record_draft response shape

```json
{
  "outcome": { "type": "PartiallyReproduced", "content": { "details": "..." } },
  "validator_attested": true,
  "data_hash": "e3b0c44298fc1c149afb4c8996fb92427ae41e4649b934ca495991b7852b855",
  "findings_summary": { "critical": 0, "significant": 2, "low_confidence": 3, "total": 5 },
  "harmony_record_hash": "uhCkk7mXy...",
  "harmony_record_url": "https://..."
}
```

`harmony_record_hash` is `null` when the Holochain conductor is offline — the analysis results are always returned regardless.

### API key authentication

Set the `VALICHORD_API_KEYS` environment variable to a comma-separated list of valid keys. When unset, all endpoints are open (dev default). Clients include their key in `X-ValiChord-Key: <key>` on write requests.

### Webhooks

Supply `callback_url` in the `POST /validate` form. ValiChord fires one POST to that URL when the job completes, with `Content-Type: application/json`, `X-ValiChord-Job-Id: <job_id>` header, and the full result body. One retry after 5 seconds on failure.

For full API documentation and code examples in Python and TypeScript, see `docs/INTEGRATION_GUIDE.md`. The machine-readable spec is at `backend/openapi.yaml`.

---

## Two-Round Protocol — Proposed Extension (NOT YET IMPLEMENTED)

**Status: Design proposal only. No code has been written. The existing single-round protocol is unchanged.**

Full specification: `docs/23_Two_Round_Protocol_Proposal.md`

---

### Motivation

In the current single-round protocol, validators seal their `AttestationOutcome` (Reproduced / PartiallyReproduced / FailedToReproduce / UnableToAssess) *before* the reveal phase — based on comparing their execution output to the researcher's **published paper** claims. The `ResearcherReveal` (the formally committed values, cryptographically proven against the pre-submission hash) arrives on the DHT at the same moment validators reveal their attestations. The formal comparison between `validator.produced_value` and `researcher.committed_value` therefore happens outside the protocol as a background inference, not as a structured decision step.

The two-round protocol makes that comparison a first-class protocol step with its own commit-reveal cycle. Validators commit to raw findings first; see the researcher's formally committed values; then commit to their verdict blind to the other validators.

---

### Protocol Sequence (two-round studies only)

```
Round 1 — Raw Findings
  validator: seal_raw_findings()          → ValidatorRawFindings (DNA 2, private)
                                          → RawFindingsAnchor    (DNA 3, shared DHT)
  [all anchors present]
  validator: submit_raw_findings()        → ValidatorRawFindings published (DNA 3)
  researcher: [auto-triggered]
             reveal_researcher_result()  → ResearcherReveal (DNA 3)

Round 2 — Verdict
  validator: seal_verdict()               → VerdictAnchor (DNA 3, shared DHT)
  [all verdict anchors present]
  validator: submit_verdict()             → ValidationAttestation (DNA 3)
                                            ↑ same entry type as single-round reveal
  [all ValidationAttestations present]
  any validator: → check_and_create_harmony_record() (DNA 4)
```

---

### Changes Required

**`valichord/shared_types/src/lib.rs`**

Updated `ValidationPhase` enum — two new variants (added after `RevealOpen`):
```rust
pub enum ValidationPhase {
    RevealOpen,
    VerdictCommitOpen,   // all Round 1 reveals + ResearcherReveal present
    VerdictRevealOpen,   // all VerdictAnchors sealed
    Complete,
}
```

No new outcome types. Round 2 verdict uses the existing `AttestationOutcome` enum unchanged.

---

**`attestation_integrity` — new `ValidationRequest` field**

```rust
pub struct ValidationRequest {
    // ... existing fields unchanged ...

    /// Opt-in two-round protocol for human validators.
    /// When true: Round 1 seals raw findings only; Round 2 seals the verdict
    /// (Reproduced / PartiallyReproduced / etc.) after ResearcherReveal is on the DHT.
    /// When false (default): existing single-round behaviour.
    /// #[serde(default)] — all existing entries on the DHT deserialise as false.
    #[serde(default)]
    pub two_round_protocol: bool,
}
```

---

**`attestation_integrity` — new entry types**

```rust
/// Round 1 sealed record — raw execution findings, no verdict.
/// Private entry in DNA 2 (Validator Workspace). Never leaves the validator's device.
/// Replaces ValidatorPrivateAttestation as the DNA 2 commit entry for two-round studies.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidatorRawFindings {
    pub request_ref:             ExternalHash,
    pub produced_values:         Vec<ProducedMetric>,  // what the execution output
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub computational_resources: ComputationalResources,
    pub discipline:              Discipline,
    pub nonce:                   Vec<u8>,               // generated at seal time
    pub commitment_hash:         Vec<u8>,               // SHA-256(msgpack(self) || nonce)
}

/// Simple produced-value record for Round 1 — no expected_value yet.
/// expected_value is filled from ResearcherReveal.metrics at Round 2 verdict time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProducedMetric {
    pub metric_name:    String,
    pub produced_value: String,
}

/// Round 2 commitment anchor — proof that a validator has sealed their verdict,
/// with no indication of what that verdict is.
/// Immutable after creation.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct VerdictAnchor {
    pub request_ref:              ExternalHash,
    pub validator:                AgentPubKey,
    /// SHA-256(msgpack(ValidationAttestation) || nonce). Verified at submit_verdict.
    pub verdict_commitment_hash:  Vec<u8>,
    pub validation_request_hash:  ActionHash,
}
```

New link types in `attestation_integrity::LinkTypes`:
```rust
/// request_ref path → RawFindingsAnchor ActionHash
RequestToRawFindingsAnchor,
/// request_ref path → VerdictAnchor ActionHash
RequestToVerdictAnchor,
/// AgentPubKey → ValidatorVerdict ActionHash (tag = request_ref bytes)
ValidatorToVerdict,
```

Immutability rules: `VerdictAnchor` blocks updates and deletes in `validate()`, identical to `CommitmentAnchor`.

---

**`attestation_coordinator` — new functions**

```rust
/// Round 1 commit. DNA 2 equivalent of seal_private_attestation.
/// Creates ValidatorRawFindings (private, DNA 2) and fires
/// notify_raw_findings_sealed to DNA 3 (analogous to notify_commitment_sealed).
/// Gated: only for two_round_protocol = true studies.
pub fn seal_raw_findings(input: RawFindingsInput) -> ExternResult<ActionHash>

/// Round 1 reveal. DNA 3 equivalent of submit_attestation.
/// Gated: all RawFindingsAnchors present for this study.
/// Writes ValidatorRawFindings to the shared DHT.
/// When all Round 1 reveals are present, auto-triggers reveal_researcher_result
/// (researcher reveal is protocol-driven in the two-round flow).
pub fn submit_raw_findings(input: RawFindingsRevealInput) -> ExternResult<ActionHash>

/// Round 2 commit. Creates VerdictAnchor on shared DHT.
/// Gated: all Round 1 reveals AND ResearcherReveal present.
/// If called on a two_round_protocol = false study, rejected.
pub fn seal_verdict(input: VerdictSealInput) -> ExternResult<ActionHash>

/// Round 2 reveal. Takes AttestationRevealInput (same struct as submit_attestation).
/// Verifies SHA-256(msgpack(attestation) || nonce) against VerdictAnchor.commitment_hash.
/// Writes ValidationAttestation — same entry type as single-round reveal.
/// OutcomeSummary.key_metrics[i].expected_value is populated from ResearcherReveal.metrics.
/// When all ValidationAttestations present, fires check_and_create_harmony_record.
pub fn submit_verdict(input: AttestationRevealInput) -> ExternResult<ActionHash>
```

**Modified `submit_attestation`** — skips the `call_governance_fire_and_forget` call when `two_round_protocol = true` on the study. Governance finalisation is triggered by `submit_verdict` instead.

---

**Governance DNA — no structural changes**

`HarmonyRecord`, `derive_majority_outcome`, `derive_agreement_level`, `check_and_create_harmony_record`, and the badge system all work unchanged. The Round 2 `submit_verdict` produces `ValidationAttestation` entries in exactly the same form as the single-round `submit_attestation`. The governance layer cannot distinguish between the two flows — and does not need to.

---

### Backwards Compatibility

- `ValidationRequest.two_round_protocol` uses `#[serde(default)]` — all existing entries deserialise as `false`
- All existing single-round studies, tests, and integrations are completely unaffected
- DNA hash changes only if this feature is merged into `attestation_integrity` — treat as a deliberate network reset at that point

---

## Frontend — `valichord-ui`

**Status: Complete (v0.4.2, April 2026).** A Svelte 5 + TypeScript single-page application that connects directly to a running Holochain conductor via `AppWebsocket` over WebSocket — no intermediary server required.

### Tech Stack

| Component | Choice |
|---|---|
| Framework | Svelte 5 (TypeScript, Vite) |
| Holochain client | `@holochain/client` v0.20.4-rc.0 |
| Entry point | `valichord-ui/src/App.svelte` |
| Type definitions | `valichord-ui/src/lib/types.ts` — TypeScript mirrors of all Rust types |
| Conductor bridge | `valichord-ui/src/lib/holochain.ts` — singleton `AppWebsocket` wrapper |
| State | `valichord-ui/src/lib/store.ts` — Svelte stores |

### Port Detection

The app resolves the conductor's WebSocket port from three sources in priority order:
1. `window.location.hash` — Holochain Launcher injects `#APP_PORT=PORT` at startup
2. `VITE_HC_PORT` build-time env var — set in `.env` for local development
3. `AppWebsocket` default — falls back to Launcher's well-known port

`AppWebsocket.connect()` requires the `url` option to be a `URL` object, not a plain string: `{ url: new URL("ws://localhost:PORT") }`.

### Role Detection

On connect, `get_validator_profile(myPubKey)` is called on the `attestation` zome. If a `ValidatorProfile` is returned, the active tab defaults to **Validator**. Otherwise it defaults to **Researcher**. Users can switch freely between all three tabs.

### Signal Handling

`RevealOpen` signals arrive as `{ RevealOpen: { request_ref: Uint8Array } }` (external-tag serde — the `Signal` enum in `attestation_coordinator` has no `#[serde(tag)]` attribute). The global listener in `App.svelte` calls `addPendingReveal(request_ref)` which the `ValidatorView` consumes to surface the reveal workflow.

### Three Views

**ResearcherView** (`src/lib/ResearcherView.svelte`):
1. Submit `ValidationRequest` — data hash (hex), access URL, deposit access type, discipline, institution, validation tier, number of validators required
2. Lock result metrics before validators finish — `lock_researcher_result({ request_ref, metrics })` on the `researcher_repository` DNA + `publish_researcher_commitment` on the `attestation` DNA
3. Reveal when prompted — `get_locked_result(request_ref)` (returns stored nonce) → `reveal_researcher_result({ request_ref, metrics, nonce })` on the `attestation` DNA

**ValidatorView** (`src/lib/ValidatorView.svelte`) — five-screen workflow:
1. **Dashboard** — profile status, pending reveal badge from `RevealOpen` signals
2. **Setup profile** — `publish_validator_profile` (institution, disciplines, certification tier, availability)
3. **Browse open requests** — `get_pending_requests_for_discipline` filtered by validator's disciplines; lists all claimable studies
4. **Attest (commit)** — after `claim_study` on DNA 3, UI calls `receive_task` on DNA 2 to create a `ValidationTask` and obtain `task_hash`; full attestation form; on submit calls `seal_private_attestation({ task_hash, attestation })` on DNA 2 — nonce is generated internally and never passed by the UI; `post_commit` fires `notify_commitment_sealed` automatically
5. **Reveal** — triggered by `RevealOpen` signal or manual check; `get_private_attestation_for_task` retrieves the sealed nonce; `submit_attestation({ attestation, nonce })` publishes to DNA 3

**GovernanceView** (`src/lib/GovernanceView.svelte`) — read-only analytics:
- Browse `HarmonyRecord` entries by discipline via `get_harmony_records_by_discipline`
- Inferred badge (Gold/Silver/Bronze/Failed) from outcome agreement counts — matches the badge threshold logic in the governance DNA
- Validator type breakdown per round (`ValidatorAgentType` from `HarmonyRecord.validator_types`)
- Advanced: `force_finalize_round` panel (collapsed amber `<details>` block) — accepts hex `request_ref`, calls `force_finalize_round` on the governance DNA for stuck rounds

### Serialisation Rules — TypeScript ↔ Rust

All types in `types.ts` mirror the Rust serde encoding exactly:

| Type | Serde strategy | TypeScript encoding |
|---|---|---|
| `Discipline`, `AttestationOutcome`, `DeviationType` | adjacent-tag (`#[serde(tag="type", content="content")]`) | unit → `{ type: "Reproduced" }`, struct → `{ type: "PartiallyReproduced", content: { details: "..." } }` |
| `ValidatorAgentType`, `CertificationTier`, `ValidationTier`, `AttestationConfidence`, `AgreementLevel`, `ValidationFocus` | plain string (no tag) | `"Individual"`, `"Gold"`, `"Basic"`, etc. |
| `CompensationTier` | external-tag (default serde, no attributes) | `{ Tier1: { amount_pence: 5000 } }` |
| `ExternalHash` | `Uint8Array` (39 bytes) | construct via `hashFrom32AndType(core32, HoloHashType.External)` — DHT location bytes must be a valid blake2b checksum; never use raw `new Uint8Array(39)` |

### Running the Frontend

```bash
cd valichord-ui
cp .env.example .env           # set VITE_HC_PORT to your conductor's app port
npm install
npm run dev                    # opens http://localhost:5173
```

Requires a running Holochain conductor with the `valichord.happ` installed. See `valichord-ui/FRONTEND.md` for the full UX walkthrough.

---

## What This Document Does and Doesn't Claim

**It does claim:**
- The architectural approach is sound and confirmed feasible by Holochain Foundation engineers
- The four-DNA hApp is fully implemented and tested — 158 integration tests pass across two suites (94 Tryorama, 64 Rust sweettest), 1 skipped
- The REST API layer is live, with API keys, webhooks, OpenAPI spec, and Swagger UI
- The REST API is integration-ready — any tool that can make an HTTP request can integrate

**It does not claim:**
- That these specific struct definitions are final (see Important Note on Status for actual divergences)
- That all engineering problems are solved (Known Gaps are documented in the Engineer Handover)
- That the system can be built or operated by one person without infrastructure support
- That ValiChord validates data provenance — it validates computation (see Known Risks and Scope Limitations)

---

**Companion Documents:**
- *ValiChord Vision & Architecture* — What ValiChord is and why it matters
- *ValiChord Governance Framework* — How the system resists corruption
- *ValiChord Phase 0 Proposal* — Workload Discovery Pilot (~£150K FEC, 12 months)
- *ValiChord Researcher Support* — Feedback pipeline and pre-validation tools
- *Engineer Handover* (`docs/13_Valichord_Engineer_Handover.md`) — Authoritative implementation reference
- *Integration Guide* (`docs/INTEGRATION_GUIDE.md`) — REST API integration for external tools

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**

