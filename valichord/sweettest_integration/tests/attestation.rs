//! Integration tests for DNA 3 — Attestation.
//!
//! Key design notes:
//! - `authorized_joining_certificate_issuer: ""` (dev bypass) in all test DNA
//!   properties — genesis_self_check, validate_membrane_proof, init(), and
//!   commit-reveal hash verification all bypass when this is empty.
//! - `min_claim_timeout_secs: 0` allows reclaim_abandoned_claim with timeout_secs=0.
//! - All multi-agent tests use setup_two_agents() + await_consistency_20_s.
//!
//! Test inventory:
//!   1.  submit_validation_request + get_validation_request + get_validation_request_for_data_hash
//!   2.  get_current_phase returns None before any commits
//!   3.  Two validators commit → phase transitions to RevealOpen
//!   4.  Full commit-reveal round (core 2-agent protocol)
//!   5.  get_attestations_for_request
//!   6.  ValidationAttestation immutability — no update/delete functions
//!   7.  CommitmentAnchor and PhaseMarker immutability — no update/delete functions
//!   8.  publish_validator_profile + get_validator_profile (new)
//!   9.  claim_study + release_claim (new)
//!  10.  COI rejection — same institution blocks claim (new)
//!  11.  reclaim_abandoned_claim with timeout_secs=0 (new)
//!  12.  assess_difficulty + get_difficulty_assessment (new)
//!  13.  link_agent_identity — self-link rejected (new)
//!  14.  get_linked_agents returns empty when no identity links exist (new)
//!  15.  DHT-poll phase transition (late-joining validator discovers RevealOpen)

use valichord_sweettest::*;
use attestation_integrity::{AssessmentConfidence, DifficultyTier};
use attestation_coordinator::{AssessDifficultyInput, LinkAgentIdentityInput, ReclaimInput};

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Commit phase for one validator (notify_commitment_sealed with empty hash).
async fn commit(conductor: &SweetConductor, app: &ValiChordApp, request_ref: ExternalHash) {
    let _: () = conductor
        .call(
            &app.attestation_zome(),
            "notify_commitment_sealed",
            CommitmentSealedInput {
                request_ref,
                commitment_hash: vec![0u8; 32],
            },
        )
        .await;
}

/// Reveal phase for one validator (submit_attestation with empty nonce).
async fn reveal(conductor: &SweetConductor, app: &ValiChordApp, request_ref: ExternalHash) {
    let _: ActionHash = conductor
        .call(
            &app.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref),
                nonce: vec![], // empty = dev bypass skips hash verification
            },
        )
        .await;
}

// ---------------------------------------------------------------------------
// 1. submit_validation_request + get_validation_request
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn submit_and_get_validation_request() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let request_hash: ActionHash = conductor
        .call(&zome, "submit_validation_request", make_validation_request(fake_external_hash(0xab)))
        .await;

    let record: Option<Record> = conductor
        .call(&zome, "get_validation_request", request_hash)
        .await;
    assert!(record.is_some(), "submitted ValidationRequest should be retrievable by ActionHash");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_validation_request_unknown_returns_none() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let unknown = fake_action_hash(0xff);
    let result: Option<Record> = conductor.call(&zome, "get_validation_request", unknown).await;
    assert!(result.is_none());
}

#[tokio::test(flavor = "multi_thread")]
async fn get_validation_request_for_data_hash() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let data_hash = fake_external_hash(0xac);
    conductor
        .call::<_, ActionHash>(&zome, "submit_validation_request", make_validation_request(data_hash.clone()))
        .await;

    let record: Option<Record> = conductor
        .call(&zome, "get_validation_request_for_data_hash", data_hash)
        .await;
    assert!(record.is_some(), "get_validation_request_for_data_hash should find the request");
}

// ---------------------------------------------------------------------------
// 2. get_current_phase returns None before any commits
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_current_phase_none_before_commits() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let request_ref = fake_external_hash(0x01);
    let phase: Option<String> = conductor.call(&zome, "get_current_phase", request_ref).await;
    assert!(phase.is_none(), "phase should be None before any commits");
}

