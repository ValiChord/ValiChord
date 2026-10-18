<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">
</div>

# ValiChord — Integration Tests

> **Updated 2026-10-18.** The integration suite is now **sweettest only** (Rust, `valichord/sweettest_integration/tests/`). The **Tryorama** suite described in the first half of this page was **retired on 2026-08-03** (upstream Tryorama will not support Holochain 0.7; its unique tests were ported to sweettest first) and `valichord/tests/` no longer exists. That half is kept as a historical record only — none of its commands will work. For current counts and how to run every suite, see [TESTING.md](../TESTING.md) and the CI workflow `.github/workflows/tests.yml`.

- **Sweettest** (Rust/`cargo test`) — native conductor harness, the only integration suite. Authoritative source: `valichord/sweettest_integration/tests/`. Runs in CI on every push and PR.
- **Tryorama** (TypeScript/Node) — *historical.* Last recorded status: 96 pass, 1 skipped, 0 fail (2026-05-09).

---

## Tryorama Integration Tests (historical — retired 2026-08-03)

Four test files, one per DNA. All tests exercised live Holochain conductors via
the compiled `workdir/valichord.happ` bundle. The commands below are kept as a record; `tests/` has been deleted.
---

## Build prerequisites

```bash
# 1. Rust WASM toolchain
rustup target add wasm32-unknown-unknown

# 2. Holochain CLI (hc)
cargo install holochain hc --locked

# 3. Node dependencies
cd tests && npm install
```

## Build and run

```bash
# From valichord/ workspace root

export PATH="/home/codespace/.cargo/bin:$PATH"

# Compile all four WASM zomes
cargo build --target wasm32-unknown-unknown --release

# Pack each DNA
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna

# Pack the hApp bundle (reads workdir/ DNAs)
hc app pack . -o workdir/valichord.happ

# Run all tests
cd tests && npm test
```

> **Warning:** Do NOT use `pack_dna.py`. It embeds the attestation DNA bytes for
> all four roles, making every cell require the attestation membrane proof.
> Always use `hc dna pack` + `hc app pack` directly.

---

## Test inventory

### DNA 1 — `researcher_repository.test.ts` (14 tests)

| ID  | Test name | Status |
|-----|-----------|--------|
| 1.1 | registered study is retrievable by its ActionHash | PASS |
| 1.2 | get_study returns null for an unknown ActionHash | PASS |
| 2.1 | protocol is retrievable via its parent study | PASS |
| 2.2 | get_protocol_for_study returns null when no protocol registered | PASS |
| 3.1 | two snapshots are both retrievable for the same study | PASS |
| 3.2 | get_snapshots_for_study returns empty array before any snapshot | PASS |
| 4.1 | declared deviation is retrievable for its parent study | PASS |
| 4.2 | get_deviations_for_study returns empty array when no deviation declared | PASS |
| 5.1 | compute_data_hash returns a 39-byte ExternalHash | PASS |
| 5.2 | same bytes always produce the same hash (deterministic) | PASS |
| 5.3 | different bytes produce different hashes (collision resistance) | PASS |
| 6.1 | attempting to delete a PreRegisteredProtocol is rejected (no delete fn in API) | PASS |
| 7.1 | get_all_studies returns empty list before any study registered | PASS |
| 7.2 | get_all_studies returns all 3 registered studies with distinct ActionHashes | PASS |

### DNA 2 — `validator_workspace.test.ts` (7 tests)

| ID  | Test name | Status |
|-----|-----------|--------|
| 1.1 | received task is retrievable by its ActionHash | PASS |
| 1.2 | get_task returns null for an unknown ActionHash | PASS |
| 2.1 | sealed private attestation is retrievable via its parent task | PASS |
| 2.2 | get_private_attestation_for_task returns null before any attestation | PASS |
| 3.1 | get_all_tasks returns all 3 received tasks from the local source chain | PASS |
| 4.1 | get_all_private_attestations returns empty list when no attestations sealed | PASS |
| 4.2 | get_all_private_attestations returns all sealed attestations across multiple tasks | PASS |

### DNA 3 — `attestation.test.ts` (46 tests, 1 Tryorama-skipped)

