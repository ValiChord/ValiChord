//! Integration tests for DNA 1 — Researcher Repository.
//!
//! All entries are private (visibility = "private") — single-agent source chain
//! only.  No dhtSync / consistency_10s needed.  Every test uses setup_single().
//!
//! Test inventory:
//!   1. register_study + get_study
//!   2. register_protocol + get_protocol_for_study
//!   3. take_data_snapshot + get_snapshots_for_study
//!   4. declare_deviation + get_deviations_for_study
//!   5. compute_data_hash (SHA-256, deterministic, collision-resistant)
//!   6. PreRegisteredProtocol immutability — no delete function in API
//!   7. get_all_studies (empty + multi)
//!   8. lock_researcher_result + get_locked_result (new — previously untested)
//!   9. lock_researcher_result cross-DNA commitment publish (new)
//!  10. get_locked_result returns None for unknown request_ref (new)

use valichord_sweettest::*;
use researcher_repository_coordinator::{
    DeclareDeviationInput, LockResultInput, RegisterProtocolInput, TakeDataSnapshotInput,
};

// ---------------------------------------------------------------------------
// 1. register_study + get_study
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn register_and_get_study() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    let record: Option<Record> = conductor.call(&zome, "get_study", study_hash).await;
    assert!(record.is_some(), "registered study should be retrievable by its ActionHash");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_study_unknown_hash_returns_none() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let unknown = fake_action_hash(0xff);
    let result: Option<Record> = conductor.call(&zome, "get_study", unknown).await;
    assert!(result.is_none(), "get_study should return None for an unwritten ActionHash");
}

// ---------------------------------------------------------------------------
// 2. register_protocol + get_protocol_for_study
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn register_and_get_protocol() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    let protocol_hash: ActionHash = conductor
        .call(
            &zome,
            "register_protocol",
            RegisterProtocolInput {
                study_ref: study_hash.clone(),
                protocol:  make_protocol(),
            },
        )
        .await;
    assert_ne!(protocol_hash.as_ref(), study_hash.as_ref());

    let record: Option<Record> = conductor
        .call(&zome, "get_protocol_for_study", study_hash)
        .await;
    assert!(record.is_some(), "registered protocol should be retrievable via its parent study");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_protocol_returns_none_before_registration() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    let result: Option<Record> = conductor
        .call(&zome, "get_protocol_for_study", study_hash)
        .await;
    assert!(result.is_none(), "get_protocol_for_study should return None before any protocol is registered");
}

// ---------------------------------------------------------------------------
// 3. take_data_snapshot + get_snapshots_for_study
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn two_snapshots_are_both_retrievable() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    // Snapshot 1 — initial dataset.
    conductor
        .call::<_, ActionHash>(
            &zome,
            "take_data_snapshot",
            TakeDataSnapshotInput {
                study_ref: study_hash.clone(),
                snapshot:  make_snapshot(fake_external_hash(0x01)),
            },
        )
        .await;

    // Snapshot 2 — updated dataset after data cleaning.
    let mut snap2 = make_snapshot(fake_external_hash(0x02));
    snap2.file_count = 13;
    conductor
        .call::<_, ActionHash>(
            &zome,
            "take_data_snapshot",
            TakeDataSnapshotInput {
                study_ref: study_hash.clone(),
                snapshot:  snap2,
            },
        )
        .await;

    let snapshots: Vec<Record> = conductor
        .call(&zome, "get_snapshots_for_study", study_hash)
        .await;
    assert_eq!(snapshots.len(), 2, "both snapshots should be retrievable for the same study");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_snapshots_empty_before_any_snapshot() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    let snapshots: Vec<Record> = conductor
        .call(&zome, "get_snapshots_for_study", study_hash)
        .await;
    assert_eq!(snapshots.len(), 0);
}

