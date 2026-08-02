//! Shared helpers for ValiChord Sweettest integration tests.
//!
//! # DNA order contract
//! `load_dnas()` returns: `[researcher_repository, validator_workspace, attestation, governance]`
//! `setup_valichord()` exposes a `ValiChordApp` whose fields match that order.

use std::path::{Path, PathBuf};

use attestation_integrity::{ValidatorAgentType, ValidationRequest, ValidationTier};
pub use valichord_shared_types::{CommitmentSealedInput, ResearcherCommitmentInput};
use governance_integrity::GovernanceDecision;
use researcher_repository_integrity::{
    PreRegisteredProtocol, ResearchStudy, VerifiedDataSnapshot,
};
use validator_workspace_integrity::{
    CompensationTier, ValidationFocus, ValidationTask,
};
use valichord_shared_types::{
    AgreementLevel, AttestationConfidence, AttestationOutcome, ComputationalResources,
    CertificationTier, Discipline, OutcomeSummary, Severity, TimeBreakdown,
    UndeclaredDeviation,
};
pub use valichord_shared_types::ValidationAttestation;

// Re-export commonly used types so tests only need `use valichord_sweettest::*`
pub use attestation_coordinator::AttestationRevealInput as RevealInput;
pub use attestation_integrity::{StudyClaim, ValidatorProfile};
pub use holochain::prelude::*;
pub use holochain::sweettest::*;

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

/// Directory the packed `.dna` bundles are loaded from.
///
/// Defaults to `valichord/workdir` (the production pack target). Set
/// `VALICHORD_DNA_DIR` to point at an alternative set — used by
/// `build-test-dnas.sh`, which packs DNAs whose coordinators are built with
/// `--features test_utils` so the immutability tripwire tests can issue a
/// forbidden update. The integrity zomes in those bundles are the *same
/// bytes* as production; only the coordinators differ.
pub fn workdir() -> PathBuf {
    match std::env::var("VALICHORD_DNA_DIR") {
        Ok(d) if !d.trim().is_empty() => PathBuf::from(d),
        _ => Path::new(env!("CARGO_MANIFEST_DIR")).join("../workdir"),
    }
}

pub fn dna_path(name: &str) -> PathBuf {
    workdir().join(name)
}

// ---------------------------------------------------------------------------
// DNA loading with test properties
// ---------------------------------------------------------------------------

/// Attestation DNA properties for tests (issuer key = "" → full dev bypass).
fn attestation_yaml_props() -> yaml_serde::Value {
    yaml_serde::from_str(
        "minimum_validators: 2\n\
         discipline: computational_biology\n\
         authorized_joining_certificate_issuer: \"\"\n\
         min_claim_timeout_secs: 0\n",
    )
    .unwrap()
}

/// Governance DNA properties for tests (system_coordinator_key = "" → dev bypass).
/// round_timeout_secs: 0 bypasses the clock constraint in force_finalize_round.
/// Governance DNA properties for ordinary tests.
///
/// ⚠️ `round_timeout_secs` is deliberately LARGE, and changing it back to 0 will
/// reintroduce an intermittent failure that took three sessions to diagnose.
///
/// `init()` in the governance coordinator calls `schedule("sweep_timed_out_rounds")`,
/// which fires **hourly on the wall clock** (`"0 0 * * * * *"`) on *every* conductor
/// and calls `force_finalize_round` for every pending study. That function finalises
/// a round when BOTH:
///
///   * `attestation_records.len() >= min_required`, where
///     `min_required = if min_attestations_for_finalization == 0 { 1 } else { .. }`
///     — so a `0` here means **one attestation is enough**; and
///   * `elapsed_secs >= round_timeout_secs` — so a `0` here means **always**.
///
/// With both at 0, any multi-validator test whose round is still in progress when the
/// clock crosses the top of an hour has that round force-finalised early, with only
/// the attestations that happen to have arrived. A HarmonyRecord is immutable, so the
/// late validators can never be added: `participating_validators` is permanently short
/// and the badge tier is permanently wrong.
///
/// That is what produced `gold_badge_issued_with_seven_validators`'s
/// `left: 5, right: 7` on 2026-08-02 — the test ran 16:31→17:02 and straddled
/// 17:00:00 — and it is the same shape as the earlier `left: 6, right: 7`. It also
/// explains why the failure moved between tests, why docs-only commits flipped it
/// (they shift start times), and why widening retry windows never helped: the record
/// already existed and could not be rewritten.
///
/// The safe configuration is the default; tests that are *about* force-finalisation
/// opt into the dangerous one via [`governance_yaml_props_instant_timeout`].
fn governance_yaml_props() -> yaml_serde::Value {
    yaml_serde::from_str(
        "system_coordinator_key: \"\"\n\
         min_attestations_for_finalization: 0\n\
         round_timeout_secs: 86400\n",
    )
    .unwrap()
}

