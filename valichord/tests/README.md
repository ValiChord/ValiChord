# ValiChord — Tryorama Integration Tests

**Status: 80 pass, 1 skipped, 0 fail** (as of 2026-03-14)

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

### DNA 3 — `attestation.test.ts` (37 tests, 1 skipped)

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
| 13.1 | 2 validators both FailedToReproduce → FailedReproduction badge issued | PASS |
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

> ¹ **Skipped:** requires 7 simultaneous Holochain conductors. Conductor
> processes crash under load in resource-constrained environments (codespace /
> CI with <16 GB RAM). The test logic is correct; run it on adequately
> resourced hardware.

### DNA 4 — `governance.test.ts` (22 tests)

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

---

## Remaining gaps

These are areas not yet covered by tests, ordered by value.

| Area | What to add | Notes |
|------|-------------|-------|
| DNA 3 — GoldReproducible (12.3) | 7 validators all Reproduced → GoldReproducible | Skipped; requires ≥16 GB RAM to run 7 conductors reliably |

---

## Architecture notes

- `minimum_validators: 2` is set in test DNA properties (production default is 3–7).
- `system_coordinator_key` is set to the test admin's base64 pubkey in governance DNA
  test properties. It gates `GovernanceDecision` writes only. `harmony_record_creator_key`
  no longer exists — `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation`
  are open to any participant. Empty string = dev/test bypass for `system_coordinator_key`.
- `submit_attestation` (DNA 3) automatically fires a same-agent cross-DNA call to
  `check_and_create_harmony_record` (DNA 4) after writing each attestation. The last
  validator to reveal triggers HarmonyRecord creation without a central coordinator node.
- Membrane proof signature verification is real Ed25519: `coordinator init()` calls `verify_signature(issuer_key, sig, Vec<u8> of joining agent's 39-byte pubkey)`. Empty `authorized_joining_certificate_issuer` = dev/test bypass.
- Tests call `notify_commitment_sealed()` directly on the attestation DNA; in production
  this is triggered by DNA 2's `post_commit` (exercised by test 9.1).
- `dhtSync` is required between agents for any multi-player read assertion.
- ExternalHash in JS: use `hashFrom32AndType(core32, HoloHashType.External)` — never
  `new Uint8Array(39).fill(byte)` (DHT location bytes must be a valid blake2b checksum).
- `Discipline` and `AttestationOutcome` use `#[serde(tag="type", content="content")]`
  (adjacent tagging) → `{ type: "ComputationalBiology" }` / `{ type: "Reproduced" }`.
  All other enums (`ValidationPhase`, `AgreementLevel`, etc.) use no tag → plain strings.
- `HarmonyRecord`, `ValidatorReputation`, and `ReproducibilityBadge` do **not** store
  self-reported timestamps (`created_at_secs`, `last_updated_secs`, `issued_at_secs`).
  Timestamps are read from the Holochain Action, which is tamper-evident. Do not add
  timestamp fields back — they would be falsifiable.
- `ReproducibilityBadge.issued_to` is the researcher who submitted the study, resolved
  via a cross-DNA call to `attestation_coordinator::get_validation_request_for_data_hash`.
  It is NOT the first participating validator.
- `get_all_tasks` and `get_all_private_attestations` (DNA 2), `get_all_studies`
  (DNA 1), and `get_all_governance_decisions` (DNA 4) all use type-safe
  deserialization to filter source-chain entries — not hardcoded `ZomeIndex`/
  `EntryDefIndex` values. Do not reintroduce hardcoded indices.
- `BadgePath` link type (DNA 4) is written at badge issuance in
  `check_and_create_harmony_record` and read by `get_badges_by_type`. It indexes
  badges by type for cross-study analytics (e.g. "how many Bronze badges this quarter").
- `AllDecisions` link type (DNA 4) is written by `create_governance_decision` and
  read by `get_all_governance_decisions` via a "decisions.all" path anchor.
- `InstitutionPath` link type (DNA 3) is written by `publish_validator_profile` under
  "institution.{institution}" paths and read by `get_validators_for_institution`.
  Used for conflict-of-interest detection in validator assignment.
- `DisciplinePath` link type (DNA 3) is written by `submit_attestation` under
  "attestations.{discipline_tag}" paths and read by `get_attestations_for_discipline`.
  Provides cross-study analytics on attestation outcomes by discipline.
- `StudyClaim` (DNA 3) — validators self-assign via `claim_study(request_ref)`.
  Two link indexes are written: `RequestToClaim` (base = request_ref) and `ValidatorToClaim`
  (base = agent pubkey). The coordinator enforces capacity and duplicate checks;
  validate() enforces COI (same institution as researcher → invalid).
  `release_claim(request_ref)` deletes both links; the StudyClaim entry remains as audit.
  Empty `researcher_institution` or `validator_institution` bypasses the COI check.
