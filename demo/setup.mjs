/**
 * ValiChord Demo Setup
 *
 * Connects to the running Holochain conductor admin interface (ws://localhost:4444),
 * installs valichord.happ with single-validator dev-mode properties, attaches an
 * app WebSocket interface on port 4500, issues a reusable auth token, and writes
 * demo/app-config.json for the demo page to read.
 *
 * Run after the conductor is up:
 *   node demo/setup.mjs
 */

import { pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeFileSync, existsSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_DIR   = resolve(__dirname, '..');

// Resolve @holochain/client — prefer local demo/node_modules (Render / Docker),
// fall back to valichord/tests/node_modules (Codespace dev env).
const localClientPath = resolve(__dirname, 'node_modules/@holochain/client/lib/index.js');
const testClientPath  = resolve(REPO_DIR, 'valichord/tests/node_modules/@holochain/client/lib/index.js');
const clientPath = existsSync(localClientPath) ? localClientPath : testClientPath;
const { AdminWebsocket } = await import(pathToFileURL(clientPath).href);

const ADMIN_PORT = 4444;
const APP_PORT   = 4500;
const APP_ID     = 'valichord-demo';
const HAPP_PATH  = resolve(REPO_DIR, 'valichord/workdir/valichord.happ');

// ── Wait for conductor admin port to be ready ──────────────────────────────

async function connectAdmin(retries = 180) {
  for (let i = 0; i < retries; i++) {
    try {
      return await AdminWebsocket.connect({
        url: new URL(`ws://localhost:${ADMIN_PORT}`),
        wsClientOptions: { origin: 'demo-setup' },
        defaultTimeout: 120_000,
      });
    } catch {
      process.stdout.write(i === 0 ? 'Waiting for admin port' : '.');
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  throw new Error(`\nAdmin port ${ADMIN_PORT} not available after ${retries}s. Is the conductor running?`);
}

// ── Main ──────────────────────────────────────────────────────────────────

async function main() {
  const admin = await connectAdmin();
  console.log('\nConnected to admin WS.');

  // ── Install the hApp (idempotent) ────────────────────────────────────────
  const apps = await admin.listApps({});
  const already = apps.some(a => a.installed_app_id === APP_ID);

  if (!already) {
    console.log(`Installing ${APP_ID} from ${HAPP_PATH} …`);
    await admin.installApp({
      installed_app_id: APP_ID,
      source: { type: 'path', value: HAPP_PATH },
      network_seed: 'valichord-demo',
      roles_settings: {
        attestation: {
          type: 'provisioned',
          value: {
            // 64 bytes — passes the ≥64-byte format check in genesis_self_check.
            // Full Ed25519 verification is bypassed because authorized_joining_certificate_issuer
            // is an empty string (dev/test bypass — see attestation_coordinator init()).
            membrane_proof: new Uint8Array(64).fill(0x42),
            modifiers: {
              properties: {
                minimum_validators: 1,          // single validator → single-agent demo
                discipline: 'genomics',
                authorized_joining_certificate_issuer: '', // dev bypass
              },
            },
          },
        },
        governance: {
          type: 'provisioned',
          value: {
            modifiers: {
              properties: {
                system_coordinator_key: '',     // dev bypass — any agent may write
                harmony_record_creator_key: '', // dev bypass — any agent may write HarmonyRecord
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
  }

  // ── Ensure the app is enabled (handles install-then-timeout edge case) ───
  const freshApps = await admin.listApps({});
  const appStatus = freshApps.find(a => a.installed_app_id === APP_ID)?.status;
  if (appStatus?.type !== 'enabled') {
    console.log(`Enabling app (status was: ${JSON.stringify(appStatus)})…`);
    await admin.enableApp({ installed_app_id: APP_ID });
    console.log('App enabled.');
  }

  // ── Attach app WebSocket interface (idempotent) ──────────────────────────
  const ifaces = await admin.listAppInterfaces();
  let appPort = APP_PORT;
  if (!ifaces.some(i => i.port === APP_PORT)) {
    const res = await admin.attachAppInterface({
      port: APP_PORT,
      allowed_origins: '*',
    });
    appPort = res.port;
    console.log(`App interface attached on port ${appPort}.`);
  } else {
    console.log(`App interface already on port ${appPort}.`);
  }

  // ── Issue a reusable auth token ───────────────────────────────────────────
  const { token } = await admin.issueAppAuthenticationToken({
    installed_app_id: APP_ID,
    expiry_seconds: 0,   // no expiry
    single_use: false,   // reusable across page reloads
  });

  // ── Get the agent key for display in the demo page ───────────────────────
  const updatedApps = await admin.listApps({});
  const appInfo = updatedApps.find(a => a.installed_app_id === APP_ID);
  const agentPubKey = appInfo.agent_pub_key;

  // ── Resolve WebSocket URLs (localhost / GitHub Codespace / Render) ────────
  // Browsers block ws:// from https:// pages as mixed content; use wss://.
  // All WebSocket traffic routes through the serve.mjs proxy (/app-ws, /admin-ws)
  // so only one port needs to be externally reachable.
  const CODESPACE_NAME  = process.env.CODESPACE_NAME;
  const GH_DOMAIN       = process.env.GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN || 'app.github.dev';
  const RENDER_HOSTNAME = process.env.RENDER_EXTERNAL_HOSTNAME; // e.g. my-service.onrender.com
  const RENDER_PORT     = process.env.PORT;                     // Render assigns a port (often 10000)

  const wsBase = CODESPACE_NAME
    ? `wss://${CODESPACE_NAME}-8888.${GH_DOMAIN}`
    : RENDER_HOSTNAME
      ? `wss://${RENDER_HOSTNAME}`      // Render TLS terminates at the edge; no port in URL
      : `ws://localhost:${RENDER_PORT || 8888}`;
  const wsUrl = (port) => port === ADMIN_PORT
    ? `${wsBase}/admin-ws`
    : `${wsBase}/app-ws`;

  // ── Write app-config.json for the demo page ──────────────────────────────
  const config = {
    appPort,
    appWsUrl:   wsUrl(appPort),
    adminWsUrl: wsUrl(ADMIN_PORT),
    // AppAuthenticationToken is number[] in the type; Array.from handles Uint8Array too.
    token: Array.from(token),
    agentPubKey: Array.from(agentPubKey),
    appId: APP_ID,
  };
  const out = resolve(__dirname, 'app-config.json');
  writeFileSync(out, JSON.stringify(config, null, 2));
  console.log(`Wrote ${out}`);

  await admin.client.close();
  console.log('Setup complete.');
}

main().catch(e => {
  console.error('\nSetup failed:', e.message ?? e);
  process.exit(1);
});
