/**
 * node-lib.mjs — Shared Holochain session helpers for decentralised demo nodes.
 *
 * Imported by researcher-node.mjs and validator-node.mjs.
 */

import { pathToFileURL } from 'node:url';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { existsSync, readFileSync } from 'node:fs';

export const ADMIN_PORT = parseInt(process.env.ADMIN_PORT || '4444', 10);
export const APP_PORT   = parseInt(process.env.APP_PORT   || '4500', 10);

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_DIR  = resolve(__dirname, '..');

// ── @holochain/client lazy loader ─────────────────────────────────────────────

let _hcClient = null;
export async function loadHcClient() {
  if (_hcClient) return _hcClient;
  const localPath  = resolve(__dirname, 'node_modules/@holochain/client/lib/index.js');
  const testPath   = resolve(REPO_DIR,  'valichord/tests/node_modules/@holochain/client/lib/index.js');
  const clientPath = existsSync(localPath) ? localPath : testPath;
  _hcClient = await import(pathToFileURL(clientPath).href);
  return _hcClient;
}

// ── Uint8Array ↔ JSON serialisation ──────────────────────────────────────────
// Mirrors the _serialize/_deserialize convention in serve.mjs so that in-memory
// values can be passed through zome call payloads without manual conversion.

export function serialize(v) {
  if (v instanceof Uint8Array) return { __bytes: Buffer.from(v).toString('base64') };
  if (Array.isArray(v))        return v.map(serialize);
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.entries(v).map(([k, w]) => [k, serialize(w)]));
  }
  return v;
}

export function deserialize(v) {
  // Uint8Array (and Buffer) pass through unchanged — Object.entries on a typed
  // array destroys the byte values.
  if (v instanceof Uint8Array) return v;
  if (v && typeof v === 'object' && typeof v.__bytes === 'string') {
    return Buffer.from(v.__bytes, 'base64');
  }
  if (Array.isArray(v))        return v.map(deserialize);
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.entries(v).map(([k, w]) => [k, deserialize(w)]));
  }
  return v;
}

// ── Utilities ─────────────────────────────────────────────────────────────────

export const sleep = ms => new Promise(r => setTimeout(r, ms));

export function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end',  () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

// Retry wrapper for zome calls that touch the shared DHT.
// Under iroh/QUIC (Holochain 0.6.1+) transport errors are rare but gossip lag
// can still cause transient network timeouts on first DHT read.
export async function retryOnNetworkError(fn, label, maxRetries = 5, delayMs = 4000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      const msg = err?.message ?? String(err);
      const isTransient = msg.includes('response channel dropped') || msg.includes('response timeout') ||
                          msg.includes('network') || msg.includes('connection');
      if (!isTransient || attempt === maxRetries) throw err;
      console.error(`[${label}] network error (attempt ${attempt}/${maxRetries}), retrying in ${delayMs}ms…`);
      await sleep(delayMs);
    }
  }
}

// ── Authenticated session factory ─────────────────────────────────────────────
// Opens one AppWebsocket session, runs fn({ call }), then closes.
// call(role, zome, fn, payload) applies deserialize to payload before callZome
// and serialize to the result — matching serve.mjs behaviour exactly.

export async function withSession(fn) {
  const configPath = resolve(__dirname, 'app-config.json');
  if (!existsSync(configPath)) {
    throw new Error('app-config.json not found — run node-setup.mjs first');
  }
  const config = JSON.parse(readFileSync(configPath, 'utf8'));
  const { AdminWebsocket, AppWebsocket } = await loadHcClient();

  // Authorise signing credentials for all cells (required by Holochain 0.6.x).
  const admin = await AdminWebsocket.connect({
    url: new URL(`ws://localhost:${ADMIN_PORT}`),
    wsClientOptions: { origin: 'valichord-node' },
    defaultTimeout: 60_000,
  });
  const apps    = await admin.listApps({});
  const appInfo = apps.find(a => a.installed_app_id === config.appId);
  if (!appInfo) throw new Error(`App '${config.appId}' not installed in conductor`);
  for (const cells of Object.values(appInfo.cell_info)) {
    for (const cell of cells) {
      const cellId = cell.value?.cell_id;
      if (cellId) await admin.authorizeSigningCredentials(cellId);
    }
  }
  await admin.client.close();

  const appWs = await AppWebsocket.connect({
    url: new URL(`ws://localhost:${APP_PORT}`),
    token: new Uint8Array(config.token),
    wsClientOptions: { origin: 'valichord-node' },
    defaultTimeout: 120_000,
  });

  const call = (role_name, zome_name, fn_name, payload) =>
    appWs.callZome({ role_name, zome_name, fn_name, payload: deserialize(payload) })
         .then(serialize);

  try {
    return await fn({ call });
  } finally {
    await appWs.client.close();
  }
}

// ── ExternalHash reconstruction ───────────────────────────────────────────────
// encodeHashToBase64 returns 'u' + base64url(39-byte HoloHash).
// This reverses the encoding to get back the raw Uint8Array usable as a zome payload.
export function externalHashFromB64(b64) {
  const stripped = b64.startsWith('u') ? b64.slice(1) : b64;
  return Buffer.from(stripped, 'base64url');
}
