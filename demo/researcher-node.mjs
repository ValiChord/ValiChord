/**
 * researcher-node.mjs — HTTP API for the researcher conductor in the
 * decentralised demo.
 *
 * Each container runs its own Holochain conductor with its own keypair.
 * This process connects only to the LOCAL conductor (localhost) and exposes
 * a simple HTTP API that ai_validator.py calls to drive the researcher side of
 * the commit-reveal protocol.
 *
 * Endpoints:
 *   GET  /health                   — liveness probe (no auth)
 *   POST /lock-result              — lock_researcher_result + extract nonce
 *   POST /submit-request           — submit_validation_request
 *   GET  /phase?hash=<b64>         — get_current_phase (poll until RevealOpen)
 *   POST /reveal                   — reveal_researcher_result (SHA-256 verified on-chain)
 *   GET  /record?hash=<b64>        — get_harmony_record (for shareable /record/ URLs)
 *
 * State is held in memory keyed by external_hash_b64 (unique per demo run).
 */

import { createServer } from 'node:http';
import {
  withSession, readBody, loadHcClient, externalHashFromB64,
} from './node-lib.mjs';

const PORT = parseInt(process.env.NODE_API_PORT || '3001', 10);

// In-memory store: external_hash_b64 → { nonce: Buffer(32), externalHash: Buffer(39) }
const lockedResults = new Map();

