//! Security regression tests — ValiChord self-audit (March 2026).
//!
//! Covers the 11 protocol-gap fixes from commit 41e7dcb.  Only guards
//! exercisable at the coordinator/client layer are tested here.  Validate()-
//! level guards for crafted DHT ops are enforced at the network layer and not
//! exercisable through normal coordinator calls.
//!
//! Test inventory:
//!   S1. Duplicate attestation guard — second submit_attestation rejected
//!   S2. Duplicate commitment guard — second notify_commitment_sealed rejected
//!   S3. Researcher commitment idempotency — second publish_researcher_commitment rejected
//!   S4. reclaim_abandoned_claim respects min_claim_timeout_secs DNA floor
//!       S4a. timeout below floor → reclaim returns false
//!       S4b. no floor (0) → timeout_secs=0 succeeds
//!   S5. force_finalize_round conservative abort when no ValidationRequest
//!   S6. reveal_researcher_result idempotency — second call rejected
//!   S7. Real-nonce reveal passes hash verification (genuine seal flow)
//!   S8. Tampered reveal rejected by hash verification ("Hash mismatch")
//!   S9.  Reveal with a DIFFERENT reproduction bundle hash is rejected
//!   S10. Reveal with the SAME reproduction bundle hash succeeds
//!   S11. A wrong-length reproduction_bundle_hash is rejected by validate()
//!
//! S9–S11 cover validator→bundle binding. The "unbound verdict" case
//! (`reproduction_bundle_hash: None`) needs no test of its own — **S7 already is
//! that test**, because `make_validation_attestation` leaves the field `None`. A
//! fourth test asserting the same path would add ~2 minutes of CI and no signal.

use valichord_sweettest::*;
use holochain_types::prelude::YamlProperties;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

async fn reveal(conductor: &SweetConductor, app: &ValiChordApp, request_ref: ExternalHash) {
    let _: ActionHash = conductor
        .call(
            &app.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref),
                nonce: vec![],
            },
        )
        .await;
}

