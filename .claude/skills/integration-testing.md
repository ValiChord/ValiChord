# ValiChord Integration Testing

## Critical: kill stale processes first

Holochain conductors and lair-keystore instances from previous runs stay alive after test failures or interruptions. They block ports and cause the next run to hang silently. Always kill them before running tests.

```bash
pkill -f holochain; pkill -f lair-keystore; sleep 2
```

If processes are stubborn:

```bash
pkill -9 -f holochain; pkill -9 -f lair-keystore; sleep 2
```

---

## PATH requirement

The `hc` CLI and `cargo` must be on PATH. Codespaces does not always add the cargo bin directory automatically:

```bash
export PATH="/home/codespace/.cargo/bin:$PATH"
```

Add this before any `cargo`, `hc`, or `npm test` command in a fresh shell.

---

## Build sequence

Always build in this order. Do NOT use `pack_dna.py` — it is broken and embeds the same DNA bytes for all four roles.

```bash
export PATH="/home/codespace/.cargo/bin:$PATH"
cd /workspaces/ValiChord/valichord

# 1. Compile all four WASM zomes
cargo build --target wasm32-unknown-unknown --release

# 2. Pack each DNA individually
hc dna pack dnas/attestation           -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc dna pack dnas/governance            -o workdir/governance.dna

# 3. Pack the hApp bundle
hc app pack . -o workdir/valichord.happ
```

The WASM compile step is slow (~5–10 minutes on Codespaces for a clean build). Subsequent builds that touch only coordinator zomes recompile only changed crates.

---

## Running the tests

```bash
cd /workspaces/ValiChord/valichord/tests
npm test
```

All test files run via the `npm test` script. To run a single file:

```bash
npx vitest run src/attestation.test.ts
```

---

## Timeout context

Each `runScenario` starts fresh Holochain conductors that JIT-compile all 8 WASM modules (~30 MB total). On Codespaces this takes approximately 60 seconds per player. All per-test timeouts are set to 900 000 ms (15 minutes) to accommodate this.

If a test times out, the cause is almost always slow conductor startup, not a logic error. Check:
1. Were stale processes killed before the run?
2. Is the machine under heavy load from a parallel build?

`DepMissingFromDht` errors in logs are a secondary symptom of slow gossip under load — they are transient and self-resolve as `dhtSync` completes. They are not the root cause of failures.

---

## Expected results

- **96 Tryorama tests pass, 1 Tryorama-skipped**
- Tryorama-skipped: `GoldReproducible badge (7 validators)` — 7 process conductors exhaust websocket connections in Codespaces (<16 GB RAM). **Covered by sweettest test 15** (`gold_badge_issued_with_seven_validators` in `sweettest_integration/tests/governance.rs`) — passes with in-process conductors.

---

## Full pre-run checklist

```bash
# 1. Kill stale processes
pkill -f holochain; pkill -f lair-keystore; sleep 2

# 2. Set PATH
export PATH="/home/codespace/.cargo/bin:$PATH"

# 3. Navigate to valichord workspace
cd /workspaces/ValiChord/valichord

# 4. Build (only needed if Rust source has changed)
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation           -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc dna pack dnas/governance            -o workdir/governance.dna
hc app pack . -o workdir/valichord.happ

# 5. Run tests
cd tests && npm test
```
