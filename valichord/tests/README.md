# ValiChord — Tryorama Integration Tests

**Status: 50 pass, 1 skipped, 0 fail** (as of 2026-03-10)

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

### DNA 1 — `researcher_repository.test.ts` (11 tests)

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

### DNA 2 — `validator_workspace.test.ts` (5 tests)

| ID  | Test name | Status |
|-----|-----------|--------|
| 1.1 | received task is retrievable by its ActionHash | PASS |
| 1.2 | get_task returns null for an unknown ActionHash | PASS |
| 2.1 | sealed private attestation is retrievable via its parent task | PASS |
| 2.2 | get_private_attestation_for_task returns null before any attestation | PASS |
| 3.1 | get_all_tasks returns all received tasks from the local source chain | PASS |

### DNA 3 — `attestation.test.ts` (24 tests, 1 skipped)

| ID   | Test name | Status |
|------|-----------|--------|
| 1.1  | agent with valid membrane proof (≥64 bytes) can join | PASS |
| 1.2  | agent with no membrane proof is rejected at genesis_self_check | PASS |
| 1.3  | agent with too-short membrane proof (<64 bytes) is rejected | PASS |
| 2.1  | two validators commit, phase opens, both reveal, attestations retrievable | PASS |
| 3.1  | late-joining validator discovers RevealOpen by polling, not via signal | PASS |
| 4.1  | attempting to update a ValidationAttestation is rejected | PASS |
| 4.2  | attempting to delete a CommitmentAnchor is rejected | PASS |
| 5.1  | published validator profile is retrievable by agent public key | PASS |
| 5.2  | get_validator_profile returns null when no profile published | PASS |
| 5.3  | assess_difficulty returns an ActionHash; get_difficulty_assessment is a stub | PASS |
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
| 12.1 | 5 validators all Reproduced → SilverReproducible badge issued | PASS |
| 12.2 | 7 validators all Reproduced → GoldReproducible badge issued | SKIP¹ |
| 13.1 | 2 validators both FailedToReproduce → FailedReproduction badge issued | PASS |
| 14.1 | update_validator_reputation then get_validator_reputation returns the record | PASS |

> ¹ **Skipped:** requires 7 simultaneous Holochain conductors. Conductor
> processes crash under load in resource-constrained environments (codespace /
> CI with <16 GB RAM). The test logic is correct; run it on adequately
> resourced hardware.

### DNA 4 — `governance.test.ts` (11 tests)

| ID  | Test name | Status |
|-----|-----------|--------|
| 1.1 | two calls for the same request_ref with no attestations both return null | PASS |
| 1.2 | second call short-circuits when HarmonyRecord already exists | PASS |
| 2.1 | HarmonyRecord creation from non-creator key is rejected by validate() | PASS |
| 2.2 | agent key does not equal placeholder key (validate() precondition) | PASS |
| 3.1 | researcher → request → validator attestations → HarmonyRecord on DHT | PASS |
| 4.1 | reputation update from non-coordinator key is rejected by validate() | PASS |
| 4.2 | reputation update from system_coordinator_key is accepted | PASS |
| 5.1 | get_harmony_records_by_discipline returns the record after creation | PASS |
| 5.2 | get_harmony_records_by_discipline returns empty array when no records exist | PASS |
| 5.3 | get_badges_for_study returns empty when validator count < 3 | PASS |
| 6.1 | get_badges_for_study returns BronzeReproducible when 3 validators all Reproduced | PASS |

---

## Remaining gaps

These are areas not yet covered by tests, ordered by value.

| Area | What to add | Notes |
|------|-------------|-------|
| DNA 3 — `get_validators_for_discipline` | Returns non-empty list after `publish_validator_profile` | Currently a stub returning `[]`; worth testing once implemented |
| DNA 3 — `get_difficulty_assessment` positive path | Returns the assessment written by `assess_difficulty` | Currently a stub returning `None` |
| DNA 3 — real membrane proof signature verification | Rejects a proof not signed by the authorized issuer key | Placeholder accepts all ≥64-byte proofs; test when real crypto is wired in |
| DNA 4 — mixed-outcome badge | Some Reproduced, some Divergent → correct AgreementLevel + badge | Tests the blended outcome path in `check_and_create_harmony_record` |
| DNA 4 — GoldReproducible (12.2) | 7 validators all Reproduced → GoldReproducible | Skipped; requires ≥16 GB RAM to run 7 conductors reliably |
| DNA 2 — `get_all_tasks` with multiple tasks | Receive 3 tasks, verify all 3 returned | Current test checks only a single-task list |

---

## Architecture notes

- `minimum_validators: 2` is set in test DNA properties (production default is 3–7).
- `harmony_record_creator_key` and `system_coordinator_key` are set to `""` in
  governance DNA test properties — the empty-string bypass in `governance_integrity`
  allows any agent to write governance entries in test/dev mode.
- Membrane proof signature verification is a placeholder (accepts all ≥64-byte proofs).
- Tests call `notify_commitment_sealed()` directly on the attestation DNA; in production
  this is triggered by DNA 2's `post_commit` (exercised by test 9.1).
- `dhtSync` is required between agents for any multi-player read assertion.
- ExternalHash in JS: use `hashFrom32AndType(core32, HoloHashType.External)` — never
  `new Uint8Array(39).fill(byte)` (DHT location bytes must be a valid blake2b checksum).
- `Discipline` and `AttestationOutcome` use `#[serde(tag="type", content="content")]`
  (adjacent tagging) → `{ type: "ComputationalBiology" }` / `{ type: "Reproduced" }`.
  All other enums (`ValidationPhase`, `AgreementLevel`, etc.) use no tag → plain strings.
