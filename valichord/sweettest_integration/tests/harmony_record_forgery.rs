//! HARMONYRECORD FORGERY TRIPWIRE — issue #11, added 2026-10-17
//!
//! ## What was wrong
//!
//! A HarmonyRecord's `validate()` checked only that its author listed themselves in
//! `participating_validators`, that no key appeared twice, and that the count was in
//! range — with `validators_requested` also written by the author. Nothing required
//! the OTHER listed keys to have taken part. So one agent running a modified
//! coordinator could list six real, unrelated keys and publish a record whose count
//! passes the Gold ceiling, with any outcome they liked.
//!
//! ## What changed
//!
//! The record now carries each validator's own signed action creating their
//! `ValidationAttestation`, and `check_attestation_evidence` (governance_integrity)
//! verifies every signature, that each carried attestation hashes to the entry its
//! validator signed, that each is for this request, and that the record's outcome,
//! agreement level, duration and discipline are what those attestations produce.
//!
//! ## Why this needs the test build
//!
//! The production coordinator always attaches genuine evidence, so a forged record
//! cannot reach `validate()` through the production API. `test_force_create_harmony_record`
//! (governance_coordinator, `--features test_utils`) writes a caller-supplied record
//! directly — standing in for the modified coordinator #11 describes. Run with the
//! tripwire bundles:
//!
//! ```text
//! ./build-test-dnas.sh
//! cd sweettest_integration
//! VALICHORD_DNA_DIR=../workdir-test cargo test --test harmony_record_forgery -- --test-threads=1
//! ```
//!
//! ## Shape
//!
//! ONE genuine round, then every variant against it, in sequence. Each variant is a
//! single targeted change to the genuine record and must be refused with the
//! specific message of the check it targets — never a bare `is_err()`.
//!
//! The FIRST step is the positive control: the untouched genuine record, re-submitted
//! through the same hook, must be ACCEPTED. Without it, every rejection below could be
//! the hook failing for an unrelated reason. It also proves the evidence round-trips:
//! the attestations are decoded from DNA 3 and re-hashed here, so if re-serialisation
//! were not byte-identical, honest records would fail — and this step would catch it.
//!
//! Variants 8 and 9 (added the same day) cover cherry-picking: a genuine SUBSET of
//! the round, either passed off as a smaller complete round or honestly labelled
//! but published before the round timeout.
//!
//! ## What these tests do NOT cover — see `check_attestation_evidence`
//!
//! * Choosing a subset AFTER the round has timed out. Permitted by design (that is
//!   force-finalisation); the record still says "k of n".
//! * Validators who collude by each signing a genuine but false attestation.

use valichord_sweettest::*;
use governance_integrity::HarmonyRecord;
use valichord_shared_types::{AgreementLevel, AttestationOutcome};