const server = createServer(async (req, res) => {
  const parsedUrl = new URL(req.url ?? '/', `http://localhost`);
  const url       = parsedUrl.pathname;

  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // ── GET /health ─────────────────────────────────────────────────────────────
  if (req.method === 'GET' && url === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ status: 'ok', role: 'researcher' }));
    return;
  }

  // ── POST /lock-result ───────────────────────────────────────────────────────
  // Calls lock_researcher_result (DNA 1), then reads back the nonce via
  // get_locked_result so the reveal step can verify the hash.
  //
  // Body:   { data_hash_hex: string, metrics: MetricResult[] }
  // Returns { external_hash_b64: string }
  if (req.method === 'POST' && url === '/lock-result') {
    let body;
    try { body = JSON.parse(await readBody(req)); }
    catch { res.writeHead(400); res.end(JSON.stringify({ error: 'Invalid JSON' })); return; }

    if (!body.data_hash_hex || !Array.isArray(body.metrics)) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Missing data_hash_hex or metrics' }));
      return;
    }

    try {
      const { hashFrom32AndType, HoloHashType, encodeHashToBase64 } = await loadHcClient();
      const externalHash = hashFrom32AndType(
        Buffer.from(body.data_hash_hex, 'hex'),
        HoloHashType.External,
      );

      let lockedNonce = null;
      await withSession(async ({ call }) => {
        await call(
          'researcher_repository', 'researcher_repository_coordinator',
          'lock_researcher_result',
          { request_ref: externalHash, metrics: body.metrics },
        );

        const record = await call(
          'researcher_repository', 'researcher_repository_coordinator',
          'get_locked_result',
          externalHash,
        );
        if (!record) throw new Error('get_locked_result returned null after locking');

        const { decode: msgpackDecode } = await import('@msgpack/msgpack');
        const entryB64 = record?.entry?.Present?.entry?.__bytes ?? null;
        if (!entryB64) throw new Error('LockedResult entry bytes not found');
        const lockedResult = msgpackDecode(Buffer.from(entryB64, 'base64'));
        // lockedResult.nonce is a Uint8Array(32) from the Rust zome.
        lockedNonce = lockedResult.nonce;
      });

      const externalHashB64 = encodeHashToBase64(externalHash);
      lockedResults.set(externalHashB64, { nonce: lockedNonce, externalHash });

      console.log(`[lock-result] locked ${externalHashB64.slice(0, 20)}…`);
      res.writeHead(200);
      res.end(JSON.stringify({ external_hash_b64: externalHashB64 }));
    } catch (err) {
      console.error('[lock-result]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ── POST /submit-request ────────────────────────────────────────────────────
  // Publishes ValidationRequest to the shared Attestation DHT.
  //
  // Body:   { external_hash_b64, discipline?, num_validators_required?, data_access_url? }
  // Returns { ok: true }
  if (req.method === 'POST' && url === '/submit-request') {
    let body;
    try { body = JSON.parse(await readBody(req)); }
    catch { res.writeHead(400); res.end(JSON.stringify({ error: 'Invalid JSON' })); return; }

    const stored = lockedResults.get(body.external_hash_b64);
    if (!stored) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: `No locked result for ${body.external_hash_b64}` }));
      return;
    }

    try {
      const disc = body.discipline ?? { type: 'ComputationalBiology' };
      await withSession(async ({ call }) => {
        await call('attestation', 'attestation_coordinator', 'submit_validation_request', {
          protocol_ref:            null,
          data_hash:               stored.externalHash,
          data_access_url:         body.data_access_url    ?? '',
          deposit_access_type:     body.deposit_access_type ?? 'PublicUrl',
          deposit_token:           null,
          protocol_access_url:     null,
          num_validators_required: body.num_validators_required ?? 3,
          validation_tier:         'Basic',
          discipline:              disc,
          researcher_institution:  '',
        });
      });

      console.log('[submit-request] ValidationRequest published.');
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true }));
    } catch (err) {
      console.error('[submit-request]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ── GET /phase?hash=<external_hash_b64> ────────────────────────────────────
  // Calls get_current_phase on the shared Attestation DHT.
  // Returns { phase: "RevealOpen" | null } — null means still in commit phase.
  if (req.method === 'GET' && url === '/phase') {
    const hashB64 = parsedUrl.searchParams.get('hash');
    if (!hashB64) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Missing hash query param' }));
      return;
    }

    const stored = lockedResults.get(hashB64);
    if (!stored) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: `No locked result for ${hashB64}` }));
      return;
    }

    try {
      const phase = await withSession(async ({ call }) => {
        return call(
          'attestation', 'attestation_coordinator', 'get_current_phase',
          stored.externalHash,
        );
      });

      res.writeHead(200);
      res.end(JSON.stringify({ phase }));
    } catch (err) {
      console.error('[/phase]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ── POST /reveal ────────────────────────────────────────────────────────────
  // Calls reveal_researcher_result, which recomputes SHA-256(msgpack(metrics) || nonce)
  // on-chain and verifies it matches the commitment hash from step (0).
  //
  // Body:   { external_hash_b64, metrics: MetricResult[] }
  // Returns { researcher_reveal_hash: string | null }
  if (req.method === 'POST' && url === '/reveal') {
    let body;
    try { body = JSON.parse(await readBody(req)); }
    catch { res.writeHead(400); res.end(JSON.stringify({ error: 'Invalid JSON' })); return; }

    const stored = lockedResults.get(body.external_hash_b64);
    if (!stored) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: `No locked result for ${body.external_hash_b64}` }));
      return;
    }

    if (!Array.isArray(body.metrics)) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Missing metrics array' }));
      return;
    }

    try {
      const { encodeHashToBase64 } = await loadHcClient();
      let revealHashSerialized = null;

      await withSession(async ({ call }) => {
        revealHashSerialized = await call(
          'attestation', 'attestation_coordinator', 'reveal_researcher_result', {
            request_ref: stored.externalHash,
            metrics:     body.metrics,
            nonce:       stored.nonce,
          },
        );
      });

      const revealHash = revealHashSerialized?.__bytes
        ? encodeHashToBase64(Buffer.from(revealHashSerialized.__bytes, 'base64'))
        : null;

      console.log(`[/reveal] researcher reveal hash: ${revealHash?.slice(0, 20)}…`);
      res.writeHead(200);
      res.end(JSON.stringify({ researcher_reveal_hash: revealHash }));
    } catch (err) {
      console.error('[/reveal]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ── GET /record?hash=<external_hash_b64> ────────────────────────────────────
  // Fetches a HarmonyRecord from the Governance DHT by ExternalHash.
  // Used by ai_validator.py to verify the record is publicly readable.
  if (req.method === 'GET' && url === '/record') {
    const hashB64 = parsedUrl.searchParams.get('hash');
    if (!hashB64) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Missing hash query param' }));
      return;
    }

    try {
      const hashBytes = externalHashFromB64(hashB64);

      // Retry until the HarmonyRecord has gossiped to this node (up to 30s).
      let record = null;
      for (let attempt = 0; attempt < 6 && !record; attempt++) {
        if (attempt > 0) await new Promise(r => setTimeout(r, 5000));
        record = await withSession(async ({ call }) => {
          return call('governance', 'governance_coordinator', 'get_harmony_record', hashBytes);
        });
      }

      if (!record) {
        res.writeHead(404);
        res.end(JSON.stringify({ error: 'Record not found' }));
        return;
      }

      const { decode: msgpackDecode } = await import('@msgpack/msgpack');
      const entryB64 = record?.entry?.Present?.entry?.__bytes ?? null;
      const hr       = entryB64 ? (msgpackDecode(Buffer.from(entryB64, 'base64')) ?? {}) : {};

      res.writeHead(200, { 'Cache-Control': 'public, max-age=3600' });
      res.end(JSON.stringify({
        harmony_record_hash: hashB64,
        outcome:         hr.outcome         ?? null,
        agreement_level: hr.agreement_level ?? null,
        discipline:      hr.discipline      ?? null,
        validator_count: Array.isArray(hr.participating_validators)
                           ? hr.participating_validators.length : 0,
      }, null, 2));
    } catch (err) {
      console.error('[/record]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Researcher node API → http://0.0.0.0:${PORT}`);
});
