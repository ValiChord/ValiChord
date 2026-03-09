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
 *   We use `scenario.addPlayers(n)` to register keys in lair FIRST, then read
 *   adminPlayer.agentPubKey and bake it into governance DNA properties, then
 *   call `scenario.installAppsForPlayers(configs, players)`.
 *
 * Key note on get_attestations_for_request:
 *   This function discovers validators via CommitmentAnchor entries on the
 *   "commitments.{request_ref}" path, created by notify_commitment_sealed.
 *   Tests must call notify_commitment_sealed before submit_attestation so the
 *   coordinator can find attestations for the request.
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
 * Do NOT pass agentPubKey here — use addPlayers + installAppsForPlayers
 * so the key is pre-registered in lair before installation.
 */
function makePlayerConfig(adminKeyB64: string) {
  return {
    appBundleSource: {
      type: "path" as const,
      value: HAPP_PATH,
    },
    options: {
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

/** callZome helper. */
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

/** Return the DNA hash for a given role via namedCells map. */
function dnaHashForRole(player: any, roleName: string): Uint8Array {
  return player.namedCells?.get(roleName)?.cell_id[0];
}

// ---------------------------------------------------------------------------
// 1. Idempotency
// ---------------------------------------------------------------------------

describe("1. check_and_create_harmony_record idempotency", () => {
  test(
    "two calls for the same request_ref with no attestations both return null",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Step 1: create conductor + register key in lair.
        const [adminPlayer] = await scenario.addPlayers(1);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        // Step 2: install happ with governance DNA properties matching admin key.
        const [admin] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64)],
          [adminPlayer],
        );

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
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "second call short-circuits when HarmonyRecord already exists",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [adminPlayer, bobPlayer] = await scenario.addPlayers(2);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        const [admin, bob] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64), makePlayerConfig(adminKeyB64)],
          [adminPlayer, bobPlayer],
        );

        const attDnaHash = dnaHashForRole(admin, "attestation");

        // Use a consistent request_ref for all protocol steps.
        const requestRef = fakeExternalHash(0x11);

        // Both validators commit (creates CommitmentAnchors so get_attestations_for_request works).
        await att(admin, "notify_commitment_sealed", requestRef);
        await att(bob,   "notify_commitment_sealed", requestRef);

        // Sync attestation DHT — CommitmentAnchors must be visible before
        // get_attestations_for_request can discover validator keys.
        await dhtSync([admin, bob], attDnaHash);

        // Both validators reveal (creates ValidatorToAttestation links).
        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));

        await dhtSync([admin, bob], attDnaHash);

        // First call: both CommitmentAnchors + attestations present → HarmonyRecord created.
        const first = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(first).not.toBeNull();

        // Second call: RequestToHarmonyRecord link already on admin's DHT → null.
        const second = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(second).toBeNull();

        // Exactly one record visible.
        const record = await gov(admin, "get_harmony_record", requestRef);
        expect(record).not.toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 2. Author enforcement
// ---------------------------------------------------------------------------

