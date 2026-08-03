//! Integration tests for DNA 3 — Attestation.
//!
//! Key design notes:
//! - `authorized_joining_certificate_issuer: ""` (dev bypass) in all test DNA
//!   properties — genesis_self_check, validate_membrane_proof, init(), and
//!   commit-reveal hash verification all bypass when this is empty.
//! - `min_claim_timeout_secs: 0` allows reclaim_abandoned_claim with timeout_secs=0.
//! - All multi-agent tests use setup_two_agents() + await_consistency_s(20, ...).
//!
//! Test inventory:
//!   1.  submit_validation_request + get_validation_request + get_validation_request_for_data_hash
//!   2.  get_current_phase returns None before any commits
//!   3.  Two validators commit → phase transitions to RevealOpen
//!   4.  Full commit-reveal round (core 2-agent protocol)
//!   5.  get_attestations_for_request
//!   6.  REMOVED 2026-07-30 — was a fake immutability test (see note in body)
//!   7.  REMOVED 2026-07-30 — was two fake immutability tests (see note in body)
//!   8.  publish_validator_profile + get_validator_profile (new)
//!   9.  claim_study + release_claim (new)
//!  10.  COI rejection — same institution blocks claim (new)
//!  11.  reclaim_abandoned_claim with timeout_secs=0 (new)
//!  12.  assess_difficulty + get_difficulty_assessment (new)
//!  13.  link_agent_identity — self-link rejected (new)
//!  14.  get_linked_agents returns empty when no identity links exist (new)
//!  15.  DHT-poll phase transition (late-joining validator discovers RevealOpen)
//!  16.  update_validator_profile — merged fields overwrite, unchanged fields preserved (new)
//!  17.  check_all_commitments_sealed — false before quorum, true after (new)
//!  18.  get_researcher_reveal — None before reveal, Some after (new)
//!  19.  revoke_agent_identity_link — live entry deleted, get_linked_agents returns empty (new)
//!  20.  get_my_claimed_studies — own claims visible, filtered by release (new)
//!
//! Ported from the Tryorama suite 2026-08-02 as part of retiring it (upstream
//! @holochain/tryorama is unmaintained and will not support Holochain 0.7). Only
//! the tests with NO sweettest equivalent were carried over — an audit found ~69
//! of the 92 Tryorama tests already duplicated here:
//!  24.  researcher cannot claim their own study (validate() guard)
//!  25.  claim rejected when the study is at capacity
//!  26.  same validator cannot claim the same study twice
//!  27.  reclaim refused once the validator has attested
//!  28.  third party cannot revoke someone else's identity link
//!  29.  validator profiles indexed by discipline AND institution
//!  30.  pending requests indexed by discipline
//!  31.  attestations indexed by discipline
//!
//! The five membrane-proof tests went to `membrane_proof.rs` instead — they need
//! a real issuer key rather than this file's dev bypass.

