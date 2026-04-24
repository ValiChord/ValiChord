//! Shared helpers for ValiChord Sweettest integration tests.
//!
//! # DNA order contract
//! `load_dnas()` returns: `[researcher_repository, validator_workspace, attestation, governance]`
//! `setup_valichord()` exposes a `ValiChordApp` whose fields match that order.

use holochain::prelude::*;
use holochain::sweettest::*;
use holochain_types::prelude::YamlProperties;
use std::path::{Path, PathBuf};

use attestation_coordinator::{AttestationRevealInput, ReclaimInput, UpdateValidatorProfileInput};
use attestation_integrity::{
    DifficultyTier, AssessmentConfidence,
    ResearcherRevealInput,
    ValidatorAgentType, ValidationRequest, ValidationTier,
};
pub use valichord_shared_types::{CommitmentSealedInput, ResearcherCommitmentInput};
use governance_coordinator::ReputationUpdateInput;
use governance_integrity::{BadgeType, GovernanceDecision, HarmonyRecord};
use researcher_repository_coordinator::{
    DeclareDeviationInput, LockResultInput, RegisterProtocolInput, TakeDataSnapshotInput,
};
use researcher_repository_integrity::{
    PreRegisteredProtocol, ResearchStudy, VerifiedDataSnapshot,
};
use validator_workspace_coordinator::SealAttestationInput;
use validator_workspace_integrity::{
    CompensationTier, ValidationFocus, ValidationTask,
};
use valichord_shared_types::{
    AgreementLevel, AttestationConfidence, AttestationOutcome, ComputationalResources,
    CertificationTier, Discipline, MetricResult, OutcomeSummary, Severity, TimeBreakdown,
    UndeclaredDeviation, ValidationAttestation,
};

// Re-export commonly used types so tests only need `use valichord_sweettest::*`
pub use attestation_coordinator::AttestationRevealInput as RevealInput;
pub use attestation_integrity::{StudyClaim, ValidatorProfile};
pub use holochain::prelude::*;
pub use holochain::sweettest::*;

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

pub fn workdir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../workdir")
}

pub fn dna_path(name: &str) -> PathBuf {
    workdir().join(name)
}

// ---------------------------------------------------------------------------
// DNA loading with test properties
// ---------------------------------------------------------------------------

/// Attestation DNA properties for tests (issuer key = "" → full dev bypass).
fn attestation_yaml_props() -> serde_yaml::Value {
    serde_yaml::from_str(
        "minimum_validators: 2\n\
         discipline: computational_biology\n\
         authorized_joining_certificate_issuer: \"\"\n\
         min_claim_timeout_secs: 0\n",
    )
    .unwrap()
}

/// Governance DNA properties for tests (system_coordinator_key = "" → dev bypass).
/// round_timeout_secs: 0 bypasses the clock constraint in force_finalize_round.
fn governance_yaml_props() -> serde_yaml::Value {
    serde_yaml::from_str(
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
    let mut conductor = SweetConductor::from_standard_config().await;
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
            properties: Some(YamlProperties::new(serde_yaml::from_str(
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
    let mut conductor = SweetConductor::from_standard_config().await;
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
    let mut conductors = SweetConductorBatch::from_standard_config_rendezvous(2).await;
    let dnas = dnas_with_roles().await;
    let apps = conductors.setup_app("valichord", &dnas).await.unwrap();
    let mut app_iter = apps.into_inner().into_iter();
    let alice = ValiChordApp::from_sweet_app(app_iter.next().unwrap());
    let bob   = ValiChordApp::from_sweet_app(app_iter.next().unwrap());
    TwoAgentSetup { conductors, alice, bob }
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
