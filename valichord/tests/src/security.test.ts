/**
 * ValiChord security regression tests — self-audit fixes (March 2026)
 *
 * Covers the 11 protocol-gap fixes from the self red-team audit in commit
 * 41e7dcb. Only guards that can be exercised at the coordinator/client layer
 * are tested here. Validate()-level guards for crafted DHT ops (link deletion,
 * badge integrity, StudyClaim mismatch) are enforced at the network layer and
 * not exercisable through normal coordinator calls.
 *
 * Prerequisites: built & packed (same as other test files).
 */

import { runScenario, dhtSync } from "@holochain/tryorama";
import {
  encodeHashToBase64,
  HoloHashType,
  hashFrom32AndType,
  ActionHash,
} from "@holochain/client";
import { expect, test, describe } from "vitest";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HAPP_PATH = path.join(__dirname, "../../workdir/valichord.happ");

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function validMembraneProof(): Uint8Array {
  return new Uint8Array(64).fill(0x42);
}

function fakeExternalHash(coreByte: number): Uint8Array {
  const core = new Uint8Array(32).fill(coreByte);
  return hashFrom32AndType(core, HoloHashType.External);
}

/** Wrap request_ref into CommitmentSealedInput (empty hash = dev bypass). */
function commitInput(requestRef: Uint8Array) {
  return { request_ref: requestRef, commitment_hash: new Uint8Array(0) };
}

/** Wrap attestation into AttestationRevealInput (empty nonce = dev bypass). */
function revealInput(attestation: object) {
  return { attestation, nonce: new Uint8Array(0) };
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

function makeValidationRequest(overrides?: Record<string, unknown>) {
  return {
    protocol_ref: null,
    data_hash: fakeExternalHash(0xab),
    data_access_url: "https://osf.io/example/files",
    protocol_access_url: "https://osf.io/example/preregistration",
    num_validators_required: 2,
    validation_tier: "Basic",
    discipline: { type: "ComputationalBiology" },
    researcher_institution: "MIT",
    ...overrides,
  };
}

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

/** Standard test player config (dev bypass: empty issuer + governance keys). */
function playerConfig(membraneProof?: Uint8Array, minValidators = 2) {
  return {
    appBundleSource: { type: "path" as const, value: HAPP_PATH },
    options: {
      rolesSettings: {
        attestation: {
          type: "provisioned" as const,
          value: {
            membrane_proof: membraneProof ?? validMembraneProof(),
            modifiers: {
              properties: {
                minimum_validators: minValidators,
                discipline: "genomics",
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
                system_coordinator_key: "",
                min_attestations_for_finalization: 0,
              },
            },
          },
        },
      },
    },
  };
}

/**
 * Player config with a min_claim_timeout_secs floor, used to verify that the
 * reclaim_abandoned_claim coordinator respects the DNA-baked minimum.
 */
function playerConfigWithMinTimeout(minTimeoutSecs: number) {
  return {
    appBundleSource: { type: "path" as const, value: HAPP_PATH },
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
                authorized_joining_certificate_issuer: "",
                min_claim_timeout_secs: minTimeoutSecs,
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
                min_attestations_for_finalization: 0,
              },
            },
          },
        },
      },
    },
  };
}

async function att(player: any, fn: string, payload?: unknown) {
  return player.appWs.callZome({
    role_name: "attestation",
    zome_name: "attestation_coordinator",
    fn_name: fn,
    payload: payload ?? null,
  });
}

// ---------------------------------------------------------------------------
// S1. Duplicate attestation guard
// ---------------------------------------------------------------------------
//
// Fix: submit_attestation now checks ValidatorToAttestation links before
// writing a new attestation entry. A second call with the same request_ref
// is rejected with "Validator has already submitted an attestation".

