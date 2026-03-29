#!/usr/bin/env bash
# Start the Holochain HTTP Gateway alongside a running conductor.
#
# Prerequisites:
#   - holochain_http_gateway binary installed (cargo install holochain_http_gateway --version 0.3.1)
#   - Conductor running on admin port 4444 (run bash demo/start.sh first)
#   - app-config.json present (written by setup.mjs)
#
# The gateway exposes:
#   GET /{dna-hash}/valichord-demo/governance_coordinator/get_harmony_record?payload=<base64url-json>
#
# Usage:
#   bash demo/start-gateway.sh
#
# The governance DNA hash to use in URLs is printed on startup.
# Set HOLOCHAIN_GATEWAY_URL + HOLOCHAIN_GOVERNANCE_DNA_HASH in the Flask env to enable harmony_record_url.

set -euo pipefail

ADMIN_PORT=4444
GATEWAY_PORT=8090
APP_ID="valichord-demo"

# Allowed zome functions — expand this list to expose more read endpoints.
ALLOWED_FNS="governance_coordinator/get_harmony_record,governance_coordinator/get_harmony_records_by_discipline"

export HC_GW_ADMIN_WS_URL="ws://localhost:${ADMIN_PORT}"
export HC_GW_ALLOWED_APP_IDS="${APP_ID}"
export HC_GW_ZOME_CALL_TIMEOUT_MS=15000

# HC_GW_ALLOWED_FNS env var key: exact app ID with hyphens preserved.
# hyphens are invalid in bash variable names so we use env() at launch.

echo "Starting Holochain HTTP Gateway on port ${GATEWAY_PORT}..."
echo ""
echo "Governance DNA hash (needed for HOLOCHAIN_GOVERNANCE_DNA_HASH env var):"
node -e "
const { AdminWebsocket, encodeHashToBase64 } = require('$(pwd)/valichord/tests/node_modules/@holochain/client/lib/index.js');
(async () => {
  const admin = await AdminWebsocket.connect({ url: new URL('ws://localhost:${ADMIN_PORT}'), wsClientOptions: { origin: 'valichord-bridge' }, defaultTimeout: 10000 });
  const apps = await admin.listApps({});
  const app = apps.find(a => a.installed_app_id === '${APP_ID}');
  for (const [role, cells] of Object.entries(app.cell_info)) {
    if (role === 'governance') {
      const cellId = cells[0]?.value?.cell_id;
      if (cellId) console.log(encodeHashToBase64(cellId[0]));
    }
  }
  await admin.client.close();
})().catch(e => { console.error('Could not get DNA hash:', e.message); process.exit(1); });
" 2>/dev/null
echo ""
echo "Gateway URL base: http://localhost:${GATEWAY_PORT}"
echo ""

env "HC_GW_ALLOWED_FNS_${APP_ID}=${ALLOWED_FNS}" hc-http-gw --port ${GATEWAY_PORT} --address 0.0.0.0
