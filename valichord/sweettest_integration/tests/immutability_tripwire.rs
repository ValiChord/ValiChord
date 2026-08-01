//! IMMUTABILITY TRIPWIRE TESTS
//!
//! These prove that the *integrity zomes* reject forbidden updates AND deletes.
//! They are the only tests in this repo that do so.
//!
//! Delete coverage was added 2026-08-01; before that the delete guards had none
//! that could fail. See the DELETE TRIPWIRES section at the foot of this file.
//!
//! ## Why they exist
//!
//! Immutability in ValiChord is enforced by **Rust match-arm ordering** inside
//! each integrity zome's `validate()`: the per-type guard arms must precede the
//! generic `OpUpdate::Entry { action, .. }` arm and the `RegisterUpdate(_)`
//! catch-all (see `docs/7_ValiChord_4-DNA_architecture_technical.md:325`).
//!
//! Reordering those arms during a refactor — for instance the Holochain 0.7
//! `FlatOp` rename, which touches all 51 of them — **silently disables
//! immutability**. There is no compile error and no test failure, because
//! nothing else in the suite ever attempts a forbidden update.
//!
//! ## Why they need a special build
//!
//! No production coordinator exposes `update_entry`, so a forbidden update
//! cannot be issued from a test at all. Three coordinators therefore carry
//! `#[cfg(feature = "test_utils")]` externs that do exactly one thing: issue an
//! Update against a committed entry. They are absent from every production
//! build. Run:
//!
//! ```text
//! ./build-test-dnas.sh
//! cd sweettest_integration
//! VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire
//! ```
//!
//! The integrity zomes in those bundles are the *same bytes* as production —
//! only the coordinators differ — so what is under test is what ships.
//!
//! ## The assertion discipline that matters
//!
//! Three earlier "immutability" tests were deleted on 2026-07-30 because they
//! asserted only `result.is_err()` against zome functions that **did not
//! exist**. They passed on "function not found" and would have stayed green
//! with `validate()` deleted entirely.
//!
//! Every test here asserts on the **specific rejection message emitted by the
//! guard**. A missing extern, a wrong-reason rejection, or a silently accepted
//! update all fail. Never weaken these to a bare `is_err()`.
//!
//! ## Coverage, and why it is shaped this way
//!
//! Verified against shipped `hdi 0.8.0` (`src/op.rs`): a **private** entry can
//! never surface as `OpUpdate::Entry`; it only ever arrives as
//! `OpUpdate::PrivateEntry`. So:
//!
//! * **attestation** (public entries) — per-type guard arms are live, and arm
//!   ordering genuinely matters. Tested per type.
//! * **validator_workspace / researcher_repository** (all entries private) —
//!   the per-type arms are unreachable dead code and immutability rests on a
//!   *single* blanket `OpUpdate::PrivateEntry { .. }` arm per DNA. Ordering is
//!   irrelevant, but losing that one arm removes immutability from every
//!   private entry at once. One tripwire each, aimed at that arm.

use valichord_sweettest::*;
use attestation_integrity::StudyClaim;
use researcher_repository_coordinator::LockResultInput;
use researcher_repository_integrity::LockedResult;
use validator_workspace_coordinator::SealAttestationInput;
use validator_workspace_integrity::ValidatorPrivateAttestation;
use valichord_shared_types::{AttestationConfidence, AttestationOutcome, Discipline};

// ---------------------------------------------------------------------------
// Assertion helper — the load-bearing part of this file
// ---------------------------------------------------------------------------

/// Assert an update attempt was rejected *by the immutability guard*, named by
/// the exact message that guard emits.
///
/// Deliberately strict. It is not enough that the call failed:
///   * a missing tripwire extern (DNA built without `--features test_utils`)
///     fails with a build hint rather than passing;
///   * a rejection for any other reason fails, because the guard's own message
///     must appear.
fn assert_rejected_by_guard(err_dbg: &str, expected_fragment: &str, what: &str) {
    let looks_missing = err_dbg.contains("not found")
        || err_dbg.contains("NotFound")
        || err_dbg.contains("Unresolved");
    assert!(
        !looks_missing,
        "{what}: the tripwire extern is missing from the loaded DNA.\n\
         These tests need the test-feature build:\n  \
         ./build-test-dnas.sh\n  \
         VALICHORD_DNA_DIR=../workdir-test cargo test --test immutability_tripwire\n\
         raw error: {err_dbg}"
    );
    assert!(
        err_dbg.contains(expected_fragment),
        "{what}: the update was rejected, but NOT by the immutability guard.\n  \
         expected the guard message to contain: {expected_fragment:?}\n  \
         raw error: {err_dbg}\n\
         If the guard arm was reordered behind the generic update arm, this is \
         exactly how that failure looks."
    );
}

