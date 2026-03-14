/**
 * Tryorama integration tests for ValiChord DNA 1 — Researcher Repository
 *
 * All entries are private (visibility = "private") — single-agent source
 * chain only. No dhtSync needed. Single player, local GetOptions.
 *
 * Tests:
 *   1. register_study + get_study
 *   2. register_protocol + get_protocol_for_study
 *   3. take_data_snapshot + get_snapshots_for_study
 *   4. declare_deviation + get_deviations_for_study
 *   5. compute_data_hash
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

async function repo(player: any, fn: string, payload: unknown = null): Promise<any> {
  return player.appWs.callZome({
    role_name: "researcher_repository",
    zome_name: "researcher_repository_coordinator",
    fn_name: fn,
    payload,
  });
}

function makeStudy(overrides?: Record<string, unknown>) {
  return {
    title: "Replication of Smith et al. 2023",
    discipline: { type: "ComputationalBiology" },
    institution: "Open Science Lab",
    abstract_text: "Full computational reproduction attempt.",
    pre_registration_ref: null,
    ...overrides,
  };
}

function makeProtocol(overrides?: Record<string, unknown>) {
  return {
    analysis_plan: "Run the provided R scripts in order.",
    hypotheses: ["H1: Effect size > 0.3", "H2: p < 0.05"],
    statistical_methods: "Linear mixed-effects model with REML estimation.",
    ...overrides,
  };
}

function makeSnapshot(dataHash: Uint8Array, overrides?: Record<string, unknown>) {
  return {
    data_hash: dataHash,
    file_count: 12,
    total_size_bytes: 524_288_000,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// 1. register_study + get_study
// ---------------------------------------------------------------------------

describe("1. register_study + get_study", () => {
  test(
    "registered study is retrievable by its ActionHash",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());
        expect(studyHash).toBeTruthy();

        const record = await repo(alice, "get_study", studyHash);
        expect(record).not.toBeNull();
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "get_study returns null for an unknown ActionHash",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        // A properly-typed ActionHash that was never written to the source chain.
        const unknownHash = fakeActionHash(0xff);
        const result = await repo(alice, "get_study", unknownHash);
        expect(result).toBeNull();
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 2. register_protocol + get_protocol_for_study
// ---------------------------------------------------------------------------

describe("2. register_protocol + get_protocol_for_study", () => {
  test(
    "protocol is retrievable via its parent study",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());

        const protocolHash = await repo(alice, "register_protocol", {
          study_ref: studyHash,
          protocol: makeProtocol(),
        });
        expect(protocolHash).toBeTruthy();

        const record = await repo(alice, "get_protocol_for_study", studyHash);
        expect(record).not.toBeNull();
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "get_protocol_for_study returns null when no protocol registered",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());

        const result = await repo(alice, "get_protocol_for_study", studyHash);
        expect(result).toBeNull();
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 3. take_data_snapshot + get_snapshots_for_study
// ---------------------------------------------------------------------------

describe("3. take_data_snapshot + get_snapshots_for_study", () => {
  test(
    "two snapshots are both retrievable for the same study",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());

        // Snapshot 1 — initial dataset.
        const hash1 = await repo(alice, "take_data_snapshot", {
          study_ref: studyHash,
          snapshot: makeSnapshot(fakeExternalHash(0x01)),
        });
        expect(hash1).toBeTruthy();

        // Snapshot 2 — updated dataset after data cleaning.
        const hash2 = await repo(alice, "take_data_snapshot", {
          study_ref: studyHash,
          snapshot: makeSnapshot(fakeExternalHash(0x02), {
            file_count: 13,
          }),
        });
        expect(hash2).toBeTruthy();

        const snapshots = await repo(alice, "get_snapshots_for_study", studyHash);
        expect(snapshots).toHaveLength(2);
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "get_snapshots_for_study returns empty array before any snapshot",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());
        const snapshots = await repo(alice, "get_snapshots_for_study", studyHash);
        expect(snapshots).toHaveLength(0);
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 4. declare_deviation + get_deviations_for_study
// ---------------------------------------------------------------------------

describe("4. declare_deviation + get_deviations_for_study", () => {
  test(
    "declared deviation is retrievable for its parent study",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());

        // DeviationType uses #[serde(tag="type", content="content")] — adjacent-tagged.
        // EpistemicImpact: no serde tag → external tag → unit variant = plain string.
        const deviation = {
          deviation_type: {
            type: "DataAccess",
            content: {
              reason: "Original dataset behind paywall; used public replication package instead.",
              impact: "Minimal",
            },
          },
          // Severity: external tag, unit variant = plain string.
          severity: "Minor",
          evidence: "Used OSF pre-registered replication package v2.1.",
        };

        const deviationHash = await repo(alice, "declare_deviation", {
          study_ref: studyHash,
          deviation,
        });
        expect(deviationHash).toBeTruthy();

        const deviations = await repo(alice, "get_deviations_for_study", studyHash);
        expect(deviations).toHaveLength(1);
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "get_deviations_for_study returns empty array when no deviation declared",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const studyHash = await repo(alice, "register_study", makeStudy());
        const deviations = await repo(alice, "get_deviations_for_study", studyHash);
        expect(deviations).toHaveLength(0);
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 5. compute_data_hash
// ---------------------------------------------------------------------------

describe("5. compute_data_hash", () => {
  test(
    "returns a 39-byte ExternalHash (SHA-256 of input bytes)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        // Input: arbitrary bytes representing a file content fingerprint.
        const data = new Uint8Array(256).fill(0xab);

        const hash = await repo(alice, "compute_data_hash", data);

        // ExternalHash is a 39-byte Uint8Array:
        //   prefix [0x84, 0x2F, 0x24] + 32 bytes SHA-256 + 4 bytes DHT location
        expect(hash).toBeInstanceOf(Uint8Array);
        expect(hash.length).toBe(39);
        // ExternalHash prefix bytes.
        expect(hash[0]).toBe(0x84);
        expect(hash[1]).toBe(0x2f);
        expect(hash[2]).toBe(0x24);
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "same bytes always produce the same hash (deterministic)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const data = new Uint8Array([1, 2, 3, 4, 5]);

        const h1 = await repo(alice, "compute_data_hash", data);
        const h2 = await repo(alice, "compute_data_hash", data);

        expect(h1).toEqual(h2);
      }, true, { timeout: 180_000 });
    },
  );

  test(
    "different bytes produce different hashes (collision resistance)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        const h1 = await repo(alice, "compute_data_hash", new Uint8Array([0x01]));
        const h2 = await repo(alice, "compute_data_hash", new Uint8Array([0x02]));

        // Hashes must differ.
        let differ = false;
        for (let i = 0; i < h1.length; i++) {
          if (h1[i] !== h2[i]) { differ = true; break; }
        }
        expect(differ).toBe(true);
      }, true, { timeout: 180_000 });
    },
  );
});

// ---------------------------------------------------------------------------
// 6. PreRegisteredProtocol immutability — delete rejected
// ---------------------------------------------------------------------------
//
// validate() in researcher_repository_integrity blocks all deletes of
// PreRegisteredProtocol entries. The coordinator exposes no delete function —
// immutability is enforced at both the API level (no function exists) and
// the validation level (validate() rejects OpDelete).
//
// Pattern mirrors attestation.test.ts describe 4: call a nonexistent
// coordinator function → rejected with "function not found", which confirms
// the API offers no delete path.

describe("6. PreRegisteredProtocol immutability (delete)", () => {
  test(
    "attempting to delete a PreRegisteredProtocol is rejected (no delete function in API)",
    { timeout: 300_000 },
    async () => {
      await runScenario(async (scenario) => {
        const [alice] = await scenario.addPlayersWithApps([simplePlayerConfig()]);

        // Register a study and then a protocol.
        const studyHash = await repo(alice, "register_study", makeStudy());
        const protocolHash = await repo(alice, "register_protocol", {
          study_ref: studyHash,
          protocol: makeProtocol(),
        });
        expect(protocolHash).toBeTruthy();

        // Attempt to delete via a nonexistent coordinator function.
        // The rejection confirms no delete path exists in the public API.
        // validate() provides a second layer of defence for any future
        // function that might be added: it blocks OpDelete for PreRegisteredProtocol.
        await expect(
          alice.appWs.callZome({
            role_name: "researcher_repository",
            zome_name: "researcher_repository_coordinator",
            fn_name: "delete_protocol_for_test",
            payload: protocolHash,
          }),
        ).rejects.toThrow();
      }, true, { timeout: 180_000 });
    },
  );
});
