// =============================================================================
// ValiChord — Distributed Validation Infrastructure for Computational Research
// =============================================================================
//
// ARCHITECTURE SCAFFOLD — NOT PRODUCTION CODE
//
// This file captures ValiChord's full eight-layer architecture as Rust types,
// traits, and stub implementations. It is designed to be read by Holochain
// engineers (Shin Sakamoto, Paul D'Aoust) and Rust experts (Joel Marcey) as
// a concrete specification of what ValiChord needs to do.
//
// Status:
//   - Types: Complete and reviewed against the Technical Reference document
//   - Trait definitions: Complete — these define the system's API surface
//   - Implementations: Stubs only — marked with TODO for Phase 1 engineering
//   - Holochain integration: Annotated but not HDK-specific — the HDK API
//     evolves and this scaffold should be adapted to the current SDK version
//
// What this IS:
//   - A type-level specification of ValiChord's data model
//   - A trait-level specification of ValiChord's behaviour
//   - A guide for Phase 1 engineering decisions
//   - Something Joel and Shin can review and say "this is the right shape"
//
// What this is NOT:
//   - Compilable against the current Holochain HDK (API may have changed)
//   - Production-ready (no error handling, no tests, no persistence)
//   - A substitute for Phase 0 evidence (compensation tiers, difficulty
//     weights, and thresholds are all placeholders pending empirical data)
//
// Architecture layers:
//   Layer 0: Data & Integrity Foundation
//   Layer 1: Intake & Pre-Commitment
//   Layer 2: Validation Engine (core)
//   Layer 3: Governance & Policy
//   Layer 4: Audit & Provenance
//   Layer 5: Output & Certification (Harmony Records)
//   Layer 6: Incentive & Reputation
//   Layer 7: Integration & Interface
//   Layer 8: Access & Presentation
//
// Companion documents:
//   - ValiChord Technical Reference (1,622 lines — full architecture narrative)
//   - ValiChord Vision & Architecture (system-level design rationale)
//   - ValiChord Governance Framework (governance mechanics and anti-capture)
//   - ValiChord Phase 0 Proposal (the empirical study that informs all of this)
//   - ValiChord Open Design Questions (13 unresolved engineering questions)
//
// Author: Ceri John (architecture), with AI assistance (scaffold generation)
// Date: February 2026
// Licence: Copyright held by author; will be open-sourced on funding
// =============================================================================

#![allow(dead_code, unused_variables)]

use std::collections::HashMap;
use std::time::{Duration, SystemTime};

// =============================================================================
// COMMON TYPES
// =============================================================================

/// SHA-256 digest. Content addressing is fundamental to ValiChord — every piece
/// of data is identified by its hash, not by a database key.
pub type Hash = [u8; 32];

/// UTC timestamp. All ValiChord events are timestamped for audit and provenance.
pub type DateTime = SystemTime;

/// Holochain AgentPubKey equivalent. Each participant has a unique cryptographic
/// identity derived from their keypair. In Holochain, this is the AgentPubKey.
/// Outside Holochain (e.g. in tests), any unique identifier works.
pub type AgentId = [u8; 32];

/// Alias for readability when the agent is acting as a validator.
pub type ValidatorId = AgentId;

/// Alias for readability when referencing a validation event.
pub type ValidationId = Hash;

/// Cryptographic signature from an agent's keypair.
pub type Signature = Vec<u8>;

/// Scientific discipline. Extensible — disciplines are added by governance
/// decision, not by code change.
#[derive(Debug, Clone, Hash, Eq, PartialEq)]
pub enum Discipline {
    ComputationalBiology,
    ClimateScience,
    SocialScience,
    Economics,
    Physics,
    Chemistry,
    Psychology,
    Neuroscience,
    MachineLearning,
    Other(String),
}

/// Error types. Intentionally broad at scaffold stage — Phase 1 engineering
/// should define granular error types per layer.
#[derive(Debug)]
pub enum ValiChordError {
    NotFound(String),
    Unauthorized(String),
    ValidationFailed(String),
    GovernanceRequired(String),
    HashMismatch { expected: Hash, actual: Hash },
    TimeLockViolation,
    QuorumNotMet { required: u8, received: u8 },
    HolochainError(String),
    StorageError(String),
}

pub type Result<T> = std::result::Result<T, ValiChordError>;

// =============================================================================
// LAYER 0: DATA & INTEGRITY FOUNDATION
// =============================================================================
//
// Purpose: Content-addressed, tamper-evident data snapshots. The fingerprint
// matters, not where the data lives.
//
// Holochain relevance: These structs become Holochain entries. The content_id
// is the EntryHash. Storage locations are metadata links.

pub mod layer0_data {
    use super::*;

    /// Content-addressed, tamper-evident data snapshot.
    /// This is the foundational data unit — every study entering ValiChord
    /// begins as a VerifiedDataSnapshot.
    #[derive(Debug, Clone)]
    pub struct VerifiedDataSnapshot {
        /// Unique content identifier (SHA-256 hash of contents)
        pub content_id: Hash,
        /// Redundant storage locations — the hash matters, not the location
        pub storage_locations: Vec<StorageLocation>,
        /// Primary integrity hash
        pub sha256_hash: Hash,
        /// Dataset metadata
        pub size_bytes: u64,
        pub created_at: DateTime,
        pub creator_id: AgentId,
    }

    /// Storage location is deliberately agnostic. Academic repositories are
    /// the natural first choice. The integrity guarantee comes from the
    /// content hash recorded on Holochain, not from the storage system.
    #[derive(Debug, Clone)]
    pub enum StorageLocation {
        Zenodo { deposit_id: String },
        Figshare { article_id: String },
        InstitutionalRepository { url: String },
        Osf { project_id: String },
        GitHub { repo: String, commit_sha: String },
        S3 { bucket: String, region: String },
        Other { provider: String, location: String },
    }

    /// External links to existing research infrastructure.
    #[derive(Debug, Clone, Default)]
    pub struct ExternalLinks {
        pub osf_project: Option<String>,
        pub github_repo: Option<String>,
        pub preregistration_doi: Option<String>,
        pub trial_registry: Option<String>,
        pub publication_doi: Option<String>,
    }

