//! Integration tests for DNA 4 — Governance.
//!
//! Key design notes:
//! - HarmonyRecord, ReproducibilityBadge, ValidatorReputation are open to any participant.
//! - GovernanceDecision is gated by `system_coordinator_key` in validate().
//!   With `system_coordinator_key: ""` (dev bypass), any agent can write.
//! - `round_timeout_secs: 0` in test DNA properties means force_finalize_round
//!   passes the age check immediately (elapsed_secs >= 0 always).
//! - `min_attestations_for_finalization: 0` → treated as 1 in force_finalize_round.
//!
//! Attestation flow required before any HarmonyRecord can be created:
//!   1. submit_validation_request (attestation DNA)
//!   2. notify_commitment_sealed × N  (attestation DNA, one per validator)
//!   3. DHT sync
//!   4. submit_attestation × N  (attestation DNA, one per validator)
//!   5. DHT sync
//!   6. check_and_create_harmony_record (governance DNA)
//!
//! Test inventory:
//!   1.  check_and_create_harmony_record returns None when no attestations
//!   2.  Full 2-agent round — HarmonyRecord created on public DHT
//!   3.  check_and_create_harmony_record idempotent after record exists
//!   4.  Any participant can trigger finalisation (Bob, not the request submitter)
//!   5.  Premature finalisation (1 of 2 attestations) returns None
//!   6.  force_finalize_round — partial quorum + round_timeout_secs=0 (new)
//!   7.  GovernanceDecision key-gated — non-matching key rejected (new)
//!   8.  update_validator_reputation — dev bypass allows any agent
//!   9.  get_harmony_records_by_discipline — empty + after round (new)
//!  10.  get_badges_for_study — 2 validators, count < 3, no badge (new)
//!  11.  get_badges_by_type — 3 validators, BronzeReproducible issued (new)
//!  12.  tier promotion — Provisional → Standard after 3 Reproduced rounds
//!  13.  tier stays Provisional before 3 rounds
//!  14.  AI validator tier does not advance through completed rounds

use valichord_sweettest::*;
use governance_coordinator::ReputationUpdateInput;
use governance_integrity::{BadgeType, ValidatorReputation};
use valichord_shared_types::{AttestationOutcome, CertificationTier, Discipline, ValidatorType};

// ---------------------------------------------------------------------------
// Internal helpers — shared attestation round setup
// ---------------------------------------------------------------------------

/// Run the commit phase for a single validator: notify_commitment_sealed.
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

/// Run the reveal phase for a single validator: submit_attestation.
async fn reveal(conductor: &SweetConductor, app: &ValiChordApp, request_ref: ExternalHash) {
    let _: ActionHash = conductor
        .call(
            &app.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref),
                nonce: vec![], // empty = dev bypass
            },
        )
        .await;
}

// ---------------------------------------------------------------------------
// 1. check_and_create_harmony_record returns None when no attestations
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn check_and_create_harmony_record_no_attestations_returns_none() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();

    let request_ref = fake_external_hash(0x01);

    // No ValidationRequest or attestations — should return None immediately.
    let result: Option<ActionHash> = conductor
        .call(&gov_zome, "check_and_create_harmony_record", request_ref.clone())
        .await;
    assert!(result.is_none(), "should return None when no attestations exist");

    // No record on the DHT either.
    let record: Option<Record> = conductor
        .call(&gov_zome, "get_harmony_record", request_ref)
        .await;
    assert!(record.is_none());
}

// ---------------------------------------------------------------------------
// 2. Full 2-agent round — HarmonyRecord created
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn full_round_creates_harmony_record() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x10);

    // 1. Submit ValidationRequest on attestation DNA (Alice submits).
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;

    // 2. Sync attestation DHT so Bob sees the request.
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // 3. Both validators commit.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // 4. Both validators reveal.
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // 5. Trigger HarmonyRecord creation via governance DNA.
    let harmony_hash: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(harmony_hash.is_some(), "full round should produce a HarmonyRecord");

    // 6. Record must be retrievable.
    let record: Option<Record> = setup.conductors[0]
        .call(&setup.alice.governance_zome(), "get_harmony_record", request_ref)
        .await;
    assert!(record.is_some(), "HarmonyRecord should be visible on the governance DHT");
}