describe("S1. Duplicate attestation guard", () => {
  test(
    "second submit_attestation for the same study rejects",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const requestRef = fakeExternalHash(0x51);

        // notify_commitment_sealed requires a prior ValidationRequest (inductive chain).
        await att(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: requestRef }));

        // First commit + reveal — must succeed.
        await att(alice, "notify_commitment_sealed", commitInput(requestRef));
        await att(alice, "submit_attestation", revealInput(makeAttestation(requestRef)));

        // Second reveal for the same study — must be rejected.
        await expect(
          att(alice, "submit_attestation", revealInput(makeAttestation(requestRef))),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// S2. Duplicate commitment guard (Guard 2 in notify_commitment_sealed)
// ---------------------------------------------------------------------------
//
// Fix: notify_commitment_sealed checks existing RequestToCommitment links by
// author before writing a new CommitmentAnchor. A validator who calls it
// twice for the same study is rejected.

describe("S2. Duplicate commitment guard", () => {
  test(
    "second notify_commitment_sealed for the same study rejects",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const requestRef = fakeExternalHash(0x52);

        // notify_commitment_sealed requires a prior ValidationRequest (inductive chain).
        await att(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: requestRef }));

        // First commitment — must succeed.
        await att(alice, "notify_commitment_sealed", commitInput(requestRef));

        // Second commitment for same study — must be rejected.
        await expect(
          att(alice, "notify_commitment_sealed", commitInput(requestRef)),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// S3. publish_researcher_commitment idempotency guard
// ---------------------------------------------------------------------------
//
// Fix: publish_researcher_commitment checks RequestToResearcherCommitment
// links before writing. A second call for the same study is rejected,
// preventing a researcher from swapping their prediction after validators
// have started work.

describe("S3. Researcher commitment idempotency", () => {
  test(
    "second publish_researcher_commitment for the same study rejects",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
        ]);

        const requestRef = fakeExternalHash(0x53);
        const commitmentHash = new Uint8Array(32).fill(0xaa);

        const commitmentInput = {
          request_ref: requestRef,
          result_commitment_hash: commitmentHash,
        };

        // First commitment — must succeed.
        const hash = await att(alice, "publish_researcher_commitment", commitmentInput);
        expect(hash).toBeTruthy();

        // Second commitment — must be rejected.
        await expect(
          att(alice, "publish_researcher_commitment", commitmentInput),
        ).rejects.toThrow();
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// S4. reclaim_abandoned_claim respects min_claim_timeout_secs DNA floor
// ---------------------------------------------------------------------------
//
// Fix: reclaim_abandoned_claim reads min_claim_timeout_secs from DNA
// properties and enforces it as a floor even if the caller passes a smaller
// timeout_secs. This prevents governance erosion by an operator who bakes a
// minimum reclaim window into the DNA hash.

describe("S4. reclaim_abandoned_claim min_claim_timeout_secs floor", () => {
  test(
    "caller-supplied timeout below DNA floor is overridden — reclaim returns false",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Install with min_claim_timeout_secs = 86400 (one day).
        // Caller will try timeout_secs = 0 (immediate); floor must block it.
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfigWithMinTimeout(86400),
          playerConfigWithMinTimeout(86400),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const requestRef = fakeExternalHash(0x54);

        // Submit a ValidationRequest for this study.
        await att(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: requestRef, researcher_institution: "MIT" }));

        // Bob registers a profile with a different institution.
        await att(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob], dnaHash!);

        // Bob claims the study.
        const claimHash = await att(bob, "claim_study", requestRef);
        expect(claimHash).toBeTruthy();
        await dhtSync([alice, bob], dnaHash!);

        // Alice tries to reclaim with timeout_secs=0 — should be blocked by
        // the DNA floor of 86400 seconds. Claim is effectively fresh → false.
        const result = await att(alice, "reclaim_abandoned_claim", {
          request_ref:  requestRef,
          claim_hash:   claimHash,
          timeout_secs: 0,
        });
        expect(result).toBe(false);
      }, true, { timeout: 300_000 });
    },
  );

  test(
    "when no DNA floor is set (0), caller-supplied timeout_secs=0 succeeds immediately",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        // Default config has min_claim_timeout_secs unset → default 0.
        const [alice, bob] = await scenario.addPlayersWithApps([
          playerConfig(validMembraneProof()),
          playerConfig(validMembraneProof()),
        ]);
        const dnaHash = alice.namedCells.get("attestation")?.cell_id[0];

        const requestRef = fakeExternalHash(0x55);

        await att(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: requestRef, researcher_institution: "MIT" }));
        await att(bob, "publish_validator_profile", makeProfile("Oxford"));
        await dhtSync([alice, bob], dnaHash!);

        const claimHash = await att(bob, "claim_study", requestRef);
        await dhtSync([alice, bob], dnaHash!);

        // No DNA floor: timeout_secs=0 → elapsed (0 s) >= 0 → eligible.
        const result = await att(alice, "reclaim_abandoned_claim", {
          request_ref:  requestRef,
          claim_hash:   claimHash,
          timeout_secs: 0,
        });
        expect(result).toBe(true);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// S6. reveal_researcher_result idempotency guard