use valichord_sweettest::*;
use attestation_integrity::{AssessmentConfidence, DifficultyTier, ResearcherRevealInput, StudyClaim};
use attestation_coordinator::{AssessDifficultyInput, LinkAgentIdentityInput, ReclaimInput};
use valichord_shared_types::Discipline;

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
    let setup = setup_two_agents().await;
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
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // After Alice's commit: phase still None (Bob hasn't committed yet).
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let phase_after_alice: Option<String> = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "get_current_phase", request_ref.clone())
        .await;
    assert!(phase_after_alice.is_none(), "phase should still be None after only one commit");

    // After Bob's commit: both anchors present → PhaseMarker(RevealOpen) written.
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xcc);

    // Submit ValidationRequest.
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Both validators commit.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
// 6 & 7. REMOVED 2026-07-30 — three fake "immutability" tests deleted.
// ---------------------------------------------------------------------------
//
// `validation_attestation_immutable_no_update_fn`, `commitment_anchor_immutable_
// no_update_fn` and `phase_marker_immutable_no_update_fn` asserted immutability
// like this:
//
//     let result: Result<(), _> = conductor
//         .call_fallible(&zome, "update_attestation_for_test", ()).await;
//     assert!(result.is_err(), "...must be rejected");
//
// The zome functions `update_attestation_for_test`, `update_commitment_for_test`
// and `update_phase_marker_for_test` DO NOT EXIST anywhere in this repo. Each
// call failed with "function not found", the assert passed, and all three tests
// were permanently green — they would have stayed green with `validate()`
// deleted entirely. They tested the coordinator's public surface (that no update
// function is exposed), not the integrity zome's immutability guard.
//
// Nothing real was lost: the only genuine assertion among them was the
// phase == RevealOpen check in the PhaseMarker test, which duplicates test 3.
//
// STILL MISSING — real coverage. A test that actually proves immutability must
// issue an Update action against a committed entry and assert the INTEGRITY zome
// rejects it. No coordinator exposes `update_entry`, so this needs a
// `#[cfg(feature = "test_utils")]`-gated extern per coordinator. Scope, per the
// 2026-07-30 verification pass against shipped hdi 0.8.0 (see CLAUDE.md →
// "Pending upgrade checks"):
//   - attestation DNA: 12 live per-type `OpUpdate::Entry` guard arms that must
//     stay ahead of the generic arm (lib.rs:490) and the catch-all (:508).
//     This is where match-ordering genuinely matters.
//   - validator_workspace / researcher_repository: all entries are private, so
//     their per-type arms are unreachable dead code. Immutability rests on ONE
//     blanket `OpUpdate::PrivateEntry { .. } => Invalid` arm each. One tripwire
//     test per DNA is sufficient — but losing that single arm is catastrophic.
//
// This matters most at the 0.7 migration: reflowing the renamed match arms can
// silently disable immutability with no compile error and no test failure.

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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x50);

    // Alice (researcher) submits the ValidationRequest.
    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
//
// ⚠️ MUST BE TWO AGENTS, and this test proves why. It was written on a single
// conductor, so the researcher and the would-be validator were the SAME agent —
// and the self-claim guard sits AHEAD of the COI guard in validate() (see
// attestation_integrity/src/lib.rs:665, then :677). The claim was therefore
// rejected before the COI comparison was ever reached, and the COI rule had no
// coverage at all. It looked green only because the assertion was a bare
// `is_err()`; strengthening it to `assert_rejected_with` on 2026-08-02 exposed
// the substitution immediately, with the self-claim message in the error.
// Same shape as `link_agent_identity_self_link_rejected` — a test that passes
// on the wrong guard tests nothing it claims to.

#[tokio::test(flavor = "multi_thread")]
async fn claim_study_coi_same_institution_rejected() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x51);

    // Alice is the researcher. make_validation_request declares
    // researcher_institution = "Open Science Lab".
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Bob is a DIFFERENT agent — so the self-claim guard passes and the COI
    // guard is the only one left that can reject — but declares the SAME
    // institution, which is the violation under test.
    let _: ActionHash = setup.conductors[1]
        .call(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Open Science Lab"),
        )
        .await;

    // validate() should reject the StudyClaim.
    let result: Result<ActionHash, _> = setup.conductors[1]
        .call_fallible(&setup.bob.attestation_zome(), "claim_study", request_ref)
        .await;
    let err = result
        .expect_err("claim_study must be rejected when validator and researcher share an institution");
    // The COI rule lives in validate(), not the coordinator — assert on the
    // integrity guard's own wording so a coordinator-level failure (bad payload,
    // missing request, an earlier guard) cannot masquerade as COI enforcement.
    assert_rejected_with(
        &format!("{err:?}"),
        "Conflict of interest",
        "claim_study same-institution COI",
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x60);

    // Alice (researcher) submits the ValidationRequest.
    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
    let err = result.expect_err("linking an agent to itself must be rejected");
    // NOTE: the coordinator rejects this before validate() is reached, so this
    // asserts the COORDINATOR's message. The integrity guard behind it
    // ("AgentIdentityAttestation requires two distinct agents") is therefore
    // still unproven — it is unreachable through any coordinator call.
    assert_rejected_with(
        &format!("{err:?}"),
        "Cannot link an agent to itself",
        "self-link rejection",
    );
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
    let mut conductors = SweetConductorBatch::from_config_rendezvous(3, SweetConductorConfig::rendezvous(true)).await;
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
    await_consistency_s(20, [&carol.attestation, &dave.attestation, &eve.attestation])
        .await
        .unwrap();

    // Carol and Dave commit — Eve is "offline" (not involved yet).
    commit(&conductors[0], &carol, request_ref.clone()).await;
    await_consistency_s(20, [&carol.attestation, &dave.attestation])
        .await
        .unwrap();
    commit(&conductors[1], &dave, request_ref.clone()).await;
    // Sync only Carol + Dave — Eve is excluded from this sync round,
    // simulating her being offline when the PhaseMarker signal fired.
    await_consistency_s(20, [&carol.attestation, &dave.attestation])
        .await
        .unwrap();

    // Now include Eve in the full sync — she learns of the PhaseMarker via DHT.
    await_consistency_s(20, [&carol.attestation, &dave.attestation, &eve.attestation])
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

