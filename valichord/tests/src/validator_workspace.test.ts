/**
 * Tryorama integration tests for ValiChord DNA 2 — Validator Workspace
 *
 * All entries are private (visibility = "private") — single-agent source
 * chain only. No dhtSync needed. Single player, local GetOptions.
 *
 * Note: seal_private_attestation post_commit fires a cross-DNA call to
 * attestation.notify_commitment_sealed. With minimum_validators=2 and only
 * one validator, the CommitmentAnchor count stays at 1 — no PhaseMarker is
 * written. The post_commit is infallible so failures are silently logged.
 *
 * Tests:
 *   1. receive_task + get_task
 *   2. seal_private_attestation + get_private_attestation_for_task
 *   3. get_all_tasks
 *
 * Run: cd tests && npm test
 */

import { runScenario } from "@holochain/tryorama";
import { ActionHash, HoloHashType, hashFrom32AndType, encodeHashToBase64 } from "@holochain/client";
import { expect, test, describe } from "vitest";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HAPP_PATH = path.join(__dirname, "../../workdir/valichord.happ");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Empty string = dev bypass in verify_membrane_proof (skips Ed25519 check).
const PLACEHOLDER_KEY = "";

function simplePlayerConfig() {
  return {
    appBundleSource: { type: "path" as const, value: HAPP_PATH },
    options: {
      rolesSettings: {
        attestation: {
          type: "provisioned" as const,
          value: {
            membrane_proof: new Uint8Array(64).fill(0x42),
            modifiers: {
              properties: {
                minimum_validators: 2,
                discipline: "genomics",
                authorized_joining_certificate_issuer: PLACEHOLDER_KEY,
              },
            },
          },
        },
        governance: {
          type: "provisioned" as const,
          value: {
            modifiers: {
              properties: {
                system_coordinator_key: PLACEHOLDER_KEY,
                harmony_record_creator_key: PLACEHOLDER_KEY,
              },
            },
          },
        },
      },
    },
  };
}

function fakeExternalHash(coreByte: number): Uint8Array {
  const core = new Uint8Array(32).fill(coreByte);
  return hashFrom32AndType(core, HoloHashType.External);
}

function fakeActionHash(coreByte: number): Uint8Array {
  const core = new Uint8Array(32).fill(coreByte);
  return hashFrom32AndType(core, HoloHashType.Action);
}

async function ws(player: any, fn: string, payload: unknown = null): Promise<any> {
  return player.appWs.callZome({
    role_name: "validator_workspace",
    zome_name: "validator_workspace_coordinator",
    fn_name: fn,
    payload,
  });
}

/**
 * A minimal ValidationTask payload.
 *
 * ValidationFocus: no serde tag → external tag → unit variant = plain string.
 * CompensationTier: no serde tag → external tag → struct variant = { "Tier1": { amount_pence: N } }.
 * Discipline: #[serde(tag="type", content="content")] → { "type": "VariantName" } for unit variants.
 */
function makeTask(requestRef: Uint8Array, overrides?: Record<string, unknown>) {
  return {
    request_ref: requestRef,
    discipline: { type: "ComputationalBiology" },
    deadline_secs: 1_700_100_000,
    validation_focus: "ComputationalReproducibility",
    time_cap_secs: 86_400,
    compensation_tier: { Tier1: { amount_pence: 5_000 } },
    ...overrides,
  };
}

/**
 * A minimal ValidatorPrivateAttestation payload.
 *
 * AttestationOutcome: #[serde(tag="type", content="content")] — adjacent-tagged.
 *   Unit variant Reproduced → { "type": "Reproduced" } (no content key needed).
 * AttestationConfidence: no serde tag → external tag → plain string.
 */
function makePrivateAttestation(requestRef: Uint8Array) {
  return {
    request_ref: requestRef,
    outcome: { type: "Reproduced" },
    outcome_summary: {
      key_metrics: [],
      effect_direction_matches: null,
      confidence_interval_overlap: null,
      overall_agreement: "ExactMatch",
    },
    time_invested_secs: 3_600,
    time_breakdown: {
      environment_setup_secs: 900,
      data_acquisition_secs:  600,
      code_execution_secs:    1_800,
      troubleshooting_secs:   300,
    },
    deviation_flags: [],
    computational_resources: {
      personal_hardware_sufficient:  true,
      hpc_required:                  false,
      gpu_required:                  false,
      cloud_compute_required:        false,
      estimated_compute_cost_pence:  null,
    },
    confidence: "High",
  };
}