// ---------------------------------------------------------------------------
// 3. check_and_create_harmony_record is idempotent
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn check_and_create_harmony_record_idempotent() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x11);

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

    // First call — creates record.
    let first: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(first.is_some(), "first call should create the HarmonyRecord");

    // Second call — must short-circuit and return the existing hash (record already exists).
    // The coordinator returns Ok(Some(existing_hash)) on the idempotency path, not Ok(None).
    let second: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref,
        )
        .await;
    assert!(second.is_some(), "second call should return the existing HarmonyRecord hash — idempotent, no new record created");
}

// ---------------------------------------------------------------------------
// 4. Any participant can finalise (Bob triggers, not the request submitter)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn any_participant_can_finalize() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x12);

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

    // Bob triggers finalisation — he did not submit the ValidationRequest.
    let harmony_hash: Option<ActionHash> = setup.conductors[1]
        .call(
            &setup.bob.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(
        harmony_hash.is_some(),
        "any participant should be able to trigger finalisation"
    );

    // Record must be visible to Alice too after governance DHT sync.
    await_consistency_20_s([&setup.alice.governance, &setup.bob.governance])
        .await
        .unwrap();
    let record: Option<Record> = setup.conductors[0]
        .call(&setup.alice.governance_zome(), "get_harmony_record", request_ref)
        .await;
    assert!(record.is_some(), "HarmonyRecord should be visible to all participants");
}

// ---------------------------------------------------------------------------
// 5. Premature finalisation (1 of 2 required attestations) returns None
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn premature_finalization_returns_none() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x13);

    // num_validators_required: 2 (from make_validation_request default).
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

    // Only Alice commits and reveals — Bob is absent.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Only 1 attestation, but 2 required — must return None.
    let result: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(result.is_none(), "premature finalisation should return None (1 of 2 attestations)");

    // No record on DHT.
    let record: Option<Record> = setup.conductors[0]
        .call(&setup.alice.governance_zome(), "get_harmony_record", request_ref)
        .await;
    assert!(record.is_none());
}

// ---------------------------------------------------------------------------
// 6. force_finalize_round — partial quorum, round_timeout_secs=0 (new)
// ---------------------------------------------------------------------------
//
// With round_timeout_secs=0 the age check (elapsed_secs >= round_timeout_secs)
// passes immediately, even for a request created moments ago.
// With min_attestations_for_finalization=0 → treated as 1 in the code.
// With only 1 of 2 validators attesting, check_and_create_harmony_record
// would return None; force_finalize_round should return Some.

#[tokio::test(flavor = "multi_thread")]
async fn force_finalize_round_with_partial_quorum() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x20);

    // Submit ValidationRequest so force_finalize_round can verify the round age.
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

    // Only Alice commits and reveals (Bob is the absent validator).
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Verify that normal finalisation is blocked.
    let normal: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(
        normal.is_none(),
        "check_and_create_harmony_record should return None (1 of 2 required)"
    );

    // force_finalize_round must succeed: 1 attestation >= 1 required, timeout=0.
    let forced: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "force_finalize_round",
            request_ref.clone(),
        )
        .await;
    assert!(
        forced.is_some(),
        "force_finalize_round should create a HarmonyRecord when at least 1 attestation exists \
         and round_timeout_secs=0"
    );

    // The resulting HarmonyRecord must be retrievable.
    let record: Option<Record> = setup.conductors[0]
        .call(&setup.alice.governance_zome(), "get_harmony_record", request_ref)
        .await;
    assert!(record.is_some(), "HarmonyRecord should be visible after force_finalize_round");
}

// ---------------------------------------------------------------------------
// 7. GovernanceDecision key-gated — non-matching key rejected (new)
// ---------------------------------------------------------------------------
//
// setup_single_locked_governance() installs governance DNA with
// system_coordinator_key: "not-a-real-key" — any agent's real key will
// not match, so GovernanceDecision writes must be rejected by validate().

