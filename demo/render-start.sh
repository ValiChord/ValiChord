#!/usr/bin/env bash
# Startup script for Render web service.
# Runs inside the Docker container at /app.
set -euo pipefail

echo "=== ValiChord demo startup ==="

# ── Start Holochain conductor (background) ────────────────────────────────────
cd /app/demo
mkdir -p conductor_data

echo "Starting Holochain conductor…"
holochain --config-path conductor-config.yaml > conductor.log 2>&1 &
CONDUCTOR_PID=$!
echo "Conductor PID: $CONDUCTOR_PID"

# ── Run setup (waits for conductor, installs happ, writes app-config.json) ───
echo "Running setup.mjs…"
node setup.mjs

# ── Start static server + WS proxy (foreground) ──────────────────────────────
echo "Starting serve.mjs…"
exec node serve.mjs
