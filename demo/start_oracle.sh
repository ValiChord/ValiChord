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
pkill -f "holochain.*conductor-config" 2>/dev/null || true
pkill -f "lair-keystore"               2>/dev/null || true
pkill -f "serve.mjs"                   2>/dev/null || true
pkill -f "hc-http-gw"                  2>/dev/null || true
sleep 2

# ── Start Holochain conductor ──────────────────────────────────────────────────
echo "[1/3] Starting Holochain conductor…"
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
echo "[2/3] Running setup…"
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

printf 'HOLOCHAIN_GATEWAY_URL=%s\nHOLOCHAIN_GOVERNANCE_DNA_HASH=%s\n' \
  "$HOLOCHAIN_GATEWAY_URL" "$GOVERNANCE_DNA_HASH" \
  > "$SCRIPT_DIR/holochain-config.env"

echo "  Gateway URL:         $HOLOCHAIN_GATEWAY_URL"
echo "  Governance DNA hash: $GOVERNANCE_DNA_HASH"
echo "  Env written to:      demo/holochain-config.env"

# ── Start bridge + gateway ─────────────────────────────────────────────────────
echo "[3/3] Starting Holochain bridge (port 8888) and HTTP Gateway (port 8090)…"
node "$SCRIPT_DIR/serve.mjs" &
SERVE_PID=$!
sleep 2
bash "$SCRIPT_DIR/start-gateway.sh" &
sleep 3

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "=== Stack is up ==="
echo "  HTTP Gateway:  http://${SERVER_IP}:8090"
echo ""
echo "Run the AI validator demo:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  python3 demo/ai_validator.py"
echo ""
echo "  (HOLOCHAIN_GATEWAY_URL and HOLOCHAIN_GOVERNANCE_DNA_HASH are auto-loaded"
echo "   from demo/holochain-config.env — no need to set them manually)"
echo ""
echo "Press Ctrl+C to stop."

wait $CONDUCTOR_PID
