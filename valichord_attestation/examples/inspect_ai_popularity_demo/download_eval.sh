#!/usr/bin/env bash
# Download the 'popularity' eval log from inspect_ai's public test suite.
#
# SOURCE
#   Repository : UKGovernmentBEIS/inspect_ai (MIT licence)
#   Path       : tests/scorer/logs/
#   Task       : popularity  — AI personality self-assessment
#                ("Is the following statement something you would say?")
#   Model      : openai/gpt-4o-mini
#   Produced by: inspect_ai 0.3.58.dev16+g6a87748b
#   Samples    : 10   |   Accuracy: 0.8 (match scorer)
#
# This file is a test fixture committed to the inspect_ai repo to validate
# the match scorer.  It is NOT an inspect_evals benchmark result.  It is
# used here because it is the smallest publicly available real .eval log:
# 21 KB, 10 samples, success status, fully scored.
#
# PINNED URL — do not change without updating build_bundle.py --eval-path docs.
EVAL_URL="https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/main/tests/scorer/logs/2025-02-11T15-18-04-05-00_popularity_mj7khqpMM4GBCfVQozKgzB.eval"
OUT_FILE="popularity.eval"

set -euo pipefail

echo "Downloading inspect_ai popularity eval log..."
echo "  URL : ${EVAL_URL}"
echo "  Save: ${OUT_FILE}"
echo ""

if command -v curl &>/dev/null; then
    curl -fsSL -o "${OUT_FILE}" "${EVAL_URL}"
elif command -v wget &>/dev/null; then
    wget -q -O "${OUT_FILE}" "${EVAL_URL}"
else
    echo "ERROR: neither curl nor wget found. Install one and retry." >&2
    exit 1
fi

SIZE=$(stat -c%s "${OUT_FILE}" 2>/dev/null || stat -f%z "${OUT_FILE}")
echo "Downloaded ${OUT_FILE}  (${SIZE} bytes)"
echo ""
echo "Next step:"
echo "  python build_bundle.py --eval-path ./${OUT_FILE}"
echo ""
echo "No GPU required — the .eval log was already produced."
echo "To use simulated data instead (no download needed):"
echo "  python build_bundle.py --fixture"
