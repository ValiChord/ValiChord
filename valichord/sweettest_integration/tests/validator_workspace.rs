//! Integration tests for DNA 2 — Validator Workspace.
//!
//! All entries are private (visibility = "private") — single-agent source chain
//! only.  No dhtSync / consistency_10s needed.  Every test uses setup_single().
//!
//! Note: seal_private_attestation's post_commit fires a cross-DNA call to
//! attestation.notify_commitment_sealed.  With minimum_validators: 2 and only
//! one validator, the CommitmentAnchor count stays at 1 — no PhaseMarker is
//! written.  post_commit is infallible so failures are logged and dropped.
//!
//! Test inventory:
//!   1. receive_task + get_task
//!   2. seal_private_attestation + get_private_attestation_for_task
//!   3. get_all_tasks (empty + multi)
//!   4. get_all_private_attestations — empty + multi (new — previously untested)
//!   5. ValidatorPrivateAttestation immutability — no delete function in API (new)
//!   6. record_deliberate_abstention + get_abstention_for_request (new)

use valichord_sweettest::*;
use validator_workspace_coordinator::SealAttestationInput;
use validator_workspace_integrity::DeliberateAbstention;

// ---------------------------------------------------------------------------
// 1. receive_task + get_task
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn receive_and_get_task() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0xaa);
    let task_hash: ActionHash = conductor
        .call(&zome, "receive_task", make_task(request_ref))
        .await;

    let record: Option<Record> = conductor.call(&zome, "get_task", task_hash).await;
    assert!(record.is_some(), "received task should be retrievable by its ActionHash");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_task_unknown_hash_returns_none() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let unknown = fake_action_hash(0xff);
    let result: Option<Record> = conductor.call(&zome, "get_task", unknown).await;
    assert!(result.is_none(), "get_task should return None for an unwritten ActionHash");
}

// ---------------------------------------------------------------------------
// 2. seal_private_attestation + get_private_attestation_for_task
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn seal_and_get_private_attestation() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0xbb);

    // Step 1: receive the task.
    let task_hash: ActionHash = conductor
        .call(&zome, "receive_task", make_task(request_ref.clone()))
        .await;

    // Step 2: seal the private attestation.
    // post_commit fires notify_commitment_sealed on the attestation DNA
    // (infallible — failures are silently logged, not propagated).
    let attestation_hash: ActionHash = conductor
        .call(
            &zome,
            "seal_private_attestation",
            SealAttestationInput {
                task_hash: task_hash.clone(),
                attestation: make_validation_attestation(request_ref),
            },
        )
        .await;
    assert_ne!(attestation_hash.as_ref(), task_hash.as_ref());

    // Step 3: retrieve via task link.
    let record: Option<Record> = conductor
        .call(&zome, "get_private_attestation_for_task", task_hash)
        .await;
    assert!(record.is_some(), "sealed private attestation should be retrievable via its parent task");
}

#[tokio::test(flavor = "multi_thread")]
async fn get_private_attestation_returns_none_before_sealing() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0xcc);
    let task_hash: ActionHash = conductor
        .call(&zome, "receive_task", make_task(request_ref))
        .await;

    let result: Option<Record> = conductor
        .call(&zome, "get_private_attestation_for_task", task_hash)
        .await;
    assert!(result.is_none(), "get_private_attestation_for_task should return None before any attestation is sealed");
}

// ---------------------------------------------------------------------------
// 3. get_all_tasks
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_all_tasks_empty_initially() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let tasks: Vec<Record> = conductor.call(&zome, "get_all_tasks", ()).await;
    assert_eq!(tasks.len(), 0);
}

#[tokio::test(flavor = "multi_thread")]
async fn get_all_tasks_returns_all_received() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    for byte in [0x01u8, 0x02, 0x03] {
        conductor
            .call::<_, ActionHash>(
                &zome,
                "receive_task",
                make_task(fake_external_hash(byte)),
            )
            .await;
    }

    let tasks: Vec<Record> = conductor.call(&zome, "get_all_tasks", ()).await;
    assert_eq!(tasks.len(), 3, "get_all_tasks should return all three received tasks");

    let hashes: std::collections::HashSet<Vec<u8>> = tasks
        .iter()
        .map(|r| r.action_address().as_ref().to_vec())
        .collect();
    assert_eq!(hashes.len(), 3, "all three returned records should have distinct ActionHashes");
}