// ---------------------------------------------------------------------------
// attestation DNA — public entries, per-type guards, ordering matters
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn validation_request_update_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0xa1);

    let original: ActionHash = conductor
        .call(&zome, "submit_validation_request", make_validation_request(request_ref.clone()))
        .await;

    let err = conductor
        .call_fallible::<_, ActionHash>(
            &zome,
            "test_force_update_validation_request",
            (original, make_validation_request(request_ref)),
        )
        .await
        .expect_err("updating a ValidationRequest must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "ValidationRequest is immutable",
        "ValidationRequest",
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn validation_attestation_update_is_rejected() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xa2);
    let att = [&setup.alice.attestation, &setup.bob.attestation];

    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    // Both validators commit so the round reaches RevealOpen.
    for (i, app) in [(0usize, &setup.alice), (1usize, &setup.bob)] {
        let _: () = setup.conductors[i]
            .call(
                &app.attestation_zome(),
                "notify_commitment_sealed",
                CommitmentSealedInput {
                    request_ref: request_ref.clone(),
                    commitment_hash: vec![0u8; 32],
                },
            )
            .await;
        await_consistency_s(20, att).await.unwrap();
    }

    let original: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref.clone()),
                nonce: vec![], // empty nonce = dev bypass, skips hash verification
            },
        )
        .await;

    let err = setup.conductors[0]
        .call_fallible::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "test_force_update_validation_attestation",
            (original, make_validation_attestation(request_ref)),
        )
        .await
        .expect_err("updating a ValidationAttestation must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "ValidationAttestation is immutable",
        "ValidationAttestation",
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn study_claim_update_is_rejected() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xa3);
    let att = [&setup.alice.attestation, &setup.bob.attestation];

    let request_hash: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    let original: Option<ActionHash> = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref.clone())
        .await;
    let original = original.expect("claim_study should return the StudyClaim ActionHash");

    let err = setup.conductors[1]
        .call_fallible::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "test_force_update_study_claim",
            (
                original,
                StudyClaim {
                    request_ref,
                    validation_request_hash: request_hash,
                    validator_institution: "Independent".to_string(),
                },
            ),
        )
        .await
        .expect_err("updating a StudyClaim must be rejected by validate()");

    assert_rejected_by_guard(&format!("{err:?}"), "StudyClaim is immutable", "StudyClaim");
}

// ---------------------------------------------------------------------------
// validator_workspace DNA — all private; ONE blanket arm is the whole guard
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn validator_private_attestation_update_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();
    let request_ref = fake_external_hash(0xb1);

    let task_hash: ActionHash = conductor
        .call(&zome, "receive_task", make_task(request_ref.clone()))
        .await;

    let original: ActionHash = conductor
        .call(
            &zome,
            "seal_private_attestation",
            SealAttestationInput {
                task_hash,
                attestation: make_validation_attestation(request_ref.clone()),
            },
        )
        .await;

    let replacement = ValidatorPrivateAttestation {
        request_ref,
        outcome: AttestationOutcome::Reproduced,
        outcome_summary: make_outcome_summary(),
        time_invested_secs: 1,
        time_breakdown: make_time_breakdown(),
        deviation_flags: vec![],
        computational_resources: make_computational_resources(),
        confidence: AttestationConfidence::High,
        discipline: Discipline::ComputationalBiology,
        nonce: vec![9u8; 32],
        commitment_hash: vec![9u8; 32],
        reproduction_bundle_hash: None,
    };

    let err = conductor
        .call_fallible::<_, ActionHash>(
            &zome,
            "test_force_update_private_attestation",
            (original, replacement),
        )
        .await
        .expect_err("updating a ValidatorPrivateAttestation must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "Private entry updates not supported",
        "ValidatorPrivateAttestation (blanket PrivateEntry arm)",
    );
}

