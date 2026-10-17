//! VALIDATOR TIER TRIPWIRE — issue #8, added 2026-10-17
//!
//! ## What was wrong
//!
//! `ValidatorProfile.certification_tier` was whatever the caller wrote:
//! `publish_validator_profile` takes the whole profile, and no validate() rule
//! covered profiles at all. Any validator could call themselves Certified. And the
//! tier an issuer granted an AI validator in its joining certificate was never read
//! anywhere — every AI validator sat at Provisional.
//!
//! ## What changed
//!
//! The profile carries its author's joining certificate, and attestation_integrity's
//! validate() — on creates AND updates — checks it is a genuine certificate issued to
//! that author (`check_joining_certificate`, the membrane check from #37) and that
//! `certification_tier` is exactly what it grants (`JoiningCertificate::granted_tier`).
//! `publish_validator_profile` fills both in, so honest callers need not.
//!
//! ## Why this needs the test build
//!
//! The honest coordinator overwrites the tier, so a forged one cannot reach
//! validate() through the production API. `test_force_create_validator_profile` and
//! `test_force_update_validator_profile` write the entry directly — standing in for a
//! modified coordinator. Run with the tripwire bundles:
//!
//! ```text
//! ./build-test-dnas.sh
//! cd sweettest_integration
//! VALICHORD_DNA_DIR=../workdir-test cargo test --test validator_tier_forgery -- --test-threads=1
//! ```
//!
//! ## Shape
//!
//! One credentialed AI validator, granted Advanced by the issuer. Step 0 is the
//! positive control (the honest path yields Advanced even though the caller asked for
//! Standard); every later step is one forgery, refused with its own message.

use valichord_sweettest::*;
use attestation_integrity::ValidatorProfile;
use valichord_shared_types::{
    CertificationTier, JoiningCertificate, ValidatorCertification, ValidatorType,
};

const APP_ID: &str = "valichord-tier";
const ATTESTATION_ROLE: &str = "attestation";

fn assert_refused(err_dbg: &str, expected_fragment: &str, what: &str) {
    let looks_missing = err_dbg.contains("not found")
        || err_dbg.contains("NotFound")
        || err_dbg.contains("Unresolved");
    assert!(
        !looks_missing,
        "{what}: a test_force_* hook is missing from the loaded DNA — build the test \
         bundles (./build-test-dnas.sh) and set VALICHORD_DNA_DIR=../workdir-test.\n\
         raw error: {err_dbg}"
    );
    assert!(
        err_dbg.contains(expected_fragment),
        "{what}: refused, but NOT by the check this step targets.\n  \
         expected: {expected_fragment:?}\n  raw error: {err_dbg}"
    );
}

/// Same as membrane_proof.rs: the four DNAs, attestation with `issuer_b64` as the
/// authorised issuer (which switches the credential system on).
async fn dnas_with_issuer(issuer_b64: &str) -> Vec<(RoleName, DnaFile)> {
    let attestation = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("attestation.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(
                yaml_serde::from_str(&format!(
                    "authorized_joining_certificate_issuer: \"{issuer_b64}\"\n\
                     ai_validator_issuer: \"\"\n\
                     discipline: genomics\n\
                     minimum_validators: 2\n\
                     min_claim_timeout_secs: 0\n"
                ))
                .expect("issuer properties are valid YAML"),
            )),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("attestation.dna not found — run ./build-test-dnas.sh");

    let [r, v, _a, g] = load_dnas().await;
    vec![
        ("researcher_repository".into(), r),
        ("validator_workspace".into(), v),
        (ATTESTATION_ROLE.into(), attestation),
        ("governance".into(), g),
    ]
}

/// An AI joining certificate for `agent`, signed by `issuer`, granting `tier`.
///
/// Wire format: signature (64) || meta. Signed payload: encode(agent_raw_39 || meta),
/// built with `Sign::new` so the msgpack step matches `verify_signature` exactly
/// (see the header of membrane_proof.rs for why that matters).
async fn ai_certificate(
    keystore: &holochain_keystore::MetaLairClient,
    issuer: &AgentPubKey,
    agent: &AgentPubKey,
    tier: CertificationTier,
) -> Vec<u8> {
    let meta = JoiningCertificate::meta_bytes(ValidatorType::AI, Some(tier)).unwrap();
    let mut payload = agent.get_raw_39().to_vec();
    payload.extend_from_slice(&meta);
    let to_sign = Sign::new(issuer.clone(), payload).expect("payload serialises");
    let data: std::sync::Arc<[u8]> = to_sign.data.to_vec().into();
    let signature = keystore.sign(issuer.clone(), data).await.expect("issuer key in keystore");
    let mut proof = signature.0.to_vec();
    proof.extend_from_slice(&meta);
    proof
}

fn as_membrane_proof(bytes: Vec<u8>) -> MembraneProof {
    std::sync::Arc::new(SerializedBytes::from(UnsafeBytes::from(bytes)))
}

