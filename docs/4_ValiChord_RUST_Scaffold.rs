// =============================================================================
// ValiChord — Distributed Validation Infrastructure for Computational Research
// =============================================================================
//
// ARCHITECTURE SCAFFOLD — NOT PRODUCTION CODE
//
// This file captures ValiChord's architecture as Rust types, traits, and stub
// implementations, organised around the four Holochain DNA membranes.
//
// Status:
//   - Types: Structured around the correct four-DNA architecture
//   - Trait definitions: Complete — these define the system's API surface
//   - Implementations: Stubs only — marked with TODO for Phase 1 engineering
//   - Holochain integration: Annotated with HDK patterns (entry macros, link
//     types, validate callback) — adapt to current SDK version at build time
//
// What this IS:
//   - A type-level specification of ValiChord's data model per DNA
//   - A trait-level specification of ValiChord's behaviour
//   - A guide for Phase 1 engineering decisions
//   - The starting point for the scaffolding session with Arthur Brock
//
// What this is NOT:
//   - Compilable against the current Holochain HDK (entry macros and zome
//     function signatures need adapting to the current SDK version)
//   - Production-ready (no error handling, no tests, no persistence)
//   - A substitute for Phase 0 evidence (compensation tiers, difficulty
//     weights, and thresholds are all placeholders pending empirical data)
//
// Four-DNA Membrane Architecture:
//   DNA 1: Researcher Repository  — private membrane, researcher only
//   DNA 2: Validator Workspace    — private membrane, per validator
//   DNA 3: Attestation            — shared DHT, credentialed participants
//   DNA 4: Governance & Harmony   — public DHT, open read
//
// The old eight-layer conceptual framework (Layers 0–8) described what
// ValiChord does. The four-DNA structure describes how it is built.
// Layers still appear as comments where useful to explain purpose, but
// they are not the organising principle of the code.
//
// Companion documents:
//   - ValiChord Technical Reference (full architecture narrative)
//   - ValiChord Vision & Architecture (system-level design rationale)
//   - ValiChord Governance Framework (governance mechanics and anti-capture)
//   - ValiChord Phase 0 Proposal (the empirical study that informs all of this)
//
// Author: Ceri John (architecture), with AI assistance (scaffold generation)
// Date: March 2026
// Licence: Copyright held by author; will be open-sourced on funding
// =============================================================================

#![allow(dead_code, unused_variables)]

use std::collections::HashMap;
use std::time::Duration;

// =============================================================================
// COMMON TYPES
// =============================================================================
//
// These types are used across multiple DNAs. In the actual implementation,
// shared types should be defined in a common crate imported by each DNA's
// integrity zome rather than duplicated.

/// SHA-256 digest — used for research file fingerprints (data, code, protocols).
/// This is the researcher-facing hash: content-addressed identification of study
/// materials, compatible with academic repositories (Zenodo, Figshare, etc.).
///
/// Note: Holochain uses BLAKE2b internally for addressing Actions and DHT records.
/// These are separate layers — SHA-256 identifies *what was validated*,
/// BLAKE2b addresses *the validation actions themselves*.
pub type ExternalHash = [u8; 32];

/// UTC timestamp. All ValiChord events are timestamped for audit and provenance.
/// In the actual Holochain implementation, use Holochain's native `Timestamp`
/// type from the HDK — it provides microsecond precision and integrates with
/// source chain sequencing.
pub type DateTime = u64; // microseconds since Unix epoch (placeholder)

/// Holochain AgentPubKey equivalent. Each participant has a unique cryptographic
/// identity derived from their keypair.
///
/// IMPORTANT: In Holochain, AgentPubKey is 39 bytes — NOT 32. It carries a
/// multihash protocol prefix and a DHT location suffix in addition to the
/// 32-byte key material. Using [u8; 32] here would be structurally wrong in
/// the actual implementation. Use `AgentPubKey` from the HDK directly.
///
/// This type alias is used throughout the scaffold for readability. Replace
/// with the HDK's `AgentPubKey` type at implementation time.
pub type AgentId = Vec<u8>; // 39 bytes in practice; Vec used here to avoid hardcoding wrong size

/// Alias for readability when the agent is acting as a validator.
pub type ValidatorId = AgentId;

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

/// Error types. Intentionally broad at scaffold stage.
#[derive(Debug)]
pub enum ValiChordError {
    NotFound(String),
    Unauthorized(String),
    ValidationFailed(String),
    GovernanceRequired(String),
    HashMismatch { expected: ExternalHash, actual: ExternalHash },
    QuorumNotMet { required: u8, received: u8 },
    HolochainError(String),
}

pub type Result<T> = std::result::Result<T, ValiChordError>;

// =============================================================================
// DNA 1: RESEARCHER REPOSITORY
// =============================================================================
//
// Private membrane — only the researcher (and their institution, if they choose
// to share access) can join this DNA. Nothing sensitive ever leaves this space.
//
// The researcher publishes only a cryptographic commitment outward to the
// Attestation DNA: metadata and a hash. The membrane is the primary GDPR
// protection — data minimisation enforced structurally, not by policy.
//
// Integrity zome (hdi): entry types, link types, validate callback
// Coordinator zome (hdk): CRUD functions, init, post_commit

pub mod researcher_repository_dna {
    use super::*;

    // ---- Entry Types --------------------------------------------------------
    //
    // In the actual implementation, each struct must be decorated with:
    //   #[hdk_entry_helper]
    // and registered in an enum decorated with:
    //   #[derive(Serialize, Deserialize)]
    //   #[hdk_entry_types]
    //   #[unit_enum(UnitEntryTypes)]
    //   pub enum EntryTypes { ... }
    //
    // Without these macros the entries cannot be stored on the source chain.

