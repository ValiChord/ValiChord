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
    let mut props: serde_yaml::Value = serde_yaml::from_str(
        "authorized_joining_certificate_issuer: \"\"\n\
         discipline: computational_biology\n\
         min_claim_timeout_secs: 0\n\
         minimum_validators: 2\n"
    ).unwrap();
    if !extra_attestation_props.is_empty() {
        let extra: serde_yaml::Value = serde_yaml::from_str(extra_attestation_props).unwrap();
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
    let mut conductor = SweetConductor::from_standard_config().await;
    let app = conductor.setup_app("valichord", &dnas).await.unwrap();
    (conductor, ValiChordApp::from_sweet_app(app))
}

/// Build a custom 2-conductor setup with non-default attestation DNA properties.
async fn setup_two_agents_custom_attestation(extra_attestation_props: &str) -> TwoAgentSetup {
    let mut props: serde_yaml::Value = serde_yaml::from_str(
        "authorized_joining_certificate_issuer: \"\"\n\
         discipline: computational_biology\n\
         min_claim_timeout_secs: 0\n\
         minimum_validators: 2\n"
    ).unwrap();
    if !extra_attestation_props.is_empty() {
        let extra: serde_yaml::Value = serde_yaml::from_str(extra_attestation_props).unwrap();
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
    let mut conductors = SweetConductorBatch::from_standard_config_rendezvous(2).await;
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
    let mut setup = setup_two_agents_custom_attestation("min_claim_timeout_secs: 86400\n").await;

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
    let mut setup = setup_two_agents().await;
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
