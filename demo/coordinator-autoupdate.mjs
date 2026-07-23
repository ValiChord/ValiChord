#!/usr/bin/env node
// coordinator-autoupdate.mjs — Phase 2 of the coordinator auto-updater.
// Plan: docs/AUTO_UPDATER_SIDECAR_PLAN.md
//
// Polls a published coordinators-manifest.json (produced by pack-coordinators.mjs,
// Phase 1) and, when it advertises a newer revision, downloads each coordinator
// WASM, VERIFIES its sha256 against the manifest, and applies it via
// AdminRequest::UpdateCoordinators — the zero-DNA-hash-change hot-swap already
// proven live (see hotswap-coordinators.mjs, 2026-07-08). Published HarmonyRecord
// URLs survive because the DNA hash never changes.
//
// SAFETY (fail-closed):
//   - Every WASM is sha256-verified BEFORE anything is applied; ANY mismatch
//     aborts the whole update.
//   - manifest.holochain must match the running conductor version, else refuse.
//   - After each swap the cell's DNA hash is re-checked; if it changed, abort
//     (a coordinator swap must never change it — this asserts that invariant).
//   - Integrity/DNA-hash changes are impossible here: only coordinator zomes are
//     ever sent, never InstallApp.
//   - Every cycle is non-fatal in loop mode — a failure retries next interval.
//
// This is opt-in. node-entrypoint.sh only launches it when AUTOUPDATE=on. Run
// directly for testing/one-shot use.
//
// Modes:
//   (default)   loop: check every AUTOUPDATE_INTERVAL_S, forever, non-fatal
//   --once      single check+apply cycle, then exit (0 ok/noop, 1 error)
//   --check     fetch manifest + download + sha256-verify only; never connects
//               to a conductor and never applies (conductor-free smoke test)
//
// Env:
//   AUTOUPDATE_MANIFEST_URL   (required) URL of coordinators-manifest.json;
//                             WASMs are fetched from the same directory
//   AUTOUPDATE_INTERVAL_S     loop sleep seconds (default 21600 = 6h)
//   AUTOUPDATE_MARKER         applied-revision file (default:
//                             /app/demo/conductor_data/.coordinator-revision)
//   AUTOUPDATE_ROLE           this node's role, for logging + ordering
//   AUTOUPDATE_ROLE_DELAY_S   wait before applying (validators > researcher so
//                             the researcher node lands first; default 0)
//   ADMIN_PORT                conductor admin port (default 4444)
//   APP_ID                    installed app id (default: first "valichord*")
//   CLIENT_PATH               path to @holochain/client entry (lib/index.js)

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { dirname } from 'node:path';

const SCHEMA = 'valichord-coordinators-manifest/v1';

const MANIFEST_URL = process.env.AUTOUPDATE_MANIFEST_URL;
const ADMIN_PORT = parseInt(process.env.ADMIN_PORT || '4444', 10);
const INTERVAL_S = parseInt(process.env.AUTOUPDATE_INTERVAL_S || '21600', 10);
const MARKER = process.env.AUTOUPDATE_MARKER || '/app/demo/conductor_data/.coordinator-revision';
const ROLE = process.env.AUTOUPDATE_ROLE || '';
const ROLE_DELAY_S = parseInt(process.env.AUTOUPDATE_ROLE_DELAY_S || '0', 10);
const CLIENT_PATH = process.env.CLIENT_PATH || null;
let APP_ID = process.env.APP_ID || '';

const MODE = process.argv.includes('--check') ? 'check'
  : process.argv.includes('--once') ? 'once'
    : 'loop';

// Read-only, self-authored verify functions per cell role. Cells without an
// entry are still applied + DNA-hash-checked; they just skip the zome-call
// smoke test. Extend as safe read fns are confirmed for other cells.
const VERIFY_FNS = {
  attestation: { zome: 'attestation_coordinator', fn: 'get_my_claimed_studies', payload: null },
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString(), '[autoupdate]', ...a);
const sha256hex = (bytes) => createHash('sha256').update(bytes).digest('hex');