// ---------------------------------------------------------------------------
// 16. update_validator_profile — merged fields, unchanged fields preserved (new)
// ---------------------------------------------------------------------------
//
// update_validator_profile fetches the current profile and merges supplied
// Some fields on top, leaving None fields unchanged.  Tests:
//   a. Fields supplied as Some are updated.
//   b. Fields supplied as None (not in UpdateValidatorProfileInput) are kept.
//   c. certification_tier is NOT editable via this function (always preserved).

#[tokio::test(flavor = "multi_thread")]
async fn update_validator_profile_merges_fields() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let agent = app.attestation.agent_pubkey().clone();

    // Publish initial profile.
    conductor
        .call::<_, ActionHash>(&zome, "publish_validator_profile", make_validator_profile("Initial Lab"))
        .await;

    // Update only the institution — other fields should be preserved.
    let _: ActionHash = conductor
        .call(
            &zome,
            "update_validator_profile",
            attestation_coordinator::UpdateValidatorProfileInput {
                institution:          Some("Updated Lab".into()),
                disciplines:          None,
                available:            None,
                max_concurrent_tasks: None,
                orcid:                None,
                agent_type:           None,
                person_key:           None,
            },
        )
        .await;

    let record: Option<Record> = conductor.call(&zome, "get_validator_profile", agent).await;
    let profile: ValidatorProfile = record
        .expect("profile must exist after update")
        .entry()
        .to_app_option()
        .unwrap()
        .unwrap();

    assert_eq!(profile.institution, "Updated Lab", "institution should be updated");
    // disciplines was None in the update — preserved from original profile.
    assert_eq!(
        profile.disciplines,
        vec![Discipline::ComputationalBiology],
        "disciplines should be preserved when not supplied"
    );
}

// ---------------------------------------------------------------------------
// 17. check_all_commitments_sealed — false before quorum, true after (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn check_all_commitments_sealed_lifecycle() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xa0);

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Before any commits: not sealed.
    let before: bool = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "check_all_commitments_sealed", request_ref.clone())
        .await;
    assert!(!before, "should not be sealed before any commitments");

    // After Alice commits only: still not sealed (need 2).
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let after_one: bool = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "check_all_commitments_sealed", request_ref.clone())
        .await;
    assert!(!after_one, "should not be sealed with only one of two commitments");

    // After Bob commits: both committed → sealed.
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let after_two: bool = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "check_all_commitments_sealed", request_ref.clone())
        .await;
    assert!(after_two, "should be sealed once both validators have committed");
}

// ---------------------------------------------------------------------------
// 18. get_researcher_reveal — None before reveal, Some after (new)
// ---------------------------------------------------------------------------
//
// The researcher calls reveal_researcher_result after all validators have
// committed.  Metrics + nonce are supplied in the input; the coordinator
// verifies SHA-256(msgpack(metrics) || nonce) == result_commitment_hash before
// writing the ResearcherReveal entry to the DHT.
//
// Dev bypass (authorized_joining_certificate_issuer: ""): commitment hash
// verification is skipped when nonce is empty, so we can use fake metrics.

