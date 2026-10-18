//! REVEAL-PHASE TRIPWIRE — issues #51 and #53, added 2026-10-19
//!
//! #51: peers accepted a RevealOpen PhaseMarker from any validator who had
//! committed, even if the rest of the cohort had not. A PhaseMarker now lists
//! every committed validator's CommitmentAnchor, and validate() requires at least
//! `num_validators_required` distinct validators among them.
//!
//! #53: a ResearcherReveal had no creation rule. It now names its ValidationRequest
//! and the researcher's own ResearcherResultCommitment, and validate() checks both
//! (plus, on a credentialed network, that the revealer authored both).
//!
//! The honest coordinator never writes a short marker or a reveal pointing at the
//! wrong entries, so the forged ones are written through `test_force_create_*`
//! hooks (attestation_coordinator, `--features test_utils`) — standing in for a
//! modified app. Run with the tripwire bundles:
//!
//! ```text
//! ./build-test-dnas.sh
//! cd sweettest_integration
//! VALICHORD_DNA_DIR=../workdir-test cargo test --test reveal_phase_forgery -- --test-threads=1
//! ```
//!
//! Dev-bypass network (empty issuer): the #51 cohort check and the #53 entry checks
//! apply there too; only #53's author checks are credentialed-only, so they are not
//! exercised here. #52 (the coordinator's phase check in submit_attestation) is
//! likewise credentialed-only and not exercised by this file.

use valichord_sweettest::*;
use attestation_integrity::{PhaseMarker, ResearcherReveal, ResearcherRevealInput};
use valichord_shared_types::ValidationPhase;

fn assert_refused(err_dbg: &str, expected_fragment: &str, what: &str) {
    let looks_missing = err_dbg.contains("not found")
        || err_dbg.contains("NotFound")
        || err_dbg.contains("Unresolved");
    assert!(
        !looks_missing,
        "{what}: a test_force_* hook is missing — build the test bundles \
         (./build-test-dnas.sh) and set VALICHORD_DNA_DIR=../workdir-test.\nraw error: {err_dbg}"
    );
    assert!(
        err_dbg.contains(expected_fragment),
        "{what}: refused, but NOT by the check this step targets.\n  \
         expected: {expected_fragment:?}\n  raw error: {err_dbg}"
    );
}

async fn commit(conductor: &SweetConductor, app: &ValiChordApp, request_ref: ExternalHash) {
    let _: () = conductor
        .call(
            &app.attestation_zome(),
            "notify_commitment_sealed",
            CommitmentSealedInput { request_ref, commitment_hash: vec![0u8; 32] },
        )
        .await;
}

#[tokio::test(flavor = "multi_thread")]
async fn forged_reveal_phase_entries_are_refused_by_validate() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xd1);
    let att = [&setup.alice.attestation, &setup.bob.attestation];
    let c0 = &setup.conductors[0];
    let zome = setup.alice.attestation_zome();

    // The study asks for 2 validators (make_validation_request).
    let _: ActionHash = c0
        .call(&zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;
    await_consistency_s(20, att).await.unwrap();

    // Only Alice commits.
    commit(c0, &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, att).await.unwrap();
    let anchors: Vec<ActionHash> = c0
        .call(&zome, "get_commitment_anchor_hashes", request_ref.clone())
        .await;
    assert_eq!(anchors.len(), 1, "one validator has committed");
    let alice_anchor = anchors[0].clone();

    let force_marker = |m: PhaseMarker| {
        let zome = setup.alice.attestation_zome();
        async move {
            c0.call_fallible::<_, ActionHash>(&zome, "test_force_create_phase_marker", m)
                .await
                .map_err(|e| format!("{e:?}"))
        }
    };

    // ── #51-1: RevealOpen with 1 of 2 committed ──────────────────────────────
    let short = PhaseMarker {
        request_ref:              request_ref.clone(),
        phase:                    ValidationPhase::RevealOpen,
        commitment_anchor_hash:   alice_anchor.clone(),
        commitment_anchor_hashes: vec![alice_anchor.clone()],
    };
    assert_refused(
        &force_marker(short).await.expect_err("an early RevealOpen must be refused"),
        "needs commitments from 2 distinct validators; it lists 1",
        "RevealOpen before the cohort committed",
    );

    // ── #51-2: padding the list with the same validator's anchor twice ───────
    let padded = PhaseMarker {
        request_ref:              request_ref.clone(),
        phase:                    ValidationPhase::RevealOpen,
        commitment_anchor_hash:   alice_anchor.clone(),
        commitment_anchor_hashes: vec![alice_anchor.clone(), alice_anchor.clone()],
    };
    assert_refused(
        &force_marker(padded).await.expect_err("a padded list must be refused"),
        "needs commitments from 2 distinct validators; it lists 1",
        "RevealOpen padded with one validator's anchor",
    );

    // ── #51 positive control: Bob commits; the coordinator's own marker passes ──
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(30, att).await.unwrap();
    let phase: Option<ValidationPhase> = c0
        .call(&zome, "get_current_phase", request_ref.clone())
        .await;
    assert_eq!(
        phase,
        Some(ValidationPhase::RevealOpen),
        "positive control: a marker listing the whole cohort must be accepted"
    );

    // ── #53 ─────────────────────────────────────────────────────────────────
    let request_record: Option<Record> = c0
        .call(&zome, "get_validation_request_for_data_hash", request_ref.clone())
        .await;
    let request_hash = request_record.expect("request exists").action_address().clone();

    let force_reveal = |r: ResearcherReveal| {
        let zome = setup.alice.attestation_zome();
        async move {
            c0.call_fallible::<_, ActionHash>(&zome, "test_force_create_researcher_reveal", r)
                .await
                .map_err(|e| format!("{e:?}"))
        }
    };

    // #53-1: a reveal that points at something other than a researcher commitment.
    let no_commitment = ResearcherReveal {
        request_ref:                request_ref.clone(),
        metrics:                    vec![],
        validation_request_hash:    request_hash.clone(),
        researcher_commitment_hash: alice_anchor.clone(), // a CommitmentAnchor, not a ResearcherResultCommitment
    };
    assert_refused(
        &force_reveal(no_commitment).await.expect_err("a reveal without a commitment must be refused"),
        "does not point to a ResearcherResultCommitment",
        "reveal pointing at a non-commitment",
    );

    // A genuine researcher commitment, so the next variants reach the later checks.
    let commitment_hash: ActionHash = c0
        .call(
            &zome,
            "publish_researcher_commitment",
            ResearcherCommitmentInput { request_ref: request_ref.clone(), result_commitment_hash: vec![7u8; 32] },
        )
        .await;

    // #53-2: a reveal naming something other than the ValidationRequest.
    let wrong_request = ResearcherReveal {
        request_ref:                request_ref.clone(),
        metrics:                    vec![],
        validation_request_hash:    alice_anchor.clone(),
        researcher_commitment_hash: commitment_hash.clone(),
    };
    assert_refused(
        &force_reveal(wrong_request).await.expect_err("a reveal naming a non-request must be refused"),
        "does not point to a ValidationRequest",
        "reveal pointing at a non-request",
    );

    // #53 positive control: the honest reveal path (dev bypass: empty nonce skips
    // only the hash check) writes a reveal that passes the new rules.
    let _: ActionHash = c0
        .call(
            &zome,
            "reveal_researcher_result",
            ResearcherRevealInput { request_ref: request_ref.clone(), metrics: vec![], nonce: vec![] },
        )
        .await;
}
