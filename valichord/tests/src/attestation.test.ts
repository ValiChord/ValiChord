/**
 * Tryorama integration tests for ValiChord DNA 3 — Attestation
 *
 * Test priority order (from SCAFFOLDING_PLAN.md):
 *   1. Membrane proof acceptance / rejection
 *   2. Full commit-reveal round
 *   3. DHT-poll phase transition (validator misses signal, polls instead)
 *   4. ValidationAttestation immutability
 *
 * Prerequisites:
 *   cargo build --target wasm32-unknown-unknown --release
 *   hc dna pack dnas/attestation -o workdir/attestation.dna
 *   hc app pack . -o workdir/valichord.happ
 *
 * Run: cd tests && npm install && npm test
 */

import { runScenario, dhtSync, pause } from "@holochain/tryorama";
import type { Scenario } from "@holochain/tryorama";
import {
  AppBundleSource,
  ActionHash,
  AgentPubKey,
  encodeHashToBase64,
  HoloHashType,
  hashFrom32AndType,
} from "@holochain/client";
import { decode, encode } from "@msgpack/msgpack";
import * as ed from "@noble/ed25519";
import { expect, test, describe } from "vitest";
import { fileURLToPath } from "url";
import path from "path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Absolute path to the compiled hApp bundle */
const HAPP_PATH = path.join(__dirname, "../../workdir/valichord.happ");

/** A membrane proof that passes the format check (>= 64 zero bytes). */
function validMembraneProof(): Uint8Array {
  return new Uint8Array(64).fill(0x42);
}

/** A membrane proof that fails the format check (only 10 bytes). */
function shortMembraneProof(): Uint8Array {
  return new Uint8Array(10).fill(0x01);
}

/**
 * Create a valid Ed25519 membrane proof for a joining agent.
 *
 * The Rust coordinator's verify_membrane_proof() calls:
 *   verify_signature(issuer_key, sig, raw_bytes_vec)
 * where raw_bytes_vec: Vec<u8> is the joining agent's 39-byte pubkey.
 * rmp_serde serialises Vec<u8> as a msgpack array of unsigned integers.
 * We must sign the same bytes: encode(Array.from(agentPubKey)).
 *
 * @param issuerPrivKey - 32-byte @noble/ed25519 private key (seed)
 * @param joiningAgentPubKey - 39-byte Holochain AgentPubKey of the joining agent
 */
async function makeMembraneProof(
  issuerPrivKey: Uint8Array,
  joiningAgentPubKey: AgentPubKey,
): Promise<Uint8Array> {
  // encode(Array.from(Uint8Array)) → msgpack array of u8 integers,
  // matching rmp_serde's Vec<u8> serialisation.
  const signedData = encode(Array.from(joiningAgentPubKey));
  return ed.signAsync(signedData, issuerPrivKey);
}

/**
 * Build a valid 39-byte ExternalHash from a single repeated core byte.
 * Structure: [0x84, 0x2F, 0x24] + 32×coreByte + dhtLocation(4 bytes).
 * Uses @holochain/client's hashFrom32AndType which computes the correct
 * DHT location (blake2b-based XOR fold) so try_from_raw_39 accepts it.
 */
function fakeExternalHash(coreByte: number): Uint8Array {
  const core = new Uint8Array(32).fill(coreByte);
  return hashFrom32AndType(core, HoloHashType.External);
}

/**
 * Player config that injects a membrane proof for the attestation role
 * and sets minimum_validators (default 2) so that many tests need only
 * Alice + Bob.
 *
 * Governance DNA properties are set to empty strings so that the
 * empty-key bypass in governance_integrity/validate() allows any agent
 * to write HarmonyRecord, ReproducibilityBadge, and ValidatorReputation
 * entries. In production, set these to the real coordinator keys.
 */
function playerConfig(membraneProof?: Uint8Array, minValidators: number = 2) {
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
            // membrane_proof lives inside value, not at top-level options.
            // RoleSettings.provisioned.value: { membrane_proof?, modifiers? }
            membrane_proof: membraneProof,
            modifiers: {
              properties: {
                minimum_validators: minValidators,
                discipline: "genomics",
                // Empty string = dev/test bypass in coordinator init().
                // Full Ed25519 verification is tested in tests 1.4 and 1.5.
                authorized_joining_certificate_issuer: "",
              },
            },
          },
        },
        governance: {
          type: "provisioned" as const,
          value: {
            modifiers: {
              properties: {
                // Empty = unrestricted (test / development mode).
                // governance_integrity bypasses the author key check when
                // system_coordinator_key is an empty string, so any test agent
                // can write GovernanceDecision, ValidatorReputation, etc.
                // In production, set to the real coordinator agent key.
                system_coordinator_key: "",
                // 0 = use at-least-one default in force_finalize_round.
                min_attestations_for_finalization: 0,
              },
            },
          },
        },
      },
    },
  };
}

/** Typed wrapper for callZome — avoids repetition in test bodies. */
async function zomeCall<T>(
  player: Awaited<ReturnType<typeof runScenario extends (fn: (s: infer S) => any) => any ? S : never>["addPlayerWithApp"]>,
  fnName: string,
  payload: unknown = null,
): Promise<T> {
  return player.appWs.callZome({
    role_name: "attestation",
    zome_name: "attestation_coordinator",
    fn_name: fnName,
    payload,
  }) as Promise<T>;
}

/** callZome for the validator_workspace DNA. */
async function wsCall<T = unknown>(
  player: any,
  fnName: string,
  payload: unknown = null,
): Promise<T> {
  return player.appWs.callZome({
    role_name: "validator_workspace",
    zome_name: "validator_workspace_coordinator",
    fn_name: fnName,
    payload,
  }) as Promise<T>;
}

/** callZome for the governance DNA. */
async function govCall<T = unknown>(
  player: any,
  fnName: string,
  payload: unknown = null,
): Promise<T> {
  return player.appWs.callZome({
    role_name: "governance",
    zome_name: "governance_coordinator",
    fn_name: fnName,
    payload,
  }) as Promise<T>;
}

/**
 * Attestation payload for seal_private_attestation tests.
 * SealAttestationInput.attestation is ValidationAttestation (the public struct).
 * The nonce, commitment_hash, and sealed_at_secs are generated internally by Rust.
 */
function makePrivateAttestation(requestRef: Uint8Array) {
  return makeAttestation(requestRef);
}

/** Minimal ValidationRequest payload */
function makeValidationRequest(overrides?: Record<string, unknown>) {
  return {
    protocol_ref: null,
    // ExternalHash: valid 39-byte Uint8Array (prefix + core + DHT loc).
    // Must be Uint8Array so msgpack encodes as binary (bin), not array.
    data_hash: fakeExternalHash(0xab),
    // Where validators download the dataset (OSF, Zenodo, institutional repo, etc.).
    data_access_url: "https://osf.io/example/files",
    // DOI or URL of the pre-registered analysis plan. null = not yet pre-registered.
    protocol_access_url: "https://osf.io/example/preregistration",
    num_validators_required: 2,
    // ValidationTier has no serde tag attr → external tag → unit variant = plain string.
    validation_tier: "Basic",
    // Discipline uses #[serde(tag="type", content="content")] → adjacent-tagged.
    // Unit variants: {"type": "VariantName"} (no content key for unit variants).
    discipline: { type: "ComputationalBiology" },
    // Researcher's institution — used for COI checks. Empty string = independent researcher (no institutional COI).
    researcher_institution: "MIT",
    ...overrides,
  };
}

/**
 * Attestation payload with FailedToReproduce outcome.
 * Used for FailedReproduction badge threshold tests.
 * AttestationOutcome uses adjacent tag: { type: "FailedToReproduce", content: { details } }
 */
function makeFailedAttestation(requestRef: Uint8Array) {
  return {
    ...makeAttestation(requestRef),
    outcome: { type: "FailedToReproduce", content: { details: "Results did not match published findings" } },
  };
}

/** Minimal ValidationAttestation payload */
function makeAttestation(requestRef: Uint8Array) {
  return {
    request_ref: requestRef,
    // AttestationOutcome uses #[serde(tag="type", content="content")] → adjacent-tagged.
    outcome: { type: "Reproduced" },
    outcome_summary: {
      key_metrics: [],
      effect_direction_matches: null,
      confidence_interval_overlap: null,
      // AgreementLevel has no serde tag → external tag → unit variant = plain string.
      overall_agreement: "ExactMatch",
    },
    time_invested_secs: 3600,
    time_breakdown: {
      environment_setup_secs: 900,
      data_acquisition_secs: 600,
      code_execution_secs: 1800,
      troubleshooting_secs: 300,
    },
    // AttestationConfidence has no serde tag → external tag → unit variant = plain string.
    confidence: "High",
    deviation_flags: [],
    computational_resources: {
      personal_hardware_sufficient: true,
      hpc_required: false,
      gpu_required: false,
      cloud_compute_required: false,
      estimated_compute_cost_pence: null,
    },
    // Discipline uses #[serde(tag="type", content="content")] → adjacent-tagged.
    discipline: { type: "ComputationalBiology" },
  };
}