    /// GDPR compliance: sensitive data stays local, only salted hashes
    /// go to the DHT. This is Holochain's killer feature for ValiChord.
    pub fn hash_dataset_with_salt(data: &[u8], salt: &[u8]) -> Hash {
        // TODO: Use proper SHA-256 (ring, sha2, or Holochain's built-in)
        // The salt prevents rainbow table attacks on the hash.
        // Salt is transmitted off-DHT from data custodian to validator.
        let mut combined = data.to_vec();
        combined.extend_from_slice(salt);
        [0u8; 32] // Placeholder
    }

    impl VerifiedDataSnapshot {
        /// Verify integrity by re-hashing content and comparing.
        pub fn verify_integrity(&self, content: &[u8]) -> bool {
            // TODO: SHA-256 hash of content == self.sha256_hash
            false // Placeholder
        }
    }
}

// =============================================================================
// LAYER 1: INTAKE & PRE-COMMITMENT
// =============================================================================
//
// Purpose: Bring research into ValiChord in structured form with pre-commitment
// enforcement. Front-end protection that complements back-end validation.
//
// Key insight: Converting free-text research protocols into structured claims
// is a significant UX challenge. Phase 1 likely needs a structured submission
// form rather than automated parsing.

pub mod layer1_intake {
    use super::*;
    use super::layer0_data::*;

    /// Pre-registered protocol with committed analysis plan.
    /// Time-locked after registration to prevent post-hoc modification.
    #[derive(Debug, Clone)]
    pub struct PreRegisteredProtocol {
        pub protocol_id: Hash,
        pub analysis_plan: TimeLocked<AnalysisPlan>,
        pub hypotheses: Vec<Hypothesis>,
        pub analysis_type: AnalysisType,
        pub primary_outcomes: Vec<OutcomeMeasure>,
        pub secondary_outcomes: Vec<OutcomeMeasure>,
        pub stopping_rules: StoppingRules,
        pub sample_size: SampleSizeSpec,
        pub allowed_deviation_types: Vec<DeviationType>,
        pub registered_at: DateTime,
        pub institutional_approval: Option<Signature>,
        pub external_links: ExternalLinks,
    }

    /// Time-locked container. Once locked, modifications require explicit
    /// declaration + justification + governance review if impact is substantial.
    #[derive(Debug, Clone)]
    pub struct TimeLocked<T> {
        pub inner: T,
        pub locked_at: DateTime,
        pub locked_hash: Hash,
        pub modification_history: Vec<Modification>,
    }

    impl<T> TimeLocked<T> {
        /// Modifications require explicit declaration + justification.
        /// Substantial epistemic impact triggers governance review.
        pub fn request_modification(
            &mut self,
            modification: Modification,
            justification: String,
            epistemic_impact: EpistemicImpact,
            requested_by: AgentId,
        ) -> Result<()> {
            if epistemic_impact == EpistemicImpact::Substantial {
                return Err(ValiChordError::GovernanceRequired(
                    "Substantial epistemic impact requires governance review".into()
                ));
            }
            self.modification_history.push(Modification {
                changed_at: SystemTime::now(),
                justification,
                impact: epistemic_impact,
                approver: requested_by,
            });
            Ok(())
        }
    }

    #[derive(Debug, Clone)]
    pub struct AnalysisPlan {
        pub description: String,
        pub statistical_methods: Vec<String>,
        pub software_requirements: Vec<String>,
    }

    #[derive(Debug, Clone)]
    pub struct Hypothesis {
        pub statement: String,
        pub formal_spec: Option<FormalClaim>,
        pub claim_type: ClaimType,
    }

    #[derive(Debug, Clone)]
    pub struct FormalClaim {
        pub null_hypothesis: String,
        pub alternative_hypothesis: String,
        pub significance_threshold: f64,
        pub test_statistic: String,
        pub direction: Direction,
    }

    #[derive(Debug, Clone)]
    pub enum Direction { TwoSided, GreaterThan, LessThan }

    #[derive(Debug, Clone)]
    pub enum ClaimType {
        Primary,
        Secondary,
        Exploratory { disclosed: bool },
        Robustness,
    }

    #[derive(Debug, Clone)]
    pub enum AnalysisType { Confirmatory, Exploratory, Mixed }

    #[derive(Debug, Clone)]
    pub struct OutcomeMeasure { pub name: String, pub specification: String }

    #[derive(Debug, Clone)]
    pub struct StoppingRules { pub description: String }

    #[derive(Debug, Clone)]
    pub struct SampleSizeSpec { pub n: usize, pub justification: String }

    #[derive(Debug, Clone)]
    pub struct Modification {
        pub changed_at: DateTime,
        pub justification: String,
        pub impact: EpistemicImpact,
        pub approver: AgentId,
    }

    /// Not all deviations are equal. The system must distinguish between them.
    /// This typology is one of ValiChord's key contributions — making deviation
    /// reporting structured rather than free-text.
    #[derive(Debug, Clone)]
    pub enum DeviationType {
        DataAccess { reason: String, impact: EpistemicImpact },
        EthicalConcern { review_board: String, decision_date: DateTime },
        ModelFailure {
            attempted_model: String,
            fallback_model: String,
            justification: String,
        },
        ComputationalLimit {
            planned_method: String,
            actual_method: String,
            reason: String,
        },
        SampleSizeAdjustment {
            original_n: usize,
            revised_n: usize,
            power_analysis: String,
        },
    }

    #[derive(Debug, Clone, PartialEq)]
    pub enum EpistemicImpact {
        /// No impact on inference
        Minimal,
        /// May affect confidence bounds
        Moderate,
        /// Changes interpretation — triggers governance review
        Substantial,
    }

    /// Explicit, versioned, testable claim.
    #[derive(Debug, Clone)]
    pub struct VerifiableClaim {
        pub claim_id: Hash,
        pub statement: String,
        pub formal_spec: Option<FormalClaim>,
        pub depends_on: Vec<Hash>,
        pub evidence_threshold: EvidenceThreshold,
        pub claim_type: ClaimType,
    }

    #[derive(Debug, Clone)]
    pub struct EvidenceThreshold {
        pub min_validators: u8,
        pub min_agreement: f64,
    }
}