// ---------------------------------------------------------------------------
// 1. receive_task + get_task
// ---------------------------------------------------------------------------

describe("1. receive_task + get_task", () => {
  test(
    "received task is retrievable by its ActionHash",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const REQUEST_REF = fakeExternalHash(0xaa);
        const taskHash = await ws(alice, "receive_task", makeTask(REQUEST_REF));
        expect(taskHash).toBeTruthy();

        const record = await ws(alice, "get_task", taskHash);
        expect(record).not.toBeNull();
      }, true, { timeout: 900_000 });
    },
  );

  test(
    "get_task returns null for an unknown ActionHash",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        // A properly-typed ActionHash that was never written to the source chain.
        const unknownHash = fakeActionHash(0xff);
        const result = await ws(alice, "get_task", unknownHash);
        expect(result).toBeNull();
      }, true, { timeout: 900_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 2. seal_private_attestation + get_private_attestation_for_task
// ---------------------------------------------------------------------------

describe("2. seal_private_attestation + get_private_attestation_for_task", () => {
  test(
    "sealed private attestation is retrievable via its parent task",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const REQUEST_REF = fakeExternalHash(0xbb);

        // Step 1: receive the task.
        const taskHash = await ws(alice, "receive_task", makeTask(REQUEST_REF));
        expect(taskHash).toBeTruthy();

        // Step 2: seal the private attestation.
        // post_commit fires notify_commitment_sealed on the attestation DNA
        // (infallible — any failure is silently logged).
        const attestationHash = await ws(alice, "seal_private_attestation", {
          task_hash: taskHash,
          attestation: makePrivateAttestation(REQUEST_REF),
        });
        expect(attestationHash).toBeTruthy();

        // Step 3: retrieve via task link.
        const record = await ws(alice, "get_private_attestation_for_task", taskHash);
        expect(record).not.toBeNull();
      }, true, { timeout: 900_000 });
    },
  );

  test(
    "get_private_attestation_for_task returns null before any attestation is sealed",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const REQUEST_REF = fakeExternalHash(0xcc);
        const taskHash = await ws(alice, "receive_task", makeTask(REQUEST_REF));

        const result = await ws(alice, "get_private_attestation_for_task", taskHash);
        expect(result).toBeNull();
      }, true, { timeout: 900_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 3. get_all_tasks
// ---------------------------------------------------------------------------

describe("3. get_all_tasks", () => {
  test(
    "returns all received tasks from the local source chain",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        // No tasks yet.
        const emptyResult = await ws(alice, "get_all_tasks", null);
        expect(emptyResult).toHaveLength(0);

        // Receive three tasks with different request_refs.
        await ws(alice, "receive_task", makeTask(fakeExternalHash(0x01)));
        await ws(alice, "receive_task", makeTask(fakeExternalHash(0x02)));
        await ws(alice, "receive_task", makeTask(fakeExternalHash(0x03)));

        const tasks = await ws(alice, "get_all_tasks", null);
        expect(tasks).toHaveLength(3);
      }, true, { timeout: 900_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 4. get_all_private_attestations
// ---------------------------------------------------------------------------
//
// get_all_private_attestations was missing — no way to list sealed
// attestations without knowing every attestation ActionHash in advance.
// Uses query() + deserialization filter, identical pattern to get_all_tasks.

describe("4. get_all_private_attestations", () => {
  test(
    "returns empty list when no attestations sealed",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const attestations = await ws(alice, "get_all_private_attestations", null);
        expect(attestations).toHaveLength(0);
      }, true, { timeout: 900_000 });
    },
  );

  test(
    "returns all sealed attestations across multiple tasks",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const task1Hash = await ws(alice, "receive_task", makeTask(fakeExternalHash(0x01)));
        const task2Hash = await ws(alice, "receive_task", makeTask(fakeExternalHash(0x02)));

        await ws(alice, "seal_private_attestation", {
          task_hash: task1Hash,
          attestation: makePrivateAttestation(fakeExternalHash(0x01)),
        });
        await ws(alice, "seal_private_attestation", {
          task_hash: task2Hash,
          attestation: makePrivateAttestation(fakeExternalHash(0x02)),
        });

        const attestations = await ws(alice, "get_all_private_attestations", null);
        expect(attestations).toHaveLength(2);

        // All ActionHashes must be distinct.
        const hashes = (attestations as any[]).map((r: any) =>
          Buffer.from(r?.signed_action?.hashed?.hash as Uint8Array).toString("base64"),
        );
        expect(new Set(hashes).size).toBe(2);
      }, true, { timeout: 900_000 });
    },
  );
});