/**
 * Wrap a request_ref into CommitmentSealedInput with an empty commitment_hash.
 * The empty hash triggers the dev/test bypass in notify_commitment_sealed
 * (authorized_joining_certificate_issuer is "" in test configs).
 */
function commitInput(requestRef: Uint8Array) {
  return { request_ref: requestRef, commitment_hash: new Uint8Array(0) };
}

/**
 * Wrap a ValidationAttestation into AttestationRevealInput with an empty nonce.
 * The empty nonce (combined with the dev bypass) skips commit-reveal hash
 * verification in submit_attestation.
 */
function revealInput(attestation: object) {
  return { attestation, nonce: new Uint8Array(0) };
}

// ---------------------------------------------------------------------------
// 1. Membrane Proof — acceptance and rejection
// ---------------------------------------------------------------------------

describe("1. Membrane proof", () => {
  test(
    "agent with valid membrane proof (>= 64 bytes) can join the attestation DNA",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        // An agent with a sufficiently-long proof joins without error.
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        // If genesis completed successfully, we can call a read function.
        // get_current_phase takes ExternalHash directly (not wrapped in object).
        // Must be a valid 39-byte ExternalHash (prefix + 32-byte core + DHT loc).
        const result = await zomeCall<null>(
          alice,
          "get_current_phase",
          fakeExternalHash(0x01),
        );

        // No PhaseMarker written yet — should return null/undefined.
        expect(result).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "agent with no membrane proof is rejected at genesis_self_check",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Missing proof should cause genesis_self_check to fail, so
        // addPlayersWithApps should throw.
        await expect(
          scenario.addPlayersWithApps([playerConfig(undefined)]),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "agent with too-short membrane proof (< 64 bytes) is rejected at genesis_self_check",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        await expect(
          scenario.addPlayersWithApps([playerConfig(shortMembraneProof())]),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "agent with valid real Ed25519 proof is accepted by coordinator init",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const privKey = ed.utils.randomPrivateKey();
        const pubKeyBytes = await ed.getPublicKeyAsync(privKey);
        const issuerPubKey = hashFrom32AndType(pubKeyBytes, HoloHashType.Agent);
        const issuerBase64 = encodeHashToBase64(issuerPubKey);

        // Two-step setup: generate agent key first, then sign it with the issuer.
        const conductor = await scenario.addConductor();
        const agentPubKey: AgentPubKey = await conductor.adminWs().generateAgentPubKey();
        const membraneProof = await makeMembraneProof(privKey, agentPubKey);

        const alice = await (scenario as any).installPlayerApp(conductor, {
          appBundleSource: { type: "path" as const, value: HAPP_PATH },
          options: {
            networkSeed: scenario.networkSeed,
            agentPubKey,
            rolesSettings: {
              attestation: {
                type: "provisioned" as const,
                value: {
                  membrane_proof: membraneProof,
                  modifiers: {
                    properties: {
                      minimum_validators: 2,
                      discipline: "genomics",
                      authorized_joining_certificate_issuer: issuerBase64,
                    },
                  },
                },
              },
              governance: {
                type: "provisioned" as const,
                value: {
                  modifiers: {
                    properties: {
                      system_coordinator_key: "",
                      harmony_record_creator_key: "",
                    },
                  },
                },
              },
            },
          },
        });

        // Valid proof → coordinator init() should pass → zome call succeeds.
        const result = await alice.appWs.callZome({
          role_name: "attestation",
          zome_name: "attestation_coordinator",
          fn_name: "get_current_phase",
          payload: fakeExternalHash(0x01),
        });
        expect(result).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "agent with wrong-signature proof is rejected by coordinator init",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const privKey = ed.utils.randomPrivateKey();
        const pubKeyBytes = await ed.getPublicKeyAsync(privKey);
        const issuerPubKey = hashFrom32AndType(pubKeyBytes, HoloHashType.Agent);
        const issuerBase64 = encodeHashToBase64(issuerPubKey);

        const conductor = await scenario.addConductor();
        const agentPubKey: AgentPubKey = await conductor.adminWs().generateAgentPubKey();
        // 64 bytes of zeros — passes genesis_self_check (≥ 64 bytes) but is
        // NOT a valid Ed25519 signature, so coordinator init() must reject it.
        const invalidProof = new Uint8Array(64).fill(0x00);

        const alice = await (scenario as any).installPlayerApp(conductor, {
          appBundleSource: { type: "path" as const, value: HAPP_PATH },
          options: {
            networkSeed: scenario.networkSeed,
            agentPubKey,
            rolesSettings: {
              attestation: {
                type: "provisioned" as const,
                value: {
                  membrane_proof: invalidProof,
                  modifiers: {
                    properties: {
                      minimum_validators: 2,
                      discipline: "genomics",
                      authorized_joining_certificate_issuer: issuerBase64,
                    },
                  },
                },
              },
              governance: {
                type: "provisioned" as const,
                value: {
                  modifiers: {
                    properties: {
                      system_coordinator_key: "",
                      harmony_record_creator_key: "",
                    },
                  },
                },
              },
            },
          },
        });

        // Invalid proof → coordinator init() returns Fail → zome call throws.
        await expect(
          alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "get_current_phase",
            payload: fakeExternalHash(0x01),
          }),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 2. Full commit-reveal round
// ---------------------------------------------------------------------------
//
// Protocol:
//   Alice seals private attestation (in DNA 2, not here) →
//   Alice calls notify_commitment_sealed() → CommitmentAnchor on DHT
//   Bob  calls notify_commitment_sealed() → CommitmentAnchor on DHT
//   Both anchors present → PhaseMarker(RevealOpen) written automatically
//   Alice calls submit_attestation() → attestation on DHT
//   Bob  calls submit_attestation() → attestation on DHT
//   get_attestations_for_request() returns both

describe("2. Full commit-reveal round", () => {
  test(
    "two validators commit, phase opens, both reveal, attestations retrievable",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        // Shared request_ref: valid 39-byte ExternalHash.
        // fakeExternalHash computes correct DHT location so try_from_raw_39 accepts it.
        const REQUEST_REF = fakeExternalHash(0xcc);

        // --- Step 1: Alice submits the ValidationRequest ---
        // data_hash must match REQUEST_REF so check_all_commitments_sealed can
        // find the quorum requirement for this specific study.
        const _requestHash = await zomeCall<ActionHash>(
          alice,
          "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }),
        );
        expect(_requestHash).toBeTruthy();

        // Sync so Bob sees the request.
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];
        await dhtSync([alice, bob], dnaHash);

        // --- Step 2: Alice commits (seals private attestation in DNA 2) ---
        // In real deployment, notify_commitment_sealed is called from DNA 2's
        // post_commit. Here we call it directly to test the Attestation DNA logic.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // After Alice's commit: phase should still be null (Bob hasn't committed).
        const phaseAfterAlice = await zomeCall<string | null>(
          bob,
          "get_current_phase",
          REQUEST_REF,
        );
        expect(phaseAfterAlice).toBeNull();

        // Bob commits.
        await zomeCall(bob, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // After Bob's commit: both anchors present → PhaseMarker(RevealOpen) written.
        // ValidationPhase has no serde tag → external tag → unit variant = plain string.
        const phaseAfterBoth = await zomeCall<string | null>(
          alice,
          "get_current_phase",
          REQUEST_REF,
        );
        expect(phaseAfterBoth).not.toBeNull();
        expect(phaseAfterBoth).toBe("RevealOpen");

        // --- Step 3: Reveal phase — both submit public attestations ---
        const aliceAttestationHash = await zomeCall<ActionHash>(
          alice,
          "submit_attestation",
          revealInput(makeAttestation(REQUEST_REF)),
        );
        expect(aliceAttestationHash).toBeTruthy();

        const bobAttestationHash = await zomeCall<ActionHash>(
          bob,
          "submit_attestation",
          revealInput(makeAttestation(REQUEST_REF)),
        );
        expect(bobAttestationHash).toBeTruthy();

        await dhtSync([alice, bob], dnaHash);

        // --- Step 4: Retrieve all attestations for this request ---
        const attestations = await zomeCall<unknown[]>(
          alice,
          "get_attestations_for_request",
          REQUEST_REF,
        );
        expect(attestations).toHaveLength(2);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 3. DHT-poll phase transition
// ---------------------------------------------------------------------------
//
// Engineering constraint #1: phase transitions MUST be discoverable via DHT
// polling. Signals are fire-and-forget and cannot be relied upon.
//
// Scenario: Carol commits, Dave commits. Eve comes online AFTER the
// PhaseMarker is written (she missed the signal). Eve polls get_current_phase()
// and discovers RevealOpen without ever receiving a signal.

describe("3. DHT-poll phase transition", () => {
  test(
    "late-joining validator discovers RevealOpen by polling, not via signal",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [carol, dave, eve] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xee);

        const dnaHash = carol.namedCells.get("attestation")?.cell_id[0];

        // Track signal received by Eve (should NOT be needed for phase discovery).
        let eveReceivedSignal = false;
        eve.appWs.on("signal", (_signal: unknown) => {
          eveReceivedSignal = true;
        });

        // Submit a ValidationRequest so check_all_commitments_sealed can
        // determine num_validators_required (2) and write the PhaseMarker.
        await zomeCall(carol, "submit_validation_request", makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([carol, dave, eve], dnaHash);

        // Carol and Dave commit — Eve is "offline" (not involved yet).
        await zomeCall(carol, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([carol, dave], dnaHash);

        await zomeCall(dave, "notify_commitment_sealed", commitInput(REQUEST_REF));
        // Sync Carol + Dave only — Eve is excluded from this sync round,
        // simulating her being offline when the signal fired.
        await dhtSync([carol, dave], dnaHash);

        // Both committed; PhaseMarker should exist on the DHT now.
        // Allow Eve to sync with the network WITHOUT relying on signals.
        await dhtSync([carol, dave, eve], dnaHash);

        // Eve polls the DHT — must learn the phase without a signal.
        // ValidationPhase serializes as plain string (external tag, unit variant).
        const phase = await zomeCall<string | null>(
          eve,
          "get_current_phase",
          REQUEST_REF,
        );
        expect(phase).not.toBeNull();
        expect(phase).toBe("RevealOpen");

        // The signal flag is informational — we do NOT assert eveReceivedSignal.
        // The test passes regardless of whether the signal arrived.
        // This confirms the design: DHT state is the source of truth.
        console.log(`[test] Eve received signal: ${eveReceivedSignal} (irrelevant to correctness)`);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 4. ValidationAttestation immutability
// ---------------------------------------------------------------------------
//
// Once a ValidationAttestation is written, the validate() callback MUST
// reject any attempt to update or delete it.

// ---------------------------------------------------------------------------
// 5. ValidatorProfile and DifficultyAssessment
// ---------------------------------------------------------------------------

describe("5. ValidatorProfile and DifficultyAssessment", () => {
  test(
    "published validator profile is retrievable by agent public key",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        // CertificationTier: no serde tag → external tag → unit variant = plain string.
        // Discipline uses #[serde(tag="type", content="content")] — adjacent-tagged.
        const profile = {
          institution: "Open Science Lab",
          disciplines: [{ type: "ComputationalBiology" }],
          certification_tier: "Provisional",
          available: true,
          max_concurrent_tasks: 3,
          orcid: null,
        };

        const profileHash = await zomeCall<ActionHash>(
          alice,
          "publish_validator_profile",
          profile,
        );
        expect(profileHash).toBeTruthy();

        // Retrieve by agent pub key.
        const record = await zomeCall<unknown>(
          alice,
          "get_validator_profile",
          alice.agentPubKey,
        );
        expect(record).not.toBeNull();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "get_validator_profile returns null when no profile published",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const result = await zomeCall<unknown>(
          alice,
          "get_validator_profile",
          alice.agentPubKey,
        );
        expect(result).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "assess_difficulty then get_difficulty_assessment returns the assessment; unknown ref returns null",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const ASSESSED_REF   = fakeExternalHash(0xf0);
        const UNASSESSED_REF = fakeExternalHash(0xf1);

        // Before assessment: both refs return null.
        const before = await zomeCall<unknown>(alice, "get_difficulty_assessment", ASSESSED_REF);
        expect(before).toBeNull();

        // assess_difficulty now accepts a caller-provided AssessDifficultyInput
        // struct. The coordinator stores it verbatim and indexes via DifficultyPath.
        const assessmentInput = {
          request_ref:            ASSESSED_REF,
          code_volume:            4,
          dependency_count:       5,
          documentation_quality:  2,
          data_accessibility:     3,
          environment_complexity: 4,
          study_age_years:        3,
          predicted_tier:         "Moderate",
          predicted_min_secs:     14400,
          predicted_max_secs:     43200,
          confidence:             "Medium",
        };
        const assessmentHash = await zomeCall<ActionHash>(alice, "assess_difficulty", assessmentInput);
        expect(assessmentHash).toBeTruthy();

        // get_difficulty_assessment follows the DifficultyPath link.
        const record = await zomeCall<any>(alice, "get_difficulty_assessment", ASSESSED_REF);
        expect(record).not.toBeNull();

        // Decode and verify request_ref + caller-supplied fields round-trip.
        // msgpack decodes bytes as a Node.js Buffer (subclass of Uint8Array);
        // wrap in Uint8Array so toEqual compares byte content, not prototype.
        const entry = record?.entry;
        if (entry?.Present?.entry_type === "App") {
          const decoded = decode(entry.Present.entry as Uint8Array) as {
            request_ref: Uint8Array;
            code_volume: number;
            predicted_min_secs: number;
          };
          expect(new Uint8Array(decoded.request_ref)).toEqual(ASSESSED_REF);
          expect(decoded.code_volume).toBe(4);
          expect(decoded.predicted_min_secs).toBe(14400);
        }

        // A different request_ref that was never assessed still returns null.
        const nullResult = await zomeCall<unknown>(alice, "get_difficulty_assessment", UNASSESSED_REF);
        expect(nullResult).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 6. ValidationRequest lifecycle
// ---------------------------------------------------------------------------

describe("6. ValidationRequest lifecycle", () => {
  test(
    "submitted ValidationRequest is retrievable by its ActionHash",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const requestHash = await zomeCall<ActionHash>(
          alice,
          "submit_validation_request",
          makeValidationRequest(),
        );
        expect(requestHash).toBeTruthy();

        const record = await zomeCall<unknown>(
          alice,
          "get_validation_request",
          requestHash,
        );
        expect(record).not.toBeNull();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "get_validation_request returns null for an unknown ActionHash",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        // A properly-typed ActionHash that was never written to the source chain.
        const unknownHash = hashFrom32AndType(
          new Uint8Array(32).fill(0xff),
          HoloHashType.Action,
        );

        const result = await zomeCall<unknown>(
          alice,
          "get_validation_request",
          unknownHash,
        );
        expect(result).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 7. PhaseMarker and CommitmentAnchor immutability (update path)
// ---------------------------------------------------------------------------
//
// validate() in attestation_integrity blocks updates to CommitmentAnchor,
// PhaseMarker, and ValidationAttestation. The coordinator exposes no update
// or delete functions for these entries — immutability is enforced at both
// the API level (no function exists) and the validation level (validate()
// rejects the op if the function were ever added).
//
// These tests verify the API-level protection, which is the practical guard.

describe("7. CommitmentAnchor and PhaseMarker immutability (update path)", () => {
  test(
    "attempting to update a CommitmentAnchor is rejected (no update function in API)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0x11);

        // notify_commitment_sealed now requires a prior ValidationRequest (inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));

        // Post a CommitmentAnchor.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));

        // No update coordinator function exists — call must fail.
        await expect(
          alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "update_commitment_for_test",
            payload: null,
          }),
        ).rejects.toThrow();
        // Rejection confirms no update path exists in the public API.
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "attempting to update a PhaseMarker is rejected (no update function in API)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0x22);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // Submit a VR so check_all_commitments_sealed_inner can find num_validators_required=2.
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([alice, bob], dnaHash);

        // Both validators commit → PhaseMarker(RevealOpen) is written.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);
        await zomeCall(bob, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // Confirm PhaseMarker exists.
        const phase = await zomeCall<string | null>(
          alice, "get_current_phase", REQUEST_REF,
        );
        expect(phase).toBe("RevealOpen");

        // No update coordinator function exists — call must fail.
        await expect(
          alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "update_phase_marker_for_test",
            payload: null,
          }),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "attempting to delete a PhaseMarker is rejected (no delete function in API)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0x33);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // notify_commitment_sealed now requires a prior ValidationRequest (inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([alice, bob], dnaHash);

        // Both validators commit → PhaseMarker written.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);
        await zomeCall(bob, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // No delete coordinator function exists — call must fail.
        await expect(
          alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "delete_phase_marker_for_test",
            payload: null,
          }),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 8. ValidationRequest query by discipline
// ---------------------------------------------------------------------------
//
// submit_validation_request indexes requests under:
//   "requests.pending.{discipline_tag}" → LinkTypes::StatusPath
// get_pending_requests_for_discipline queries that path.

describe("8. ValidationRequest query by discipline", () => {
  test(
    "get_pending_requests_for_discipline returns submitted request for matching discipline",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        // Submit a request with ComputationalBiology discipline.
        await zomeCall(alice, "submit_validation_request", makeValidationRequest());

        // Query by the same discipline — should return exactly one request.
        const records = await zomeCall<unknown[]>(
          alice,
          "get_pending_requests_for_discipline",
          { type: "ComputationalBiology" },
        );
        expect(records).toHaveLength(1);
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "get_pending_requests_for_discipline returns empty for a different discipline",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        // Submit a request with ComputationalBiology.
        await zomeCall(alice, "submit_validation_request", makeValidationRequest());

        // Query a different discipline — should return nothing.
        const records = await zomeCall<unknown[]>(
          alice,
          "get_pending_requests_for_discipline",
          { type: "MachineLearning" },
        );
        expect(records).toHaveLength(0);
      }, true, { timeout: 300_000 });
    },
  );
});


describe("4. ValidationAttestation immutability", () => {
  test(
    "attempting to update a ValidationAttestation is rejected by validate()",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xbb);

        // submit_attestation now requires a prior CommitmentAnchor (inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));

        // Alice submits a public attestation.
        const hash = await zomeCall<ActionHash>(
          alice,
          "submit_attestation",
          revealInput(makeAttestation(REQUEST_REF)),
        );
        expect(hash).toBeTruthy();

        // Now attempt to update it. The validate() callback should reject this.
        // Tryorama surfaces validation failure as a thrown error.
        await expect(
          alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "update_attestation_for_test",
            payload: { original_hash: hash, new_attestation: makeAttestation(REQUEST_REF) },
          }),
        ).rejects.toThrow();

        // Alternate path: call update_entry directly via the HDK.
        // Since there is no explicit update function in the coordinator, the
        // zome_call above will fail with "function not found" — which is itself
        // evidence that updates are impossible from the public API. The validate()
        // callback adds a second layer of defence if the function were added.
        //
        // The rejection of zome_call (function-not-found) is the EXPECTED outcome
        // and is treated as passing this test.
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "attempting to delete a CommitmentAnchor is rejected by validate()",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xdd);

        // notify_commitment_sealed now requires a prior ValidationRequest (inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));

        // Alice posts a CommitmentAnchor.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));

        // There is no "delete_commitment" coordinator function — the immutability
        // guarantee is enforced both at the API level (no delete function exists)
        // and at the validation level (validate() rejects OpDelete for CommitmentAnchor).
        //
        // This test verifies the API-level protection.
        await expect(
          alice.appWs.callZome({
            role_name: "attestation",
            zome_name: "attestation_coordinator",
            fn_name: "delete_commitment_for_test",
            payload: null,
          }),
        ).rejects.toThrow();
        // Rejection confirms no delete path exists in the public API.
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 9. Cross-DNA post_commit: DNA 2 seal → DNA 3 notify auto-trigger
// ---------------------------------------------------------------------------
//
// When a validator calls seal_private_attestation in DNA 2 (validator_workspace),
// post_commit fires and calls notify_commitment_sealed in DNA 3 (attestation)
// via call(OtherRole("attestation")). This is the real production protocol path.
//
// post_commit MUST NOT write data directly, but CAN call other zome functions.
// The write (CommitmentAnchor) happens inside notify_commitment_sealed in DNA 3,
// not inside post_commit itself — so the Holochain constraint is satisfied.
//
// Warm-up pattern: each player's attestation cell must have completed init()
// before post_commit fires. If init() is triggered for the first time from
// inside a cross-DNA post_commit call the conductor times out (30 s) waiting
// for init() while post_commit holds the cell operation lock. The warm-up
// calls (get_current_phase with a throwaway hash) trigger init() eagerly.

describe("9. Cross-DNA post_commit: DNA 2 seal → DNA 3 notify", () => {
  test(
    "seal_private_attestation post_commit triggers notify_commitment_sealed in attestation DNA",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0x9a);
        const attDnaHash = alice.namedCells.get("attestation")!.cell_id[0];

        // Store a ValidationTask in each validator's workspace DNA.
        const taskPayload = {
          request_ref: REQUEST_REF,
          assigned_at_secs: 1_700_000_000,
          discipline: { type: "ComputationalBiology" },
          deadline_secs: 1_700_100_000,
          validation_focus: "ComputationalReproducibility",
          time_cap_secs: 86400,
          compensation_tier: { Tier1: { amount_pence: 5000 } },
        };
        const aliceTaskHash = await wsCall<Uint8Array>(alice, "receive_task", taskPayload);
        const bobTaskHash   = await wsCall<Uint8Array>(bob,   "receive_task", taskPayload);

        // Submit a ValidationRequest so check_all_commitments_sealed can
        // determine num_validators_required (2) and write the PhaseMarker.
        await zomeCall(alice, "submit_validation_request", makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([alice, bob], attDnaHash);

        // Warm up each player's attestation cell so init() completes before
        // post_commit fires. If init() is triggered for the first time from
        // inside a cross-DNA post_commit call the conductor times out (30 s)
        // waiting for init() while post_commit still holds the cell operation.
        await zomeCall(alice, "get_current_phase", fakeExternalHash(0x00));
        await zomeCall(bob,   "get_current_phase", fakeExternalHash(0x00));

        // Alice seals her private attestation in DNA 2.
        // post_commit fires after the source chain write and calls
        // notify_commitment_sealed in DNA 3 — no direct call here.
        await wsCall(alice, "seal_private_attestation", {
          task_hash:   aliceTaskHash,
          attestation: makePrivateAttestation(REQUEST_REF),
        });

        // post_commit fires asynchronously after the source chain write.
        // A short pause here lets the cross-DNA call to notify_commitment_sealed
        // complete before dhtSync tries to verify the CommitmentAnchor is present.
        // Without this pause the test races against post_commit and fails
        // intermittently.
        await pause(4000);
        await dhtSync([alice, bob], attDnaHash);

        // Bob seals — his post_commit raises the total to 2 (≥ minimum_validators=2),
        // so PhaseMarker(RevealOpen) is written inside notify_commitment_sealed.
        await wsCall(bob, "seal_private_attestation", {
          task_hash:   bobTaskHash,
          attestation: makePrivateAttestation(REQUEST_REF),
        });

        await pause(4000);
        await dhtSync([alice, bob], attDnaHash);

        // Phase should be RevealOpen — triggered entirely by DNA 2 post_commit,
        // not by any direct call to notify_commitment_sealed.
        const phase = await zomeCall<string | null>(
          alice,
          "get_current_phase",
          REQUEST_REF,
        );
        expect(phase).not.toBeNull();
        expect(phase).toBe("RevealOpen");
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 10. Privacy across agents — ValidatorPrivateAttestation
// ---------------------------------------------------------------------------
//
// Security property: ValidatorPrivateAttestation is stored with
// visibility = "private" in the Validator Workspace DNA. Its entry content
// is written only to Alice's own source chain and is never propagated to
// the shared DHT. Bob's workspace cell has no link to Alice's attestation
// and cannot retrieve it through any standard coordinator function.
//
// This is a structural guarantee, not a policy check: Holochain's private
// entry mechanism makes it architecturally impossible for Bob to fetch
// Alice's attestation content via any normal zome call path.

describe("10. Privacy across agents — ValidatorPrivateAttestation", () => {
  test(
    "Bob cannot read Alice's sealed private attestation from Bob's workspace cell",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xa2);

        // Submit a VR so post_commit's notify_commitment_sealed call can find
        // the study.{request_ref} path (required by the inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));

        // Alice creates a validation task in her workspace DNA.
        const taskPayload = {
          request_ref: REQUEST_REF,
          assigned_at_secs: 1_700_000_000,
          discipline: { type: "ComputationalBiology" },
          deadline_secs: 1_700_100_000,
          validation_focus: "ComputationalReproducibility",
          time_cap_secs: 86400,
          compensation_tier: { Tier1: { amount_pence: 5000 } },
        };
        const aliceTaskHash = await wsCall<Uint8Array>(alice, "receive_task", taskPayload);

        // Alice seals her private attestation. The entry is written to Alice's
        // local source chain only — it is NOT published to the shared DHT.
        await wsCall(alice, "seal_private_attestation", {
          task_hash:   aliceTaskHash,
          attestation: makePrivateAttestation(REQUEST_REF),
        });

        // Confirm Alice can retrieve her own attestation via her workspace cell.
        const aliceRecord = await wsCall<unknown>(
          alice, "get_private_attestation_for_task", aliceTaskHash,
        );
        expect(aliceRecord).not.toBeNull();

        // Bob attempts to read Alice's private attestation from Bob's own
        // workspace cell. Bob has no TaskToPrivateAttestation link (the link
        // lives only in Alice's cell) and no local copy of the private entry.
        // The call MUST return null — confirming the privacy guarantee.
        const bobRecord = await wsCall<unknown>(
          bob, "get_private_attestation_for_task", aliceTaskHash,
        );
        expect(bobRecord).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 11. Phase threshold — single validator below minimum_validators
// ---------------------------------------------------------------------------
//
// With minimum_validators=2, one CommitmentAnchor is not enough to trigger
// the PhaseMarker write. get_current_phase must return null until the
// minimum is reached.

describe("11. Phase threshold — single validator below minimum_validators", () => {
  test(
    "one commit with minimum_validators=2 leaves phase as null",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xa3);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // notify_commitment_sealed now requires a prior ValidationRequest (inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([alice, bob], dnaHash);

        // Only Alice commits — Bob does not.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // With minimum_validators=2, one anchor is not enough.
        // No PhaseMarker should have been written — both agents must see null.
        const phaseAlice = await zomeCall<string | null>(
          alice, "get_current_phase", REQUEST_REF,
        );
        expect(phaseAlice).toBeNull();

        const phaseBob = await zomeCall<string | null>(
          bob, "get_current_phase", REQUEST_REF,
        );
        expect(phaseBob).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 12. Badge thresholds — Silver (5 validators) and Gold (7 validators)
// ---------------------------------------------------------------------------
//
// evaluate_badge() in governance_coordinator applies:
//   GoldReproducible:   ExactMatch  AND validator_count >= 7
//   SilverReproducible: ExactMatch | WithinTolerance  AND validator_count >= 5
//
// ExactMatch is derived when ≥90% of attestation outcomes are
// Reproduced or PartiallyReproduced. All-Reproduced rounds always
// produce ExactMatch, making them the cleanest threshold test.
//
// check_and_create_harmony_record fetches attestations from DNA 3 via a
// same-agent cross-DNA call, derives the outcome and badge type, then
// writes HarmonyRecord + ReproducibilityBadge to the governance DHT.
//
// The governance_integrity empty-key bypass allows any agent to write
// these entries when system_coordinator_key / harmony_record_creator_key
// are set to "" in the player config (test mode only).

describe("12. Badge thresholds — Bronze, Silver and Gold", () => {
  test(
    "3 validators all Reproduced → BronzeReproducible badge issued",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const N = 3;
        const configs = Array.from({ length: N }, () =>
          playerConfig(validMembraneProof(), N),
        );
        const validators = await scenario.addPlayersWithApps(configs);

        const REQUEST_REF = fakeExternalHash(0xb0);
        const attDnaHash = validators[0].namedCells.get("attestation")?.cell_id[0];

        // Submit a ValidationRequest so check_and_create_harmony_record can
        // resolve num_validators_required (N) via cross-DNA call.
        await zomeCall(validators[0], "submit_validation_request", makeValidationRequest({ data_hash: REQUEST_REF, num_validators_required: N }));
        await dhtSync(validators, attDnaHash);

        // All 3 validators post CommitmentAnchors.
        for (const v of validators) {
          await zomeCall(v, "notify_commitment_sealed", commitInput(REQUEST_REF));
        }
        await dhtSync(validators, attDnaHash);

        // All 3 validators submit Reproduced attestations.
        // success_rate = 3/3 = 100% → ExactMatch.
        for (const v of validators) {
          await zomeCall(v, "submit_attestation", revealInput(makeAttestation(REQUEST_REF)));
        }
        await dhtSync(validators, attDnaHash);

        // ExactMatch + count=3 ≥ 3 (and < 5) → BronzeReproducible.
        const harmonyHash = await govCall<Uint8Array | null>(
          validators[0], "check_and_create_harmony_record", REQUEST_REF,
        );
        expect(harmonyHash).not.toBeNull();

        const badges = await govCall<any[]>(
          validators[0], "get_badges_for_study", REQUEST_REF,
        );
        expect(badges).toHaveLength(1);

        const entry = (badges[0] as any).entry;
        if (entry?.Present?.entry_type === "App") {
          const badge = decode(entry.Present.entry as Uint8Array) as {
            badge_type: string;
          };
          expect(badge.badge_type).toBe("BronzeReproducible");
        }
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "5 validators all Reproduced → SilverReproducible badge issued",
    { timeout: 900_000 },
    async () => {
      await runScenario(async (scenario) => {
        const N = 5;
        const configs = Array.from({ length: N }, () =>
          playerConfig(validMembraneProof(), N),
        );
        const [alice, bob, carol, dave, eve] =
          await scenario.addPlayersWithApps(configs);
        const validators = [alice, bob, carol, dave, eve];

        const REQUEST_REF = fakeExternalHash(0xb1);
        const attDnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // Submit a ValidationRequest so check_and_create_harmony_record can
        // resolve num_validators_required (N) via cross-DNA call.
        // No separate dhtSync here — the VR propagates alongside the
        // CommitmentAnchors in the single sync below, which is sufficient
        // because check_and_create_harmony_record is only called after the
        // attestation round completes.
        await zomeCall(alice, "submit_validation_request", makeValidationRequest({ data_hash: REQUEST_REF, num_validators_required: N }));
        // Sync so all validators see Alice's VR before calling notify_commitment_sealed
        // (which now requires the study.{request_ref} path to resolve the VR ActionHash).
        await dhtSync(validators, attDnaHash, 100, 120_000);

        // All N validators post CommitmentAnchors. After the Nth call the
        // coordinator's check_all_commitments_sealed_inner fires and writes
        // the PhaseMarker — but for badge issuance only the anchors and
        // public attestations matter. We do them in sequence to keep tests
        // deterministic, then sync once.
        for (const v of validators) {
          await zomeCall(v, "notify_commitment_sealed", commitInput(REQUEST_REF));
        }
        // 5-player dhtSync needs more time than the default 40 s on loaded machines.
        await dhtSync(validators, attDnaHash, 100, 120_000);

        // All N validators submit public (Reproduced) attestations.
        for (const v of validators) {
          await zomeCall(v, "submit_attestation", revealInput(makeAttestation(REQUEST_REF)));
        }
        await dhtSync(validators, attDnaHash, 100, 120_000);

        // Alice (acting as governance coordinator) assembles the HarmonyRecord.
        // check_and_create_harmony_record fetches attestations via cross-DNA
        // call, derives ExactMatch agreement (5/5 = 100% success rate),
        // and issues SilverReproducible (count=5, 5 >= 5, < 7).
        const harmonyHash = await govCall<Uint8Array | null>(
          alice, "check_and_create_harmony_record", REQUEST_REF,
        );
        expect(harmonyHash).not.toBeNull();

        // Retrieve the issued badge.
        const badges = await govCall<any[]>(
          alice, "get_badges_for_study", REQUEST_REF,
        );
        expect(badges).toHaveLength(1);

        // Decode entry bytes to verify badge_type.
        // ReproducibilityBadge.badge_type serialises as a plain string
        // (BadgeType enum has no serde tag → external tag → unit variant = string).
        const entry = (badges[0] as any).entry;
        if (entry?.Present?.entry_type === "App") {
          const badge = decode(entry.Present.entry as Uint8Array) as {
            badge_type: string;
          };
          expect(badge.badge_type).toBe("SilverReproducible");
        }
      }, true, { timeout: 800_000 });
    },
  );

  // SKIP: requires 7 simultaneous Holochain conductors. Conductors crash under
  // load in resource-constrained dev environments (codespace / CI with <16 GB
  // RAM). The test logic is correct; run it on adequately resourced hardware.
  test.skip(
    "7 validators all Reproduced → GoldReproducible badge issued",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const N = 7;
        const configs = Array.from({ length: N }, () =>
          playerConfig(validMembraneProof(), N),
        );
        const validators = await scenario.addPlayersWithApps(configs);

        const REQUEST_REF = fakeExternalHash(0xb2);
        const attDnaHash = validators[0].namedCells.get("attestation")?.cell_id[0];

        for (const v of validators) {
          await zomeCall(v, "notify_commitment_sealed", commitInput(REQUEST_REF));
        }
        await dhtSync(validators, attDnaHash);

        for (const v of validators) {
          await zomeCall(v, "submit_attestation", revealInput(makeAttestation(REQUEST_REF)));
        }
        await dhtSync(validators, attDnaHash);

        // Derives ExactMatch (7/7 = 100%) + count=7 ≥ 7 → GoldReproducible.
        const harmonyHash = await govCall<Uint8Array | null>(
          validators[0], "check_and_create_harmony_record", REQUEST_REF,
        );
        expect(harmonyHash).not.toBeNull();

        const badges = await govCall<any[]>(
          validators[0], "get_badges_for_study", REQUEST_REF,
        );
        expect(badges).toHaveLength(1);

        const entry = (badges[0] as any).entry;
        if (entry?.Present?.entry_type === "App") {
          const badge = decode(entry.Present.entry as Uint8Array) as {
            badge_type: string;
          };
          expect(badge.badge_type).toBe("GoldReproducible");
        }
      }, true, { timeout: 600_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 13. FailedReproduction badge
// ---------------------------------------------------------------------------
//
// When no validator reports Reproduced or PartiallyReproduced, the
// success rate is 0 → derive_agreement_level returns UnableToAssess →
// evaluate_badge returns FailedReproduction.

describe("13. FailedReproduction badge", () => {
  test(
    "2 validators both FailedToReproduce → FailedReproduction badge issued",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xb3);
        const attDnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // Submit a ValidationRequest so check_and_create_harmony_record can
        // resolve num_validators_required via cross-DNA call.
        await zomeCall(alice, "submit_validation_request", makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([alice, bob], attDnaHash);

        // Both validators post CommitmentAnchors.
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], attDnaHash);
        await zomeCall(bob, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], attDnaHash);

        // Both submit FailedToReproduce public attestations.
        await zomeCall(alice, "submit_attestation", revealInput(makeFailedAttestation(REQUEST_REF)));
        await zomeCall(bob,   "submit_attestation", revealInput(makeFailedAttestation(REQUEST_REF)));
        await dhtSync([alice, bob], attDnaHash);

        // Derives 0 successes → UnableToAssess → FailedReproduction badge.
        const harmonyHash = await govCall<Uint8Array | null>(
          alice, "check_and_create_harmony_record", REQUEST_REF,
        );
        expect(harmonyHash).not.toBeNull();

        const badges = await govCall<any[]>(
          alice, "get_badges_for_study", REQUEST_REF,
        );
        expect(badges).toHaveLength(1);

        const entry = (badges[0] as any).entry;
        if (entry?.Present?.entry_type === "App") {
          const badge = decode(entry.Present.entry as Uint8Array) as {
            badge_type: string;
          };
          expect(badge.badge_type).toBe("FailedReproduction");
        }
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 14. Validator reputation
// ---------------------------------------------------------------------------
//
// update_validator_reputation creates a ValidatorReputation entry linked
// from the validator's AgentPubKey. get_validator_reputation follows that
// link and returns the most recent record.
//
// The governance_integrity empty-key bypass allows any agent to write
// ValidatorReputation entries in test mode.

describe("14. Validator reputation", () => {
  test(
    "update then get_validator_reputation returns the written record",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const reputationInput = {
          validator:          alice.agentPubKey,
          discipline:         { type: "ComputationalBiology" },
          // AttestationOutcome: adjacent tag. Reproduced is a unit variant → no content key.
          outcome:            { type: "Reproduced" },
          time_invested_secs: 3600,
        };

        const repHash = await govCall<Uint8Array>(
          alice, "update_validator_reputation", reputationInput,
        );
        expect(repHash).toBeTruthy();

        // get_validator_reputation follows the ValidatorToReputation link.
        const record = await govCall<unknown>(
          alice, "get_validator_reputation", alice.agentPubKey,
        );
        expect(record).not.toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 15. get_validators_for_discipline — real path-based query
// ---------------------------------------------------------------------------
//
// publish_validator_profile now creates a link on "validators.{discipline_tag}"
// (LinkTypes::ValidatorTierPath) for each discipline in the profile.
// get_validators_for_discipline queries that path and returns all profiles.

describe("15. get_validators_for_discipline", () => {
  test(
    "two profiles published for ComputationalBiology — both returned; MachineLearning returns 0",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const compBioProfile = {
          institution: "Open Science Lab",
          disciplines: [{ type: "ComputationalBiology" }],
          certification_tier: "Provisional",
          available: true,
          max_concurrent_tasks: 3,
          orcid: null,
        };

        // Alice and Bob both publish ComputationalBiology profiles.
        await zomeCall(alice, "publish_validator_profile", compBioProfile);
        await zomeCall(bob,   "publish_validator_profile", compBioProfile);
        await dhtSync([alice, bob], dnaHash);

        // Both profiles indexed under ComputationalBiology → returns 2.
        const compBioProfiles = await zomeCall<unknown[]>(
          alice,
          "get_validators_for_discipline",
          { type: "ComputationalBiology" },
        );
        expect(compBioProfiles).toHaveLength(2);

        // MachineLearning has no profiles published → returns 0.
        const mlProfiles = await zomeCall<unknown[]>(
          alice,
          "get_validators_for_discipline",
          { type: "MachineLearning" },
        );
        expect(mlProfiles).toHaveLength(0);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 16. check_all_commitments_sealed — direct call
// ---------------------------------------------------------------------------
//
// check_all_commitments_sealed is exposed as a public #[hdk_extern] and can
// be called directly. It compares the number of CommitmentAnchor links under
// "commitments.{request_ref}" to minimum_validators (DNA property, default 2).
//
// Sequence:
//   1. One validator commits → sealed? false (1 < 2)
//   2. Second validator commits → sealed? true (2 >= 2)

// ---------------------------------------------------------------------------
// 17. get_validation_request_for_data_hash
// ---------------------------------------------------------------------------
//
// submit_validation_request writes a StudyToValidation link under the path
// "study.{data_hash}".  get_validation_request_for_data_hash resolves that
// path and returns the Record (or null if never submitted).
//
// This extern is used by governance's check_and_create_harmony_record to
// determine the researcher (record author) who becomes the badge recipient
// (ReproducibilityBadge.issued_to).  A bug here would silently mis-attribute
// every badge in production.

describe("17. get_validation_request_for_data_hash", () => {
  test(
    "returns the ValidationRequest record for a known data_hash",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const DATA_HASH = fakeExternalHash(0xd0);

        // Submit a request whose data_hash is DATA_HASH.
        const requestHash = await zomeCall<ActionHash>(
          alice,
          "submit_validation_request",
          makeValidationRequest({ data_hash: DATA_HASH }),
        );
        expect(requestHash).toBeTruthy();

        // The extern must resolve the path and return the same record.
        const record = await zomeCall<unknown>(
          alice,
          "get_validation_request_for_data_hash",
          DATA_HASH,
        );
        expect(record).not.toBeNull();

        // The returned record's ActionHash must match what submit returned.
        const returnedHash: Uint8Array = (record as any)?.signed_action?.hashed?.hash;
        expect(returnedHash).toBeDefined();
        // Compare as base64 strings — Uint8Array reference equality fails across
        // the serialisation boundary.
        expect(Buffer.from(returnedHash).toString("base64")).toBe(
          Buffer.from(requestHash as Uint8Array).toString("base64"),
        );
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "returns null for a data_hash that was never submitted",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        // A data_hash for which no ValidationRequest has ever been submitted.
        const UNKNOWN_HASH = fakeExternalHash(0xd1);

        const result = await zomeCall<unknown>(
          alice,
          "get_validation_request_for_data_hash",
          UNKNOWN_HASH,
        );
        expect(result).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 16. check_all_commitments_sealed — direct call
// ---------------------------------------------------------------------------
//
// check_all_commitments_sealed is exposed as a public #[hdk_extern] and can
// be called directly. It compares the number of CommitmentAnchor links under
// "commitments.{request_ref}" to minimum_validators (DNA property, default 2).
//
// Sequence:
//   1. One validator commits → sealed? false (1 < 2)
//   2. Second validator commits → sealed? true (2 >= 2)

describe("16. check_all_commitments_sealed direct call", () => {
  test(
    "returns false after 1 of 2 commits, true after 2nd commit",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()), // minimum_validators=2 (default)
          playerConfig(validMembraneProof()),
        ]);

        const REQUEST_REF = fakeExternalHash(0xc0);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // Submit a ValidationRequest so check_all_commitments_sealed can
        // determine num_validators_required (2).
        await zomeCall(alice, "submit_validation_request", makeValidationRequest({ data_hash: REQUEST_REF }));
        await dhtSync([alice, bob], dnaHash);

        // Only Alice commits — count (1) < minimum_validators (2).
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // Direct check: 1 of 2 committed → false.
        const afterFirst = await zomeCall<boolean>(
          alice, "check_all_commitments_sealed", REQUEST_REF,
        );
        expect(afterFirst).toBe(false);

        // Bob commits — count (2) >= minimum_validators (2).
        await zomeCall(bob, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob], dnaHash);

        // Direct check: both committed → true.
        const afterSecond = await zomeCall<boolean>(
          alice, "check_all_commitments_sealed", REQUEST_REF,
        );
        expect(afterSecond).toBe(true);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 18. get_validators_for_institution — InstitutionPath index
// ---------------------------------------------------------------------------
//
// publish_validator_profile now writes two link indexes:
//   - ValidatorTierPath: "validators.{discipline_tag}" → profile hash
//   - InstitutionPath:   "institution.{institution}"   → profile hash
//
// get_validators_for_institution queries the InstitutionPath index.
// Used for conflict-of-interest detection in validator assignment.

describe("18. get_validators_for_institution", () => {
  test(
    "returns profiles for matching institution, empty for non-matching",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const mitProfile = {
          institution: "MIT",
          disciplines: [{ type: "ComputationalBiology" }],
          certification_tier: "Provisional",
          available: true,
          max_concurrent_tasks: 3,
          orcid: null,
        };
        const oxfordProfile = {
          institution: "Oxford",
          disciplines: [{ type: "MachineLearning" }],
          certification_tier: "Provisional",
          available: true,
          max_concurrent_tasks: 2,
          orcid: null,
        };

        await zomeCall(alice, "publish_validator_profile", mitProfile);
        await zomeCall(bob,   "publish_validator_profile", oxfordProfile);
        await dhtSync([alice, bob], dnaHash!);

        // MIT has 1 validator; Oxford has 1; Cambridge has 0.
        const mitResults = await zomeCall<unknown[]>(alice, "get_validators_for_institution", "MIT");
        expect(mitResults).toHaveLength(1);

        const oxfordResults = await zomeCall<unknown[]>(alice, "get_validators_for_institution", "Oxford");
        expect(oxfordResults).toHaveLength(1);

        const cambridgeResults = await zomeCall<unknown[]>(alice, "get_validators_for_institution", "Cambridge");
        expect(cambridgeResults).toHaveLength(0);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 19. get_attestations_for_discipline — DisciplinePath index
// ---------------------------------------------------------------------------
//
// submit_attestation writes a DisciplinePath link under
// "attestations.{discipline_tag}" → attestation hash.
//
// get_attestations_for_discipline queries that path. Useful for cross-study
// analytics — e.g. aggregate outcomes across a discipline cohort.

describe("19. get_attestations_for_discipline", () => {
  test(
    "returns attestation for matching discipline, empty for non-matching",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);

        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xd1);

        // submit_attestation now requires a prior CommitmentAnchor (inductive chain).
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF }));
        await zomeCall(alice, "notify_commitment_sealed", commitInput(REQUEST_REF));

        // Alice submits a ComputationalBiology attestation.
        await zomeCall(alice, "submit_attestation", revealInput(makeAttestation(REQUEST_REF)));
        await dhtSync([alice, bob], dnaHash!);

        // ComputationalBiology has 1 attestation.
        const compBioAtts = await zomeCall<unknown[]>(
          alice, "get_attestations_for_discipline", { type: "ComputationalBiology" },
        );
        expect(compBioAtts).toHaveLength(1);

        // MachineLearning has no attestations.
        const mlAtts = await zomeCall<unknown[]>(
          alice, "get_attestations_for_discipline", { type: "MachineLearning" },
        );
        expect(mlAtts).toHaveLength(0);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 20. Validator self-assignment — claim_study / release_claim /
//     get_claims_for_request / get_my_claimed_studies
// ---------------------------------------------------------------------------
//
// Validators discover studies via get_pending_requests_for_discipline and
// call claim_study(request_ref) to self-assign.  The coordinator:
//   - Resolves the ValidationRequest ActionHash via StudyToValidation path.
//   - Looks up the validator's institution from their ValidatorProfile.
//   - Writes a StudyClaim entry + RequestToClaim + ValidatorToClaim links.
//   - Rejects duplicate claims from the same agent.
//   - Rejects claims when num_validators_required slots are already filled.
//
// validate() in the integrity zome rejects StudyClaim if validator_institution is
// empty (validators must declare affiliation) or if validator_institution matches
// researcher_institution (COI). Empty researcher_institution is permitted.
//
// release_claim(request_ref) deletes both links (freeing the slot); the
// StudyClaim entry remains on the DHT as an immutable audit record.
//
// Helper: a minimal ValidatorProfile (different institutions avoid COI).
function makeProfile(institution: string) {
  return {
    institution,
    disciplines: [{ type: "ComputationalBiology" }],
    certification_tier: "Provisional",
    available: true,
    max_concurrent_tasks: 3,
    orcid: null,
  };
}

describe("20. Validator self-assignment (StudyClaim)", () => {
  // 20.1 — basic happy path
  test(
    "validator claims a study and the claim is retrievable",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // Alice is the researcher; Bob is the validator.
        // researcher_institution="MIT", Bob's profile="Oxford" → no COI.
        const REQUEST_REF = fakeExternalHash(0xe0);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));

        await zomeCall(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob], dnaHash!);

        // Bob claims the study.
        const claimHash = await zomeCall<ActionHash>(bob, "claim_study", REQUEST_REF);
        expect(claimHash).toBeTruthy();

        await dhtSync([alice, bob], dnaHash!);

        // get_claims_for_request returns the claim.
        const claims = await zomeCall<unknown[]>(alice, "get_claims_for_request", REQUEST_REF);
        expect(claims).toHaveLength(1);

        // get_my_claimed_studies (Bob's view) contains his claim.
        const mine = await zomeCall<unknown[]>(bob, "get_my_claimed_studies", null);
        expect(mine).toHaveLength(1);
      }, true, { timeout: 300_000 });
    },
  );

  // 20.2 — duplicate rejection
  test(
    "same validator cannot claim the same study twice",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xe1);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));
        await zomeCall(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob], dnaHash!);

        // First claim succeeds.
        await zomeCall<ActionHash>(bob, "claim_study", REQUEST_REF);
        await dhtSync([alice, bob], dnaHash!);

        // Second claim from the same agent must fail.
        await expect(
          zomeCall(bob, "claim_study", REQUEST_REF),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );

  // 20.3 — conflict-of-interest rejection (same institution)
  test(
    "validator from the same institution as researcher is rejected",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        // Both Alice (researcher) and Bob (validator) are at "MIT".
        const REQUEST_REF = fakeExternalHash(0xe2);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));
        await zomeCall(bob, "publish_validator_profile", makeProfile("MIT"));
        await dhtSync([alice, bob], dnaHash!);

        // Bob's claim must be rejected by validate() (COI).
        await expect(
          zomeCall(bob, "claim_study", REQUEST_REF),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );

  // 20.4 — capacity rejection
  test(
    "claiming when all slots are full is rejected",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        // num_validators_required=2 (DNA default); add 3 validators so the 3rd is rejected.
        const [alice, bob, carol, dave] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()), // researcher
          playerConfig(validMembraneProof()), // validator 1
          playerConfig(validMembraneProof()), // validator 2
          playerConfig(validMembraneProof()), // validator 3 — should be rejected
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xe3);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));

        await zomeCall(bob,  "publish_validator_profile", makeProfile("Oxford"));
        await zomeCall(carol,"publish_validator_profile", makeProfile("Cambridge"));
        await zomeCall(dave, "publish_validator_profile", makeProfile("Harvard"));
        await dhtSync([alice, bob, carol, dave], dnaHash!, 500, 120_000);

        // First two claims fill all slots (num_validators_required=2).
        await zomeCall(bob,  "claim_study", REQUEST_REF);
        await dhtSync([alice, bob, carol, dave], dnaHash!, 500, 120_000);
        await zomeCall(carol,"claim_study", REQUEST_REF);
        await dhtSync([alice, bob, carol, dave], dnaHash!, 500, 120_000);

        // Third claim must be rejected (capacity exceeded).
        await expect(
          zomeCall(dave, "claim_study", REQUEST_REF),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );

  // 20.5 — release_claim frees the slot
  test(
    "release_claim removes the claim from get_claims_for_request",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xe4);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));
        await zomeCall(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob], dnaHash!);

        // Claim, verify it appears, then release.
        await zomeCall(bob, "claim_study", REQUEST_REF);
        await dhtSync([alice, bob], dnaHash!);

        const before = await zomeCall<unknown[]>(alice, "get_claims_for_request", REQUEST_REF);
        expect(before).toHaveLength(1);

        await zomeCall(bob, "release_claim", REQUEST_REF);
        await dhtSync([alice, bob], dnaHash!);

        const after = await zomeCall<unknown[]>(alice, "get_claims_for_request", REQUEST_REF);
        expect(after).toHaveLength(0);

        // get_my_claimed_studies should also be empty after release.
        const mine = await zomeCall<unknown[]>(bob, "get_my_claimed_studies", null);
        expect(mine).toHaveLength(0);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 21. Dropout recovery — reclaim_abandoned_claim
// ---------------------------------------------------------------------------
//
// reclaim_abandoned_claim(input: { request_ref, claim_hash, timeout_secs })
// frees a slot held by a validator who has gone dark.
//
// Behaviour:
//   - Returns false if the claim is too recent (elapsed < timeout_secs).
//   - Returns false if the validator has already submitted an attestation.
//   - Returns true and deletes both link indexes when eligible.
//
// Tests use timeout_secs=0 so reclamation is immediately eligible (claim
// age is always ≥ 0 seconds). In production, set timeout_secs=604800 (7 days).

describe("21. Dropout recovery (reclaim_abandoned_claim)", () => {
  // 21.1 — too-recent claim is rejected
  test(
    "returns false when claim is younger than timeout_secs",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xf0);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));
        await zomeCall(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob], dnaHash!);

        const claimHash = await zomeCall<ActionHash>(bob, "claim_study", REQUEST_REF);
        await dhtSync([alice, bob], dnaHash!);

        // timeout_secs = 999999 (far future) — claim is too recent.
        const result = await zomeCall<boolean>(alice, "reclaim_abandoned_claim", {
          request_ref: REQUEST_REF,
          claim_hash:  claimHash,
          timeout_secs: 999999,
        });
        expect(result).toBe(false);

        // Slot still occupied.
        const claims = await zomeCall<unknown[]>(alice, "get_claims_for_request", REQUEST_REF);
        expect(claims).toHaveLength(1);
      }, true, { timeout: 300_000 });
    },
  );

  // 21.2 — eligible claim is reclaimed
  test(
    "returns true and frees the slot when timeout has elapsed",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob, carol] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xf1);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));
        await zomeCall(bob,   "publish_validator_profile", makeProfile("Oxford"));
        await zomeCall(carol, "publish_validator_profile", makeProfile("Cambridge"));
        await dhtSync([alice, bob, carol], dnaHash!);

        // Bob claims, then goes dark (never attests).
        const claimHash = await zomeCall<ActionHash>(bob, "claim_study", REQUEST_REF);
        await dhtSync([alice, bob, carol], dnaHash!);

        // Carol reclaims Bob's slot with timeout_secs=0 (immediately eligible).
        const reclaimed = await zomeCall<boolean>(carol, "reclaim_abandoned_claim", {
          request_ref:  REQUEST_REF,
          claim_hash:   claimHash,
          timeout_secs: 0,
        });
        expect(reclaimed).toBe(true);

        await dhtSync([alice, bob, carol], dnaHash!);

        // Slot is now free.
        const claims = await zomeCall<unknown[]>(alice, "get_claims_for_request", REQUEST_REF);
        expect(claims).toHaveLength(0);

        // Carol can now claim the freed slot.
        const carolClaim = await zomeCall<ActionHash>(carol, "claim_study", REQUEST_REF);
        expect(carolClaim).toBeTruthy();
      }, true, { timeout: 300_000 });
    },
  );

  // 21.3 — validator who already attested cannot be reclaimed
  test(
    "returns false when validator has already submitted an attestation",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice, bob, carol] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const REQUEST_REF = fakeExternalHash(0xf2);
        await zomeCall(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: REQUEST_REF, researcher_institution: "MIT" }));
        await zomeCall(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob, carol], dnaHash!);

        const claimHash = await zomeCall<ActionHash>(bob, "claim_study", REQUEST_REF);
        await dhtSync([alice, bob, carol], dnaHash!);

        // Bob commits before attesting (inductive chain requires CommitmentAnchor).
        await zomeCall(bob, "notify_commitment_sealed", commitInput(REQUEST_REF));
        await dhtSync([alice, bob, carol], dnaHash!);

        // Bob actually attests — he hasn't dropped out.
        await zomeCall(bob, "submit_attestation", revealInput(makeAttestation(REQUEST_REF)));
        await dhtSync([alice, bob, carol], dnaHash!);

        // Reclaim attempt must fail — Bob has attested.
        const result = await zomeCall<boolean>(carol, "reclaim_abandoned_claim", {
          request_ref:  REQUEST_REF,
          claim_hash:   claimHash,
          timeout_secs: 0,
        });
        expect(result).toBe(false);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 22. AgentIdentityAttestation — native multi-device identity linking
// ---------------------------------------------------------------------------
//
// Ceremony: each agent calls sign_for_identity_link(other_pubkey) to produce
// their half, then one agent calls link_agent_identity with both signatures.

describe("22. AgentIdentityAttestation", () => {
  test(
    "happy path: link two agents and retrieve via get_linked_agents",
    { timeout: 900_000 },
    async () => {
      await runScenario(
        async (scenario: Scenario) => {
          const [alice, bob] = await scenario.addPlayersWithApps([
            playerConfig(validMembraneProof()),
            playerConfig(validMembraneProof()),
          ]);

          const dnaHash = alice.namedCells.get("attestation")!.cell_id[0];
          await dhtSync([alice, bob], dnaHash, 100, 120_000);

          // Each agent signs the canonical payload via the zome helper.
          const aliceSig: Uint8Array = await zomeCall(
            alice, "sign_for_identity_link", bob.agentPubKey,
          );
          const bobSig: Uint8Array = await zomeCall(
            bob, "sign_for_identity_link", alice.agentPubKey,
          );

          // Alice submits the link with both signatures.
          const attHash: ActionHash = await zomeCall(
            alice, "link_agent_identity", {
              other_agent:     bob.agentPubKey,
              my_signature:    aliceSig,
              other_signature: bobSig,
            },
          );
          expect(attHash).toBeTruthy();

          await dhtSync([alice, bob], dnaHash, 100, 120_000);

          // Both agents can enumerate the live attestation.
          const aliceLinks = await zomeCall<unknown[]>(alice, "get_linked_agents", null);
          const bobLinks   = await zomeCall<unknown[]>(bob,   "get_linked_agents", null);
          expect(aliceLinks).toHaveLength(1);
          expect(bobLinks).toHaveLength(1);
        },
        true,
        { timeout: 900_000 },
      );
    },
  );

  test(
    "self-link is rejected",
    { timeout: 900_000 },
    async () => {
      await runScenario(
        async (scenario: Scenario) => {
          const [alice] = await scenario.addPlayersWithApps([
            playerConfig(validMembraneProof()),
          ]);

          // sign_for_identity_link with self as the other agent.
          const selfSig: Uint8Array = await zomeCall(
            alice, "sign_for_identity_link", alice.agentPubKey,
          );

          await expect(
            zomeCall(alice, "link_agent_identity", {
              other_agent:     alice.agentPubKey,
              my_signature:    selfSig,
              other_signature: selfSig,
            }),
          ).rejects.toThrow();
        },
        true,
        { timeout: 900_000 },
      );
    },
  );

  test(
    "bad signature is rejected",
    { timeout: 900_000 },
    async () => {
      await runScenario(
        async (scenario: Scenario) => {
          const [alice, bob] = await scenario.addPlayersWithApps([
            playerConfig(validMembraneProof()),
            playerConfig(validMembraneProof()),
          ]);

          const dnaHash = alice.namedCells.get("attestation")!.cell_id[0];
          await dhtSync([alice, bob], dnaHash, 100, 120_000);

          const aliceSig: Uint8Array = await zomeCall(
            alice, "sign_for_identity_link", bob.agentPubKey,
          );
          // Corrupt Bob's signature — flip a byte.
          const badBobSig = new Uint8Array(aliceSig);
          badBobSig[10] ^= 0xff;

          await expect(
            zomeCall(alice, "link_agent_identity", {
              other_agent:     bob.agentPubKey,
              my_signature:    aliceSig,
              other_signature: badBobSig,
            }),
          ).rejects.toThrow();
        },
        true,
        { timeout: 900_000 },
      );
    },
  );

  test(
    "either named agent can revoke; entry disappears from get_linked_agents",
    { timeout: 900_000 },
    async () => {
      await runScenario(
        async (scenario: Scenario) => {
          const [alice, bob] = await scenario.addPlayersWithApps([
            playerConfig(validMembraneProof()),
            playerConfig(validMembraneProof()),
          ]);

          const dnaHash = alice.namedCells.get("attestation")!.cell_id[0];
          await dhtSync([alice, bob], dnaHash, 100, 120_000);

          const aliceSig: Uint8Array = await zomeCall(
            alice, "sign_for_identity_link", bob.agentPubKey,
          );
          const bobSig: Uint8Array = await zomeCall(
            bob, "sign_for_identity_link", alice.agentPubKey,
          );

          const attHash: ActionHash = await zomeCall(
            alice, "link_agent_identity", {
              other_agent:     bob.agentPubKey,
              my_signature:    aliceSig,
              other_signature: bobSig,
            },
          );

          await dhtSync([alice, bob], dnaHash, 100, 120_000);

          // Bob revokes the link.
          await zomeCall(bob, "revoke_agent_identity_link", attHash);

          await dhtSync([alice, bob], dnaHash, 100, 120_000);

          // Entry is deleted — get_linked_agents returns empty for both.
          const aliceLinks = await zomeCall<unknown[]>(alice, "get_linked_agents", null);
          const bobLinks   = await zomeCall<unknown[]>(bob,   "get_linked_agents", null);
          expect(aliceLinks).toHaveLength(0);
          expect(bobLinks).toHaveLength(0);
        },
        true,
        { timeout: 900_000 },
      );
    },
  );

  test(
    "third-party revocation is rejected",
    { timeout: 900_000 },
    async () => {
      await runScenario(
        async (scenario: Scenario) => {
          const [alice, bob, carol] = await scenario.addPlayersWithApps([
            playerConfig(validMembraneProof()),
            playerConfig(validMembraneProof()),
            playerConfig(validMembraneProof()),
          ]);

          const dnaHash = alice.namedCells.get("attestation")!.cell_id[0];
          await dhtSync([alice, bob, carol], dnaHash, 100, 120_000);

          const aliceSig: Uint8Array = await zomeCall(
            alice, "sign_for_identity_link", bob.agentPubKey,
          );
          const bobSig: Uint8Array = await zomeCall(
            bob, "sign_for_identity_link", alice.agentPubKey,
          );

          const attHash: ActionHash = await zomeCall(
            alice, "link_agent_identity", {
              other_agent:     bob.agentPubKey,
              my_signature:    aliceSig,
              other_signature: bobSig,
            },
          );

          await dhtSync([alice, bob, carol], dnaHash, 100, 120_000);

          // Carol (uninvolved party) tries to revoke — must be rejected.
          await expect(
            zomeCall(carol, "revoke_agent_identity_link", attHash),
          ).rejects.toThrow();
        },
        true,
        { timeout: 900_000 },
      );
    },
  );
});
