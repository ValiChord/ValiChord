/**
 * E2E conductor manager — starts a throwaway Holochain conductor, installs
 * valichord.happ with the dev-mode membrane-proof bypass, and issues the
 * auth token + per-cell signing credentials the browser needs.
 *
 * Pattern ported from happenings-community/requests-and-offers
 * (feat/e2e-real-conductor-infrastructure): one real conductor per Playwright
 * run, managed by globalSetup/globalTeardown, connection details handed to the
 * page via URL hash params (#APP_PORT=&TOKEN=&CREDS=) — the same channel the
 * Holochain Launcher uses.
 *
 * The install block (roles_settings, membrane proof, dev-bypass properties)
 * deliberately mirrors dev-setup.mjs. If DNA properties change, update BOTH
 * files — a drift here fails e2e loudly, which is the point.
 *
 * Ports/paths are distinct from dev.sh (admin 4444/app 8888//tmp/valichord-dev-data)
 * so an e2e run never clobbers a running dev session.
 */

import { spawn, execSync, type ChildProcess } from 'node:child_process';
import { writeFileSync, readFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  AdminWebsocket,
  AppWebsocket,
  encodeHashToBase64,
  getSigningCredentials,
  WsClient,
} from '@holochain/client';

const __dirname = dirname(fileURLToPath(import.meta.url));

export const UI_DIR = resolve(__dirname, '../../..');
export const REPO_DIR = resolve(UI_DIR, '..');
export const HAPP_PATH = resolve(REPO_DIR, 'valichord/workdir/valichord.happ');

export const ADMIN_PORT = 4445;
export const APP_PORT = 8889;
export const APP_ID = 'valichord-e2e';
export const DATA_DIR = '/tmp/valichord-e2e-data';
export const CONDUCTOR_LOG = '/tmp/valichord-e2e-conductor.log';
const CONFIG_PATH = `${DATA_DIR}/e2e-conductor.yaml`;
const PID_FILE = `${DATA_DIR}/.conductor.pid`;
export const ENV_FILE = '/tmp/valichord-e2e-env.json';

export interface TestEnv {
  appPort: number;
  tokenB64: string;
  credsB64: string;
}

function conductorConfig(): string {
  // Mirrors dev-conductor.yaml with e2e ports/paths.
  return [
    `data_root_path: ${DATA_DIR}`,
    'keystore:',
    '  type: lair_server_in_proc',
    `  lair_root: ${DATA_DIR}/ks`,
    'admin_interfaces:',
    '  - driver:',
    '      type: websocket',
    `      port: ${ADMIN_PORT}`,
    "      allowed_origins: '*'",
    'network:',
    '  bootstrap_url: https://dev-test-bootstrap2.holochain.org/',
    '  signal_url: wss://dev-test-bootstrap2.holochain.org/',
    '  relay_url: https://dev-test-bootstrap2.holochain.org/',
    'db_sync_strategy: Resilient',
    '',
  ].join('\n');
}

export async function startConductor(): Promise<void> {
  if (!existsSync(HAPP_PATH)) {
    throw new Error(
      `[e2e] hApp not found at ${HAPP_PATH}. Build + pack it first (see CLAUDE.md → Build and test commands).`,
    );
  }

  // Kill any stale e2e conductor from a previous crashed run, then start fresh.
  try {
    execSync('pkill -f "holochain.*e2e-conductor.yaml"', { stdio: 'ignore' });
    await new Promise((r) => setTimeout(r, 1000));
  } catch {
    /* none running */
  }
  rmSync(DATA_DIR, { recursive: true, force: true });
  mkdirSync(DATA_DIR, { recursive: true });
  writeFileSync(CONFIG_PATH, conductorConfig());

  console.log(`[e2e] Starting conductor (admin :${ADMIN_PORT}, logs → ${CONDUCTOR_LOG})…`);
  const logFd = (await import('node:fs')).openSync(CONDUCTOR_LOG, 'w');
  const proc: ChildProcess = spawn('holochain', ['--config-path', CONFIG_PATH, '--piped'], {
    env: { ...process.env, PATH: `/home/codespace/.cargo/bin:${process.env.PATH ?? ''}` },
    stdio: ['pipe', logFd, logFd],
    detached: false,
  });
  // --piped reads the lair passphrase from stdin; dev uses an empty one.
  proc.stdin?.write('\n');
  proc.stdin?.end();

  if (!proc.pid) throw new Error('[e2e] Conductor process failed to start');
  writeFileSync(PID_FILE, String(proc.pid));
}