| ID   | Test name | Status |
|------|-----------|--------|
| 1.1  | agent with valid membrane proof (≥64 bytes) can join | PASS |
| 1.2  | agent with no membrane proof is rejected at genesis_self_check | PASS |
| 1.3  | agent with too-short membrane proof (<64 bytes) is rejected | PASS |
| 1.4  | agent with valid real Ed25519 proof is accepted by coordinator init | PASS |
| 1.5  | agent with wrong-signature proof is rejected by coordinator init | PASS |
| 2.1  | two validators commit, phase opens, both reveal, attestations retrievable | PASS |
| 3.1  | late-joining validator discovers RevealOpen by polling, not via signal | PASS |
| 4.1  | attempting to update a ValidationAttestation is rejected | PASS |
| 4.2  | attempting to delete a CommitmentAnchor is rejected | PASS |
| 5.1  | published validator profile is retrievable by agent public key | PASS |
| 5.2  | get_validator_profile returns null when no profile published | PASS |
| 5.3  | assess_difficulty → get_difficulty_assessment returns record + correct request_ref; unknown ref returns null | PASS |
| 6.1  | submitted ValidationRequest is retrievable by its ActionHash | PASS |
| 6.2  | get_validation_request returns null for an unknown ActionHash | PASS |
| 7.1  | attempting to update a CommitmentAnchor is rejected (no update fn in API) | PASS |
| 7.2  | attempting to update a PhaseMarker is rejected (no update fn in API) | PASS |
| 7.3  | attempting to delete a PhaseMarker is rejected (no delete fn in API) | PASS |
| 8.1  | get_pending_requests_for_discipline returns request for matching discipline | PASS |
| 8.2  | get_pending_requests_for_discipline returns empty for a different discipline | PASS |
| 9.1  | seal_private_attestation post_commit triggers notify_commitment_sealed in attestation DNA | PASS |
| 10.1 | Bob cannot read Alice's sealed private attestation from Bob's workspace cell | PASS |
| 11.1 | one commit with minimum_validators=2 leaves phase as null | PASS |
| 12.1 | 3 validators all Reproduced → BronzeReproducible badge issued | PASS |
| 12.2 | 5 validators all Reproduced → SilverReproducible badge issued | PASS |
| 12.3 | 7 validators all Reproduced → GoldReproducible badge issued | SKIP¹ |
| 13.1 | 3 validators all FailedToReproduce → FailedReproduction badge issued | PASS |
| 14.1 | update_validator_reputation then get_validator_reputation returns the record | PASS |
| 15.1 | two ComputationalBiology profiles published → both returned; MachineLearning returns 0 | PASS |
| 16.1 | check_all_commitments_sealed: false after 1 of 2 commits, true after 2nd | PASS |
| 17.1 | get_validation_request_for_data_hash returns the record for a known data_hash | PASS |
| 17.2 | get_validation_request_for_data_hash returns null for an unknown data_hash | PASS |
| 18.1 | get_validators_for_institution returns profiles for matching institution, empty for non-matching | PASS |
| 19.1 | get_attestations_for_discipline returns attestation for matching discipline, empty for non-matching | PASS |
| 20.1 | validator claims a study and the claim is retrievable | PASS |
| 20.2 | same validator cannot claim the same study twice | PASS |
| 20.3 | validator from the same institution as researcher is rejected (COI) | PASS |
| 20.4 | claiming when all slots are full is rejected | PASS |
| 20.5 | release_claim removes the claim from get_claims_for_request | PASS |
| 21.1 | reclaim_abandoned_claim returns false when claim is younger than timeout_secs | PASS |
| 21.2 | returns true and frees the slot when timeout has elapsed; replacement can claim | PASS |
| 21.3 | returns false when validator has already submitted an attestation | PASS |
| 22.1 | happy path: link two agents and retrieve via get_linked_agents | PASS |
| 22.2 | self-link is rejected | PASS |
| 22.3 | bad signature is rejected | PASS |
| 22.4 | either named agent can revoke; entry disappears from get_linked_agents | PASS |
| 22.5 | third-party revocation is rejected | PASS |

> ‡ **Phase threshold (11.1):** Passes on a clean Codespace. `dhtSync([alice, bob])` can time out at 40 s when the Codespace is under load. Clean up with `pkill -f holochain; pkill -f lair-keystore` before running.

> † **Silver (12.2):** Passes on a clean Codespace. May fail with WebsocketClosedError when the Codespace is under heavy load (5 conductors). Clean up orphaned processes with `pkill -f kitsune2-bootstrap-srv; pkill -f holochain; pkill -f lair-keystore` before running.

> ¹ **Tryorama-skipped:** requires 7 simultaneous Holochain conductors. Conductor
> processes exhaust available websocket connections in resource-constrained environments
> (Codespace / CI with <16 GB RAM). **Covered by sweettest test 15**
> (`sweettest_integration/tests/governance.rs` → `gold_badge_issued_with_seven_validators`) —
> in-process conductors make 7-agent runs feasible within normal RAM budgets. Run the
> sweettest for authoritative GoldReproducible coverage.

