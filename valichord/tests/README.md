# ValiChord — Tryorama Integration Tests

**Status: 44 / 44 tests passing** (as of 2026-03-09)

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

### DNA 3 — `attestation.test.ts` (17 tests)

| ID  | Test name | Status |
|-----|-----------|--------|
| 1.1 | agent with valid membrane proof (≥64 bytes) can join | PASS |
| 1.2 | agent with no membrane proof is rejected at genesis_self_check | PASS |
| 1.3 | agent with too-short membrane proof (<64 bytes) is rejected | PASS |
| 2.1 | two validators commit, phase opens, both reveal, attestations retrievable | PASS |
| 3.1 | late-joining validator discovers RevealOpen by polling, not via signal | PASS |
| 4.1 | attempting to update a ValidationAttestation is rejected | PASS |
| 4.2 | attempting to delete a CommitmentAnchor is rejected | PASS |
| 5.1 | published validator profile is retrievable by agent public key | PASS |
| 5.2 | get_validator_profile returns null when no profile published | PASS |
| 5.3 | assess_difficulty returns an ActionHash; get_difficulty_assessment is a stub | PASS |
| 6.1 | submitted ValidationRequest is retrievable by its ActionHash | PASS |
| 6.2 | get_validation_request returns null for an unknown ActionHash | PASS |
| 7.1 | attempting to update a CommitmentAnchor is rejected (no update fn in API) | PASS |
| 7.2 | attempting to update a PhaseMarker is rejected (no update fn in API) | PASS |
| 7.3 | attempting to delete a PhaseMarker is rejected (no delete fn in API) | PASS |
| 8.1 | get_pending_requests_for_discipline returns submitted request for matching discipline | PASS |
| 8.2 | get_pending_requests_for_discipline returns empty for a different discipline | PASS |

### DNA 4 — `governance.test.ts` (11 tests)

| ID  | Test name | Status |
|-----|-----------|--------|
| 1.1 | two calls for the same request_ref with no attestations both return null | PASS |
| 1.2 | second call short-circuits when HarmonyRecord already exists | PASS |
| 2.1 | HarmonyRecord creation from non-creator key is rejected by validate() | PASS |
| 2.2 | agent key does not equal placeholder key (validate() precondition) | PASS |
| 3.1 | researcher → request → validator attestations → HarmonyRecord on DHT (end-to-end) | PASS |
| 4.1 | reputation update from non-coordinator key is rejected by validate() | PASS |
| 4.2 | reputation update from system_coordinator_key is accepted | PASS |
| 5.1 | get_harmony_records_by_discipline returns the record after creation | PASS |
| 5.2 | get_badges_for_study returns empty when validator count < 3 | PASS |
| 5.3 | get_harmony_records_by_discipline returns empty array when no records exist | PASS |
| 6.1 | get_badges_for_study returns BronzeReproducible when 3 validators all Reproduced | PASS |

---

## Not yet tested — candidate additions

These are gaps identified against the current Rust API. Ordered roughly by value.

### High value

| Area | What to add | Notes |
|------|-------------|-------|
| DNA 4 — badge thresholds | Silver (≥5 validators, ExactMatch) and Gold (≥7 validators, ExactMatch) | Requires multi-player scenarios; logic is already in `evaluate_badge` |
| DNA 4 — FailedReproduction badge | `get_badges_for_study` when outcome is Divergent or UnableToAssess | Exercises the negative outcome path through `evaluate_badge` |
| DNA 4 — `get_validator_reputation` | Retrieve reputation by AgentPubKey after `update_validator_reputation` | Function exists, not yet exercised by any test |
| DNA 3 — single-validator commit | `notify_commitment_sealed` with only 1 validator (< minimum) → phase stays None | Negative boundary for the commit-reveal threshold |
| DNA 2 — privacy guarantee | Verify private attestation is NOT readable from a different agent's cell | Core privacy property; `get_private_attestation_for_task` returns None across agents |

### Medium value

| Area | What to add | Notes |
|------|-------------|-------|
| DNA 4 — mixed outcomes | Some Reproduced, some Divergent — verify correct badge/outcome resolution | Tests the blended outcome path in `check_and_create_harmony_record` |
| DNA 1 — study immutability | No update or delete function exists → call rejected | Mirrors DNA 3 immutability pattern |
| DNA 3 — `check_all_commitments_sealed` direct call | Returns false before threshold, true at threshold | Already called internally; worth a direct read test |
| DNA 2 — `get_all_tasks` with multiple tasks | Receive 3 tasks, verify all 3 returned | Current test only checks a single-task list |

### Low value / deferred

| Area | Notes |
|------|-------|
| DNA 3 — `get_validators_for_discipline` | Currently a stub returning `[]`; only worth testing once implemented |
| DNA 3 — `get_difficulty_assessment` positive path | Currently a stub returning `None`; only worth testing once implemented |
| DNA 3 — real membrane proof signature verification | Placeholder accepts all ≥64 byte proofs; test when real crypto is wired in |
| DNA 2 — cross-DNA post_commit (seal → notify) | Holochain constraint: `post_commit` MUST NOT write data — cross-DNA entry writes are silently dropped. Behaviour proven implicitly by test 3.1 (direct `notify_commitment_sealed` call). An isolated post_commit test cannot pass with current Holochain. |

---

## Architecture notes

- `minimum_validators: 2` in test DNA properties (production default is 3 or 7).
- Membrane proof signature verification is a placeholder (accepts all ≥64 byte proofs).
- Tests call `notify_commitment_sealed()` directly; in production this is triggered
  from DNA 2's `post_commit` — but see the cross-DNA constraint note above.
- `dhtSync` is required between agents for any multi-player read assertion.
- `scenario.addPlayers(n)` + `scenario.installAppsForPlayers(configs, players)` is
  used when the governance DNA properties must embed a known agent key (baked at
  install time). Single-DNA tests use the simpler `addPlayersWithApps`.
- ExternalHash in JS: use `hashFrom32AndType(core32, HoloHashType.External)` — never
  `new Uint8Array(39).fill(byte)` (DHT location bytes must be a valid blake2b checksum).
