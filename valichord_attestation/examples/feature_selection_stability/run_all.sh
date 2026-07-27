#!/usr/bin/env bash
# Full demonstration, steps 1-7. No key, no GPU, no network, no conductor.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n\033[1m=== %s ===\033[0m\n\n' "$1"; }

step "1-2. Data + pre-registration (fixed and hashed before anyone runs anything)"
python3 protocol.py

step "3-4. Commit-reveal round: 1 researcher + 5 validators, each on their own resample"
python3 round.py

step "5. Aggregation: exact-match, per-feature, per-block"
python3 aggregate.py

step "6. Adversarial: lambda-shopping, and what catches it"
python3 lambda_shop.py

step "7. Attestation bundles + two-hash semantics"
python3 bundles.py