describe("2. Author enforcement", () => {
  test(
    "HarmonyRecord creation from non-creator key is rejected by validate()",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Alice joins with the PLACEHOLDER key (which is not her real key).
        // Any governance write must be rejected.
        const [alicePlayer] = await scenario.addPlayers(1);
        const [alice] = await scenario.installAppsForPlayers(
          [makePlayerConfig(PLACEHOLDER_KEY)],
          [alicePlayer],
        );

        const requestRef = fakeExternalHash(0x10);

        // Submit one attestation (but only 1, so we have data; we test governance directly).
        await att(alice, "notify_commitment_sealed", requestRef);
        await att(alice, "submit_attestation", makeAttestation(requestRef));
        await pause(300);

        // Alice's key != harmony_record_creator_key → validate() must reject.
        await expect(
          gov(alice, "check_and_create_harmony_record", requestRef),
        ).rejects.toThrow();
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "agent key does not equal placeholder key (validate() precondition)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alicePlayer] = await scenario.addPlayers(1);
        const [alice] = await scenario.installAppsForPlayers(
          [makePlayerConfig(PLACEHOLDER_KEY)],
          [alicePlayer],
        );
        // Sanity-check: the test relies on alice's actual key being different
        // from the placeholder so validate() fires correctly.
        expect(encodeHashToBase64(alice.agentPubKey)).not.toBe(PLACEHOLDER_KEY);
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 3. Full end-to-end round (all four DNAs)
// ---------------------------------------------------------------------------

describe("3. Full end-to-end round", () => {
  test(
    "researcher → request → validator attestations → HarmonyRecord on public DHT",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Pre-register admin key in lair, then bake it into governance DNA props.
        const [adminPlayer, bobPlayer] = await scenario.addPlayers(2);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        const [admin, bob] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64), makePlayerConfig(adminKeyB64)],
          [adminPlayer, bobPlayer],
        );

        const attDnaHash = dnaHashForRole(admin, "attestation");

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

        // Use a consistent fake request_ref for the commit-reveal protocol.
        // (In production this would be the actual ExternalHash of the study.)
        const requestRef = fakeExternalHash(0xcc);

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
        //    Sync between commits so bob sees admin's CommitmentAnchor when
        //    check_all_commitments_sealed_inner counts links (≥2 → PhaseMarker).
        await att(admin, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob], attDnaHash);

        await att(bob, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob], attDnaHash);

        // 5. PhaseMarker(RevealOpen) should now be on the DHT.
        const phase = await att(admin, "get_current_phase", requestRef);
        expect(phase).toBe("RevealOpen");

        // 6. Both validators submit public attestations to DNA 3.
        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));

        await dhtSync([admin, bob], attDnaHash);

        // 7. Admin manually triggers governance record assembly.
        //    post_commit no longer calls governance (would deadlock: attestation
        //    post_commit → governance → attestation.get_attestations_for_request
        //    re-entry). The coordinator calls this explicitly instead.
        const harmonyHash = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(harmonyHash).not.toBeNull();

        await pause(500);

        // 8. HarmonyRecord is visible on the public DHT.
        const harmonyRecord = await gov(admin, "get_harmony_record", requestRef);
        expect(harmonyRecord).not.toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 4. ValidatorReputation author enforcement
// ---------------------------------------------------------------------------

describe("4. ValidatorReputation author enforcement", () => {
  test(
    "reputation update from non-coordinator key is rejected by validate()",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alicePlayer] = await scenario.addPlayers(1);
        const [alice] = await scenario.installAppsForPlayers(
          [makePlayerConfig(PLACEHOLDER_KEY)],
          [alicePlayer],
        );

        // Alice's key != system_coordinator_key → validate() must reject.
        await expect(
          gov(alice, "update_validator_reputation", {
            validator: alice.agentPubKey,
            discipline: { type: "ComputationalBiology" },
            outcome: { type: "Reproduced" },
            time_invested_secs: 3600,
          }),
        ).rejects.toThrow();
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "reputation update from system_coordinator_key is accepted",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [adminPlayer] = await scenario.addPlayers(1);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        const [admin] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64)],
          [adminPlayer],
        );

        const repHash = await gov(admin, "update_validator_reputation", {
          validator: admin.agentPubKey,
          discipline: { type: "ComputationalBiology" },
          outcome: { type: "Reproduced" },
          time_invested_secs: 3600,
        });
        expect(repHash).not.toBeNull();

        const rep = await gov(admin, "get_validator_reputation", admin.agentPubKey);
        expect(rep).not.toBeNull();
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 5. Read queries — get_harmony_records_by_discipline + get_badges_for_study
// ---------------------------------------------------------------------------