    /// Content-addressed, tamper-evident data snapshot.
    /// Stored as a private entry in this DNA — never enters the shared DHT.
    ///
    /// Note: Holochain Actions already carry author key, signature, and
    /// timestamp natively. These fields do not need to be duplicated inside
    /// entry structs — do not add `created_at` or `creator_id` to entries
    /// that Holochain itself timestamps and signs.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct VerifiedDataSnapshot {
        /// SHA-256 hash of the research files (the integrity fingerprint)
        pub sha256_hash: ExternalHash,
        /// Redundant storage locations — the hash is the guarantee, not the location
        pub storage_locations: Vec<StorageLocation>,
        pub size_bytes: u64,
    }

    /// Storage location is deliberately agnostic. The integrity guarantee
    /// comes from the content hash recorded on Holochain, not the storage system.
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

    /// Pre-registered protocol with committed analysis plan.
    ///
    /// In Holochain, immutability is not enforced by a "TimeLocked" wrapper —
    /// it is enforced by the architecture itself. All entries on the source
    /// chain are immutable once written. "Updates" in Holochain create new
    /// immutable records that mark the old ones as superseded, preserving
    /// the full modification history automatically. No application-level
    /// locking mechanism is needed or appropriate.
    ///
    /// Protocol modifications are recorded as new entries linked to the
    /// original via ProtocolVersionLink. The full history is always queryable.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct PreRegisteredProtocol {
        pub analysis_plan_description: String,
        pub hypotheses: Vec<Hypothesis>,
        pub analysis_type: AnalysisType,
        pub primary_outcomes: Vec<OutcomeMeasure>,
        pub secondary_outcomes: Vec<OutcomeMeasure>,
        pub stopping_rules: String,
        pub sample_size_n: usize,
        pub sample_size_justification: String,
        pub allowed_deviation_types: Vec<DeviationType>,
        pub institutional_approval: Option<Signature>,
        pub external_links: ExternalLinks,
    }

    /// Declared deviation from pre-registered plan.
    /// Each deviation is a new, immutable entry — not an update to the protocol.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct DeclaredDeviation {
        /// Links back to the original protocol
        pub protocol_ref: ExternalHash,
        pub deviation_type: DeviationType,
        pub justification: String,
        pub epistemic_impact: EpistemicImpact,
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
    pub struct OutcomeMeasure {
        pub name: String,
        pub specification: String,
    }

    /// Not all deviations are equal. This typology is one of ValiChord's
    /// key contributions — making deviation reporting structured rather than
    /// free-text.
    #[derive(Debug, Clone)]
    pub enum DeviationType {
        DataAccess { reason: String, impact: EpistemicImpact },
        EthicalConcern { review_board: String },
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
        Minimal,
        Moderate,
        Substantial, // Triggers governance review
    }

    #[derive(Debug, Clone, Default)]
    pub struct ExternalLinks {
        pub osf_project: Option<String>,
        pub github_repo: Option<String>,
        pub preregistration_doi: Option<String>,
        pub trial_registry: Option<String>,
        pub publication_doi: Option<String>,
    }

    // ---- Link Types ---------------------------------------------------------
    //
    // Defined in the integrity zome. Each DNA has its own enum — not shared.

    // #[hdk_link_types]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum LinkTypes {
        /// protocol entry → dataset/snapshot entries for that protocol
        ProtocolToSnapshot,
        /// study entry → dataset entries (never leaves this private DNA)
        StudyToDataset,
        /// protocol entry → deviation entries (the modification history)
        ProtocolToDeviation,
    }

    // ---- Validate Callback --------------------------------------------------
    //
    // Researcher Repository DNA: the researcher is the only participant.
    // Standard Holochain source chain integrity (sequence numbers, author
    // signatures) is sufficient. No complex custom rules are needed.
    // genesis_self_check() and validate() can use default implementations.

    // ---- Coordinator Zome Functions -----------------------------------------
    //
    // These are the public API of this DNA:
    //   submit_protocol(protocol: PreRegisteredProtocol) -> ExternResult<ActionHash>
    //   declare_deviation(deviation: DeclaredDeviation) -> ExternResult<ActionHash>
    //   upload_snapshot(snapshot: VerifiedDataSnapshot) -> ExternResult<ActionHash>
    //   get_protocol(protocol_hash: ActionHash) -> ExternResult<Option<Record>>
    //   get_protocol_history(protocol_hash: ActionHash) -> ExternResult<Vec<Record>>

    /// Hash a research dataset with a salt before transmitting the fingerprint
    /// to the Attestation DNA.
    ///
    /// Privacy by architecture: sensitive data never enters the shared DHT —
    /// only this hash travels outward. Salt is transmitted off-DHT from data
    /// custodian to validator. The primary protection is the membrane separation;
    /// salting is a secondary layer for any summary properties that do travel.
    pub fn hash_dataset_with_salt(data: &[u8], salt: &[u8]) -> ExternalHash {
        // TODO: Use SHA-256 via an external crate (ring or sha2).
        // Holochain has no built-in SHA-256 — its native hashing is BLAKE2b.
        let mut combined = data.to_vec();
        combined.extend_from_slice(salt);
        [0u8; 32] // Placeholder
    }
}

// =============================================================================
// DNA 2: VALIDATOR WORKSPACE
// =============================================================================
//
// Private membrane, per validator — the "Repro Witnessing hApp."
// Each validator runs this locally. Only they can join.
//
// This is where the actual reproduction work happens:
//   - Validator receives study materials and task assignment
//   - Runs analysis in their local environment
//   - Records findings as a private entry (the commit phase)
//   - Only the signed attestation — never raw results — leaves this space
//
// Because the local app controls how data is serialised before hashing,
// outputs are consistent regardless of database query ordering or other
// non-deterministic operations outside the validator's control.