async fn install(
    conductor: &SweetConductor,
    dnas: &[(RoleName, DnaFile)],
    agent: AgentPubKey,
    proof: Vec<u8>,
) {
    let bundle = app_bundle_from_dnas(dnas, false, None).await;
    let mut roles_settings = std::collections::HashMap::new();
    roles_settings.insert(
        ATTESTATION_ROLE.to_string(),
        RoleSettings::Provisioned {
            membrane_proof: Some(as_membrane_proof(proof)),
            modifiers: None,
            init_properties: None,
        },
    );
    conductor
        .raw_handle()
        .install_app_bundle(InstallAppPayload {
            source: AppBundleSource::Bytes(bundle.pack().unwrap().into()),
            agent_key: Some(agent),
            installed_app_id: Some(APP_ID.into()),
            network_seed: None,
            roles_settings: Some(roles_settings),
            ignore_genesis_failure: false,
            restore_from_dht: false,
        })
        .await
        .expect("install with a valid AI certificate must succeed");
    conductor.enable_app(APP_ID.into()).await.unwrap();
}

#[tokio::test(flavor = "multi_thread")]
async fn forged_validator_tiers_are_refused_by_validate() {
    let conductor = SweetConductor::standard().await;
    let keystore = conductor.keystore();
    let issuer = SweetAgents::one(keystore.clone()).await;
    let issuer_b64 = AgentPubKeyB64::from(issuer.clone()).to_string();
    let dnas = dnas_with_issuer(&issuer_b64).await;

    let agent = SweetAgents::one(keystore.clone()).await;
    let own_cert = ai_certificate(&keystore, &issuer, &agent, CertificationTier::Advanced).await;
    install(&conductor, &dnas, agent.clone(), own_cert.clone()).await;

    let att_dna = &dnas.iter().find(|(r, _)| r.as_str() == ATTESTATION_ROLE).unwrap().1;
    let zome = conductor
        .get_sweet_cell(CellId::new(att_dna.dna_hash().clone(), agent.clone()))
        .unwrap()
        .zome("attestation_coordinator");

    let (zome_ref, conductor_ref) = (&zome, &conductor);
    let force_create = |p: ValidatorProfile| async move {
        {
            conductor_ref
                .call_fallible::<_, ActionHash>(zome_ref, "test_force_create_validator_profile", p)
                .await
                .map_err(|e| format!("{e:?}"))
        }
    };

    // ── 0. POSITIVE CONTROL — the honest path yields the issuer's tier ────────────
    // The caller asks for Standard; the certificate grants Advanced; Advanced wins.
    let honest: ActionHash = conductor
        .call(&zome, "publish_validator_profile", make_validator_profile("Tier Lab"))
        .await;
    let certification: Option<ValidatorCertification> = conductor
        .call(&zome, "get_validator_certification", agent.clone())
        .await;
    assert_eq!(
        certification,
        Some(ValidatorCertification {
            validator_type: ValidatorType::AI,
            tier: CertificationTier::Advanced,
        }),
        "the profile must carry the certificate's type and tier, not the caller's",
    );

    // A correctly-formed profile written through the hook must ALSO pass — otherwise
    // every refusal below could be the hook failing for some unrelated reason.
    let mut genuine = make_validator_profile("Tier Lab");
    genuine.certification_tier = CertificationTier::Advanced;
    genuine.joining_certificate = Some(as_membrane_proof(own_cert.clone()));
    force_create(genuine.clone())
        .await
        .expect("positive control: a profile matching its certificate must pass validate()");

    // ── 1. Self-promoted tier, genuine certificate ───────────────────────────────
    let mut p = genuine.clone();
    p.certification_tier = CertificationTier::Certified;
    assert_refused(
        &force_create(p).await.expect_err("a tier above the certificate's must be refused"),
        "certification_tier must be the tier its joining certificate grants",
        "self-promoted tier",
    );

    // ── 2. A certificate issued to SOMEONE ELSE ──────────────────────────────────
    let other = SweetAgents::one(keystore.clone()).await;
    let borrowed = ai_certificate(&keystore, &issuer, &other, CertificationTier::Certified).await;
    let mut p = genuine.clone();
    p.certification_tier = CertificationTier::Certified;
    p.joining_certificate = Some(as_membrane_proof(borrowed));
    assert_refused(
        &force_create(p).await.expect_err("a borrowed certificate must be refused"),
        "Membrane proof signature is invalid",
        "certificate issued to another agent",
    );

    // ── 3. No certificate at all ─────────────────────────────────────────────────
    let mut p = genuine.clone();
    p.joining_certificate = None;
    assert_refused(
        &force_create(p).await.expect_err("a profile without a certificate must be refused"),
        "requires a membrane proof",
        "missing certificate",
    );

    // ── 4. The EDIT path — forging the tier by updating an honest profile ────────
    // The generic update arm checks authorship only. If the ValidatorProfile update
    // arm were missing or ordered after it, this would succeed.
    let mut p = genuine.clone();
    p.certification_tier = CertificationTier::Certified;
    let err = conductor
        .call_fallible::<_, ActionHash>(&zome, "test_force_update_validator_profile", (honest, p))
        .await
        .map(|_| ())
        .map_err(|e| format!("{e:?}"))
        .expect_err("editing in a forged tier must be refused");
    assert_refused(
        &err,
        "certification_tier must be the tier its joining certificate grants",
        "forged tier via update",
    );
}