/// Governance properties with `round_timeout_secs: 0` — force-finalisation fires
/// immediately.
///
/// Only for tests that are specifically exercising `force_finalize_round`. Any test
/// running a full multi-validator round must NOT use this: see the warning on
/// [`governance_yaml_props`].
fn governance_yaml_props_instant_timeout() -> yaml_serde::Value {
    yaml_serde::from_str(
        "system_coordinator_key: \"\"\n\
         min_attestations_for_finalization: 0\n\
         round_timeout_secs: 0\n",
    )
    .unwrap()
}

/// Load all four DNAs with test-mode properties applied.
///
/// Returns `(researcher_repository, validator_workspace, attestation, governance)`.
pub async fn load_dnas() -> [DnaFile; 4] {
    let researcher = SweetDnaFile::from_bundle(&dna_path("researcher_repository.dna"))
        .await
        .expect("researcher_repository.dna not found — run hc dna pack first");

    let validator = SweetDnaFile::from_bundle(&dna_path("validator_workspace.dna"))
        .await
        .expect("validator_workspace.dna not found");

    let attestation = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("attestation.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(attestation_yaml_props())),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("attestation.dna not found");

    let governance = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("governance.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(governance_yaml_props())),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("governance.dna not found");

    [researcher, validator, attestation, governance]
}

/// The four role names, in the same order as `load_dnas()`.
pub fn role_names() -> [RoleName; 4] {
    [
        "researcher_repository".into(),
        "validator_workspace".into(),
        "attestation".into(),
        "governance".into(),
    ]
}

/// Build `[(RoleName, DnaFile); 4]` ready to pass to `conductor.setup_app()`.
pub async fn dnas_with_roles() -> [(RoleName, DnaFile); 4] {
    let [r, v, a, g] = load_dnas().await;
    let [rn, vn, an, gn] = role_names();
    [(rn, r), (vn, v), (an, a), (gn, g)]
}

// ---------------------------------------------------------------------------
// Per-agent app wrapper
// ---------------------------------------------------------------------------

/// Cells for one installed ValiChord app, named by role.
pub struct ValiChordApp {
    pub researcher: SweetCell,
    pub validator:  SweetCell,
    pub attestation: SweetCell,
    pub governance: SweetCell,
}

impl ValiChordApp {
    pub fn from_sweet_app(app: SweetApp) -> Self {
        let mut cells = app.into_cells();
        // cells are in installation order: researcher, validator, attestation, governance
        assert_eq!(cells.len(), 4, "expected 4 cells in ValiChord app");
        let governance  = cells.remove(3);
        let attestation = cells.remove(2);
        let validator   = cells.remove(1);
        let researcher  = cells.remove(0);
        ValiChordApp { researcher, validator, attestation, governance }
    }

    pub fn researcher_zome(&self) -> SweetZome {
        self.researcher.zome("researcher_repository_coordinator")
    }
    pub fn validator_zome(&self) -> SweetZome {
        self.validator.zome("validator_workspace_coordinator")
    }
    pub fn attestation_zome(&self) -> SweetZome {
        self.attestation.zome("attestation_coordinator")
    }
    pub fn governance_zome(&self) -> SweetZome {
        self.governance.zome("governance_coordinator")
    }
}

// ---------------------------------------------------------------------------
// Single-conductor setup
// ---------------------------------------------------------------------------

/// Spin up one conductor with one ValiChord app installed.
pub async fn setup_single() -> (SweetConductor, ValiChordApp) {
    let mut conductor = SweetConductor::standard().await;
    let dnas = dnas_with_roles().await;
    let app = conductor.setup_app("valichord", &dnas).await.unwrap();
    let vc = ValiChordApp::from_sweet_app(app);
    (conductor, vc)
}

/// Spin up one conductor with governance DNA configured to use a non-matching
/// `system_coordinator_key`.  Used to verify GovernanceDecision authorship
/// enforcement: any write attempt from this conductor must be rejected.
pub async fn setup_single_locked_governance() -> (SweetConductor, ValiChordApp) {
    let governance_locked = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("governance.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(yaml_serde::from_str(
                "system_coordinator_key: \"not-a-real-key\"\n\
                 min_attestations_for_finalization: 0\n\
                 round_timeout_secs: 0\n",
            ).unwrap())),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("governance.dna not found");

    let [r, v, a, _g] = load_dnas().await;
    let dnas: [(RoleName, DnaFile); 4] = [
        ("researcher_repository".into(), r),
        ("validator_workspace".into(),   v),
        ("attestation".into(),           a),
        ("governance".into(),            governance_locked),
    ];
    let mut conductor = SweetConductor::standard().await;
    let app = conductor.setup_app("valichord", &dnas).await.unwrap();
    let vc = ValiChordApp::from_sweet_app(app);
    (conductor, vc)
}