// ---------------------------------------------------------------------------
// 3. Two validators commit → phase transitions to RevealOpen
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn two_commits_trigger_reveal_open_phase() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x02);

    // Submit ValidationRequest so check_all_commitments_sealed_inner can
    // find num_validators_required=2 when deciding whether to write the PhaseMarker.
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // After Alice's commit: phase still None (Bob hasn't committed yet).
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let phase_after_alice: Option<String> = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "get_current_phase", request_ref.clone())
        .await;
    assert!(phase_after_alice.is_none(), "phase should still be None after only one commit");

    // After Bob's commit: both anchors present → PhaseMarker(RevealOpen) written.
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let phase_after_both: Option<String> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_current_phase", request_ref)
        .await;
    assert_eq!(
        phase_after_both.as_deref(),
        Some("RevealOpen"),
        "phase should be RevealOpen after both validators commit"
    );
}

// ---------------------------------------------------------------------------
// 4. Full commit-reveal round
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn full_commit_reveal_round() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xcc);

    // Submit ValidationRequest.
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Both validators commit.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Both validators reveal.
    let alice_hash: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref.clone()),
                nonce: vec![],
            },
        )
        .await;
    let bob_hash: ActionHash = setup.conductors[1]
        .call(
            &setup.bob.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref.clone()),
                nonce: vec![],
            },
        )
        .await;
    assert_ne!(alice_hash, bob_hash, "Alice and Bob's attestation hashes must differ");

    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Both attestations must be retrievable.
    let attestations: Vec<Record> = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "get_attestations_for_request",
            request_ref,
        )
        .await;
    assert_eq!(attestations.len(), 2, "both attestations should be retrievable after full round");
}

// ---------------------------------------------------------------------------
// 5. get_attestations_for_request — returns empty before any reveals
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_attestations_for_request_empty_before_reveal() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let request_ref = fake_external_hash(0x03);
    let attestations: Vec<Record> = conductor
        .call(&zome, "get_attestations_for_request", request_ref)
        .await;
    assert_eq!(attestations.len(), 0);
}

// ---------------------------------------------------------------------------
// 6. ValidationAttestation immutability — no update/delete functions
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn validation_attestation_immutable_no_update_fn() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x04);

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // No update function exists — call must fail.
    let result: Result<(), _> = setup.conductors[0]
        .call_fallible(
            &setup.alice.attestation_zome(),
            "update_attestation_for_test",
            (),
        )
        .await;
    assert!(result.is_err(), "no update function for ValidationAttestation must be rejected");
}

// ---------------------------------------------------------------------------
// 7. CommitmentAnchor and PhaseMarker immutability
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn commitment_anchor_immutable_no_update_fn() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0x11);

    conductor
        .call::<_, ActionHash>(
            &zome,
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    commit(&conductor, &app, request_ref).await;

    let result: Result<(), _> = conductor
        .call_fallible(&zome, "update_commitment_for_test", ())
        .await;
    assert!(result.is_err(), "no update function for CommitmentAnchor must be rejected");
}

#[tokio::test(flavor = "multi_thread")]
async fn phase_marker_immutable_no_update_fn() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x22);

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Phase must be RevealOpen now.
    let phase: Option<String> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_current_phase", request_ref)
        .await;
    assert_eq!(phase.as_deref(), Some("RevealOpen"));

    let result: Result<(), _> = setup.conductors[0]
        .call_fallible(&setup.alice.attestation_zome(), "update_phase_marker_for_test", ())
        .await;
    assert!(result.is_err(), "no update function for PhaseMarker must be rejected");
}

// ---------------------------------------------------------------------------
// 8. publish_validator_profile + get_validator_profile (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn publish_and_get_validator_profile() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let agent = app.attestation.agent_pubkey().clone();

    let profile_hash: ActionHash = conductor
        .call(&zome, "publish_validator_profile", make_validator_profile("Open Science Lab"))
        .await;
    assert_ne!(profile_hash.as_ref().len(), 0);

    let record: Option<Record> = conductor
        .call(&zome, "get_validator_profile", agent)
        .await;
    assert!(record.is_some(), "published validator profile should be retrievable by agent key");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_validator_profile_none_when_unpublished() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let agent = app.attestation.agent_pubkey().clone();
    let result: Option<Record> = conductor.call(&zome, "get_validator_profile", agent).await;
    assert!(result.is_none(), "get_validator_profile should return None when no profile exists");
}