function wasmUrl(name) {
  // WASMs live alongside the manifest (same GitHub release / directory).
  return MANIFEST_URL.replace(/[^/]+$/, encodeURIComponent(name));
}

async function fetchJson(url) {
  const r = await fetch(url, { redirect: 'follow' });
  if (!r.ok) throw new Error(`GET ${url} → HTTP ${r.status}`);
  return r.json();
}
async function fetchBytes(url) {
  const r = await fetch(url, { redirect: 'follow' });
  if (!r.ok) throw new Error(`GET ${url} → HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

function readMarker() {
  try { return parseInt(readFileSync(MARKER, 'utf8').trim(), 10) || 0; }
  catch { return 0; }
}
function writeMarker(n) {
  try { mkdirSync(dirname(MARKER), { recursive: true }); } catch { /* dir exists */ }
  writeFileSync(MARKER, `${n}\n`);
}

function runningHolochainVersion() {
  try {
    const out = execFileSync('holochain', ['--version'], { encoding: 'utf8' });
    return out.match(/(\d+\.\d+\.\d+)/)?.[1] ?? null;
  } catch { return null; }
}

const dnaHashOf = (cell_id) => (cell_id ? String(cell_id[0]) : null);
const cellIdFrom = (info) => info?.value?.cell_id ?? info?.cell_id ?? null;

// One check+apply cycle. Returns 'noop' | 'applied'. Throws on any failure.
async function cycle() {
  const manifest = await fetchJson(MANIFEST_URL);
  if (manifest.schema !== SCHEMA) throw new Error(`unexpected manifest schema: ${manifest.schema}`);
  if (!Number.isInteger(manifest.revision)) throw new Error('manifest revision is not an integer');

  const applied = readMarker();
  if (manifest.revision <= applied) {
    log(`up to date (applied rev ${applied}, manifest rev ${manifest.revision})`);
    return 'noop';
  }
  log(`new revision ${manifest.revision} available (applied ${applied})`);

  // Guard: conductor version must match what the WASMs were built against.
  const running = runningHolochainVersion();
  if (MODE !== 'check' && running && manifest.holochain && running !== manifest.holochain) {
    throw new Error(`holochain mismatch: running ${running}, manifest built for ${manifest.holochain} — refusing`);
  }

  // Download + verify EVERY wasm before applying anything (fail-closed).
  const bytesByWasm = {};
  for (const cell of manifest.cells) {
    for (const z of cell.zomes) {
      if (bytesByWasm[z.wasm]) continue;
      const bytes = await fetchBytes(wasmUrl(z.wasm));
      const got = sha256hex(bytes);
      if (got !== z.sha256) {
        throw new Error(`sha256 mismatch for ${z.wasm}: expected ${z.sha256}, got ${got} — refusing update`);
      }
      if (bytes.length !== z.bytes) {
        throw new Error(`size mismatch for ${z.wasm}: expected ${z.bytes}, got ${bytes.length} — refusing update`);
      }
      bytesByWasm[z.wasm] = bytes;
      log(`verified ${z.wasm} (${bytes.length} bytes) sha256 ✓`);
    }
  }

  if (MODE === 'check') {
    log(`[check] revision ${manifest.revision} verified; not connecting to a conductor. OK to apply.`);
    return 'noop';
  }

  if (ROLE_DELAY_S > 0) {
    log(`role-ordering delay ${ROLE_DELAY_S}s${ROLE ? ` (${ROLE})` : ''} before applying`);
    await sleep(ROLE_DELAY_S * 1000);
  }

  const { AdminWebsocket, AppWebsocket } = await import(
    CLIENT_PATH ? pathToFileURL(CLIENT_PATH).href : '@holochain/client'
  );
  const admin = await AdminWebsocket.connect({
    url: new URL(`ws://127.0.0.1:${ADMIN_PORT}`),
    wsClientOptions: { origin: 'valichord-autoupdate' },
  });
  try {
    const apps = await admin.listApps({});
    const app = APP_ID
      ? apps.find((a) => a.installed_app_id === APP_ID)
      : apps.find((a) => a.installed_app_id.startsWith('valichord'));
    if (!app) throw new Error(`no valichord app installed (found: ${apps.map((a) => a.installed_app_id).join(', ') || 'none'})`);
    APP_ID = app.installed_app_id;

    // App interface + signing, only needed for the verify zome calls.
    const ifaces = await admin.listAppInterfaces();
    let appPort = ifaces.find((i) => i.installed_app_id == null || i.installed_app_id === APP_ID)?.port;
    if (!appPort) ({ port: appPort } = await admin.attachAppInterface({ allowed_origins: '*' }));
    const { token } = await admin.issueAppAuthenticationToken({ installed_app_id: APP_ID, single_use: false, expiry_seconds: 0 });
    const appWs = await AppWebsocket.connect({
      url: new URL(`ws://127.0.0.1:${appPort}`),
      token,
      wsClientOptions: { origin: 'valichord-autoupdate' },
    });

    try {
      let appliedCount = 0;
      for (const cell of manifest.cells) {
        const info = app.cell_info[cell.role]?.[0];
        const cell_id = cellIdFrom(info);
        if (!cell_id) { log(`skip ${cell.role} (cell not present on this node)`); continue; }
        const dnaBefore = dnaHashOf(cell_id);

        const zomes = cell.zomes.map((z) => ({ name: z.name, path: z.wasm, dependencies: [{ name: z.integrity }] }));
        const resources = {};
        for (const z of cell.zomes) resources[z.wasm] = bytesByWasm[z.wasm];

        await admin.authorizeSigningCredentials(cell_id);
        await admin.updateCoordinators({ cell_id, source: { type: 'bundle', value: { manifest: { zomes }, resources } } });
        log(`updated ${cell.role} coordinators (${zomes.map((z) => z.name).join(', ')})`);

        // Invariant: a coordinator swap must NOT change the DNA hash.
        const app2 = (await admin.listApps({})).find((a) => a.installed_app_id === APP_ID);
        const dnaAfter = dnaHashOf(cellIdFrom(app2?.cell_info?.[cell.role]?.[0]));
        if (dnaAfter !== dnaBefore) {
          throw new Error(`DNA hash changed on ${cell.role} after swap (${dnaBefore} → ${dnaAfter}) — aborting`);
        }

        const v = VERIFY_FNS[cell.role];
        if (v) {
          await appWs.callZome({ cell_id, zome_name: v.zome, fn_name: v.fn, payload: v.payload });
          log(`verify ${cell.role}.${v.fn} OK`);
        }
        appliedCount += 1;
      }

      writeMarker(manifest.revision);
      log(`revision ${manifest.revision} applied (${appliedCount} cell(s) on this node)`);
      return 'applied';
    } finally {
      await appWs.client.close();
    }
  } finally {
    await admin.client.close();
  }
}

async function main() {
  if (!MANIFEST_URL) {
    console.error('[autoupdate] AUTOUPDATE_MANIFEST_URL is required');
    process.exit(2);
  }
  if (MODE === 'once' || MODE === 'check') {
    try { await cycle(); process.exit(0); }
    catch (e) { log('ERROR:', e.message); process.exit(1); }
  }
  log(`poller starting: manifest=${MANIFEST_URL} interval=${INTERVAL_S}s marker=${MARKER}${ROLE ? ` role=${ROLE}` : ''}`);
  for (;;) {
    try { await cycle(); }
    catch (e) { log('cycle error (will retry next interval):', e.message); }
    await sleep(INTERVAL_S * 1000);
  }
}

main();
