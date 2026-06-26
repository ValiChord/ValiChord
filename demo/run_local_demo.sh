#!/usr/bin/env bash
# Run the CORE-Bench demo against a local 5-conductor Holochain stack.
# Requires: Docker, ANTHROPIC_API_KEY set, CORE-Bench installed (pip install core-bench).
# Usage: bash demo/run_local_demo.sh [extra core_bench_runner.py flags]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Error: ANTHROPIC_API_KEY is not set." >&2
    exit 1
fi

echo "==> Starting local Holochain stack..."
docker compose -f "$SCRIPT_DIR/docker-compose.yml" up --build -d

echo "==> Waiting for all 4 node APIs to be ready..."
until [ "$(docker compose -f "$SCRIPT_DIR/docker-compose.yml" logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do
    sleep 3
done
echo "==> Stack ready."

echo "==> Running CORE-Bench demo (targets localhost by default)..."
cd "$SCRIPT_DIR"
python3 core_bench_runner.py \
    --capsule capsule-0851068 \
    --researcher-runs 1 \
    --researcher-model anthropic/claude-sonnet-4-6 \
    --validator-models anthropic/claude-sonnet-4-6 anthropic/claude-sonnet-4-6 anthropic/claude-sonnet-4-6 \
    "$@"

echo ""
echo "==> Done. To tear down the local stack: docker compose -f demo/docker-compose.yml down -v"
