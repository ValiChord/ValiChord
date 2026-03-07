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
//   - ValiChord Open Design Questions (14 unresolved engineering questions)
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

/// SHA-256 digest — used for research file fingerprints (data, code, protocols).
/// This is the researcher-facing hash: content-addressed identification of study
/// materials, compatible with academic repositories (Zenodo, Figshare, etc.).
///
/// Note: Holochain uses BLAKE2b internally for addressing Actions and DHT records.
/// These are separate layers — SHA-256 identifies *what was validated*,
/// BLAKE2b addresses *the validation actions themselves*.
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

    /// Hash a research dataset for transmission to the Attestation DHT.
    ///
    /// Privacy by architecture: sensitive data never enters the shared DHT —
    /// it stays in the private Researcher Repository DNA. Only this hash travels
    /// to the Attestation layer. This is data minimisation enforced structurally,
    /// not just by policy.
    ///
    /// Note on salting: Holochain Actions already carry unique properties
    /// (identity + timestamp, carried forward through chaining), so explicit
    /// random salting is unnecessary for Action/Record hashes. For *research
    /// data* hashes (where the content being hashed is a dataset, not a
    /// Holochain action), salting may still be warranted to prevent pre-image
    /// attacks on known datasets. Salt is transmitted off-DHT from data
    /// custodian to validator. Serialisation consistency (identical byte
    /// representation before hashing) is the more fundamental concern.
    pub fn hash_dataset_with_salt(data: &[u8], salt: &[u8]) -> Hash {
        // TODO: Use proper SHA-256 via an external crate (ring or sha2).
        // Holochain has no built-in SHA-256 function — its native hashing is
        // Blake2b-256 (used internally for Actions and DHT addressing).
        // SHA-256 must come from an external crate compiled into the WASM zome.
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
        PrivateEntrySealed { sealed_at: DateTime },
        CountersigningSessionOpen,
        HarmonyRecordCountersigned { harmony_record: Hash },
        Completed,
        Withdrawn { reason: String },
        TimedOut,
    }

    // ---- Blind Commitment Protocol ----
    // Holochain mechanism: each validator records findings as a PRIVATE ENTRY
    // on their own source chain (the commitment). Private entries are sealed
    // by the validator's signing key and invisible to other validators and
    // the shared DHT — but their existence and authorship is verifiable on-chain.
    //
    // Once all validators have sealed private entries, a COUNTERSIGNING SESSION
    // is initiated: all parties simultaneously contribute their findings to
    // construct the shared Harmony Record entry. Each validator's chain is locked
    // during the session — no validator can observe another's findings and
    // adjust their own position. All parties countersign the Harmony Record
    // atomically. This is the reveal: simultaneous, not sequential.
    //
    // This maps onto Holochain's native countersigning affordance — the
    // PreflightRequest / countersigning flow described in the Holochain white
    // paper (v2.0, Appendix A). The private entry IS the commitment.
    // The countersigning session IS the reveal.

    /// Phase 1 — Blind commitment: validator seals findings as a private entry
    /// on their local Validator Workspace DNA source chain.
    /// Not published to any shared DHT. Only the validator can read the content.
    /// Existence is verifiable; content is not visible until reveal.
    #[derive(Debug, Clone)]
    pub struct ValidatorPrivateAttestation {
        pub validator_id: ValidatorId,
        pub validation_id: Hash,
        /// Full attestation, stored as a private entry — sealed, immutable,
        /// not shared until the countersigning session begins.
        pub attestation: ValidationAttestation,
        pub sealed_at: DateTime,
        pub signature: Signature,
    }

    /// Phase 2 — Simultaneous reveal via countersigning session.
    /// Initiated once all assigned validators have sealed private entries.
    /// All validators contribute findings simultaneously; chains are locked
    /// during the session to prevent last-mover adjustment.
    /// Output: a countersigned Harmony Record entry on the shared Attestation DNA.
    #[derive(Debug, Clone)]
    pub struct CountersigningSessionRequest {
        pub validation_id: Hash,
        /// All assigned validators must participate
        pub signing_agents: Vec<ValidatorId>,
        /// Session window — all validators must respond within this period
        pub session_timeout: Duration,
        /// The Harmony Record entry that all parties will countersign
        pub harmony_record_entry_hash: Hash,
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
            // NOTE: With Holochain countersigning, the "reveal" is the countersigning
            // session itself — validators cannot participate without their private entry
            // already sealed. Hash verification against a separately submitted commitment
            // is not required; the private entry IS the commitment, and the countersigning
            // session enforces simultaneous reveal. This function is a placeholder for
            // any additional post-session integrity checks an engineer identifies.
            true
        }

        /// Check for gaming patterns across a validator's history.
        /// Called from coordinator zome logic — NOT from validate() callbacks.
        /// Validation callbacks must be deterministic (no historical queries, no
        /// time-dependent logic). Gaming detection is inherently statistical and
        /// time-dependent, so it belongs here in coordinator logic, called
        /// explicitly before key interactions (e.g. before admitting a validator
        /// to a countersigning session).
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
            //
            // WARRANTS: Holochain's enforcement mechanism (stabilised in v0.7).
            // When a participant violates the Attestation DNA's validation rules,
            // any peer detecting the violation creates and signs a warrant —
            // a cryptographic proof of the bad action — published to the network.
            // Warrants are permanent and discoverable via get_agent_activity().
            // Current behaviour: warrants are created, persisted, and queryable.
            // Automatic network-level blocking of warranted agents is on Holochain's
            // roadmap but not yet shipped — the application layer (here) is
            // responsible for gating interactions with warranted validators in the
            // interim (e.g. reject their commitments in the commit-reveal phase).
            // GamingFlags detected here are the evidence base for peer-issued warrants.
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
    // depends on the web framework used alongside Holochain).
    //
    // HTTP GATEWAY: Holochain's HTTP Gateway (released March 2025, v0.2 July 2025)
    // provides the bridge between these REST endpoints and the running Holochain
    // application. External systems — journals, funders, institutional platforms —
    // query ValiChord via standard HTTP without needing to run a Holochain node.
    // The Governance/Harmony Records DNA is the primary target for external queries
    // (publicly readable). The Gateway handles translation to Holochain behind the
    // scenes. This is solved infrastructure, not custom development.
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
// The LinkTypes enum below and the path table make these relationships
// queryable. Without them, data is stored but not discoverable —
// Holochain has no global query; every collection must be traversable
// via get_links(base, link_type) from a known anchor or path.

