
<div align="center">
  <img src="../Valichord logo-standard v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">
</div>

# Test Scenario Specification


Distributed Validation Infrastructure for Computational Research

This document defines seven test scenarios for ValiChord's Holochain implementation, written using the Tryorama testing framework. Each scenario demonstrates a specific trust guarantee that the system must uphold. The scenarios are intended for review by Holochain engineers, academic partners, and research integrity stakeholders.

Author
Ceri John — Independent Researcher & Documentary Filmmaker
Project
ValiChord — Distributed Validation Infrastructure
Status
Specification Draft — February 2026
Implementation Update (March 2026): The trust guarantees specified in this document have been verified in the actual implementation. 94 Tryorama integration tests pass against live Holochain conductors, plus a sweettest Rust suite covering all four DNAs. See valichord/tests/ for the authoritative Tryorama suite, valichord/sweettest_integration/ for the Rust suite, and docs/14_ValiChord_Integration_Tests.md for the full test inventory. Function names in the implementation may differ slightly from the placeholder names used in this specification document.
Date
February 2026
Framework
Tryorama (Holochain JavaScript Test Framework)
Language
TypeScript

Introduction
ValiChord is a distributed infrastructure for validating computational research. It uses Holochain — a cryptographically secured, agent-centric distributed computing platform — to create a tamper-evident record of the validation process that no single institution controls.

This document specifies seven test scenarios that collectively prove ValiChord's core trust guarantees. Each scenario is written as executable TypeScript using Tryorama, Holochain's multi-agent testing framework. Tryorama allows us to simulate multiple independent researchers and validators running on separate virtual nodes, including scenarios where participants go offline, behave maliciously, or attempt to game the system.

These scenarios are not yet executed — they depend on a compiled Holochain back end. They are written here to demonstrate that ValiChord's trust assumptions have been thought through at the implementation level, and to serve as a specification for the engineering team.

What Tryorama Does
Tryorama is a JavaScript-based test framework that runs real Holochain conductors in a controlled environment. Each 'player' in a scenario represents an independent agent running their own node — exactly as validators and researchers would in production. The framework provides:

Multiple independent agents running real Holochain conductors
dhtSync() — a function that waits for DHT propagation between nodes before assertions
conductor.shutDown() / startUp() — simulate nodes going offline and returning
Signal handlers — listen for UI notifications sent between agents
callZome() — invoke back-end functions as any agent would from a front end

Trust Guarantee Summary

Trust Guarantee
What It Prevents
Test Scenario
Membrane integrity
Uncredentialed agents cannot join the validator network
Scenario 1
Attestation immutability
Validators cannot alter findings after committing
Scenario 2
Protocol resilience
One offline validator does not hang the protocol
Scenario 3, 4
Collusion resistance
Coordinated validators produce statistically detectable signatures
Scenario 5
Double-blind integrity
Researcher identity is not visible to validators during review
Scenario 6
Fork prevention
Validators cannot submit two different results for the same task
Scenario 7

How to Read Each Scenario
Each scenario is structured in four parts:

What This Tests — a plain-English statement of the trust guarantee being verified
Why It Matters — the research integrity consequence if this guarantee failed
The Test Code — executable TypeScript in Tryorama structure
Expected Result — what must be true for the scenario to pass

Scenario 1  Membrane Proof — Uncredentialed Agent Rejected

What This Tests
The Attestation DNA's membrane correctly rejects an agent who does not hold a valid institutional credential, preventing them from joining the validator network.

Why It Matters
ValiChord's credibility rests on validators being accountable, identifiable professionals. An open network where anyone could join as a validator would allow bad actors to flood the system with fraudulent attestations. The membrane is the first line of defence.

Test Code

import { runScenario, dhtSync } from "@holochain/tryorama";

// SCENARIO 1: Membrane Proof — Uncredentialed Agent Rejected

