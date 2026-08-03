#!/usr/bin/env bash
#
# Build + pack the TEST DNAs used by the immutability tripwire tests.
#
#   ./build-test-dnas.sh
#   cd sweettest_integration && VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire
#
# WHAT THIS PRODUCES, AND WHY IT IS SAFE
# --------------------------------------
# The tripwire tests must issue an Update against a committed entry to prove the
# integrity zome rejects it. No production coordinator exposes `update_entry`, so
# four coordinators carry `#[cfg(feature = "test_utils")]` externs that do.
#
# Those externs must never reach a production hApp. This script keeps them
# quarantined by construction:
#
#   * the feature build goes to  target-test/  (a SEPARATE target dir), so it can
#     never overwrite the production wasm in  target/
#   * output is packed to        workdir-test/ (NOT workdir/), so it can never
#     overwrite the committed production bundles
#   * the test manifests in      test-dnas/*/dna.yaml  point their INTEGRITY zome
#     at the production build in target/ — identical bytes to the shipped DNA —
#     and only their COORDINATOR at target-test/
#
# That last point is what makes the tests meaningful: the integrity zome under
# test is byte-identical to the one we ship. Only the calling surface differs.
#
# `check-no-test-hooks.sh` enforces the separation in CI.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/home/codespace/.cargo/bin:$PATH"

FEATURES="attestation_coordinator/test_utils,\
validator_workspace_coordinator/test_utils,\
governance_coordinator/test_utils,\
researcher_repository_coordinator/test_utils"

echo "==> [1/3] production build (integrity zomes + governance) -> target/"
cargo build --target wasm32-unknown-unknown --release

echo "==> [2/3] test-feature build (coordinators only) -> target-test/"
cargo build --target wasm32-unknown-unknown --release \
  --target-dir target-test --features "$FEATURES"

# HC_BIN overrides the packing tool, mirroring HOLOCHAIN_BIN in dev.sh and the
# e2e harness. It is REQUIRED on the v0.7.0 branch: `hc` on PATH in the
# Codespace is deliberately still 0.6.2, and a DNA packed by 0.6.2 is not what
# the 0.7 sweettest conductor loads from workdir/. Packing with the wrong
# version produces bundles that differ from the production ones for a reason
# that has nothing to do with the code under test.
HC_BIN="${HC_BIN:-hc}"

echo "==> [3/3] packing test DNAs -> workdir-test/  (using: $("$HC_BIN" --version))"
mkdir -p workdir-test
for d in attestation researcher_repository validator_workspace governance; do
  "$HC_BIN" dna pack "test-dnas/$d" -o "workdir-test/$d.dna"
done

echo
echo "Done. Test DNAs in workdir-test/ (production workdir/ untouched):"
ls -la workdir-test/*.dna
echo
echo "Run the tripwire tests with:"
echo "  cd sweettest_integration && VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire"
