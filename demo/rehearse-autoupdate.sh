#!/usr/bin/env bash
# rehearse-autoupdate.sh — Phase 3 of the coordinator auto-updater.
# Plan: docs/AUTO_UPDATER_SIDECAR_PLAN.md
#
# End-to-end rehearsal against a THROWAWAY local conductor (no Oracle, no peers):
# installs valichord.happ (dev bypass), serves the packed manifest over http,
# runs coordinator-autoupdate.mjs --once, and asserts the applied-revision marker
# advanced. Exercises the real apply path (UpdateCoordinators + DNA-hash
# assertion + verify call) that --check skips.
#
# Isolated + self-cleaning: temp data dir, isolated admin port, full teardown.
set -uo pipefail

export PATH="/home/codespace/.cargo/bin:$PATH"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADMIN_PORT="${ADMIN_PORT:-4446}"
HTTP_PORT="${HTTP_PORT:-8791}"
HAPP="${HAPP_PATH:-$REPO_ROOT/valichord/workdir/valichord.happ}"
UPDATES="${UPDATES_DIR:-$REPO_ROOT/demo/coordinator-updates}"
CLIENT="$REPO_ROOT/valichord-ui/node_modules/@holochain/client/lib/index.js"
[ -f "$CLIENT" ] || CLIENT="$REPO_ROOT/demo/node_modules/@holochain/client/lib/index.js"
WORK="$(mktemp -d)"
MARKER="$WORK/.coordinator-revision"
SRV=0; COND=0

cleanup() {
  [ "$SRV" != 0 ] && kill "$SRV" 2>/dev/null
  [ "$COND" != 0 ] && kill "$COND" 2>/dev/null
  pkill -x holochain 2>/dev/null
  pkill -x lair-keystore 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT

command -v holochain >/dev/null 2>&1 || { echo "ERROR: holochain not on PATH"; exit 1; }
[ -f "$HAPP" ]   || { echo "ERROR: no happ at $HAPP (pack it first)"; exit 1; }
[ -f "$CLIENT" ] || { echo "ERROR: @holochain/client not found (npm install in demo/ or valichord-ui/)"; exit 1; }
[ -f "$UPDATES/coordinators-manifest.json" ] || { echo "ERROR: no manifest (run node demo/pack-coordinators.mjs)"; exit 1; }

echo "=== killing stale conductors ==="
pkill -x holochain 2>/dev/null; pkill -x lair-keystore 2>/dev/null; sleep 2

echo "=== throwaway conductor config (admin :$ADMIN_PORT) ==="
cat > "$WORK/conductor-config.yaml" <<EOF
data_root_path: $WORK/data
keystore:
  type: lair_server_in_proc
  lair_root: $WORK/data/ks
admin_interfaces:
  - driver:
      type: websocket
      port: $ADMIN_PORT
      allowed_origins: '*'
network:
  bootstrap_url: "http://127.0.0.1:1"
  relay_url: "ws://127.0.0.1:1"
EOF

echo "=== starting conductor ==="
echo "rehearse-pass" | holochain --config-path "$WORK/conductor-config.yaml" --piped > "$WORK/conductor.log" 2>&1 &
COND=$!
READY=0
for i in $(seq 1 120); do
  if bash -c "echo > /dev/tcp/localhost/$ADMIN_PORT" 2>/dev/null; then READY=1; break; fi
  sleep 1
done
[ "$READY" = 1 ] || { echo "ERROR: conductor did not open :$ADMIN_PORT"; tail -40 "$WORK/conductor.log"; exit 1; }
echo "conductor up."

echo "=== install valichord.happ (dev bypass) + enable ==="
ADMIN_PORT="$ADMIN_PORT" HAPP_PATH="$HAPP" CLIENT_PATH="$CLIENT" \
  node --input-type=module - <<'NODE'
import { pathToFileURL } from 'node:url';
const { AdminWebsocket } = await import(pathToFileURL(process.env.CLIENT_PATH).href);
const admin = await AdminWebsocket.connect({ url: new URL(`ws://127.0.0.1:${process.env.ADMIN_PORT}`), wsClientOptions: { origin: 'valichord-rehearse' } });
await admin.installApp({
  installed_app_id: 'valichord',
  source: { type: 'path', value: process.env.HAPP_PATH },
  network_seed: `rehearse-${Date.now()}`,
  roles_settings: {
    attestation: { type: 'provisioned', value: { membrane_proof: new Uint8Array(64).fill(0x42), modifiers: { properties: { minimum_validators: 1, discipline: 'genomics', authorized_joining_certificate_issuer: '' } } } },
    governance:  { type: 'provisioned', value: { modifiers: { properties: { system_coordinator_key: '', harmony_record_creator_key: '' } } } },
  },
});
await admin.enableApp({ installed_app_id: 'valichord' });
console.log('installed + enabled');
await admin.client.close();
NODE
[ $? -eq 0 ] || { echo "ERROR: install failed"; tail -40 "$WORK/conductor.log"; exit 1; }

echo "=== serve manifest on :$HTTP_PORT ==="
python3 -m http.server "$HTTP_PORT" --directory "$UPDATES" >/dev/null 2>&1 &
SRV=$!
for i in $(seq 1 20); do curl -sf "http://localhost:$HTTP_PORT/coordinators-manifest.json" >/dev/null 2>&1 && break; sleep 0.3; done

echo "=== run coordinator-autoupdate --once ==="
AUTOUPDATE_MANIFEST_URL="http://localhost:$HTTP_PORT/coordinators-manifest.json" \
AUTOUPDATE_MARKER="$MARKER" ADMIN_PORT="$ADMIN_PORT" APP_ID="valichord" CLIENT_PATH="$CLIENT" \
  node "$REPO_ROOT/demo/coordinator-autoupdate.mjs" --once
RC=$?

EXPECT=$(node -e "process.stdout.write(String(JSON.parse(require('fs').readFileSync('$UPDATES/coordinators-manifest.json','utf8')).revision))")
APPLIED=$(cat "$MARKER" 2>/dev/null || echo "<none>")
echo
echo "=== result: marker=$APPLIED (expected $EXPECT), exit=$RC ==="
if [ "$APPLIED" = "$EXPECT" ] && [ "$RC" = 0 ]; then
  echo "REHEARSAL PASS"
  exit 0
else
  echo "REHEARSAL FAIL"; tail -30 "$WORK/conductor.log"
  exit 1
fi