test("uncredentialed agent cannot join Attestation DNA", async () => {
  await runScenario(async (scenario) => {

    // Alice holds a valid institutional credential signed by
    // the recognised authority (e.g. Cardiff University Research Office).
    // This credential is her membrane proof.
    const validCredential = generateValidCredential({
      institution: "Cardiff University",
      role: "PostdoctoralResearcher",
      signedBy: RECOGNISED_AUTHORITY_KEYPAIR,
    });

    // Bob has no credential at all — he just wants to join.
    const noCredential = null;

    // Eve has a credential, but it was signed by an unrecognised authority.
    const forgeddCredential = generateValidCredential({
      institution: "Eve's Institute",
      role: "SeniorResearcher",
      signedBy: UNRECOGNISED_KEYPAIR,  // Not in DNA properties
    });

    // Alice should join successfully
    const alice = await scenario.addPlayerWithApp({
      appBundleSource: { path: VALICHORD_HAPP_PATH },
      options: {
        rolesSettings: {
          attestation: { membrane_proof: validCredential }
        }
      }
    });
    expect(alice).toBeDefined();

    // Bob should be rejected — no credential
    await expect(
      scenario.addPlayerWithApp({
        appBundleSource: { path: VALICHORD_HAPP_PATH },
        options: {
          rolesSettings: {
            attestation: { membrane_proof: noCredential }
          }
        }
      })
    ).rejects.toThrow(/membrane proof/i);

    // Eve should be rejected — unrecognised signing authority
    await expect(
      scenario.addPlayerWithApp({
        appBundleSource: { path: VALICHORD_HAPP_PATH },
        options: {
          rolesSettings: {
            attestation: { membrane_proof: forgeddCredential }
          }
        }
      })
    ).rejects.toThrow(/invalid credential authority/i);

  });
});

Expected Result
Alice joins successfully. Bob and Eve are both rejected at the genesis stage, before they can write anything to the DHT. Their rejection is recorded as a Warrant on the DHT, visible to other participants.

Scenario 2  Commit-Reveal Integrity — Attestation Cannot Be Altered After Committing

What This Tests
Once a validator writes a commitment hash to the DHT, the system verifies that their revealed attestation matches that hash. A tampered or substituted attestation is rejected.

Why It Matters
Without commit-reveal, a dishonest validator could wait to see other validators' results and then adjust their own to influence the outcome. The commitment hash acts as a cryptographic seal on their findings, submitted before any results are visible.

Test Code

// SCENARIO 2: Commit-Reveal Integrity

test("validator cannot alter attestation after committing", async () => {
  await runScenario(async (scenario) => {

    const [alice, bob, carol] = await scenario.addPlayersWithApps([
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Researcher
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator
    ]);

    // Alice submits a study for validation
    const protocolHash = await alice.appWs.callZome({
      role_name: "researcher_repository",
      zome_name: "protocols",
      fn_name: "submit_protocol",
      payload: SAMPLE_PROTOCOL,
    });

    // Bob computes his real attestation and commits a hash of it
    const bobTrueAttestation = {
      outcome: "Reproduced",
      confidence: "High",
      time_invested_hours: 6,
    };
    const bobCommitmentHash = hashAttestation(bobTrueAttestation);

    await bob.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: { protocol_hash: protocolHash, commitment_hash: bobCommitmentHash },
    });

    await dhtSync([alice, bob, carol], alice.dnaHash("attestation"));

    // Bob attempts to reveal a DIFFERENT attestation — he changed his mind
    // after seeing that Carol revealed "Failed"
    const bobTamperedAttestation = {
      outcome: "Failed",      // Changed to match Carol
      confidence: "Medium",
      time_invested_hours: 6,
    };

    // This reveal should be REJECTED because:
    //   hash(tamperedAttestation) !== bobCommitmentHash
    await expect(
      bob.appWs.callZome({
        role_name: "attestation",
        zome_name: "validation",
        fn_name: "reveal_attestation",
        payload: { attestation: bobTamperedAttestation },
      })
    ).rejects.toThrow(/commitment hash mismatch/i);

    // Bob's true attestation reveals correctly
    await expect(
      bob.appWs.callZome({
        role_name: "attestation",
        zome_name: "validation",
        fn_name: "reveal_attestation",
        payload: { attestation: bobTrueAttestation },
      })
    ).resolves.toBeDefined();

  });
});

Expected Result
Bob's tampered reveal is rejected with a commitment hash mismatch error. His true attestation reveals successfully. The Harmony Record reflects Bob's original finding, not the post-hoc revision.

Scenario 3  Offline Validator Resilience — Protocol Continues With Quorum

What This Tests
If one validator goes offline after committing but before revealing, the protocol can still proceed to completion once quorum (two of three) have revealed — without hanging indefinitely.

Why It Matters
A protocol that requires unanimous participation is fragile in practice. Validators may lose internet connectivity, change jobs, or simply miss a deadline. The system must be resilient to partial non-participation while maintaining its integrity guarantees.

Test Code

// SCENARIO 3: Offline Validator Resilience