// =============================================================================
// LAYER 2: VALIDATION ENGINE (CORE)
// =============================================================================
//
// Purpose: Coordinate distributed validation with gaming detection and
// collusion resistance. This is ValiChord's core.
//
// Key design decisions:
//   - Commit-reveal protocol: validators commit hash of results before seeing
//     others'. Prevents last-mover advantage.
//   - Double-blind: validators don't see author names or institutions.
//   - Three validators per study minimum (Phase 0 evidence drives this).
//   - Difficulty assessment from surface features (Phase 0 provides training data).

pub mod layer2_validation {
    use super::*;
    use super::layer0_data::*;
    use super::layer1_intake::*;

    /// A request to validate a study.
    #[derive(Debug, Clone)]
    pub struct ValidationRequest {
        pub request_id: Hash,
        /// References Layer 1 pre-registered protocol
        pub protocol_ref: Option<Hash>,
        /// Data snapshot from Layer 0
        pub data_snapshot: VerifiedDataSnapshot,
        /// Validation parameters
        pub num_validators_required: u8,
        pub validation_tier: ValidationTier,
        /// Requester (researcher, journal, funder)
        pub requester: AgentId,
        pub requested_at: DateTime,
    }

    #[derive(Debug, Clone)]
    pub enum ValidationTier {
        /// Simple computational reproducibility
        Basic,
        /// Includes robustness checks
        Enhanced,
        /// Full methodological review
        Comprehensive,
    }

    // ---- Difficulty Assessment ----
    // Phase 0 provides the training data for this. All weights and thresholds
    // below are PLACEHOLDERS pending empirical evidence.

    /// Surface feature scores for predicting validation difficulty.
    /// Each score is 1–5. Weights are derived from Phase 0 correlations.
    #[derive(Debug, Clone)]
    pub struct DifficultyAssessment {
        pub code_volume: u8,
        pub dependency_count: u8,
        pub documentation_quality: u8,
        pub data_accessibility: u8,
        pub environment_complexity: u8,
        pub study_age_years: u8,
        /// Computed from weighted scores
        pub predicted_tier: DifficultyTier,
        pub predicted_time_range: (Duration, Duration),
        pub confidence: AssessmentConfidence,
    }

    #[derive(Debug, Clone, PartialEq)]
    pub enum DifficultyTier {
        Standard,     // ~4-8 hours predicted
        Moderate,     // ~8-16 hours predicted
        Complex,      // ~16-30 hours predicted
        Extreme,      // ~30+ hours — flagged for triage review
        Excluded,     // Fails minimum criteria
    }

    #[derive(Debug, Clone)]
    pub enum AssessmentConfidence { High, Medium, Low }

    impl DifficultyAssessment {
        /// Compute predicted tier from surface feature scores.
        /// PLACEHOLDER: weights must come from Phase 0 regression.
        pub fn compute(
            code_volume: u8,
            dependency_count: u8,
            documentation_quality: u8,
            data_accessibility: u8,
            environment_complexity: u8,
            study_age_years: u8,
        ) -> Self {
            // TODO: Replace with empirically derived weights from Phase 0
            // The current weights are illustrative only.
            let weighted_score =
                (code_volume as f64 * 0.15) +
                (dependency_count as f64 * 0.20) +
                ((5 - documentation_quality) as f64 * 0.25) + // Inverse: poor docs = harder
                ((5 - data_accessibility) as f64 * 0.20) +    // Inverse: poor access = harder
                (environment_complexity as f64 * 0.10) +
                (study_age_years as f64 * 0.10);

            let predicted_tier = if weighted_score < 1.5 {
                DifficultyTier::Standard
            } else if weighted_score < 2.5 {
                DifficultyTier::Moderate
            } else if weighted_score < 3.5 {
                DifficultyTier::Complex
            } else {
                DifficultyTier::Extreme
            };

            DifficultyAssessment {
                code_volume,
                dependency_count,
                documentation_quality,
                data_accessibility,
                environment_complexity,
                study_age_years,
                predicted_tier,
                predicted_time_range: (Duration::from_secs(0), Duration::from_secs(0)), // TODO
                confidence: AssessmentConfidence::Low, // Low until Phase 0 data
            }
        }
    }

    /// Improvement feedback for studies that score poorly.
    /// The same surface features that predict difficulty generate actionable
    /// recommendations — turning ValiChord from a gatekeeper into a mentor.
    #[derive(Debug, Clone)]
    pub struct ImprovementReport {
        pub study_ref: Hash,
        pub overall_assessment: DifficultyTier,
        pub feature_scores: DifficultyAssessment,
        pub recommendations: Vec<ImprovementRecommendation>,
        pub projected_tier_if_improved: DifficultyTier,
    }

    #[derive(Debug, Clone)]
    pub struct ImprovementRecommendation {
        pub feature: String,
        pub current_score: u8,
        pub target_score: u8,
        pub action: String,
        pub guidance_link: String,
        pub estimated_effort: String,
    }

    // ---- Validation Task & Assignment ----

    /// A validation task assigned to a specific validator.
    #[derive(Debug, Clone)]
    pub struct ValidationTask {
        pub task_id: Hash,
        pub request_ref: Hash,
        pub protocol_ref: Option<Hash>,
        pub preregistered_plan: Option<PreRegisteredProtocol>,
        pub data_snapshot: VerifiedDataSnapshot,
        pub assigned_validator: ValidatorId,
        pub assigned_at: DateTime,
        pub validation_focus: ValidationFocus,
        pub time_cap: Duration,
        pub status: TaskStatus,
    }

    #[derive(Debug, Clone)]
    pub enum ValidationFocus {
        ComputationalReproducibility,
        PreCommitmentAdherence,
        MethodologicalReview,
    }

    #[derive(Debug, Clone)]
    pub enum TaskStatus {
        Assigned,
        InProgress { started_at: DateTime },
        CommitmentSubmitted { commitment_hash: Hash },
        Revealed { attestation: ValidationAttestation },
        Completed,
        Withdrawn { reason: String },
        TimedOut,
    }

    // ---- Commit-Reveal Protocol ----
    // Validators submit a hash of their results before seeing anyone else's.
    // Only after ALL validators have committed do they reveal actual findings.
    // This prevents last-mover advantage and coordination.

