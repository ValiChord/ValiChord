#!/usr/bin/env bash
# Startup script for Render web service.
# Runs inside the Docker container at /app.
set -uo pipefail

echo "=== ValiChord demo startup ==="

cd /app/demo
mkdir -p conductor_data

# ── Start HTTP server FIRST so Render's port scanner finds the port ──────────
# The demo page will show a loading state until setup.mjs writes app-config.json.
echo "Starting HTTP server on port ${PORT:-10000}..."
node serve.mjs &
SERVE_PID=$!
sleep 1

# ── Start Holochain conductor (background) ────────────────────────────────────
echo "Starting Holochain conductor..."
holochain --config-path conductor-config.yaml > conductor.log 2>&1 &
CONDUCTOR_PID=$!

# ── Run setup (waits for conductor, installs happ, writes app-config.json) ───
echo "Running setup.mjs (takes ~2 min on first run — conductor JIT-compiles WASMs)..."
if ! node setup.mjs; then
    echo "=== setup.mjs failed. Conductor log tail: ==="
    tail -50 conductor.log || true
    echo "=== Keeping HTTP server alive for diagnostics ==="
    wait $SERVE_PID
    exit 1
fi

echo "=== Setup complete. Demo is live. ==="
wait $SERVE_PID
