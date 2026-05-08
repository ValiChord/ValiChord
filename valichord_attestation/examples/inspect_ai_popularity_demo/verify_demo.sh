#!/usr/bin/env bash
# verify_demo.sh — one-step protocol verification for the inspect_ai Popularity demo.
#
# Builds bundle.json in fixture mode (no download required), then runs the
# challenge-response walkthrough.  Both steps must succeed; any failure
# exits non-zero.
#
# Overrides:
#   FIXTURE_DATE  — value passed to --generated-at
#                   (default: "2026-05-07T00:00:00+00:00", matches committed bundle)
#
# To verify against the real .eval log instead:
#   bash download_eval.sh
#   python build_bundle.py --eval-path ./popularity.eval
#   python challenge_response_demo.py

set -euo pipefail

FIXTURE_DATE="${FIXTURE_DATE:-2026-05-07T00:00:00+00:00}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Building bundle (fixture mode, generated-at: $FIXTURE_DATE)..."
python "$SCRIPT_DIR/build_bundle.py" --fixture --generated-at "$FIXTURE_DATE" \
  || { echo "ERROR: build_bundle.py failed"; exit 1; }

echo "==> Running challenge-response demo..."
python "$SCRIPT_DIR/challenge_response_demo.py" \
  || { echo "ERROR: challenge_response_demo.py failed"; exit 1; }

echo "✅ Protocol verification passed"
