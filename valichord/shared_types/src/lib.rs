use hdi::prelude::*;
use std::borrow::Cow;

// ---------------------------------------------------------------------------
// Domain error type — shared across all ValiChord coordinator zomes
// ---------------------------------------------------------------------------
//
// Internal helper functions return `ValiChordResult<T>` and use `?` freely.
// The `#[hdk_extern]` boundary converts back to `ExternResult<T>` via
// `fn_inner(args).map_err(Into::into)` — keeping wasm_error! at the surface.
//
// Pattern borrowed from ad4m's `SocialContextError`.

#[derive(thiserror::Error, Debug)]
pub enum ValiChordError {
    /// Wraps any WasmError already produced by an HDK/HDI call.
    #[error(transparent)]
    Wasm(#[from] WasmError),
    /// Application-level rejection with a human-readable message.
    #[error("{0}")]
    Guest(String),
    /// Serialization failure (SerializedBytes / msgpack round-trip).
    #[error(transparent)]
    Serialization(#[from] SerializedBytesError),
}

pub type ValiChordResult<T> = Result<T, ValiChordError>;

/// Convert a `ValiChordError` back to the `WasmError` that `ExternResult` expects.
impl From<ValiChordError> for WasmError {
    fn from(e: ValiChordError) -> Self {
        match e {
            ValiChordError::Wasm(w) => w,
            other => wasm_error!(WasmErrorInner::Guest(other.to_string())),
        }
    }
}

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
        Discipline::Other(s)             => format!("other_{}", s.to_lowercase().replace('.', "_")).into(),
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
    /// Reserved for a future UI indicator — never written by the protocol today.
    /// The coordinator writes only `RevealOpen`; `PhaseMarker` is an append-only
    /// audit log, not a gate.  Do not add protocol logic that depends on `Complete`
    /// until a phase-transition write is implemented.
    #[allow(dead_code)]
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

/// Discriminates between human validators, institutional accounts, and
/// automated tools.  Stored as `Option` so profiles created before this
/// field was introduced deserialise as `None` (backwards-compatible).
///
/// Defined in shared_types (not attestation_integrity) so HarmonyRecord in
/// governance_integrity can embed it without a cdylib→cdylib dependency.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ValidatorAgentType {
    /// A human individual acting under their own identity.
    Individual,
    /// An institutional or group account (e.g. a lab or review committee).
    Institution,
    /// An automated tool or pipeline (e.g. a CI-based reproducer or AI system).
    AutomatedTool,
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

    /// Serialise to MessagePack bytes for commit/reveal hash computation.
    /// Both `seal_private_attestation` (DNA 2) and `submit_attestation` (DNA 3)
    /// call this — guaranteeing byte-for-byte consistency.
    ///
    /// `commitment_anchor_hash` is always normalised to `None` before
    /// serialisation so the output is independent of injection order.
    /// Callers do not need to ensure the field is unset before calling.
    pub fn commitment_msgpack_bytes(&self) -> ExternResult<Vec<u8>> {
        let mut canonical = self.clone();
        canonical.commitment_anchor_hash = None;
        SerializedBytes::try_from(&canonical)
            .map(|sb| sb.bytes().to_vec())
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))
    }
}

/// Serialise a `MetricResult` slice to MessagePack bytes for commit/reveal hash
/// computation on the researcher side.
///
/// Mirrors `ValidationAttestation::commitment_msgpack_bytes()` — both use
/// `SerializedBytes` (Holochain's canonical msgpack encoding) so the two hash
/// paths remain byte-for-byte consistent regardless of future serialiser changes.
/// `reveal_researcher_result` must call this instead of `rmps::to_vec_named`
/// directly so any future change to the encoding is made in one place.
pub fn metric_results_msgpack_bytes(metrics: &[MetricResult]) -> ExternResult<Vec<u8>> {
    rmp_serde::to_vec_named(metrics)
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))
}

// ---------------------------------------------------------------------------
// Cross-DNA coordinator input types
//
// These are plain payload structs used when one coordinator calls a function
// on a different DNA's coordinator via `call()`.  They live here (not in
// any integrity zome) so that cross-DNA coordinators can import them without
// taking a dependency on another DNA's integrity zome — which would pull
// that integrity zome's `#[no_mangle]` HDI symbols into the native (test)
// build and cause duplicate-symbol link errors.
// ---------------------------------------------------------------------------

/// Payload sent from `validator_workspace_coordinator` `seal_private_attestation`
/// to `attestation_coordinator` `notify_commitment_sealed`.
///
/// Only safe fields are included: public identifiers (`request_ref`) and
/// opaque hashes (`commitment_hash`).  Never add assessment content, scores,
/// or any data derived from the private `ValidatorPrivateAttestation`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitmentSealedInput {
    pub request_ref:     ExternalHash,
    pub commitment_hash: Vec<u8>,
}

