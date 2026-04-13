#!/usr/bin/env bash
# start_oracle.sh — Start the full ValiChord stack on the Oracle server.
#
# Set these before running:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   export VALICHORD_API_KEYS=your-key-here          # optional
#
# Ports opened:
#   5000  — Flask REST API  (opened in Oracle Security List)
#   8090  — HTTP Gateway    (opened in Oracle Security List)
#   8888  — Holochain bridge + demo page (internal only)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SERVER_IP="$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')"

source "$HOME/.cargo/env" 2>/dev/null || true

echo "=== Starting ValiChord on $SERVER_IP ==="

# ── Kill any old processes ────────────────────────────────────────────────────
pkill -f "holochain.*conductor-config" 2>/dev/null || true
pkill -f "lair-keystore"               2>/dev/null || true
pkill -f "serve.mjs"                   2>/dev/null || true
pkill -f "gunicorn.*app:app"           2>/dev/null || true
pkill -f "hc-http-gw"                  2>/dev/null || true
sleep 2

# ── Start Holochain conductor ─────────────────────────────────────────────────
echo "[1/4] Starting Holochain conductor…"
cd "$SCRIPT_DIR"
echo "demo-passphrase" | holochain \
    --config-path conductor-config.yaml \
    --piped \
    > "$SCRIPT_DIR/conductor.log" 2>&1 &
CONDUCTOR_PID=$!
echo "  PID $CONDUCTOR_PID — logs: demo/conductor.log"

# Wait for admin port
echo -n "  Waiting for admin port"
for i in $(seq 1 60); do
    if bash -c 'echo > /dev/tcp/localhost/4444' 2>/dev/null; then
        echo " ready."
        break
    fi
    sleep 1; echo -n "."
done

# ── Run setup (installs happ if fresh) ───────────────────────────────────────
echo "[2/4] Running setup…"
cd "$REPO_DIR"
node "$SCRIPT_DIR/setup.mjs"

# ── Start demo bridge (port 8888, internal) ───────────────────────────────────
echo "[3/4] Starting Holochain bridge on port 8888…"
node "$SCRIPT_DIR/serve.mjs" &
SERVE_PID=$!
echo "  PID $SERVE_PID"
sleep 2

# ── Start HTTP Gateway (port 8090, public) ────────────────────────────────────
echo "[4a/4] Starting HTTP Gateway on port 8090…"
bash "$SCRIPT_DIR/start-gateway.sh" &
sleep 3

# ── Start Flask backend (port 5000, public) ───────────────────────────────────
echo "[4b/4] Starting Flask backend on port 5000…"
export VALICHORD_BASE_URL="http://${SERVER_IP}:5000"
# HOLOCHAIN_GATEWAY_URL and HOLOCHAIN_GOVERNANCE_DNA_HASH are read from
# demo/app-config.json by the gateway; set them if you have them already.
# They will be printed by setup.mjs — check conductor.log or setup output.

cd "$REPO_DIR/backend"
gunicorn app:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - &
FLASK_PID=$!
echo "  PID $FLASK_PID"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Stack is up ==="
echo "  Flask API:      http://${SERVER_IP}:5000"
echo "  HTTP Gateway:   http://${SERVER_IP}:8090"
echo "  Health check:   curl http://${SERVER_IP}:5000/health"
echo ""
echo "Run the AI validator demo:"
echo "  ANTHROPIC_API_KEY=\$ANTHROPIC_API_KEY python3 demo/ai_validator.py"
echo ""
echo "Press Ctrl+C to stop all services."

# Keep alive — wait on conductor (longest-lived process)
wait $CONDUCTOR_PID