/// Build a custom single-conductor setup with non-default attestation DNA properties.
///
/// `extra_attestation_props` is a YAML string whose keys override the base defaults.
/// Example: `"min_claim_timeout_secs: 86400\n"` or `"minimum_validators: 1\n"`.
async fn setup_single_custom_attestation(extra_attestation_props: &str) -> (SweetConductor, ValiChordApp) {
    let mut props: yaml_serde::Value = yaml_serde::from_str(
        "authorized_joining_certificate_issuer: \"\"\n\
         discipline: computational_biology\n\
         min_claim_timeout_secs: 0\n\
         minimum_validators: 2\n"
    ).unwrap();
    if !extra_attestation_props.is_empty() {
        let extra: yaml_serde::Value = yaml_serde::from_str(extra_attestation_props).unwrap();
        if let (Some(base_map), Some(extra_map)) = (props.as_mapping_mut(), extra.as_mapping()) {
            for (k, v) in extra_map {
                base_map.insert(k.clone(), v.clone());
            }
        }
    }

    let attestation = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("attestation.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(props)),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("attestation.dna not found");

    let [r, v, _a, g] = load_dnas().await;
    let dnas: [(RoleName, DnaFile); 4] = [
        ("researcher_repository".into(), r),
        ("validator_workspace".into(),   v),
        ("attestation".into(),           attestation),
        ("governance".into(),            g),
    ];
    let mut conductor = SweetConductor::standard().await;
    let app = conductor.setup_app("valichord", &dnas).await.unwrap();
    (conductor, ValiChordApp::from_sweet_app(app))
}

/// Build a custom 2-conductor setup with non-default attestation DNA properties.
async fn setup_two_agents_custom_attestation(extra_attestation_props: &str) -> TwoAgentSetup {
    let mut props: yaml_serde::Value = yaml_serde::from_str(
        "authorized_joining_certificate_issuer: \"\"\n\
         discipline: computational_biology\n\
         min_claim_timeout_secs: 0\n\
         minimum_validators: 2\n"
    ).unwrap();
    if !extra_attestation_props.is_empty() {
        let extra: yaml_serde::Value = yaml_serde::from_str(extra_attestation_props).unwrap();
        if let (Some(base_map), Some(extra_map)) = (props.as_mapping_mut(), extra.as_mapping()) {
            for (k, v) in extra_map {
                base_map.insert(k.clone(), v.clone());
            }
        }
    }

    let attestation = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("attestation.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(props)),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("attestation.dna not found");

    let [r, v, _a, g] = load_dnas().await;
    let dnas: [(RoleName, DnaFile); 4] = [
        ("researcher_repository".into(), r),
        ("validator_workspace".into(),   v),
        ("attestation".into(),           attestation),
        ("governance".into(),            g),
    ];
    let mut conductors = SweetConductorBatch::from_config_rendezvous(2, SweetConductorConfig::rendezvous(true)).await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut iter = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(iter.next().unwrap());
    let bob   = ValiChordApp::from_sweet_app(iter.next().unwrap());
    TwoAgentSetup { conductors, alice, bob }
}

// ---------------------------------------------------------------------------
// S1. Duplicate attestation guard
// ---------------------------------------------------------------------------
//
// Fix: submit_attestation checks ValidatorToAttestation links before writing.
// A second call with the same request_ref must be rejected.

#[tokio::test(flavor = "multi_thread")]
async fn s1_duplicate_attestation_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0x51);

    // notify_commitment_sealed requires a prior ValidationRequest.
    conductor
        .call::<_, ActionHash>(&zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;
    commit(&conductor, &app, request_ref.clone()).await;

    // First reveal — must succeed.
    reveal(&conductor, &app, request_ref.clone()).await;

    // Second reveal for the same study — duplicate guard must reject.
    let result: Result<ActionHash, _> = conductor
        .call_fallible(
            &zome,
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref),
                nonce: vec![],
            },
        )
        .await;
    assert!(
        result.is_err(),
        "second submit_attestation for the same study must be rejected"
    );
}

// ---------------------------------------------------------------------------
// S2. Duplicate commitment guard
// ---------------------------------------------------------------------------
//
// Fix: notify_commitment_sealed checks existing RequestToCommitment links by
// author before writing a new CommitmentAnchor.  A second call for the same
// study must be rejected.

#[tokio::test(flavor = "multi_thread")]
async fn s2_duplicate_commitment_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0x52);

    conductor
        .call::<_, ActionHash>(&zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;

    // First commitment — must succeed.
    commit(&conductor, &app, request_ref.clone()).await;

    // Second commitment for the same study — must be rejected.
    let result: Result<(), _> = conductor
        .call_fallible(
            &zome,
            "notify_commitment_sealed",
            CommitmentSealedInput {
                request_ref,
                commitment_hash: vec![0u8; 32],
            },
        )
        .await;
    assert!(
        result.is_err(),
        "second notify_commitment_sealed for the same study must be rejected"
    );
}

// ---------------------------------------------------------------------------
// S3. Researcher commitment idempotency
// ---------------------------------------------------------------------------
//
// Fix: publish_researcher_commitment checks RequestToResearcherCommitment
// links before writing.  A second call for the same study must be rejected.

#[tokio::test(flavor = "multi_thread")]
async fn s3_researcher_commitment_idempotency() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0x53);
    let commitment_hash = vec![0xaau8; 32];

    // First commitment — must succeed.
    let first: ActionHash = conductor
        .call(
            &zome,
            "publish_researcher_commitment",
            ResearcherCommitmentInput {
                request_ref:            request_ref.clone(),
                result_commitment_hash: commitment_hash.clone(),
            },
        )
        .await;
    assert_ne!(first.as_ref().len(), 0);

    // Second commitment for the same study — idempotency guard must reject.
    let result: Result<ActionHash, _> = conductor
        .call_fallible(
            &zome,
            "publish_researcher_commitment",
            ResearcherCommitmentInput {
                request_ref,
                result_commitment_hash: commitment_hash,
            },
        )
        .await;
    assert!(
        result.is_err(),
        "second publish_researcher_commitment for the same study must be rejected"
    );
}

