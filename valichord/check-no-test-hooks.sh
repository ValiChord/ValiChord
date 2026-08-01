#!/usr/bin/env bash
#
# CI guard: the committed production bundles must NOT contain the test-only
# immutability tripwire externs.
#
# The tripwire hooks live behind `#[cfg(feature = "test_utils")]` and are built
# into target-test/ + workdir-test/ by build-test-dnas.sh. If a production hApp
# is ever packed from a test-feature build, the exported symbol names land in
# the wasm — this catches that before it ships.
#
# ─────────────────────────────────────────────────────────────────────────────
# WHY THIS DECOMPRESSES INSTEAD OF GREPPING DIRECTLY
#
# The first version of this script ran `grep -a` straight at the bundle files
# and always reported "clean" — including for workdir-test/ bundles that
# definitely contain the hooks. It was a false-negative machine: it could not
# fail. Holochain bundles are COMPRESSED, so the plaintext symbol names are
# never present in the raw bytes.
#
#   *.dna   = a single gzip stream            (needle visible after 1 decompress)
#   *.happ  = gzip -> msgpack -> nested gzip  (needle visible after 2)
#
# Hence the recursive scan below. If you change this script, re-run the
# negative control at the bottom of this comment — a guard that cannot fail is
# worse than no guard, because it manufactures false confidence:
#
#   ./check-no-test-hooks.sh                      # expect PASS (exit 0)
#   NEEDLE_SCAN_DIR=workdir-test ./check-no-test-hooks.sh   # expect FAIL (exit 1)
# ─────────────────────────────────────────────────────────────────────────────
#
# Exit 0 = clean. Exit 1 = a bundle carries test hooks.
set -uo pipefail
cd "$(dirname "$0")"

# Matches the `test_force_` PREFIX, not a specific hook name.
#
# This was `test_force_update` until 2026-08-01, when delete tripwires were added
# and the guard would silently have ignored `test_force_delete_entry` — a guard
# that only catches the hooks that existed when it was written is a guard with an
# expiry date nobody is told about. The prefix is the naming convention, so any
# future hook following it is covered on the day it is written rather than the day
# somebody remembers to update this line.
#
# Verified to have no legitimate hits: `test_force_` appears nowhere in production
# source, only in the #[cfg(feature = "test_utils")] blocks.
NEEDLE="${NEEDLE:-test_force_}"
DIR="${NEEDLE_SCAN_DIR:-workdir}"

echo "Scanning '$DIR' for test-only hooks (needle: '$NEEDLE')..."

python3 - "$DIR" "$NEEDLE" <<'PY'
import sys, os, zlib, glob

scan_dir, needle = sys.argv[1], sys.argv[2].encode()
GZIP_MAGIC = b"\x1f\x8b\x08"
MAX_DEPTH = 4

def gunzip_members(buf):
    """Yield every gzip member decompressible from anywhere in buf."""
    start = 0
    while True:
        i = buf.find(GZIP_MAGIC, start)
        if i == -1:
            return
        try:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            out = d.decompress(buf[i:])
            if out:
                yield out
        except zlib.error:
            pass
        start = i + 1

def contains(buf, depth=0):
    if needle in buf:
        return True
    if depth >= MAX_DEPTH:
        return False
    for member in gunzip_members(buf):
        if contains(member, depth + 1):
            return True
    return False

targets = sorted(glob.glob(os.path.join(scan_dir, "*.happ"))
                 + glob.glob(os.path.join(scan_dir, "*.dna")))
if not targets:
    print(f"  ERROR: no .dna/.happ bundles found in '{scan_dir}'")
    sys.exit(2)

failed = []
for path in targets:
    with open(path, "rb") as fh:
        data = fh.read()
    if contains(data):
        print(f"  X FAIL: {path} contains '{needle.decode()}'")
        failed.append(path)
    else:
        print(f"  ok clean: {path}")

print()
if failed:
    print("FAILED - bundle(s) packed from a --features test_utils build:")
    for p in failed:
        print(f"  {p}")
    print()
    print("Rebuild without the feature:")
    print("  cargo build --target wasm32-unknown-unknown --release")
    print("then repack per CLAUDE.md and commit the clean bundles.")
    sys.exit(1)

print(f"PASS - no test-only hooks in any bundle under '{scan_dir}'.")
PY