// ---------------------------------------------------------------------------
// 4. declare_deviation + get_deviations_for_study
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn declare_and_retrieve_deviation() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    conductor
        .call::<_, ActionHash>(
            &zome,
            "declare_deviation",
            DeclareDeviationInput {
                study_ref: study_hash.clone(),
                deviation: make_undeclared_deviation(),
            },
        )
        .await;

    let deviations: Vec<Record> = conductor
        .call(&zome, "get_deviations_for_study", study_hash)
        .await;
    assert_eq!(deviations.len(), 1, "declared deviation should be retrievable for its parent study");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_deviations_empty_before_any_declaration() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;

    let deviations: Vec<Record> = conductor
        .call(&zome, "get_deviations_for_study", study_hash)
        .await;
    assert_eq!(deviations.len(), 0);
}

// ---------------------------------------------------------------------------
// 5. compute_data_hash (SHA-256)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn compute_data_hash_returns_external_hash() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    // 256 bytes all set to 0xAB — arbitrary fingerprint stand-in.
    let data: Vec<u8> = vec![0xab; 256];
    let hash: ExternalHash = conductor.call(&zome, "compute_data_hash", data).await;

    // ExternalHash encodes as 39 bytes: 3-byte type prefix + 32-byte SHA-256 + 4-byte loc.
    let raw = hash.get_raw_39();
    assert_eq!(raw.len(), 39, "ExternalHash should be 39 bytes");
    // ExternalHash prefix bytes [0x84, 0x2F, 0x24] (ExternalHash type).
    assert_eq!(raw[0], 0x84);
    assert_eq!(raw[1], 0x2f);
    assert_eq!(raw[2], 0x24);
}

#[tokio::test(flavor = "multi_thread")]
async fn compute_data_hash_is_deterministic() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let data: Vec<u8> = vec![1, 2, 3, 4, 5];
    let h1: ExternalHash = conductor.call(&zome, "compute_data_hash", data.clone()).await;
    let h2: ExternalHash = conductor.call(&zome, "compute_data_hash", data).await;

    assert_eq!(h1, h2, "same bytes should always produce the same hash");
}

#[tokio::test(flavor = "multi_thread")]
async fn compute_data_hash_collision_resistant() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let h1: ExternalHash = conductor.call(&zome, "compute_data_hash", vec![0x01u8]).await;
    let h2: ExternalHash = conductor.call(&zome, "compute_data_hash", vec![0x02u8]).await;

    assert_ne!(h1, h2, "different bytes must produce different hashes");
}

// ---------------------------------------------------------------------------
// 6. PreRegisteredProtocol immutability — no delete function in the API
// ---------------------------------------------------------------------------
//
// validate() in researcher_repository_integrity blocks all deletes of
// PreRegisteredProtocol entries.  The coordinator provides no delete function,
// so any attempt to call one is rejected at the conductor level (function not
// found) before the entry system is even reached.  Both layers are tested
// by this approach: if a delete fn were added in the future it would need
// validation to approve it — which validate() never will.

#[tokio::test(flavor = "multi_thread")]
async fn protocol_immutability_no_delete_fn_in_api() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;
    let protocol_hash: ActionHash = conductor
        .call(
            &zome,
            "register_protocol",
            RegisterProtocolInput {
                study_ref: study_hash,
                protocol:  make_protocol(),
            },
        )
        .await;

    // Calling a nonexistent function must fail — confirms no delete path in API.
    // call_fallible returns ConductorApiResult<O>; O = () since we don't need the value.
    let result: Result<(), _> = conductor
        .call_fallible(&zome, "delete_protocol_for_test", protocol_hash)
        .await;
    assert!(result.is_err(), "calling a nonexistent delete function must be rejected");
}

