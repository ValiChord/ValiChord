#!/usr/bin/env bash
# Start a local Holochain conductor + install valichord.happ in dev-bypass mode.
#
# Usage:
#   Terminal 1 (conductor + setup):  cd valichord-ui && bash dev.sh
#   Terminal 2 (UI):                 cd valichord-ui && npm run dev
#
# Then open http://localhost:5173
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HAPP="$SCRIPT_DIR/../valichord/workdir/valichord.happ"
CONDUCTOR_LOG="/tmp/valichord-dev-conductor.log"
DATA_DIR="/tmp/valichord-dev-data"

export PATH="/home/codespace/.cargo/bin:$PATH"

if [ ! -f "$HAPP" ]; then
  echo "ERROR: valichord.happ not found at $HAPP"
  echo "Build it first (from valichord/):"
  echo "  cargo build --target wasm32-unknown-unknown --release"
  echo "  hc dna pack dnas/attestation -o workdir/attestation.dna"
  echo "  hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna"
  echo "  hc dna pack dnas/validator_workspace -o workdir/validator_workspace.dna"
  echo "  hc dna pack dnas/governance -o workdir/governance.dna"
  echo "  hc app pack . -o workdir/valichord.happ"
  exit 1
fi

# Kill stale conductor from previous runs
pkill -f "holochain.*dev-conductor.yaml" 2>/dev/null || true
sleep 1

# Fresh data dir (wipes previous agent identity — expected for dev)
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

echo "Starting conductor (logs → $CONDUCTOR_LOG)…"
# Tie the conductor to this script: if dev.sh dies (Ctrl-C, crash, SIGKILL, OOM,
# closed terminal) the kernel SIGTERMs the conductor so it can't orphan and hold
# the admin/app ports for the next run. setpriv --pdeathsig is the bash-native
# equivalent of prctl(PR_SET_PDEATHSIG); degrade gracefully if it's unavailable.
if command -v setpriv >/dev/null 2>&1; then REAP=(setpriv --pdeathsig TERM); else REAP=(); fi
"${REAP[@]}" holochain \
  --config-path "$SCRIPT_DIR/dev-conductor.yaml" \
  --piped \
  <<< "" \
  > "$CONDUCTOR_LOG" 2>&1 &
CONDUCTOR_PID=$!
echo "Conductor PID: $CONDUCTOR_PID"
# Clean-exit reaper (fallback when setpriv is absent; redundant-but-harmless with pdeathsig)
trap 'kill "$CONDUCTOR_PID" 2>/dev/null' EXIT INT TERM

# Run setup: waits for admin port, installs app, issues auth token
node "$SCRIPT_DIR/dev-setup.mjs"

echo ""
echo "Conductor is running (PID $CONDUCTOR_PID). Press Ctrl-C to stop."
echo "────────────────────────────────────────"
tail -f "$CONDUCTOR_LOG"