// ---------------------------------------------------------------------------
// S4a. reclaim_abandoned_claim respects min_claim_timeout_secs DNA floor
// ---------------------------------------------------------------------------
//
// With min_claim_timeout_secs=86400, passing timeout_secs=0 must not succeed
// because 0 < 86400 = DNA floor.  The floor is enforced by reading
// DnaProperties.min_claim_timeout_secs inside the coordinator.

#[tokio::test(flavor = "multi_thread")]
async fn s4a_reclaim_respects_min_claim_timeout_floor() {
    use attestation_coordinator::ReclaimInput;

    // Install with min_claim_timeout_secs = 86400 (one day).
    let setup = setup_two_agents_custom_attestation("min_claim_timeout_secs: 86400\n").await;

    let request_ref = fake_external_hash(0x54);

    // Submit ValidationRequest (Alice as researcher; researcher_institution = "Open Science Lab").
    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;

    // Bob claims the study (different institution — no COI).
    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Oxford"),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let claim_hash: ActionHash = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // Alice tries to reclaim with timeout_secs=0 — DNA floor=86400 blocks it.
    // Claim is fresh (< 86400 s old) → reclaim must return false.
    let reclaimed: bool = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "reclaim_abandoned_claim",
            ReclaimInput {
                request_ref,
                claim_hash,
                timeout_secs: 0,
            },
        )
        .await;
    assert!(
        !reclaimed,
        "reclaim_abandoned_claim must return false when timeout_secs < min_claim_timeout_secs"
    );
}

// ---------------------------------------------------------------------------
// S4b. reclaim_abandoned_claim — no DNA floor (0) → timeout_secs=0 succeeds
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn s4b_reclaim_no_floor_timeout_zero_succeeds() {
    use attestation_coordinator::ReclaimInput;

    // Default config: min_claim_timeout_secs=0 (dev bypass).
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0x55);

    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;

    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Oxford"),
        )
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    let claim_hash: ActionHash = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    await_consistency_s(20, [&setup.alice.attestation, &setup.bob.attestation])
        .await
        .unwrap();

    // No floor: timeout_secs=0 → elapsed (near 0 s) >= 0 → eligible → returns true.
    let reclaimed: bool = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "reclaim_abandoned_claim",
            ReclaimInput {
                request_ref,
                claim_hash,
                timeout_secs: 0,
            },
        )
        .await;
    assert!(
        reclaimed,
        "reclaim_abandoned_claim must return true when min_claim_timeout_secs=0 and no attestation"
    );
}

// ---------------------------------------------------------------------------
// S5. force_finalize_round conservative abort on missing ValidationRequest
// ---------------------------------------------------------------------------
//
// Fix: when get_validation_request_for_data_hash returns None,
// force_finalize_round returns None conservatively (cannot verify round age).
// The "no attestations" early-return fires first anyway, but both guard paths
// produce the same conservative null return.

#[tokio::test(flavor = "multi_thread")]
async fn s5_force_finalize_no_vr_returns_none() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();

    // No ValidationRequest and no attestation for this request_ref.
    let fake_ref = fake_external_hash(0x5a);

    let result: Option<ActionHash> = conductor
        .call(&gov_zome, "force_finalize_round", fake_ref)
        .await;
    assert!(
        result.is_none(),
        "force_finalize_round must return None when no ValidationRequest or attestations exist"
    );
}

