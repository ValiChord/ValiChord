#!/usr/bin/env node
// Coordinator hot-swap for the attestation DNA (AdminRequest::UpdateCoordinators,
// zero DNA-hash change — running cells switch immediately, DHT state untouched).
//
// First used 2026-07-08 to roll the local-read coordinator change onto the live
// Oracle demo nodes without restarting containers or losing HarmonyRecord URLs.
//
// Oracle runbook (per container, researcher first, verify between nodes):
//   scp attestation_coordinator.wasm + this script to the host, then:
//   sudo docker cp <files> <container>:/tmp/
//   sudo docker exec \
//     -e WASM_PATH=/tmp/attestation_coordinator.wasm \
//     -e CLIENT_PATH=/app/demo/node_modules/@holochain/client/lib/index.js \
//     -e ADMIN_PORT=4444 <container> node /tmp/hotswap-coordinators.mjs
//
// Local rehearsal (throwaway conductor, REQUIRED before any live rollout):
//   REHEARSAL=1 ADMIN_PORT=4446 HAPP_PATH=…/workdir/valichord.happ \
//   WASM_PATH=…/release/attestation_coordinator.wasm \
//   CLIENT_PATH=…/valichord-ui/node_modules/@holochain/client/lib/index.js \
//   node demo/hotswap-coordinators.mjs
//
// Modes:
//   REHEARSAL=1  — throwaway local conductor: install happ (dev bypass) first, then swap.
//   (default)    — assume app already installed (Oracle node): just swap + verify.
//
// Env:
//   ADMIN_PORT   (default 4444)
//   WASM_PATH    path to new attestation_coordinator.wasm (required)
//   CLIENT_PATH  path to @holochain/client entry (lib/index.js)
//   HAPP_PATH    only for REHEARSAL install
//   APP_ID       optional; auto-detects the first installed valichord* app
//
// Verifies with a real zome call (get_my_claimed_studies, read-only)
// before and after the swap.
//
// Only for coordinator-zome changes. Integrity changes = new DNA hash = new
// network; they cannot be hot-swapped (see CLAUDE.md).

import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const ADMIN_PORT = parseInt(process.env.ADMIN_PORT || '4444', 10);
const WASM_PATH = process.env.WASM_PATH;
const REHEARSAL = process.env.REHEARSAL === '1';
const HAPP_PATH = process.env.HAPP_PATH;
let APP_ID = process.env.APP_ID || (REHEARSAL ? 'valichord' : '');
if (!WASM_PATH) throw new Error('WASM_PATH required');

const { AdminWebsocket, AppWebsocket } = await import(
  process.env.CLIENT_PATH ? pathToFileURL(process.env.CLIENT_PATH).href : '@holochain/client'
);

const admin = await AdminWebsocket.connect({
  url: new URL(`ws://127.0.0.1:${ADMIN_PORT}`),
  wsClientOptions: { origin: 'valichord-hotswap' },
});
console.log(`[admin] connected :${ADMIN_PORT}`);

if (REHEARSAL) {
  const apps = await admin.listApps({});
  if (!apps.find((a) => a.installed_app_id === APP_ID)) {
    if (!HAPP_PATH) throw new Error('HAPP_PATH required for rehearsal install');
    await admin.installApp({
      installed_app_id: APP_ID,
      source: { type: 'path', value: HAPP_PATH },
      network_seed: `hotswap-rehearsal-${Date.now()}`,
      roles_settings: {
        attestation: {
          type: 'provisioned',
          value: {
            membrane_proof: new Uint8Array(64).fill(0x42),
            modifiers: {
              properties: {
                minimum_validators: 1,
                discipline: 'genomics',
                authorized_joining_certificate_issuer: '',
              },
            },
          },
        },
        governance: {
          type: 'provisioned',
          value: {
            modifiers: {
              properties: {
                system_coordinator_key: '',
                harmony_record_creator_key: '',
              },
            },
          },
        },
      },
    });
    await admin.enableApp({ installed_app_id: APP_ID });
    console.log('[rehearsal] app installed + enabled');
  }
}

// find attestation cell (auto-detect app id on demo nodes: valichord-<role>)
const apps = await admin.listApps({});
const app = APP_ID
  ? apps.find((a) => a.installed_app_id === APP_ID)
  : apps.find((a) => a.installed_app_id.startsWith('valichord'));
if (!app) throw new Error(`no valichord app installed (found: ${apps.map((a) => a.installed_app_id).join(', ')})`);
APP_ID = app.installed_app_id;
console.log(`[app] ${APP_ID} (status: ${JSON.stringify(app.status)})`);
const cellInfo = app.cell_info['attestation']?.[0];
const cell_id = cellInfo?.value?.cell_id ?? cellInfo?.cell_id;
if (!cell_id) throw new Error('attestation cell not found');
console.log('[cell] attestation cell found');

// app ws + signing for verification calls
const ifaces = await admin.listAppInterfaces();
let appPort = ifaces.find((i) => i.installed_app_id == null || i.installed_app_id === APP_ID)?.port;
if (!appPort) {
  ({ port: appPort } = await admin.attachAppInterface({ allowed_origins: '*' }));
}
await admin.authorizeSigningCredentials(cell_id);
const { token } = await admin.issueAppAuthenticationToken({ installed_app_id: APP_ID, single_use: false, expiry_seconds: 0 });
const appWs = await AppWebsocket.connect({
  url: new URL(`ws://127.0.0.1:${appPort}`),
  token,
  wsClientOptions: { origin: 'valichord-hotswap' },
});

async function verify(label) {
  const res = await appWs.callZome({
    cell_id,
    zome_name: 'attestation_coordinator',
    fn_name: 'get_my_claimed_studies',
    payload: null,
  });
  console.log(`[verify ${label}] get_my_claimed_studies OK (${Array.isArray(res) ? res.length : '?'} records)`);
}

await verify('pre-swap');

const wasm = new Uint8Array(readFileSync(WASM_PATH));
console.log(`[swap] uploading ${wasm.length} bytes`);
await admin.updateCoordinators({
  cell_id,
  source: {
    type: 'bundle',
    value: {
      manifest: {
        zomes: [{
          name: 'attestation_coordinator',
          path: 'attestation_coordinator.wasm',
          dependencies: [{ name: 'attestation_integrity' }],
        }],
      },
      resources: { 'attestation_coordinator.wasm': wasm },
    },
  },
});
console.log('[swap] updateCoordinators returned OK');

await verify('post-swap');
console.log('HOTSWAP COMPLETE');
await appWs.client.close();
await admin.client.close();
process.exit(0);
