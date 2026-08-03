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
use valichord_shared_types::{AttestationConfidence, AttestationOutcome, DataLocalityMode, Discipline};

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
            LockResultInput { request_ref: request_ref.clone(), metrics: vec![], data_locality_mode: DataLocalityMode::Gdpr },
        )
        .await;

    let replacement = LockedResult {
        request_ref,
        metrics: vec![],
        nonce: vec![7u8; 32],
        commitment_hash: vec![7u8; 32],
        data_locality_mode: DataLocalityMode::Gdpr,
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

// ---------------------------------------------------------------------------
// LockedResult erasability — mode-dependent, and that is the design
// ---------------------------------------------------------------------------
//
// The only guard in this repo that deliberately says "it depends". Every other
// tripwire asserts an unconditional refusal; these two assert that the refusal is
// conditional on the study's DataLocalityMode, and BOTH directions are load-bearing:
//
//   Gdpr      -> delete ALLOWED. Guarding it would remove the erasure right the
//                mode exists to protect, and it buys nothing — the binding
//                commitment is ResearcherResultCommitment on DNA 3, already public
//                and immutable. Deleting a LockedResult destroys only the
//                researcher's own ability to reveal, which is the same outcome as
//                declining to reveal, which the protocol already handles.
//   OpenAudit -> delete REFUSED. That mode is a permanent, irrevocable commitment
//                to post-reveal public access; erasing the sealed material
//                afterwards contradicts the promise the mode IS.
//
// ⚠️ The Gdpr test is not a formality. Without it, a guard that simply refused
// every LockedResult delete would pass the OpenAudit test and look correct, while
// silently breaking GDPR erasure. Only the pair distinguishes "discriminates" from
// "refuses everything".

async fn lock_result_in_mode(
    conductor: &SweetConductor,
    app: &ValiChordApp,
    request_ref: ExternalHash,
    mode: DataLocalityMode,
) -> ActionHash {
    conductor
        .call(
            &app.researcher_zome(),
            "lock_researcher_result",
            LockResultInput { request_ref, metrics: vec![], data_locality_mode: mode },
        )
        .await
}

#[tokio::test(flavor = "multi_thread")]
async fn locked_result_delete_is_rejected_in_open_audit_mode() {
    let (conductor, app) = setup_single().await;
    let original = lock_result_in_mode(
        &conductor,
        &app,
        fake_external_hash(0xe1),
        DataLocalityMode::OpenAudit,
    )
    .await;

    let err = conductor
        .call_fallible::<_, ActionHash>(&app.researcher_zome(), "test_force_delete_entry", original)
        .await
        .expect_err("deleting a LockedResult in Open Audit mode must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "permanent commitment to post-reveal public access",
        "LockedResult (delete, OpenAudit)",
    );
}

#[tokio::test(flavor = "multi_thread")]
async fn locked_result_delete_is_allowed_in_gdpr_mode() {
    let (conductor, app) = setup_single().await;
    let original = lock_result_in_mode(
        &conductor,
        &app,
        fake_external_hash(0xe2),
        DataLocalityMode::Gdpr,
    )
    .await;

    let result = conductor
        .call_fallible::<_, ActionHash>(&app.researcher_zome(), "test_force_delete_entry", original)
        .await;

    assert!(
        result.is_ok(),
        "a researcher MUST be able to erase their own sealed result in GDPR mode — \
         refusing this would defeat the erasure right the mode exists to protect. \
         got: {:?}",
        result.err(),
    );
}

// ===========================================================================
// GOVERNANCE DELETE TRIPWIRES — added 2026-08-03
// ===========================================================================
//
// The three governance entry types had NO delete coverage that could fail.
// What appeared to cover them were three Tryorama tests asserting that "no
// delete function exists in the coordinator API" — an API-surface check that
// says nothing about whether the integrity zome would refuse a delete, and
// which passes identically against a DNA with no guards at all. They surfaced
// only because retiring the Tryorama suite meant reading every test in it.
//
// These matter more than most: a HarmonyRecord is the protocol's permanent
// public output. If it could be deleted it would be a retractable claim, and
// the reason for publishing one at all would be gone. Same for the badge
// derived from it and for the governance decisions that record how the
// protocol's own rules were changed.
//
// Requires the governance test build (governance_coordinator/test_utils), added
// at the same time — governance had no tripwire hooks before this.

/// Commit phase for one validator.
async fn commit(conductor: &SweetConductor, app: &ValiChordApp, request_ref: ExternalHash) {
    let _: () = conductor
        .call(
            &app.attestation_zome(),
            "notify_commitment_sealed",
            CommitmentSealedInput { request_ref, commitment_hash: vec![0u8; 32] },
        )
        .await;
}

/// Reveal phase for one validator.
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
// 11. HarmonyRecord cannot be deleted
// ---------------------------------------------------------------------------
//
// Needs a real round, because there is no other way to produce a HarmonyRecord
// — it is written by check_and_create_harmony_record once quorum is met.
#[tokio::test(flavor = "multi_thread")]
async fn harmony_record_delete_is_rejected() {
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xe1);
    let att = [&setup.alice.attestation, &setup.bob.attestation];

    let _: ActionHash = setup.conductors[0]
        .call(
            &setup.alice.attestation_zome(),
            "submit_validation_request",
            make_validation_request(request_ref.clone()),
        )
        .await;
    await_consistency_s(20, att).await.unwrap();

    commit(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    await_consistency_s(20, att).await.unwrap();
    commit(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, att).await.unwrap();

    reveal(&setup.conductors[0], &setup.alice, request_ref.clone()).await;
    reveal(&setup.conductors[1], &setup.bob, request_ref.clone()).await;
    await_consistency_s(20, att).await.unwrap();

    let harmony: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref,
        )
        .await;
    let harmony = harmony.expect("a full round must produce a HarmonyRecord to delete");

    let err = setup.conductors[0]
        .call_fallible::<_, ActionHash>(
            &setup.alice.governance_zome(),
            "test_force_delete_entry",
            harmony,
        )
        .await
        .expect_err("deleting a HarmonyRecord must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "HarmonyRecord is immutable",
        "HarmonyRecord (delete)",
    );
}