#[tokio::test(flavor = "multi_thread")]
async fn governance_decision_non_matching_key_rejected() {
    let (conductor, app) = setup_single_locked_governance().await;
    let gov_zome = app.governance_zome();

    let result: Result<(), _> = conductor
        .call_fallible(
            &gov_zome,
            "create_governance_decision",
            make_governance_decision(),
        )
        .await;
    assert!(
        result.is_err(),
        "GovernanceDecision write must be rejected when agent key does not match \
         system_coordinator_key"
    );
}

// ---------------------------------------------------------------------------
// 8. update_validator_reputation — dev bypass allows any agent
// ---------------------------------------------------------------------------
//
// In test DNA (system_coordinator_key: ""), validate() bypasses the author
// check, so any agent can call update_validator_reputation.

#[tokio::test(flavor = "multi_thread")]
async fn update_validator_reputation_dev_bypass() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();

    // Retrieve the agent key directly from the SweetCell.
    let cell_agent = app.governance.agent_pubkey().clone();

    let rep_hash: ActionHash = conductor
        .call(
            &gov_zome,
            "update_validator_reputation",
            ReputationUpdateInput {
                validator:          cell_agent.clone(),
                discipline:         valichord_shared_types::Discipline::ComputationalBiology,
                outcome:            valichord_shared_types::AttestationOutcome::Reproduced,
                time_invested_secs: 3_600,
                validator_type:     ValidatorType::Human,
                initial_tier:       None,
            },
        )
        .await;
    // rep_hash is valid (non-default) — the write succeeded.
    assert_ne!(rep_hash.as_ref().len(), 0);

    let record: Option<Record> = conductor
        .call(&gov_zome, "get_validator_reputation", cell_agent)
        .await;
    assert!(record.is_some(), "validator reputation should be retrievable after update");
}

// ---------------------------------------------------------------------------
// 9. get_harmony_records_by_discipline — empty + after round (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_harmony_records_by_discipline_empty_initially() {
    let (conductor, app) = setup_single().await;

    let records: Vec<Record> = conductor
        .call(
            &app.governance_zome(),
            "get_harmony_records_by_discipline",
            valichord_shared_types::Discipline::ComputationalBiology,
        )
        .await;
    assert_eq!(records.len(), 0, "should return empty when no HarmonyRecords exist");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_harmony_records_by_discipline_returns_record_after_round() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x30);

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

    // Interleaved sync between reveals: ensures only Bob's auto-call (the last reveal) sees
    // both attestations and creates the HarmonyRecord, preventing the TOCTOU race where
    // Alice's explicit call below would otherwise miss Bob's governance write and create a
    // second HarmonyRecord.
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_20_s([&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    // Sync governance DHT so Alice sees the HarmonyRecord created by Bob's auto-call.
    await_consistency_20_s([&setup.alice.governance, &setup.bob.governance])
        .await
        .unwrap();

    // Explicit call — idempotent: Bob's auto-call already created the record.
    let _: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref,
        )
        .await;

    // Query by discipline — must include the newly created record.
    let records: Vec<Record> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "get_harmony_records_by_discipline",
            valichord_shared_types::Discipline::ComputationalBiology,
        )
        .await;
    assert_eq!(records.len(), 1, "get_harmony_records_by_discipline should return the created record");
}

// ---------------------------------------------------------------------------
// 10. get_badges_for_study — 2 validators, count < 3, no badge issued (new)
// ---------------------------------------------------------------------------
//
// evaluate_badge thresholds:
//   ExactMatch + count >= 7 → GoldReproducible
//   ExactMatch + count >= 5 → SilverReproducible
//   ExactMatch + count >= 3 → BronzeReproducible
//   count < 3               → None
//
// With 2 validators both Reproduced → ExactMatch + count=2 → no badge.

#[tokio::test(flavor = "multi_thread")]
async fn get_badges_for_study_none_with_two_validators() {
    let mut setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x40);

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

    let _: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;

    // 2 validators → count < 3 → no badge.
    let badges: Vec<Record> = setup.conductors[0]
        .call(&setup.alice.governance_zome(), "get_badges_for_study", request_ref)
        .await;
    assert_eq!(
        badges.len(),
        0,
        "no badge should be issued when validator count is below the Bronze threshold (3)"
    );
}

