#!/usr/bin/env bash
# node-entrypoint.sh — Startup script for a single decentralised demo container.
#
# Environment variables (all have defaults):
#   ROLE              researcher | validator          (default: validator)
#   BOOTSTRAP_URL     http://bootstrap:9000           (default: http://localhost:9000)
#   ADMIN_PORT        4444                            (default: 4444)
#   APP_PORT          4500                            (default: 4500)
#   NODE_API_PORT     3001                            (default: 3001)
#   NETWORK_SEED      valichord-demo-decentralised    (default as shown)
#   HAPP_PATH         /app/valichord/workdir/valichord.happ
#   HOLOCHAIN_PASSPHRASE  demo-passphrase
set -euo pipefail

ROLE="${ROLE:-validator}"
BOOTSTRAP_URL="${BOOTSTRAP_URL:-http://localhost:9000}"
ADMIN_PORT="${ADMIN_PORT:-4444}"
APP_PORT="${APP_PORT:-4500}"
NODE_API_PORT="${NODE_API_PORT:-3001}"
NETWORK_SEED="${NETWORK_SEED:-valichord-demo-decentralised}"
HAPP_PATH="${HAPP_PATH:-/app/valichord/workdir/${ROLE}.happ}"
PASSPHRASE="${HOLOCHAIN_PASSPHRASE:-demo-passphrase}"

# Derive WebSocket signal URL from bootstrap HTTP URL (same port, different scheme).
SIGNAL_URL="${BOOTSTRAP_URL/http:/ws:}"

echo "=== ValiChord node: role=$ROLE bootstrap=$BOOTSTRAP_URL ==="

# ── Generate conductor config from template ────────────────────────────────────
# conductor-config-node.yaml lives next to this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_OUT="/tmp/conductor-config.yaml"
sed -e "s|__BOOTSTRAP_URL__|$BOOTSTRAP_URL|g" \
    -e "s|__SIGNAL_URL__|$SIGNAL_URL|g" \
    -e "s|__ADMIN_PORT__|$ADMIN_PORT|g" \
    "$SCRIPT_DIR/conductor-config-node.yaml" > "$CONFIG_OUT"

# ── Start Holochain conductor ──────────────────────────────────────────────────
cd "$SCRIPT_DIR"
echo "$PASSPHRASE" | RUST_LOG="warn,holochain_conductor=info,holochain_p2p=warn,kitsune_p2p=warn" \
    holochain --config-path "$CONFIG_OUT" --piped \
    > /tmp/conductor.log 2>&1 &
CONDUCTOR_PID=$!

# Write exit code to file when conductor dies (for post-mortem debugging).
( wait $CONDUCTOR_PID; echo "conductor exited: code=$? pid=$CONDUCTOR_PID" >> /tmp/conductor.log ) &
echo "  Conductor PID $CONDUCTOR_PID — logs: /tmp/conductor.log"

# ── Wait for admin port ────────────────────────────────────────────────────────
echo -n "  Waiting for admin port $ADMIN_PORT"
CONDUCTOR_READY=false
for i in $(seq 1 120); do
    if bash -c "echo > /dev/tcp/localhost/$ADMIN_PORT" 2>/dev/null; then
        echo " ready."
        CONDUCTOR_READY=true
        break
    fi
    sleep 1; echo -n "."
done

if [ "$CONDUCTOR_READY" = false ]; then
    echo ""
    echo "=== CONDUCTOR FAILED TO START — dumping log ==="
    cat /tmp/conductor.log
    echo "=== END CONDUCTOR LOG ==="
    exit 1
fi

# ── Install happ on this conductor ────────────────────────────────────────────
ADMIN_PORT="$ADMIN_PORT" \
APP_PORT="$APP_PORT" \
NETWORK_SEED="$NETWORK_SEED" \
HAPP_PATH="$HAPP_PATH" \
ROLE="$ROLE" \
    node "$SCRIPT_DIR/node-setup.mjs"

# ── Start the role-specific node API ──────────────────────────────────────────
ADMIN_PORT="$ADMIN_PORT" \
APP_PORT="$APP_PORT" \
NODE_API_PORT="$NODE_API_PORT" \
    node "$SCRIPT_DIR/${ROLE}-node.mjs"

# If node exits, the conductor should also stop.
kill $CONDUCTOR_PID 2>/dev/null || true
