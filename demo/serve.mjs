 /**
 * Static file server + WebSocket proxy for the ValiChord demo page.
 * Serves files from the demo/ directory on http://localhost:8888.
 * Also proxies WebSocket connections to the local Holochain conductor:
 *   /app-ws   → ws://localhost:4500  (app interface)
 *   /admin-ws → ws://localhost:4444  (admin interface)
 * This lets the browser use a single port (8888) regardless of whether
 * it is connecting from localhost or via HTTPS Codespace port-forwarding.
 * No external dependencies — pure Node.js built-ins.
 */

import { createServer, request as httpRequest } from 'node:http';
import { createConnection } from 'node:net';
import { readFile }         from 'node:fs/promises';
import { extname, join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL }    from 'node:url';
import { existsSync, readFileSync }        from 'node:fs';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const REPO_DIR   = resolve(__dirname, '..');
const PORT       = parseInt(process.env.PORT || '8888', 10);  // Render sets PORT
const APP_PORT   = 4500;
const ADMIN_PORT = 4444;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.mjs':  'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
};

// ── Holochain bridge helpers ──────────────────────────────────────────────────
// Internal-only endpoint (localhost) that lets the Python backend call zome
// functions without speaking WebSocket/msgpack directly.

// Lazy-loaded @holochain/client — same resolution strategy as setup.mjs.
let _hcClient = null;
async function _loadHcClient() {
  if (_hcClient) return _hcClient;
  const localPath  = resolve(__dirname, 'node_modules/@holochain/client/lib/index.js');
  const testPath   = resolve(REPO_DIR,  'valichord/tests/node_modules/@holochain/client/lib/index.js');
  const clientPath = existsSync(localPath) ? localPath : testPath;
  _hcClient = await import(pathToFileURL(clientPath).href);
  return _hcClient;
}

// Uint8Array ↔ JSON convention: { __bytes: "<base64>" }
// Lets Python pass ActionHash / ExternalHash values back into subsequent calls.
function _serialize(v) {
  if (v instanceof Uint8Array) return { __bytes: Buffer.from(v).toString('base64') };
  if (Array.isArray(v))        return v.map(_serialize);
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.entries(v).map(([k, w]) => [k, _serialize(w)]));
  }
  return v;
}
function _deserialize(v) {
  // Uint8Array (and Buffer) must pass through unchanged — Object.entries()
  // on a typed array produces numeric-keyed pairs and destroys the bytes.
  if (v instanceof Uint8Array) return v;
  if (v && typeof v === 'object' && typeof v.__bytes === 'string') {
    return Buffer.from(v.__bytes, 'base64');
  }
  if (Array.isArray(v))        return v.map(_deserialize);
  if (v && typeof v === 'object') {
    return Object.fromEntries(Object.entries(v).map(([k, w]) => [k, _deserialize(w)]));
  }
  return v;
}

const _sleep = ms => new Promise(r => setTimeout(r, ms));

function _readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end',  () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

// Open one authenticated session and run fn({ call, hashFrom32AndType, HoloHashType }).
// `call(role, zome, fn, payload)` makes a zome call with auto serialize/deserialize.
// Closes the AppWebsocket when fn resolves or rejects.
async function _withSession(fn) {
  const configPath = join(__dirname, 'app-config.json');
  if (!existsSync(configPath)) {
    throw new Error('app-config.json not found — run node demo/setup.mjs first');
  }
  const config = JSON.parse(readFileSync(configPath, 'utf8'));
  const { AdminWebsocket, AppWebsocket, hashFrom32AndType, HoloHashType } = await _loadHcClient();

  // Authorize signing credentials (required by Holochain 0.6.x before callZome).
  const admin = await AdminWebsocket.connect({
    url: new URL(`ws://localhost:${ADMIN_PORT}`),
    wsClientOptions: { origin: 'valichord-bridge' },
    defaultTimeout: 30_000,
  });
  const apps = await admin.listApps({});
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
    wsClientOptions: { origin: 'valichord-bridge' },
    defaultTimeout: 60_000,
  });

  const call = (role_name, zome_name, fn_name, payload) =>
    appWs.callZome({ role_name, zome_name, fn_name, payload: _deserialize(payload) })
         .then(_serialize);

  try {
    return await fn({ call, hashFrom32AndType, HoloHashType });
  } finally {
    await appWs.client.close();
  }
}

