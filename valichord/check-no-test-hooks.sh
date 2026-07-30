#!/usr/bin/env bash
#
# CI guard: the committed production bundles must NOT contain the test-only
# immutability tripwire externs.
#
# The tripwire hooks live behind `#[cfg(feature = "test_utils")]` and are built
# into target-test/ + workdir-test/ by build-test-dnas.sh. If a production hApp
# is ever packed from a test-feature build, the exported symbol names leak into
# the wasm — this catches that before it ships.
#
# Exit 0 = clean. Exit 1 = a production bundle carries test hooks.
set -uo pipefail
cd "$(dirname "$0")"

# The wasm export names are the extern fn names.
NEEDLE='test_force_update'
FAIL=0

check() {
  local f="$1"
  [ -f "$f" ] || { echo "  skip (absent): $f"; return; }
  if grep -qa "$NEEDLE" "$f"; then
    echo "  ✗ FAIL: $f contains '$NEEDLE' — packed from a test_utils build"
    FAIL=1
  else
    echo "  ✓ clean: $f"
  fi
}

echo "Checking committed production bundles for test-only hooks..."
check workdir/valichord.happ
for d in attestation researcher_repository validator_workspace governance; do
  check "workdir/$d.dna"
done

echo
if [ "$FAIL" = 1 ]; then
  echo "FAILED — a production bundle was packed from a --features test_utils build."
  echo "Rebuild without the feature:  cargo build --target wasm32-unknown-unknown --release"
  echo "then repack per CLAUDE.md, and commit the clean bundles."
  exit 1
fi
echo "PASS — no test-only hooks in any production bundle."