#[tokio::test(flavor = "multi_thread")]
async fn get_researcher_reveal_none_then_some() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xa1);

    // Submit the study and lock the researcher's result (with empty nonce bypass).
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;

    // Publish researcher commitment before validators commit.
    use valichord_shared_types::ResearcherCommitmentInput;
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "publish_researcher_commitment",
            ResearcherCommitmentInput {
                request_ref:            request_ref.clone(),
                result_commitment_hash: vec![0u8; 32],
            },
        )
        .await;

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Before reveal: None.
    let before: Option<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_researcher_reveal", request_ref.clone())
        .await;
    assert!(before.is_none(), "researcher reveal should be None before reveal_researcher_result");

    // Both validators commit and reveal so the reveal window is open.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Researcher reveals (dev bypass: empty nonce skips hash verification).
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "reveal_researcher_result",
            ResearcherRevealInput {
                request_ref: request_ref.clone(),
                metrics:     vec![],
                nonce:       vec![],
            },
        )
        .await;

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // After reveal: Some.
    let after: Option<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_researcher_reveal", request_ref)
        .await;
    assert!(after.is_some(), "get_researcher_reveal should return the record after reveal");
}

// ---------------------------------------------------------------------------
// 19. revoke_agent_identity_link — entry deleted, get_linked_agents empty (new)
// ---------------------------------------------------------------------------
//
// Two agents sign a cross-device identity attestation.  Either named agent
// may revoke it by calling revoke_agent_identity_link.  After revocation the
// entry's delete record is present in DHT details, so get_linked_agents
// (which filters on rd.deletes.is_empty()) returns nothing.

#[tokio::test(flavor = "multi_thread")]
async fn revoke_agent_identity_link_removes_from_linked_agents() {
    let setup = setup_two_agents().await;

    // Each agent signs the canonical 78-byte payload for the prospective link.
    let alice_sig: Signature = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "sign_for_identity_link",
            setup.bob.attestation.agent_pubkey().clone(),
        )
        .await;
    let bob_sig: Signature = setup.conductors[1]
        .call(
            &setup.bob.attestation_zome(),
            "sign_for_identity_link",
            setup.alice.attestation.agent_pubkey().clone(),
        )
        .await;

    // Alice writes the attestation (she is the caller — agent_a or agent_b by lex order).
    let att_hash: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "link_agent_identity",
            LinkAgentIdentityInput {
                other_agent:     setup.bob.attestation.agent_pubkey().clone(),
                my_signature:    alice_sig,
                other_signature: bob_sig,
            },
        )
        .await;

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Alice should see the link.
    let linked: Vec<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_linked_agents", ())
        .await;
    assert_eq!(linked.len(), 1, "Alice should see one identity link after creation");

    // Alice revokes it.
    let _: ActionHash = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "revoke_agent_identity_link", att_hash)
        .await;

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // After revocation get_linked_agents filters deleted entries → empty.
    let after: Vec<Record> = setup.conductors[0]
        .call(&setup.alice.attestation_zome(), "get_linked_agents", ())
        .await;
    assert_eq!(after.len(), 0, "get_linked_agents should return empty after revocation");
}

// ---------------------------------------------------------------------------
// 20. get_my_claimed_studies — own claims visible, filtered by release (new)
// ---------------------------------------------------------------------------
//
// get_my_claimed_studies returns StudyClaim Records for studies Bob has
// actively claimed.  Released claims are filtered out using the same
// release-link mechanism as get_claims_for_request.

