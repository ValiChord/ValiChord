//! SUPERSESSION TRIPWIRE — protocol-backlog 01, added 2026-10-19
//!
//! ## What this protects
//!
//! A `Supersession` links a newer HarmonyRecord to an older one. Ceri's decision
//! (2026-10-19): the researcher, or any validator from either round, may make the
//! link; the entry records the role they made it in, and **every peer checks that
//! role is true** (`governance_integrity::check_supersession`). Neither record
//! changes, and the link can never be deleted.
//!
//! The researcher's role is proved without a cross-DNA call: the entry carries the
//! signed `Create` action of their ValidationRequest (never the entry, which holds
//! the membrane-protected `deposit_token`), and its hash must equal the
//! `request_action_hash` the validators stated under their own signatures.
//!
//! ## Why this needs the test build
//!
//! `supersede_harmony_record` only ever attaches the caller's own genuine proof, so
//! a forged role or proof reaches `validate()` only through
//! `test_force_create_supersession` (`--features test_utils`) — standing in for a
//! node running a modified coordinator. Run with the tripwire bundles:
//!
//! ```text
//! ./build-test-dnas.sh
//! cd sweettest_integration
//! VALICHORD_DNA_DIR=../workdir-test cargo test --test supersession_forgery -- --test-threads=1
//! ```
//!
//! ## Shape
//!
//! Three agents. Alice makes both requests and validates; Bob validates; Carol takes
//! no part. Two genuine rounds, then: the production path for both roles (positive
//! controls, and the read path in both directions), the hook's own positive control,
//! then one targeted forgery per check, each refused with that check's message.
//!
//! ## Not covered
//!
//! * Whether the two rounds are about related work. The protocol does not judge
//!   that; the link is the maker's statement, made under a checked role.

use valichord_sweettest::*;
use governance_coordinator::{SupersedeInput, SupersessionsOf};
use governance_integrity::{
    HarmonyRecord, RequestAuthorship, Supersession, SupersessionReason, SupersessionRole,
};
use serde::{Deserialize, Serialize};

/// Mirror of the test-only `ForceLinkInput` (cfg-gated in the coordinator, so not
/// importable from a normal dependency build).
#[derive(Serialize, Deserialize, Debug)]
struct ForceLinkInput {
    base:        ActionHash,
    target:      ActionHash,
    superseding: bool,
}

fn assert_refused(err_dbg: &str, expected_fragment: &str, what: &str) {
    let looks_missing = err_dbg.contains("not found")
        || err_dbg.contains("NotFound")
        || err_dbg.contains("Unresolved");
    assert!(
        err_dbg.contains(expected_fragment),
        "{what}: refused, but NOT by the check this variant targets.\n  \
         expected: {expected_fragment:?}\n  raw error: {err_dbg}{}",
        if looks_missing {
            "\n  (looks like a missing hook — build with ./build-test-dnas.sh and \
             VALICHORD_DNA_DIR=../workdir-test)"
        } else {
            ""
        }
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
                nonce: vec![], // dev bypass
            },
        )
        .await;
}