    /// Phase 1 of commit-reveal: validator commits hash of their attestation.
    #[derive(Debug, Clone)]
    pub struct ValidationCommitment {
        pub validator_id: ValidatorId,
        pub validation_id: Hash,
        /// Hash of the full attestation — proves what the validator found
        /// without revealing it until all validators have committed.
        pub commitment_hash: Hash,
        pub committed_at: DateTime,
        pub signature: Signature,
    }

    /// Phase 2 of commit-reveal: validator reveals their actual attestation.
    /// The system verifies that hash(attestation) == commitment_hash.
    #[derive(Debug, Clone)]
    pub struct ValidationReveal {
        pub validator_id: ValidatorId,
        pub validation_id: Hash,
        pub attestation: ValidationAttestation,
        pub revealed_at: DateTime,
    }

    /// The validator's assessment of a study.
    #[derive(Debug, Clone)]
    pub struct ValidationAttestation {
        pub validator_id: ValidatorId,
        pub validation_id: Hash,
        pub outcome: AttestationOutcome,
        pub detailed_report: String,
        pub time_invested: Duration,
        /// Structured time breakdown (Phase 0's four categories)
        pub time_breakdown: TimeBreakdown,
        pub confidence: AttestationConfidence,
        /// Validators can flag undeclared deviations
        pub deviation_flags: Vec<UndeclaredDeviation>,
        pub impact_agreement: Option<EpistemicImpact>,
        pub computational_resources: ComputationalResources,
    }

    #[derive(Debug, Clone)]
    pub struct TimeBreakdown {
        pub environment_setup: Duration,
        pub data_acquisition: Duration,
        pub code_execution: Duration,
        pub troubleshooting: Duration,
    }

    #[derive(Debug, Clone)]
    pub enum AttestationOutcome {
        /// Code runs and results match published findings
        Reproduced,
        /// Code runs but results partially match
        PartiallyReproduced { details: String },
        /// Code runs but results do not match
        FailedToReproduce { details: String },
        /// Could not reach the point of running the code
        UnableToAssess { reason: String },
    }

    #[derive(Debug, Clone)]
    pub enum AttestationConfidence { High, Medium, Low }

    #[derive(Debug, Clone)]
    pub struct UndeclaredDeviation {
        pub deviation_type: DeviationType,
        pub severity: Severity,
        pub evidence: String,
        pub flagged_by: ValidatorId,
    }

    #[derive(Debug, Clone)]
    pub enum Severity { Minor, Moderate, Major, Critical }

    #[derive(Debug, Clone)]
    pub struct ComputationalResources {
        pub personal_hardware_sufficient: bool,
        pub hpc_required: bool,
        pub gpu_required: bool,
        pub cloud_compute_required: bool,
        pub estimated_compute_cost: Option<f64>,
    }

    // ---- Validator Assignment Logic ----
    // Reputation-weighted constrained randomness with safeguards.

    /// Constraints on validator panel composition.
    #[derive(Debug, Clone)]
    pub struct AssignmentConstraints {
        /// Maximum percentage of validators from one institution
        pub max_institutional_share: f64,  // Default: 0.4 (40%)
        /// Minimum number of validators
        pub min_validators: u8,            // Default: 3
        /// Require at least one domain expert?
        pub require_domain_expert: bool,
        /// Double-blind: validators don't see author identity
        pub double_blind: bool,            // Default: true
    }

    impl Default for AssignmentConstraints {
        fn default() -> Self {
            AssignmentConstraints {
                max_institutional_share: 0.4,
                min_validators: 3,
                require_domain_expert: true,
                double_blind: true,
            }
        }
    }

    /// The validation engine orchestrates the full lifecycle.
    pub struct ValidationEngine {
        pub constraints: AssignmentConstraints,
        // TODO: In Holochain, this would query the DHT for available validators,
        // their reputation scores, institutional affiliations, and availability.
    }

    impl ValidationEngine {
        /// Select validators for a study, respecting all constraints.
        pub fn select_validators(
            &self,
            request: &ValidationRequest,
            available_validators: &[ValidatorProfile],
        ) -> Result<Vec<ValidatorId>> {
            // TODO: Implement reputation-weighted constrained random selection
            // 1. Filter by discipline capability
            // 2. Apply institutional caps
            // 3. Weight by reputation score
            // 4. Ensure at least one domain expert if required
            // 5. Check for co-authorship conflicts (social distance)
            // 6. Return selected validator IDs
            Err(ValiChordError::NotFound("Not implemented".into()))
        }

        /// Verify that a revealed attestation matches the prior commitment.
        pub fn verify_commitment(
            commitment: &ValidationCommitment,
            reveal: &ValidationReveal,
        ) -> bool {
            // TODO: hash(reveal.attestation) == commitment.commitment_hash
            false
        }

        /// Check for gaming patterns across a validator's history.
        pub fn detect_gaming_patterns(
            &self,
            validator_id: ValidatorId,
            history: &[ValidationAttestation],
        ) -> Vec<GamingFlag> {
            // TODO: Implement detection patterns:
            // - Collusion: >90% agreement with specific other validators over 20+ events
            // - Speed: unrealistically fast completion times
            // - Rubber-stamping: always "Reproduced" with minimal time invested
            // - Social distance: co-authorship graph proximity to study authors
            Vec::new()
        }
    }

    #[derive(Debug, Clone)]
    pub struct ValidatorProfile {
        pub id: ValidatorId,
        pub institution: String,
        pub disciplines: Vec<Discipline>,
        pub reputation: f64,
        pub total_validations: u32,
        pub available: bool,
    }

    #[derive(Debug, Clone)]
    pub enum GamingFlag {
        SuspiciousAgreementPattern { with_validator: ValidatorId, agreement_rate: f64 },
        UnrealisticallyFast { expected_min: Duration, actual: Duration },
        RubberStamping { approval_rate: f64, avg_time: Duration },
        SocialProximity { distance: u8, shared_publications: u32 },
    }
}

// =============================================================================
// LAYER 3: GOVERNANCE & POLICY
// =============================================================================
//
// Purpose: Transparent, auditable rule-setting that resists institutional capture.
// Full governance mechanics are in the companion Governance Framework document.