describe("5. Read queries", () => {
  test(
    "get_harmony_records_by_discipline returns the record after creation",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [adminPlayer, bobPlayer] = await scenario.addPlayers(2);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        const [admin, bob] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64), makePlayerConfig(adminKeyB64)],
          [adminPlayer, bobPlayer],
        );

        const attDnaHash = dnaHashForRole(admin, "attestation");
        const requestRef = fakeExternalHash(0x55);

        // Both validators commit then reveal.
        await att(admin, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob], attDnaHash);

        await att(bob, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob], attDnaHash);

        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));
        await dhtSync([admin, bob], attDnaHash);

        // Create the HarmonyRecord.
        const harmonyHash = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(harmonyHash).not.toBeNull();

        await dhtSync([admin, bob], dnaHashForRole(admin, "governance"));

        // Query by discipline — should return exactly one record.
        const records = await gov(
          admin,
          "get_harmony_records_by_discipline",
          { type: "ComputationalBiology" },
        );
        expect(records).toHaveLength(1);
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "get_harmony_records_by_discipline returns empty array when no records exist",
    { timeout: 180_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [adminPlayer] = await scenario.addPlayers(1);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);
        const [admin] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64)],
          [adminPlayer],
        );

        // No HarmonyRecords have been created — should return empty.
        const records = await gov(
          admin,
          "get_harmony_records_by_discipline",
          { type: "ComputationalBiology" },
        );
        expect(records).toHaveLength(0);
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "get_badges_for_study returns empty when validator count < 3 (no badge threshold met)",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [adminPlayer, bobPlayer] = await scenario.addPlayers(2);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        const [admin, bob] = await scenario.installAppsForPlayers(
          [makePlayerConfig(adminKeyB64), makePlayerConfig(adminKeyB64)],
          [adminPlayer, bobPlayer],
        );

        const attDnaHash = dnaHashForRole(admin, "attestation");
        const requestRef = fakeExternalHash(0x66);

        // Two validators commit and reveal (ExactMatch outcome).
        await att(admin, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob], attDnaHash);

        await att(bob, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob], attDnaHash);

        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));
        await dhtSync([admin, bob], attDnaHash);

        // Create HarmonyRecord — 2 validators, ExactMatch.
        // evaluate_badge: ExactMatch + count=2 → None (Bronze requires >= 3).
        const harmonyHash = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(harmonyHash).not.toBeNull();

        // No badge should be linked — count too low for any tier.
        const badges = await gov(admin, "get_badges_for_study", requestRef);
        expect(badges).toHaveLength(0);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 6. Badge positive case — Bronze (3 validators, all Reproduced)
// ---------------------------------------------------------------------------
//
// evaluate_badge thresholds (from governance_coordinator):
//   ExactMatch  + count >= 7  → GoldReproducible
//   ExactMatch  + count >= 5  → SilverReproducible
//   ExactMatch  + count >= 3  → BronzeReproducible
//   Divergent / UnableToAssess (any count) → FailedReproduction
//
// With 3 validators all returning Reproduced:
//   derive_agreement_level: rate = 3/3 = 1.0 → ExactMatch
//   evaluate_badge: ExactMatch + 3 → BronzeReproducible

describe("6. Badge positive case", () => {
  test(
    "get_badges_for_study returns BronzeReproducible when 3 validators all Reproduced",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [adminPlayer, bobPlayer, carolPlayer] = await scenario.addPlayers(3);
        const adminKeyB64 = encodeHashToBase64(adminPlayer.agentPubKey);

        const [admin, bob, carol] = await scenario.installAppsForPlayers(
          [
            makePlayerConfig(adminKeyB64),
            makePlayerConfig(adminKeyB64),
            makePlayerConfig(adminKeyB64),
          ],
          [adminPlayer, bobPlayer, carolPlayer],
        );

        const attDnaHash = dnaHashForRole(admin, "attestation");
        // Use a unique requestRef not shared with any other test.
        const requestRef = fakeExternalHash(0xb1);

        // All three validators commit.
        // minimum_validators=2, so the PhaseMarker is written after the 2nd commit.
        // The 3rd commit also succeeds — a second PhaseMarker is written (harmless,
        // get_current_phase uses links.last()). All three CommitmentAnchors are needed
        // so get_attestations_for_request can discover all three attestations.
        await att(admin, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob, carol], attDnaHash);

        await att(bob, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob, carol], attDnaHash);

        await att(carol, "notify_commitment_sealed", requestRef);
        await dhtSync([admin, bob, carol], attDnaHash);

        // All three reveal with Reproduced outcome.
        await att(admin, "submit_attestation", makeAttestation(requestRef));
        await att(bob,   "submit_attestation", makeAttestation(requestRef));
        await att(carol, "submit_attestation", makeAttestation(requestRef));
        await dhtSync([admin, bob, carol], attDnaHash);

        // check_and_create_harmony_record sees 3 attestations:
        //   rate=1.0 → ExactMatch; count=3 → BronzeReproducible.
        const harmonyHash = await gov(admin, "check_and_create_harmony_record", requestRef);
        expect(harmonyHash).not.toBeNull();

        await dhtSync([admin, bob, carol], dnaHashForRole(admin, "governance"));

        // Exactly one badge should be linked to this study_ref.
        const badges = await gov(admin, "get_badges_for_study", requestRef);
        expect(badges).toHaveLength(1);
      }, true, { timeout: 300_000 });
    },
  );
});