### DNA 4 — `governance.test.ts` (24 tests)

| ID   | Test name | Status |
|------|-----------|--------|
| 1.1  | two calls for the same request_ref with no attestations both return null | PASS |
| 1.2  | second call short-circuits when HarmonyRecord already exists | PASS |
| 2.1  | a validator who did not submit the ValidationRequest can trigger finalisation | PASS |
| 2.2  | premature finalisation (only 1 of 2 required attestations) returns null | PASS |
| 3.1  | researcher → request → validator attestations → HarmonyRecord on DHT | PASS |
| 4.1  | any validator can update reputation (not key-gated) | PASS |
| 4.2  | GovernanceDecision remains key-gated — non-coordinator key is rejected | PASS |
| 5.1  | get_harmony_records_by_discipline returns the record after creation | PASS |
| 5.2  | get_harmony_records_by_discipline returns empty array when no records exist | PASS |
| 5.3  | get_badges_for_study returns empty when validator count < 3 | PASS |
| 6.1  | get_badges_for_study returns BronzeReproducible when 3 validators all Reproduced | PASS |
| 7.1  | 1 Reproduced + 2 FailedToReproduce → Divergent agreement + FailedReproduction badge | PASS |
| 8.1  | create_governance_decision + get_all_governance_decisions round-trip | PASS |
| 8.2  | multiple GovernanceDecisions are all returned by get_all_governance_decisions | PASS |
| 9.1  | get_badges_by_type returns empty list before any badge of that type is issued | PASS |
| 9.2  | get_badges_by_type returns the correct badge after check_and_create_harmony_record | PASS |
| 10.1 | no delete function exists for HarmonyRecord in the coordinator API | PASS |
| 10.2 | no delete function exists for GovernanceDecision in the coordinator API | PASS |
| 10.3 | no delete function exists for ReproducibilityBadge in the coordinator API | PASS |
| 11.1 | force_finalize_round returns null when round has not yet timed out (< 7 days old) | PASS |
| 11.2 | force_finalize_round returns null when no attestations exist yet | PASS |

### Security — `security.test.ts` (7 tests)

| ID   | Test name | Status |
|------|-----------|--------|
| S1   | Duplicate attestation guard — second submit_attestation for the same study rejects | PASS |
| S2   | Duplicate commitment guard — second notify_commitment_sealed for the same study rejects | PASS |
| S3   | Researcher commitment idempotency — second publish_researcher_commitment for the same study rejects | PASS |
| S4.1 | reclaim_abandoned_claim min_claim_timeout_secs floor — caller-supplied timeout below DNA floor is overridden — reclaim returns false | PASS |
| S4.2 | when no DNA floor is set (0), caller-supplied timeout_secs=0 succeeds immediately | PASS |
| S5   | force_finalize_round conservative abort on missing VR — returns null when no ValidationRequest exists for the request_ref | PASS |
| S6   | reveal_researcher_result idempotency — second reveal for the same study rejects | PASS |

---

## Sweettest Integration Tests

Rust-native tests using Holochain's `sweettest` harness. Run directly via `cargo test` — no Node, no Tryorama. Authoritative source: `valichord/sweettest_integration/tests/`. The lists below were counted from the source on 2026-10-18 (117 tests across nine files); if they disagree with the files, the files win.

**How to run** (from `valichord/`, after building the WASM and packing the DNAs with `hc dna pack` / `hc app pack` as in the CI workflow):

```bash
./run-sweettest.sh attestation                # one suite; keeps the raw log and cross-checks the result count
./run-sweettest.sh governance silver_badge    # optional name filter
```

CI runs each suite as `cargo test --test <suite> -- --test-threads=1` (see `.github/workflows/tests.yml`). The immutability and forgery tests need a separate test-only build: `./build-test-dnas.sh`, then `VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh immutability_tripwire`.

### DNA 1 — `researcher_repository.rs` (17 tests)

All entries are private (single-agent source chain only). No DHT sync needed.

register_and_get_study · get_study_unknown_hash_returns_none · register_and_get_protocol · get_protocol_returns_none_before_registration · two_snapshots_are_both_retrievable · get_snapshots_empty_before_any_snapshot · declare_and_retrieve_deviation · get_deviations_empty_before_any_declaration · compute_data_hash_returns_external_hash · compute_data_hash_is_deterministic · compute_data_hash_collision_resistant · protocol_immutability_no_delete_fn_in_api · get_all_studies_empty_initially · get_all_studies_returns_all_registered · lock_researcher_result_creates_private_entry · get_locked_result_returns_none_for_unknown_request · lock_researcher_result_publishes_commitment_to_attestation_dna

