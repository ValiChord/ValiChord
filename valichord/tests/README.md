# ValiChord Tryorama Tests — DNA 3 (Attestation)

## Prerequisites

### 1. Rust WASM toolchain
```bash
rustup target add wasm32-unknown-unknown
```

### 2. Holochain CLI tools
```bash
cargo install holochain hc --locked
```

### 3. Node.js dependencies
```bash
cd tests && npm install
```

## Build and run

```bash
# From the valichord/ workspace root:

# Compile the two WASM zomes
cargo build --target wasm32-unknown-unknown --release

# Pack the Attestation DNA
hc dna pack dnas/attestation -o workdir/attestation.dna

# Pack the hApp bundle
hc app pack . -o workdir/valichord.happ

# Run tests
cd tests && npm test
```

## Test coverage

| # | Test | What it verifies |
|---|------|-----------------|
| 1a | Membrane proof accepted | Valid (≥64 byte) proof → genesis succeeds |
| 1b | Missing proof rejected | No proof → genesis_self_check fails |
| 1c | Short proof rejected | <64 byte proof → genesis_self_check fails |
| 2 | Full commit-reveal | Alice + Bob commit → PhaseMarker appears → both reveal → 2 attestations retrievable |
| 3 | DHT-poll transition | Eve misses signal, learns RevealOpen by polling get_current_phase() |
| 4a | Attestation immutability | update_attestation_for_test call rejected (function doesn't exist) |
| 4b | CommitmentAnchor immutability | delete_commitment_for_test call rejected (function doesn't exist) |

## Architecture notes

- `minimum_validators: 2` in test config (overrides the production value of 3/7).
- Membrane proof signature verification is a TODO (placeholder accepts all ≥64 byte proofs).
- Tests call `notify_commitment_sealed()` directly; in production this is called from DNA 2's `post_commit`.