// ---------------------------------------------------------------------------
//
// Fix: reveal_researcher_result now checks RequestToResearcherReveal links
// before writing a new ResearcherReveal entry. A second call for the same
// study is rejected, preventing link-table bloat and non-determinism in
// get_researcher_reveal (which uses links.last()).
//
// Commitment hash: SHA256(msgpack([]) || []) where msgpack([]) = 0x90.
// Pre-computed: 9e076ceaf246b6003d9c2680a2b4cf0bffd069805902b0b5edeebf49039fe4bd

describe("S6. reveal_researcher_result idempotency", () => {
  test(
    "second reveal_researcher_result for the same study rejects",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([
          // minimum_validators=1 so alice can be the sole validator and
          // check_all_commitments_sealed passes after her single commit.
          playerConfig(validMembraneProof(), 1),
        ]);

        const requestRef = fakeExternalHash(0x56);

        // SHA256(msgpack([]) || []) — msgpack encodes empty Vec as 0x90.
        // This matches reveal payload of metrics=[], nonce=[].
        const commitmentHash = new Uint8Array(
          "9e076ceaf246b6003d9c2680a2b4cf0bffd069805902b0b5edeebf49039fe4bd"
            .match(/.{2}/g)!
            .map((b) => parseInt(b, 16)),
        );

        await att(alice, "publish_researcher_commitment", {
          request_ref: requestRef,
          result_commitment_hash: commitmentHash,
        });

        // ValidationRequest so check_all_commitments_sealed_inner can resolve
        // num_validators_required=1.
        await att(alice, "submit_validation_request",
          makeValidationRequest({ data_hash: requestRef, num_validators_required: 1 }));

        // Alice commits as the sole validator.
        await att(alice, "notify_commitment_sealed", commitInput(requestRef));

        const revealPayload = {
          request_ref: requestRef,
          metrics: [],
          nonce: new Uint8Array(0),
        };

        // First reveal — must succeed (hash matches, all preconditions met).
        await att(alice, "reveal_researcher_result", revealPayload);

        // Second reveal — idempotency guard fires before hash check.
        await expect(
          att(alice, "reveal_researcher_result", revealPayload),
        ).rejects.toThrow(/already exists/);
      }, true, { timeout: 300_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// S5. force_finalize_round — missing ValidationRequest returns null
// ---------------------------------------------------------------------------
//
// Fix: when the cross-DNA call to get the ValidationRequest returns None,
// force_finalize_round returns null conservatively (cannot verify round age).
// This guards against a crafted request_ref with no matching VR.

describe("S5. force_finalize_round conservative abort on missing VR", () => {
  test(
    "returns null when no ValidationRequest exists for the request_ref",
    { timeout: 600_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alicePlayer] = await scenario.addPlayers(1);
        const aliceKeyB64 = encodeHashToBase64(alicePlayer.agentPubKey);
        const [alice] = await scenario.installAppsForPlayers(
          [{
            appBundleSource: { type: "path" as const, value: HAPP_PATH },
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
                        authorized_joining_certificate_issuer: "",
                      },
                    },
                  },
                },
                governance: {
                  type: "provisioned" as const,
                  value: {
                    modifiers: { properties: { system_coordinator_key: aliceKeyB64 } },
                  },
                },
              },
            },
          }],
          [alicePlayer],
        );

        // No ValidationRequest and no attestation for fakeRef — conservative abort → null.
        // (Inductive validation now prevents creating an attestation without a VR, so
        // the "no attestations" early-return guard fires before the VR lookup. Both paths
        // produce the same conservative null return.)
        const fakeRef = fakeExternalHash(0x5a);

        // force_finalize_round — no VR or attestation → conservative abort → null.
        const result = await alice.appWs.callZome({
          role_name: "governance",
          zome_name: "governance_coordinator",
          fn_name: "force_finalize_round",
          payload: fakeRef,
        });
        expect(result).toBeNull();
      }, true, { timeout: 300_000 });
    },
  );
});