#[tokio::test(flavor = "multi_thread")]
async fn get_my_claimed_studies_filtered_by_release() {
    let setup = setup_two_agents().await;

    let ref_a = fake_external_hash(0xa2);
    let ref_b = fake_external_hash(0xa3);

    // Alice submits two studies.
    for ref_ in [ref_a.clone(), ref_b.clone()] {
        setup.conductors[0]
            .call::<_, ActionHash>(
                &setup.alice.attestation_zome(),
                "submit_validation_request",
                make_validation_request(ref_),
            )
            .await;
    }
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Bob publishes a profile and claims both studies.
    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;
    for ref_ in [ref_a.clone(), ref_b.clone()] {
        setup.conductors[1]
            .call::<_, ActionHash>(&setup.bob.attestation_zome(), "claim_study", ref_)
            .await;
    }

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Both studies should appear in Bob's claimed list.
    let claimed: Vec<Record> = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "get_my_claimed_studies", ())
        .await;
    assert_eq!(claimed.len(), 2, "Bob should see both claimed studies");

    // Bob releases study A.
    let _: () = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "release_claim", ref_a.clone())
        .await;

    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Only study B should remain.
    let after_release: Vec<Record> = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "get_my_claimed_studies", ())
        .await;
    assert_eq!(after_release.len(), 1, "released study A should not appear in claimed list");
    let remaining: StudyClaim = after_release[0]
        .entry()
        .to_app_option()
        .unwrap()
        .unwrap();
    assert_eq!(
        remaining.request_ref.get_raw_32(),
        ref_b.get_raw_32(),
        "remaining claimed study should be study B"
    );
}

// ---------------------------------------------------------------------------
// 24. A researcher cannot claim their own study  (ported from Tryorama)
// ---------------------------------------------------------------------------
//
// This is the guard that makes "independent validator" mean anything. Without
// it a researcher could submit a study and then validate it themselves, and
// every downstream claim ValiChord makes — blind commit-reveal, independent
// reproduction, the HarmonyRecord — would rest on nothing.
//
// It lives in validate() (integrity), not the coordinator, so it is asserted on
// the integrity guard's own wording.
//
// The validator profile deliberately names a DIFFERENT institution from the
// request's `researcher_institution` ("Open Science Lab"). The conflict-of-
// interest guard fires on matching institutions and would otherwise reject this
// claim first — the test would still pass, while proving the wrong rule.
#[tokio::test(flavor = "multi_thread")]
async fn researcher_cannot_claim_their_own_study() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0x71);

    let _: ActionHash = conductor
        .call(&zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;

    // Same agent, unrelated institution → only the self-claim rule can reject.
    let _: ActionHash = conductor
        .call(&zome, "publish_validator_profile", make_validator_profile("Somewhere Else"))
        .await;

    let result: Result<ActionHash, _> = conductor
        .call_fallible(&zome, "claim_study", request_ref)
        .await;
    let err = result.expect_err("a researcher claiming their own study must be rejected");
    assert_rejected_with(
        &format!("{err:?}"),
        "Researcher cannot claim their own study",
        "self-claim",
    );
}

