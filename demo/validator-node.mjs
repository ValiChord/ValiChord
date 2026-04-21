/**
 * validator-node.mjs — HTTP API for a validator conductor in the
 * decentralised demo.
 *
 * Each validator container runs its own Holochain conductor with its own
 * keypair. This process connects only to the LOCAL conductor (localhost) and
 * exposes a simple HTTP API that ai_validator.py calls to drive one validator's
 * side of the commit-reveal protocol.
 *
 * Endpoints:
 *   GET  /health                   — liveness probe (no auth)
 *   POST /commit                   — profile + claim + receive_task + seal + extract nonce
 *   POST /reveal                   — submit_attestation (SHA-256 verified on-chain)
 *   POST /create-harmony-record    — check_and_create_harmony_record (governance DNA)
 *
 * State is held in memory keyed by external_hash_b64 (unique per demo run).
 */

import { createServer } from 'node:http';
import {
  withSession, retryOnTx5, readBody, loadHcClient, externalHashFromB64,
} from './node-lib.mjs';

const PORT = parseInt(process.env.NODE_API_PORT || '3001', 10);

// In-memory store: external_hash_b64 → { taskHash, nonce, validationAttestation }
const tasks = new Map();

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
    res.end(JSON.stringify({ status: 'ok', role: 'validator' }));
    return;
  }

  // ── POST /commit ────────────────────────────────────────────────────────────
  // Runs the full blind commit sequence:
  //   publish_validator_profile → claim_study → receive_task →
  //   seal_private_attestation (post_commit → CommitmentAnchor on shared DHT) →
  //   get_private_attestation_for_task (extract nonce for reveal)
  //
  // Body:   { external_hash_b64, verdict: { outcome, confidence, reasoning },
  //           metrics: MetricResult[], discipline? }
  // Returns { ok: true }
  if (req.method === 'POST' && url === '/commit') {
    let body;
    try { body = JSON.parse(await readBody(req)); }
    catch { res.writeHead(400); res.end(JSON.stringify({ error: 'Invalid JSON' })); return; }

    if (!body.external_hash_b64 || !body.verdict || !Array.isArray(body.metrics)) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: 'Missing external_hash_b64, verdict, or metrics' }));
      return;
    }

    try {
      const hashBytes = externalHashFromB64(body.external_hash_b64);
      const disc      = body.discipline ?? { type: 'ComputationalBiology' };
      const verdict   = body.verdict;
      const outcome   = { type: verdict.outcome };
      const conf      = verdict.confidence;
      const agreementLevel = {
        Reproduced:          'ExactMatch',
        PartiallyReproduced: 'DirectionalMatch',
        FailedToReproduce:   'Divergent',
        UnableToAssess:      'UnableToAssess',
      }[verdict.outcome] ?? 'ExactMatch';

      const nowSecs = Math.floor(Date.now() / 1000);

      // This is the public ValidationAttestation — the SAME object is used for
      // both seal and reveal so the SHA-256(msgpack(attestation) || nonce) hash
      // computed at seal time matches the recomputed hash at reveal time.
      const va = {
        request_ref: hashBytes,
        outcome,
        outcome_summary: {
          key_metrics:                 body.metrics,
          effect_direction_matches:    null,
          confidence_interval_overlap: null,
          overall_agreement:           agreementLevel,
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

      let taskHashSerialized = null;
      let nonce              = null;

      await withSession(async ({ call }) => {
        // Profile required before claim_study.
        await call('attestation', 'attestation_coordinator', 'publish_validator_profile', {
          institution:          'ValiChord Demo',
          disciplines:          [disc],
          certification_tier:   'Provisional',
          available:            true,
          max_concurrent_tasks: 4,
          orcid:                null,
          agent_type:           null,
          person_key:           null,
        });

        // claim_study returns null if the ValidationRequest hasn't gossiped yet — retry.
        // Inner retryOnTx5 handles WebRTC relay errors; outer loop handles gossip lag.
        let claimed = null;
        for (let attempt = 0; attempt < 12 && !claimed; attempt++) {
          if (attempt > 0) await new Promise(r => setTimeout(r, 5000));
          claimed = await retryOnTx5(
            () => call('attestation', 'attestation_coordinator', 'claim_study', hashBytes),
            'claim_study', 3, 3000,
          );
        }
        if (!claimed) throw new Error('claim_study: ValidationRequest not yet gossiped after 60s');

        taskHashSerialized = await call(
          'validator_workspace', 'validator_workspace_coordinator', 'receive_task', {
            request_ref:       hashBytes,
            assigned_at_secs:  nowSecs,
            discipline:        disc,
            deadline_secs:     nowSecs + 86400 * 14,
            validation_focus:  'ComputationalReproducibility',
            time_cap_secs:     3600,
            compensation_tier: { Tier1: { amount_pence: 5000 } },
          },
        );

        // post_commit fires notify_commitment_sealed → CommitmentAnchor on DNA 3.
        await call(
          'validator_workspace', 'validator_workspace_coordinator', 'seal_private_attestation',
          { task_hash: taskHashSerialized, attestation: va },
        );

        // Retrieve nonce from the private entry for use in reveal.
        const privateRecord = await call(
          'validator_workspace', 'validator_workspace_coordinator',
          'get_private_attestation_for_task', taskHashSerialized,
        );
        if (!privateRecord) throw new Error('get_private_attestation_for_task returned null');

        const { decode: msgpackDecode } = await import('@msgpack/msgpack');
        const privB64 = privateRecord?.entry?.Present?.entry?.__bytes ?? null;
        if (!privB64) throw new Error('ValidatorPrivateAttestation entry bytes not found');
        const privateAttestation = msgpackDecode(Buffer.from(privB64, 'base64'));
        nonce = privateAttestation.nonce;
      });

      tasks.set(body.external_hash_b64, { taskHash: taskHashSerialized, nonce, va });

      console.log(`[/commit] sealed commitment for ${body.external_hash_b64.slice(0, 20)}…`);
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true }));
    } catch (err) {
      console.error('[/commit]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ── POST /reveal ────────────────────────────────────────────────────────────
  // Calls submit_attestation which recomputes SHA-256(msgpack(attestation) || nonce)
  // on-chain and verifies it against CommitmentAnchor.commitment_hash.
  //
  // Body:   { external_hash_b64 }
  // Returns { ok: true }
  if (req.method === 'POST' && url === '/reveal') {
    let body;
    try { body = JSON.parse(await readBody(req)); }
    catch { res.writeHead(400); res.end(JSON.stringify({ error: 'Invalid JSON' })); return; }

    const task = tasks.get(body.external_hash_b64);
    if (!task) {
      res.writeHead(400);
      res.end(JSON.stringify({ error: `No committed task for ${body.external_hash_b64}` }));
      return;
    }

    try {
      await withSession(async ({ call }) => {
        await call('attestation', 'attestation_coordinator', 'submit_attestation', {
          attestation: task.va,
          nonce:       task.nonce,
        });
      });

      console.log(`[/reveal] attestation submitted for ${body.external_hash_b64.slice(0, 20)}…`);
      res.writeHead(200);
      res.end(JSON.stringify({ ok: true }));
    } catch (err) {
      console.error('[/reveal]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  // ── POST /create-harmony-record ─────────────────────────────────────────────
  // Calls check_and_create_harmony_record on the Governance DHT.
  // Must be called by a participating validator — governance integrity requires
  // the HarmonyRecord author to be listed in participating_validators.
  //
  // Body:   { external_hash_b64 }
  // Returns { harmony_record_hash: string | null }
  if (req.method === 'POST' && url === '/create-harmony-record') {
    let body;
    try { body = JSON.parse(await readBody(req)); }
    catch { res.writeHead(400); res.end(JSON.stringify({ error: 'Invalid JSON' })); return; }

    try {
      const hashBytes = externalHashFromB64(body.external_hash_b64);
      const { encodeHashToBase64 } = await loadHcClient();

      // Retry until attestations have gossiped to this node (up to 60s).
      let harmonyRecordHash = null;
      for (let attempt = 0; attempt < 12 && harmonyRecordHash === null; attempt++) {
        if (attempt > 0) await new Promise(r => setTimeout(r, 5000));
        const result = await withSession(async ({ call }) => {
          return call(
            'governance', 'governance_coordinator',
            'check_and_create_harmony_record', hashBytes,
          );
        });
        harmonyRecordHash = result?.__bytes
          ? encodeHashToBase64(Buffer.from(result.__bytes, 'base64'))
          : null;
        console.log(`[/create-harmony-record] attempt ${attempt + 1}: ${harmonyRecordHash?.slice(0, 20) ?? 'null'}`);
      }

      console.log(`[/create-harmony-record] final hash: ${harmonyRecordHash?.slice(0, 20) ?? 'null'}…`);
      res.writeHead(200);
      res.end(JSON.stringify({ harmony_record_hash: harmonyRecordHash }));
    } catch (err) {
      console.error('[/create-harmony-record]', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Validator node API → http://0.0.0.0:${PORT}`);
});
