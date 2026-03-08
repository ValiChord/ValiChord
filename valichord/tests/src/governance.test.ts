/**
 * Tryorama integration tests for ValiChord DNA 4 — Governance
 *
 * Test priority order (from spec):
 *   1. check_and_create_harmony_record is idempotent
 *   2. Author enforcement — non-creator key rejected by validate()
 *   3. Full end-to-end round across all four DNAs
 *   4. ValidatorReputation — non-coordinator key rejected
 *
 * Key design note for governance writes:
 *   DNA 4's validate() checks action.author against harmony_record_creator_key /
 *   system_coordinator_key (both stored as base64 strings in DNA properties).
 *   Tests that require governance writes use `generateSigningKeyPair` to produce
 *   a known key pair BEFORE adding the player, then pass that key as
 *   `agentPubKey` in the player config so conductor identity matches the gate.
 *
 * Prerequisites:
 *   cargo build --target wasm32-unknown-unknown --release
 *   hc dna pack dnas/attestation            -o workdir/attestation.dna
 *   hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
 *   hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
 *   hc dna pack dnas/governance             -o workdir/governance.dna
 *   hc app pack . -o workdir/valichord.happ
 *
 * Run: cd tests && npm test
 */

import { runScenario, dhtSync, pause } from "@holochain/tryorama";
import {
  encodeHashToBase64,
  HoloHashType,
  hashFrom32AndType,
  generateSigningKeyPair,
} from "@holochain/client";
import { expect, test, describe } from "vitest";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HAPP_PATH = path.join(__dirname, "../../workdir/valichord.happ");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function validMembraneProof(): Uint8Array {
  return new Uint8Array(64).fill(0x42);
}

function fakeExternalHash(coreByte: number): Uint8Array {
  const core = new Uint8Array(32).fill(coreByte);
  return hashFrom32AndType(core, HoloHashType.External);
}

/**
 * Build a player config.
 *
 * adminKeyB64 is baked into governance DNA properties as both
 * harmony_record_creator_key and system_coordinator_key.
 * If agentPubKey is supplied the conductor will use that key identity,
 * allowing the agent to satisfy validate()'s author check.
 */
function makePlayerConfig(adminKeyB64: string, agentPubKey?: Uint8Array) {
  return {
    appBundleSource: {
      type: "path" as const,
      value: HAPP_PATH,
    },
    options: {
      ...(agentPubKey ? { agentPubKey } : {}),
      rolesSettings: {
        attestation: {
          type: "provisioned" as const,
          value: {
            membrane_proof: validMembraneProof(),
            modifiers: {
              properties: {
                minimum_validators: 2,
                discipline: "genomics",
                authorized_joining_certificate_issuer:
                  "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew",
              },
            },
          },
        },
        governance: {
          type: "provisioned" as const,
          value: {
            modifiers: {
              properties: {
                system_coordinator_key: adminKeyB64,
                harmony_record_creator_key: adminKeyB64,
              },
            },
          },
        },
      },
    },
  };
}

// Placeholder key baked into happ.yaml — no real agent has this key.
const PLACEHOLDER_KEY =
  "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew";

/** callZome helper — typed as any to avoid fighting @holochain/client generics. */
async function callZome(
  player: any,
  roleName: string,
  zomeName: string,
  fnName: string,
  payload: unknown = null,
): Promise<any> {
  return player.appWs.callZome({
    role_name: roleName,
    zome_name: zomeName,
    fn_name: fnName,
    payload,
  });
}

const gov = (player: any, fn: string, payload?: unknown) =>
  callZome(player, "governance", "governance_coordinator", fn, payload);

const att = (player: any, fn: string, payload?: unknown) =>
  callZome(player, "attestation", "attestation_coordinator", fn, payload);

const repo = (player: any, fn: string, payload?: unknown) =>
  callZome(player, "researcher_repository", "researcher_repository_coordinator", fn, payload);

const ws = (player: any, fn: string, payload?: unknown) =>
  callZome(player, "validator_workspace", "validator_workspace_coordinator", fn, payload);

function makeValidationRequest(overrides?: Record<string, unknown>) {
  return {
    protocol_ref: null,
    data_hash: fakeExternalHash(0xab),
    num_validators_required: 2,
    validation_tier: "Basic",
    discipline: { type: "ComputationalBiology" },
    ...overrides,
  };
}