// Single-call convenience wrapper (used by POST /holochain/call).
async function _holochainCall(role_name, zome_name, fn_name, payload) {
  return _withSession(({ call }) => call(role_name, zome_name, fn_name, payload));
}

// Full single-agent commit-reveal round → HarmonyRecord ActionHash.
//
// Requires the conductor to be running with minimum_validators=1 and
// authorized_joining_certificate_issuer="" (dev/test bypass).
//
// Sequence:
//   1. submit_validation_request  (attestation)
//   2. claim_study                (attestation)
//   3. receive_task               (validator_workspace)
//   4. seal_private_attestation   (validator_workspace) → post_commit → notify_commitment_sealed
//   5. poll get_current_phase until RevealOpen
//   6. submit_attestation         (attestation)  — empty nonce uses dev bypass
//   7. check_and_create_harmony_record (governance) — explicit call fixes DHT timing
async function _runValidationRound({ data_hash_hex, outcome, discipline, confidence }) {
  return _withSession(async ({ call, hashFrom32AndType, HoloHashType }) => {
    const externalHash = hashFrom32AndType(
      Buffer.from(data_hash_hex, 'hex'),
      HoloHashType.External,
    );

    const disc = discipline ?? { type: 'ComputationalBiology' };
    const conf = confidence ?? 'Medium';

    const agreementLevel = {
      Reproduced:          'ExactMatch',
      PartiallyReproduced: 'DirectionalMatch',
      FailedToReproduce:   'Divergent',
      UnableToAssess:      'UnableToAssess',
    }[outcome?.type] ?? 'DirectionalMatch';

    // The public ValidationAttestation — identical object used for both seal
    // and reveal so the commitment hash verifies correctly.
    const validationAttestation = {
      request_ref: externalHash,
      outcome,
      outcome_summary: {
        key_metrics:                [],
        effect_direction_matches:   null,
        confidence_interval_overlap: null,
        overall_agreement:          agreementLevel,
      },
      time_invested_secs: 0,
      time_breakdown: {
        environment_setup_secs: 0,
        data_acquisition_secs:  0,
        code_execution_secs:    0,
        troubleshooting_secs:   0,
      },
      confidence:          conf,
      deviation_flags:     [],
      computational_resources: {
        personal_hardware_sufficient: true,
        hpc_required:                 false,
        gpu_required:                 false,
        cloud_compute_required:       false,
        estimated_compute_cost_pence: null,
      },
      discipline:             disc,
      commitment_anchor_hash: null,
    };

    const nowSecs = Math.floor(Date.now() / 1000);

    // 1. Open a validation request on the shared Attestation DHT.
    await call('attestation', 'attestation_coordinator', 'submit_validation_request', {
      protocol_ref:            null,
      data_hash:               externalHash,
      data_access_url:         '',
      protocol_access_url:     null,
      num_validators_required: 1,
      validation_tier:         'Basic',
      discipline:              disc,
      researcher_institution:  '',
    });

    // 2. Claim the study (required by notify_commitment_sealed's claim guard).
    await call('attestation', 'attestation_coordinator', 'claim_study', externalHash);

    // 3. Store the task in the private Validator Workspace DNA.
    const taskHash = await call(
      'validator_workspace', 'validator_workspace_coordinator', 'receive_task',
      {
        request_ref:      externalHash,
        assigned_at_secs: nowSecs,
        discipline:       disc,
        deadline_secs:    nowSecs + 86400 * 14,
        validation_focus: 'ComputationalReproducibility',
        time_cap_secs:    3600,
        compensation_tier: { Tier1: { amount_pence: 5000 } },
      },
    );

    // 4. Seal — post_commit fires and calls notify_commitment_sealed on DNA 3.
    //    With minimum_validators=1 this immediately writes PhaseMarker(RevealOpen).
    await call(
      'validator_workspace', 'validator_workspace_coordinator', 'seal_private_attestation',
      { task_hash: taskHash, attestation: validationAttestation },
    );

    // 5. Poll until RevealOpen — post_commit is async relative to seal returning.
    for (let i = 0; i < 60; i++) {
      const phase = await call(
        'attestation', 'attestation_coordinator', 'get_current_phase', externalHash,
      );
      if (phase !== null) break;
      await _sleep(500);
    }

    // 6. Reveal — empty nonce is accepted because authorized_joining_certificate_issuer
    //    is empty in dev mode, which bypasses hash verification in submit_attestation.
    await call('attestation', 'attestation_coordinator', 'submit_attestation', {
      attestation: validationAttestation,
      nonce:       new Uint8Array(0),
    });

    // 7. Trigger HarmonyRecord creation explicitly. submit_attestation fires this
    //    internally via post_commit but the ValidatorToAttestation link is not yet
    //    DHT-queryable at that point — governance returns empty. Calling again here
    //    (after submit_attestation returns) resolves the timing issue.
    const harmonyHashSerialized = await call(
      'governance', 'governance_coordinator', 'check_and_create_harmony_record', externalHash,
    );

    // Convert from { __bytes: "base64" } to the canonical uhCkk... string so
    // Python can embed it directly in URLs without further transformation.
    // harmonyHashSerialized is null when governance returns None.
    const { encodeHashToBase64 } = await _loadHcClient();
    let harmonyRecordHash = null;
    if (harmonyHashSerialized && harmonyHashSerialized.__bytes) {
      harmonyRecordHash = encodeHashToBase64(
        Buffer.from(harmonyHashSerialized.__bytes, 'base64'),
      );
    }

    // Compute the base64url-encoded JSON payload for the HTTP Gateway URL.
    // The gateway expects: GET /{dna-hash}/{app-id}/{zome}/{fn}?payload=<base64url-json>
    // For get_harmony_record the input is the ExternalHash (data hash), encoded as
    // a uhC0k... string in JSON: base64url(JSON.stringify("uhC0k..."))
    const externalHashB64 = encodeHashToBase64(externalHash);
    const gatewayPayload = Buffer.from(JSON.stringify(externalHashB64)).toString('base64url');

    return { harmony_record_hash: harmonyRecordHash, gateway_payload: gatewayPayload };
  });
}