// ---------------------------------------------------------------------------
// 9. claim_study + release_claim (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn claim_and_release_study() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x50);

    // Alice (researcher) submits the ValidationRequest.
    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Bob (validator, different agent) publishes profile and claims the study.
    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;

    let claim_hash: ActionHash = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    assert_ne!(claim_hash.as_ref().len(), 0, "claim_study should return an ActionHash");

    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Claims for this request should include Bob's claim.
    let claims: Vec<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_claims_for_request", request_ref.clone())
        .await;
    assert_eq!(claims.len(), 1, "one claim should be registered for this request");

    // Bob releases the claim — slot freed.
    let _: () = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "release_claim", request_ref.clone())
        .await;

    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let claims_after: Vec<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_claims_for_request", request_ref)
        .await;
    assert_eq!(claims_after.len(), 0, "claim list should be empty after release");
}

// ---------------------------------------------------------------------------
// 10. COI rejection — same institution blocks StudyClaim write (new)
// ---------------------------------------------------------------------------
//
// validate() in attestation_integrity rejects StudyClaim when
// validator_institution == researcher_institution (conflict of interest).

#[tokio::test(flavor = "multi_thread")]
async fn claim_study_coi_same_institution_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let request_ref = fake_external_hash(0x51);

    // ValidationRequest with researcher_institution = "Open Science Lab".
    conductor
        .call::<_, ActionHash>(&zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;

    // Validator profile with SAME institution → COI violation.
    conductor
        .call::<_, ActionHash>(&zome, "publish_validator_profile", make_validator_profile("Open Science Lab"))
        .await;

    // validate() should reject the StudyClaim.
    let result: Result<ActionHash, _> = conductor
        .call_fallible(&zome, "claim_study", request_ref)
        .await;
    assert!(
        result.is_err(),
        "claim_study must be rejected when validator and researcher share the same institution"
    );
}

// ---------------------------------------------------------------------------
// 11. reclaim_abandoned_claim with timeout_secs=0 (new)
// ---------------------------------------------------------------------------
//
// min_claim_timeout_secs=0 in DNA properties → any timeout_secs is accepted.
// With timeout_secs=0, any claim (even one just created) can be reclaimed.
// The absent validator has not submitted an attestation → reclaim returns true.
// Alice = researcher, Bob = validator who claims but never attests (abandoned).

#[tokio::test(flavor = "multi_thread")]
async fn reclaim_abandoned_claim_timeout_zero() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x60);

    // Alice (researcher) submits the ValidationRequest.
    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Bob (validator) claims but never attests — simulating abandonment.
    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;
    let claim_hash: ActionHash = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;

    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Alice reclaims with timeout_secs=0 — succeeds immediately since Bob has
    // not attested and min_claim_timeout_secs=0 (dev bypass).
    let reclaimed: bool = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "reclaim_abandoned_claim",
            ReclaimInput {
                request_ref: request_ref.clone(),
                claim_hash,
                timeout_secs: 0,
            },
        )
        .await;
    assert!(reclaimed, "reclaim_abandoned_claim should return true when conditions are met");

    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Slot is freed — claims list should be empty.
    let claims: Vec<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_claims_for_request", request_ref)
        .await;
    assert_eq!(claims.len(), 0, "claim slot should be freed after reclamation");
}

// ---------------------------------------------------------------------------
// 12. assess_difficulty + get_difficulty_assessment (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn assess_and_get_difficulty() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let request_ref = fake_external_hash(0xf0);
    let unassessed_ref = fake_external_hash(0xf1);

    // Before assessment: both refs return None.
    let before: Option<Record> = conductor
        .call(&zome, "get_difficulty_assessment", request_ref.clone())
        .await;
    assert!(before.is_none());

    // Assess the request.
    let assessment_hash: ActionHash = conductor
        .call(
            &zome,
            "assess_difficulty",
            AssessDifficultyInput {
                request_ref:            request_ref.clone(),
                code_volume:            4,
                dependency_count:       5,
                documentation_quality:  2,
                data_accessibility:     3,
                environment_complexity: 4,
                study_age_years:        3,
                predicted_tier:         DifficultyTier::Moderate,
                predicted_min_secs:     14_400,
                predicted_max_secs:     43_200,
                confidence:             AssessmentConfidence::Medium,
            },
        )
        .await;
    assert_ne!(assessment_hash.as_ref().len(), 0);

    // Assessed ref must return Some.
    let record: Option<Record> = conductor
        .call(&zome, "get_difficulty_assessment", request_ref)
        .await;
    assert!(record.is_some(), "difficulty assessment should be retrievable by request_ref");

    // A different unassessed ref must still return None.
    let null_result: Option<Record> = conductor
        .call(&zome, "get_difficulty_assessment", unassessed_ref)
        .await;
    assert!(null_result.is_none());
}