test("protocol completes with two of three validators revealing", async () => {
  await runScenario(async (scenario) => {

    const [alice, bob, carol, dave] = await scenario.addPlayersWithApps([
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Researcher
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 1
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 2
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 3
    ]);

    // All three validators commit their hashes
    for (const validator of [bob, carol, dave]) {
      await validator.appWs.callZome({
        role_name: "attestation",
        zome_name: "validation",
        fn_name: "submit_commitment",
        payload: { commitment_hash: hashAttestation(SAMPLE_ATTESTATION) },
      });
    }

    await dhtSync([alice, bob, carol, dave], alice.dnaHash("attestation"));

    // Dave goes offline before revealing — simulates a real-world dropout
    await dave.conductor.shutDown();

    // Bob and Carol reveal successfully — quorum of 2/3 is met
    await bob.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "reveal_attestation",
      payload: { attestation: SAMPLE_ATTESTATION },
    });

    await carol.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "reveal_attestation",
      payload: { attestation: SAMPLE_ATTESTATION },
    });

    await dhtSync([alice, bob, carol], alice.dnaHash("attestation"));

    // Harmony Record should be generatable with 2/3 revealed
    const harmonyRecord = await alice.appWs.callZome({
      role_name: "governance",
      zome_name: "harmony",
      fn_name: "generate_harmony_record",
      payload: { protocol_hash: PROTOCOL_HASH },
    });

    expect(harmonyRecord).toBeDefined();
    expect(harmonyRecord.validation_summary.total_validators).toBe(3);
    // Dave's non-reveal is recorded as Withdrawn/TimedOut, not as failure
    expect(harmonyRecord.validation_summary.successful_validations).toBe(2);

  });
});

Expected Result
A valid Harmony Record is produced reflecting two successful validations and one recorded withdrawal. Dave's disconnection delays the Harmony Record but does not prevent it. When Dave reconnects, his committed hash remains on the DHT as evidence of his original intent.

Scenario 4  Phase Transition Is DHT-Driven — Not Signal-Driven

What This Tests
A validator who was offline when the 'reveal phase open' signal was sent still transitions correctly to the reveal phase when they reconnect — because phase state is read from the DHT, not from a signal that may never have arrived.

Why It Matters
Signals in Holochain are fire-and-forget: if a peer is offline when a signal fires, it is lost permanently. A system that relies on signals for protocol phase transitions would silently stall for any validator who happened to be offline at the wrong moment. All phase logic must instead query the DHT for current state.

Test Code

// SCENARIO 4: Phase Transition Is DHT-Driven

test("offline validator learns phase state from DHT on reconnect", async () => {
  await runScenario(async (scenario) => {

    const [alice, bob, carol] = await scenario.addPlayersWithApps([
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Researcher
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 1
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 2
    ]);

    // Carol goes offline immediately after committing
    await carol.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: { commitment_hash: hashAttestation(CAROL_ATTESTATION) },
    });
    await carol.conductor.shutDown();

    // Bob commits and then Alice's coordinator opens the reveal phase
    // This emits a signal — but Carol is offline and misses it entirely
    await bob.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: { commitment_hash: hashAttestation(BOB_ATTESTATION) },
    });

    // Reveal phase opens — writes phase entry to the DHT
    await alice.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "open_reveal_phase",
      payload: { protocol_hash: PROTOCOL_HASH },
    });

    await dhtSync([alice, bob], alice.dnaHash("attestation"));

    // Carol comes back online — she missed the signal entirely
    await carol.conductor.startUp();

    // Carol polls the DHT to check current phase state
    // (This is what the coordinator zome does — no reliance on signals)
    const phaseState = await carol.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "get_current_phase",
      payload: { protocol_hash: PROTOCOL_HASH },
    });

    // Carol correctly sees the reveal phase is open
    expect(phaseState.phase).toBe("RevealOpen");

    // Carol can now reveal her attestation normally
    await expect(
      carol.appWs.callZome({
        role_name: "attestation",
        zome_name: "validation",
        fn_name: "reveal_attestation",
        payload: { attestation: CAROL_ATTESTATION },
      })
    ).resolves.toBeDefined();

  });
});

Expected Result
Carol correctly determines the reveal phase is open by reading DHT state, despite never receiving the signal. She reveals her attestation successfully. The protocol is robust to intermittent connectivity.

Scenario 5  Collusion Detection — Identical Commitments Flagged

What This Tests
If two validators submit byte-identical commitment hashes within seconds of each other, the coordinator detects this as a statistically improbable event and flags the validation for review.

Why It Matters
Two validators who independently run a study on different hardware will almost never produce byte-identical output — different floating-point rounding, different execution times, different random seeds all produce minute differences. Identical hashes are a near-certain sign of coordination. This is the system's front-line defence against collusion rings.