/// Link types — defined per DNA, not shared across DNAs.
/// Each DNA's integrity zome gets its own #[hdk_link_types] enum.
///
/// Paths for collection discovery (no global query exists in Holochain):
///   "studies\0{institution_id}"              → all studies from an institution
///   "studies\0status\0{active|completed}"    → studies by status
///   "validations\0{discipline_slug}"         → validations by discipline
///   "validators\0{tier}"                     → validators by certification tier
///
/// Hotspot prevention: at Phase 2+ scale, prefix path components with
///   "<width>:<depth>#"  e.g. "2:1#cardiff_university"
/// to shard large collections across the DHT hash space. Not needed at
/// Phase 0/1 scale. Lives in coordinator logic only — does not affect
/// these enums or the integrity zomes.

// --- Attestation DNA integrity zome ---
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AttestationLinkTypes {
    StudyToValidation,      // study entry → all validation entries for that study
    ValidatorToValidation,  // agent pubkey → all validations authored by that agent
    StudyToHarmonyRecord,   // study entry → resulting harmony record (not reverse)
    StudyStatusPath,        // path anchor → study entry (queryable by status)
    InstitutionPath,        // path anchor → study entry (queryable by institution)
    DisciplinePath,         // path anchor → validation entry (queryable by discipline)
}

// --- Governance DNA integrity zome ---
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GovernanceLinkTypes {
    ValidatorToReputation,  // agent pubkey → reputation record
}

// --- Researcher Repository DNA integrity zome (private membrane) ---
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RepositoryLinkTypes {
    StudyToDataset,         // study entry → dataset entries (never leaves private DNA)
}

/// Op variants relevant to ValiChord's validation rules.
/// Simplified stand-in for Holochain's Op enum — the real implementation
/// uses op.flattened::<EntryTypes, LinkTypes>() to pattern match.
/// Full Rust stubs with HDK types are in the Technical Reference.
#[derive(Debug)]
pub enum ValidateOpType {
    UpdateStudy    { original_author: AgentId },
    DeleteStudy    { original_author: AgentId },
    UpdateAttestation,
    DeleteAttestation,
    /// signed_count: sum of successful + partial + failed + inconclusive
    /// from ValidationSummary — HarmonyRecord has no validator_signatures field
    CreateHarmonyRecord { signed_count: u8, total_validators: u8 },
    Other,
}