/// Payload sent from `researcher_repository_coordinator` `lock_researcher_result`
/// to `attestation_coordinator` `publish_researcher_commitment`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearcherCommitmentInput {
    pub request_ref:            ExternalHash,
    pub result_commitment_hash: Vec<u8>,
}

// ---------------------------------------------------------------------------
// Pure outcome functions — moved here from governance_coordinator so they can
// be unit-tested without a Holochain conductor.
//
// Pattern: "functional core, imperative shell" — all decision logic lives in
// pure functions over shared types; the coordinator handles DHT I/O only.
// ---------------------------------------------------------------------------

/// Plurality-vote majority outcome across a set of attestations.
///
/// In the event of a tie among non-Reproduced outcomes, precedence is given
/// to `PartiallyReproduced` over `FailedToReproduce` over `UnableToAssess`.
pub fn derive_majority_outcome(attestations: &[ValidationAttestation]) -> AttestationOutcome {
    let (mut reproduced, mut partial, mut failed, mut unable) = (0u32, 0u32, 0u32, 0u32);
    for a in attestations {
        match &a.outcome {
            AttestationOutcome::Reproduced               => reproduced += 1,
            AttestationOutcome::PartiallyReproduced { .. } => partial  += 1,
            AttestationOutcome::FailedToReproduce { .. }   => failed   += 1,
            AttestationOutcome::UnableToAssess { .. }      => unable   += 1,
        }
    }
    let max = reproduced.max(partial).max(failed).max(unable);
    if reproduced == max {
        AttestationOutcome::Reproduced
    } else if partial == max {
        AttestationOutcome::PartiallyReproduced { details: "Majority partially reproduced".into() }
    } else if failed == max {
        AttestationOutcome::FailedToReproduce   { details: "Majority failed to reproduce".into() }
    } else {
        AttestationOutcome::UnableToAssess      { reason:  "Majority unable to assess".into() }
    }
}

/// Derive AgreementLevel from the success rate across a set of attestations.
///
/// Two rates are computed separately:
///   `full_rate`  = Reproduced / total
///   `any_rate`   = (Reproduced + PartiallyReproduced) / total
///
/// Thresholds:
///   full_rate ≥ 90%  → ExactMatch       (nearly all validators reproduced exactly)
///   any_rate  ≥ 70%  → WithinTolerance  (majority reproduced, some only partially)
///   any_rate  ≥ 50%  → DirectionalMatch
///   any_rate  >  0%  → Divergent
///   any_rate  == 0%  → UnableToAssess
///
/// PartiallyReproduced deliberately cannot reach ExactMatch — "all validators
/// only partially reproduced" is WithinTolerance at best, not an exact match.
pub fn derive_agreement_level(attestations: &[ValidationAttestation]) -> AgreementLevel {
    if attestations.is_empty() {
        return AgreementLevel::UnableToAssess;
    }
    let total = attestations.len() as f64;
    let full = attestations
        .iter()
        .filter(|a| matches!(&a.outcome, AttestationOutcome::Reproduced))
        .count();
    let any_success = attestations
        .iter()
        .filter(|a| matches!(
            &a.outcome,
            AttestationOutcome::Reproduced | AttestationOutcome::PartiallyReproduced { .. }
        ))
        .count();
    let full_rate = full as f64 / total;
    let any_rate  = any_success as f64 / total;
    if full_rate >= 0.90 {
        AgreementLevel::ExactMatch
    } else if any_rate >= 0.70 {
        AgreementLevel::WithinTolerance
    } else if any_rate >= 0.50 {
        AgreementLevel::DirectionalMatch
    } else if any_success > 0 {
        AgreementLevel::Divergent
    } else {
        AgreementLevel::UnableToAssess
    }
}