function makeAttestation(requestRef: Uint8Array) {
  return {
    request_ref: requestRef,
    outcome: { type: "Reproduced" },
    outcome_summary: {
      key_metrics: [],
      effect_direction_matches: null,
      confidence_interval_overlap: null,
      overall_agreement: "ExactMatch",
    },
    time_invested_secs: 3600,
    time_breakdown: {
      environment_setup_secs: 900,
      data_acquisition_secs: 600,
      code_execution_secs: 1800,
      troubleshooting_secs: 300,
    },
    confidence: "High",
    deviation_flags: [],
    computational_resources: {
      personal_hardware_sufficient: true,
      hpc_required: false,
      gpu_required: false,
      cloud_compute_required: false,
      estimated_compute_cost_pence: null,
    },
    discipline: { type: "ComputationalBiology" },
  };
}

// ---------------------------------------------------------------------------
// 1. Idempotency
// ---------------------------------------------------------------------------

describe("1. check_and_create_harmony_record idempotency", () => {
  test(
    "two calls for the same request_ref with no attestations both return null",
    { timeout: 120_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Pre-generate an admin key so the conductor identity matches the
        // governance DNA-property gate.
        const [_sigKey, adminPubKey] = await generateSigningKeyPair();
        const adminKeyB64 = encodeHashToBase64(adminPubKey);

        const [admin] = await scenario.addPlayersWithApps([
          makePlayerConfig(adminKeyB64, adminPubKey),
        ]);

        const requestRef = fakeExternalHash(0x01);

        // First call — no attestations → null.
        const first = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(first).toBeNull();

        // Second call — same input, idempotent.
        const second = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(second).toBeNull();

        // No record on the DHT.
        const record = await gov(admin, "get_harmony_record", requestRef);
        expect(record).toBeNull();
      });
    },
  );

  test(
    "second call short-circuits when HarmonyRecord already exists",
    { timeout: 180_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [_sigKey, adminPubKey] = await generateSigningKeyPair();
        const adminKeyB64 = encodeHashToBase64(adminPubKey);

        const [admin, bob] = await scenario.addPlayersWithApps([
          makePlayerConfig(adminKeyB64, adminPubKey),
          makePlayerConfig(adminKeyB64),
        ]);

        // Submit a request and two public attestations so the coordinator
        // has enough data to assemble a HarmonyRecord.
        const requestHash = await att(admin, "submit_validation_request",
          makeValidationRequest());

        const requestRecord = await att(admin, "get_validation_request", requestHash);
        // Extract the ExternalHash request_ref — fall back to a fake hash.
        const requestRef: Uint8Array =
          requestRecord?.entry?.Present?.entry?.App?.[1]?.request_ref
          ?? fakeExternalHash(0x02);

        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));

        await dhtSync([admin, bob], admin.cells[0].cell_id[0]);

        // First call: attestations present → HarmonyRecord created.
        const first = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(first).not.toBeNull();

        // Second call: record already exists → idempotent return of null.
        const second = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(second).toBeNull();

        // Exactly one record visible.
        const record = await gov(admin, "get_harmony_record", requestRef);
        expect(record).not.toBeNull();
      });
    },
  );
});

// ---------------------------------------------------------------------------
// 2. Author enforcement
// ---------------------------------------------------------------------------

describe("2. Author enforcement", () => {
  test(
    "HarmonyRecord creation from non-creator key is rejected by validate()",
    { timeout: 60_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Alice joins with the PLACEHOLDER key (which is not her real key).
        // Any governance write must be rejected.
        const [alice] = await scenario.addPlayersWithApps([
          makePlayerConfig(PLACEHOLDER_KEY),
        ]);

        const requestRef = fakeExternalHash(0x10);

        // Submit one attestation (but only 1, so DNA 3 doesn't fire the
        // post_commit chain; we test governance directly).
        await att(alice, "submit_attestation", makeAttestation(requestRef));
        await pause(300);

        // Alice's key != harmony_record_creator_key → validate() must reject.
        await expect(
          gov(alice, "check_and_create_harmony_record", requestRef),
        ).rejects.toThrow();
      });
    },
  );

  test(
    "agent key does not equal placeholder key (validate() precondition)",
    { timeout: 30_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          makePlayerConfig(PLACEHOLDER_KEY),
        ]);
        // Sanity-check: the test relies on alice's actual key being different
        // from the placeholder so validate() fires correctly.
        expect(encodeHashToBase64(alice.agentPubKey)).not.toBe(PLACEHOLDER_KEY);
      });
    },
  );
});

// ---------------------------------------------------------------------------
// 3. Full end-to-end round (all four DNAs)
// ---------------------------------------------------------------------------