/// Same discipline as `immutability_tripwire.rs`: the call must fail, it must not be
/// because the hook is missing, and the guard's own message must appear.
fn assert_refused(err_dbg: &str, expected_fragment: &str, what: &str) {
    let looks_missing = err_dbg.contains("not found")
        || err_dbg.contains("NotFound")
        || err_dbg.contains("Unresolved");
    assert!(
        !looks_missing,
        "{what}: test_force_create_harmony_record is missing from the loaded DNA.\n\
         Build the test bundles first:\n  ./build-test-dnas.sh\n  \
         VALICHORD_DNA_DIR=../workdir-test cargo test --test harmony_record_forgery\n\
         raw error: {err_dbg}"
    );
    assert!(
        err_dbg.contains(expected_fragment),
        "{what}: the forged record was refused, but NOT by the check this variant \
         targets.\n  expected: {expected_fragment:?}\n  raw error: {err_dbg}"
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

#[tokio::test(flavor = "multi_thread")]
async fn forged_harmony_records_are_refused_by_validate() {
    // ── One genuine two-validator round (same steps as immutability_tripwire #11) ──
    let setup = setup_two_agents().await;
    let request_ref = fake_external_hash(0xf1);
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

    let written: Option<ActionHash> = setup.conductors[0]
        .call(
            &setup.alice.governance_zome(),
            "check_and_create_harmony_record",
            request_ref.clone(),
        )
        .await;
    written.expect("a full round must produce a genuine HarmonyRecord");

    let record: Option<Record> = setup.conductors[0]
        .call(&setup.alice.governance_zome(), "get_harmony_record", request_ref.clone())
        .await;
    let genuine: HarmonyRecord = record
        .expect("the genuine HarmonyRecord must be readable")
        .entry()
        .to_app_option()
        .expect("HarmonyRecord decodes")
        .expect("HarmonyRecord carries its entry");

    assert_eq!(genuine.participating_validators.len(), 2, "two validators took part");
    assert_eq!(
        genuine.attestation_evidence.len(),
        2,
        "the honest coordinator must attach one signed attestation per validator"
    );

    // Alice is a participant, so the "author must be listed" rule never fires — every
    // refusal below comes from the evidence check, which is what is under test.
    let force = |r: HarmonyRecord| {
        let conductor = &setup.conductors[0];
        let zome = setup.alice.governance_zome();
        async move {
            conductor
                .call_fallible::<_, ActionHash>(&zome, "test_force_create_harmony_record", r)
                .await
                .map_err(|e| format!("{e:?}"))
        }
    };

    // ── 0. POSITIVE CONTROL — the untouched genuine record is accepted ────────────
    force(genuine.clone())
        .await
        .expect("positive control: the genuine record must pass validate() unchanged");

    // ── 1. THE #11 ATTACK — validators listed with no attestation behind them ─────
    let mut r = genuine.clone();
    r.attestation_evidence.clear();
    assert_refused(
        &force(r).await.expect_err("a record with no evidence must be refused"),
        "must carry one signed attestation per participating validator",
        "no evidence",
    );

    // ── 2. Evidence attributed to the wrong validator ────────────────────────────
    let mut r = genuine.clone();
    r.attestation_evidence.swap(0, 1);
    assert_refused(
        &force(r).await.expect_err("evidence out of order must be refused"),
        "but participating_validators[0] is",
        "evidence attributed to the wrong validator",
    );

    // ── 3. Forged signature ──────────────────────────────────────────────────────
    let mut r = genuine.clone();
    r.attestation_evidence[0].signature.0[0] ^= 0xff;
    assert_refused(
        &force(r).await.expect_err("a corrupted signature must be refused"),
        "signature is invalid",
        "forged signature",
    );

    // ── 4. Attestation content altered after the validator signed it ─────────────
    let mut r = genuine.clone();
    r.attestation_evidence[0].attestation.time_invested_secs += 1;
    assert_refused(
        &force(r).await.expect_err("an altered attestation must be refused"),
        "content does not match the attestation the validator signed",
        "altered attestation content",
    );

    // ── 5. Outcome the attestations do not support ───────────────────────────────
    let mut r = genuine.clone();
    r.outcome = AttestationOutcome::FailedToReproduce {
        details: "Majority failed to reproduce".into(),
    };
    assert_refused(
        &force(r).await.expect_err("an unsupported outcome must be refused"),
        "outcome does not match the majority of its signed attestations",
        "unsupported outcome",
    );

    // ── 6. Agreement level the attestations do not support ───────────────────────
    let mut r = genuine.clone();
    r.agreement_level = AgreementLevel::Divergent;
    assert_refused(
        &force(r).await.expect_err("an unsupported agreement level must be refused"),
        "agreement_level does not match its signed attestations",
        "unsupported agreement level",
    );

    // ── 7. Genuine attestations re-used for a different study ────────────────────
    let mut r = genuine.clone();
    r.request_ref = fake_external_hash(0xf2);
    assert_refused(
        &force(r).await.expect_err("evidence from another request must be refused"),
        "is for a different request",
        "attestations re-used for a different request",
    );

    // ── Cherry-picking: a genuine SUBSET of the round ────────────────────────────
    // Keep only Alice (index 0 after the coordinator's key sort may be either agent;
    // what matters is that one genuine, correctly signed attestation remains).
    // `min_attestations_for_finalization` is 0 in the test properties, so the
    // pre-existing minimum check passes and the refusal must come from the new
    // completeness check. The request asked for 2 (make_validation_request).
    let subset = |mut r: HarmonyRecord| {
        let keep = r
            .participating_validators
            .iter()
            .position(|v| v == setup.alice.attestation.agent_pubkey())
            .expect("Alice took part");
        r.participating_validators = vec![r.participating_validators[keep].clone()];
        r.validator_types = vec![r.validator_types[keep].clone()];
        r.attestation_evidence = vec![r.attestation_evidence[keep].clone()];
        r
    };

    // ── 8. ...passed off as a smaller COMPLETE round ("1 of 1") ──────────────────
    let mut r = subset(genuine.clone());
    r.validators_requested = 1;
    assert_refused(
        &force(r).await.expect_err("a subset claiming to be complete must be refused"),
        "validators_requested is 1 but its signed attestations say the study asked for 2",
        "subset passed off as a complete round",
    );

    // ── 9. ...honestly labelled "1 of 2", but before the round has timed out ─────
    // round_timeout_secs is 86400 in governance_yaml_props, and the request is
    // seconds old, so this must be refused. A record like this is legitimate only
    // after the timeout — the same rule force_finalize_round applies.
    let r = subset(genuine.clone());
    assert_refused(
        &force(r).await.expect_err("an incomplete round before the timeout must be refused"),
        "carries 1 of 2 requested attestations before the round timeout",
        "incomplete round finalised early",
    );
}