pub mod layer3_governance {
    use super::*;
    use super::layer1_intake::EpistemicImpact;

    #[derive(Debug, Clone)]
    pub struct GovernanceConfig {
        pub pre_registration_requirements: RequirementMatrix,
        pub deviation_review_board: ReviewBoard,
        pub impact_guidelines: ImpactGuidelines,
        pub discipline_standards: HashMap<Discipline, DisciplineStandard>,
    }

    #[derive(Debug, Clone)]
    pub struct RequirementMatrix {
        pub confirmatory_studies: PreRegRequirement,
        pub exploratory_studies: PreRegRequirement,
        pub replication_studies: PreRegRequirement,
    }

    #[derive(Debug, Clone)]
    pub enum PreRegRequirement { Mandatory, Recommended, Optional, NotApplicable }

    #[derive(Debug, Clone)]
    pub struct ReviewBoard {
        pub members: Vec<AgentId>,
        pub quorum: u8,
        pub term_months: u8,
        /// Anti-capture: no member serves more than 2 consecutive terms
        pub max_consecutive_terms: u8,
    }

    #[derive(Debug, Clone)]
    pub struct ImpactGuidelines {
        pub minimal_criteria: String,
        pub moderate_criteria: String,
        pub substantial_criteria: String,
    }

    #[derive(Debug, Clone)]
    pub struct DisciplineStandard {
        pub discipline: Discipline,
        pub pre_commitment_requirements: Vec<String>,
        pub acceptable_deviations: Vec<(String, EpistemicImpact)>,
        pub required_outcome_measures: Vec<String>,
    }

    /// Governance decision — every decision is logged to the audit trail.
    #[derive(Debug, Clone)]
    pub struct GovernanceDecision {
        pub decision_id: Hash,
        pub decision_type: DecisionType,
        pub made_by: GovernanceBody,
        pub rationale: String,
        pub vote_tally: Option<VoteTally>,
        pub made_at: DateTime,
    }

    #[derive(Debug, Clone)]
    pub enum DecisionType {
        DeviationApproved { protocol_id: Hash },
        DeviationDenied { protocol_id: Hash, reason: String },
        StandardUpdated { discipline: Discipline },
        ValidatorSanctioned { validator_id: ValidatorId, reason: String },
        PolicyChanged { policy: String, old_value: String, new_value: String },
    }

    #[derive(Debug, Clone)]
    pub enum GovernanceBody {
        DeviationReviewBoard,
        DisciplinaryStandardsCommittee { discipline: Discipline },
        SteeringCommittee,
        CommunityVote,
    }

    #[derive(Debug, Clone)]
    pub struct VoteTally {
        pub for_votes: u32,
        pub against_votes: u32,
        pub abstentions: u32,
    }
}

// =============================================================================
// LAYER 4: AUDIT & PROVENANCE
// =============================================================================
//
// Purpose: Tamper-evident record of every significant action.
//
// Holochain implementation: Every action becomes a source chain entry.
// The DHT stores cryptographic proofs. Tamper-evidence is guaranteed by
// Holochain's architecture — every agent's source chain is append-only
// and any modification is detectable by peers.

pub mod layer4_audit {
    use super::*;
    use super::layer1_intake::{DeviationType, EpistemicImpact, Modification};
    use super::layer2_validation::AttestationOutcome;
    use super::layer3_governance::{DecisionType, GovernanceBody};

    /// Every significant action creates a tamper-evident log entry.
    /// In Holochain, these are source chain entries propagated to the DHT.
    #[derive(Debug, Clone)]
    pub enum AuditEvent {
        // Layer 1 events
        ProtocolRegistered {
            protocol_id: Hash,
            registered_by: AgentId,
            registered_at: DateTime,
            protocol_hash: Hash,
        },
        ProtocolModificationRequested {
            protocol_id: Hash,
            modification: Modification,
            justification: String,
            impact: EpistemicImpact,
        },
        DeviationDeclared {
            protocol_id: Hash,
            deviation: DeviationType,
            declared_at: DateTime,
            declared_by: AgentId,
        },

        // Layer 2 events
        ValidationRequested {
            protocol_id: Hash,
            requester: AgentId,
        },
        ValidatorAssigned {
            validation_id: Hash,
            validator_id: ValidatorId,
            assigned_at: DateTime,
        },
        CommitmentSubmitted {
            validation_id: Hash,
            validator_id: ValidatorId,
            commitment_hash: Hash,
            submitted_at: DateTime,
        },
        AttestationRevealed {
            validation_id: Hash,
            validator_id: ValidatorId,
            outcome: AttestationOutcome,
            revealed_at: DateTime,
        },

        // Layer 3 events
        GovernanceDecision {
            decision_type: DecisionType,
            made_by: GovernanceBody,
            rationale: String,
            made_at: DateTime,
        },

        // Layer 5 events
        HarmonyRecordGenerated {
            protocol_id: Hash,
            harmony_record_hash: Hash,
            generated_at: DateTime,
        },

        // Layer 6 events
        ReputationUpdated {
            validator_id: ValidatorId,
            old_score: f64,
            new_score: f64,
            reason: String,
        },
    }

    /// Complete lineage from hypothesis to validation.
    #[derive(Debug, Clone)]
    pub struct ProvenanceGraph {
        pub root: Hash,
        pub nodes: Vec<ProvenanceNode>,
        pub edges: Vec<(usize, usize, ProvenanceEdge)>,
    }

    #[derive(Debug, Clone)]
    pub enum ProvenanceNode {
        PreRegistration(Hash),
        Modification(Hash),
        Deviation(Hash),
        DataSnapshot(Hash),
        ValidationRequest(Hash),
        Attestation(Hash),
        HarmonyRecord(Hash),
        Publication(Hash),
    }

    #[derive(Debug, Clone)]
    pub enum ProvenanceEdge {
        ModifiedFrom,
        DeviatedFrom,
        ValidatedUsing,
        GeneratedFrom,
        PublishedAs,
        CitedBy,
    }

    /// Access control: different views for different audiences.
    #[derive(Debug, Clone)]
    pub struct AuditRecord {
        /// Always visible
        pub public_summary: String,
        /// Research Integrity Office only
        pub internal_details: Option<String>,
        /// Validator can see their own details
        pub validator_view: Option<String>,
    }