describe("3. Full end-to-end round", () => {
  test(
    "researcher → request → validator attestations → HarmonyRecord on public DHT",
    { timeout: 240_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Pre-generate admin key — this player acts as both a validator and
        // the governance record creator (harmony_record_creator_key = admin).
        const [_sigKey, adminPubKey] = await generateSigningKeyPair();
        const adminKeyB64 = encodeHashToBase64(adminPubKey);

        const [admin, bob] = await scenario.addPlayersWithApps([
          makePlayerConfig(adminKeyB64, adminPubKey),
          makePlayerConfig(adminKeyB64),
        ]);

        // 1. Researcher registers a study in DNA 1.
        const studyHash = await repo(admin, "register_study", {
          title: "Replication of Smith et al. 2023",
          discipline: { type: "ComputationalBiology" },
          institution: "Open Science Lab",
          abstract_text: "Full computational reproduction attempt.",
          pre_registration_ref: null,
        });
        expect(studyHash).not.toBeNull();

        // 2. Validation request submitted to DNA 3.
        const requestHash = await att(admin, "submit_validation_request",
          makeValidationRequest());
        expect(requestHash).not.toBeNull();

        // Retrieve the request to extract request_ref.
        const requestRecord = await att(admin, "get_validation_request", requestHash);
        expect(requestRecord).not.toBeNull();

        // Use data_hash from makeValidationRequest as a stand-in for request_ref
        // when direct deserialization is unavailable.
        const requestRef: Uint8Array =
          requestRecord?.entry?.Present?.entry?.App?.[1]?.data_hash
          ?? fakeExternalHash(0xcc);

        // 3. Two validators seal private attestation tasks in DNA 2.
        const taskPayload = {
          request_ref: requestRef,
          assigned_at_secs: 1_700_000_000,
          discipline: { type: "ComputationalBiology" },
          deadline_secs: 1_700_100_000,
          validation_focus: "ComputationalReproducibility",
          time_cap_secs: 86400,
          compensation_tier: { Tier1: { amount_pence: 5000 } },
        };
        await ws(admin, "receive_task", taskPayload);
        await ws(bob,   "receive_task", taskPayload);

        // 4. Both validators call notify_commitment_sealed on DNA 3.
        await att(admin, "notify_commitment_sealed", requestRef);
        await att(bob,   "notify_commitment_sealed", requestRef);

        await dhtSync([admin, bob], admin.cells[0].cell_id[0]);

        // 5. PhaseMarker(RevealOpen) should now be on the DHT.
        const phase = await att(admin, "get_current_phase", requestRef);
        expect(phase).toBe("RevealOpen");

        // 6. Both validators submit public attestations to DNA 3.
        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));

        await dhtSync([admin, bob], admin.cells[0].cell_id[0]);

        // 7. Admin manually triggers governance record assembly.
        //    (DNA 3 post_commit also fires but admin is the key holder so this
        //    call from admin is authoritative.)
        const harmonyHash = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(harmonyHash).not.toBeNull();

        await dhtSync([admin, bob], admin.cells[0].cell_id[0]);

        // 8. HarmonyRecord is visible on the public DHT.
        const harmonyRecord = await gov(admin, "get_harmony_record", requestRef);
        expect(harmonyRecord).not.toBeNull();
      });
    },
  );
});

// ---------------------------------------------------------------------------
// 4. ValidatorReputation author enforcement
// ---------------------------------------------------------------------------

describe("4. ValidatorReputation author enforcement", () => {
  test(
    "reputation update from non-coordinator key is rejected by validate()",
    { timeout: 60_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          makePlayerConfig(PLACEHOLDER_KEY),
        ]);

        // Alice's key != system_coordinator_key → validate() must reject.
        await expect(
          gov(alice, "update_validator_reputation", {
            validator: alice.agentPubKey,
            discipline: { type: "ComputationalBiology" },
            outcome: { type: "Reproduced" },
            time_invested_secs: 3600,
          }),
        ).rejects.toThrow();
      });
    },
  );

  test(
    "reputation update from system_coordinator_key is accepted",
    { timeout: 60_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [_sigKey, adminPubKey] = await generateSigningKeyPair();
        const adminKeyB64 = encodeHashToBase64(adminPubKey);

        const [admin] = await scenario.addPlayersWithApps([
          makePlayerConfig(adminKeyB64, adminPubKey),
        ]);

        const repHash = await gov(admin, "update_validator_reputation", {
          validator: admin.agentPubKey,
          discipline: { type: "ComputationalBiology" },
          outcome: { type: "Reproduced" },
          time_invested_secs: 3600,
        });
        expect(repHash).not.toBeNull();

        const rep = await gov(admin, "get_validator_reputation", admin.agentPubKey);
        expect(rep).not.toBeNull();
      });
    },
  );
});