// ---------------------------------------------------------------------------
// 12. GovernanceDecision cannot be deleted
// ---------------------------------------------------------------------------
//
// Single agent: create_governance_decision is key-gated in production, but the
// test properties use the dev bypass (`system_coordinator_key: ""`), so any
// agent may write one. The delete guard is not key-gated either way.
#[tokio::test(flavor = "multi_thread")]
async fn governance_decision_delete_is_rejected() {
    let (conductor, app) = setup_single().await;
    let gov_zome = app.governance_zome();

    let decision: ActionHash = conductor
        .call(&gov_zome, "create_governance_decision", make_governance_decision())
        .await;

    let err = conductor
        .call_fallible::<_, ActionHash>(&gov_zome, "test_force_delete_entry", decision)
        .await
        .expect_err("deleting a GovernanceDecision must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "GovernanceDecision is immutable",
        "GovernanceDecision (delete)",
    );
}

// ---------------------------------------------------------------------------
// 13. ReproducibilityBadge cannot be deleted
// ---------------------------------------------------------------------------
//
// The most expensive tripwire in the file: a badge only exists as a by-product
// of a round that met a badge threshold, so it needs three validators to reach
// BronzeReproducible. There is no cheaper path — no coordinator function issues
// a badge directly, by design.
#[tokio::test(flavor = "multi_thread")]
async fn reproducibility_badge_delete_is_rejected() {
    let mut conductors =
        SweetConductorBatch::from_config_rendezvous(3, SweetConductorConfig::rendezvous(true)).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut it = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(it.next().unwrap());
    let bob   = ValiChordApp::from_sweet_app(it.next().unwrap());
    let carol = ValiChordApp::from_sweet_app(it.next().unwrap());

    let mut vr = make_validation_request(fake_external_hash(0xe3));
    vr.num_validators_required = 3;
    let request_ref = vr.data_hash.clone();
    let att = [&alice.attestation, &bob.attestation, &carol.attestation];
    let gov = [&alice.governance, &bob.governance, &carol.governance];

    let _: ActionHash = conductors[0]
        .call(&alice.attestation_zome(), "submit_validation_request", vr)
        .await;
    await_consistency_s(60, att).await.unwrap();

    for (i, app) in [(0usize, &alice), (1, &bob), (2, &carol)] {
        commit(&conductors[i], app, request_ref.clone()).await;
        await_consistency_s(60, att).await.unwrap();
    }
    for (i, app) in [(0usize, &alice), (1, &bob), (2, &carol)] {
        reveal(&conductors[i], app, request_ref.clone()).await;
        await_consistency_s(60, att).await.unwrap();
    }
    await_consistency_s(60, gov).await.unwrap();

    let harmony: Option<ActionHash> = conductors[0]
        .call(
            &alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    assert!(harmony.is_some(), "a full 3-agent round must produce a HarmonyRecord");

    // Same retry shape as the bronze badge test: the badge is issued by the call
    // above, but its indexes can lag by a gossip round on a loaded box.
    let mut badges: Vec<Record> = Vec::new();
    for _ in 0..5 {
        await_consistency_s(60, gov).await.unwrap();
        badges = conductors[0]
            .call(&alice.governance_zome(), "get_badges_for_study", request_ref.clone())
            .await;
        if !badges.is_empty() {
            break;
        }
    }
    let badge_hash = badges
        .first()
        .expect("three Reproduced attestations must issue a BronzeReproducible badge")
        .action_address()
        .clone();

    let err = conductors[0]
        .call_fallible::<_, ActionHash>(
            &alice.governance_zome(),
            "test_force_delete_entry",
            badge_hash,
        )
        .await
        .expect_err("deleting a ReproducibilityBadge must be rejected by validate()");

    assert_rejected_by_guard(
        &format!("{err:?}"),
        "ReproducibilityBadge is immutable",
        "ReproducibilityBadge (delete)",
    );
}