    impl ProvenanceGraph {
        /// "Show me everything that happened to this protocol"
        pub fn full_history(&self, protocol_id: Hash) -> Vec<AuditEvent> {
            // TODO: Walk the graph from root, collecting all events
            Vec::new()
        }

        /// "Did this protocol have substantial deviations?"
        pub fn check_deviations(&self, protocol_id: Hash) -> Vec<DeviationType> {
            // TODO: Filter graph for deviation nodes
            Vec::new()
        }
    }
}

// =============================================================================
// LAYER 5: OUTPUT & CERTIFICATION (HARMONY RECORDS)
// =============================================================================
//
// Purpose: Transform internal processes into externally usable trust signals.
// The Harmony Record is ValiChord's canonical output — it preserves the full
// texture of agreement and disagreement rather than a single verdict.
//
// Design philosophy: "Harmony" means agreement *and* the structure of
// disagreement. A Harmony Record with 2 successes and 1 failure is more
// informative than a binary pass/fail.

pub mod layer5_output {
    use super::*;
    use super::layer2_validation::AttestationOutcome;

    /// The canonical output of ValiChord.
    #[derive(Debug, Clone)]
    pub struct HarmonyRecord {
        pub record_id: Hash,
        pub protocol_id: Hash,
        pub validation_summary: ValidationSummary,
        pub validators: Vec<ValidatorSummary>,
        /// Disagreements are always visible — per governance commitments
        pub disagreements: Vec<Disagreement>,
        pub confidence_level: ConfidenceLevel,
        pub status: ReproducibilityStatus,
        pub issued_at: DateTime,
        /// 24 months minimum per governance policy
        pub valid_until: DateTime,
        pub provenance_link: String,
    }

    #[derive(Debug, Clone)]
    pub struct ValidationSummary {
        pub total_validators: u8,
        pub successful_validations: u8,
        pub partial_validations: u8,
        pub failed_validations: u8,
        pub inconclusive_validations: u8,
        pub agreement_level: f64,
        pub outlier_count: u8,
    }

    #[derive(Debug, Clone)]
    pub struct ValidatorSummary {
        pub validator_id: ValidatorId,
        pub outcome: AttestationOutcome,
        pub time_invested: Duration,
        pub confidence: String,
    }

    #[derive(Debug, Clone)]
    pub struct Disagreement {
        pub description: String,
        pub validators_involved: Vec<ValidatorId>,
        pub resolution: Option<String>,
    }

    #[derive(Debug, Clone)]
    pub enum ConfidenceLevel {
        High { agreement: f64, reasoning: String },
        Medium { concerns: Vec<String>, reasoning: String },
        Low { substantial_disagreement: bool, reasoning: String },
    }

    /// ValiChord refuses to force a verdict where evidence doesn't support one.
    /// PersistentlyIndeterminate is a valid, informative status.
    #[derive(Debug, Clone)]
    pub enum ReproducibilityStatus {
        ExactMatch { validator_count: u8 },
        DirectionalMatch { validator_count: u8, variance_explanation: String },
        PartialMatch { successful_aspects: Vec<String>, failed_aspects: Vec<String> },
        Failed { failure_reasons: Vec<String>, validator_count: u8 },
        Inconclusive { reasons: Vec<String> },
        PersistentlyIndeterminate {
            time_elapsed: Duration,
            validator_count: u8,
            disagreement_summary: String,
        },
    }

    /// Domain-specific badges. Cannot be reduced to a single numerical score.
    #[derive(Debug, Clone)]
    pub enum ReproducibilityBadge {
        ComputationalReproducible { level: BadgeLevel, discipline: Discipline },
        PreRegisteredAndValidated { adherence_score: f64 },
        OpenDataValidated,
        MultiLabValidated { lab_count: u8 },
    }

    #[derive(Debug, Clone)]
    pub enum BadgeLevel {
        Bronze,  // ≥3 validators, ≥60% success
        Silver,  // ≥5 validators, ≥70%, pre-registered
        Gold,    // ≥7 validators, ≥80%, multi-institutional
    }

    /// Human-readable narrative report tailored to audience.
    #[derive(Debug, Clone)]
    pub struct NarrativeReport {
        pub executive_summary: String,
        pub protocol_description: String,
        pub validation_process: String,
        pub findings: String,
        pub limitations: Vec<String>,  // Always included
        pub recommendations: Vec<String>,
        pub generated_at: DateTime,
    }

    impl HarmonyRecord {
        /// Generate a narrative report from this Harmony Record.
        pub fn to_narrative(&self) -> NarrativeReport {
            // TODO: Template-based generation with discipline-specific language.
            // Must explicitly flag disagreements (governance commitment).
            // Must avoid overconfident language.
            // Must include appropriate caveats.
            NarrativeReport {
                executive_summary: String::new(),
                protocol_description: String::new(),
                validation_process: String::new(),
                findings: String::new(),
                limitations: Vec::new(),
                recommendations: Vec::new(),
                generated_at: SystemTime::now(),
            }
        }
    }
}

// =============================================================================
// LAYER 6: INCENTIVE & REPUTATION
// =============================================================================
//
// Purpose: Align behaviour with system goals. Multi-dimensional reputation
// that cannot be reduced to a single gameable number.

pub mod layer6_incentive {
    use super::*;

    /// Multi-dimensional reputation. No single number that can be gamed.
    #[derive(Debug, Clone)]
    pub struct ValidatorReputation {
        pub validator_id: ValidatorId,
        pub validation_score: f64,
        pub preregistration_quality: f64,
        pub deviation_handling: f64,
        pub time_investment_consistency: f64,
        pub peer_endorsements: u32,
        pub expertise_areas: HashMap<Discipline, ExpertiseLevel>,
        pub institution: String,
        pub total_validations: u32,
        pub total_score: f64,
    }

    #[derive(Debug, Clone)]
    pub enum ExpertiseLevel { Novice, Competent, Expert, Authority }