// ---------------------------------------------------------------------------
// S6. reveal_researcher_result idempotency
// ---------------------------------------------------------------------------
//
// Fix: reveal_researcher_result checks RequestToResearcherReveal links before
// writing.  A second call is rejected ("already exists") before hash check.
//
// Requires minimum_validators=1 so Alice alone can complete the commit phase.
//
// The commitment hash is SHA-256(msgpack([]) || []) where:
//   msgpack([]) = 0x90 (fixarray, 0 elements)
//   nonce = []
//   SHA-256([0x90]) = 9e076ceaf246b6003d9c2680a2b4cf0bffd069805902b0b5edeebf49039fe4bd
//
// This hash MUST match what the coordinator computes for metrics=[], nonce=[].

#[tokio::test(flavor = "multi_thread")]
async fn s6_reveal_researcher_result_idempotency() {
    // Inline single-conductor setup with minimum_validators=1.
    let (conductor, app) =
        setup_single_custom_attestation("minimum_validators: 1\n").await;
    let zome = app.attestation_zome();

    let request_ref = fake_external_hash(0x56);

    // SHA-256(msgpack(vec![]) || vec![]) = SHA-256([0x90])
    // Pre-computed; must match exactly what the Rust sha2+rmp_serde codec produces.
    let commitment_hash: Vec<u8> = vec![
        0x9e, 0x07, 0x6c, 0xea, 0xf2, 0x46, 0xb6, 0x00,
        0x3d, 0x9c, 0x26, 0x80, 0xa2, 0xb4, 0xcf, 0x0b,
        0xff, 0xd0, 0x69, 0x80, 0x59, 0x02, 0xb0, 0xb5,
        0xed, 0xee, 0xbf, 0x49, 0x03, 0x9f, 0xe4, 0xbd,
    ];

    // Publish the researcher's commitment hash.
    conductor
        .call::<_, ActionHash>(
            &zome,
            "publish_researcher_commitment",
            ResearcherCommitmentInput {
                request_ref:            request_ref.clone(),
                result_commitment_hash: commitment_hash,
            },
        )
        .await;

    // Submit ValidationRequest with num_validators_required=1 so Alice can be
    // the sole validator.
    let mut vr = make_validation_request(request_ref.clone());
    vr.num_validators_required = 1;
    conductor
        .call::<_, ActionHash>(&zome, "submit_validation_request", vr)
        .await;

    // Alice commits as the sole validator — with min_validators=1 this
    // triggers check_all_commitments_sealed_inner to return true.
    conductor
        .call::<_, ()>(
            &zome,
            "notify_commitment_sealed",
            CommitmentSealedInput {
                request_ref:     request_ref.clone(),
                commitment_hash: vec![0u8; 32],
            },
        )
        .await;

    // First reveal — must succeed (hash matches commitment).
    let reveal_payload = attestation_integrity::ResearcherRevealInput {
        request_ref: request_ref.clone(),
        metrics:     vec![],
        nonce:       vec![],
    };
    conductor
        .call::<_, ActionHash>(&zome, "reveal_researcher_result", reveal_payload.clone())
        .await;

    // Second reveal — idempotency guard fires before hash check.
    let result: Result<ActionHash, _> = conductor
        .call_fallible(&zome, "reveal_researcher_result", reveal_payload)
        .await;
    assert!(
        result.is_err(),
        "second reveal_researcher_result for the same study must be rejected"
    );
}

// ---------------------------------------------------------------------------
// S7. Commit-reveal hash verification — happy path with a REAL nonce
// ---------------------------------------------------------------------------
//
// Runs the genuine flow: seal_private_attestation (workspace DNA generates a
// random 32-byte nonce, computes commitment_hash, post_commit writes the
// CommitmentAnchor), then submit_attestation with the SAME attestation and the
// real nonce.  Because the nonce is non-empty, the coordinator recomputes
// SHA-256(msgpack(attestation) || nonce) and compares it to the anchor — this
// exercises the verification branch even on a dev-mode network (empty issuer).
//
// Before this test, no automated test anywhere exercised the verification
// branch: every other test reveals with an empty nonce (dev bypass).