// ---------------------------------------------------------------------------
// Multi-conductor setup (for DHT sync tests)
// ---------------------------------------------------------------------------

pub struct TwoAgentSetup {
    pub conductors: SweetConductorBatch,
    pub alice: ValiChordApp,
    pub bob: ValiChordApp,
}

/// Spin up two conductors with rendezvous, each with their own ValiChord app.
pub async fn setup_two_agents() -> TwoAgentSetup {
    setup_two_agents_with_governance(governance_yaml_props()).await
}

/// Two agents whose governance DNA has `round_timeout_secs: 0`, so
/// `force_finalize_round` finalises immediately.
///
/// ⚠️ Only for tests *about* force-finalisation. In this configuration the hourly
/// `sweep_timed_out_rounds` can finalise any in-flight round with a single
/// attestation — see the warning on `governance_yaml_props`.
pub async fn setup_two_agents_instant_timeout() -> TwoAgentSetup {
    setup_two_agents_with_governance(governance_yaml_props_instant_timeout()).await
}

async fn setup_two_agents_with_governance(props: yaml_serde::Value) -> TwoAgentSetup {
    let mut conductors = SweetConductorBatch::from_config_rendezvous(2, SweetConductorConfig::rendezvous(true)).await;
    let governance = SweetDnaFile::from_bundle_with_overrides(
        &dna_path("governance.dna"),
        DnaModifiersOpt {
            properties: Some(YamlProperties::new(props)),
            ..DnaModifiersOpt::none()
        },
    )
    .await
    .expect("governance.dna not found");

    let [r, v, a, _g] = load_dnas().await;
    let [rn, vn, an, gn] = role_names();
    let dnas: [(RoleName, DnaFile); 4] = [(rn, r), (vn, v), (an, a), (gn, governance)];

    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut app_iter = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(app_iter.next().unwrap());
    let bob   = ValiChordApp::from_sweet_app(app_iter.next().unwrap());
    TwoAgentSetup { conductors, alice, bob }
}

// ---------------------------------------------------------------------------
// Rejection assertions
// ---------------------------------------------------------------------------