/// Stub for the unified validate(op: Op) callback (integrity zome).
///
/// Modern Holochain uses ONE unified callback, not per-action callbacks.
///
/// CRITICAL ORDERING: guarded arms (attestation immutability) MUST come
/// before unguarded arms (author check). Rust evaluates match arms in
/// order — if the unguarded arm comes first it catches everything and the
/// guarded arms below it are unreachable. The immutability guarantee
/// silently disappears without a compile error. This is the single most
/// important structural point in this stub.
///
/// Key rules:
///   1. ValidationAttestation entries: immutable after publication (no update/delete)
///   2. Study entries: only original author may update or delete
///   3. HarmonyRecord: all assigned validators must have submitted attestations
pub fn validate_stub(op_author: AgentId, op_type: ValidateOpType) -> Result<()> {
    match op_type {
        // Attestation immutability — MUST be first (see ordering note above)
        ValidateOpType::UpdateAttestation => {
            Err(ValiChordError::Unauthorized(
                "Validation attestations cannot be updated after publication".into()
            ))
        }
        ValidateOpType::DeleteAttestation => {
            Err(ValiChordError::Unauthorized(
                "Validation attestations cannot be deleted — the record is permanent".into()
            ))
        }
        // Author check for study entries — after attestation arms
        ValidateOpType::UpdateStudy { original_author } |
        ValidateOpType::DeleteStudy { original_author } => {
            if op_author != original_author {
                return Err(ValiChordError::Unauthorized(
                    "Only the original author may modify or delete a study entry".into()
                ));
            }
            Ok(())
        }
        // HarmonyRecord: check via validation_summary fields (the actual struct
        // has no validator_signatures field — use successful + partial + failed
        // + inconclusive against total_validators)
        ValidateOpType::CreateHarmonyRecord { signed_count, total_validators } => {
            if signed_count < total_validators {
                return Err(ValiChordError::QuorumNotMet {
                    required: total_validators,
                    received: signed_count,
                });
            }
            Ok(())
        }
        ValidateOpType::Other => Ok(()),
    }
}