// ---------------------------------------------------------------------------
// 13. link_agent_identity — self-link rejected (new)
// ---------------------------------------------------------------------------
//
// link_agent_identity explicitly checks `if caller == other_agent` and returns
// an error. The signatures and Signature type are not needed to test this path.

#[tokio::test(flavor = "multi_thread")]
async fn link_agent_identity_self_link_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let agent = app.attestation.agent_pubkey().clone();

    // Build a fake signature (64 zero bytes — won't be verified since the
    // self-link check fires first).
    let fake_sig = Signature([0u8; 64]);

    let result: Result<ActionHash, _> = conductor
        .call_fallible(
            &zome,
            "link_agent_identity",
            LinkAgentIdentityInput {
                other_agent:     agent.clone(),
                my_signature:    fake_sig.clone(),
                other_signature: fake_sig,
            },
        )
        .await;
    assert!(result.is_err(), "linking an agent to itself must be rejected");
}

// ---------------------------------------------------------------------------
// 14. get_linked_agents returns empty when no identity links exist (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_linked_agents_empty_initially() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let agents: Vec<Record> = conductor.call(&zome, "get_linked_agents", ()).await;
    assert_eq!(agents.len(), 0, "get_linked_agents should return empty when no links exist");
}

// ---------------------------------------------------------------------------
// 15. DHT-poll phase transition (late-joining validator)
// ---------------------------------------------------------------------------
//
// Engineering constraint: phase transitions MUST be discoverable via DHT
// polling. Signals are fire-and-forget and cannot be relied upon.
//
// Carol and Dave commit; Eve comes online AFTER the PhaseMarker is written
// (she missed the signal). Eve polls get_current_phase() and discovers
// RevealOpen via DHT, not via a signal.

#[tokio::test(flavor = "multi_thread")]
async fn late_joining_validator_discovers_reveal_open_via_dht_poll() {
    // Inline 3-conductor setup.
    let mut conductors = SweetConductorBatch::from_standard_config_rendezvous(3).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut iter = apps.into_inner().into_iter();
    let carol = ValiChordApp::from_sweet_app(iter.next().unwrap());
    let dave  = ValiChordApp::from_sweet_app(iter.next().unwrap());
    let eve   = ValiChordApp::from_sweet_app(iter.next().unwrap());

    let request_ref = fake_external_hash(0xee);

    // Submit ValidationRequest so check_all_commitments_sealed_inner can
    // find num_validators_required=2 when writing the PhaseMarker.
    let _: ActionHash = conductors[0]
        .call(&carol.attestation_zome(), "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;
    await_consistency_20_s([&carol.attestation, &dave.attestation, &eve.attestation])
        .await
        .unwrap();

    // Carol and Dave commit — Eve is "offline" (not involved yet).
    commit(&conductors[0], &carol, request_ref.clone()).await;
    await_consistency_20_s([&carol.attestation, &dave.attestation])
        .await
        .unwrap();
    commit(&conductors[1], &dave, request_ref.clone()).await;
    // Sync only Carol + Dave — Eve is excluded from this sync round,
    // simulating her being offline when the PhaseMarker signal fired.
    await_consistency_20_s([&carol.attestation, &dave.attestation])
        .await
        .unwrap();

    // Now include Eve in the full sync — she learns of the PhaseMarker via DHT.
    await_consistency_20_s([&carol.attestation, &dave.attestation, &eve.attestation])
        .await
        .unwrap();

    // Eve polls the DHT — must learn the phase without a signal.
    let phase: Option<String> = conductors[2]
        .call(&eve.attestation_zome(), "get_current_phase", request_ref)
        .await;
    assert_eq!(
        phase.as_deref(),
        Some("RevealOpen"),
        "late-joining validator should discover RevealOpen by polling the DHT"
    );
}
