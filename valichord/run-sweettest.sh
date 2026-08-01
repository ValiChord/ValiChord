#!/usr/bin/env bash
#
# Run a sweettest suite and report its results without being able to lie about them.
#
#   ./run-sweettest.sh security
#   ./run-sweettest.sh governance silver_badge          # optional name filter
#   VALICHORD_DNA_DIR=../workdir-test ./run-sweettest.sh immutability_tripwire
#
# WHY THIS EXISTS
# ---------------
# Twice now a hand-rolled `cargo test ... | grep -v sqlcipher_mlock` has DELETED A
# TEST'S RESULT LINE. Under memory pressure SQLCipher emits ENOMEM spam that can land
# on the same line as `test <name> ... ok`, so an exclusive line filter drops the
# result along with the noise. Both times the summary still said "5 passed" while only
# four test names were greppable, and both times the discrepancy was caught by eye —
# which is not a control, it is luck.
#
# The mitigation recorded in docs/Holochain_complete.md 44.7 was a note asking a human
# to remember. That is why it recurred. This script is the fix: the rule is executable.
#
# THREE PROPERTIES THAT MAKE IT UNABLE TO SILENTLY MISREPORT
# ----------------------------------------------------------
# 1. The raw log is written to disk UNFILTERED and kept. Whatever is extracted, the
#    ground truth is still on disk to check against.
# 2. Extraction is INCLUSIVE ("find the result lines") rather than EXCLUSIVE ("drop the
#    noisy lines"), and the pattern is UNANCHORED, so it still matches when junk has
#    been prepended to a result line. An inclusive filter cannot delete a line it is
#    looking for.
# 3. It CROSS-CHECKS the number of extracted per-test lines against the count in
#    cargo's own summary, and fails loudly if they disagree. This is the part that
#    would have caught both incidents automatically. A count that matches is evidence;
#    a summary read on its own never was.
#
# Note it deliberately does NOT suppress the ENOMEM spam. Suppression is what caused
# the problem. The noise is harmless in a file.

set -uo pipefail

if [ $# -lt 1 ]; then
    echo "usage: $0 <suite> [name-filter]" >&2
    echo "  e.g. $0 security" >&2
    echo "       $0 governance silver_badge" >&2
    exit 2
fi

SUITE="$1"
FILTER="${2:-}"

cd "$(dirname "$0")/sweettest_integration" || exit 1

# SWEETTEST_REPLAY_LOG analyses an existing log instead of running cargo. It exists so
# the cross-check below can be NEGATIVE-CONTROLLED: point it at a log with a result
# line deliberately removed and this script must fail. A guard nobody has watched fail
# is exactly the class of thing this script was written to stop trusting.
if [ -n "${SWEETTEST_REPLAY_LOG:-}" ]; then
    LOG="$SWEETTEST_REPLAY_LOG"
    CARGO_EXIT=0
    echo "REPLAY MODE — analysing $LOG, not running tests"
    echo
else
    LOG="$(mktemp "/tmp/sweettest-${SUITE}-XXXXXX.log")"

    # Stale conductors from a previous run will make this one fail for reasons that have
    # nothing to do with the code. -x not -f: -f matches this script's own command line
    # and SIGTERMs the shell running it.
    pkill -x holochain 2>/dev/null
    pkill -x lair-keystore 2>/dev/null
    sleep 2

    echo "suite:   $SUITE"
    [ -n "$FILTER" ] && echo "filter:  $FILTER"
    echo "dna dir: ${VALICHORD_DNA_DIR:-../workdir (default)}"
    echo "raw log: $LOG"
    echo

    # Unfiltered, both streams, straight to disk. Nothing is dropped here by design.
    if [ -n "$FILTER" ]; then
        cargo test --test "$SUITE" "$FILTER" -- --test-threads=1 > "$LOG" 2>&1
    else
        cargo test --test "$SUITE" -- --test-threads=1 > "$LOG" 2>&1
    fi
    CARGO_EXIT=$?
fi

# Unanchored and inclusive: matches "test foo ... ok" even with junk prepended.
PER_TEST=$(grep -aoE "test [A-Za-z0-9_:]+ \.\.\. (ok|FAILED|ignored)" "$LOG" | sort -u)
SUMMARY=$(grep -aoE "test result: [A-Za-z]+\. [0-9]+ passed; [0-9]+ failed; [0-9]+ ignored" "$LOG" | tail -1)

echo "$PER_TEST"
echo
echo "${SUMMARY:-(no summary line found)}"

if [ -z "$SUMMARY" ]; then
    echo
    echo "FAIL: cargo produced no summary line. The run did not complete —"
    echo "      a build error, a panic outside a test, or a kill. See $LOG"
    exit 1
fi

# The cross-check. Named results found must equal passed+failed+ignored.
FOUND=$(printf '%s\n' "$PER_TEST" | grep -ac . )
CLAIMED=$(( $(sed -E 's/.* ([0-9]+) passed.*/\1/' <<<"$SUMMARY") \
          + $(sed -E 's/.* ([0-9]+) failed.*/\1/' <<<"$SUMMARY") \
          + $(sed -E 's/.* ([0-9]+) ignored.*/\1/' <<<"$SUMMARY") ))

echo
if [ "$FOUND" -ne "$CLAIMED" ]; then
    echo "FAIL: result lines found ($FOUND) != summary count ($CLAIMED)."
    echo "      A test's result line is missing from the log — most likely eaten by"
    echo "      interleaved output. Do NOT trust the summary. Re-run the missing test"
    echo "      by name and read its result directly:"
    echo "        $0 $SUITE <test_name>"
    echo "      Raw log kept at: $LOG"
    exit 1
fi
echo "cross-check ok: $FOUND named results == $CLAIMED in summary"

if [ "$CARGO_EXIT" -ne 0 ]; then
    echo "FAIL: cargo exited $CARGO_EXIT. Raw log: $LOG"
    exit "$CARGO_EXIT"
fi

echo "PASS. Raw log: $LOG"
