/**
 * ValiChord UI Dev Setup
 *
 * Waits for the local conductor (admin on :4444), installs valichord.happ
 * with dev-mode membrane-proof bypass, attaches an app interface on :8888,
 * issues a reusable no-expiry auth token, authorizes per-cell signing
 * credentials, and writes everything to .env.local so the Vite dev server
 * can bootstrap AppWebsocket.connect without Holochain Launcher.
 *
 * Run AFTER the conductor is started by dev.sh:
 *   node valichord-ui/dev-setup.mjs
 */

import { pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFileSync, existsSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_DIR  = resolve(__dirname, '..');

// Prefer UI node_modules, fall back to tests node_modules
const uiClientPath   = resolve(__dirname, 'node_modules/@holochain/client/lib/index.js');
const testClientPath = resolve(REPO_DIR, 'valichord/tests/node_modules/@holochain/client/lib/index.js');
const clientPath = existsSync(uiClientPath) ? uiClientPath : testClientPath;

const {
  AdminWebsocket,
  AppWebsocket,
  encodeHashToBase64,
  getSigningCredentials,
} = await import(pathToFileURL(clientPath).href);

const ADMIN_PORT = 4444;
const APP_PORT   = 8888;
const APP_ID     = 'valichord-dev';
const HAPP_PATH  = resolve(REPO_DIR, 'valichord/workdir/valichord.happ');
const ENV_LOCAL  = resolve(__dirname, '.env.local');

async function waitForAdmin(retries = 120) {
  for (let i = 0; i < retries; i++) {
    try {
      return await AdminWebsocket.connect({
        url: new URL(`ws://localhost:${ADMIN_PORT}`),
        wsClientOptions: { origin: 'dev-setup' },
        defaultTimeout: 600_000,   // 10 min — WASM JIT on slow Codespace can take 5+ min
      });
    } catch {
      if (i === 0) process.stdout.write('Waiting for conductor admin port');
      else process.stdout.write('.');
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  throw new Error(`\nAdmin port ${ADMIN_PORT} not ready after ${retries}s`);
}

const admin = await waitForAdmin();
console.log('\nConnected to admin.');

// ── Install app ──────────────────────────────────────────────────────────────

const apps = await admin.listApps({});
if (!apps.some(a => a.installed_app_id === APP_ID)) {
  console.log(`Installing ${APP_ID} from ${HAPP_PATH}…`);
  await admin.installApp({
    installed_app_id: APP_ID,
    source: { type: 'path', value: HAPP_PATH },
    network_seed: 'valichord-dev',
    roles_settings: {
      attestation: {
        type: 'provisioned',
        value: {
          // 64 bytes satisfies the ≥64-byte format check in genesis_self_check.
          // Full Ed25519 verification is bypassed because authorized_joining_certificate_issuer
          // is set to '' (dev bypass).
          membrane_proof: new Uint8Array(64).fill(0x42),
          modifiers: {
            properties: {
              minimum_validators: 1,
              discipline: 'genomics',
              authorized_joining_certificate_issuer: '',  // dev bypass
            },
          },
        },
      },
      governance: {
        type: 'provisioned',
        value: {
          modifiers: {
            properties: {
              system_coordinator_key: '',       // dev bypass — any agent may write
              harmony_record_creator_key: '',   // dev bypass
            },
          },
        },
      },
    },
  });
  await admin.enableApp({ installed_app_id: APP_ID });
  console.log('App installed and enabled.');
} else {
  console.log(`${APP_ID} already installed.`);
  // Always ensure enabled — a previous install may have timed out before enableApp ran.
  const freshApps = await admin.listApps({});
  const appStatus = freshApps.find(a => a.installed_app_id === APP_ID)?.status;
  if (appStatus?.type !== 'enabled') {
    await admin.enableApp({ installed_app_id: APP_ID });
    console.log('App enabled.');
  }
}

// ── Attach app interface ─────────────────────────────────────────────────────

const ifaces = await admin.listAppInterfaces();
if (!ifaces.some(i => i.port === APP_PORT)) {
  await admin.attachAppInterface({ port: APP_PORT, allowed_origins: '*' });
  console.log(`App interface attached on port ${APP_PORT}.`);
} else {
  console.log(`App interface already on port ${APP_PORT}.`);
}

// ── Issue reusable auth token ────────────────────────────────────────────────

const { token } = await admin.issueAppAuthenticationToken({
  installed_app_id: APP_ID,
  expiry_seconds: 0,    // no expiry
  single_use: false,    // survives page reloads
});

// ── Authorize signing credentials for every cell ─────────────────────────────
// @holochain/client 0.20.x requires client-side Ed25519 signing for every
// zome call. In Launcher this is handled automatically; for a raw conductor
// we pre-generate a key pair per cell, grant it via the admin API, and
// serialize the credentials for the Vite dev server to inject at build time.

// Connect app WS to read cell IDs via appInfo()
const appClient = await AppWebsocket.connect({
  url: new URL(`ws://localhost:${APP_PORT}`),
  token: Array.from(token),
  wsClientOptions: { origin: 'dev-setup' },
  defaultTimeout: 30_000,
});
const appInfo = await appClient.appInfo();
const cellCreds = [];

for (const [, cellList] of Object.entries(appInfo.cell_info)) {
  for (const cellData of cellList) {
    // cellData shape: { type: "provisioned", value: { cell_id: [DnaHash, AgentPubKey] } }
    if (cellData.type !== 'provisioned') continue;
    const cellId = cellData.value?.cell_id;
    if (!cellId) continue;

    await admin.authorizeSigningCredentials(cellId);
    const creds = getSigningCredentials(cellId);
    if (!creds) continue;

    cellCreds.push({
      dnaHash:    encodeHashToBase64(cellId[0]),
      agentKey:   encodeHashToBase64(cellId[1]),
      capSecret:  Buffer.from(creds.capSecret).toString('base64'),
      signingKey: encodeHashToBase64(creds.signingKey),
      pubKey:     Buffer.from(creds.keyPair.publicKey).toString('base64'),
      privKey:    Buffer.from(creds.keyPair.privateKey).toString('base64'),
    });
    console.log(`  signing credentials authorized for DNA ${encodeHashToBase64(cellId[0]).slice(0, 10)}…`);
  }
}

// ── Write .env.local ─────────────────────────────────────────────────────────

const tokenB64 = Buffer.from(token).toString('base64');
const credsB64 = Buffer.from(JSON.stringify(cellCreds)).toString('base64');

writeFileSync(ENV_LOCAL,
  `# Auto-generated by dev-setup.mjs — do not edit\n` +
  `VITE_HC_PORT=${APP_PORT}\n` +
  `VITE_HC_TOKEN=${tokenB64}\n` +
  `VITE_HC_SIGNING_CREDENTIALS=${credsB64}\n`
);

console.log(`\nToken + signing credentials written to ${ENV_LOCAL}`);
console.log('Ready. In a second terminal run:');
console.log('  cd valichord-ui && npm run dev');
console.log('Then open http://localhost:5173');
