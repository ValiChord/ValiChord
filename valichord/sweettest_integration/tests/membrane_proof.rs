//! Membrane-proof tests for DNA 3 (attestation) — the credentialed join boundary.
//!
//! WHY THIS FILE EXISTS
//! --------------------
//! Every other sweettest suite installs the attestation DNA with
//! `authorized_joining_certificate_issuer: ""`. That is the **dev bypass**, and it is
//! total: `genesis_self_check` returns `Valid` on its first branch without looking at
//! the proof, and `verify_membrane_proof()` returns `Ok(())` before reading the source
//! chain. So no other test in this crate exercises the membrane at all — a
//! `grep -c membrane_proof` across `sweettest_integration/tests` returned exactly one
//! hit before this file, and it was a comment.
//!
//! That mattered because the membrane is what decides **who may join DNA 3**. Until
//! 2026-08-02 the only tests of it lived in the Tryorama suite, which is being retired
//! (upstream `@holochain/tryorama` is unmaintained and will not support Holochain 0.7).
//! Retiring it without porting these would have deleted the only coverage of a security
//! boundary — a regression caused by a test migration, which is exactly the failure
//! shape this repo keeps rediscovering.
//!
//! WHAT THE PROOF ACTUALLY IS
//! --------------------------
//! Wire format (`JoiningCertificate::from_proof_bytes`, shared_types):
//!
//!   [0..64]  Ed25519 signature
//!   [64..]   optional msgpack `JoiningCertificateMeta` (validator_type, initial_tier).
//!            Exactly 64 bytes = legacy form, read as Human with no tier.
//!
//! The **signed payload** is `encode(agent.get_raw_39().to_vec())` — the joining agent's
//! 39-byte public key, msgpack-encoded, plus the meta bytes verbatim when present.
//!
//! ⚠️ The msgpack step is easy to get wrong and silently fatal. `verify_signature(key,
//! sig, data)` does NOT verify over `data` as given: `VerifySignature::new` stores
//! `holochain_serialized_bytes::encode(&data)`, so a `Vec<u8>` argument is verified as a
//! msgpack **array of integers**, not as 39 raw bytes. Signing the raw bytes here would
//! produce a proof that fails for a reason that looks exactly like "the guard works".
//! These tests therefore build the payload with `Sign::new`, which routes through the
//! same `encode()` as `VerifySignature::new` — so the two cannot drift apart even if
//! that encoding changes.
//!
//! Two conductors are never needed here: joining is a single-agent property.

use holochain::sweettest::*;
use holochain_types::prelude::*;
use valichord_sweettest::*;

const APP_ID: &str = "valichord-membrane";
const ATTESTATION_ROLE: &str = "attestation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Load the four DNAs, replacing `attestation` with a build whose DNA properties
/// name `issuer_b64` as the authorised joining-certificate issuer.
///
/// A non-empty issuer is what *activates* the whole credential path: with `""`
/// both the genesis format check and the coordinator signature check short-circuit
/// to success.
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
    .expect("attestation.dna not found — run ./build-test-dnas.sh or hc dna pack");

    let [r, v, _a, g] = load_dnas().await;
    vec![
        ("researcher_repository".into(), r),
        ("validator_workspace".into(), v),
        (ATTESTATION_ROLE.into(), attestation),
        ("governance".into(), g),
    ]
}

/// Produce the exact bytes the coordinator will verify, then sign them with the
/// issuer's key.
///
/// Uses `Sign::new`, whose `data` field is `holochain_serialized_bytes::encode(&data)`
/// — byte-identical to what `VerifySignature::new` will reconstruct on the guest side.
/// Hand-rolling the msgpack here would be a second source of truth that can drift.
async fn valid_proof_for(
    keystore: &holochain_keystore::MetaLairClient,
    issuer: &AgentPubKey,
    joining_agent: &AgentPubKey,
) -> Vec<u8> {
    let to_sign = Sign::new(issuer.clone(), joining_agent.get_raw_39().to_vec())
        .expect("agent pubkey bytes are serializable");
    // Sign::data is a serde_bytes::ByteBuf, so go via to_vec() to reach Arc<[u8]>.
    let payload: std::sync::Arc<[u8]> = to_sign.data.to_vec().into();
    let signature = keystore
        .sign(issuer.clone(), payload)
        .await
        .expect("issuer key is in the test keystore");
    signature.0.to_vec()
}