// Validation callback → single validate(op: Op) function (integrity zome)
//
//   Modern Holochain uses ONE unified callback, not per-action callbacks.
//   The Op enum covers all seven DHT operation types:
//     StoreRecord, StoreEntry, RegisterUpdate, RegisterDelete,
//     RegisterCreateLink, RegisterDeleteLink, RegisterAgentActivity.
//   Pattern-match on op.flattened::<EntryTypes, LinkTypes>() to dispatch.
//
//   ValiChord's required rules (see validate_stub above for shape;
//   see Technical Reference for full HDK Rust stubs):
//     RegisterUpdate / RegisterDelete on study entries:
//       → only the original author may modify or delete
//     RegisterUpdate / RegisterDelete on ValidationAttestation entries:
//       → INVALID always — attestations are immutable once published
//     StoreEntry on HarmonyRecord:
//       → validator_signatures.len() must equal required_validator_count
//     RegisterAgentActivity (CreateAgent):
//       → membrane proof must be valid
//
//   genesis_self_check() runs BEFORE network join (no DHT access) — check
//   membrane proof format only. validate() runs after join and can use
//   must_get_* to retrieve dependencies.
//
// CRITICAL CONSTRAINT: validate() callbacks must be fully deterministic.
//   No time-dependent logic, no historical queries, no statistical patterns.
//   This means gaming detection, collusion analysis, and reputation scoring
//   CANNOT live in validate() — they belong in coordinator zome functions,
//   called explicitly at the right moments (e.g. before accepting a commitment).
//
// IMPORTANT: Zomes come in two kinds — keep this distinction in mind at
// implementation time:
//
// INTEGRITY ZOMES: Define entry types and validation rules. Changing these
//   creates a new DNA hash, requiring migration. Keep small and stable.
//   ValiChord's entry type definitions (VerifiedDataSnapshot, ValidationAttestation,
//   HarmonyRecord etc.) and membrane proof logic belong here.
//
// COORDINATOR ZOMES: Implement application logic and the public zome function API.
//   Can be updated on a running network without migration — governance decisions
//   in Phase 2+ can update thresholds, standards, and business logic without
//   requiring every participant to reinstall. ValiChord's assignment logic,
//   gaming detection, agreement analysis, and governance rules belong here
//   where possible.
//
// Getting this split right during MVP design matters. Moving logic from
// coordinator to integrity later is disruptive; the other direction is easy.
//
// Zome functions (public API):
//   - submit_protocol(protocol: PreRegisteredProtocol) -> ExternResult<Hash>
//   - request_validation(request: ValidationRequest) -> ExternResult<Hash>
//   - submit_commitment(commitment: ValidationCommitment) -> ExternResult<()>
//   - reveal_attestation(reveal: ValidationReveal) -> ExternResult<()>
//   - get_harmony_record(protocol_id: Hash) -> ExternResult<HarmonyRecord>
//   - get_provenance(protocol_id: Hash) -> ExternResult<ProvenanceGraph>
//
// CROSS-DNA CALLS (within the same hApp instance):
//   Use hdk::p2p::call with CallTargetCell::OtherRole("dna_role_name").
//   Example: the Attestation DNA's coordinator zome calling the Governance DNA:
//     call(CallTargetCell::OtherRole("governance"), "governance", "get_standards", None, discipline)
//   The AUTHOR GRANT applies automatically: when the calling cell and the target
//   cell belong to the same agent (which is true for all four ValiChord DNAs on
//   a single node), no capability tokens are required. Cross-DNA coordination
//   within one researcher's or validator's node is therefore straightforward.
//
//   IMPORTANT CONSTRAINT: call_remote() only works between agents within the
//   SAME DNA's network. You cannot call_remote across different DNAs.
//   Alice's Attestation DNA can call_remote to Bob's Attestation DNA.
//   Alice's Attestation DNA CANNOT call_remote to Bob's Researcher Repository DNA.
//   Data from private DNAs must be passed explicitly by the owning agent — it
//   cannot be pulled remotely. All peer-to-peer coordination between validators
//   happens within the Attestation DNA's shared network.
//
// IDENTIFIERS — note for implementation:
//   The scaffold uses `pub type Hash = [u8; 32]` as a simplification.
//   In the Holochain implementation, distinguish:
//   - ExternalHash: the correct type for SHA-256 research file fingerprints.
//     ExternalHash accepts any 32-byte external identifier, serves as a DHT
//     link anchor without Holochain storing content at the address. Use this
//     for content_id / sha256_hash fields in VerifiedDataSnapshot.
//   - EntryHash / ActionHash: for Holochain-native data (attestations, records).
//   - AgentPubKey: for participant identities (replaces AgentId in the scaffold).
//
// TWO DISTINCT ACCESS MODELS — do not conflate:
//
//   Model A — LOCAL FRONT END (researcher UI, validator UI):
//     Connects via AppWebsocket.connect() over a local WebSocket interface.
//     This interface is ONLY exposed to processes on the same device — it is
//     not reachable from the network. The UI must be distributed with the hApp
//     and a Holochain runtime (hc-spin for dev, Kangaroo/p2p Shipyard for prod).
//     Layer 8 dashboards (ResearcherDashboard, ValidatorDashboard) are served
//     this way. The front end calls coordinator zome functions directly via
//     appWs.callZome() and listens to signals via appWs.on("signal", handler).
//     Security implication: no remote process can reach a participant's conductor
//     without being on their local device. This is a hard boundary, not policy.
//
//   Model B — EXTERNAL HTTP GATEWAY (journals, funders, institutional platforms):
//     Uses the Holochain HTTP Gateway (v0.2, July 2025) to reach the
//     Governance/Harmony Records DNA over standard HTTP/REST. External callers
//     do not run a Holochain node — the Gateway translates HTTP requests into
//     zome calls behind the scenes. Only publicly readable data in the
//     Governance DNA is exposed this way. Private DNA data (Researcher Repository,
//     Validator Workspace) is never reachable via this path.
//     Layer 7 REST endpoints (/api/v1/protocols, /api/v1/validations/*/harmony
//     etc.) are served this way.
//
//   These two models must be kept architecturally separate. Layer 8 view models
//   (ResearcherDashboard, ValidatorDashboard) are populated by local zome calls.
//   Layer 7 integration traits (JournalIntegration, FunderIntegration) are
//   satisfied by the HTTP Gateway. They do not share a code path.
//
// TWO DISTINCT ACCESS MODELS — keep these separate in your mental model:
//
//   MODEL A: Participant UIs (researcher dashboard, validator dashboard)
//     These are LOCAL front ends. They run on the same device as the conductor
//     and connect via AppWebsocket.connect() over a local WebSocket interface.
//     Holochain only exposes this interface to processes on the same device —
//     no remote process can reach it. This is a security guarantee, not just
//     an implementation choice. The Layer 8 ResearcherDashboard and
//     ValidatorDashboard views are served to these local front ends only.
//     Distribution: Kangaroo or p2p Shipyard bundles conductor + UI together.
//
//   MODEL B: External systems (journals, funders, institutional platforms)
//     These are REMOTE HTTP clients. They cannot connect to a participant's
//     local WebSocket. Instead, they query ValiChord via the HTTP Gateway
//     (Holochain v0.4+), which translates HTTP requests to zome calls on an
//     always-on Holochain node running the Governance/Harmony Records DNA.
//     Only publicly readable data is exposed this way. The Layer 7
//     JournalIntegration and FunderIntegration traits describe this path.
//
//   DO NOT conflate these. A journal cannot call a researcher's local zome
//   functions directly. A researcher's UI does not go through the HTTP Gateway.
//   The Governance/Harmony Records DNA is the only DNA that needs to be
//   reachable externally — keep it on an always-on node for that purpose.
//
// Signal handlers (UI notifications only — emit_signal / send_remote_signal):
//   - signal_validation_assigned(validator_id, task_id)   → notifies validator's UI
//   - signal_harmony_record_ready(protocol_id)            → notifies researcher's UI
//
//   CRITICAL: Signals are SEND-AND-FORGET. No delivery confirmation, no persistence,
//   no guarantee of receipt if the peer is offline. You CANNOT use a signal to
//   trigger a protocol phase transition (e.g. moving from commit phase to reveal
//   phase). If a validator is offline when the signal fires, the transition never
//   happens for them.
//
//   Phase transitions must be driven by COORDINATOR ZOME FUNCTIONS that poll the
//   DHT for state: check whether all expected validators have written commitment
//   entries, then proceed. Signals are appropriate for notifying UIs that something
//   is ready to act on — the protocol machinery underneath must be state-based, not
//   event-based.
//
//   Remote signals (send_remote_signal) also require the target function
//   recv_remote_signal to have an UNRESTRICTED capability grant, set up in the
//   init() callback of that cell. See CAPABILITY GRANTS below.
//
// CAPABILITY GRANTS — required per cell, set up in init():
//   Zome functions in a cell are inaccessible to any external caller until the
//   agent creates explicit capability grants. A grant only covers ONE cell.
//   ValiChord needs grants set up in the init() callback of each DNA that
//   receives remote calls or signals:
//
//   Unrestricted (anyone can call, no secret):
//     - recv_remote_signal in Attestation DNA (required for send_remote_signal)
//     - Any public read functions in Governance/Harmony Records DNA (journals,
//       funders, HTTP Gateway access to public Harmony Records)
//
//   Assigned (specific agents only, requires secret):
//     - Commit/reveal functions if you want to restrict to credentialed validators
//
//   Same-agent calls (all four ValiChord DNAs running on one node) are covered
//   by the author grant — no explicit capability required.
//
//   Without an init() callback creating these grants, remote callers will receive
//   ZomeCallResponse::Unauthorized even for functions you intend to be public.
//