/// Assert that an error came from a **specific** guard, naming the message that
/// guard emits.
///
/// Use this instead of `assert!(result.is_err())`. A bare `is_err()` passes
/// whenever the call fails *for any reason at all* — a renamed zome function, a
/// serde mismatch on the payload, a different guard firing earlier in the same
/// function. It cannot distinguish "the protection I am testing worked" from
/// "something unrelated broke", which is the whole point of the test.
///
/// That is not a hypothetical here. Three tests in this repo were deleted on
/// 2026-07-30 and eight more on 2026-08-01 because they asserted `is_err()`
/// against zome functions that had never been written: every one passed on
/// *"function not found"* while claiming to prove a guard rejected something.
/// See `CLAUDE.md` → "Assertion discipline".
///
/// On mismatch this prints the actual error, and adds a hint when the failure
/// looks like a missing function rather than a rejection. The hint is only
/// consulted *after* the fragment check fails, so guards whose own wording
/// legitimately contains "not found" (`"ValidationRequest not found — cannot
/// verify researcher identity"`, `"StudyClaim record not found"`) still pass
/// normally.
pub fn assert_rejected_with(err_dbg: &str, expected_fragment: &str, what: &str) {
    if err_dbg.contains(expected_fragment) {
        return;
    }
    let hint = if err_dbg.contains("Unresolved")
        || err_dbg.contains("not found in this zome")
        || err_dbg.contains("FunctionNotFound")
    {
        "\n  NOTE: this looks like the zome function is MISSING, not like a guard \
         rejection. A test that passes on this proves nothing."
    } else {
        ""
    };
    panic!(
        "{what}: expected rejection from the guard emitting {expected_fragment:?}, \
         but got a different error.\n  actual: {err_dbg}{hint}"
    );
}

// ---------------------------------------------------------------------------
// Hash helpers
// ---------------------------------------------------------------------------

/// Build an ExternalHash from 32 bytes all set to `byte`.
/// Uses `from_raw_32` which computes the correct 4-byte DHT location.
pub fn fake_external_hash(byte: u8) -> ExternalHash {
    ExternalHash::from_raw_32(vec![byte; 32])
}

/// Build an ActionHash from 32 bytes all set to `byte`.
pub fn fake_action_hash(byte: u8) -> ActionHash {
    ActionHash::from_raw_32(vec![byte; 32])
}

// ---------------------------------------------------------------------------
// Fixture builders — DNA 1 (researcher_repository)
// ---------------------------------------------------------------------------

pub fn make_study() -> ResearchStudy {
    ResearchStudy {
        title: "Replication of Smith et al. 2023".into(),
        discipline: Discipline::ComputationalBiology,
        institution: "Open Science Lab".into(),
        abstract_text: "Full computational reproduction attempt.".into(),
        pre_registration_ref: None,
    }
}

pub fn make_protocol() -> PreRegisteredProtocol {
    PreRegisteredProtocol {
        analysis_plan: "Run the provided R scripts in order.".into(),
        hypotheses: vec!["H1: Effect size > 0.3".into(), "H2: p < 0.05".into()],
        statistical_methods: "Linear mixed-effects model with REML.".into(),
    }
}

pub fn make_snapshot(data_hash: ExternalHash) -> VerifiedDataSnapshot {
    VerifiedDataSnapshot {
        data_hash,
        file_count: 12,
        total_size_bytes: 524_288_000,
    }
}

pub fn make_undeclared_deviation() -> UndeclaredDeviation {
    use valichord_shared_types::{DeviationType, EpistemicImpact};
    UndeclaredDeviation {
        deviation_type: DeviationType::DataAccess {
            reason: "Original dataset behind paywall.".into(),
            impact: EpistemicImpact::Minimal,
        },
        severity: Severity::Minor,
        evidence: "Used OSF replication package v2.1.".into(),
    }
}

// ---------------------------------------------------------------------------
// Fixture builders — DNA 2 (validator_workspace)
// ---------------------------------------------------------------------------

pub fn make_task(request_ref: ExternalHash) -> ValidationTask {
    ValidationTask {
        request_ref,
        discipline: Discipline::ComputationalBiology,
        deadline_secs: 1_700_100_000,
        validation_focus: ValidationFocus::ComputationalReproducibility,
        time_cap_secs: 86_400,
        compensation_tier: CompensationTier::Tier1 { amount_pence: 5_000 },
    }
}

