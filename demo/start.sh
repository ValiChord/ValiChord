#!/usr/bin/env bash
# ValiChord Demo — start a persistent conductor and launch the demo page.
#
# Usage:
#   bash demo/start.sh          # reuse existing conductor data if present
#   bash demo/start.sh --fresh  # wipe conductor data and start clean
#
# Prerequisites:
#   valichord/workdir/valichord.happ must exist.
#   Build it first (from valichord/):
#
#     export PATH="$HOME/.cargo/bin:$PATH"
#     cargo build --target wasm32-unknown-unknown --release
#     hc dna pack dnas/attestation            -o workdir/attestation.dna
#     hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
#     hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
#     hc dna pack dnas/governance             -o workdir/governance.dna
#     hc app pack .                           -o workdir/valichord.happ

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
HAPP="$REPO_DIR/valichord/workdir/valichord.happ"
DATA_DIR="$SCRIPT_DIR/conductor_data"

# ── Guard: happ must be built ─────────────────────────────────────────────────
if [ ! -f "$HAPP" ]; then
  echo "Error: $HAPP not found. Build the hApp first (see usage in this script)."
  exit 1
fi

# ── Option: --fresh ───────────────────────────────────────────────────────────
FRESH=false
for arg in "$@"; do
  [[ "$arg" == "--fresh" ]] && FRESH=true
done
# Also start fresh if there is no conductor data yet.
[[ ! -d "$DATA_DIR" ]] && FRESH=true

# ── Kill any existing conductor ───────────────────────────────────────────────
echo "Stopping any existing conductor…"
pkill -f "holochain.*conductor-config" 2>/dev/null || true
pkill -f "lair-keystore"               2>/dev/null || true
sleep 2

if $FRESH; then
  echo "Removing old conductor data (fresh start)."
  rm -rf "$DATA_DIR"
fi

# ── Start conductor ───────────────────────────────────────────────────────────
# holochain resolves relative paths in conductor-config.yaml from CWD,
# so we cd into demo/ before launching.
echo "Starting Holochain conductor on admin port 4444…"
cd "$SCRIPT_DIR"
echo "demo-passphrase" | holochain \
  --config-path conductor-config.yaml \
  --piped \
  > "$SCRIPT_DIR/conductor.log" 2>&1 &
CONDUCTOR_PID=$!
echo "  PID $CONDUCTOR_PID — logs: demo/conductor.log"

# ── Wait for admin port ───────────────────────────────────────────────────────
echo -n "Waiting for admin port"
READY=false
for i in $(seq 1 40); do
  if nc -z localhost 4444 2>/dev/null \
     || 2>/dev/null bash -c 'echo > /dev/tcp/localhost/4444'; then
    READY=true
    break
  fi
  sleep 1
  echo -n "."
done
echo ""

if ! $READY; then
  echo "Conductor did not open admin port after 40s. Check demo/conductor.log."
  exit 1
fi
echo "Admin port ready."

# ── Run setup ─────────────────────────────────────────────────────────────────
export PATH="$HOME/.cargo/bin:$PATH"
cd "$REPO_DIR"
node "$SCRIPT_DIR/setup.mjs"

# ── Open browser ──────────────────────────────────────────────────────────────
sleep 0.5
if command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:8888" &
elif command -v open &>/dev/null; then
  open "http://localhost:8888" &
fi

# ── Serve demo page (blocks until Ctrl+C) ────────────────────────────────────
echo ""
node "$SCRIPT_DIR/serve.mjs"
