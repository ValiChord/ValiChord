<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Valichord%20logo-standard%20v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">
</div>

# ValiChord — Integration Tests

Two test suites cover the protocol end-to-end:

- **Tryorama** (TypeScript/Node) — live conductor tests against a compiled `.happ` bundle. Status: **94 pass, 1 skipped, 0 fail** (as of 2026-03-25)
- **Sweettest** (Rust/`cargo test`) — native HDK harness, faster, no bundle needed. Authoritative source: `valichord/sweettest_integration/tests/`

---

## Tryorama Integration Tests

Four test files, one per DNA. All tests exercise live Holochain conductors via
the compiled `workdir/valichord.happ` bundle.

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

### DNA 3 — `attestation.test.ts` (46 tests, 1 skipped)

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

> ¹ **Skipped:** requires 7 simultaneous Holochain conductors. Conductor
> processes crash under load in resource-constrained environments (codespace /
> CI with <16 GB RAM). The test logic is correct; run it on adequately
> resourced hardware.

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

Rust-native tests using `hdk`'s `sweettest` harness. Run directly via `cargo test` — no Node, no Tryorama. Each test file mirrors one DNA. Authoritative source: `valichord/sweettest_integration/tests/`.

### DNA 1 — `researcher_repository.rs` (10 tests)

All entries are private (single-agent source chain only). No DHT sync needed.

1. register_study + get_study
2. register_protocol + get_protocol_for_study
3. take_data_snapshot + get_snapshots_for_study
4. declare_deviation + get_deviations_for_study
5. compute_data_hash (SHA-256, deterministic, collision-resistant)
6. PreRegisteredProtocol immutability — no delete function in API
7. get_all_studies (empty + multi)
8. lock_researcher_result + get_locked_result
9. lock_researcher_result cross-DNA commitment publish
10. get_locked_result returns None for unknown request_ref

### DNA 2 — `validator_workspace.rs` (5 tests)

All entries are private (single-agent source chain only). No DHT sync needed.

1. receive_task + get_task
2. seal_private_attestation + get_private_attestation_for_task
3. get_all_tasks (empty + multi)
4. get_all_private_attestations — empty + multi
5. ValidatorPrivateAttestation immutability — no delete function in API

### DNA 3 — `attestation.rs` (15 tests)

1. submit_validation_request + get_validation_request + get_validation_request_for_data_hash
2. get_current_phase returns None before any commits
3. Two validators commit → phase transitions to RevealOpen
4. Full commit-reveal round (core 2-agent protocol)
5. get_attestations_for_request
6. ValidationAttestation immutability — no update/delete functions
7. CommitmentAnchor and PhaseMarker immutability — no update/delete functions
8. publish_validator_profile + get_validator_profile
9. claim_study + release_claim
10. COI rejection — same institution blocks claim
11. reclaim_abandoned_claim with timeout_secs=0
12. assess_difficulty + get_difficulty_assessment
13. link_agent_identity — self-link rejected
14. get_linked_agents returns empty when no identity links exist
15. DHT-poll phase transition (late-joining validator discovers RevealOpen)

### DNA 4 — `governance.rs` (14 tests)

1. check_and_create_harmony_record returns None when no attestations
2. Full 2-agent round — HarmonyRecord created on public DHT
3. check_and_create_harmony_record idempotent after record exists
4. Any participant can trigger finalisation (Bob, not the request submitter)
5. Premature finalisation (1 of 2 attestations) returns None
6. force_finalize_round — partial quorum + round_timeout_secs=0
7. GovernanceDecision key-gated — non-matching key rejected
8. update_validator_reputation — dev bypass allows any agent
9. get_harmony_records_by_discipline — empty + after round
10. get_badges_for_study — 2 validators, count < 3, no badge
11. get_badges_by_type — 3 validators, BronzeReproducible issued
12. Tier promotion — Provisional → Standard after 3 Reproduced rounds
13. Tier stays Provisional before 3 rounds
14. AI validator tier does not advance through completed rounds