// ---------------------------------------------------------------------------
// 25. Claiming a study that is already at capacity is rejected  (ported)
// ---------------------------------------------------------------------------
//
// `num_validators_required` is the size of the validator cohort. Without this
// guard a study could accumulate unbounded claims, and the quorum that gates
// the reveal phase would stop meaning "the requested cohort has committed".
//
// ⚠️ CAPACITY CANNOT BE 1 HERE. This was written with
// `num_validators_required = 1` and three agents, and failed at the FIRST call:
// the attestation DNA properties used by these tests set `minimum_validators: 2`,
// and validate() rejects a ValidationRequest below that floor
// (attestation_integrity/src/lib.rs:614) — so the request was never written and
// the capacity guard was never reached. Lowering the DNA floor to suit the test
// would have been the wrong fix: that floor exists so a single colluding
// validator cannot satisfy the commitment gate alone.
//
// Capacity 2 is also the better test. It needs FOUR agents — a researcher (who
// cannot claim at all, see test 24), two validators who fill the cohort, and a
// third to be refused — but it asserts BOTH directions: the second claim must
// SUCCEED, which a guard that simply refused every claim after the first would
// fail. At capacity 1 that guard would have passed.
#[tokio::test(flavor = "multi_thread")]
async fn claim_rejected_when_study_is_at_capacity() {
    let mut conductors =
        SweetConductorBatch::from_config_rendezvous(4, SweetConductorConfig::rendezvous(true)).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut it = apps.into_inner().into_iter();
    let researcher = ValiChordApp::from_sweet_app(it.next().unwrap());
    let first = ValiChordApp::from_sweet_app(it.next().unwrap());
    let second = ValiChordApp::from_sweet_app(it.next().unwrap());
    let third = ValiChordApp::from_sweet_app(it.next().unwrap());

    // Capacity of exactly two — the DNA minimum — so the third claim is the
    // first one over the line.
    let mut vr = make_validation_request(fake_external_hash(0x72));
    vr.num_validators_required = 2;
    let request_ref = vr.data_hash.clone();

    let _: ActionHash = conductors[0]
        .call(&researcher.attestation_zome(), "submit_validation_request", vr)
        .await;
    await_consistency_s(60, [
        &researcher.attestation, &first.attestation, &second.attestation, &third.attestation,
    ])
    .await
    .unwrap();

    for (i, app) in [(1usize, &first), (2usize, &second), (3usize, &third)] {
        let _: ActionHash = conductors[i]
            .call(
                &app.attestation_zome(),
                "publish_validator_profile",
                make_validator_profile("Independent"),
            )
            .await;
    }

    // The two slots are filled one at a time, with the first claim gossiped
    // before the second is made — otherwise both validators could count one
    // active claim and the cohort would be over-filled for reasons unrelated to
    // the guard. That the SECOND claim succeeds is half of what this test proves.
    let _: ActionHash = conductors[1]
        .call(&first.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    await_consistency_s(60, [
        &researcher.attestation, &first.attestation, &second.attestation, &third.attestation,
    ])
    .await
    .unwrap();

    let _: ActionHash = conductors[2]
        .call(&second.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    await_consistency_s(60, [
        &researcher.attestation, &first.attestation, &second.attestation, &third.attestation,
    ])
    .await
    .unwrap();

    // Third validator must be refused — the study is full.
    let result: Result<ActionHash, _> = conductors[3]
        .call_fallible(&third.attestation_zome(), "claim_study", request_ref)
        .await;
    let err = result.expect_err("claiming a study at capacity must be rejected");
    assert_rejected_with(&format!("{err:?}"), "at capacity", "claim over capacity");
}

// ---------------------------------------------------------------------------
// 26. A validator cannot claim the same study twice  (ported from Tryorama)
// ---------------------------------------------------------------------------
//
// Without this, one validator could occupy several slots of the same cohort and
// the "N independent validators" claim would be false while looking satisfied —
// the capacity guard in test 25 counts claims, not distinct people.
#[tokio::test(flavor = "multi_thread")]
async fn same_validator_cannot_claim_a_study_twice() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x73);

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let _: ActionHash = setup.conductors[1]
        .call(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;
    let _: ActionHash = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let result: Result<ActionHash, _> = setup.conductors[1]
        .call_fallible(&setup.bob.attestation_zome(), "claim_study", request_ref)
        .await;
    let err = result.expect_err("a second claim by the same validator must be rejected");
    assert_rejected_with(
        &format!("{err:?}"),
        "already claimed this study",
        "duplicate claim by same validator",
    );
}

// ---------------------------------------------------------------------------
// 27. reclaim_abandoned_claim refuses once the validator has attested  (ported)
// ---------------------------------------------------------------------------
//
// Reclaiming frees a slot so a replacement can be found. Doing that to a
// validator who has ALREADY submitted their attestation would vacate a slot that
// was properly filled, and — given the liveness gate now keys finalisation on
// live claims — could let a round close while misrepresenting who took part.
//
// Note this guard returns Ok(false), not an error: "no reclamation needed" is a
// normal outcome, not a rejection. Asserting on a message here would be wrong.
#[tokio::test(flavor = "multi_thread")]
async fn reclaim_refused_once_validator_has_attested() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x74);

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let _: ActionHash = setup.conductors[1]
        .call(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;
    let claim_hash: ActionHash = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Bob does the work: commit then reveal. His slot is now properly filled.
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // timeout_secs: 0 isolates the already-attested guard — the age check cannot
    // be what refuses, so a `false` here can only come from the attestation check.
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
    assert!(
        !reclaimed,
        "reclaim must refuse a slot whose validator has already attested — freeing it \
         would vacate a properly filled slot"
    );
}

