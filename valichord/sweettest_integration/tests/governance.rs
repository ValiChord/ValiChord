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
//!  15.  GoldReproducible badge — 7 validators, all Reproduced (ExactMatch)
//!  16.  SilverReproducible badge — 5 validators, all Reproduced (ExactMatch)
//!  17.  get_pending_request_refs — empty initially, then covers Discipline::Other (new)

use valichord_sweettest::*;
use governance_coordinator::ReputationUpdateInput;
use governance_integrity::ValidatorReputation;
use valichord_shared_types::{AttestationOutcome, BadgeType, CertificationTier, Discipline, ValidatorType};

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
    let setup = setup_two_agents().await;
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
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // 3. Both validators commit.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // 4. Both validators reveal.
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x11);

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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x12);

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
    await_consistency_s(20, [&setup.alice.governance, &setup.bob.governance])
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x13);

    // num_validators_required: 2 (from make_validation_request default).
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

    // Only Alice commits and reveals — Bob is absent.
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x20);

    // Submit ValidationRequest so force_finalize_round can verify the round age.
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

    // Only Alice commits and reveals (Bob is the absent validator).
    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x30);

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

    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Interleaved sync between reveals: ensures only Bob's auto-call (the last reveal) sees
    // both attestations and creates the HarmonyRecord, preventing the TOCTOU race where
    // Alice's explicit call below would otherwise miss Bob's governance write and create a
    // second HarmonyRecord.
    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    // Sync governance DHT so Alice sees the HarmonyRecord created by Bob's auto-call.
    await_consistency_s(20, [&setup.alice.governance, &setup.bob.governance])
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
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x40);

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
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();

    // All three commit — interleaved sync so each sees prior CommitmentAnchors.
    commit(&conductors[0], &alice, request_ref.clone()).await;
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    commit(&conductors[1], &bob, request_ref.clone()).await;
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    commit(&conductors[2], &carol, request_ref.clone()).await;
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();

    // All three reveal with interleaved attestation sync so each sees prior attestations.
    reveal(&conductors[0], &alice, request_ref.clone()).await;
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    reveal(&conductors[1], &bob, request_ref.clone()).await;
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();
    reveal(&conductors[2], &carol, request_ref.clone()).await;
    await_consistency_s(20, [&alice.attestation, &bob.attestation, &carol.attestation])
        .await
        .unwrap();

    // Sync governance cells before the explicit call so Carol's auto-call HarmonyRecord
    // (link + entry) has fully propagated.  This deterministically exercises the
    // idempotency + issue_badge_if_missing path.  Without this sync, on a fast runner
    // the RequestToHarmonyRecord *link* arrives at Alice's shard before the
    // HarmonyRecord *entry* does; issue_badge_if_missing then returns Ok(()) silently
    // when get(record_hash) returns None, leaving the badge absent.
    await_consistency_s(20, [&alice.governance, &bob.governance, &carol.governance])
        .await
        .unwrap();

    // ExactMatch + count=3 → BronzeReproducible badge via idempotency+retry path.
    let harmony: Option<ActionHash> = conductors[0]
        .call(
            &alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(harmony.is_some(), "full 3-agent round should produce a HarmonyRecord");

    // Sync governance DHT so the badge propagates before querying.
    await_consistency_s(20, [&alice.governance, &bob.governance, &carol.governance])
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

// ---------------------------------------------------------------------------
// 15. GoldReproducible badge — 7 validators, all Reproduced (ExactMatch)
// ---------------------------------------------------------------------------
//
// This is the highest badge tier. 7 independent conductors each commit and
// reveal a Reproduced attestation. ExactMatch (7/7 = 100%) + count=7 satisfies
// the GoldReproducible threshold.
//
// Sweettest conductors are in-process with no Node.js or WebSocket overhead,
// making this feasible within normal CI RAM budgets where a 7-conductor
// Tryorama run would OOM.

#[tokio::test(flavor = "multi_thread")]
async fn gold_badge_issued_with_seven_validators() {
    const N: usize = 7;

    let mut conductors = SweetConductorBatch::from_standard_config_rendezvous(N).await;
    let dnas = dnas_with_roles().await;
    let apps: Vec<ValiChordApp> = conductors
        .setup_app("valichord", &dnas)
        .await
        .unwrap()
        .into_inner()
        .into_iter()
        .map(ValiChordApp::from_sweet_app)
        .collect();

    // 7 validators required so the quorum check and badge threshold both trigger.
    let mut vr = make_validation_request(fake_external_hash(0x60));
    vr.num_validators_required = N as u8;
    let request_ref = vr.data_hash.clone();

    let _: ActionHash = conductors[0]
        .call(&apps[0].attestation_zome(), "submit_validation_request", vr)
        .await;

    let att_cells: Vec<&SweetCell> = apps.iter().map(|a| &a.attestation).collect();
    // 60-second timeout: N=7 conductors gossip slowly on a loaded CI runner.
    await_consistency(att_cells.iter().copied()).await.unwrap();

    // Commit phase — sequential with interleaved DHT sync so each conductor
    // sees all prior CommitmentAnchors before the phase-open check fires.
    for i in 0..N {
        commit(&conductors[i], &apps[i], request_ref.clone()).await;
        await_consistency(att_cells.iter().copied()).await.unwrap();
    }

    // Reveal phase — sequential with interleaved sync. No governance sync here:
    // the last reveal's auto-call (submit_attestation → check_and_create_harmony_record)
    // creates the HarmonyRecord but skips badge creation via the 3-deep cross-DNA
    // call chain. apps[0]'s explicit call below creates both.
    for i in 0..N {
        reveal(&conductors[i], &apps[i], request_ref.clone()).await;
        await_consistency(att_cells.iter().copied()).await.unwrap();
    }

    // Sync governance first so check_and_create_harmony_record takes the
    // idempotency path and issue_badge_if_missing reliably issues the badge
    // (same pattern as the silver badge test).
    let gov_cells: Vec<&SweetCell> = apps.iter().map(|a| &a.governance).collect();
    await_consistency(gov_cells.iter().copied()).await.unwrap();

    let harmony: Option<ActionHash> = conductors[0]
        .call(
            &apps[0].governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(harmony.is_some(), "7-agent round must produce a HarmonyRecord");

    // Sync again so the badge propagates before querying.
    await_consistency(gov_cells.iter().copied()).await.unwrap();

    // GoldReproducible: ExactMatch (7/7) + count=7 ≥ 7.
    let badges: Vec<Record> = conductors[0]
        .call(&apps[0].governance_zome(), "get_badges_for_study", request_ref.clone())
        .await;
    assert!(
        !badges.is_empty(),
        "GoldReproducible badge should be issued for ExactMatch + count=7"
    );

    let by_type: Vec<Record> = conductors[0]
        .call(
            &apps[0].governance_zome(),
            "get_badges_by_type",
            BadgeType::GoldReproducible,
        )
        .await;
    assert!(
        !by_type.is_empty(),
        "get_badges_by_type(GoldReproducible) should return the issued badge"
    );
}

// ---------------------------------------------------------------------------
// 16. SilverReproducible badge — 5 validators, all Reproduced (ExactMatch)
// ---------------------------------------------------------------------------
//
// ExactMatch (5/5 = 100%) + count=5 satisfies SilverReproducible but not Gold.

#[tokio::test(flavor = "multi_thread")]
async fn silver_badge_issued_with_five_validators() {
    const N: usize = 5;

    let mut conductors = SweetConductorBatch::from_standard_config_rendezvous(N).await;
    let dnas = dnas_with_roles().await;
    let apps: Vec<ValiChordApp> = conductors
        .setup_app("valichord", &dnas)
        .await
        .unwrap()
        .into_inner()
        .into_iter()
        .map(ValiChordApp::from_sweet_app)
        .collect();

    let mut vr = make_validation_request(fake_external_hash(0x61));
    vr.num_validators_required = N as u8;
    let request_ref = vr.data_hash.clone();

    let _: ActionHash = conductors[0]
        .call(&apps[0].attestation_zome(), "submit_validation_request", vr)
        .await;

    let att_cells: Vec<&SweetCell> = apps.iter().map(|a| &a.attestation).collect();
    // 60-second timeout: N=5 conductors on a loaded CI runner (runs after gold).
    await_consistency(att_cells.iter().copied()).await.unwrap();

    for i in 0..N {
        commit(&conductors[i], &apps[i], request_ref.clone()).await;
        await_consistency(att_cells.iter().copied()).await.unwrap();
    }

    for i in 0..N {
        reveal(&conductors[i], &apps[i], request_ref.clone()).await;
        await_consistency(att_cells.iter().copied()).await.unwrap();
    }

    // Sync governance cells before the explicit call so the auto-call's HarmonyRecord
    // link has propagated — this guarantees we exercise the idempotency + badge-retry
    // path (issue_badge_if_missing) rather than depending on a gossip-timing race.
    let gov_cells: Vec<&SweetCell> = apps.iter().map(|a| &a.governance).collect();
    await_consistency(gov_cells.iter().copied()).await.unwrap();

    let harmony: Option<ActionHash> = conductors[0]
        .call(
            &apps[0].governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(harmony.is_some(), "5-agent round must produce a HarmonyRecord");

    // SilverReproducible: ExactMatch (5/5) + count=5 ≥ 5, count=5 < 7 → not Gold.
    await_consistency(gov_cells.iter().copied()).await.unwrap();

    let badges: Vec<Record> = conductors[0]
        .call(&apps[0].governance_zome(), "get_badges_for_study", request_ref.clone())
        .await;
    assert!(
        !badges.is_empty(),
        "SilverReproducible badge should be issued for ExactMatch + count=5"
    );

    let by_type: Vec<Record> = conductors[0]
        .call(
            &apps[0].governance_zome(),
            "get_badges_by_type",
            BadgeType::SilverReproducible,
        )
        .await;
    assert!(
        !by_type.is_empty(),
        "get_badges_by_type(SilverReproducible) should return the issued badge"
    );
}

// ---------------------------------------------------------------------------
// 17. get_pending_request_refs — empty initially, Discipline::Other covered (new)
// ---------------------------------------------------------------------------
//
// submit_validation_request writes a PendingStudiesPath link tagged with the
// data_hash raw bytes regardless of discipline.  get_pending_request_refs
// reads that global index and returns all pending ExternalHashes.
//
// Before this change, sweep_timed_out_rounds iterated a static list of named
// disciplines and never processed Discipline::Other studies.  The fix routes
// the sweep through get_pending_request_refs, which covers all disciplines.
//
// This test verifies:
//   a. Empty before any submissions.
//   b. Both a ComputationalBiology and a Discipline::Other("custom") study
//      appear after submission — no discipline is excluded from the index.
//   c. force_finalize_round succeeds for the Discipline::Other study, proving
//      the governance sweep path covers it end-to-end.

#[tokio::test(flavor = "multi_thread")]
async fn get_pending_request_refs_includes_other_discipline_studies() {
    let setup = setup_two_agents().await;

    // a. Empty before any submissions.
    let initial: Vec<ExternalHash> = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "get_pending_request_refs",
            (),
        )
        .await;
    assert!(
        initial.is_empty(),
        "get_pending_request_refs should return empty before any submissions"
    );

    // Submit a named-discipline (ComputationalBiology) request.
    let ref_bio = fake_external_hash(0x70);
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(ref_bio.clone()),
        )
        .await;

    // Submit a Discipline::Other("custom") request — the previously-unindexed gap.
    let ref_other = fake_external_hash(0x71);
    let mut vr_other = make_validation_request(ref_other.clone());
    vr_other.discipline = Discipline::Other("custom".into());
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            vr_other,
        )
        .await;

    // Sync attestation DHT so the Network-mode query in get_pending_request_refs
    // sees both PendingStudiesPath links written by Alice.
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // b. Both hashes appear in the index, regardless of discipline.
    let refs: Vec<ExternalHash> = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "get_pending_request_refs",
            (),
        )
        .await;
    assert_eq!(
        refs.len(),
        2,
        "get_pending_request_refs should return both submitted studies"
    );
    let raw_refs: Vec<Vec<u8>> = refs.iter().map(|h| h.get_raw_32().to_vec()).collect();
    assert!(
        raw_refs.contains(&ref_bio.get_raw_32().to_vec()),
        "ComputationalBiology study should appear in pending refs"
    );
    assert!(
        raw_refs.contains(&ref_other.get_raw_32().to_vec()),
        "Discipline::Other study should appear in pending refs"
    );

    // c. force_finalize_round succeeds for the Discipline::Other study.
    //    Alice commits and reveals; round_timeout_secs=0 so the age check passes,
    //    and min_attestations_for_finalization=0 → treated as 1 → 1 attestation suffices.
    commit(&setup.conductors[0], &setup.alice, ref_other.clone()).await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();
    // Must use the same discipline as the request (Other("custom")); the generic
    // `reveal` helper hardcodes ComputationalBiology which now fails validation.
    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: ValidationAttestation {
                    discipline: Discipline::Other("custom".into()),
                    ..make_validation_attestation(ref_other.clone())
                },
                nonce: vec![],
            },
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let forced: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "force_finalize_round",
            ref_other.clone(),
        )
        .await;
    assert!(
        forced.is_some(),
        "force_finalize_round should create a HarmonyRecord for a Discipline::Other study"
    );
}