//   - get_validators_by_discipline(discipline) → Vec<ValidatorProfile>
//   - get_active_validations(validator_id) → Vec<ValidationTask>
//   - get_institution_metrics(institution) → InstitutionalMetrics
//
// DNA PROPERTIES — per-network constants accessible in validation:
//   Use the #[dna_properties] macro on a struct to embed configuration into the
//   DNA hash. These are immutable for the lifetime of a network instance.
//   ValiChord uses cases:
//     - authorized_joining_certificate_issuer: AgentPubKey of the institutional
//       authority whose signatures are valid membrane proofs for this network
//     - discipline: String identifying the validation domain (e.g. "genomics")
//     - minimum_validators: u32 threshold baked into this network's rules
//   Changing properties creates a new DNA hash = a new network. Use for
//   configuration that must be stable and tamper-evident across the network.
//
// TWO-STAGE MEMBRANE PROOF validation for the Attestation DNA:
//   Stage 1 — genesis_self_check(): runs BEFORE network join, no DHT access.
//     Check format only: is this a valid-length signature blob? Is it decodable?
//     Protects the joining agent from accidentally committing a malformed proof.
//   Stage 2 — validate_agent_joining() in validate(): runs AFTER network join,
//     has DHT access. Full validation: does the signing authority exist on the
//     DHT? Is their own credential valid? Is this signature over the agent's key?
//   Both stages must agree — validate_agent_joining() must cover at least
//   everything genesis_self_check() covers, and add the DHT-dependent checks.
//
//   NOTE: A coordinator zome can currently only safely depend on ONE integrity
//   zome (known bug in dependency mapping). Always list the dependency explicitly
//   in dna.yaml even when there is only one integrity zome.
//
 The exact derive macros,
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