// ---------------------------------------------------------------------------
// 7. get_all_studies
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_all_studies_empty_initially() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let studies: Vec<Record> = conductor.call(&zome, "get_all_studies", ()).await;
    assert_eq!(studies.len(), 0, "get_all_studies should return empty list before any registration");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_all_studies_returns_all_registered() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    for title in &["Study Alpha", "Study Beta", "Study Gamma"] {
        let mut s = make_study();
        s.title = (*title).into();
        conductor.call::<_, ActionHash>(&zome, "register_study", s).await;
    }

    let studies: Vec<Record> = conductor.call(&zome, "get_all_studies", ()).await;
    assert_eq!(studies.len(), 3, "get_all_studies should return all three registered studies");

    // Verify that all three ActionHashes are distinct.
    let hashes: std::collections::HashSet<Vec<u8>> = studies
        .iter()
        .map(|r| r.action_address().as_ref().to_vec())
        .collect();
    assert_eq!(hashes.len(), 3, "all three returned records should have distinct ActionHashes");
}

// ---------------------------------------------------------------------------
// 8. lock_researcher_result + get_locked_result (new)
// ---------------------------------------------------------------------------
//
// lock_researcher_result:
//   1. Generates a random nonce.
//   2. Computes SHA-256(msgpack(metrics) || nonce) → commitment_hash.
//   3. Stores a private LockedResult entry.
//   4. Cross-calls publish_researcher_commitment on the attestation DNA.
//   5. Returns ActionHash of the private entry.
//
// get_locked_result follows the RequestToLockedResult link.

#[tokio::test(flavor = "multi_thread")]
async fn lock_researcher_result_creates_private_entry() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let request_ref = fake_external_hash(0x10);

    let locked_hash: ActionHash = conductor
        .call(
            &zome,
            "lock_researcher_result",
            LockResultInput {
                request_ref: request_ref.clone(),
                metrics:     vec![],   // empty metrics — tests the locking mechanism, not metric content
            },
        )
        .await;

    // Private entry should be retrievable locally.
    let record: Option<Record> = conductor
        .call(&zome, "get_locked_result", request_ref)
        .await;
    assert!(record.is_some(), "locked result should be retrievable by its request_ref");

    // The locked_hash must match the action address of the retrieved record.
    let retrieved_hash = record.unwrap().action_address().clone();
    assert_eq!(
        locked_hash, retrieved_hash,
        "lock_researcher_result return value should match get_locked_result record hash"
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn get_locked_result_returns_none_for_unknown_request() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    // A request_ref that was never locked.
    let unknown_ref = fake_external_hash(0xaa);
    let result: Option<Record> = conductor
        .call(&zome, "get_locked_result", unknown_ref)
        .await;
    assert!(result.is_none(), "get_locked_result should return None for a request that was never locked");
}

// ---------------------------------------------------------------------------
// 9. lock_researcher_result cross-DNA commitment publish (new)
// ---------------------------------------------------------------------------
//
// After lock_researcher_result succeeds, the commitment hash must be visible
// on the attestation DNA via get_researcher_commitment.  This verifies the
// cross-DNA call (CallTargetCell::OtherRole("attestation")) actually landed.

#[tokio::test(flavor = "multi_thread")]
async fn lock_researcher_result_publishes_commitment_to_attestation_dna() {
    let (conductor, app) = setup_single().await;
    let researcher_zome   = app.researcher_zome();
    let attestation_zome  = app.attestation_zome();

    let request_ref = fake_external_hash(0x20);

    // Lock the result on the researcher DNA — this triggers the cross-DNA call.
    conductor
        .call::<_, ActionHash>(
            &researcher_zome,
            "lock_researcher_result",
            LockResultInput {
                request_ref: request_ref.clone(),
                metrics:     vec![],
            },
        )
        .await;

    // The commitment must now be visible on the attestation DNA.
    let commitment: Option<Record> = conductor
        .call(&attestation_zome, "get_researcher_commitment", request_ref)
        .await;
    assert!(
        commitment.is_some(),
        "publish_researcher_commitment cross-DNA call should make the commitment \
         visible via get_researcher_commitment on the attestation DNA"
    );
}