pub mod validator_workspace_dna {
    use super::*;
    use super::researcher_repository_dna::{
        DeviationType, EpistemicImpact, PreRegisteredProtocol,
        VerifiedDataSnapshot,
    };

    // ---- Entry Types --------------------------------------------------------

    /// A validation task assigned to this validator.
    /// Received from the Attestation DNA's coordinator via call().
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ValidationTask {
        pub task_id: ExternalHash,
        /// Reference to the ValidationRequest in the Attestation DNA
        pub request_ref: ExternalHash,
        pub protocol_summary: Option<PreRegisteredProtocol>,
        pub data_snapshot: VerifiedDataSnapshot,
        pub validation_focus: ValidationFocus,
        pub time_cap: Duration,
        pub estimated_time_range: (Duration, Duration),
        pub compensation_tier: CompensationTier,
    }

    /// Private attestation entry — the COMMIT phase.
    ///
    /// Stored as a private entry on this validator's source chain.
    /// Invisible to other validators and to the shared DHT.
    /// Its existence is verifiable on-chain; its contents are not visible
    /// until the validator participates in the countersigning reveal session.
    ///
    /// This is Holochain's native private entry mechanism — the sealed
    /// commitment is not a hash of results submitted elsewhere; it IS the
    /// entry, stored locally and invisible to peers until the reveal.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ValidatorPrivateAttestation {
        pub task_ref: ExternalHash,
        pub outcome: AttestationOutcome,
        pub detailed_report: String,
        pub time_invested: Duration,
        pub time_breakdown: TimeBreakdown,
        pub confidence: AttestationConfidence,
        pub deviation_flags: Vec<UndeclaredDeviation>,
        pub computational_resources: ComputationalResources,
    }

    #[derive(Debug, Clone)]
    pub enum ValidationFocus {
        ComputationalReproducibility,
        PreCommitmentAdherence,
        MethodologicalReview,
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

    /// Phase 0's four-category time breakdown — the primary data collection
    /// goal of the workload discovery pilot.
    #[derive(Debug, Clone)]
    pub struct TimeBreakdown {
        pub environment_setup: Duration,
        pub data_acquisition: Duration,
        pub code_execution: Duration,
        pub troubleshooting: Duration,
    }

    #[derive(Debug, Clone)]
    pub struct UndeclaredDeviation {
        pub deviation_type: DeviationType,
        pub severity: Severity,
        pub evidence: String,
    }

    #[derive(Debug, Clone)]
    pub enum Severity { Minor, Moderate, Major, Critical }

    #[derive(Debug, Clone)]
    pub struct ComputationalResources {
        pub personal_hardware_sufficient: bool,
        pub hpc_required: bool,
        pub gpu_required: bool,
        pub cloud_compute_required: bool,
        pub estimated_compute_cost_gbp: Option<f64>,
    }

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

    // ---- Link Types ---------------------------------------------------------

    // #[hdk_link_types]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum LinkTypes {
        /// task entry → private attestation entry for that task
        TaskToPrivateAttestation,
    }

    // ---- Validate Callback --------------------------------------------------
    //
    // Validator Workspace DNA: the validator is the only participant.
    // Standard source chain integrity is sufficient.
    // The private entry is the commitment — its existence is the proof.
    // No peers are validating this DNA so no custom membrane rules needed.

    // ---- Coordinator Zome Functions -----------------------------------------
    //
    //   receive_task(task: ValidationTask) -> ExternResult<ActionHash>
    //   seal_private_attestation(attestation: ValidatorPrivateAttestation) -> ExternResult<ActionHash>
    //   get_task(task_ref: ExternalHash) -> ExternResult<Option<Record>>
    //   get_my_attestation(task_ref: ExternalHash) -> ExternResult<Option<Record>>
    //
    // Note: seal_private_attestation writes a private entry — it never appears
    // in the DHT, only on this validator's local source chain.
    //
    // post_commit callback: after a private attestation is sealed, use
    // post_commit to send a remote signal to the Attestation DNA coordinator
    // that this validator's commitment is ready. The Attestation DNA then
    // polls to check whether all validators have sealed their commitments
    // before opening the reveal window.
    //
    // IMPORTANT: Signals are send-and-forget — they cannot drive protocol
    // phase transitions. The Attestation DNA coordinator must poll the DHT
    // for state (all expected validators sealed?) and not rely on signal delivery.
}

// =============================================================================
// DNA 3: ATTESTATION
// =============================================================================
//
// Shared DHT, credentialed participants (membrane proof required to join).
// This is the core shared layer.
//
// Records the *act* of validation: protocol registered, attestation submitted,
// warrant issued. Not the content of the research — only the signed outcome
// summary. All inter-validator coordination happens here because call_remote()
// only works between agents on the SAME DNA's network.
//
// Agreement detection operates on structured outcome summaries, not raw result
// hashes — because computational reproduction almost never produces bit-identical
// outputs due to floating point differences and hardware variation.

pub mod attestation_dna {
    use super::*;
    use super::researcher_repository_dna::{
        DeviationType, EpistemicImpact, DeclaredDeviation,
    };
    use super::validator_workspace_dna::{
        AttestationOutcome, AttestationConfidence, TimeBreakdown,
        ComputationalResources, Severity, ValidationFocus,
    };

    // ---- Entry Types --------------------------------------------------------