    /// Compensation tiers. PLACEHOLDERS — Phase 0 evidence determines real values.
    #[derive(Debug, Clone)]
    pub enum CompensationTier {
        /// Quick check (~1-2 hours): £50-100
        Tier1 { amount_pence: u64 },
        /// Standard validation (~4-8 hours): £200-400
        Tier2 { amount_pence: u64 },
        /// Comprehensive review (~16+ hours): £800-1600
        Tier3 { amount_pence: u64 },
    }

    /// Incentive types — compensation is one of several motivators.
    #[derive(Debug, Clone)]
    pub enum ValidatorIncentive {
        CreditRecognition { credit_type: CreditType },
        DirectPayment { amount_pence: u64, currency: String },
        ReputationGain { increase: f64 },
        CareerAdvancement { validation_count: u32 },
    }

    #[derive(Debug, Clone)]
    pub enum CreditType {
        ValidationExecution,
        MethodologyReview,
        FormalAnalysis,
        Software,
    }

    /// Time tracking with audit flags for anomaly detection.
    #[derive(Debug, Clone)]
    pub struct TimeTracking {
        pub reported_hours: f64,
        pub expected_range: (f64, f64),
        pub audit_flags: Vec<AuditFlag>,
    }

    #[derive(Debug, Clone)]
    pub enum AuditFlag {
        TooFast { expected_min: f64, actual: f64 },
        TooSlow { expected_max: f64, actual: f64 },
        InactivityPeriods { gap_count: u32 },
    }

    /// Anti-gaming constraints built into the incentive structure.
    #[derive(Debug, Clone)]
    pub struct IncentiveConstraints {
        /// No bonuses for finishing fast
        pub no_speed_incentives: bool,
        /// Quality multiplier for thorough work
        pub quality_multiplier: f64,
        /// Bonus for cross-discipline validation
        pub cross_discipline_bonus: f64,
        /// Bonus for discovering legitimate disagreement
        pub disagreement_discovery_bonus: f64,
        /// Penalty for homophily (>90% agreement with single institution)
        pub homophily_penalty: f64,
    }
}

// =============================================================================
// LAYER 7: INTEGRATION & INTERFACE
// =============================================================================
//
// Purpose: How external systems plug into ValiChord. Journals, funders, and
// institutions query ValiChord. ValiChord is infrastructure, not a silo.

pub mod layer7_integration {
    use super::*;
    use super::layer2_validation::ValidationTier;
    use super::layer5_output::*;

    /// Journal integration — query validation status, require validation,
    /// display badges.
    pub trait JournalIntegration {
        fn check_validation_status(
            &self, manuscript_id: &str,
        ) -> Result<HarmonyRecord>;

        fn require_validation(
            &self, article_type: &str, minimum_tier: ValidationTier,
        ) -> Result<ValidationRequirement>;

        fn get_reproducibility_badge(
            &self, doi: &str,
        ) -> Result<ReproducibilityBadge>;
    }

    /// Funder integration — compliance checking and portfolio dashboards.
    pub trait FunderIntegration {
        fn check_grant_compliance(
            &self, grant_id: &str,
        ) -> Result<ComplianceReport>;

        fn portfolio_risk_dashboard(
            &self, funder_id: &str,
        ) -> Result<PortfolioDashboard>;
    }

    /// Repository integration — link OSF projects, GitHub repos.
    pub trait RepositoryIntegration {
        fn link_osf_project(
            &self, osf_id: &str, protocol_id: Hash,
        ) -> Result<()>;

        fn link_github_commits(
            &self, repo: &str, commits: &[String], protocol_id: Hash,
        ) -> Result<()>;

        fn get_repo_validation_badge(
            &self, repo: &str,
        ) -> Result<String>;
    }

    #[derive(Debug, Clone)]
    pub struct ValidationRequirement {
        pub minimum_tier: ValidationTier,
        pub required_validators: u8,
        pub deadline: Option<DateTime>,
    }

    #[derive(Debug, Clone)]
    pub struct ComplianceReport {
        pub grant_id: String,
        pub total_outputs: u32,
        pub validated_outputs: u32,
        pub compliance_percentage: f64,
        pub non_compliant_items: Vec<String>,
    }

    #[derive(Debug, Clone)]
    pub struct PortfolioDashboard {
        pub funder_id: String,
        pub total_grants: u32,
        pub grants_with_validated_outputs: u32,
        pub reproducibility_rate: f64,
        pub risk_items: Vec<String>,
    }

    // REST API endpoint definitions (for documentation — actual implementation
    // depends on the web framework used alongside Holochain)
    //
    // POST   /api/v1/protocols                    Submit new protocol
    // GET    /api/v1/protocols/{id}               Get protocol details
    // PUT    /api/v1/protocols/{id}/deviations    Declare deviation
    //
    // POST   /api/v1/validations                  Request validation
    // GET    /api/v1/validations/{id}             Get validation status
    // GET    /api/v1/validations/{id}/harmony     Get Harmony Record
    //
    // GET    /api/v1/researchers/{orcid}          Researcher portfolio
    // GET    /api/v1/institutions/{id}/metrics    Institutional metrics
    // GET    /api/v1/funders/{id}/portfolio       Funder portfolio
    //
    // GET    /api/v1/query/doi/{doi}
    // GET    /api/v1/query/osf/{osf_id}
    // GET    /api/v1/query/github/{repo}
}

// =============================================================================
// LAYER 8: ACCESS & PRESENTATION
// =============================================================================
//
// Purpose: Make the system legible to different audiences.
// This layer is primarily frontend (web dashboard, API responses).
// The Rust scaffold defines the view models.

pub mod layer8_presentation {
    use super::*;
    use super::layer5_output::*;

    /// Different audiences see different views of the same data.
    #[derive(Debug, Clone)]
    pub enum AudienceView {
        /// Researcher: their own studies, validation history, reputation
        Researcher(ResearcherDashboard),
        /// Validator: assigned tasks, completed validations, reputation
        Validator(ValidatorDashboard),
        /// Journal: manuscript validation status, badges
        Journal(JournalView),
        /// Funder: portfolio compliance, risk dashboard
        Funder(FunderView),
        /// Public: anonymised aggregate statistics
        Public(PublicView),
    }

    #[derive(Debug, Clone)]
    pub struct ResearcherDashboard {
        pub orcid: String,
        pub submitted_studies: Vec<StudySummary>,
        pub validation_history: Vec<HarmonyRecord>,
        pub badges: Vec<ReproducibilityBadge>,
    }