### Security — `security.rs` (7 tests)

Covers protocol-gap fixes. Only guards exercisable at the coordinator/client layer are tested here.

- S1. Duplicate attestation guard — second submit_attestation rejected
- S2. Duplicate commitment guard — second notify_commitment_sealed rejected
- S3. Researcher commitment idempotency — second publish_researcher_commitment rejected
- S4a. reclaim_abandoned_claim: timeout below DNA floor → reclaim returns false
- S4b. reclaim_abandoned_claim: no floor (0) → timeout_secs=0 succeeds
- S5. force_finalize_round conservative abort when no ValidationRequest
- S6. reveal_researcher_result idempotency — second call rejected

---

## Remaining gaps

These are areas not yet covered by tests, ordered by value.

| Area | What to add | Notes |
|------|-------------|-------|
| DNA 3 — GoldReproducible (12.3) | 7 validators all Reproduced → GoldReproducible | Skipped; requires ≥16 GB RAM to run 7 conductors reliably |
| DNA 1 — lock_researcher_result | lock_researcher_result → LockedResult stored privately + ResearcherResultCommitment on DNA 3; get_locked_result returns private record | Cross-DNA call in test scenario required |
| DNA 3 — reveal_researcher_result | Correct metrics+nonce → ResearcherReveal on DHT; wrong nonce → error rejected; get_researcher_reveal returns verified reveal | Must call all validators notify_commitment_sealed first (gate: check_all_commitments_sealed) |
| DNA 4 — force_finalize_round success path | Round ≥ 7 days old + partial attestations → HarmonyRecord created | ROUND_TIMEOUT_SECS is hardcoded; cannot wind clock in Tryorama |

---

## Architecture notes

- `minimum_validators: 2` is set in test DNA properties (production default is 3–7). `check_all_commitments_sealed_inner` uses `num_validators_required` from the `ValidationRequest` entry (not the DNA-property `minimum_validators`) — phase opens when the study's own validator count has committed.
- `system_coordinator_key` is set to the test admin's base64 pubkey in governance DNA test properties. It gates `GovernanceDecision` writes only. `harmony_record_creator_key` no longer exists — `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation` are open to any participant. Empty string = dev/test bypass for `system_coordinator_key`.
- Membrane proof signature verification is real Ed25519: `coordinator init()` calls `verify_signature(issuer_key, sig, Vec<u8> of joining agent's 39-byte pubkey)`. Empty `authorized_joining_certificate_issuer` = dev/test bypass.
- Tests call `notify_commitment_sealed()` directly on the attestation DNA; in production this is triggered by DNA 2's `post_commit` (exercised by test 9.1). The function now takes `CommitmentSealedInput { request_ref, commitment_hash }` — pass the commitment hash alongside the request reference.
- `dhtSync` is required between agents for any multi-player read assertion.
- ExternalHash in JS: use `hashFrom32AndType(core32, HoloHashType.External)` — never `new Uint8Array(39).fill(byte)` (DHT location bytes must be a valid blake2b checksum).
- `Discipline` and `AttestationOutcome` use `#[serde(tag="type", content="content")]` (adjacent tagging) → `{ type: "ComputationalBiology" }` / `{ type: "Reproduced" }`. All other enums (`ValidationPhase`, `AgreementLevel`, etc.) use no tag → plain strings.
- `HarmonyRecord`, `ValidatorReputation`, and `ReproducibilityBadge` do **not** store self-reported timestamps. Timestamps are read from the Holochain Action. Do not add timestamp fields back.
- `CommitmentAnchor` now carries `commitment_hash: Vec<u8>` — the SHA-256 of the validator's serialised `ValidationAttestation` concatenated with a private nonce. At reveal time, verifying `SHA-256(msgpack(attestation) || nonce) == commitment_hash` closes the last-mover-advantage gap at the architectural level, not just the UX level.


