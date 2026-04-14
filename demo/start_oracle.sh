#!/usr/bin/env bash
# start_oracle.sh — Start the ValiChord demo stack on the Oracle server.
#
# Starts: Holochain conductor + Node.js bridge + HTTP Gateway.
# Does NOT start the valichord_at_home Flask backend — that is a separate project.
#
# Set before running:
#   export ANTHROPIC_API_KEY=sk-ant-...
#
# Ports:
#   8090  — HTTP Gateway (public, opened in Oracle Security List)
#   8888  — Holochain bridge (internal only)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SERVER_IP="$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP')"

source "$HOME/.cargo/env" 2>/dev/null || true

echo "=== Starting ValiChord demo on $SERVER_IP ==="

# ── Kill any old processes ─────────────────────────────────────────────────────
pkill -f "holochain.*conductor-config"  2>/dev/null || true
pkill -f "lair-keystore"                2>/dev/null || true
pkill -f "serve.mjs"                    2>/dev/null || true
pkill -f "hc-http-gw"                   2>/dev/null || true
pkill -f "kitsune2-bootstrap-srv"       2>/dev/null || true
sleep 2

# ── Install + start local bootstrap + SBD signal server ───────────────────────
# Holochain 0.6.0 uses tx5/WebRTC transport.  By default it tries to reach
# dev-test-bootstrap2.holochain.org, which causes "Peer connection failed"
# errors in single-agent mode on Oracle (no external peer to connect to).
# Running kitsune2-bootstrap-srv locally on port 9000 gives the conductor a
# working SBD relay without any internet dependency.
echo "[1/4] Starting local kitsune2 bootstrap + signal server (port 9000)…"
if ! command -v kitsune2-bootstrap-srv &>/dev/null; then
    echo "  Installing kitsune2_bootstrap_srv 0.3.2 (one-time, may take a few minutes)…"
    cargo install kitsune2_bootstrap_srv --version 0.3.2 --locked
fi
kitsune2-bootstrap-srv \
    --listen 127.0.0.1:9000 \
    --sbd-disable-rate-limiting \
    > "$SCRIPT_DIR/bootstrap.log" 2>&1 &
BOOTSTRAP_PID=$!
sleep 1
echo "  PID $BOOTSTRAP_PID — logs: demo/bootstrap.log"

# ── Start Holochain conductor ──────────────────────────────────────────────────
echo "[2/4] Starting Holochain conductor…"
cd "$SCRIPT_DIR"
echo "demo-passphrase" | holochain \
    --config-path conductor-config.yaml \
    --piped \
    > "$SCRIPT_DIR/conductor.log" 2>&1 &
CONDUCTOR_PID=$!
echo "  PID $CONDUCTOR_PID — logs: demo/conductor.log"

echo -n "  Waiting for admin port"
for i in $(seq 1 60); do
    if bash -c 'echo > /dev/tcp/localhost/4444' 2>/dev/null; then
        echo " ready."
        break
    fi
    sleep 1; echo -n "."
done

# ── Run setup ─────────────────────────────────────────────────────────────────
echo "[3/4] Running setup…"
cd "$REPO_DIR"
node "$SCRIPT_DIR/setup.mjs"

# ── Extract governance DNA hash + write env config ─────────────────────────────
# setup.mjs writes governanceDnaHash into app-config.json — read it with Python.
echo "  Extracting governance DNA hash…"
GOVERNANCE_DNA_HASH=$(python3 -c "
import json, sys
try:
    c = json.load(open('$SCRIPT_DIR/app-config.json'))
    print(c.get('governanceDnaHash', ''))
except Exception as e:
    sys.stderr.write('Could not read app-config.json: ' + str(e) + '\n')
" 2>/dev/null || true)

export HOLOCHAIN_GATEWAY_URL="http://${SERVER_IP}:8090"
export HOLOCHAIN_GOVERNANCE_DNA_HASH="$GOVERNANCE_DNA_HASH"
export VALICHORD_PUBLIC_API_KEY="${VALICHORD_PUBLIC_API_KEY:-valichord-demo-2026}"

printf 'HOLOCHAIN_GATEWAY_URL=%s\nHOLOCHAIN_GOVERNANCE_DNA_HASH=%s\nVALICHORD_BRIDGE_URL=%s\nVALICHORD_API_KEY=%s\n' \
  "$HOLOCHAIN_GATEWAY_URL" \
  "$GOVERNANCE_DNA_HASH" \
  "http://localhost:8888" \
  "$VALICHORD_PUBLIC_API_KEY" \
  > "$SCRIPT_DIR/holochain-config.env"

echo "  Gateway URL:         $HOLOCHAIN_GATEWAY_URL"
echo "  Governance DNA hash: $GOVERNANCE_DNA_HASH"
echo "  Public API URL:      http://${SERVER_IP}:5000"
echo "  API key:             $VALICHORD_PUBLIC_API_KEY"
echo "  Env written to:      demo/holochain-config.env"

# ── Start bridge + gateway ─────────────────────────────────────────────────────
echo "[4/4] Starting Holochain bridge (port 8888) and HTTP Gateway (port 8090)…"
node "$SCRIPT_DIR/serve.mjs" &
SERVE_PID=$!
sleep 2
bash "$SCRIPT_DIR/start-gateway.sh" &
sleep 3

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "=== Stack is up ==="
echo "  HTTP Gateway:  http://${SERVER_IP}:8090"
echo "  Public API:    http://${SERVER_IP}:5000  (X-ValiChord-Key: $VALICHORD_PUBLIC_API_KEY)"
echo ""
echo "Local demo (on this server):"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  python3 demo/ai_validator.py"
echo ""
echo "Remote demo (from any machine — no Holochain install needed):"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  export VALICHORD_BRIDGE_URL=http://${SERVER_IP}:5000"
echo "  export VALICHORD_API_KEY=$VALICHORD_PUBLIC_API_KEY"
echo "  python3 demo/ai_validator.py"
echo ""
echo "Press Ctrl+C to stop."

wait $CONDUCTOR_PID