// ---------------------------------------------------------------------------
// researcher_repository DNA — all private; ONE blanket arm is the whole guard
// ---------------------------------------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn locked_result_update_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();
    let request_ref = fake_external_hash(0xc1);

    let original: ActionHash = conductor
        .call(
            &zome,
            "lock_researcher_result",
            LockResultInput { request_ref: request_ref.clone(), metrics: vec![] },
        )
        .await;

    let replacement = LockedResult {
        request_ref,
        metrics: vec![],
        nonce: vec![7u8; 32],
        commitment_hash: vec![7u8; 32],
    };

    let err = conductor
        .call_fallible::<_, ActionHash>(&zome, "test_force_update_locked_result", (original, replacement))
        .await
        .expect_err("updating a LockedResult must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "Private entry updates not supported",
        "LockedResult (blanket PrivateEntry arm)",
    );
}

// ===========================================================================
// DELETE TRIPWIRES
// ===========================================================================
//
// Added 2026-08-01. Until then the delete guards had NO working coverage at
// all — 16 "… cannot be deleted" guards across the integrity zomes and not one
// test that could fail if they were removed.
//
// What looked like coverage was six Tryorama tests and two sweettests calling
// functions that were never written (`delete_commitment_for_test`,
// `delete_phase_marker_for_test`, `delete_protocol_for_test`) and asserting a
// bare "did it error?". They passed on "function not found" — the same defect
// found in the update tests on 2026-07-30, which was fixed there and missed
// here. A delete needs no payload, which is exactly why the fakes looked
// plausible: there was no struct to get wrong.
//
// Consequence worth stating plainly: the 0.7 migration reflowed four
// `RegisterDelete` → `Delete` arms with no runtime net that could have caught a
// mistake. The arm-order checker covered them mechanically, but "the arms are
// in the right order" and "the guard actually rejects a delete" are different
// claims, and only the first was ever demonstrated.
//
// ── Deletes are shaped differently from updates ────────────────────────────
//
// The update guards depend on entry visibility (a private entry can only ever
// surface as `OpUpdate::PrivateEntry`). Deletes do not: every `FlatOp::Delete`
// arm fetches the *original record* via `must_get_valid_record` and
// deserialises it to discriminate by type. So per-type delete guards are live
// in all three DNAs, including the private ones — the dead-code caveat that
// applies to the private DNAs' update arms does NOT apply here.
//
// ⚠️ KNOWN GAP, deliberately not covered by a test below: `LockedResult`
// (researcher_repository) has NO delete guard. Its DNA guards only
// `PreRegisteredProtocol`, so a LockedResult delete falls through to the
// "only the original author may delete" check — which the researcher passes,
// being the author. It is update-guarded but not delete-guarded, unlike every
// analogous sealed entry in the other DNAs. Not obviously exploitable (the
// commitment hash is already immutable on DNA 3, so deleting the local copy
// destroys only the researcher's own ability to reveal, which the protocol
// already handles as an abandoned round) — but it is an asymmetry, and anyone
// reading `locked_result_update_is_rejected` would reasonably assume deletes
// were blocked too. Flagged rather than silently encoded either way.

// The delete tests reuse `assert_rejected_by_guard` unchanged. Its
// "function not found" check is exactly what these need — the delete hook takes
// only an `ActionHash`, so an absent or typo'd extern produces precisely the
// error the fake tests mistook for proof. A separate wrapper was written here
// and removed: it added nothing, and its doc comment claimed a check it did not
// perform, which is the same disease as the tests this section replaces.

