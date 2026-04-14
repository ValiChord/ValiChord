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

# ── Option: --fresh (wipe conductor state) ────────────────────────────────────
FRESH=false
for arg in "$@"; do [[ "$arg" == "--fresh" ]] && FRESH=true; done

# ── Kill any old processes ─────────────────────────────────────────────────────
pkill -f "holochain.*conductor-config" 2>/dev/null || true
pkill -f "lair-keystore"               2>/dev/null || true
pkill -f "serve.mjs"                   2>/dev/null || true
pkill -f "hc-http-gw"                  2>/dev/null || true
sleep 2

if $FRESH; then
  echo "  Removing conductor data (fresh start)."
  rm -rf "$SCRIPT_DIR/conductor_data"
fi

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

# Give the tx5 transport time to fully register with the SBD relay server
# before any zome calls are made.  get_links calls the tx5 layer and returns
# a fatal error if the relay registration is not yet complete.
echo -n "  Waiting 30s for tx5 network layer to initialise"
for i in $(seq 1 30); do sleep 1; echo -n "."; done
echo " done."

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