    #[derive(Debug, Clone)]
    pub struct ValidatorDashboard {
        pub validator_id: ValidatorId,
        pub active_tasks: Vec<TaskSummary>,
        pub completed_validations: u32,
        pub reputation_scores: HashMap<String, f64>,
        pub earnings: u64, // pence
    }

    #[derive(Debug, Clone)]
    pub struct JournalView {
        pub manuscript_id: String,
        pub validation_status: Option<HarmonyRecord>,
        pub badge: Option<ReproducibilityBadge>,
    }

    #[derive(Debug, Clone)]
    pub struct FunderView {
        pub funder_id: String,
        pub portfolio_compliance: f64,
        pub validated_grants: u32,
        pub total_grants: u32,
    }

    #[derive(Debug, Clone)]
    pub struct PublicView {
        pub total_validations: u64,
        pub total_studies: u64,
        pub overall_reproducibility_rate: f64,
        pub discipline_breakdown: HashMap<Discipline, f64>,
    }

    #[derive(Debug, Clone)]
    pub struct StudySummary {
        pub protocol_id: Hash,
        pub title: String,
        pub status: String,
        pub submitted_at: DateTime,
    }

    #[derive(Debug, Clone)]
    pub struct TaskSummary {
        pub task_id: Hash,
        pub study_title: String,
        pub assigned_at: DateTime,
        pub deadline: DateTime,
        pub status: String,
    }
}

// =============================================================================
// HOLOCHAIN-SPECIFIC ANNOTATIONS
// =============================================================================
//
// When implementing on Holochain, the following mappings apply:
//
// Rust struct → Holochain Entry (stored on agent's source chain)
//   - VerifiedDataSnapshot → Entry
//   - PreRegisteredProtocol → Entry
//   - ValidationRequest → Entry
//   - ValidationCommitment → Entry (commit phase)
//   - ValidationAttestation → Entry (reveal phase)
//   - HarmonyRecord → Entry
//   - AuditEvent → Entry
//
// Relationships → Holochain Links
//   - Protocol → DataSnapshot: Link
//   - Protocol → ValidationRequest: Link
//   - ValidationRequest → ValidationTask: Link
//   - ValidationTask → Attestation: Link
//   - Protocol → HarmonyRecord: Link
//
// Validation callbacks → Holochain validate() functions
//   - validate_create_entry: check data integrity, signatures
//   - validate_update_entry: check modification permissions
//   - validate_delete_entry: GDPR deletion rights
//   - validate_create_link: check relationship permissions
//
// Zome functions (public API):
//   - submit_protocol(protocol: PreRegisteredProtocol) -> ExternResult<Hash>
//   - request_validation(request: ValidationRequest) -> ExternResult<Hash>
//   - submit_commitment(commitment: ValidationCommitment) -> ExternResult<()>
//   - reveal_attestation(reveal: ValidationReveal) -> ExternResult<()>
//   - get_harmony_record(protocol_id: Hash) -> ExternResult<HarmonyRecord>
//   - get_provenance(protocol_id: Hash) -> ExternResult<ProvenanceGraph>
//
// Signal handlers (real-time notifications):
//   - signal_validation_assigned(validator_id, task_id)
//   - signal_all_committed(validation_id) → triggers reveal phase
//   - signal_harmony_record_ready(protocol_id)
//
// DHT queries:
//   - get_validators_by_discipline(discipline) → Vec<ValidatorProfile>
//   - get_active_validations(validator_id) → Vec<ValidationTask>
//   - get_institution_metrics(institution) → InstitutionalMetrics
//
// IMPORTANT: The Holochain HDK API evolves. The exact derive macros,
// entry definitions, and zome function signatures should be adapted to
// the current SDK version at implementation time. This scaffold defines
// WHAT the system does. The HDK determines HOW it's expressed.
//
// For current HDK documentation: https://docs.rs/hdk/latest/hdk/
// For Holochain developer portal: https://developer.holochain.org/

// =============================================================================
// TESTS (placeholder structure)
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_difficulty_assessment_placeholder_weights() {
        // Easy study: good docs, few deps, public data
        let easy = layer2_validation::DifficultyAssessment::compute(
            2, // code volume: low
            1, // dependency count: low
            5, // documentation: excellent
            5, // data accessibility: excellent
            1, // environment complexity: low
            1, // study age: recent
        );
        assert_eq!(easy.predicted_tier, layer2_validation::DifficultyTier::Standard);
    }

    #[test]
    fn test_difficulty_assessment_hard_study() {
        // Hard study: poor docs, many deps, restricted data
        let hard = layer2_validation::DifficultyAssessment::compute(
            4, // code volume: high
            5, // dependency count: high
            1, // documentation: poor
            1, // data accessibility: restricted
            4, // environment complexity: high
            4, // study age: old
        );
        assert!(matches!(
            hard.predicted_tier,
            layer2_validation::DifficultyTier::Complex
            | layer2_validation::DifficultyTier::Extreme
        ));
    }

    #[test]
    fn test_time_locked_modification_substantial_impact_requires_governance() {
        let mut locked = layer1_intake::TimeLocked {
            inner: layer1_intake::AnalysisPlan {
                description: "Original plan".into(),
                statistical_methods: vec![],
                software_requirements: vec![],
            },
            locked_at: SystemTime::now(),
            locked_hash: [0u8; 32],
            modification_history: vec![],
        };

        let result = locked.request_modification(
            layer1_intake::Modification {
                changed_at: SystemTime::now(),
                justification: "Changed primary outcome".into(),
                impact: layer1_intake::EpistemicImpact::Substantial,
                approver: [0u8; 32],
            },
            "Changed primary outcome".into(),
            layer1_intake::EpistemicImpact::Substantial,
            [0u8; 32],
        );

        assert!(result.is_err());
    }

    #[test]
    fn test_assignment_constraints_defaults() {
        let constraints = layer2_validation::AssignmentConstraints::default();
        assert_eq!(constraints.min_validators, 3);
        assert!(constraints.double_blind);
        assert!((constraints.max_institutional_share - 0.4).abs() < f64::EPSILON);
    }
}