#[tokio::test(flavor = "multi_thread")]
async fn s7_real_nonce_reveal_passes_hash_verification() {
    let (conductor, app) = setup_single().await;
    let att_zome = app.attestation_zome();
    let vw_zome  = app.validator_zome();
    let request_ref = fake_external_hash(0x57);

    // Researcher side: publish the ValidationRequest.
    conductor
        .call::<_, ActionHash>(&att_zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;

    // Validator side: receive task, then seal — the workspace DNA generates the
    // nonce and post_commit fires notify_commitment_sealed on the attestation DNA.
    let attestation = make_validation_attestation(request_ref.clone());
    let task_hash: ActionHash = conductor
        .call(&vw_zome, "receive_task", make_task(request_ref.clone()))
        .await;
    let _sealed: ActionHash = conductor
        .call(
            &vw_zome,
            "seal_private_attestation",
            validator_workspace_coordinator::SealAttestationInput {
                task_hash: task_hash.clone(),
                attestation: attestation.clone(),
            },
        )
        .await;

    // Extract the real nonce from the private entry.
    let private_record: Option<Record> = conductor
        .call(&vw_zome, "get_private_attestation_for_task", task_hash)
        .await;
    let private_att: validator_workspace_integrity::ValidatorPrivateAttestation = private_record
        .expect("sealed private attestation must be retrievable")
        .entry()
        .to_app_option()
        .expect("entry must deserialize")
        .expect("entry must be a ValidatorPrivateAttestation");
    assert_eq!(private_att.nonce.len(), 32, "seal must generate a 32-byte nonce");

    // Reveal with the SAME attestation + the real nonce.  post_commit's
    // notify_commitment_sealed runs asynchronously after seal returns, so
    // retry while the anchor has not landed yet.
    let mut last: Option<Result<ActionHash, _>> = None;
    for _ in 0..20 {
        let attempt = conductor
            .call_fallible(
                &att_zome,
                "submit_attestation",
                RevealInput {
                    attestation: attestation.clone(),
                    nonce: private_att.nonce.clone(),
                },
            )
            .await;
        let anchor_pending = matches!(
            &attempt,
            Err(e) if format!("{e:?}").contains("No CommitmentAnchor")
        );
        last = Some(attempt);
        if !anchor_pending { break; }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    }
    let last = last.expect("at least one submit_attestation attempt");
    assert!(
        last.is_ok(),
        "reveal with the sealed attestation and real nonce must pass hash \
         verification, got: {:?}",
        last.err(),
    );
}

// ---------------------------------------------------------------------------
// S8. Commit-reveal hash verification — TAMPERED reveal rejected
// ---------------------------------------------------------------------------
//
// Same genuine seal flow as S7, but the reveal submits an attestation whose
// content differs from what was sealed.  The recomputed hash cannot match the
// CommitmentAnchor and the coordinator must reject with "Hash mismatch".
// This is the structural guarantee the protocol advertises: a validator
// cannot change their verdict between commit and reveal.

#[tokio::test(flavor = "multi_thread")]
async fn s8_tampered_reveal_rejected_by_hash_verification() {
    let (conductor, app) = setup_single().await;
    let att_zome = app.attestation_zome();
    let vw_zome  = app.validator_zome();
    let request_ref = fake_external_hash(0x58);

    conductor
        .call::<_, ActionHash>(&att_zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;

    let sealed_attestation = make_validation_attestation(request_ref.clone());
    let task_hash: ActionHash = conductor
        .call(&vw_zome, "receive_task", make_task(request_ref.clone()))
        .await;
    let _sealed: ActionHash = conductor
        .call(
            &vw_zome,
            "seal_private_attestation",
            validator_workspace_coordinator::SealAttestationInput {
                task_hash: task_hash.clone(),
                attestation: sealed_attestation.clone(),
            },
        )
        .await;

    let private_record: Option<Record> = conductor
        .call(&vw_zome, "get_private_attestation_for_task", task_hash)
        .await;
    let private_att: validator_workspace_integrity::ValidatorPrivateAttestation = private_record
        .expect("sealed private attestation must be retrievable")
        .entry()
        .to_app_option()
        .expect("entry must deserialize")
        .expect("entry must be a ValidatorPrivateAttestation");

    // Tamper: change the verdict content after sealing.
    let mut tampered = sealed_attestation;
    tampered.time_invested_secs = 1; // any content change breaks the hash

    let mut last: Option<Result<ActionHash, _>> = None;
    for _ in 0..20 {
        let attempt = conductor
            .call_fallible(
                &att_zome,
                "submit_attestation",
                RevealInput {
                    attestation: tampered.clone(),
                    nonce: private_att.nonce.clone(),
                },
            )
            .await;
        let anchor_pending = matches!(
            &attempt,
            Err(e) if format!("{e:?}").contains("No CommitmentAnchor")
        );
        last = Some(attempt);
        if !anchor_pending { break; }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    }
    let err = last
        .expect("at least one submit_attestation attempt")
        .expect_err("tampered reveal with a real nonce must be rejected");
    assert!(
        format!("{err:?}").contains("Hash mismatch"),
        "rejection must come from hash verification, got: {err:?}",
    );
}

// ---------------------------------------------------------------------------
// Shared driver for the bundle-binding tests (S9 / S10)
// ---------------------------------------------------------------------------
//
// Seals `sealed`, then reveals `revealed`, and returns the reveal result. The
// two differ only in `reproduction_bundle_hash` at the call sites below, so any
// difference in outcome is attributable to that field and nothing else.

async fn seal_then_reveal(
    request_ref: ExternalHash,
    sealed: ValidationAttestation,
    revealed: ValidationAttestation,
) -> holochain::conductor::api::error::ConductorApiResult<ActionHash> {
    let (conductor, app) = setup_single().await;
    let att_zome = app.attestation_zome();
    let vw_zome  = app.validator_zome();

    conductor
        .call::<_, ActionHash>(
            &att_zome,
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;

    let task_hash: ActionHash = conductor
        .call(&vw_zome, "receive_task", make_task(request_ref.clone()))
        .await;
    let _sealed: ActionHash = conductor
        .call(
            &vw_zome,
            "seal_private_attestation",
            validator_workspace_coordinator::SealAttestationInput {
                task_hash: task_hash.clone(),
                attestation: sealed,
            },
        )
        .await;

    let private_record: Option<Record> = conductor
        .call(&vw_zome, "get_private_attestation_for_task", task_hash)
        .await;
    let private_att: validator_workspace_integrity::ValidatorPrivateAttestation = private_record
        .expect("sealed private attestation must be retrievable")
        .entry()
        .to_app_option()
        .expect("entry must deserialize")
        .expect("entry must be a ValidatorPrivateAttestation");

    // post_commit's notify_commitment_sealed runs asynchronously after seal
    // returns, so retry while the anchor has not landed yet.
    let mut last: Option<Result<ActionHash, _>> = None;
    for _ in 0..20 {
        let attempt = conductor
            .call_fallible(
                &att_zome,
                "submit_attestation",
                RevealInput {
                    attestation: revealed.clone(),
                    nonce: private_att.nonce.clone(),
                },
            )
            .await;
        let anchor_pending = matches!(
            &attempt,
            Err(e) if format!("{e:?}").contains("No CommitmentAnchor")
        );
        last = Some(attempt);
        if !anchor_pending { break; }
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    }
    last.expect("at least one submit_attestation attempt")
}

// ---------------------------------------------------------------------------
// S9. Validator→bundle binding — reveal with a DIFFERENT bundle hash is rejected
// ---------------------------------------------------------------------------
//
// THIS IS THE NEGATIVE CONTROL FOR THE WHOLE FEATURE, and the only test that
// distinguishes "the field exists" from "the field is bound".
//
// The validator seals a verdict committing to bundle A, then reveals the same
// verdict claiming bundle B. Everything else — outcome, confidence, timings,
// nonce — is byte-identical. Before this feature the reveal SUCCEEDED, because
// nothing tied the verdict to the work behind it: that is precisely the gap
// documented against ValiChord in falsify-cookbook Pattern 13.
//
// ⚠️ Verified to be able to fail, per the repo's standing rule. With the single
// line `canonical.reproduction_bundle_hash = None;` added to
// `commitment_msgpack_bytes()` — i.e. the field present but unbound, the exact
// accident a well-meaning "normalise the optional fields" edit would cause —
// this test PASSES WRONGLY and every other test in the suite stays green.
// Removing that line turns it red again. The binding is what it detects.

#[tokio::test(flavor = "multi_thread")]
async fn s9_reveal_with_different_bundle_hash_is_rejected() {
    let request_ref = fake_external_hash(0x59);
    let sealed   = make_validation_attestation_bound(request_ref.clone(), fake_bundle_hash(0xAA));
    let revealed = make_validation_attestation_bound(request_ref.clone(), fake_bundle_hash(0xBB));

    let err = seal_then_reveal(request_ref, sealed, revealed)
        .await
        .expect_err(
            "revealing a bundle hash other than the one committed to must be rejected — \
             if this passes, validator verdicts are not bound to their reproduction work",
        );
    assert!(
        format!("{err:?}").contains("Hash mismatch"),
        "rejection must come from commitment hash verification, got: {err:?}",
    );
}

// ---------------------------------------------------------------------------
// S10. Validator→bundle binding — the honest path still works
// ---------------------------------------------------------------------------
//
// The complement to S9, and not a formality: S9 alone would also pass if the
// binding rejected *everything*. This proves the happy path is intact, so the
// two together show the check discriminates rather than merely refuses.

#[tokio::test(flavor = "multi_thread")]
async fn s10_reveal_with_same_bundle_hash_succeeds() {
    let request_ref = fake_external_hash(0x5A);
    let bundle = fake_bundle_hash(0xCC);
    let att = make_validation_attestation_bound(request_ref.clone(), bundle);

    let result = seal_then_reveal(request_ref, att.clone(), att).await;
    assert!(
        result.is_ok(),
        "revealing the same bundle hash that was sealed must pass hash \
         verification, got: {:?}",
        result.err(),
    );
}

// ---------------------------------------------------------------------------
// S11. Shape guard — a wrong-length bundle hash is rejected by validate()
// ---------------------------------------------------------------------------
//
// A 31-byte value is not a SHA-256 content_hash. It survives commit-reveal
// verification (both sides hash the same 31 bytes), so the coordinator has no
// reason to object — the integrity zome is the only thing standing between a
// malformed binding and a record that *looks* bound but commits to nothing
// checkable. Asserts on the specific guard message, never a bare is_err(): a
// bare is_err() here would also pass on "function not found", which is exactly
// how three earlier "immutability" tests spent months proving nothing.

#[tokio::test(flavor = "multi_thread")]
async fn s11_wrong_length_bundle_hash_is_rejected() {
    let request_ref = fake_external_hash(0x5B);
    let att = make_validation_attestation_bound(request_ref.clone(), vec![0xDD; 31]);

    let err = seal_then_reveal(request_ref, att.clone(), att)
        .await
        .expect_err("a 31-byte reproduction_bundle_hash must be rejected");
    assert!(
        format!("{err:?}").contains("reproduction_bundle_hash must be exactly 32 bytes"),
        "rejection must come from the integrity zome's shape guard, not from \
         something incidental, got: {err:?}",
    );
}
