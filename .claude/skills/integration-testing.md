# ValiChord Integration Testing

Integration tests are **sweettest** (Rust, in-process conductors) in `valichord/sweettest_integration/`. The old Tryorama suite (`valichord/tests/`, `npm test`) was retired and deleted on 2026-08-03 — if you see `cd tests && npm test` anywhere, it is stale. See `TESTING.md` for the current counts and the full coverage inventory.

## Critical: kill stale processes first

Holochain conductors and lair-keystore instances from previous runs stay alive after test failures or interruptions. They block ports and cause the next run to fail or hang for reasons unrelated to the code.

```bash
pkill -x holochain; pkill -x lair-keystore; sleep 2
```

Use `-x`, not `-f`: `-f` also matches the shell running the command and kills it. If processes are stubborn, `pkill -9 -x holochain; pkill -9 -x lair-keystore`.

---

## PATH requirement

`hc` and `cargo` must be on PATH. Codespaces does not always add the cargo bin directory automatically:

```bash
export PATH="/home/codespace/.cargo/bin:$PATH"
```

---

## Build sequence

Build and pack in this order. Do NOT use `pack_dna.py` — it is broken and embeds the same DNA bytes for all four roles.

```bash
export PATH="/home/codespace/.cargo/bin:$PATH"
cd /workspaces/ValiChord/valichord

# 1. Compile all WASM zomes
cargo build --target wasm32-unknown-unknown --release

# 2. Pack each DNA individually
hc dna pack dnas/attestation           -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc dna pack dnas/governance            -o workdir/governance.dna

# 3. Pack the hApp bundle
hc app pack . -o workdir/valichord.happ
```

A clean WASM build is slow (minutes on Codespaces). Later builds that touch only coordinator zomes recompile only the changed crates.

---

## Running the tests

Always use the wrapper script, not a hand-rolled `cargo test ... | grep -v`. Under memory pressure SQLCipher ENOMEM spam can land on a result line and a filter deletes the result; the script keeps the raw log and cross-checks the result lines against cargo's own summary.

```bash
cd /workspaces/ValiChord/valichord
./run-sweettest.sh attestation
./run-sweettest.sh governance
./run-sweettest.sh researcher_repository
./run-sweettest.sh validator_workspace
./run-sweettest.sh security
./run-sweettest.sh membrane_proof
./run-sweettest.sh governance silver_badge     # optional name filter
```

The immutability tripwire and forgery tests (`immutability_tripwire`, `harmony_record_forgery`, `validator_tier_forgery`, `reveal_phase_forgery`, `supersession_forgery`) need a separate build with the `test_utils` feature, because no production coordinator exposes `update_entry`/`delete_entry` or a way to write a forged entry:

```bash
cd /workspaces/ValiChord/valichord && ./build-test-dnas.sh
VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh immutability_tripwire
VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh harmony_record_forgery
VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh validator_tier_forgery
VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh reveal_phase_forgery
VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh supersession_forgery
```

CI (`.github/workflows/tests.yml`) runs the six standard suites as parallel matrix legs plus a `tripwire` job that runs all five of these binaries.

---

## If a test times out or hangs

Each sweettest starts fresh in-process conductors that JIT-compile the WASM modules, which is slow on a small machine. A timeout is almost always slow startup or memory pressure, not a logic error. Check:
1. Were stale processes killed before the run?
2. Is the machine under heavy load from a parallel build?

`DepMissingFromDht` errors in logs are a secondary symptom of slow gossip under load — transient, and not the root cause of a failure.

---

## Expected results

Counts change; do not trust a number written here. Read the totals in `TESTING.md` (counted from source) or the latest CI run. No tests are skipped. The 7-validator Gold badge case is covered by `gold_badge_issued_with_seven_validators` in `sweettest_integration/tests/governance.rs`.

---

## Full pre-run checklist

```bash
pkill -x holochain; pkill -x lair-keystore; sleep 2
export PATH="/home/codespace/.cargo/bin:$PATH"
cd /workspaces/ValiChord/valichord

# Build (only needed if Rust source has changed)
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation           -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc dna pack dnas/governance            -o workdir/governance.dna
hc app pack . -o workdir/valichord.happ

# Run
./run-sweettest.sh governance
```