Test Code

// SCENARIO 5: Collusion Detection

test("identical commitment hashes are flagged as suspicious", async () => {
  await runScenario(async (scenario) => {

    const [alice, bob, carol, dave] = await scenario.addPlayersWithApps([
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Researcher
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 1 (honest)
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 2 (colluding)
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator 3 (colluding)
    ]);

    // Bob submits an honest, independently computed commitment
    await bob.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: { commitment_hash: hashAttestation(BOB_INDEPENDENT_ATTESTATION) },
    });

    // Carol and Dave are colluding — they agreed on a result in advance
    // and submit exactly the same commitment hash within 3 seconds
    const COLLUDED_HASH = hashAttestation(SHARED_FAKE_ATTESTATION);

    await carol.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: { commitment_hash: COLLUDED_HASH },
    });

    // Dave submits the identical hash 2 seconds later
    await sleep(2000);
    await dave.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: { commitment_hash: COLLUDED_HASH },  // Identical
    });

    await dhtSync([alice, bob, carol, dave], alice.dnaHash("attestation"));

    // Coordinator checks for collusion signals after all commits received
    const collusionFlags = await alice.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "check_collusion_signals",
      payload: { protocol_hash: PROTOCOL_HASH },
    });

    // Identical hashes from Carol and Dave must be flagged
    expect(collusionFlags.suspicious_pairs.length).toBeGreaterThan(0);
    expect(collusionFlags.suspicious_pairs[0]).toMatchObject({
      validators: expect.arrayContaining([carol.agentPubKey, dave.agentPubKey]),
      reason: "IdenticalCommitmentHash",
    });

    // Bob's honest commitment is not flagged
    expect(collusionFlags.flagged_validators).not.toContain(bob.agentPubKey);

  });
});

Expected Result
Carol and Dave's identical commitment hashes are flagged as a suspicious pair. The validation is escalated for governance review before a Harmony Record is produced. Bob's independent commitment is not affected.

Scenario 6  Double-Blind Integrity — Researcher Identity Not Visible to Validators

> **Status: NOT YET IMPLEMENTED — Phase 1 target.**
> Researcher identity blinding is a design goal but is not architecturally enforced in the current implementation. `ValidationRequest.data_access_url` is visible to validators in full — if the URL contains researcher-identifying information the blinding is defeated. A blinding proxy service (opaque URL layer) is required before this test is meaningful. The test below describes the intended behaviour for Phase 1.
> The *commit-reveal* blindness (validators cannot see each other's findings) is fully implemented and tested. These are two distinct properties — do not conflate them.

What This Tests
The study materials presented to validators during the validation phase do not contain the researcher's name, institution, or AgentPubKey. Validators assess the science, not the scientist.

Why It Matters
Reputation bias is a documented problem in peer review: work from prestigious institutions receives more favourable treatment. Double-blind validation removes this vector. If a validator could simply query the DHT for the study's author, the blinding would be trivially defeated.

Test Code

// SCENARIO 6: Double-Blind Integrity

test("validator cannot retrieve researcher identity from validation materials", async () => {
  await runScenario(async (scenario) => {

    const [alice, bob] = await scenario.addPlayersWithApps([
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Researcher
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator
    ]);

    // Alice submits a protocol — her AgentPubKey is on the source chain action
    // but should NOT be visible in the blinded validation package
    const protocolHash = await alice.appWs.callZome({
      role_name: "researcher_repository",
      zome_name: "protocols",
      fn_name: "submit_protocol",
      payload: SAMPLE_PROTOCOL,
    });

    await dhtSync([alice, bob], alice.dnaHash("attestation"));

    // Bob retrieves the validation package — the blinded view of the study
    const validationPackage = await bob.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "get_validation_package",
      payload: { protocol_hash: protocolHash },
    });

    // The package must not contain Alice's identity in any form
    expect(validationPackage.researcher_id).toBeUndefined();
    expect(validationPackage.researcher_name).toBeUndefined();
    expect(validationPackage.institution).toBeUndefined();

    // The package also must not contain the protocol's ActionHash
    // (which could be used to trace back to the author via get_agent_activity)
    expect(validationPackage.action_hash).toBeUndefined();

    // Scientific content is present
    expect(validationPackage.data_snapshot_hash).toBeDefined();
    expect(validationPackage.analysis_plan).toBeDefined();
    expect(validationPackage.discipline).toBeDefined();

  });
});

Expected Result
The validation package returned to Bob contains the scientific content needed to replicate the study but no information that would identify Alice. The blinded package is the only view validators receive during the commit phase.