pub fn make_outcome_summary() -> OutcomeSummary {
    OutcomeSummary {
        key_metrics: vec![],
        effect_direction_matches: None,
        confidence_interval_overlap: None,
        overall_agreement: AgreementLevel::ExactMatch,
    }
}

pub fn make_time_breakdown() -> TimeBreakdown {
    TimeBreakdown {
        environment_setup_secs: 900,
        data_acquisition_secs: 600,
        code_execution_secs: 1_800,
        troubleshooting_secs: 300,
    }
}

pub fn make_computational_resources() -> ComputationalResources {
    ComputationalResources {
        personal_hardware_sufficient: true,
        hpc_required: false,
        gpu_required: false,
        cloud_compute_required: false,
        estimated_compute_cost_pence: None,
    }
}

/// Build a `ValidationAttestation` (the type that goes into both
/// `SealAttestationInput.attestation` and `AttestationRevealInput.attestation`).
///
/// `reproduction_bundle_hash` is `None` — the unbound-verdict case, which is the
/// majority of existing tests and a permanently legitimate state, not a stub.
/// Use [`make_validation_attestation_bound`] to exercise the bound path.
pub fn make_validation_attestation(request_ref: ExternalHash) -> ValidationAttestation {
    ValidationAttestation {
        request_ref,
        outcome: AttestationOutcome::Reproduced,
        outcome_summary: make_outcome_summary(),
        time_invested_secs: 3_600,
        time_breakdown: make_time_breakdown(),
        confidence: AttestationConfidence::High,
        deviation_flags: vec![],
        computational_resources: make_computational_resources(),
        discipline: Discipline::ComputationalBiology,
        commitment_anchor_hash: None, // filled by coordinator on reveal
        reproduction_bundle_hash: None,
    }
}

/// A 32-byte fake bundle `content_hash`, distinct per `seed`.
///
/// Deliberately NOT random: a negative-control test has to be able to state that
/// hash A and hash B differ, and re-run to the same values.
pub fn fake_bundle_hash(seed: u8) -> Vec<u8> {
    vec![seed; 32]
}

/// `make_validation_attestation` with a bound reproduction bundle — the case where
/// the validator's verdict is tied to specific per-sample outputs.
pub fn make_validation_attestation_bound(
    request_ref: ExternalHash,
    bundle_hash: Vec<u8>,
) -> ValidationAttestation {
    ValidationAttestation {
        reproduction_bundle_hash: Some(bundle_hash),
        ..make_validation_attestation(request_ref)
    }
}

// ---------------------------------------------------------------------------
// Fixture builders — DNA 3 (attestation)
// ---------------------------------------------------------------------------

pub fn make_validation_request(data_hash: ExternalHash) -> ValidationRequest {
    ValidationRequest {
        protocol_ref: None,
        data_hash,
        data_access_url: "https://osf.io/example".into(),
        deposit_access_type: Default::default(),
        deposit_token: None,
        protocol_access_url: None,
        num_validators_required: 2,
        validation_tier: ValidationTier::Basic,
        discipline: Discipline::ComputationalBiology,
        researcher_institution: "Open Science Lab".into(),
    }
}

pub fn make_validator_profile(institution: &str) -> ValidatorProfile {
    ValidatorProfile {
        institution: institution.into(),
        disciplines: vec![Discipline::ComputationalBiology],
        certification_tier: CertificationTier::Standard,
        available: true,
        max_concurrent_tasks: 3,
        orcid: None,
        agent_type: Some(ValidatorAgentType::Individual),
        person_key: None,
    }
}

// ---------------------------------------------------------------------------
// Fixture builders — DNA 4 (governance)
// ---------------------------------------------------------------------------

pub fn make_governance_decision() -> GovernanceDecision {
    GovernanceDecision {
        proposal: "Add new discipline: Epidemiology".into(),
        decision: "Approved by 7-2 vote.".into(),
        votes_for: 7,
        votes_against: 2,
    }
}