    /// A request to validate a study.
    /// Submitted by a researcher (or journal, funder) to kick off validation.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ValidationRequest {
        /// Reference to the PreRegisteredProtocol in the Researcher Repository DNA
        pub protocol_ref: Option<ExternalHash>,
        /// SHA-256 hash of the study data — the only thing from the private DNA
        /// that travels to this shared network
        pub data_hash: ExternalHash,
        pub num_validators_required: u8,
        pub validation_tier: ValidationTier,
        pub discipline: Discipline,
    }

    #[derive(Debug, Clone)]
    pub enum ValidationTier {
        Basic,       // Simple computational reproducibility
        Enhanced,    // Includes robustness checks
        Comprehensive, // Full methodological review
    }

    /// Validator's attested outcome — the REVEAL phase.
    ///
    /// This entry is written to the shared Attestation DHT during the
    /// countersigning session. At this point all validators simultaneously
    /// contribute their findings; each validator's chain is locked during
    /// the session to prevent any party adjusting their position after seeing
    /// others' results. This is the simultaneous reveal.
    ///
    /// The private attestation in the Validator Workspace DNA is the sealed
    /// commitment. This entry is the public attestation — the revealed finding.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ValidationAttestation {
        pub request_ref: ExternalHash,
        pub outcome: AttestationOutcome,
        /// Outcome summary — structured for agreement detection.
        /// Agreement is assessed on these summaries, not on raw result hashes,
        /// because exact hash matches are unrealistic across environments.
        pub outcome_summary: OutcomeSummary,
        pub time_invested: Duration,
        pub time_breakdown: TimeBreakdown,
        pub confidence: AttestationConfidence,
        pub deviation_flags: Vec<UndeclaredDeviation>,
        pub computational_resources: ComputationalResources,
    }

    /// Structured outcome for agreement detection across validators.
    /// What constitutes agreement is defined by discipline-specific standards
    /// in the Governance DNA.
    #[derive(Debug, Clone)]
    pub struct OutcomeSummary {
        pub key_metrics: Vec<MetricResult>,
        pub effect_direction_matches: Option<bool>,
        pub confidence_interval_overlap: Option<f64>,
        pub overall_agreement: AgreementLevel,
    }

    #[derive(Debug, Clone)]
    pub struct MetricResult {
        pub metric_name: String,
        pub produced_value: String,
        pub expected_value: String,
        pub within_tolerance: bool,
    }

    #[derive(Debug, Clone)]
    pub enum AgreementLevel {
        ExactMatch,
        WithinTolerance,
        DirectionalMatch,
        Divergent,
        UnableToAssess,
    }

    #[derive(Debug, Clone)]
    pub struct UndeclaredDeviation {
        pub deviation_type: DeviationType,
        pub severity: Severity,
        pub evidence: String,
    }

    /// Validator profile — their credentials, expertise, and availability.
    /// Published to the Attestation DHT so the assignment engine can query it.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ValidatorProfile {
        pub institution: String,
        pub disciplines: Vec<Discipline>,
        pub certification_tier: CertificationTier,
        pub available: bool,
        pub max_concurrent_tasks: u8,
    }

    #[derive(Debug, Clone)]
    pub enum CertificationTier {
        Provisional,  // < 10 completed validations
        Certified,    // ≥ 10 with good standing
        Senior,       // ≥ 50 with excellent standing
    }

    // Difficulty Assessment — lives in the Attestation DNA because it runs
    // on the incoming study hash and determines validator assignment params.

    /// Surface feature scores for predicting validation difficulty.
    /// Weights are PLACEHOLDERS — Phase 0 evidence determines real values.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct DifficultyAssessment {
        pub request_ref: ExternalHash,
        pub code_volume: u8,           // 1–5
        pub dependency_count: u8,      // 1–5
        pub documentation_quality: u8, // 1–5 (5 = excellent)
        pub data_accessibility: u8,    // 1–5 (5 = fully open)
        pub environment_complexity: u8,// 1–5
        pub study_age_years: u8,       // 1–5 (5 = very old)
        pub predicted_tier: DifficultyTier,
        pub predicted_time_range: (Duration, Duration),
        pub confidence: AssessmentConfidence,
    }

    #[derive(Debug, Clone, PartialEq)]
    pub enum DifficultyTier {
        Standard,  // ~4-8 hours
        Moderate,  // ~8-16 hours
        Complex,   // ~16-30 hours
        Extreme,   // ~30+ hours — flagged for triage
        Excluded,  // Fails minimum criteria
    }

    #[derive(Debug, Clone)]
    pub enum AssessmentConfidence { High, Medium, Low }

    #[derive(Debug, Clone)]
    pub struct ImprovementReport {
        pub request_ref: ExternalHash,
        pub overall_assessment: DifficultyTier,
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

    // ---- Link Types ---------------------------------------------------------

    // #[hdk_link_types]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum LinkTypes {
        /// study hash anchor → ValidationRequest entries for that study
        StudyToValidation,
        /// agent pubkey → ValidationAttestation entries authored by that agent
        ValidatorToAttestation,
        /// ValidationRequest → resulting HarmonyRecord (in Governance DNA)
        RequestToHarmonyRecord,
        /// path anchor → ValidationRequest (queryable by status)
        StudyStatusPath,
        /// path anchor → ValidationRequest (queryable by institution)
        InstitutionPath,
        /// path anchor → ValidationAttestation (queryable by discipline)
        DisciplinePath,
        /// agent pubkey → ValidatorProfile entry
        AgentToProfile,
    }

    // ---- Validate Callback (Attestation DNA) --------------------------------
    //
    // This is the most important integrity zome in ValiChord.
    // Rules enforced here cannot be relaxed after deployment without
    // migrating to a new DNA.
    //
    // CRITICAL ORDERING: guarded arms (attestation immutability) MUST come
    // before unguarded arms (author check). Rust evaluates match arms in
    // order — if the unguarded arm comes first it catches everything and the
    // guarded arms below it are unreachable. The immutability guarantee
    // silently disappears without a compile error.

    /*
    #[hdk_extern]
    pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
        match op.flattened::<EntryTypes, LinkTypes>()? {

            // 1. ValidationAttestation entries: IMMUTABLE after publication.
            //    MUST be first — see ordering note above.
            FlatOp::RegisterUpdate(OpUpdate { original_action, .. })
                if matches!(
                    must_get_action(original_action.clone())?.action().entry_type(),
                    Some(EntryType::App(app)) if app.id() == EntryTypesId::ValidationAttestation
                ) =>
            {
                Ok(ValidateCallbackResult::Invalid(
                    "Validation attestations cannot be updated after publication".into()
                ))
            }

            FlatOp::RegisterDelete(OpDelete { original_action, .. })
                if matches!(
                    must_get_action(original_action.clone())?.action().entry_type(),
                    Some(EntryType::App(app)) if app.id() == EntryTypesId::ValidationAttestation
                ) =>
            {
                Ok(ValidateCallbackResult::Invalid(
                    "Validation attestations cannot be deleted — the record is permanent".into()
                ))
            }

            // 2. Study/ValidationRequest entries: only original author may update or delete.
            //    After the attestation immutability arms — see ordering note.
            FlatOp::RegisterUpdate(OpUpdate { original_action, .. }) => {
                let original = must_get_action(original_action)?;
                if op.action().author() != original.action().author() {
                    return Ok(ValidateCallbackResult::Invalid(
                        "Only the original requester may update a validation request".into()
                    ));
                }
                Ok(ValidateCallbackResult::Valid)
            }

            FlatOp::RegisterDelete(OpDelete { original_action, .. }) => {
                let original = must_get_action(original_action)?;
                if op.action().author() != original.action().author() {
                    return Ok(ValidateCallbackResult::Invalid(
                        "Only the original requester may delete a validation request".into()
                    ));
                }
                Ok(ValidateCallbackResult::Valid)
            }

            // 3. Membrane proof validation (RegisterAgentActivity: CreateAgent)
            //    — full verification happens here, after network join.
            //    genesis_self_check() handles format-only check before join.
            FlatOp::RegisterAgentActivity(OpActivity::CreateAgent { membrane_proof, .. }) => {
                validate_membrane_proof(membrane_proof)
            }

            _ => Ok(ValidateCallbackResult::Valid),
        }
    }

    // Two-stage membrane proof validation for the Attestation DNA:
    //   Stage 1 — genesis_self_check(): runs BEFORE network join, no DHT access.
    //     Check format only: is this a valid-length signature blob?
    //   Stage 2 — validate_agent_joining() in validate(): runs AFTER network join.
    //     Full validation: is the signing authority on the DHT? Is the signature
    //     over the agent's key? Is the issuer's credential itself valid?
    fn validate_membrane_proof(
        membrane_proof: Option<MembraneProof>
    ) -> ExternResult<ValidateCallbackResult> {
        // TODO: Verify that the membrane_proof is a valid credential signed by
        // the authorized_joining_certificate_issuer baked into the DNA properties.
        // Use dna_info().properties to retrieve the expected issuer key.
        Ok(ValidateCallbackResult::Valid) // Placeholder
    }
    */

    // ---- Coordinator Zome Functions -----------------------------------------
    //
    //   submit_validation_request(request: ValidationRequest) -> ExternResult<ActionHash>
    //   submit_attestation(attestation: ValidationAttestation) -> ExternResult<ActionHash>
    //   publish_validator_profile(profile: ValidatorProfile) -> ExternResult<ActionHash>
    //   get_validation_request(hash: ActionHash) -> ExternResult<Option<Record>>
    //   get_attestations_for_request(request_ref: ExternalHash) -> ExternResult<Vec<Record>>
    //   get_validators_for_discipline(discipline: Discipline) -> ExternResult<Vec<Record>>
    //   check_all_commitments_sealed(request_ref: ExternalHash) -> ExternResult<bool>
    //   recv_remote_signal(signal: SerializedBytes) -> ExternResult<()>  ← unrestricted grant
    //
    // Capability grants (set up in init() callback):
    //   Unrestricted: recv_remote_signal, all public read functions
    //   Assigned (credentialed validators only): submit_attestation, submit_validation_request
    //
    // Without an init() callback creating these grants, remote callers receive
    // ZomeCallResponse::Unauthorized even for functions intended to be public.

    // ---- Validator Assignment Logic -----------------------------------------

    /// Constraints on validator panel composition.
    pub struct AssignmentConstraints {
        /// Maximum proportion of validators from one institution
        pub max_institutional_share: f64,  // Default: 0.4 (40%)
        /// Minimum number of validators
        pub min_validators: u8,            // Default: 3
        /// Require at least one domain expert
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

    pub struct ValidationEngine {
        pub constraints: AssignmentConstraints,
    }

    impl ValidationEngine {
        /// Select validators for a study, respecting all constraints.
        /// Runs in coordinator zome — queries DHT for available validators,
        /// their profiles, and institutional affiliations.
        pub fn select_validators(
            &self,
            request: &ValidationRequest,
            available_validators: &[ValidatorProfile],
        ) -> Result<Vec<ValidatorId>> {
            // TODO: Implement reputation-weighted constrained random selection:
            // 1. Filter by discipline capability and certification tier
            // 2. Apply institutional caps (max 40% from one institution)
            // 3. Weight by reputation score from Governance DNA
            // 4. Check co-authorship conflicts (social distance)
            // 5. Ensure at least one domain expert if required
            Err(ValiChordError::NotFound("Not implemented".into()))
        }

        /// Check for gaming patterns across a validator's history.
        ///
        /// Runs in coordinator zome — NOT in validate() callback.
        /// Validation callbacks must be deterministic (no historical queries,
        /// no time-dependent logic). Gaming detection is inherently statistical
        /// and belongs here, called explicitly before key interactions (e.g.
        /// before accepting an attestation into the reveal session).
        pub fn detect_gaming_patterns(
            &self,
            validator_id: &ValidatorId,
            history: &[ValidationAttestation],
        ) -> Vec<GamingFlag> {
            // TODO: Implement detection patterns:
            // - Collusion: >90% agreement with specific other validators over 20+ events
            // - Speed: unrealistically fast completion times
            // - Rubber-stamping: always Reproduced with minimal time invested
            // - Social distance: co-authorship graph proximity to study authors
            //
            // WARRANTS: When a gaming pattern is confirmed, any peer can issue
            // a warrant — a cryptographic proof of the bad action — published
            // to the network. Warrants are permanent and discoverable via
            // get_agent_activity(). Stabilised in Holochain 0.7.
            Vec::new()
        }
    }

    #[derive(Debug, Clone)]
    pub enum GamingFlag {
        SuspiciousAgreementPattern { with_validator: ValidatorId, agreement_rate: f64 },
        UnrealisticallyFast { expected_min: Duration, actual: Duration },
        RubberStamping { approval_rate: f64, avg_time: Duration },
        SocialProximity { distance: u8, shared_publications: u32 },
    }

    impl DifficultyAssessment {
        /// Compute predicted tier from surface feature scores.
        /// PLACEHOLDER: weights must come from Phase 0 regression.
        pub fn compute(
            request_ref: ExternalHash,
            code_volume: u8,
            dependency_count: u8,
            documentation_quality: u8,
            data_accessibility: u8,
            environment_complexity: u8,
            study_age_years: u8,
        ) -> Self {
            // TODO: Replace with empirically derived weights from Phase 0.
            // The current weights are illustrative only.
            let weighted_score =
                (code_volume as f64 * 0.15) +
                (dependency_count as f64 * 0.20) +
                ((5 - documentation_quality) as f64 * 0.25) + // inverse: poor docs = harder
                ((5 - data_accessibility) as f64 * 0.20) +    // inverse: poor access = harder
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
                request_ref,
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
}

// =============================================================================
// DNA 4: GOVERNANCE & HARMONY RECORDS
// =============================================================================
//
// Public DHT — governance-controlled writing, publicly readable by anyone.
// This is what journals, funders, and institutions query.
//
// Harmony Records, badges, governance decisions, and validator reputation
// all live here. Anti-domestication mechanics are baked into the membrane
// proof and coordinator logic.
//
// External access via HTTP Gateway (Holochain v0.2, July 2025):
// Journals and funders query this DNA over standard HTTP/REST without running
// a Holochain node. Only this DNA needs to be reachable from outside —
// the private DNAs (Researcher Repository, Validator Workspace) are never
// exposed via the HTTP Gateway.

pub mod governance_dna {
    use super::*;
    use super::researcher_repository_dna::EpistemicImpact;
    use super::validator_workspace_dna::AttestationOutcome;
    use super::attestation_dna::{ValidationTier, AgreementLevel};

    // ---- Entry Types --------------------------------------------------------

    /// The canonical output of ValiChord.
    ///
    /// Preserves the full texture of agreement and disagreement rather than
    /// producing a single verdict. "Harmony" means the structure of agreement
    /// AND disagreement — a record with 2 successes and 1 failure is more
    /// informative than a binary pass/fail.
    ///
    /// Written to this DNA via countersigning session — all assigned validators
    /// simultaneously countersign this single entry. This is the reveal: their
    /// private attestations (in Validator Workspace DNA) become public here.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct HarmonyRecord {
        /// Reference to the ValidationRequest in the Attestation DNA
        pub request_ref: ExternalHash,
        pub validation_summary: ValidationSummary,
        pub validators: Vec<ValidatorSummary>,
        /// Disagreements are always visible — per governance commitments
        pub disagreements: Vec<Disagreement>,
        pub confidence_level: ConfidenceLevel,
        pub status: ReproducibilityStatus,
        /// 24 months minimum per governance policy
        pub valid_until: DateTime,
        pub provenance_link: String,
    }

    /// Countersigning check: successful + partial + failed + inconclusive
    /// must equal total_validators. Use these fields in the validate() callback
    /// to verify all validators participated — HarmonyRecord has no
    /// `validator_signatures` field (that was incorrect in previous versions).
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

    /// Reproducibility badge — domain-specific, not gamified.
    /// Cannot be reduced to a single numerical score.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ReproducibilityBadge {
        pub harmony_record_ref: ExternalHash,
        pub badge_type: BadgeType,
        pub level: BadgeLevel,
        pub discipline: Discipline,
        pub issued_at: DateTime,
    }

    #[derive(Debug, Clone)]
    pub enum BadgeType {
        ComputationalReproducible,
        PreRegisteredAndValidated { adherence_score: f64 },
        OpenDataValidated,
        MultiLabValidated { lab_count: u8 },
    }

    #[derive(Debug, Clone)]
    pub enum BadgeLevel {
        Bronze, // ≥3 validators, ≥60% success
        Silver, // ≥5 validators, ≥70%, pre-registered
        Gold,   // ≥7 validators, ≥80%, multi-institutional
    }

    /// Governance decision — every decision is logged immutably.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct GovernanceDecision {
        pub decision_type: DecisionType,
        pub made_by: GovernanceBody,
        pub rationale: String,
        pub vote_tally: Option<VoteTally>,
    }

    #[derive(Debug, Clone)]
    pub enum DecisionType {
        DeviationApproved { protocol_ref: ExternalHash },
        DeviationDenied { protocol_ref: ExternalHash, reason: String },
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

    /// Multi-dimensional validator reputation. No single gameable score.
    ///
    /// Only the system coordinator agent (defined in the membrane proof)
    /// may write reputation scores. Individual validators cannot edit
    /// their own scores — enforced by the validate() callback.
    // #[hdk_entry_helper]
    #[derive(Debug, Clone)]
    pub struct ValidatorReputation {
        pub validator_id: ValidatorId,
        pub validation_score: f64,
        pub preregistration_quality: f64,
        pub deviation_handling: f64,
        pub time_investment_consistency: f64,
        pub peer_endorsements: u32,
        pub expertise_areas: HashMap<Discipline, ExpertiseLevel>,
        pub total_validations: u32,
        pub total_score: f64,
    }

    #[derive(Debug, Clone)]
    pub enum ExpertiseLevel { Novice, Competent, Expert, Authority }

    /// Incentive structure. Compensation amounts are PLACEHOLDERS —
    /// Phase 0 evidence determines real values. Amounts stored as integer
    /// pence to avoid floating-point rounding errors in financial calculations.
    #[derive(Debug, Clone)]
    pub enum ValidatorIncentive {
        CreditRecognition { credit_type: CreditType },
        DirectPayment { amount_pence: u64, currency: String },
        ReputationGain { increase: f64 },
    }

    #[derive(Debug, Clone)]
    pub enum CreditType {
        ValidationExecution,
        MethodologyReview,
        FormalAnalysis,
        Software,
    }

    /// Anti-gaming constraints built into the incentive structure.
    pub struct IncentiveConstraints {
        pub no_speed_incentives: bool,
        pub quality_multiplier: f64,
        pub cross_discipline_bonus: f64,
        pub disagreement_discovery_bonus: f64,
        pub homophily_penalty: f64, // Penalty for >90% agreement with single institution
    }

    // ---- Link Types ---------------------------------------------------------

    // #[hdk_link_types]
    #[derive(Debug, Clone, PartialEq, Eq)]
    pub enum LinkTypes {
        /// agent pubkey → their ValidatorReputation record
        ValidatorToReputation,
        /// ValidationRequest ref → HarmonyRecord
        RequestToHarmonyRecord,
        /// GovernanceDecision → affected protocol/validator
        DecisionToTarget,
        /// path anchor → HarmonyRecord (for discipline-based queries)
        DisciplinePath,
    }

    // ---- Validate Callback (Governance DNA) ---------------------------------
    //
    // Key rules:
    //   1. HarmonyRecord: countersignature check — signed_count must equal total_validators
    //   2. ValidatorReputation: only the system coordinator agent may write
    //   3. Warrant records: any peer may create, but must reference a valid action hash

    /*
    #[hdk_extern]
    pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
        match op.flattened::<EntryTypes, LinkTypes>()? {

            // HarmonyRecord: verify all assigned validators participated.
            // Use validation_summary fields — successful + partial + failed +
            // inconclusive must equal total_validators.
            FlatOp::StoreEntry(OpEntry::CreateEntry {
                entry_type: EntryTypes::HarmonyRecord(record), ..
            }) => {
                let summary = &record.validation_summary;
                let signed_count = summary.successful_validations
                    + summary.partial_validations
                    + summary.failed_validations
                    + summary.inconclusive_validations;
                if signed_count < summary.total_validators {
                    return Ok(ValidateCallbackResult::Invalid(
                        "HarmonyRecord requires attestations from all assigned validators".into()
                    ));
                }
                Ok(ValidateCallbackResult::Valid)
            }

            // ValidatorReputation: only the system coordinator may write.
            FlatOp::StoreEntry(OpEntry::CreateEntry {
                entry_type: EntryTypes::ValidatorReputation(_), ..
            }) => {
                let coordinator_key = dna_info()?.properties.system_coordinator_key;
                if op.action().author() != coordinator_key {
                    return Ok(ValidateCallbackResult::Invalid(
                        "Only the system coordinator may write reputation scores".into()
                    ));
                }
                Ok(ValidateCallbackResult::Valid)
            }

            _ => Ok(ValidateCallbackResult::Valid),
        }
    }
    */

    // ---- Coordinator Zome Functions -----------------------------------------
    //
    //   create_harmony_record(record: HarmonyRecord) -> ExternResult<ActionHash>
    //   issue_badge(badge: ReproducibilityBadge) -> ExternResult<ActionHash>
    //   record_governance_decision(decision: GovernanceDecision) -> ExternResult<ActionHash>
    //   update_validator_reputation(reputation: ValidatorReputation) -> ExternResult<ActionHash>
    //   get_harmony_record(request_ref: ExternalHash) -> ExternResult<Option<Record>>
    //   get_harmony_records_for_discipline(discipline: Discipline) -> ExternResult<Vec<Record>>
    //   get_validator_reputation(validator_id: AgentId) -> ExternResult<Option<Record>>
    //
    // Capability grants (set up in init() callback):
    //   Unrestricted: ALL read functions (get_harmony_record, get_badge, etc.)
    //   This DNA is the HTTP Gateway target — public readability is the point.
    //   No unrestricted write functions — writing requires a membrane credential.
}