### DNA 2 — `validator_workspace.rs` (13 tests)

All entries are private (single-agent source chain only).

receive_and_get_task · get_task_unknown_hash_returns_none · seal_and_get_private_attestation · get_private_attestation_returns_none_before_sealing · get_all_tasks_empty_initially · get_all_tasks_returns_all_received · get_all_private_attestations_empty_initially · get_all_private_attestations_returns_all_sealed · private_attestation_immutability_no_delete_fn_in_api · get_abstention_returns_none_before_recording · record_and_retrieve_deliberate_abstention · duplicate_abstention_is_rejected · bob_cannot_read_alices_sealed_private_attestation

### DNA 3 — `attestation.rs` (30 tests)

submit_and_get_validation_request · get_validation_request_unknown_returns_none · get_validation_request_for_data_hash · get_current_phase_none_before_commits · two_commits_trigger_reveal_open_phase · full_commit_reveal_round · get_attestations_for_request_empty_before_reveal · publish_and_get_validator_profile · get_validator_profile_none_when_unpublished · claim_and_release_study · claim_study_coi_same_institution_rejected · reclaim_abandoned_claim_timeout_zero · assess_and_get_difficulty · link_agent_identity_self_link_rejected · get_linked_agents_empty_initially · late_joining_validator_discovers_reveal_open_via_dht_poll · update_validator_profile_merges_fields · check_all_commitments_sealed_lifecycle · get_researcher_reveal_none_then_some · revoke_agent_identity_link_removes_from_linked_agents · get_my_claimed_studies_filtered_by_release · researcher_cannot_claim_their_own_study · claim_rejected_when_study_is_at_capacity · same_validator_cannot_claim_a_study_twice · reclaim_refused_once_validator_has_attested · third_party_cannot_revoke_an_identity_link · validator_profiles_are_indexed_by_discipline_and_institution · pending_requests_are_indexed_by_discipline · attestations_are_indexed_by_discipline · link_agent_identity_bad_signature_rejected

### DNA 4 — `governance.rs` (22 tests)

check_and_create_harmony_record_no_attestations_returns_none · full_round_creates_harmony_record · check_and_create_harmony_record_idempotent · any_participant_can_finalize · premature_finalization_returns_none · force_finalize_round_with_partial_quorum · governance_decision_non_matching_key_rejected · update_validator_reputation_dev_bypass · get_harmony_records_by_discipline_empty_initially · get_harmony_records_by_discipline_returns_record_after_round · get_badges_for_study_none_with_two_validators · get_badges_by_type_bronze_with_three_validators · validator_tier_promotes_to_standard_after_three_rounds · validator_tier_stays_provisional_before_three_rounds · ai_validator_tier_does_not_advance_through_rounds · gold_badge_issued_with_seven_validators · silver_badge_issued_with_five_validators · get_pending_request_refs_includes_other_discipline_studies · sweep_cannot_finalize_a_round_still_in_progress · live_claim_blocks_force_finalize · released_claim_allows_force_finalize · governance_decisions_round_trip_and_accumulate

### Security — `security.rs` (12 tests)

Covers protocol-gap fixes and commit-reveal hash verification.

- S1. Duplicate attestation guard — second submit_attestation rejected
- S2. Duplicate commitment guard — second notify_commitment_sealed rejected
- S3. Researcher commitment idempotency — second publish_researcher_commitment rejected
- S4a. reclaim_abandoned_claim: timeout below DNA floor → reclaim returns false
- S4b. reclaim_abandoned_claim: no floor (0) → timeout_secs=0 succeeds
- S5. force_finalize_round conservative abort when no ValidationRequest
- S6. reveal_researcher_result idempotency — second call rejected
- S7. A reveal with the real nonce passes hash verification
- S8. A tampered reveal is rejected by hash verification
- S9–S11. Reproduction-bundle hash binding: a different bundle hash is rejected, the same one succeeds, a wrong-length one is rejected

### Membrane — `membrane_proof.rs` (6 tests)

The only tests that run with a real Ed25519 credential issuer instead of the dev bypass: a valid proof is accepted; a wrong signature, a proof issued to another agent, a missing proof and a too-short proof are each rejected at genesis; an empty issuer bypasses the membrane (dev/test mode).