// ── Static file handler ───────────────────────────────────────────────────────

const server = createServer(async (req, res) => {
  const url = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  if (url.includes('..')) { res.writeHead(403); res.end(); return; }

  // Diagnostic endpoint — serves conductor.log as plain text.
  if (url === '/conductor-log') {
    const logPath = join(__dirname, 'conductor.log');
    try {
      const data = await readFile(logPath, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' });
      res.end(data || '(conductor.log is empty)');
    } catch {
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end(existsSync(logPath) ? '(could not read log)' : '(conductor.log not yet created — conductor may not have started)');
    }
    return;
  }

  // ── Internal Holochain bridge ──────────────────────────────────────────────
  // POST /holochain/call — localhost only, used by backend/app.py.
  if (req.method === 'POST' && url === '/holochain/call') {
    const remote = req.socket.remoteAddress;
    if (remote !== '127.0.0.1' && remote !== '::1' && remote !== '::ffff:127.0.0.1') {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Forbidden — internal endpoint only' }));
      return;
    }
    let body;
    try {
      body = JSON.parse(await _readBody(req));
    } catch {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid JSON body' }));
      return;
    }
    const { role_name, zome_name, fn_name, payload } = body;
    if (!role_name || !zome_name || !fn_name) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Missing role_name, zome_name, or fn_name' }));
      return;
    }
    try {
      const result = await _holochainCall(role_name, zome_name, fn_name, payload ?? null);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ result }));
    } catch (err) {
      const msg = err.message ?? String(err);
      console.error(`[holochain/call] ${fn_name}: ${msg}`);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: msg }));
    }
    return;
  }

  // ── Full commit-reveal round ───────────────────────────────────────────────
  // POST /holochain/validate-round — localhost only, used by backend/app.py.
  // Runs the complete single-agent validation protocol and returns the
  // ActionHash of the resulting HarmonyRecord on the Governance DHT.
  if (req.method === 'POST' && url === '/holochain/validate-round') {
    const remote = req.socket.remoteAddress;
    if (remote !== '127.0.0.1' && remote !== '::1' && remote !== '::ffff:127.0.0.1') {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Forbidden — internal endpoint only' }));
      return;
    }
    let body;
    try {
      body = JSON.parse(await _readBody(req));
    } catch {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Invalid JSON body' }));
      return;
    }
    if (!body.data_hash_hex || !body.outcome) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Missing data_hash_hex or outcome' }));
      return;
    }
    try {
      const result = await _runValidationRound(body);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } catch (err) {
      const msg = err.message ?? String(err);
      console.error(`[holochain/validate-round]: ${msg}`);
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: msg }));
    }
    return;
  }

  // ── API proxy → Flask backend (port 5000) ────────────────────────────────
  // Lets the browser call /api/* on port 8888 without knowing the backend port.
  if (url.startsWith('/api/')) {
    const backendPath = url.slice(4); // /api/validate → /validate
    const qs = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
    const proxyReq = httpRequest(
      { hostname: 'localhost', port: 5000, path: backendPath + qs,
        method: req.method, headers: { ...req.headers, host: 'localhost:5000' } },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode,
          { ...proxyRes.headers, 'Access-Control-Allow-Origin': '*' });
        proxyRes.pipe(res);
      }
    );
    proxyReq.on('error', (err) => {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: `Backend unavailable: ${err.message}` }));
    });
    req.pipe(proxyReq);
    return;
  }

  const filePath = join(__dirname, url);
  try {
    const data = await readFile(filePath);
    res.writeHead(200, {
      'Content-Type': MIME[extname(filePath)] || 'application/octet-stream',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'no-cache',
    });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('404 Not Found');
  }
});