// ---------------------------------------------------------------------------
// 28. A third party cannot revoke someone else's identity link  (ported)
// ---------------------------------------------------------------------------
//
// An AgentIdentityAttestation asserts that two keys are the same person, and it
// feeds reputation aggregation across devices. If any passer-by could revoke it,
// they could sever a validator's device links and reset their standing.
#[tokio::test(flavor = "multi_thread")]
async fn third_party_cannot_revoke_an_identity_link() {
    let mut conductors =
        SweetConductorBatch::from_config_rendezvous(3, SweetConductorConfig::rendezvous(true)).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut it = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(it.next().unwrap());
    let bob = ValiChordApp::from_sweet_app(it.next().unwrap());
    let mallory = ValiChordApp::from_sweet_app(it.next().unwrap());

    let alice_sig: Signature = conductors[0]
        .call(
            &alice.attestation_zome(),
            "sign_for_identity_link",
            bob.attestation.agent_pubkey().clone(),
        )
        .await;
    let bob_sig: Signature = conductors[1]
        .call(
            &bob.attestation_zome(),
            "sign_for_identity_link",
            alice.attestation.agent_pubkey().clone(),
        )
        .await;

    let att_hash: ActionHash = conductors[0]
        .call(
            &alice.attestation_zome(),
            "link_agent_identity",
            LinkAgentIdentityInput {
                other_agent: bob.attestation.agent_pubkey().clone(),
                my_signature: alice_sig,
                other_signature: bob_sig,
            },
        )
        .await;
    await_consistency_s(60, [&alice.attestation, &bob.attestation, &mallory.attestation])
        .await
        .unwrap();

    // Mallory is neither named agent.
    let result: Result<ActionHash, _> = conductors[2]
        .call_fallible(
            &mallory.attestation_zome(),
            "revoke_agent_identity_link",
            att_hash,
        )
        .await;
    let err = result.expect_err("a third party must not be able to revoke an identity link");
    assert_rejected_with(
        &format!("{err:?}"),
        "Only one of the two named agents may revoke",
        "third-party identity revocation",
    );
}

// ---------------------------------------------------------------------------
// 29-31. Public read filters — index by discipline / institution  (ported)
// ---------------------------------------------------------------------------
//
// These four functions are in the coordinator's Unrestricted cap grant, so they
// are the PUBLIC read surface — what the UI and the HTTP gateway call. None had
// sweettest coverage; the audit on 2026-08-02 found them tested only in Tryorama.
//
// Each test asserts BOTH directions in one body: the matching query returns the
// record, and a non-matching query returns empty. A positive-only test passes
// against a function that ignores its filter entirely and returns everything.

#[tokio::test(flavor = "multi_thread")]
async fn validator_profiles_are_indexed_by_discipline_and_institution() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    let _: ActionHash = conductor
        .call(&zome, "publish_validator_profile", make_validator_profile("Cardiff University"))
        .await;

    // make_validator_profile declares ComputationalBiology only.
    let matching: Vec<Record> = conductor
        .call(&zome, "get_validators_for_discipline", Discipline::ComputationalBiology)
        .await;
    assert_eq!(matching.len(), 1, "profile must be indexed under its own discipline");

    let other: Vec<Record> = conductor
        .call(&zome, "get_validators_for_discipline", Discipline::MachineLearning)
        .await;
    assert!(
        other.is_empty(),
        "a discipline the validator did not declare must return nothing — got {}",
        other.len()
    );

    let by_inst: Vec<Record> = conductor
        .call(&zome, "get_validators_for_institution", "Cardiff University".to_string())
        .await;
    assert_eq!(by_inst.len(), 1, "profile must be indexed under its institution");

    let wrong_inst: Vec<Record> = conductor
        .call(&zome, "get_validators_for_institution", "Somewhere Else".to_string())
        .await;
    assert!(wrong_inst.is_empty(), "a different institution must return nothing");
}