// =============================================================================
// CROSS-DNA ARCHITECTURE NOTES
// =============================================================================
//
// --- Cross-DNA calls (within the same hApp instance) ---
//
// Use hdk::p2p::call with CallTargetCell::OtherRole("dna_role_name").
// When all four DNAs run on a single node (true for any researcher or validator),
// the author grant applies automatically — no capability tokens required for
// same-agent cross-DNA calls.
//
// CRITICAL CONSTRAINT: call_remote() only works between agents on the SAME
// DNA's network. Alice's Attestation DNA can call_remote to Bob's Attestation
// DNA. Alice's Attestation DNA CANNOT call_remote to Bob's Researcher Repository
// DNA. All inter-validator coordination must happen within the Attestation DNA.
//
// --- Signals ---
//
// Signals are SEND-AND-FORGET. No delivery confirmation, no persistence.
// A validator offline when the signal fires misses it entirely.
//
// Phase transitions must be driven by DHT state polling, not signal delivery:
//   - Attestation DNA coordinator polls: have all expected validators sealed
//     their private commitments? (checks source chain activity)
//   - Only when all commitments are confirmed does the reveal window open.
//   - Signals are appropriate for notifying UIs that something is ready to act
//     on — not for driving the protocol machinery.
//
// --- DNA Properties ---
//
// Use #[dna_properties] on a struct to embed configuration into the DNA hash.
// These are immutable for the lifetime of a network instance — changing them
// creates a new DNA hash = a new network.
//
// ValiChord uses cases:
//   Attestation DNA:
//     - authorized_joining_certificate_issuer: AgentPubKey
//     - discipline: String (e.g. "genomics")
//     - minimum_validators: u32
//   Governance DNA:
//     - system_coordinator_key: AgentPubKey (the only agent that may write reputation)
//
// --- Path Sharding (Phase 2+ scale) ---
//
// When a single anchor accumulates thousands of links, DHT nodes responsible
// for that address become overloaded. Holochain's Path struct includes a
// built-in sharding DSL: prefix with `<width>:<depth>#` to distribute load.
// Example: "2:1#cardiff_university" creates intermediate nodes "ca", "cb" etc.
//
// At Phase 1 scale (hundreds of studies), simple paths without sharding are
// adequate. At Phase 2 scale (thousands of studies), shard institution paths
// by the first two characters of the institution identifier.
// Path sharding belongs in coordinator logic only — no effect on integrity zomes.
//
// --- Two Access Models — Keep These Separate ---
//
// Model A — LOCAL FRONT END (researcher UI, validator UI):
//   Connects via AppWebsocket.connect() over a local WebSocket interface.
//   This interface is ONLY exposed to processes on the same device — not
//   reachable from the network. This is a hard security guarantee, not policy.
//   The UI must be distributed with the hApp and a Holochain runtime
//   (hc-spin for dev, Kangaroo/p2p Shipyard for production).
//   All four DNAs are accessible this way from the local UI.
//
// Model B — EXTERNAL HTTP GATEWAY (journals, funders, institutional platforms):
//   Uses Holochain HTTP Gateway (v0.2, July 2025) to reach the Governance DNA
//   over standard HTTP/REST. External callers do not run a Holochain node.
//   ONLY the Governance/Harmony Records DNA is exposed this way.
//   Private DNAs (Researcher Repository, Validator Workspace) are never
//   reachable via the HTTP Gateway.
//
// DO NOT conflate these. A journal cannot call a researcher's local zome
// functions directly. A researcher's UI does not go through the HTTP Gateway.
//
// --- REST API Endpoints (served via HTTP Gateway on Governance DNA) ---
//
// GET    /api/v1/harmony/{request_ref}         Get Harmony Record
// GET    /api/v1/badges/{request_ref}          Get badge for study
// GET    /api/v1/validators/{agent_id}         Get validator reputation
// GET    /api/v1/query/doi/{doi}               Query by DOI
// GET    /api/v1/query/osf/{osf_id}            Query by OSF project
// GET    /api/v1/institutions/{id}/metrics     Institutional metrics
// GET    /api/v1/funders/{id}/portfolio        Funder portfolio