// ── WebSocket proxy ───────────────────────────────────────────────────────────
// Tunnels browser WebSocket connections through to the local conductor ports.
// The browser only needs access to port 8888; the conductor ports stay local.

server.on('upgrade', (req, browserSocket, head) => {
  let backendPort;
  if      (req.url === '/app-ws')   backendPort = APP_PORT;
  else if (req.url === '/admin-ws') backendPort = ADMIN_PORT;
  else { browserSocket.end('HTTP/1.1 404 Not Found\r\n\r\n'); return; }

  const backend = createConnection(backendPort, '127.0.0.1');

  backend.on('error', err => {
    console.error(`[proxy] backend :${backendPort} error: ${err.message}`);
    browserSocket.end('HTTP/1.1 502 Bad Gateway\r\n\r\n');
  });

  backend.on('connect', () => {
    // Reconstruct the HTTP/1.1 upgrade request for the conductor.
    // Replace Origin/Host so the conductor's allowed_origins: '*' accepts it.
    let reqStr = 'GET / HTTP/1.1\r\n';
    for (const [k, v] of Object.entries(req.headers)) {
      if (k === 'host')   { reqStr += `host: localhost:${backendPort}\r\n`; continue; }
      if (k === 'origin') { reqStr += `origin: http://localhost\r\n`;       continue; }
      reqStr += `${k}: ${v}\r\n`;
    }
    reqStr += '\r\n';
    backend.write(reqStr);
    if (head && head.length) backend.write(head);

    // Bidirectional pipe: backend 101 + frames → browser, browser frames → backend.
    backend.pipe(browserSocket);
    browserSocket.pipe(backend);
  });

  browserSocket.on('error', () => backend.destroy());
  backend.on('end',   () => browserSocket.end());
  browserSocket.on('end', () => backend.end());
});

// ── Listen ────────────────────────────────────────────────────────────────────

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Demo page  → http://localhost:${PORT}`);
  console.log(`WS proxy   → /app-ws → :${APP_PORT}, /admin-ws → :${ADMIN_PORT}`);
  console.log('Press Ctrl+C to stop.');
});