// ---------------------------------------------------------------------------
// 4. get_all_private_attestations (new — previously untested)
// ---------------------------------------------------------------------------
//
// Queries the local source chain for all ValidatorPrivateAttestation entries
// via deserialization filter — same pattern as get_all_tasks.

#[tokio::test(flavor = "multi_thread")]
async fn get_all_private_attestations_empty_initially() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let attestations: Vec<Record> = conductor
        .call(&zome, "get_all_private_attestations", ())
        .await;
    assert_eq!(attestations.len(), 0);
}

#[tokio::test(flavor = "multi_thread")]
async fn get_all_private_attestations_returns_all_sealed() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    // Receive two tasks, seal an attestation for each.
    for byte in [0x10u8, 0x20] {
        let rr = fake_external_hash(byte);
        let task_hash: ActionHash = conductor
            .call(&zome, "receive_task", make_task(rr.clone()))
            .await;
        conductor
            .call::<_, ActionHash>(
                &zome,
                "seal_private_attestation",
                SealAttestationInput {
                    task_hash,
                    attestation: make_validation_attestation(rr),
                },
            )
            .await;
    }

    let attestations: Vec<Record> = conductor
        .call(&zome, "get_all_private_attestations", ())
        .await;
    assert_eq!(
        attestations.len(),
        2,
        "get_all_private_attestations should return all two sealed attestations"
    );

    // All ActionHashes must be distinct.
    let hashes: std::collections::HashSet<Vec<u8>> = attestations
        .iter()
        .map(|r| r.action_address().as_ref().to_vec())
        .collect();
    assert_eq!(hashes.len(), 2, "sealed attestations should have distinct ActionHashes");
}

// ---------------------------------------------------------------------------
// 5. ValidatorPrivateAttestation immutability — no delete function in API (new)
// ---------------------------------------------------------------------------
//
// The coordinator exposes no delete or update function for ValidatorPrivateAttestation.
// Attempting to call a nonexistent delete function must be rejected at the
// conductor level (function not found).

#[tokio::test(flavor = "multi_thread")]
async fn private_attestation_immutability_no_delete_fn_in_api() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0x30);
    let task_hash: ActionHash = conductor
        .call(&zome, "receive_task", make_task(request_ref.clone()))
        .await;
    let attestation_hash: ActionHash = conductor
        .call(
            &zome,
            "seal_private_attestation",
            SealAttestationInput {
                task_hash,
                attestation: make_validation_attestation(request_ref),
            },
        )
        .await;

    // No delete function exists — calling a nonexistent fn must fail.
    let result: Result<(), _> = conductor
        .call_fallible(&zome, "delete_attestation_for_test", attestation_hash)
        .await;
    assert!(result.is_err(), "calling a nonexistent delete function must be rejected");
}

// ---------------------------------------------------------------------------
// 6. record_deliberate_abstention + get_abstention_for_request (new)
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn get_abstention_returns_none_before_recording() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0x40);
    let result: Option<Record> = conductor
        .call(&zome, "get_abstention_for_request", request_ref)
        .await;
    assert!(result.is_none(), "get_abstention_for_request should return None before any abstention is recorded");
}

#[tokio::test(flavor = "multi_thread")]
async fn record_and_retrieve_deliberate_abstention() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0x50);
    let abstention = DeliberateAbstention {
        request_ref: request_ref.clone(),
        reason: Some("Conflict of interest — co-author on a prior study with the researcher".into()),
    };

    let abstention_hash: ActionHash = conductor
        .call(&zome, "record_deliberate_abstention", abstention)
        .await;

    let record: Option<Record> = conductor
        .call(&zome, "get_abstention_for_request", request_ref)
        .await;
    assert!(record.is_some(), "recorded abstention should be retrievable by request_ref");
    assert_eq!(
        *record.unwrap().action_address(),
        abstention_hash,
        "retrieved record ActionHash must match the one returned by record_deliberate_abstention"
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn duplicate_abstention_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();

    let request_ref = fake_external_hash(0x60);
    let abstention = DeliberateAbstention {
        request_ref: request_ref.clone(),
        reason: None,
    };

    // First abstention succeeds.
    let _: ActionHash = conductor
        .call(&zome, "record_deliberate_abstention", abstention.clone())
        .await;

    // Second abstention on the same request must be rejected.
    let result: Result<ActionHash, _> = conductor
        .call_fallible(&zome, "record_deliberate_abstention", abstention)
        .await;
    assert!(result.is_err(), "recording a second abstention for the same request must fail");
}
