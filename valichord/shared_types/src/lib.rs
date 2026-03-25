use hdi::prelude::*;
use std::borrow::Cow;

// ---------------------------------------------------------------------------
// Core type alias
// ---------------------------------------------------------------------------

/// In real crates use `ExternalHash` from `hdi::prelude::*`.
/// ExternalHash serialises correctly through Holochain's MessagePack layer
/// and can be used as a DHT base address for links.
pub type ResearchHash = ExternalHash;

// ---------------------------------------------------------------------------
// Discipline enum
// ---------------------------------------------------------------------------

/// Scientific discipline. Extended by governance decision, not code change.
/// Kept in shared types so the same enum is used across all four DNAs.
#[derive(Debug, Clone, Hash, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
pub enum Discipline {
    ComputationalBiology,
    ClimateScience,
    SocialScience,
    Economics,
    Psychology,
    Neuroscience,
    MachineLearning,
    Other(String),
}

/// Converts a Discipline to the short path-key string used in DHT path anchors.
/// Returns a `Cow<'static, str>` — zero allocation for all named variants.
pub fn discipline_tag(d: &Discipline) -> Cow<'static, str> {
    match d {
        Discipline::ComputationalBiology => "computational_biology".into(),
        Discipline::ClimateScience       => "climate_science".into(),
        Discipline::SocialScience        => "social_science".into(),
        Discipline::Economics            => "economics".into(),
        Discipline::Psychology           => "psychology".into(),
        Discipline::Neuroscience         => "neuroscience".into(),
        Discipline::MachineLearning      => "machine_learning".into(),
        Discipline::Other(s)             => format!("other_{}", s.to_lowercase()).into(),
    }
}

// ---------------------------------------------------------------------------
// Attestation outcome types
// ---------------------------------------------------------------------------

/// Structured outcome from a single validator's reproduction attempt.
/// Shared across DNA 2 (private commit) and DNA 3 (public reveal).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
pub enum AttestationOutcome {
    /// Code ran and key results match published findings.
    Reproduced,
    /// Code ran but results partially match (detail required).
    PartiallyReproduced { details: String },
    /// Code ran but results do not match published findings.
    FailedToReproduce { details: String },
    /// Validator could not reach the point of running the code.
    UnableToAssess { reason: String },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum AttestationConfidence { High, Medium, Low }

/// Phase 0's four-category time breakdown — the primary measurement goal.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct TimeBreakdown {
    pub environment_setup_secs: u64,
    pub data_acquisition_secs:  u64,
    pub code_execution_secs:    u64,
    pub troubleshooting_secs:   u64,
}

// ---------------------------------------------------------------------------
// Deviation types
// ---------------------------------------------------------------------------

/// Structured deviation type. Machine-readable, not free text.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
pub enum DeviationType {
    DataAccess            { reason: String, impact: EpistemicImpact },
    EthicalConcern        { review_board: String },
    ModelFailure          { attempted_model: String, fallback_model: String, justification: String },
    ComputationalLimit    { planned_method: String, actual_method: String, reason: String },
    SampleSizeAdjustment  { original_n: usize, revised_n: usize, power_analysis: String },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EpistemicImpact {
    Minimal,
    Moderate,
    Substantial, // Triggers governance review
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Severity { Minor, Moderate, Major, Critical }

/// A deviation the validator observed that the researcher did NOT pre-declare.
/// Defined in shared types so the same struct is used in both Validator
/// Workspace DNA (private attestation) and Attestation DNA (public reveal).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UndeclaredDeviation {
    pub deviation_type: DeviationType,
    pub severity:       Severity,
    pub evidence:       String,
}

// ---------------------------------------------------------------------------
// Computational resources
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ComputationalResources {
    pub personal_hardware_sufficient:  bool,
    pub hpc_required:                  bool,
    pub gpu_required:                  bool,
    pub cloud_compute_required:        bool,
    /// Integer pence to avoid floating-point rounding in financial values.
    pub estimated_compute_cost_pence:  Option<u64>,
}

// ---------------------------------------------------------------------------
// Validation phase (DNA 3 commit-reveal protocol state)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ValidationPhase {
    RevealOpen,
    Complete,
}

// ---------------------------------------------------------------------------
// Attestation agreement and certification types
// ---------------------------------------------------------------------------
//
// Defined here (not in attestation_integrity) so they can be imported by
// validator_workspace_integrity, governance_integrity, and governance_coordinator
// WITHOUT creating a cdylib→cdylib dependency — which would cause duplicate
// WASM symbol errors at link time.

/// Agreement level across validator outcomes for a given request.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum AgreementLevel {
    ExactMatch,
    WithinTolerance,
    DirectionalMatch,
    Divergent,
    UnableToAssess,
}

/// Per-validator certification tier used in ValidatorProfile and ValidatorReputation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum CertificationTier {
    Provisional,
    Certified,
    Senior,
}

/// Structured per-metric outcome — included in OutcomeSummary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricResult {
    pub metric_name:      String,
    pub produced_value:   String,
    pub expected_value:   String,
    pub within_tolerance: bool,
}

/// Agreement summary attached to every ValidationAttestation.
/// Agreement is assessed on summaries — NOT raw result hashes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutcomeSummary {
    pub key_metrics:                 Vec<MetricResult>,
    pub effect_direction_matches:    Option<bool>,
    pub confidence_interval_overlap: Option<f64>,
    pub overall_agreement:           AgreementLevel,
}

/// THE REVEAL PHASE public attestation entry — defined here so governance_coordinator
/// can deserialise cross-DNA records without importing attestation_integrity (cdylib).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidationAttestation {
    pub request_ref:             ExternalHash,
    pub outcome:                 AttestationOutcome,
    pub outcome_summary:         OutcomeSummary,
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub confidence:              AttestationConfidence,
    pub deviation_flags:         Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
    pub discipline:              Discipline,
    /// ActionHash of the CommitmentAnchor this validator published during the commit phase.
    /// Inductive validation chain: ValidationAttestation → CommitmentAnchor → ValidationRequest.
    /// Set by the coordinator (not the caller) — `None` only for entries predating this field.
    #[serde(default)]
    pub commitment_anchor_hash:  Option<ActionHash>,
}

impl ValidationAttestation {
    pub fn discipline_tag(&self) -> Cow<'static, str> {
        discipline_tag(&self.discipline)
    }
}