#[tokio::test(flavor = "multi_thread")]
async fn forged_supersessions_are_refused_by_validate() {
    let mut conductors =
        SweetConductorBatch::from_config_rendezvous(3, SweetConductorConfig::rendezvous(true)).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut it = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(it.next().unwrap());
    let bob = ValiChordApp::from_sweet_app(it.next().unwrap());
    let carol = ValiChordApp::from_sweet_app(it.next().unwrap());
    let att = [&alice.attestation, &bob.attestation, &carol.attestation];
    let gov = [&alice.governance, &bob.governance, &carol.governance];

    // ── Two genuine rounds; Alice is the researcher of both ───────────────────────
    let mut round = |byte: u8| {
        let (conductors, alice, bob) = (&conductors, &alice, &bob);
        async move {
            let request_ref = fake_external_hash(byte);
            let _: ActionHash = conductors[0]
                .call(
                    &alice.attestation_zome(),
                    "submit_validation_request",
                    make_validation_request(request_ref.clone()),
                )
                .await;
            await_consistency_s(60, att).await.unwrap();
            commit(&conductors[0], alice, request_ref.clone()).await;
            await_consistency_s(60, att).await.unwrap();
            commit(&conductors[1], bob, request_ref.clone()).await;
            await_consistency_s(60, att).await.unwrap();
            reveal(&conductors[0], alice, request_ref.clone()).await;
            reveal(&conductors[1], bob, request_ref.clone()).await;
            await_consistency_s(60, att).await.unwrap();
            let hr: Option<ActionHash> = conductors[0]
                .call(&alice.governance_zome(), "check_and_create_harmony_record", request_ref)
                .await;
            hr.expect("a full round must produce a HarmonyRecord")
        }
    };
    let old = round(0xe1).await;
    let new = round(0xe2).await;
    await_consistency_s(60, gov).await.unwrap();

    // The genuine researcher proof: Alice's own signed ValidationRequest action for
    // the OLD round, located by the hash its validators stated.
    let old_rec: Option<Record> = conductors[0]
        .call(&alice.governance_zome(), "get_harmony_record_by_hash", old.clone())
        .await;
    let old_hr: HarmonyRecord = old_rec.unwrap().entry().to_app_option().unwrap().unwrap();
    let request_hash = old_hr.attestation_evidence[0]
        .attestation
        .request_action_hash
        .clone()
        .expect("submit_attestation stamps the request's action hash");
    let req_rec: Option<Record> = conductors[0]
        .call(&alice.attestation_zome(), "get_validation_request", request_hash)
        .await;
    let req_rec = req_rec.expect("Alice's request is readable");
    let proof = RequestAuthorship {
        action:    req_rec.action().clone(),
        signature: req_rec.signature().clone(),
    };
    // One of Alice's OTHER signed Create actions: her own attestation in the old round.
    let alice_key = alice.attestation.agent_pubkey().clone();
    let alice_attestation_action = old_hr
        .attestation_evidence
        .iter()
        .find(|ev| ev.action.author() == &alice_key)
        .expect("Alice validated the old round")
        .action
        .clone();

    // ── 0a/0b. POSITIVE CONTROLS — the production path, both roles ────────────────
    let by_researcher: ActionHash = conductors[0]
        .call(
            &alice.governance_zome(),
            "supersede_harmony_record",
            SupersedeInput {
                superseded:  old.clone(),
                superseding: new.clone(),
                reason:      SupersessionReason::NewAttempt,
                asserted_as: SupersessionRole::Researcher,
            },
        )
        .await;
    let _by_validator: ActionHash = conductors[1]
        .call(
            &bob.governance_zome(),
            "supersede_harmony_record",
            SupersedeInput {
                superseded:  old.clone(),
                superseding: new.clone(),
                reason:      SupersessionReason::ReportedProcessError,
                asserted_as: SupersessionRole::Validator,
            },
        )
        .await;
    await_consistency_s(60, gov).await.unwrap();

    // ── 0c. The read path, from an agent who took no part, in both directions ─────
    let from_old: SupersessionsOf = conductors[2]
        .call(&carol.governance_zome(), "get_supersessions", old.clone())
        .await;
    let from_new: SupersessionsOf = conductors[2]
        .call(&carol.governance_zome(), "get_supersessions", new.clone())
        .await;
    assert_eq!(from_old.superseded_by.len(), 2, "the old record's readers see both links");
    assert!(from_old.supersedes.is_empty());
    assert_eq!(from_new.supersedes.len(), 2, "the new record's readers see both links");
    assert!(from_new.superseded_by.is_empty());

    // ── 9. Production path refuses a non-researcher claiming the role ─────────────
    let err = conductors[2]
        .call_fallible::<_, ActionHash>(
            &carol.governance_zome(),
            "supersede_harmony_record",
            SupersedeInput {
                superseded:  old.clone(),
                superseding: new.clone(),
                reason:      SupersessionReason::NewAttempt,
                asserted_as: SupersessionRole::Researcher,
            },
        )
        .await
        .expect_err("Carol made neither request");
    assert_refused(&format!("{err:?}"), "you did not make the ValidationRequest", "carol as researcher (API)");

    // ── Forgeries through the hook ────────────────────────────────────────────────
    let force = |who: usize, s: Supersession| {
        let conductor = &conductors[who];
        let zome = [&alice, &bob, &carol][who].governance_zome();
        async move {
            conductor
                .call_fallible::<_, ActionHash>(&zome, "test_force_create_supersession", s)
                .await
                .map_err(|e| format!("{e:?}"))
        }
    };
    let genuine = Supersession {
        superseded:       old.clone(),
        superseding:      new.clone(),
        reason:           SupersessionReason::NewAttempt,
        asserted_as:      SupersessionRole::Researcher,
        researcher_proof: Some(proof.clone()),
    };

    // ── 0d. Hook positive control: the genuine entry passes unchanged ─────────────
    force(0, genuine.clone())
        .await
        .expect("positive control: a genuine researcher Supersession must pass validate()");

    // ── 1. An outsider claiming to be a validator ─────────────────────────────────
    let s = Supersession {
        asserted_as: SupersessionRole::Validator,
        researcher_proof: None,
        ..genuine.clone()
    };
    assert_refused(
        &force(2, s).await.expect_err("Carol validated neither round"),
        "must be by a validator listed in one of the two records",
        "outsider as validator",
    );

    // ── 2. An outsider presenting the researcher's genuine proof ──────────────────
    assert_refused(
        &force(2, genuine.clone()).await.expect_err("Alice's proof is not Carol's"),
        "proof is for a request made by someone else",
        "outsider replaying the researcher's proof",
    );

    // ── 3. The researcher's proof with a corrupted signature ──────────────────────
    let mut s = genuine.clone();
    s.researcher_proof.as_mut().unwrap().signature.0[0] ^= 0xff;
    assert_refused(
        &force(0, s).await.expect_err("a corrupted signature must be refused"),
        "researcher proof signature is invalid",
        "corrupted proof signature",
    );

    // ── 4. A genuine signed action of the researcher — but not the request ───────
    let mut s = genuine.clone();
    let sig = old_hr
        .attestation_evidence
        .iter()
        .find(|ev| ev.action.author() == &alice_key)
        .unwrap()
        .signature
        .clone();
    s.researcher_proof = Some(RequestAuthorship { action: alice_attestation_action, signature: sig });
    assert_refused(
        &force(0, s).await.expect_err("an unrelated signed action must be refused"),
        "is not the ValidationRequest behind either record",
        "wrong signed action as proof",
    );

    // ── 5. Researcher role with no proof ──────────────────────────────────────────
    let s = Supersession { researcher_proof: None, ..genuine.clone() };
    assert_refused(
        &force(0, s).await.expect_err("the researcher role needs its proof"),
        "must carry the signed ValidationRequest action",
        "researcher without proof",
    );

    // ── 6. Validator role carrying a researcher proof ─────────────────────────────
    let s = Supersession { asserted_as: SupersessionRole::Validator, ..genuine.clone() };
    assert_refused(
        &force(1, s).await.expect_err("a validator link must not carry a proof"),
        "must not carry a researcher proof",
        "validator with proof",
    );

    // ── 7. A record superseding itself ────────────────────────────────────────────
    let s = Supersession { superseding: old.clone(), ..genuine.clone() };
    assert_refused(
        &force(0, s).await.expect_err("self-supersession must be refused"),
        "cannot supersede itself",
        "self-supersession",
    );

    // ── 8. Older and newer swapped ────────────────────────────────────────────────
    let s = Supersession { superseded: new.clone(), superseding: old.clone(), ..genuine.clone() };
    assert_refused(
        &force(0, s).await.expect_err("an older record cannot supersede a newer one"),
        "must have been written after the record it supersedes",
        "reversed order",
    );

    // ── 10. Index links pointing at the wrong record ──────────────────────────────
    let link = |who: usize, input: ForceLinkInput| {
        let conductor = &conductors[who];
        let zome = [&alice, &bob, &carol][who].governance_zome();
        async move {
            conductor
                .call_fallible::<_, ActionHash>(&zome, "test_force_create_supersession_link", input)
                .await
                .map_err(|e| format!("{e:?}"))
        }
    };
    // SupersededBy must be based on the OLD record.
    assert_refused(
        &link(0, ForceLinkInput { base: new.clone(), target: by_researcher.clone(), superseding: false })
            .await
            .expect_err("a SupersededBy link on the newer record must be refused"),
        "does not name in that position",
        "index link on the wrong record",
    );
    // Only the Supersession's author may index it.
    assert_refused(
        &link(2, ForceLinkInput { base: old.clone(), target: by_researcher.clone(), superseding: false })
            .await
            .expect_err("Carol cannot index Alice's Supersession"),
        "Only the author of a Supersession may index it",
        "index link by someone else",
    );

    // ── 11. A Supersession can never be deleted ───────────────────────────────────
    let err = conductors[0]
        .call_fallible::<_, ActionHash>(&alice.governance_zome(), "test_force_delete_entry", by_researcher)
        .await
        .expect_err("a Supersession must not be deletable, even by its author");
    assert_refused(&format!("{err:?}"), "Supersession is immutable — cannot be deleted", "delete");
}
