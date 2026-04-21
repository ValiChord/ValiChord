/**
 * node-setup.mjs — Per-container happ installation.
 *
 * Connects to the local conductor admin interface, installs valichord.happ
 * with the shared network_seed so all containers join the same DHT, attaches
 * an app WebSocket interface, issues a reusable auth token, and writes
 * demo/app-config.json for the node API to read.
 *
 * Environment variables:
 *   ADMIN_PORT    4444 (default)
 *   APP_PORT      4500 (default)
 *   NETWORK_SEED  valichord-demo-decentralised (default)
 *   HAPP_PATH     /app/valichord/workdir/valichord.happ
 *   ROLE          researcher | validator (used as app ID suffix)
 */

import { pathToFileURL } from 'node:url';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFileSync, existsSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_DIR  = resolve(__dirname, '..');

const ADMIN_PORT   = parseInt(process.env.ADMIN_PORT   || '4444', 10);
const APP_PORT     = parseInt(process.env.APP_PORT     || '4500', 10);
const NETWORK_SEED = process.env.NETWORK_SEED || 'valichord-demo-decentralised';
const ROLE         = process.env.ROLE         || 'validator';
const HAPP_PATH    = process.env.HAPP_PATH    || resolve(REPO_DIR, 'valichord/workdir/valichord.happ');
const APP_ID       = `valichord-${ROLE}`;

// Resolve @holochain/client — same strategy as setup.mjs.
const localPath  = resolve(__dirname, 'node_modules/@holochain/client/lib/index.js');
const testPath   = resolve(REPO_DIR,  'valichord/tests/node_modules/@holochain/client/lib/index.js');
const clientPath = existsSync(localPath) ? localPath : testPath;
const { AdminWebsocket } = await import(pathToFileURL(clientPath).href);

async function connectAdmin(retries = 180) {
  for (let i = 0; i < retries; i++) {
    try {
      return await AdminWebsocket.connect({
        url: new URL(`ws://localhost:${ADMIN_PORT}`),
        wsClientOptions: { origin: 'node-setup' },
        defaultTimeout: 600_000,
      });
    } catch {
      process.stdout.write(i === 0 ? 'Waiting for admin port' : '.');
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  throw new Error(`Admin port ${ADMIN_PORT} not available after ${retries}s`);
}

async function main() {
  const admin = await connectAdmin();
  console.log(`\nConnected (role: ${ROLE}, network_seed: ${NETWORK_SEED}).`);

  // ── Install the hApp (idempotent) ────────────────────────────────────────────
  const apps   = await admin.listApps({});
  const already = apps.some(a => a.installed_app_id === APP_ID);

  if (!already) {
    console.log(`Installing ${APP_ID} from ${HAPP_PATH}…`);
    await admin.installApp({
      installed_app_id: APP_ID,
      source: { type: 'path', value: HAPP_PATH },
      network_seed: NETWORK_SEED,
      roles_settings: {
        attestation: {
          type: 'provisioned',
          value: {
            // 64 bytes — passes the ≥64-byte format check in genesis_self_check.
            membrane_proof: new Uint8Array(64).fill(0x42),
            modifiers: {
              properties: {
                minimum_validators: 3,
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
                system_coordinator_key: '',   // dev bypass
              },
            },
          },
        },
      },
    });
    await admin.enableApp({ installed_app_id: APP_ID });
    console.log('App installed and enabled.');
  } else {
    console.log(`${APP_ID} already installed — skipping.`);
    const freshApps = await admin.listApps({});
    const appStatus = freshApps.find(a => a.installed_app_id === APP_ID)?.status;
    if (appStatus?.type !== 'enabled') {
      await admin.enableApp({ installed_app_id: APP_ID });
      console.log('App re-enabled.');
    }
  }

  // ── Attach app WebSocket interface (idempotent) ──────────────────────────────
  const ifaces = await admin.listAppInterfaces();
  if (!ifaces.some(i => i.port === APP_PORT)) {
    const res = await admin.attachAppInterface({ port: APP_PORT, allowed_origins: '*' });
    console.log(`App interface attached on port ${res.port}.`);
  } else {
    console.log(`App interface already on port ${APP_PORT}.`);
  }

  // ── Issue a reusable auth token ──────────────────────────────────────────────
  const { token } = await admin.issueAppAuthenticationToken({
    installed_app_id: APP_ID,
    expiry_seconds: 0,
    single_use: false,
  });

  // ── Extract agent pub key + governance DNA hash ──────────────────────────────
  const { encodeHashToBase64 } = await import(pathToFileURL(clientPath).href);
  const updatedApps = await admin.listApps({});
  const appInfo     = updatedApps.find(a => a.installed_app_id === APP_ID);

  let governanceDnaHash = '';
  for (const [role, cells] of Object.entries(appInfo.cell_info)) {
    if (role === 'governance') {
      const cellId = cells[0]?.value?.cell_id;
      if (cellId) { governanceDnaHash = encodeHashToBase64(cellId[0]); break; }
    }
  }

  // ── Write app-config.json ────────────────────────────────────────────────────
  const config = {
    appPort:          APP_PORT,
    token:            Array.from(token),
    agentPubKey:      Array.from(appInfo.agent_pub_key),
    appId:            APP_ID,
    governanceDnaHash,
  };
  writeFileSync(resolve(__dirname, 'app-config.json'), JSON.stringify(config, null, 2));
  console.log('Wrote app-config.json.');

  await admin.client.close();
  console.log('Setup complete.');
}

main().catch(e => {
  console.error('Setup failed:', e.message ?? e);
  process.exit(1);
});