// ---------------------------------------------------------------------------
// Unit tests — run with `cargo test -p valichord_shared_types`
// No Holochain conductor or WASM required.
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Minimal `ValidationAttestation` for testing pure outcome functions.
    fn att(outcome: AttestationOutcome) -> ValidationAttestation {
        ValidationAttestation {
            request_ref: ExternalHash::from_raw_32(vec![0u8; 32]),
            outcome,
            outcome_summary: OutcomeSummary {
                key_metrics: vec![],
                effect_direction_matches: None,
                confidence_interval_overlap: None,
                overall_agreement: AgreementLevel::ExactMatch,
            },
            time_invested_secs: 0,
            time_breakdown: TimeBreakdown {
                environment_setup_secs: 0,
                data_acquisition_secs: 0,
                code_execution_secs: 0,
                troubleshooting_secs: 0,
            },
            confidence: AttestationConfidence::High,
            deviation_flags: vec![],
            computational_resources: ComputationalResources {
                personal_hardware_sufficient: true,
                hpc_required: false,
                gpu_required: false,
                cloud_compute_required: false,
                estimated_compute_cost_pence: None,
            },
            discipline: Discipline::ComputationalBiology,
            commitment_anchor_hash: None,
        }
    }

    // --- derive_majority_outcome ---

    #[test]
    fn majority_all_reproduced() {
        let atts = vec![att(AttestationOutcome::Reproduced); 3];
        assert!(matches!(derive_majority_outcome(&atts), AttestationOutcome::Reproduced));
    }

    #[test]
    fn majority_failed_wins() {
        let atts = vec![
            att(AttestationOutcome::Reproduced),
            att(AttestationOutcome::FailedToReproduce { details: "x".into() }),
            att(AttestationOutcome::FailedToReproduce { details: "y".into() }),
        ];
        assert!(matches!(
            derive_majority_outcome(&atts),
            AttestationOutcome::FailedToReproduce { .. }
        ));
    }

    #[test]
    fn majority_partial_wins_on_tie_with_failed() {
        // Tie between partial and failed — partial takes precedence.
        let atts = vec![
            att(AttestationOutcome::PartiallyReproduced { details: "a".into() }),
            att(AttestationOutcome::FailedToReproduce   { details: "b".into() }),
        ];
        assert!(matches!(
            derive_majority_outcome(&atts),
            AttestationOutcome::PartiallyReproduced { .. }
        ));
    }

    #[test]
    fn majority_single_unable() {
        let atts = vec![att(AttestationOutcome::UnableToAssess { reason: "no data".into() })];
        assert!(matches!(
            derive_majority_outcome(&atts),
            AttestationOutcome::UnableToAssess { .. }
        ));
    }

    // --- derive_agreement_level ---

    #[test]
    fn agreement_empty_is_unable() {
        assert_eq!(derive_agreement_level(&[]), AgreementLevel::UnableToAssess);
    }

    #[test]
    fn agreement_all_reproduced_is_exact_match() {
        let atts = vec![att(AttestationOutcome::Reproduced); 4];
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::ExactMatch);
    }

    #[test]
    fn agreement_90_percent_is_exact_match() {
        // 9 reproduced, 1 failed → full_rate 90% → ExactMatch
        let mut atts = vec![att(AttestationOutcome::Reproduced); 9];
        atts.push(att(AttestationOutcome::FailedToReproduce { details: String::new() }));
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::ExactMatch);
    }

    #[test]
    fn agreement_all_partial_is_within_tolerance_not_exact_match() {
        // All validators only partially reproduced — not ExactMatch, despite 100% any_rate.
        let atts = vec![
            att(AttestationOutcome::PartiallyReproduced { details: "close".into() });
            4
        ];
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::WithinTolerance);
    }

    #[test]
    fn agreement_mixed_reproduced_and_partial_below_90_full_is_within_tolerance() {
        // 8 Reproduced + 2 PartiallyReproduced → full_rate 80% < 90%, any_rate 100% ≥ 70%
        let mut atts = vec![att(AttestationOutcome::Reproduced); 8];
        atts.extend(vec![att(AttestationOutcome::PartiallyReproduced { details: String::new() }); 2]);
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::WithinTolerance);
    }

    #[test]
    fn agreement_70_percent_is_within_tolerance() {
        // 7 reproduced, 3 failed → 70 % → WithinTolerance
        let mut atts = vec![att(AttestationOutcome::Reproduced); 7];
        atts.extend(vec![att(AttestationOutcome::FailedToReproduce { details: String::new() }); 3]);
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::WithinTolerance);
    }

    #[test]
    fn agreement_50_percent_is_directional_match() {
        let mut atts = vec![att(AttestationOutcome::Reproduced); 1];
        atts.push(att(AttestationOutcome::FailedToReproduce { details: String::new() }));
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::DirectionalMatch);
    }

    #[test]
    fn agreement_all_failed_is_unable_to_assess() {
        let atts = vec![
            att(AttestationOutcome::FailedToReproduce { details: String::new() });
            3
        ];
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::UnableToAssess);
    }

    #[test]
    fn agreement_one_success_among_many_failures_is_divergent() {
        let mut atts = vec![att(AttestationOutcome::Reproduced); 1];
        atts.extend(vec![att(AttestationOutcome::FailedToReproduce { details: String::new() }); 4]);
        assert_eq!(derive_agreement_level(&atts), AgreementLevel::Divergent);
    }
}