// --- attestation DNA — public entries --------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn validation_request_delete_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.attestation_zome();
    let request_ref = fake_external_hash(0xd1);

    let original: ActionHash = conductor
        .call(&zome, "submit_validation_request", make_validation_request(request_ref))
        .await;

    let err = conductor
        .call_fallible::<_, ActionHash>(&zome, "test_force_delete_entry", original)
        .await
        .expect_err("deleting a ValidationRequest must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "ValidationRequest is immutable",
        "ValidationRequest (delete)",
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn validation_attestation_delete_is_rejected() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xd2);
    let att = [&setup.alice.attestation, &setup.bob.attestation];

    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    let _: () = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "notify_commitment_sealed",
            CommitmentSealedInput {
                request_ref: request_ref.clone(),
                commitment_hash: vec![0u8; 32],
            },
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    let original: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_attestation",
            RevealInput {
                attestation: make_validation_attestation(request_ref),
                nonce: vec![], // empty nonce = dev bypass, skips hash verification
            },
        )
        .await;

    let err = setup.conductors[0]
        .call_fallible::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "test_force_delete_entry",
            original,
        )
        .await
        .expect_err("deleting a ValidationAttestation must be rejected by validate()");

    // The permanent public verdict. If this one ever passes, the record the
    // whole protocol exists to make tamper-evident can be erased by its author.
    assert_rejected_by_guard(
        &format!("{err:?}"),
        "ValidationAttestation is immutable",
        "ValidationAttestation (delete)",
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn study_claim_delete_is_rejected() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xd3);
    let att = [&setup.alice.attestation, &setup.bob.attestation];

    setup.conductors[0]
        .call::<_, ActionHash>(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    setup.conductors[1]
        .call::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "publish_validator_profile",
            make_validator_profile("Independent"),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    let original: Option<ActionHash> = setup.conductors[1]
        .call(&setup.bob.attestation_zome(), "claim_study", request_ref)
        .await;
    let original = original.expect("claim_study should return the StudyClaim ActionHash");

    let err = setup.conductors[1]
        .call_fallible::<_, ActionHash>(
            &setup.bob.attestation_zome(),
            "test_force_delete_entry",
            original,
        )
        .await
        .expect_err("deleting a StudyClaim must be rejected by validate()");

    // Claims are vacated via StudyClaimRelease, never deleted — otherwise a
    // validator could quietly un-claim a study they had already seen.
    assert_rejected_by_guard(
        &format!("{err:?}"),
        "StudyClaim is immutable",
        "StudyClaim (delete)",
    );
}

// --- validator_workspace DNA — private, and per-type guards ARE live here ---

#[tokio::test(flavor = "multi_thread")]
async fn validator_private_attestation_delete_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.validator_zome();
    let request_ref = fake_external_hash(0xd4);

    let task_hash: ActionHash = conductor
        .call(&zome, "receive_task", make_task(request_ref.clone()))
        .await;
    let original: ActionHash = conductor
        .call(
            &zome,
            "seal_private_attestation",
            SealAttestationInput {
                task_hash,
                attestation: make_validation_attestation(request_ref),
            },
        )
        .await;

    let err = conductor
        .call_fallible::<_, ActionHash>(&zome, "test_force_delete_entry", original)
        .await
        .expect_err("deleting a ValidatorPrivateAttestation must be rejected by validate()");

    // The sealed commit-reveal verdict. Deletable would mean a validator could
    // destroy their commitment after seeing others' reveals.
    assert_rejected_by_guard(
        &format!("{err:?}"),
        "ValidatorPrivateAttestation is immutable",
        "ValidatorPrivateAttestation (delete)",
    );
}

// --- researcher_repository DNA ---------------------------------------------

#[tokio::test(flavor = "multi_thread")]
async fn pre_registered_protocol_delete_is_rejected() {
    let (conductor, app) = setup_single().await;
    let zome = app.researcher_zome();

    let study_hash: ActionHash = conductor.call(&zome, "register_study", make_study()).await;
    let original: ActionHash = conductor
        .call(
            &zome,
            "register_protocol",
            researcher_repository_coordinator::RegisterProtocolInput {
                study_ref: study_hash,
                protocol: make_protocol(),
            },
        )
        .await;

    let err = conductor
        .call_fallible::<_, ActionHash>(&zome, "test_force_delete_entry", original)
        .await
        .expect_err("deleting a PreRegisteredProtocol must be rejected by validate()");

    // This is the ONLY delete guard in this DNA — see the LockedResult gap
    // noted at the top of this section.
    assert_rejected_by_guard(
        &format!("{err:?}"),
        "PreRegisteredProtocol is immutable",
        "PreRegisteredProtocol (delete)",
    );
}