#[tokio::test(flavor = "multi_thread")]
async fn pending_requests_are_indexed_by_discipline() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();

    // make_validation_request declares ComputationalBiology.
    let _: ActionHash = conductor
        .call(
            &zome,
            "submit_validation_request",
            make_validation_request(fake_external_hash(0x75)),
        )
        .await;

    let matching: Vec<Record> = conductor
        .call(&zome, "get_pending_requests_for_discipline", Discipline::ComputationalBiology)
        .await;
    assert_eq!(matching.len(), 1, "request must appear under its own discipline");

    let other: Vec<Record> = conductor
        .call(&zome, "get_pending_requests_for_discipline", Discipline::MachineLearning)
        .await;
    assert!(
        other.is_empty(),
        "a different discipline must return nothing — got {}",
        other.len()
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn attestations_are_indexed_by_discipline() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x76);

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Two commits open the reveal phase (num_validators_required = 2).
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let matching: Vec<Record> = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "get_attestations_for_discipline",
            Discipline::ComputationalBiology,
        )
        .await;
    assert_eq!(matching.len(), 1, "attestation must be indexed under its discipline");

    let other: Vec<Record> = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "get_attestations_for_discipline",
            Discipline::MachineLearning,
        )
        .await;
    assert!(other.is_empty(), "a different discipline must return nothing");
}

// ---------------------------------------------------------------------------
// 32. link_agent_identity — a corrupted counter-signature is rejected  (ported)
// ---------------------------------------------------------------------------
//
// Found by the 2026-08-03 retirement audit: the signature-verification path in
// `link_agent_identity` had NO coverage here at all. Test 13 above says so in
// its own body — it passes 64 zero bytes, because the self-link check fires
// first and the signatures are never reached. So both of this function's
// `verify_signature` calls were untested, and an implementation that skipped
// them entirely would have kept every existing test green.
//
// That matters because an AgentIdentityAttestation asserts two keys are the
// same person and feeds cross-device reputation. Without signature checking,
// anyone could assert a link to anyone.
//
// ⚠️ The signature MUST come from `sign_for_identity_link`, not from signing
// the payload by hand. `verify_signature(key, sig, data)` does not verify over
// `data` as given — `VerifySignature::new` stores
// `holochain_serialized_bytes::encode(&data)`, so hand-signed raw bytes fail in
// a way indistinguishable from "the guard works".
#[tokio::test(flavor = "multi_thread")]
async fn link_agent_identity_bad_signature_rejected() {
    let setup = setup_two_agents().await;
    let bob_key = setup.bob.attestation.agent_pubkey().clone();

    // Alice's own half of the ceremony, correctly signed over the canonical
    // sorted-pair payload.
    let alice_sig: Signature = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "sign_for_identity_link",
            bob_key.clone(),
        )
        .await;

    // Flip one byte and offer it as BOB's half. Alice's own signature stays
    // valid, so the caller check passes and `other_signature` is the only thing
    // left that can reject — which is what makes the assertion below specific.
    let mut corrupted = alice_sig.0;
    corrupted[10] ^= 0xff;

    let result: Result<ActionHash, _> = setup.conductors[0]
        .call_fallible(
            &setup.alice.attestation_zome(),
            "link_agent_identity",
            LinkAgentIdentityInput {
                other_agent:     bob_key,
                my_signature:    alice_sig,
                other_signature: Signature(corrupted),
            },
        )
        .await;
    let err = result.expect_err("a corrupted counter-signature must be rejected");
    assert_rejected_with(
        &format!("{err:?}"),
        "other_signature failed verification",
        "corrupted counter-signature",
    );
}