### Test-only builds — `immutability_tripwire.rs` (15), `harmony_record_forgery.rs` (1), `validator_tier_forgery.rs` (1)

These need the `--features test_utils` build from `build-test-dnas.sh`, because no production coordinator can write a forbidden update, delete or forged entry. The tripwires prove the integrity zomes reject forbidden updates and deletes; the two forgery tests (added with PR #47) prove peers refuse a forged HarmonyRecord and a self-assigned validator tier in `validate()`.

---

## Remaining gaps

These were the gaps recorded when the Tryorama suite was current. Status as of 2026-10-18 is in the Notes column.

| Area | What to add | Notes |
|------|-------------|-------|
| DNA 3 — GoldReproducible (12.3) | 7 validators all Reproduced → GoldReproducible | **Covered by sweettest** (`gold_badge_issued_with_seven_validators`). |
| DNA 1 — lock_researcher_result | lock_researcher_result → LockedResult stored privately + ResearcherResultCommitment on DNA 3; get_locked_result returns private record | **Covered by sweettest** (`lock_researcher_result_creates_private_entry`, `lock_researcher_result_publishes_commitment_to_attestation_dna`). |
| DNA 3 — reveal_researcher_result | Correct metrics+nonce → ResearcherReveal on DHT; wrong nonce → error rejected; get_researcher_reveal returns verified reveal | **Partly covered:** `get_researcher_reveal_none_then_some` reveals using the empty-nonce dev bypass, and S6 checks idempotency. A researcher reveal with a real nonce, and one with a wrong nonce, still have no test. |
| DNA 4 — force_finalize_round success path | Timed-out round + partial attestations → HarmonyRecord created | **Covered by sweettest** (`force_finalize_round_with_partial_quorum`, `released_claim_allows_force_finalize`). The timeout is now a DNA property, `round_timeout_secs`, so tests set it to 0. |

---

## Architecture notes

- `minimum_validators: 2` is set in test DNA properties (`happ.yaml`; the attestation `dna.yaml` default is 3). It is a network-wide floor that every peer enforces on a ValidationRequest, not the quorum target. `check_all_commitments_sealed_inner` uses `num_validators_required` from the `ValidationRequest` entry (not the DNA-property `minimum_validators`) — phase opens when the study's own validator count has committed.
- `system_coordinator_key` gates `GovernanceDecision` **and** `ValidatorReputation` writes (`governance_integrity`). `harmony_record_creator_key` no longer exists — any participant may write a `HarmonyRecord` or `ReproducibilityBadge`, but since PR #47 a HarmonyRecord must carry its validators' signed attestations and every peer checks them against the request, outcome, agreement level and cohort size. Empty string = dev/test bypass for `system_coordinator_key`.
- Membrane proof signature verification is real Ed25519 (`verify_signature(issuer_key, sig, Vec<u8> of joining agent's 39-byte pubkey)`). Since PR #47 it runs in `attestation_integrity::check_joining_certificate`, called from `validate()` by **every peer**, not only from the joining agent's own `init()`. Empty `authorized_joining_certificate_issuer` = dev/test bypass.
- Tests call `notify_commitment_sealed()` directly on the attestation DNA; in production this is triggered by DNA 2's `post_commit` (exercised by Tryorama test 9.1 in its day). The function now takes `CommitmentSealedInput { request_ref, commitment_hash }` — pass the commitment hash alongside the request reference.
- *(Tryorama-era)* `dhtSync` is required between agents for any multi-player read assertion.
- *(JS clients, e.g. the UI and demo)* ExternalHash in JS: use `hashFrom32AndType(core32, HoloHashType.External)` — never `new Uint8Array(39).fill(byte)` (DHT location bytes must be a valid blake2b checksum).
- `Discipline` and `AttestationOutcome` use `#[serde(tag="type", content="content")]` (adjacent tagging) → `{ type: "ComputationalBiology" }` / `{ type: "Reproduced" }`. All other enums (`ValidationPhase`, `AgreementLevel`, etc.) use no tag → plain strings.
- `HarmonyRecord`, `ValidatorReputation`, and `ReproducibilityBadge` do **not** store self-reported timestamps. Timestamps are read from the Holochain Action. Do not add timestamp fields back.
- `CommitmentAnchor` now carries `commitment_hash: Vec<u8>` — the SHA-256 of the validator's serialised `ValidationAttestation` concatenated with a private nonce. At reveal time, verifying `SHA-256(msgpack(attestation) || nonce) == commitment_hash` closes the last-mover-advantage gap at the architectural level, not just the UX level.