// ---------------------------------------------------------------------------
// 11. get_badges_by_type — 3 validators, BronzeReproducible issued (new)
// ---------------------------------------------------------------------------
//
// With 3 validators all returning Reproduced:
//   derive_agreement_level: rate = 3/3 = 1.0 → ExactMatch
//   evaluate_badge: ExactMatch + count=3 → BronzeReproducible

#[tokio::test(flavor = "multi_thread")]
async fn get_badges_by_type_bronze_with_three_validators() {
    // Inline 3-conductor setup (no shared helper exists for 3 agents).
    let mut conductors = SweetConductorBatch::from_standard_config_rendezvous(3).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut app_iter = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(app_iter.next().unwrap());
    let bob   = ValiChordApp::from_sweet_app(app_iter.next().unwrap());
    let carol = ValiChordApp::from_sweet_app(app_iter.next().unwrap());

    // 3 validators required so the quorum check passes.
    let mut vr = make_validation_request(fake_external_hash(0x50));
    vr.num_validators_required = 3;
    let request_ref = vr.data_hash.clone();

    let _: ActionHash = conductors[0]
        .call(&alice.attestation_zome(), "submit_validation_request", vr)
        .await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();

    // All three commit — interleaved sync so each sees prior CommitmentAnchors.
    commit(&conductors[0], &alice, request_ref.clone()).await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    commit(&conductors[1], &bob, request_ref.clone()).await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    commit(&conductors[2], &carol, request_ref.clone()).await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();

    // All three reveal with interleaved sync so each sees prior attestations.
    // No governance sync here — Alice's explicit call below must create the
    // HarmonyRecord + badge itself.  Carol's auto-call (via submit_attestation →
    // check_and_create_harmony_record) successfully creates the HarmonyRecord but
    // silently skips badge creation because the 3-deep cross-DNA call chain
    // (attestation→governance→attestation) returns None for the VR lookup.  If we
    // synced governance before Alice's call, Alice would hit idempotency and the
    // badge would never be created.  Instead we let Alice create both.
    reveal(&conductors[0], &alice, request_ref.clone()).await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    reveal(&conductors[1], &bob, request_ref.clone()).await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    reveal(&conductors[2], &carol, request_ref.clone()).await;
    await_consistency_20_s([&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();

    // ExactMatch + count=3 → BronzeReproducible badge.
    // Alice calls without a prior governance sync so she does not hit idempotency
    // from Carol's auto-call; her call creates both HarmonyRecord and badge.
    let harmony: Option<ActionHash> = conductors[0]
        .call(
            &alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(harmony.is_some(), "full 3-agent round should produce a HarmonyRecord");

    // Sync governance DHT so Alice's badge propagates to all nodes before querying.
    await_consistency_20_s([&alice.governance, &bob.governance, &carol.governance])
        .await
        .unwrap();

    // Badge for the study.
    let badges: Vec<Record> = conductors[0]
        .call(&alice.governance_zome(), "get_badges_for_study", request_ref)
        .await;
    assert!(!badges.is_empty(), "BronzeReproducible badge should be issued for ExactMatch + count=3");

    // Badge accessible via get_badges_by_type.
    let by_type: Vec<Record> = conductors[0]
        .call(
            &alice.governance_zome(),
            "get_badges_by_type",
            BadgeType::BronzeReproducible,
        )
        .await;
    assert!(!by_type.is_empty(), "get_badges_by_type(BronzeReproducible) should return at least one badge");
}

// ---------------------------------------------------------------------------
// 12. Tier promotion — Provisional → Standard after 3 Reproduced rounds
// ---------------------------------------------------------------------------
//
// update_validator_reputation accumulates totals across calls (each call reads
// the previous reputation and increments). After 3 Reproduced outcomes the
// cert_tier() function must return Standard.

#[tokio::test(flavor = "multi_thread")]
async fn validator_tier_promotes_to_standard_after_three_rounds() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();
    let validator = app.governance.agent_pubkey().clone();

    for _ in 0..3 {
        let _: ActionHash = conductor
            .call(
                &gov_zome,
                "update_validator_reputation",
                ReputationUpdateInput {
                    validator:          validator.clone(),
                    discipline:         Discipline::ComputationalBiology,
                    outcome:            AttestationOutcome::Reproduced,
                    time_invested_secs: 3_600,
                    validator_type:     ValidatorType::Human,
                    initial_tier:       None,
                },
            )
            .await;
    }

    let record: Option<Record> = conductor
        .call(&gov_zome, "get_validator_reputation", validator)
        .await;
    let rep: ValidatorReputation = record
        .expect("reputation should exist after 3 updates")
        .entry()
        .to_app_option()
        .unwrap()
        .unwrap();
    assert_eq!(rep.total_validations, 3);
    assert_eq!(
        rep.tier,
        CertificationTier::Standard,
        "3 completed rounds should promote from Provisional to Standard"
    );
}

// ---------------------------------------------------------------------------
// 13. Tier stays Provisional before 3 rounds
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn validator_tier_stays_provisional_before_three_rounds() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();
    let validator = app.governance.agent_pubkey().clone();

    for _ in 0..2 {
        let _: ActionHash = conductor
            .call(
                &gov_zome,
                "update_validator_reputation",
                ReputationUpdateInput {
                    validator:          validator.clone(),
                    discipline:         Discipline::ComputationalBiology,
                    outcome:            AttestationOutcome::Reproduced,
                    time_invested_secs: 3_600,
                    validator_type:     ValidatorType::Human,
                    initial_tier:       None,
                },
            )
            .await;
    }

    let record: Option<Record> = conductor
        .call(&gov_zome, "get_validator_reputation", validator)
        .await;
    let rep: ValidatorReputation = record
        .expect("reputation should exist after 2 updates")
        .entry()
        .to_app_option()
        .unwrap()
        .unwrap();
    assert_eq!(rep.total_validations, 2);
    assert_eq!(
        rep.tier,
        CertificationTier::Provisional,
        "2 rounds is not enough to leave Provisional — threshold is 3"
    );
}

// ---------------------------------------------------------------------------
// 14. AI validator tier does not advance through completed rounds
// ---------------------------------------------------------------------------
//
// AI validators use the issuer-granted tier only.  The first call to
// update_validator_reputation creates an initial reputation entry with the
// supplied initial_tier; all subsequent calls return the existing hash without
// creating a new entry or changing the tier.

#[tokio::test(flavor = "multi_thread")]
async fn ai_validator_tier_does_not_advance_through_rounds() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();
    let validator = app.governance.agent_pubkey().clone();

    // First call: creates initial reputation with issuer-granted Standard tier.
    let _: ActionHash = conductor
        .call(
            &gov_zome,
            "update_validator_reputation",
            ReputationUpdateInput {
                validator:          validator.clone(),
                discipline:         Discipline::ComputationalBiology,
                outcome:            AttestationOutcome::Reproduced,
                time_invested_secs: 3_600,
                validator_type:     ValidatorType::AI,
                initial_tier:       Some(CertificationTier::Standard),
            },
        )
        .await;

    // Subsequent calls: no tier advancement despite many completed rounds.
    for _ in 0..10 {
        let _: ActionHash = conductor
            .call(
                &gov_zome,
                "update_validator_reputation",
                ReputationUpdateInput {
                    validator:          validator.clone(),
                    discipline:         Discipline::ComputationalBiology,
                    outcome:            AttestationOutcome::Reproduced,
                    time_invested_secs: 3_600,
                    validator_type:     ValidatorType::AI,
                    initial_tier:       None,
                },
            )
            .await;
    }

    let record: Option<Record> = conductor
        .call(&gov_zome, "get_validator_reputation", validator)
        .await;
    let rep: ValidatorReputation = record
        .expect("reputation should exist after AI validator initialization")
        .entry()
        .to_app_option()
        .unwrap()
        .unwrap();
    assert_eq!(
        rep.tier,
        CertificationTier::Standard,
        "AI validator tier must remain issuer-granted Standard regardless of completed rounds"
    );
    assert_eq!(
        rep.total_validations, 0,
        "AI validator total_validations must stay at 0 — rounds do not count toward progression"
    );
}
