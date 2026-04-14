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

# Ensure cargo-installed binaries (hc-http-gw) are on PATH.
source "$HOME/.cargo/env" 2>/dev/null || export PATH="$HOME/.cargo/bin:$PATH"

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
python3 -c "
import json, sys
try:
    c = json.load(open('$(dirname "$0")/app-config.json'))
    print(c.get('governanceDnaHash', '(not found)'))
except Exception as e:
    print('Could not read app-config.json:', e, file=sys.stderr)
" 2>/dev/null || true
echo ""
echo "Gateway URL base: http://localhost:${GATEWAY_PORT}"
echo ""

env "HC_GW_ALLOWED_FNS_${APP_ID}=${ALLOWED_FNS}" hc-http-gw --port ${GATEWAY_PORT} --address 0.0.0.0