Scenario 7  Fork Prevention — Validator Cannot Submit Two Commitments for One Task

What This Tests
A validator who attempts to submit two different commitment hashes for the same validation task — a fork attack — is detected via source chain activity monitoring and rejected.

Why It Matters
A fork attack allows a validator to hold two conflicting results in reserve and choose which to reveal based on what other validators show. Holochain's RegisterAgentActivity DHT operation makes source chain forks detectable: every agent's actions are publicly sequenced, and a second commitment for the same task appears as an invalid chain extension.

Test Code

// SCENARIO 7: Fork Prevention

test("validator cannot submit two commitments for the same task", async () => {
  await runScenario(async (scenario) => {

    const [alice, bob] = await scenario.addPlayersWithApps([
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Researcher
      { appBundleSource: { path: VALICHORD_HAPP_PATH } },  // Validator
    ]);

    // Bob submits his first commitment honestly
    await bob.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "submit_commitment",
      payload: {
        protocol_hash: PROTOCOL_HASH,
        commitment_hash: hashAttestation(BOB_RESULT_A),
      },
    });

    // Bob attempts to submit a second, different commitment for the same task
    // He has computed two possible results and wants to choose later
    await expect(
      bob.appWs.callZome({
        role_name: "attestation",
        zome_name: "validation",
        fn_name: "submit_commitment",
        payload: {
          protocol_hash: PROTOCOL_HASH,  // Same protocol
          commitment_hash: hashAttestation(BOB_RESULT_B),  // Different hash
        },
      })
    ).rejects.toThrow(/commitment already exists for this task/i);

    await dhtSync([alice, bob], alice.dnaHash("attestation"));

    // Verify only one commitment is recorded on the DHT for Bob on this task
    const bobActivity = await alice.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "get_validator_commitments",
      payload: { validator_id: bob.agentPubKey, protocol_hash: PROTOCOL_HASH },
    });

    expect(bobActivity.commitments.length).toBe(1);

    // Bob's source chain is checked for fork attempts — any divergence
    // from linear chain history is a warrant-generating violation
    const agentStatus = await alice.appWs.callZome({
      role_name: "attestation",
      zome_name: "validation",
      fn_name: "get_agent_status",
      payload: { agent: bob.agentPubKey },
    });

    expect(agentStatus.chain_status).toBe("Valid");  // No fork detected

  });
});

Expected Result
Bob's second commitment is rejected by the coordinator zome, which checks for an existing commitment before writing. Only one commitment per validator per task is recorded on the DHT. Bob's source chain remains linear and valid. A genuine fork attempt (written to a parallel chain) would generate a Warrant DHT operation, flagging Bob network-wide.

Implementation Notes
These scenarios are written against ValiChord's intended Holochain architecture. Several implementation decisions are embedded in the test structure that the engineering team should note.

Phase Transitions
Scenarios 3 and 4 together establish a critical design rule: phase state (commit open, reveal open, complete) must be written as entries to the shared Attestation DHT, never derived solely from signals. The get_current_phase() function called in Scenario 4 reads DHT entries — it does not replay a signal history. This pattern must be enforced in the coordinator zome design.

Collusion Detection Belongs in the Coordinator
The check_collusion_signals() function in Scenario 5 is a coordinator zome function, not a validate() callback. Validation callbacks must be fully deterministic and cannot perform statistical analysis across multiple agents' actions. Collusion detection — being probabilistic and cross-agent — belongs in coordinator logic, called explicitly at the right protocol moment.

Validation Receipts and DHT Sync
All scenarios that check DHT state use dhtSync() before assertions. In production, the equivalent is waiting for sufficient validation receipts (default: 5 per operation) before considering data reliably propagated. The required_validations field on entry types can be tuned per entry — critical entries like ValidationCommitment may warrant a higher threshold.

ExternalHash for Research File Fingerprints
The data_snapshot_hash in Scenario 6 uses Holochain's ExternalHash type — a 32-byte identifier for external content (SHA-256 of the research files). ExternalHash anchors DHT links without Holochain storing or validating the content at that address. This is the correct type for all research file fingerprints in ValiChord.

Status of This Document
These scenarios are a specification, not an executed test suite. Execution requires compiled Holochain WASM zomes — the back-end implementation currently in design. The scenarios will be handed to the engineering team (Shin Sakamoto, Lead Engineer) as the primary acceptance criteria for the MVP milestone.

ValiChord — Test Scenario Specification  |  Ceri John  |  February 2026