// =============================================================================
// TESTS (placeholder structure)
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use super::attestation_dna::*;

    #[test]
    fn test_difficulty_assessment_easy_study() {
        let assessment = DifficultyAssessment::compute(
            [0u8; 32],
            2, // code volume: low
            1, // dependency count: low
            5, // documentation: excellent
            5, // data accessibility: excellent
            1, // environment complexity: low
            1, // study age: recent
        );
        assert_eq!(assessment.predicted_tier, DifficultyTier::Standard);
    }

    #[test]
    fn test_difficulty_assessment_hard_study() {
        let assessment = DifficultyAssessment::compute(
            [0u8; 32],
            4, // code volume: high
            5, // dependency count: high
            1, // documentation: poor
            1, // data accessibility: restricted
            4, // environment complexity: high
            4, // study age: old
        );
        assert!(matches!(
            assessment.predicted_tier,
            DifficultyTier::Complex | DifficultyTier::Extreme
        ));
    }

    #[test]
    fn test_harmony_record_countersigning_check() {
        // Verify the logic that the validate callback enforces:
        // signed_count must equal total_validators
        let summary = governance_dna::ValidationSummary {
            total_validators: 3,
            successful_validations: 2,
            partial_validations: 1,
            failed_validations: 0,
            inconclusive_validations: 0,
            agreement_level: 0.8,
            outlier_count: 0,
        };
        let signed_count = summary.successful_validations
            + summary.partial_validations
            + summary.failed_validations
            + summary.inconclusive_validations;
        assert_eq!(signed_count, summary.total_validators);
    }

    #[test]
    fn test_assignment_constraints_defaults() {
        let constraints = attestation_dna::AssignmentConstraints::default();
        assert_eq!(constraints.min_validators, 3);
        assert!(constraints.double_blind);
        assert!((constraints.max_institutional_share - 0.4).abs() < f64::EPSILON);
    }
}