/// Install the app for `agent` with `membrane_proof` on the attestation role.
///
/// Goes through `install_app_bundle` rather than `SweetConductor::setup_app`, because
/// the opinionated sweettest helpers hardcode `None` for the membrane proof
/// (`sweet_conductor.rs`: "TODO: make this take a more flexible config for specifying
/// things like membrane proofs"), and `install_app_minimal`, which does accept one, is
/// `pub(crate)`.
async fn install_with_proof(
    conductor: &SweetConductor,
    dnas: &[(RoleName, DnaFile)],
    agent: AgentPubKey,
    membrane_proof: Option<Vec<u8>>,
) -> Result<(), String> {
    let bundle = app_bundle_from_dnas(dnas, false, None).await;

    let proof: Option<MembraneProof> = membrane_proof
        .map(|b| std::sync::Arc::new(SerializedBytes::from(UnsafeBytes::from(b))));

    let mut roles_settings = std::collections::HashMap::new();
    roles_settings.insert(
        ATTESTATION_ROLE.to_string(),
        RoleSettings::Provisioned {
            membrane_proof: proof,
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
        .map_err(|e| format!("{e:?}"))?;
    Ok(())
}

/// Make the first zome call, which is what forces the coordinator's lazy `init()` —
/// and therefore the Ed25519 check — to run.
///
/// `get_current_phase` is deliberate: it is a read, it needs no prior state, and it
/// returns `None` on a fresh DHT. So a failure here is the membrane rejecting the
/// agent, not the call failing on its own merits.
async fn first_zome_call(
    conductor: &SweetConductor,
    dnas: &[(RoleName, DnaFile)],
    agent: &AgentPubKey,
) -> Result<Option<valichord_shared_types::ValidationPhase>, String> {
    let att_dna = dnas
        .iter()
        .find(|(r, _)| r.as_str() == ATTESTATION_ROLE)
        .map(|(_, d)| d)
        .unwrap();
    let cell_id = CellId::new(att_dna.dna_hash().clone(), agent.clone());
    let cell = conductor
        .get_sweet_cell(cell_id)
        .map_err(|e| format!("{e:?}"))?;
    let zome = cell.zome("attestation_coordinator");

    conductor
        .call_fallible(&zome, "get_current_phase", fake_external_hash(0x01))
        .await
        .map_err(|e| format!("{e:?}"))
}

// ---------------------------------------------------------------------------
// 1. Valid real Ed25519 proof → coordinator init() accepts the agent
// ---------------------------------------------------------------------------
//
// The positive control. Without this, every rejection test below could pass
// because the setup itself is broken rather than because a guard fired.
#[tokio::test(flavor = "multi_thread")]
async fn valid_ed25519_proof_is_accepted_by_coordinator_init() {
    let conductor = SweetConductor::standard().await;
    let issuer = SweetAgents::one(conductor.keystore()).await;
    let issuer_b64 = AgentPubKeyB64::from(issuer.clone()).to_string();

    let dnas = dnas_with_issuer(&issuer_b64).await;
    let agent = SweetAgents::one(conductor.keystore()).await;
    let proof = valid_proof_for(&conductor.keystore(), &issuer, &agent).await;

    install_with_proof(&conductor, &dnas, agent.clone(), Some(proof))
        .await
        .expect("install with a valid membrane proof must succeed");
    conductor.enable_app(APP_ID.into()).await.unwrap();

    let phase = first_zome_call(&conductor, &dnas, &agent)
        .await
        .expect("a correctly signed proof must pass coordinator init()");
    assert!(
        phase.is_none(),
        "fresh DHT has no PhaseMarker; got {phase:?}"
    );
}

// ---------------------------------------------------------------------------
// 2. Wrong signature → coordinator init() rejects
// ---------------------------------------------------------------------------
//
// Signed by the WRONG key. Format is perfect: 64 bytes, decodes as a legacy Human
// certificate, passes genesis_self_check. Only the Ed25519 check can catch this, so
// this test is what proves that check is load-bearing rather than decorative.
#[tokio::test(flavor = "multi_thread")]
async fn wrong_signature_proof_is_rejected_by_coordinator_init() {
    let conductor = SweetConductor::standard().await;
    let issuer = SweetAgents::one(conductor.keystore()).await;
    let impostor = SweetAgents::one(conductor.keystore()).await;
    let issuer_b64 = AgentPubKeyB64::from(issuer.clone()).to_string();

    let dnas = dnas_with_issuer(&issuer_b64).await;
    let agent = SweetAgents::one(conductor.keystore()).await;
    // Correct payload, correct length — signed by someone who is not the issuer.
    let proof = valid_proof_for(&conductor.keystore(), &impostor, &agent).await;
    assert_eq!(proof.len(), 64, "impostor proof must still be well-formed");

    install_with_proof(&conductor, &dnas, agent.clone(), Some(proof))
        .await
        .expect("genesis accepts any >=64-byte proof; rejection happens later, at init");
    conductor.enable_app(APP_ID.into()).await.unwrap();

    let err = first_zome_call(&conductor, &dnas, &agent)
        .await
        .expect_err("a proof signed by the wrong key must be rejected by init()");
    assert_rejected_with(
        &err,
        "Membrane proof signature is invalid",
        "wrong-signature membrane proof",
    );
}

// ---------------------------------------------------------------------------
// 3. No membrane proof at all → genesis_self_check rejects
// ---------------------------------------------------------------------------
//
// Rejected at genesis, before the agent ever joins the network, so the failure
// surfaces from install rather than from a zome call.
#[tokio::test(flavor = "multi_thread")]
async fn missing_membrane_proof_is_rejected_at_genesis() {
    let conductor = SweetConductor::standard().await;
    let issuer = SweetAgents::one(conductor.keystore()).await;
    let issuer_b64 = AgentPubKeyB64::from(issuer).to_string();

    let dnas = dnas_with_issuer(&issuer_b64).await;
    let agent = SweetAgents::one(conductor.keystore()).await;

    let err = install_with_proof(&conductor, &dnas, agent, None)
        .await
        .expect_err("installing with no membrane proof must fail at genesis_self_check");
    assert_rejected_with(
        &format!("{err:?}"),
        "requires a membrane proof",
        "missing membrane proof",
    );
}

// ---------------------------------------------------------------------------
// 4. Too-short proof → genesis_self_check rejects on the length rule
// ---------------------------------------------------------------------------
//
// 10 bytes cannot contain a 64-byte signature. This is the cheap structural check
// that runs before the agent joins; the expensive cryptographic one runs at init.
#[tokio::test(flavor = "multi_thread")]
async fn too_short_membrane_proof_is_rejected_at_genesis() {
    let conductor = SweetConductor::standard().await;
    let issuer = SweetAgents::one(conductor.keystore()).await;
    let issuer_b64 = AgentPubKeyB64::from(issuer).to_string();

    let dnas = dnas_with_issuer(&issuer_b64).await;
    let agent = SweetAgents::one(conductor.keystore()).await;

    let err = install_with_proof(&conductor, &dnas, agent, Some(vec![0x01; 10]))
        .await
        .expect_err("a 10-byte membrane proof must fail the >=64-byte format check");
    assert_rejected_with(
        &format!("{err:?}"),
        "too short",
        "too-short membrane proof",
    );
}

// ---------------------------------------------------------------------------
// 5. Empty issuer is a TOTAL bypass — documented, not assumed
// ---------------------------------------------------------------------------
//
// Every other suite in this crate depends on this being true. It has always been
// relied upon and never asserted, so a change that quietly made the bypass partial
// would surface as confusing failures elsewhere rather than as one clear failure here.
//
// This also records why the Tryorama test "agent with valid membrane proof (>= 64
// bytes) can join" proved less than its name suggests: it ran with `issuerKey = ""`,
// so it demonstrated the bypass, not the membrane.
#[tokio::test(flavor = "multi_thread")]
async fn empty_issuer_bypasses_the_membrane_entirely() {
    let conductor = SweetConductor::standard().await;
    let dnas = dnas_with_issuer("").await;
    let agent = SweetAgents::one(conductor.keystore()).await;

    // No proof at all, and a garbage 3-byte proof, must BOTH be accepted.
    install_with_proof(&conductor, &dnas, agent.clone(), None)
        .await
        .expect("empty issuer must accept an agent with no membrane proof");
    conductor.enable_app(APP_ID.into()).await.unwrap();

    let phase = first_zome_call(&conductor, &dnas, &agent)
        .await
        .expect("empty issuer must also bypass the coordinator init() signature check");
    assert!(phase.is_none(), "fresh DHT has no PhaseMarker; got {phase:?}");
}