async function waitForAdmin(retries = 120): Promise<AdminWebsocket> {
  for (let i = 0; i < retries; i++) {
    try {
      return await AdminWebsocket.connect({
        url: new URL(`ws://localhost:${ADMIN_PORT}`),
        wsClientOptions: { origin: 'e2e-setup' },
        // WASM JIT on a slow Codespace can take minutes — same margin as dev-setup.mjs.
        defaultTimeout: 600_000,
      });
    } catch {
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  throw new Error(`[e2e] Admin port ${ADMIN_PORT} not ready after ${retries}s`);
}

export async function setupHapp(): Promise<TestEnv> {
  const admin = await waitForAdmin();
  console.log('[e2e] Connected to admin. Installing hApp…');

  await admin.installApp({
    installed_app_id: APP_ID,
    source: { type: 'path', value: HAPP_PATH },
    network_seed: 'valichord-e2e',
    roles_settings: {
      attestation: {
        type: 'provisioned',
        value: {
          // 64 bytes satisfies the ≥64-byte format check in genesis_self_check.
          // Full Ed25519 verification is bypassed because
          // authorized_joining_certificate_issuer is '' (dev bypass) —
          // keep in sync with dev-setup.mjs.
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

  await admin.attachAppInterface({ port: APP_PORT, allowed_origins: '*' });

  const { token } = await admin.issueAppAuthenticationToken({
    installed_app_id: APP_ID,
    expiry_seconds: 0,
    single_use: false,
  });

  // Authorize per-cell signing credentials (client 0.20.x signs every zome
  // call). Serialized for both the browser (URL hash) and the Node-side
  // seeding client in the specs.
  const appClient = await AppWebsocket.connect({
    url: new URL(`ws://localhost:${APP_PORT}`),
    token: Array.from(token),
    wsClientOptions: { origin: 'e2e-setup' },
    defaultTimeout: 60_000,
  });
  const appInfo = await appClient.appInfo();
  const cellCreds: unknown[] = [];

  for (const cellList of Object.values(appInfo.cell_info)) {
    for (const cellData of cellList) {
      if (cellData.type !== 'provisioned') continue;
      const cellId = cellData.value?.cell_id;
      if (!cellId) continue;

      await admin.authorizeSigningCredentials(cellId);
      const creds = getSigningCredentials(cellId);
      if (!creds) continue;

      cellCreds.push({
        dnaHash: encodeHashToBase64(cellId[0]),
        agentKey: encodeHashToBase64(cellId[1]),
        capSecret: Buffer.from(creds.capSecret).toString('base64'),
        signingKey: encodeHashToBase64(creds.signingKey),
        pubKey: Buffer.from(creds.keyPair.publicKey).toString('base64'),
        privKey: Buffer.from(creds.keyPair.privateKey).toString('base64'),
      });
    }
  }

  // @holochain/client 0.21: AppWebsocket.client is now typed as the
  // AppClientTransport interface (request + on), because the App API can also be
  // routed over Tauri IPC, which has no socket to close. This harness always
  // dials a real websocket, so narrow it back. AdminWebsocket.client is
  // unaffected — it is still a WsClient.
  await (appClient.client as WsClient).close();
  await admin.client.close();

  const env: TestEnv = {
    appPort: APP_PORT,
    tokenB64: Buffer.from(token).toString('base64'),
    credsB64: Buffer.from(JSON.stringify(cellCreds)).toString('base64'),
  };
  writeFileSync(ENV_FILE, JSON.stringify(env));
  console.log(`[e2e] App ready → app port ${APP_PORT}, ${cellCreds.length} cells credentialed`);
  return env;
}

export async function stopConductor(): Promise<void> {
  if (existsSync(PID_FILE)) {
    const pid = parseInt(readFileSync(PID_FILE, 'utf-8'), 10);
    try {
      process.kill(pid, 'SIGTERM');
    } catch {
      /* already gone */
    }
  }
  await new Promise((r) => setTimeout(r, 1000));
  rmSync(DATA_DIR, { recursive: true, force: true });
}

export function readTestEnv(): TestEnv {
  if (!existsSync(ENV_FILE)) {
    throw new Error('[e2e] Test env not found — did globalSetup run?');
  }
  return JSON.parse(readFileSync(ENV_FILE, 'utf-8')) as TestEnv;
}
