// =============================================================================
// ValiChord — Distributed Validation Infrastructure for Computational Research
// =============================================================================
//
// ARCHITECTURE SCAFFOLD — v11 — March 2026
//
// This file is a single-file representation of ValiChord's four Holochain
// DNA membranes, written for a Holochain engineer to read and work from.
//
// HOW TO USE THIS FILE
//
//   In the real implementation each DNA becomes two separate Rust crates:
//     - <dna>_integrity   (uses `hdi` crate, compiled to WASM)
//     - <dna>_coordinator (uses `hdk` crate, compiled to WASM)
//
//   The four DNA modules below map directly to those crates. Within each
//   module, the boundary between integrity and coordinator code is clearly
//   marked. Copy each section into the appropriate crate when building.
//
//   Shared types (marked at the top of this file) belong in a shared Rust
//   library crate imported by each integrity zome as a Cargo dependency.
//   Do NOT define them inside any zome — changes to integrity zomes change
//   the DNA hash, creating a new empty network. Keeping shared types in a
//   separate crate lets you update them without rebuilding every integrity zome.
//
// STATUS
//
//   Entry types and link types:     Complete — match scaffolding plan
//   Validate callbacks:             Written — not production-audited
//   Coordinator functions:          Stubbed — marked TODO for implementation
//   init() capability grants:       Written — requires review against SDK version
//   DNA properties:                 Specified — plug in real AgentPubKey values
//   Tests:                          Placeholder structure — expand with Tryorama
//
// WHAT THIS IS NOT
//
//   - Compilable as-is (each DNA module references types from other modules
//     for clarity; in real code each crate has its own isolated type set)
//   - Production-ready (no error recovery, no retry logic, no persistence)
//   - A substitute for Phase 0 empirical data (difficulty weights, compensation
//     tiers, and gaming thresholds are all placeholders pending real evidence)
//
// FOUR-DNA MEMBRANE ARCHITECTURE
//
//   DNA 1: Researcher Repository  — private membrane, researcher only
//   DNA 2: Validator Workspace    — private membrane, per validator
//   DNA 3: Attestation            — shared DHT, credentialed participants
//   DNA 4: Governance & Harmony   — public DHT, open read / HTTP Gateway
//
// KEY ENGINEERING CONSTRAINTS (do not lose these)
//
//   1. Signals are fire-and-forget. Phase transitions MUST be driven by DHT
//      state polling — never by signal delivery. A validator offline when a
//      signal fires will miss it entirely.
//
//   2. call_remote() cannot cross DNA network boundaries. All inter-validator
//      coordination must happen within the Attestation DNA's shared network.
//      Researcher Repository and Validator Workspace are never reachable
//      from other agents' code.
//
//   3. Integrity zomes must stay small. Every change — including dependency
//      version bumps — changes the DNA hash and creates a new empty network.
//
//   4. Collusion and gaming detection belong in coordinator zomes, not in
//      validate(). The validate callback must be fully deterministic (no
//      historical queries, no statistical analysis, no time-dependent logic).
//
//   5. AgentPubKey is 39 bytes, not 32. Use the HDK's native AgentPubKey type.
//      Never use [u8; 32] or Vec<u8> as a substitute for agent identity.
//
//   6. SHA-256 for research file fingerprints; BLAKE2b is Holochain-internal.
//      Use the `sha2` crate (compiled to WASM) to compute ExternalHash values.
//      Do not use hash_entry() for research files — that produces BLAKE2b.
//
//   7. In validate(), guarded entry-type arms MUST precede unguarded arms.
//      Rust evaluates match arms in order. An unguarded update/delete arm
//      placed before the immutability guards silently swallows everything —
//      no compile error, no runtime error, just a broken security guarantee.
//
//   8. coordinator zomes can currently only safely depend on ONE integrity
//      zome. Always list the dependency explicitly in dna.yaml even if there
//      is only one — this is a known Holochain bug.
//
//   9. sys_time() and random_bytes() are coordinator-only. They cannot be
//      used in validate() — doing so would break validation determinism.
//
//  10. Holochain Actions already carry author key, timestamp, and sequence
//      number natively. Do not duplicate created_at or creator_id inside
//      entry structs — those fields will be wrong (author can set them to
//      anything) and they waste DHT space.
//
// COMPANION DOCUMENTS
//
//   SCAFFOLDING_PLAN.md           — Directory structure, call maps, protocol flow
//   3_ValiChord_Technical_Reference.md — Full architecture narrative
//   1_ValiChord_Vision&Architecture.md — System-level design rationale
//   2_ValiChord_Governance_Framework.md — Anti-capture mechanics
//   holochain_complete_knowledge.md — Synthesised Holochain Build Guide
//
// Author: Ceri John (architecture), Claude Sonnet 4.6 (scaffold generation)
// Date:   March 2026
// =============================================================================

#![allow(dead_code, unused_variables, unused_imports)]

// =============================================================================
// SHARED TYPES
// In the real implementation these live in a separate `valichord_shared_types`
// crate and are imported by each integrity zome via Cargo.toml.
// =============================================================================

/// SHA-256 digest of external research content (data files, code archives).
///
/// This is NOT a Holochain internal hash. Holochain uses BLAKE2b internally
/// for ActionHash, EntryHash, and AgentPubKey. SHA-256 is the researcher-
/// facing fingerprint that identifies study materials and is compatible with
/// academic repositories (Zenodo, Figshare, OSF, etc.).
///
/// Compute with the `sha2` crate compiled to WASM:
///   use sha2::{Sha256, Digest};
///   let hash: [u8; 32] = Sha256::digest(bytes).into();
/// Store on the DHT as Holochain's ExternalHash type.
pub type ResearchHash = [u8; 32];

/// Scientific discipline. Extended by governance decision, not code change.
/// Kept in shared types so the same enum is used across all four DNAs.
#[derive(Debug, Clone, Hash, Eq, PartialEq, serde::Serialize, serde::Deserialize)]
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

/// Structured outcome from a single validator's reproduction attempt.
/// Shared across DNA 2 (private commit) and DNA 3 (public reveal).
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
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

#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub enum AttestationConfidence { High, Medium, Low }

/// Phase 0's four-category time breakdown — the primary measurement goal.
/// These categories feed the difficulty prediction model.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TimeBreakdown {
    pub environment_setup_secs: u64,
    pub data_acquisition_secs:  u64,
    pub code_execution_secs:    u64,
    pub troubleshooting_secs:   u64,
}

/// Structured deviation type. One of ValiChord's key contributions:
/// deviation reporting as machine-readable data, not free text.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum DeviationType {
    DataAccess            { reason: String, impact: EpistemicImpact },
    EthicalConcern        { review_board: String },
    ModelFailure          { attempted_model: String, fallback_model: String, justification: String },
    ComputationalLimit    { planned_method: String, actual_method: String, reason: String },
    SampleSizeAdjustment  { original_n: usize, revised_n: usize, power_analysis: String },
}

#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub enum EpistemicImpact {
    Minimal,
    Moderate,
    Substantial, // Triggers governance review
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum Severity { Minor, Moderate, Major, Critical }

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ComputationalResources {
    pub personal_hardware_sufficient:  bool,
    pub hpc_required:                  bool,
    pub gpu_required:                  bool,
    pub cloud_compute_required:        bool,
    /// Integer pence to avoid floating-point rounding in financial values.
    pub estimated_compute_cost_pence:  Option<u64>,
}

// =============================================================================
// DNA 1: RESEARCHER REPOSITORY
// =============================================================================
//
// Private membrane — researcher (and their institution) only.
// Holds raw research materials locally.
//
// The ONLY thing that leaves this DNA is a SHA-256 hash (ResearchHash) of the
// study materials. GDPR compliance is structurally enforced: sensitive data
// cannot enter the shared DHT because it lives in a separate, private DNA.
//
// integrity crate uses:  hdi::prelude::*
// coordinator crate uses: hdk::prelude::*
//
// dna.yaml properties: none — single-agent private DNA needs no configuration.

pub mod researcher_repository {

    use super::*;

    // =========================================================================
    // INTEGRITY ZOME — hdi::prelude::*
    // =========================================================================
    //
    // In the real crate: use hdi::prelude::*;
    //
    // Entry types and link types defined here determine the DNA hash.
    // The validate callback defined here is the ONLY place validation logic lives.
    // Do not import hdk here — hdi is a strict subset and the correct choice.

    pub mod integrity {

        use super::*;

        // --- Entry Types -----------------------------------------------------

        /// Content-addressed fingerprint of a researcher's study materials.
        /// Stored as a private entry — never enters the shared DHT.
        ///
        /// The sha256_hash is what travels outward to the Attestation DNA.
        /// Storage locations tell validators where to download the materials.
        /// The hash guarantees authenticity regardless of storage provider.
        #[hdk_entry_helper]
        #[derive(Debug, Clone, PartialEq)]
        pub struct VerifiedDataSnapshot {
            /// SHA-256 fingerprint of the research files (data, code, protocol).
            pub sha256_hash:        ResearchHash,
            /// Where the files can be downloaded. The hash — not the location —
            /// is the integrity guarantee.
            pub storage_locations:  Vec<StorageLocation>,
            pub size_bytes:         u64,
        }

        #[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
        pub enum StorageLocation {
            Zenodo        { deposit_id: String },
            Figshare      { article_id: String },
            Osf           { project_id: String },
            GitHub        { repo: String, commit_sha: String },
            Institutional { url: String },
            S3            { bucket: String, region: String },
            Other         { provider: String, location: String },
        }

        /// Pre-registered protocol — what the researcher committed to before
        /// seeing results.
        ///
        /// Holochain's source chain enforces immutability: once written, this
        /// entry cannot be silently altered. Updates create new immutable entries
        /// and mark the old one as superseded, preserving the full history.
        /// No application-level "time lock" wrapper is needed or appropriate.
        ///
        /// To record a protocol modification, call update_entry() and create a
        /// linked DeclaredDeviation entry explaining the reason.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct PreRegisteredProtocol {
            pub analysis_plan_description:  String,
            pub hypotheses:                 Vec<Hypothesis>,
            pub analysis_type:              AnalysisType,
            pub primary_outcomes:           Vec<OutcomeMeasure>,
            pub secondary_outcomes:         Vec<OutcomeMeasure>,
            pub stopping_rules:             String,
            pub sample_size_n:              usize,
            pub sample_size_justification:  String,
            pub allowed_deviation_types:    Vec<DeviationType>,
            /// Raw signature bytes from the institutional authority.
            pub institutional_approval:     Option<Vec<u8>>,
            pub external_links:             ExternalLinks,
        }

        /// A declared deviation from the pre-registered plan.
        ///
        /// Each deviation is a separate, new entry — not an update to the
        /// protocol. This gives a queryable, structured deviation history
        /// without relying on Holochain's update chain for semantic meaning.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct DeclaredDeviation {
            /// ActionHash of the specific protocol version this deviates from.
            pub protocol_action_hash:   ActionHash,
            pub deviation_type:         DeviationType,
            pub justification:          String,
            pub epistemic_impact:       EpistemicImpact,
        }

        // Supporting types for protocol entries

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct Hypothesis {
            pub statement:   String,
            pub formal_spec: Option<FormalClaim>,
            pub claim_type:  ClaimType,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct FormalClaim {
            pub null_hypothesis:        String,
            pub alternative_hypothesis: String,
            pub significance_threshold: f64,
            pub test_statistic:         String,
            pub direction:              Direction,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum Direction    { TwoSided, GreaterThan, LessThan }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum ClaimType {
            Primary,
            Secondary,
            Exploratory { disclosed: bool },
            Robustness,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum AnalysisType { Confirmatory, Exploratory, Mixed }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct OutcomeMeasure {
            pub name:          String,
            pub specification: String,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct ExternalLinks {
            pub osf_project:         Option<String>,
            pub github_repo:         Option<String>,
            pub preregistration_doi: Option<String>,
            pub trial_registry:      Option<String>,
            pub publication_doi:     Option<String>,
        }

        // --- Entry Types Enum ------------------------------------------------

        #[hdk_entry_types]
        #[unit_enum(UnitEntryTypes)]
        pub enum EntryTypes {
            VerifiedDataSnapshot(VerifiedDataSnapshot),
            PreRegisteredProtocol(PreRegisteredProtocol),
            DeclaredDeviation(DeclaredDeviation),
        }

        // --- Link Types ------------------------------------------------------

        #[hdk_link_types]
        pub enum LinkTypes {
            /// Protocol ActionHash → Snapshot ActionHash
            ProtocolToSnapshot,
            /// Protocol ActionHash → DeclaredDeviation ActionHash (modification history)
            ProtocolToDeviation,
        }

        // --- Validate Callback -----------------------------------------------
        //
        // This DNA has a single participant (the researcher). Standard Holochain
        // source chain integrity — sequence numbers, author signatures, append-
        // only history — is sufficient. No custom rules are needed.

        #[hdk_extern]
        pub fn validate(_op: Op) -> ExternResult<ValidateCallbackResult> {
            Ok(ValidateCallbackResult::Valid)
        }
    }

    // =========================================================================
    // COORDINATOR ZOME — hdk::prelude::*
    // =========================================================================
    //
    // In the real crate: use hdk::prelude::*;

    pub mod coordinator {

        use super::*;

        // No init() needed — single-agent private DNA. Author grant covers all
        // calls and no remote agents need capability access.

        #[hdk_extern]
        pub fn submit_protocol(protocol: integrity::PreRegisteredProtocol) -> ExternResult<ActionHash> {
            let action_hash = create_entry(EntryTypes::PreRegisteredProtocol(protocol))?;
            // TODO: Create path link for local discovery if needed.
            Ok(action_hash)
        }

        #[hdk_extern]
        pub fn update_protocol(
            original_hash: ActionHash,
            updated_protocol: integrity::PreRegisteredProtocol,
        ) -> ExternResult<ActionHash> {
            update_entry(original_hash, updated_protocol)
        }

        #[hdk_extern]
        pub fn declare_deviation(deviation: integrity::DeclaredDeviation) -> ExternResult<ActionHash> {
            let deviation_hash = create_entry(EntryTypes::DeclaredDeviation(deviation.clone()))?;
            // Link from the protocol this deviates from
            create_link(
                deviation.protocol_action_hash.clone(),
                deviation_hash.clone(),
                LinkTypes::ProtocolToDeviation,
                (),
            )?;
            Ok(deviation_hash)
        }

        #[hdk_extern]
        pub fn upload_snapshot(snapshot: integrity::VerifiedDataSnapshot) -> ExternResult<ActionHash> {
            create_entry(EntryTypes::VerifiedDataSnapshot(snapshot))
        }

        #[hdk_extern]
        pub fn get_protocol(hash: ActionHash) -> ExternResult<Option<Record>> {
            get(hash, GetOptions::network())
        }

        /// Retrieve the full modification history of a protocol.
        /// Traverses the update chain from the original ActionHash.
        #[hdk_extern]
        pub fn get_protocol_history(original_hash: ActionHash) -> ExternResult<Details> {
            // get_details returns the record plus all updates and deletes
            let details = get_details(original_hash, GetOptions::network())?
                .ok_or(wasm_error!(WasmErrorInner::Guest("Protocol not found".into())))?;
            Ok(details)
        }

        #[hdk_extern]
        pub fn get_deviations_for_protocol(
            protocol_hash: ActionHash,
        ) -> ExternResult<Vec<Record>> {
            let links = get_links(
                GetLinksInputBuilder::try_new(protocol_hash, LinkTypes::ProtocolToDeviation)?.build(),
            )?;
            let mut records = Vec::new();
            for link in links {
                if let Some(target_hash) = link.target.into_action_hash() {
                    if let Some(record) = get(target_hash, GetOptions::network())? {
                        records.push(record);
                    }
                }
            }
            Ok(records)
        }

        /// Compute SHA-256 of research materials before transmitting the hash
        /// outward to the Attestation DNA.
        ///
        /// The data itself NEVER leaves this private DNA — only the hash travels.
        /// This is the primary GDPR protection: membrane separation ensures
        /// sensitive data cannot enter the shared DHT by architecture, not policy.
        pub fn compute_research_hash(data: &[u8]) -> ResearchHash {
            // TODO: use sha2::Sha256 compiled to WASM (add sha2 to Cargo.toml).
            // use sha2::{Sha256, Digest};
            // Sha256::digest(data).into()
            [0u8; 32] // placeholder
        }
    }
}

// =============================================================================
// DNA 2: VALIDATOR WORKSPACE
// =============================================================================
//
// Private membrane, per validator — the "Repro Witnessing hApp."
// Each validator runs their own instance. Only they can join.
//
// This is where the actual reproduction work happens:
//   - ValidationTask received from the Attestation DNA coordinator
//   - Validator runs analysis in their local environment
//   - ValidatorPrivateAttestation sealed as a private entry (COMMIT PHASE)
//   - Only the signed outcome summary — never raw results — leaves this space
//
// integrity crate uses:  hdi::prelude::*
// coordinator crate uses: hdk::prelude::*
//
// dna.yaml properties: none — single-agent private DNA.

pub mod validator_workspace {

    use super::*;

    // =========================================================================
    // INTEGRITY ZOME — hdi::prelude::*
    // =========================================================================

    pub mod integrity {

        use super::*;

        // --- Entry Types -----------------------------------------------------

        /// A validation assignment received from the Attestation DNA.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct ValidationTask {
            /// SHA-256 content hash identifying this task (not a Holochain ActionHash).
            pub task_id:             ResearchHash,
            /// References the ValidationRequest entry in the Attestation DNA.
            pub request_ref:         ResearchHash,
            pub validation_focus:    ValidationFocus,
            pub time_cap_secs:       u64,
            pub estimated_min_secs:  u64,
            pub estimated_max_secs:  u64,
            pub compensation_tier:   CompensationTier,
        }

        /// THE COMMIT PHASE — stored as a private entry.
        ///
        /// Invisible to all peers and to the shared DHT. Its *existence* is
        /// verifiable on this validator's source chain (any peer can query
        /// get_agent_activity to confirm the validator has a private action
        /// at this sequence position). Its *content* is not visible to anyone
        /// else until the reveal phase opens.
        ///
        /// This IS the cryptographic commitment. There is no need to hash it
        /// separately and post a hash elsewhere — Holochain's private entry
        /// mechanism gives us the sealed commitment natively.
        #[hdk_entry_helper]
        #[entry_type(visibility = "private")]
        #[derive(Debug, Clone)]
        pub struct ValidatorPrivateAttestation {
            pub task_ref:               ResearchHash,
            pub outcome:                AttestationOutcome,
            pub detailed_report:        String,
            pub time_invested_secs:     u64,
            pub time_breakdown:         TimeBreakdown,
            pub confidence:             AttestationConfidence,
            pub deviation_flags:        Vec<UndeclaredDeviation>,
            pub computational_resources: ComputationalResources,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct UndeclaredDeviation {
            pub deviation_type: DeviationType,
            pub severity:       Severity,
            pub evidence:       String,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum ValidationFocus {
            ComputationalReproducibility,
            PreCommitmentAdherence,
            MethodologicalReview,
        }

        /// Compensation tiers — PLACEHOLDER amounts.
        /// Phase 0 empirical evidence determines real values.
        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum CompensationTier {
            Tier1 { amount_pence: u64 }, // ~1–2 hours: £50–100
            Tier2 { amount_pence: u64 }, // ~4–8 hours: £200–400
            Tier3 { amount_pence: u64 }, // ~16+ hours: £800–1600
        }

        // --- Entry Types Enum ------------------------------------------------

        #[hdk_entry_types]
        #[unit_enum(UnitEntryTypes)]
        pub enum EntryTypes {
            ValidationTask(ValidationTask),
            #[entry_type(visibility = "private")]
            ValidatorPrivateAttestation(ValidatorPrivateAttestation),
        }

        // --- Link Types ------------------------------------------------------

        #[hdk_link_types]
        pub enum LinkTypes {
            /// ValidationTask ActionHash → ValidatorPrivateAttestation ActionHash
            TaskToPrivateAttestation,
        }

        // --- Validate Callback -----------------------------------------------
        //
        // Single participant — standard source chain integrity is sufficient.

        #[hdk_extern]
        pub fn validate(_op: Op) -> ExternResult<ValidateCallbackResult> {
            Ok(ValidateCallbackResult::Valid)
        }
    }

    // =========================================================================
    // COORDINATOR ZOME — hdk::prelude::*
    // =========================================================================

    pub mod coordinator {

        use super::*;

        // No init() needed — single-agent private DNA.

        #[hdk_extern]
        pub fn receive_task(task: integrity::ValidationTask) -> ExternResult<ActionHash> {
            create_entry(EntryTypes::ValidationTask(task))
        }

        /// Seal the validator's private attestation — the COMMIT PHASE.
        ///
        /// Writes a private entry: visible only on this validator's own
        /// source chain. post_commit fires after the write is confirmed
        /// and notifies the Attestation DNA coordinator.
        #[hdk_extern]
        pub fn seal_private_attestation(
            attestation: integrity::ValidatorPrivateAttestation,
        ) -> ExternResult<ActionHash> {
            let task_ref = attestation.task_ref;
            let attestation_hash = create_entry(
                EntryTypes::ValidatorPrivateAttestation(attestation)
            )?;
            // Link from the task so we can retrieve it later
            // Note: this link is also private since the target is private.
            // TODO: verify Holochain version behaviour for links to private entries.
            create_link(
                ActionHash::from_raw_36(task_ref.to_vec()), // placeholder — use actual task ActionHash
                attestation_hash.clone(),
                LinkTypes::TaskToPrivateAttestation,
                (),
            )?;
            Ok(attestation_hash)
        }

        #[hdk_extern]
        pub fn get_task(task_hash: ActionHash) -> ExternResult<Option<Record>> {
            get(task_hash, GetOptions::local())
        }

        #[hdk_extern]
        pub fn get_my_attestation(task_hash: ActionHash) -> ExternResult<Option<Record>> {
            let links = get_links(
                GetLinksInputBuilder::try_new(task_hash, LinkTypes::TaskToPrivateAttestation)?.build(),
            )?;
            match links.first() {
                Some(link) => {
                    let target = link.target.clone().into_action_hash()
                        .ok_or(wasm_error!(WasmErrorInner::Guest("Invalid link target".into())))?;
                    get(target, GetOptions::local())
                }
                None => Ok(None),
            }
        }

        /// Called automatically by Holochain after seal_private_attestation
        /// successfully commits to the source chain.
        ///
        /// Notifies the Attestation DNA coordinator that this validator's
        /// commitment is sealed. The Attestation coordinator must POLL DHT
        /// state to check when all validators have committed — it cannot rely
        /// on this signal (which is fire-and-forget and will be missed by
        /// any offline peer).
        ///
        /// The signal here is a UI convenience notification only.
        #[hdk_extern(infallible)]
        pub fn post_commit(committed_actions: Vec<SignedActionHashed>) -> ExternResult<()> {
            for action in committed_actions {
                if let Action::Create(create) = action.action() {
                    // When it's a ValidatorPrivateAttestation, notify the
                    // Attestation DNA coordinator via call() — author grant
                    // handles cross-DNA same-agent calls automatically.
                    // TODO: check entry type and call:
                    //   call(
                    //     CallTargetCell::OtherRole("attestation".into()),
                    //     "attestation_coordinator",
                    //     "notify_commitment_sealed",
                    //     None,
                    //     task_ref,
                    //   )
                }
            }
            Ok(())
        }
    }
}

// =============================================================================
// DNA 3: ATTESTATION
// =============================================================================
//
// Shared DHT, credentialed participants (institutional membrane proof required).
//
// Records the *act* of validation: protocol registered, attestation submitted,
// warrant issued. NOT the content of the research — only the signed outcome
// summary. All inter-validator call_remote() coordination happens here because
// call_remote() only works between agents on the SAME DNA's network.
//
// Agreement detection operates on structured OutcomeSummary fields — not on
// raw result hashes — because computational reproduction almost never produces
// bit-identical outputs due to floating-point differences and hardware variation.
//
// integrity crate uses:  hdi::prelude::*
// coordinator crate uses: hdk::prelude::*
//
// dna.yaml properties (baked into DNA hash — immutable per network instance):
//   authorized_joining_certificate_issuer: AgentPubKey  # credential issuer
//   discipline: String                                    # one network per discipline
//   minimum_validators: u32                               # e.g. 3

pub mod attestation {

    use super::*;

    // =========================================================================
    // INTEGRITY ZOME — hdi::prelude::*
    // =========================================================================

    pub mod integrity {

        use super::*;

        // --- DNA Properties --------------------------------------------------
        //
        // These are baked into the DNA hash. Changing them creates a new DNA
        // hash = new network. This tamper-evidence is the feature.

        #[dna_properties]
        #[derive(Debug, serde::Deserialize)]
        pub struct DnaProperties {
            /// AgentPubKey of the institution or authority empowered to issue
            /// joining credentials. Only credentials signed by this key are
            /// accepted by the membrane.
            pub authorized_joining_certificate_issuer: AgentPubKey,
            /// Discipline this network serves (e.g. "genomics", "economics").
            /// Each discipline runs its own Attestation DNA instance.
            pub discipline: String,
            /// Minimum number of validators required per study.
            pub minimum_validators: u32,
        }

        // --- Entry Types -----------------------------------------------------

        /// A request to validate a study. Submitted by a researcher or journal
        /// to kick off a validation round.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct ValidationRequest {
            /// SHA-256 hash of the PreRegisteredProtocol entry bytes from the
            /// Researcher Repository DNA — the ONLY link back to the private DNA.
            /// Not an ActionHash: we cannot reference another DNA's chain directly.
            pub protocol_ref:             Option<ResearchHash>,
            /// SHA-256 hash of the study data files. Validators use this to
            /// verify they downloaded the correct materials.
            pub data_hash:                ResearchHash,
            pub num_validators_required:  u8,
            pub validation_tier:          ValidationTier,
            pub discipline:               Discipline,
        }

        #[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
        pub enum ValidationTier { Basic, Enhanced, Comprehensive }

        /// THE REVEAL PHASE — the public attestation written to the shared DHT.
        ///
        /// Written once the validator's private commitment (in Validator Workspace
        /// DNA) is sealed and the reveal window is open. At this point the outcome
        /// becomes visible to all participants simultaneously.
        ///
        /// IMMUTABLE after publication — enforced by validate() callback.
        /// The validate() arms that guard this entry MUST appear before any
        /// unguarded update/delete arm (see ENGINEERING CONSTRAINTS #7 above).
        #[hdk_entry_helper]
        #[entry_type(required_validations = 7)]
        #[derive(Debug, Clone)]
        pub struct ValidationAttestation {
            /// Links this attestation to its ValidationRequest.
            pub request_ref:              ResearchHash,
            pub outcome:                  AttestationOutcome,
            /// Structured summary for agreement detection across validators.
            /// Agreement is assessed on these summaries — not on raw result
            /// hashes — because reproduction almost never produces bit-identical
            /// outputs across different hardware and environments.
            pub outcome_summary:          OutcomeSummary,
            pub time_invested_secs:       u64,
            pub time_breakdown:           TimeBreakdown,
            pub confidence:               AttestationConfidence,
            pub deviation_flags:          Vec<UndeclaredDeviation>,
            pub computational_resources:  ComputationalResources,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct OutcomeSummary {
            pub key_metrics:                 Vec<MetricResult>,
            pub effect_direction_matches:    Option<bool>,
            pub confidence_interval_overlap: Option<f64>,
            pub overall_agreement:           AgreementLevel,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct MetricResult {
            pub metric_name:      String,
            pub produced_value:   String,
            pub expected_value:   String,
            pub within_tolerance: bool,
        }

        #[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
        pub enum AgreementLevel {
            ExactMatch,
            WithinTolerance,
            DirectionalMatch,
            Divergent,
            UnableToAssess,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct UndeclaredDeviation {
            pub deviation_type: DeviationType,
            pub severity:       Severity,
            pub evidence:       String,
        }

        /// Validator profile — published to the shared DHT for assignment queries.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct ValidatorProfile {
            pub institution:          String,
            pub disciplines:          Vec<Discipline>,
            pub certification_tier:   CertificationTier,
            pub available:            bool,
            pub max_concurrent_tasks: u8,
            /// ORCID or institutional identifier for external verification.
            pub orcid:                Option<String>,
        }

        #[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
        pub enum CertificationTier {
            Provisional, // < 10 completed validations
            Certified,   // ≥ 10 in good standing
            Senior,      // ≥ 50 in excellent standing
        }

        /// Surface-feature difficulty assessment.
        /// Weights are PLACEHOLDERS — Phase 0 regression determines real values.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct DifficultyAssessment {
            pub request_ref:            ResearchHash,
            /// Each scored 1–5. See SCAFFOLDING_PLAN.md for definitions.
            pub code_volume:            u8,
            pub dependency_count:       u8,
            pub documentation_quality:  u8, // 5 = excellent
            pub data_accessibility:     u8, // 5 = fully open
            pub environment_complexity: u8,
            pub study_age_years:        u8, // 5 = very old
            pub predicted_tier:         DifficultyTier,
            pub predicted_min_secs:     u64,
            pub predicted_max_secs:     u64,
            pub confidence:             AssessmentConfidence,
        }

        #[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
        pub enum DifficultyTier {
            Standard,  // ~4–8 hours
            Moderate,  // ~8–16 hours
            Complex,   // ~16–30 hours
            Extreme,   // ~30+ hours — flag for human triage
            Excluded,  // Fails minimum criteria — rejected from pipeline
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum AssessmentConfidence { High, Medium, Low }

        // --- Entry Types Enum ------------------------------------------------

        #[hdk_entry_types]
        #[unit_enum(UnitEntryTypes)]
        pub enum EntryTypes {
            ValidationRequest(ValidationRequest),
            ValidationAttestation(ValidationAttestation),
            ValidatorProfile(ValidatorProfile),
            DifficultyAssessment(DifficultyAssessment),
        }

        // --- Link Types ------------------------------------------------------

        #[hdk_link_types]
        pub enum LinkTypes {
            /// ExternalHash anchor (study data_hash) → ValidationRequest ActionHash
            StudyToValidation,
            /// AgentPubKey → ValidationAttestation ActionHash
            ValidatorToAttestation,
            /// AgentPubKey → ValidatorProfile ActionHash
            AgentToProfile,
            /// Path anchor → ValidationRequest ActionHash, queryable by status+discipline
            /// Path format: "requests.{status}.{discipline}"
            StatusPath,
            /// Path anchor → ValidationRequest ActionHash, queryable by institution
            /// Path format: "institutions.{institution_id}"
            InstitutionPath,
            /// Path anchor → ValidationAttestation ActionHash, queryable by discipline
            /// Path format: "attestations.{discipline}.{YYYY_MM}"
            DisciplinePath,
        }

        // --- Validate Callback -----------------------------------------------
        //
        // This is the most important validate() in ValiChord.
        // Rules enforced here cannot be relaxed without migrating to a new DNA.
        //
        // ARM ORDERING IS CRITICAL:
        //   The ValidationAttestation immutability guards use helper functions
        //   (validate_update, validate_delete) that check entry type first.
        //   This is cleaner than guarded match arms (which cannot use ? in guards).

        #[hdk_extern]
        pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
            match op.flattened::<EntryTypes, LinkTypes>()? {

                // Updates: check for ValidationAttestation immutability first,
                // then fall back to author-only check for other entry types.
                FlatOp::RegisterUpdate(OpUpdate {
                    original_action,
                    original_app_entry,
                    ..
                }) => {
                    validate_update(op.action(), original_action, original_app_entry)
                }

                // Deletes: same pattern.
                FlatOp::RegisterDelete(OpDelete {
                    original_action,
                    original_app_entry,
                    ..
                }) => {
                    validate_delete(op.action(), original_action, original_app_entry)
                }

                // Membrane proof — full credential check runs after network join.
                // genesis_self_check() handles format-only check before join.
                FlatOp::RegisterAgentActivity(OpActivity::CreateAgent {
                    membrane_proof, ..
                }) => {
                    validate_membrane_proof(membrane_proof)
                }

                // All other ops: valid.
                _ => Ok(ValidateCallbackResult::Valid),
            }
        }

        fn validate_update(
            new_action: &Action,
            original_action: SignedActionHashed,
            original_app_entry: EntryTypes,
        ) -> ExternResult<ValidateCallbackResult> {
            // ValidationAttestation is immutable — block all updates.
            if matches!(original_app_entry, EntryTypes::ValidationAttestation(_)) {
                return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation cannot be updated — the record is permanent".into()
                ));
            }
            // For all other entry types: only the original author may update.
            if new_action.author() != original_action.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update this entry".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        fn validate_delete(
            new_action: &Action,
            original_action: SignedActionHashed,
            original_app_entry: EntryTypes,
        ) -> ExternResult<ValidateCallbackResult> {
            // ValidationAttestation is immutable — block all deletes.
            if matches!(original_app_entry, EntryTypes::ValidationAttestation(_)) {
                return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation cannot be deleted — the record is permanent".into()
                ));
            }
            // For all other entry types: only the original author may delete.
            if new_action.author() != original_action.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        /// Full membrane proof validation — runs after network join with DHT access.
        ///
        /// Checks:
        ///   1. A membrane proof is present (genesis_self_check already caught None).
        ///   2. It is signed by authorized_joining_certificate_issuer (from DNA properties).
        ///   3. The signature is over the joining agent's AgentPubKey.
        fn validate_membrane_proof(
            membrane_proof: Option<MembraneProof>,
        ) -> ExternResult<ValidateCallbackResult> {
            let proof = match membrane_proof {
                None => return Ok(ValidateCallbackResult::Invalid(
                    "Attestation DNA requires a membrane proof".into()
                )),
                Some(p) => p,
            };

            let props = DnaProperties::try_from_dna_properties()?;
            let issuer = props.authorized_joining_certificate_issuer;

            // TODO: Deserialise `proof` into (joining_agent_pubkey, signature).
            // Then: verify_signature(issuer, signature, joining_agent_pubkey)
            // Return Invalid if verification fails.
            //
            // Exact deserialisation format depends on how credentials are issued
            // by the institutional authority. Define a CredentialPayload struct
            // and serialise consistently on both the issuing and verifying sides.

            Ok(ValidateCallbackResult::Valid) // placeholder
        }

        // --- genesis_self_check — format-only, runs BEFORE network join ------
        //
        // No DHT access is available here. Check only that the proof is present
        // and plausibly structured — this protects the joining agent from
        // committing a malformed proof that would fail full validation later.

        #[hdk_extern]
        pub fn genesis_self_check(
            data: GenesisSelfCheckData,
        ) -> ExternResult<GenesisSelfCheckCallbackResult> {
            match data.membrane_proof {
                None => Ok(GenesisSelfCheckCallbackResult::Invalid(
                    "Attestation DNA requires a membrane proof (institutional credential)".into()
                )),
                Some(ref proof) if proof.bytes().len() < 64 => {
                    Ok(GenesisSelfCheckCallbackResult::Invalid(
                        "Membrane proof is too short to be a valid credential signature".into()
                    ))
                }
                _ => Ok(GenesisSelfCheckCallbackResult::Valid),
            }
        }
    }

    // =========================================================================
    // COORDINATOR ZOME — hdk::prelude::*
    // =========================================================================

    pub mod coordinator {

        use super::*;
        use std::collections::BTreeSet;

        // --- init() — capability grants --------------------------------------

        #[hdk_extern]
        pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
            // Grant unrestricted access to read functions and remote signal receiver.
            // Without these grants, remote callers receive Unauthorized even for
            // functions intended to be public.
            let zome = zome_info()?.name;
            let mut public_fns = BTreeSet::new();
            for fn_name in &[
                "recv_remote_signal",
                "get_validation_request",
                "get_attestations_for_request",
                "get_validators_for_discipline",
                "get_validator_profile",
                "check_all_commitments_sealed",
                "notify_commitment_sealed",
                "get_difficulty_assessment",
            ] {
                public_fns.insert((zome.clone(), (*fn_name).into()));
            }
            create_cap_grant(ZomeCallCapGrant {
                tag: "public-read".into(),
                access: CapAccess::Unrestricted,
                functions: GrantedFunctions::Listed(public_fns),
            })?;

            // Write functions (submit_validation_request, submit_attestation,
            // publish_validator_profile) are gated by the membrane credential.
            // Any agent in the network has a valid credential by definition —
            // the membrane check at join time already enforced this.
            // No additional capability grant is needed for writes among members.

            Ok(InitCallbackResult::Pass)
        }

        // --- Write functions -------------------------------------------------

        #[hdk_extern]
        pub fn submit_validation_request(
            request: integrity::ValidationRequest,
        ) -> ExternResult<ActionHash> {
            let request_hash = create_entry(EntryTypes::ValidationRequest(request.clone()))?;
            // Index by study data hash for discovery
            let study_path = Path::from(format!("study.{}", hex::encode(request.data_hash)))
                .typed(LinkTypes::StudyToValidation)?;
            study_path.ensure()?;
            create_link(
                study_path.path_entry_hash()?,
                request_hash.clone(),
                LinkTypes::StudyToValidation,
                (),
            )?;
            // Index by status + discipline for queue management
            let status_path = Path::from(
                format!("requests.pending.{:?}", request.discipline)
            ).typed(LinkTypes::StatusPath)?;
            status_path.ensure()?;
            create_link(
                status_path.path_entry_hash()?,
                request_hash.clone(),
                LinkTypes::StatusPath,
                (),
            )?;
            Ok(request_hash)
        }

        /// Submit a public attestation — THE REVEAL PHASE.
        ///
        /// Called after the reveal window opens (all validators have sealed
        /// their private commitments). This entry is IMMUTABLE — the validate()
        /// callback blocks all subsequent updates and deletes.
        ///
        /// post_commit fires after this write is confirmed and triggers
        /// HarmonyRecord assembly in the Governance DNA.
        #[hdk_extern]
        pub fn submit_attestation(
            attestation: integrity::ValidationAttestation,
        ) -> ExternResult<ActionHash> {
            let agent = agent_info()?.agent_initial_pubkey;
            let attestation_hash = create_entry(
                EntryTypes::ValidationAttestation(attestation.clone())
            )?;
            create_link(
                agent.clone(),
                attestation_hash.clone(),
                LinkTypes::ValidatorToAttestation,
                (),
            )?;
            // Index by discipline + month for analytics queries
            let disc_path = Path::from(
                format!("attestations.{:?}", attestation.discipline_tag())
            ).typed(LinkTypes::DisciplinePath)?;
            disc_path.ensure()?;
            create_link(
                disc_path.path_entry_hash()?,
                attestation_hash.clone(),
                LinkTypes::DisciplinePath,
                (),
            )?;
            Ok(attestation_hash)
        }

        #[hdk_extern]
        pub fn publish_validator_profile(
            profile: integrity::ValidatorProfile,
        ) -> ExternResult<ActionHash> {
            let agent = agent_info()?.agent_initial_pubkey;
            let profile_hash = create_entry(EntryTypes::ValidatorProfile(profile))?;
            create_link(agent, profile_hash.clone(), LinkTypes::AgentToProfile, ())?;
            Ok(profile_hash)
        }

        #[hdk_extern]
        pub fn assess_difficulty(
            request_ref: ResearchHash,
        ) -> ExternResult<ActionHash> {
            // TODO: Implement surface feature scoring.
            // Stage 1 (Phase 1): rule-based weighted rubric from Phase 0 correlations.
            // Stage 2 (Phase 1 later): automated analysis of code repository.
            // Stage 3 (Phase 2+): statistical model trained on 200+ validations.
            //
            // Placeholder scores:
            let assessment = integrity::DifficultyAssessment {
                request_ref,
                code_volume:            3,
                dependency_count:       3,
                documentation_quality:  3,
                data_accessibility:     3,
                environment_complexity: 3,
                study_age_years:        2,
                predicted_tier:         integrity::DifficultyTier::Moderate,
                predicted_min_secs:     28800,  // 8 hours
                predicted_max_secs:     57600,  // 16 hours
                confidence:             integrity::AssessmentConfidence::Low,
            };
            create_entry(EntryTypes::DifficultyAssessment(assessment))
        }

        // --- Read functions --------------------------------------------------

        #[hdk_extern]
        pub fn get_validation_request(hash: ActionHash) -> ExternResult<Option<Record>> {
            get(hash, GetOptions::network())
        }

        #[hdk_extern]
        pub fn get_attestations_for_request(
            request_ref: ResearchHash,
        ) -> ExternResult<Vec<Record>> {
            // Query via ValidatorToAttestation links on each assigned validator's
            // AgentPubKey. In practice the coordinator tracks the assignment list.
            // TODO: Implement by iterating assigned validator pubkeys and calling
            //       get_links(validator_pubkey, ValidatorToAttestation) for each.
            Ok(Vec::new())
        }

        #[hdk_extern]
        pub fn get_validators_for_discipline(
            discipline: Discipline,
        ) -> ExternResult<Vec<Record>> {
            // TODO: Query the discipline path and retrieve profiles.
            Ok(Vec::new())
        }

        #[hdk_extern]
        pub fn get_validator_profile(
            agent: AgentPubKey,
        ) -> ExternResult<Option<Record>> {
            let links = get_links(
                GetLinksInputBuilder::try_new(agent, LinkTypes::AgentToProfile)?.build(),
            )?;
            match links.first() {
                Some(link) => {
                    let target = link.target.clone().into_action_hash()
                        .ok_or(wasm_error!(WasmErrorInner::Guest("Invalid link".into())))?;
                    get(target, GetOptions::network())
                }
                None => Ok(None),
            }
        }

        #[hdk_extern]
        pub fn get_difficulty_assessment(
            request_ref: ResearchHash,
        ) -> ExternResult<Option<Record>> {
            // TODO: query by request_ref
            Ok(None)
        }

        // --- Protocol coordination -------------------------------------------

        /// Called by a validator's Workspace DNA post_commit (via call(OtherRole("attestation"))).
        ///
        /// Checks whether all assigned validators have sealed their private
        /// commitments. If all have committed, writes a PhaseMarker to the DHT
        /// opening the reveal window. Validators who missed the remote signal
        /// discover the open window by polling get_current_phase().
        ///
        /// This function is the real protocol gate. Signals are notifications only.
        #[hdk_extern]
        pub fn notify_commitment_sealed(
            task_ref: ResearchHash,
        ) -> ExternResult<()> {
            let all_sealed = check_all_commitments_sealed_inner(task_ref)?;
            if all_sealed {
                // TODO: Write a PhaseMarker entry to the DHT indicating reveal window open.
                // Emit local signal to this agent's UI.
                emit_signal(PhaseSignal { phase: "RevealOpen".into(), task_ref })?;
            }
            Ok(())
        }

        #[hdk_extern]
        pub fn check_all_commitments_sealed(
            request_ref: ResearchHash,
        ) -> ExternResult<bool> {
            check_all_commitments_sealed_inner(request_ref)
        }

        fn check_all_commitments_sealed_inner(
            request_ref: ResearchHash,
        ) -> ExternResult<bool> {
            // TODO: Retrieve the list of assigned validators for this request.
            // For each assigned validator, call:
            //   get_agent_activity(validator_pubkey, ChainQueryFilter::new(), ActivityRequest::Full)
            // Check that each validator's activity includes a ValidatorPrivateAttestation action.
            // Note: get_agent_activity returns action hashes only — not entry content
            // (private entries are not accessible). A private action appearing in the
            // agent's source chain is sufficient proof the commitment was sealed.
            Ok(false) // placeholder
        }

        #[hdk_extern]
        pub fn recv_remote_signal(signal: SerializedBytes) -> ExternResult<()> {
            // TODO: Deserialise and route to appropriate handler.
            emit_signal(signal)?;
            Ok(())
        }

        /// post_commit — fires after ValidationAttestation is confirmed written.
        ///
        /// Checks whether all validators have now revealed. If yes, calls the
        /// Governance DNA to assemble the Harmony Record.
        #[hdk_extern(infallible)]
        pub fn post_commit(committed_actions: Vec<SignedActionHashed>) -> ExternResult<()> {
            for action in committed_actions {
                // TODO: detect ValidationAttestation entries and call:
                //   call(
                //     CallTargetCell::OtherRole("governance".into()),
                //     "governance_coordinator",
                //     "check_and_create_harmony_record",
                //     None,
                //     request_ref,
                //   )
            }
            Ok(())
        }

        // --- Gaming and collusion detection ----------------------------------
        //
        // These functions run in the coordinator — NOT in validate().
        // validate() must be deterministic. Gaming detection is statistical
        // and cross-agent and cannot run inside the validation callback.
        //
        // Call these before accepting a validator into the reveal window.

        pub fn detect_gaming_patterns(
            validator: AgentPubKey,
            history: Vec<integrity::ValidationAttestation>,
        ) -> Vec<GamingFlag> {
            let mut flags = Vec::new();
            // TODO: Implement detection patterns:
            //
            // SuspiciousAgreementPattern:
            //   If a validator agrees with a specific peer in >90% of their
            //   shared cases over 20+ events, flag for investigation.
            //   Threshold is PLACEHOLDER — Phase 0 data on natural agreement
            //   rates is required to calibrate this correctly.
            //
            // UnrealisticallyFast:
            //   If time_invested_secs < predicted_min_secs * 0.5, flag.
            //   Threshold is PLACEHOLDER.
            //
            // RubberStamping:
            //   If approval_rate > 0.95 over 20+ validations with low
            //   average time invested, flag. Threshold PLACEHOLDER.
            //
            // SocialProximity:
            //   Query a co-authorship graph (Phase 2+ data source).
            //   If a validator co-authored with the study's researchers
            //   within 3 degrees, flag.
            //
            // On confirmed gaming: any peer may issue a Warrant DHT op.
            // Warrants are permanent and discoverable via get_agent_activity().
            // Application coordinator must check warrants before accepting
            // protocol participation — network does not auto-block warranted agents.
            flags
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum GamingFlag {
            SuspiciousAgreementPattern { with_validator: AgentPubKey, agreement_rate: f64 },
            UnrealisticallyFast        { expected_min_secs: u64, actual_secs: u64 },
            RubberStamping             { approval_rate: f64, avg_time_secs: u64 },
            SocialProximity            { distance: u8, shared_publications: u32 },
        }

        // --- Validator assignment --------------------------------------------

        #[derive(Debug, Clone)]
        pub struct AssignmentConstraints {
            /// Maximum proportion of validators from the same institution.
            pub max_institutional_share: f64,  // default 0.4
            pub min_validators:          u8,   // from DNA properties
            pub require_domain_expert:   bool, // default true
            /// Validators never see author name, institution, or funding source.
            pub double_blind:            bool, // default true
        }

        pub fn select_validators(
            request: &integrity::ValidationRequest,
            available_profiles: Vec<integrity::ValidatorProfile>,
            constraints: &AssignmentConstraints,
        ) -> ExternResult<Vec<AgentPubKey>> {
            // TODO:
            // 1. Filter by discipline capability and certification tier
            // 2. Apply institutional cap (max 40% from same institution)
            // 3. Exclude validators with social proximity to study authors
            // 4. Weight by ValidatorReputation score from Governance DNA
            //    (call(OtherRole("governance"), "get_validator_reputation", agent_pubkey))
            // 5. Require at least one domain expert if constraints.require_domain_expert
            // 6. Randomly sample from weighted pool
            Ok(Vec::new()) // placeholder
        }

        // Signal type for UI notification
        #[derive(Debug, serde::Serialize, serde::Deserialize)]
        struct PhaseSignal {
            phase:    String,
            task_ref: ResearchHash,
        }
    }
}

// =============================================================================
// DNA 4: GOVERNANCE & HARMONY RECORDS
// =============================================================================
//
// Public DHT — governance-controlled writing, open reading.
//
// This is what journals, funders, and institutions query. External access is
// via the Holochain HTTP Gateway (v0.2, July 2025) — a standard HTTP/REST
// interface for non-participant callers who do not run a Holochain node.
//
// ONLY this DNA is exposed via the HTTP Gateway. The private DNAs
// (Researcher Repository, Validator Workspace) are never reachable externally.
//
// REST endpoints served via HTTP Gateway:
//   GET /api/v1/harmony/{request_ref}
//   GET /api/v1/badges/{request_ref}
//   GET /api/v1/validators/{agent_id}
//   GET /api/v1/harmony/discipline/{discipline}
//   GET /api/v1/governance/decisions
//
// integrity crate uses:  hdi::prelude::*
// coordinator crate uses: hdk::prelude::*
//
// dna.yaml properties:
//   system_coordinator_key: AgentPubKey  # only this key may write reputation scores

pub mod governance {

    use super::*;

    // =========================================================================
    // INTEGRITY ZOME — hdi::prelude::*
    // =========================================================================

    pub mod integrity {

        use super::*;

        // --- DNA Properties --------------------------------------------------

        #[dna_properties]
        #[derive(Debug, serde::Deserialize)]
        pub struct DnaProperties {
            /// The only AgentPubKey permitted to write ValidatorReputation entries.
            /// Any other author is rejected by the validate() callback.
            pub system_coordinator_key: AgentPubKey,
        }

        // --- Entry Types -----------------------------------------------------

        /// The canonical output of ValiChord.
        ///
        /// "Harmony" preserves the full texture of agreement AND disagreement.
        /// A record with 2 successes and 1 failure is more informative than a
        /// forced binary pass/fail. Disagreements are ALWAYS visible — this is
        /// a non-negotiable governance commitment.
        ///
        /// Assembled by the coordinator once all ValidationAttestation entries
        /// are present in the Attestation DNA for a given request_ref.
        ///
        /// IMMUTABLE after publication — enforced by validate() callback.
        ///
        /// Note on countersigning: the Technical Reference mentions using
        /// Holochain's native countersigning session for simultaneous reveal.
        /// In this implementation the coordinator assembles the record from
        /// independently-written attestations. Countersigning can be added in
        /// Phase 2 if the simultaneous-atomicity guarantee is required — the
        /// entry structure is compatible with either approach.
        #[hdk_entry_helper]
        #[entry_type(required_validations = 7)]
        #[derive(Debug, Clone)]
        pub struct HarmonyRecord {
            /// Links back to the ValidationRequest in the Attestation DNA.
            pub request_ref:        ResearchHash,
            pub validation_summary: ValidationSummary,
            pub validators:         Vec<ValidatorSummary>,
            /// Disagreements are always visible per governance commitment.
            /// The system refuses to average away meaningful scientific signals.
            pub disagreements:      Vec<Disagreement>,
            pub confidence_level:   ConfidenceLevel,
            pub status:             ReproducibilityStatus,
            /// 24-month minimum validity per governance policy.
            pub valid_until_secs:   u64,
            /// Link to full provenance chain in Attestation DNA.
            pub provenance_link:    String,
        }

        /// Participant counts — MUST satisfy the invariant:
        ///   successful + partial + failed + inconclusive == total_validators
        /// Enforced by the validate() callback on HarmonyRecord creation.
        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct ValidationSummary {
            pub total_validators:         u8,
            pub successful_validations:   u8,
            pub partial_validations:      u8,
            pub failed_validations:       u8,
            pub inconclusive_validations: u8,
            /// 0.0–1.0 agreement rate across all validators.
            pub agreement_level:          f64,
            pub outlier_count:            u8,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct ValidatorSummary {
            pub validator_id:       AgentPubKey,
            pub outcome:            AttestationOutcome,
            pub time_invested_secs: u64,
            pub confidence:         AttestationConfidence,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct Disagreement {
            pub description:         String,
            pub validators_involved: Vec<AgentPubKey>,
            pub resolution:          Option<String>,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum ConfidenceLevel {
            High   { agreement: f64, reasoning: String },
            Medium { concerns: Vec<String>, reasoning: String },
            Low    { substantial_disagreement: bool, reasoning: String },
        }

        /// ValiChord refuses to force a verdict where evidence doesn't support one.
        /// PersistentlyIndeterminate is a valid, informative outcome — not a failure.
        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum ReproducibilityStatus {
            ExactMatch       { validator_count: u8 },
            DirectionalMatch { validator_count: u8, variance_explanation: String },
            PartialMatch     { successful_aspects: Vec<String>, failed_aspects: Vec<String> },
            Failed           { failure_reasons: Vec<String>, validator_count: u8 },
            Inconclusive     { reasons: Vec<String> },
            PersistentlyIndeterminate {
                time_elapsed_secs:    u64,
                validator_count:      u8,
                disagreement_summary: String,
            },
        }

        /// Reproducibility badge. Cannot be reduced to a single gameable number.
        /// Issued only when the associated HarmonyRecord meets the badge thresholds.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct ReproducibilityBadge {
            pub harmony_record_ref: ResearchHash,
            pub badge_type:         BadgeType,
            pub level:              BadgeLevel,
            pub discipline:         Discipline,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum BadgeType {
            ComputationalReproducible,
            PreRegisteredAndValidated  { adherence_score: f64 },
            OpenDataValidated,
            MultiLabValidated          { lab_count: u8 },
        }

        #[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
        pub enum BadgeLevel {
            Bronze, // ≥3 validators, ≥60% success
            Silver, // ≥5 validators, ≥70%, pre-registered
            Gold,   // ≥7 validators, ≥80%, multi-institutional
        }

        /// Governance decision — every decision is logged immutably.
        /// The full decision history is always queryable and tamper-evident.
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct GovernanceDecision {
            pub decision_type: DecisionType,
            pub made_by:       GovernanceBody,
            pub rationale:     String,
            pub vote_tally:    Option<VoteTally>,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum DecisionType {
            DeviationApproved   { protocol_ref: ResearchHash },
            DeviationDenied     { protocol_ref: ResearchHash, reason: String },
            StandardUpdated     { discipline: Discipline },
            ValidatorSanctioned { validator_id: AgentPubKey, reason: String },
            PolicyChanged       { policy: String, old_value: String, new_value: String },
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum GovernanceBody {
            DeviationReviewBoard,
            DisciplinaryStandardsCommittee { discipline: Discipline },
            SteeringCommittee,
            CommunityVote,
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub struct VoteTally {
            pub for_votes:    u32,
            pub against_votes: u32,
            pub abstentions:  u32,
        }

        /// Multi-dimensional validator reputation. No single gameable score.
        ///
        /// ONLY the system_coordinator_key may write these entries.
        /// Enforced by the validate() callback — validators cannot edit their
        /// own scores. Individual dimensions prevent gaming that a total score
        /// would enable (e.g. padding validation count at expense of quality).
        #[hdk_entry_helper]
        #[derive(Debug, Clone)]
        pub struct ValidatorReputation {
            pub validator_id:                AgentPubKey,
            pub validation_score:            f64, // 0.0–1.0 quality across all attempts
            pub preregistration_quality:     f64, // quality of their own pre-registrations
            pub deviation_handling:          f64, // appropriate flagging of deviations
            pub time_investment_consistency: f64, // plausible, consistent time records
            pub peer_endorsements:           u32,
            pub expertise_areas:             Vec<(Discipline, ExpertiseLevel)>,
            pub total_validations:           u32,
            pub total_score:                 f64, // composite — recalculated by coordinator
        }

        #[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
        pub enum ExpertiseLevel { Novice, Competent, Expert, Authority }

        // --- Entry Types Enum ------------------------------------------------

        #[hdk_entry_types]
        #[unit_enum(UnitEntryTypes)]
        pub enum EntryTypes {
            HarmonyRecord(HarmonyRecord),
            ReproducibilityBadge(ReproducibilityBadge),
            GovernanceDecision(GovernanceDecision),
            ValidatorReputation(ValidatorReputation),
        }

        // --- Link Types ------------------------------------------------------

        #[hdk_link_types]
        pub enum LinkTypes {
            /// AgentPubKey → ValidatorReputation ActionHash
            ValidatorToReputation,
            /// ExternalHash anchor (request_ref) → HarmonyRecord ActionHash
            RequestToHarmonyRecord,
            /// GovernanceDecision ActionHash → affected target ActionHash
            DecisionToTarget,
            /// Path anchor → HarmonyRecord ActionHash, queryable by discipline
            /// Path format: "harmony.{discipline}.{YYYY_MM}"
            DisciplinePath,
            /// Path anchor → ReproducibilityBadge ActionHash
            /// Path format: "badges.{badge_type}"
            BadgePath,
        }

        // --- Validate Callback -----------------------------------------------

        #[hdk_extern]
        pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
            match op.flattened::<EntryTypes, LinkTypes>()? {

                // HarmonyRecord creation: verify participant count invariant.
                // successful + partial + failed + inconclusive MUST equal total_validators.
                FlatOp::StoreEntry(OpEntry::CreateEntry {
                    app_entry: EntryTypes::HarmonyRecord(ref record), ..
                }) => {
                    validate_harmony_record_counts(&record.validation_summary)
                }

                // HarmonyRecord is immutable after publication.
                FlatOp::RegisterUpdate(OpUpdate {
                    original_app_entry: EntryTypes::HarmonyRecord(_), ..
                }) => {
                    Ok(ValidateCallbackResult::Invalid(
                        "HarmonyRecord cannot be updated — the record is permanent".into()
                    ))
                }

                // ValidatorReputation: only system_coordinator_key may write.
                FlatOp::StoreEntry(OpEntry::CreateEntry {
                    app_entry: EntryTypes::ValidatorReputation(_),
                    ref action,
                    ..
                }) => {
                    validate_reputation_author(action.author())
                }

                FlatOp::RegisterUpdate(OpUpdate {
                    original_app_entry: EntryTypes::ValidatorReputation(_),
                    ref action,
                    ..
                }) => {
                    validate_reputation_author(action.author())
                }

                _ => Ok(ValidateCallbackResult::Valid),
            }
        }

        fn validate_harmony_record_counts(
            summary: &ValidationSummary,
        ) -> ExternResult<ValidateCallbackResult> {
            let count = summary.successful_validations
                + summary.partial_validations
                + summary.failed_validations
                + summary.inconclusive_validations;
            if count != summary.total_validators {
                return Ok(ValidateCallbackResult::Invalid(format!(
                    "HarmonyRecord: {} outcomes submitted but {} validators assigned. \
                     successful + partial + failed + inconclusive must equal total_validators.",
                    count, summary.total_validators
                )));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        fn validate_reputation_author(
            author: &AgentPubKey,
        ) -> ExternResult<ValidateCallbackResult> {
            let props = DnaProperties::try_from_dna_properties()?;
            if *author != props.system_coordinator_key {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the system coordinator may write ValidatorReputation entries".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }
    }

    // =========================================================================
    // COORDINATOR ZOME — hdk::prelude::*
    // =========================================================================

    pub mod coordinator {

        use super::*;
        use std::collections::BTreeSet;

        // --- init() — capability grants --------------------------------------
        //
        // ALL read functions are unrestricted — this DNA is the HTTP Gateway
        // target. Public readability is the design intent, not a gap.

        #[hdk_extern]
        pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
            let zome = zome_info()?.name;
            let mut public_fns = BTreeSet::new();
            for fn_name in &[
                "recv_remote_signal",
                "get_harmony_record",
                "get_harmony_records_for_discipline",
                "get_badge",
                "get_validator_reputation",
                "get_governance_decisions",
                "check_and_create_harmony_record",
            ] {
                public_fns.insert((zome.clone(), (*fn_name).into()));
            }
            create_cap_grant(ZomeCallCapGrant {
                tag: "public-read".into(),
                access: CapAccess::Unrestricted,
                functions: GrantedFunctions::Listed(public_fns),
            })?;
            Ok(InitCallbackResult::Pass)
        }

        // --- Write functions (membrane-gated) --------------------------------

        /// Called by the Attestation DNA coordinator's post_commit via
        /// call(OtherRole("governance"), ...) — author grant applies
        /// automatically for same-agent cross-DNA calls.
        ///
        /// Checks if all ValidationAttestations are present for request_ref.
        /// If yes, assembles and creates the HarmonyRecord.
        #[hdk_extern]
        pub fn check_and_create_harmony_record(
            request_ref: ResearchHash,
        ) -> ExternResult<()> {
            // TODO:
            // 1. call(OtherRole("attestation"), "get_attestations_for_request", request_ref)
            // 2. Check count against expected num_validators_required
            // 3. If complete: assemble HarmonyRecord from attestations
            // 4. create_harmony_record(assembled_record)
            // 5. If badge thresholds met: issue_badge(...)
            // 6. update_validator_reputation(...) for each validator
            Ok(())
        }

        #[hdk_extern]
        pub fn create_harmony_record(
            record: integrity::HarmonyRecord,
        ) -> ExternResult<ActionHash> {
            let record_hash = create_entry(EntryTypes::HarmonyRecord(record.clone()))?;
            // Index by request_ref for direct lookup
            let anchor = Path::from(format!("request.{}", hex::encode(record.request_ref)))
                .typed(LinkTypes::RequestToHarmonyRecord)?;
            anchor.ensure()?;
            create_link(
                anchor.path_entry_hash()?,
                record_hash.clone(),
                LinkTypes::RequestToHarmonyRecord,
                (),
            )?;
            // Index by discipline + month for analytics
            let disc_path = Path::from(
                format!("harmony.{:?}", record.discipline_tag())
            ).typed(LinkTypes::DisciplinePath)?;
            disc_path.ensure()?;
            create_link(
                disc_path.path_entry_hash()?,
                record_hash.clone(),
                LinkTypes::DisciplinePath,
                (),
            )?;
            Ok(record_hash)
        }

        #[hdk_extern]
        pub fn issue_badge(badge: integrity::ReproducibilityBadge) -> ExternResult<ActionHash> {
            let badge_hash = create_entry(EntryTypes::ReproducibilityBadge(badge))?;
            Ok(badge_hash)
        }

        #[hdk_extern]
        pub fn record_governance_decision(
            decision: integrity::GovernanceDecision,
        ) -> ExternResult<ActionHash> {
            create_entry(EntryTypes::GovernanceDecision(decision))
        }

        /// Only the system_coordinator_key agent may call this successfully.
        /// The validate() callback enforces the authorship check on-chain.
        #[hdk_extern]
        pub fn update_validator_reputation(
            reputation: integrity::ValidatorReputation,
        ) -> ExternResult<ActionHash> {
            let validator = reputation.validator_id.clone();
            let rep_hash = create_entry(EntryTypes::ValidatorReputation(reputation))?;
            create_link(
                validator,
                rep_hash.clone(),
                LinkTypes::ValidatorToReputation,
                (),
            )?;
            Ok(rep_hash)
        }

        // --- Read functions (unrestricted — HTTP Gateway targets) -------------

        #[hdk_extern]
        pub fn get_harmony_record(
            request_ref: ResearchHash,
        ) -> ExternResult<Option<Record>> {
            let anchor = Path::from(format!("request.{}", hex::encode(request_ref)))
                .typed(LinkTypes::RequestToHarmonyRecord)?;
            let links = get_links(
                GetLinksInputBuilder::try_new(
                    anchor.path_entry_hash()?,
                    LinkTypes::RequestToHarmonyRecord,
                )?.build(),
            )?;
            match links.first() {
                Some(link) => {
                    let target = link.target.clone().into_action_hash()
                        .ok_or(wasm_error!(WasmErrorInner::Guest("Invalid link".into())))?;
                    get(target, GetOptions::network())
                }
                None => Ok(None),
            }
        }

        #[hdk_extern]
        pub fn get_harmony_records_for_discipline(
            discipline: Discipline,
        ) -> ExternResult<Vec<Record>> {
            // TODO: Query discipline path and retrieve records.
            Ok(Vec::new())
        }

        #[hdk_extern]
        pub fn get_badge(
            request_ref: ResearchHash,
        ) -> ExternResult<Option<Record>> {
            // TODO: Query by harmony_record_ref
            Ok(None)
        }

        #[hdk_extern]
        pub fn get_validator_reputation(
            agent: AgentPubKey,
        ) -> ExternResult<Option<Record>> {
            let links = get_links(
                GetLinksInputBuilder::try_new(agent, LinkTypes::ValidatorToReputation)?.build(),
            )?;
            // Return the most recent reputation record (last link in the list).
            match links.last() {
                Some(link) => {
                    let target = link.target.clone().into_action_hash()
                        .ok_or(wasm_error!(WasmErrorInner::Guest("Invalid link".into())))?;
                    get(target, GetOptions::network())
                }
                None => Ok(None),
            }
        }

        #[hdk_extern]
        pub fn get_governance_decisions(
            limit: u32,
        ) -> ExternResult<Vec<Record>> {
            // TODO: Query decisions path with pagination
            Ok(Vec::new())
        }

        #[hdk_extern]
        pub fn recv_remote_signal(signal: SerializedBytes) -> ExternResult<()> {
            emit_signal(signal)?;
            Ok(())
        }

        /// Evaluate HarmonyRecord outcome and issue badge if thresholds are met.
        pub fn evaluate_badge_threshold(
            record: &integrity::HarmonyRecord,
        ) -> Option<integrity::BadgeLevel> {
            let s = &record.validation_summary;
            let success_rate = (s.successful_validations + s.partial_validations) as f64
                / s.total_validators as f64;

            if s.total_validators >= 7 && success_rate >= 0.80 {
                Some(integrity::BadgeLevel::Gold)
            } else if s.total_validators >= 5 && success_rate >= 0.70 {
                Some(integrity::BadgeLevel::Silver)
            } else if s.total_validators >= 3 && success_rate >= 0.60 {
                Some(integrity::BadgeLevel::Bronze)
            } else {
                None
            }
        }
    }
}

// =============================================================================
// TESTS
// =============================================================================
//
// These are unit tests for business logic that does not require a running
// Holochain conductor. Integration and multi-agent tests belong in Tryorama.
//
// TRYORAMA TEST PRIORITY ORDER (see SCAFFOLDING_PLAN.md for full specifications):
//
//   1. Membrane proof acceptance/rejection for Attestation DNA
//   2. Commit-reveal round: validator seals private attestation → all sealed
//      → reveal window opens → ValidationAttestation written → HarmonyRecord created
//   3. Phase transition driven by DHT polling — NOT by signal delivery
//   4. Offline validator scenario: misses signal, reconnects, learns phase from DHT
//   5. ValidationAttestation immutability: attempt update → rejected by validate()
//   6. HarmonyRecord count mismatch → rejected by validate()
//   7. ValidatorReputation write by non-coordinator → rejected by validate()
//   8. Gaming detection: identical outcomes pattern flagged in coordinator

#[cfg(test)]
mod tests {
    use super::*;

    // --- Validate business logic (no conductor required) ---------------------

    #[test]
    fn harmony_record_count_invariant_satisfied() {
        let summary = governance::integrity::ValidationSummary {
            total_validators:         3,
            successful_validations:   2,
            partial_validations:      1,
            failed_validations:       0,
            inconclusive_validations: 0,
            agreement_level:          0.8,
            outlier_count:            0,
        };
        let count = summary.successful_validations
            + summary.partial_validations
            + summary.failed_validations
            + summary.inconclusive_validations;
        assert_eq!(count, summary.total_validators,
            "successful + partial + failed + inconclusive must equal total_validators");
    }

    #[test]
    fn harmony_record_count_invariant_violated() {
        // Simulate what validate() must catch: only 2 outcomes for 3 validators.
        let summary = governance::integrity::ValidationSummary {
            total_validators:         3,
            successful_validations:   1,
            partial_validations:      1,
            failed_validations:       0,
            inconclusive_validations: 0,
            agreement_level:          0.5,
            outlier_count:            0,
        };
        let count = summary.successful_validations
            + summary.partial_validations
            + summary.failed_validations
            + summary.inconclusive_validations;
        assert_ne!(count, summary.total_validators,
            "Test confirms validate() would reject this record");
    }

    // --- Badge threshold evaluation ------------------------------------------

    #[test]
    fn badge_threshold_gold() {
        let summary = governance::integrity::ValidationSummary {
            total_validators:         7,
            successful_validations:   6,
            partial_validations:      1,
            failed_validations:       0,
            inconclusive_validations: 0,
            agreement_level:          0.9,
            outlier_count:            0,
        };
        // 7 validators, 100% success → Gold
        let success_rate = (summary.successful_validations + summary.partial_validations) as f64
            / summary.total_validators as f64;
        assert!(summary.total_validators >= 7);
        assert!(success_rate >= 0.80);
    }

    #[test]
    fn badge_threshold_no_badge() {
        let summary = governance::integrity::ValidationSummary {
            total_validators:         3,
            successful_validations:   1,
            partial_validations:      0,
            failed_validations:       2,
            inconclusive_validations: 0,
            agreement_level:          0.33,
            outlier_count:            2,
        };
        // 3 validators, 33% success → no badge
        let success_rate = (summary.successful_validations + summary.partial_validations) as f64
            / summary.total_validators as f64;
        assert!(success_rate < 0.60, "33% success should not qualify for any badge");
    }

    // --- Difficulty assessment scoring ---------------------------------------

    #[test]
    fn difficulty_assessment_easy_study() {
        // Low code volume, excellent docs, open data, recent → Standard tier
        let weighted = difficulty_score(2, 1, 5, 5, 1, 1);
        assert!(weighted < 1.5, "Easy study should score < 1.5 (Standard tier)");
    }

    #[test]
    fn difficulty_assessment_hard_study() {
        // High code volume, poor docs, restricted data, old → Extreme tier
        let weighted = difficulty_score(5, 5, 1, 1, 5, 5);
        assert!(weighted >= 3.5, "Hard study should score >= 3.5 (Extreme tier)");
    }

    /// Weighted difficulty score computation.
    /// Weights are PLACEHOLDERS — Phase 0 regression determines real values.
    fn difficulty_score(
        code_volume:           u8,
        dependency_count:      u8,
        documentation_quality: u8,
        data_accessibility:    u8,
        environment_complexity: u8,
        study_age_years:       u8,
    ) -> f64 {
        (code_volume            as f64 * 0.15)
        + (dependency_count     as f64 * 0.20)
        + ((5 - documentation_quality)  as f64 * 0.25) // inverse: poor docs = harder
        + ((5 - data_accessibility)     as f64 * 0.20) // inverse: restricted = harder
        + (environment_complexity as f64 * 0.10)
        + (study_age_years      as f64 * 0.10)
    }

    // --- AttestationOutcome --------------------------------------------------

    #[test]
    fn attestation_outcome_variants_serialise() {
        // Verify all variants can be created — catches enum definition issues.
        let _ = AttestationOutcome::Reproduced;
        let _ = AttestationOutcome::PartiallyReproduced { details: "some match".into() };
        let _ = AttestationOutcome::FailedToReproduce   { details: "no match".into()  };
        let _ = AttestationOutcome::UnableToAssess      { reason:  "no access".into() };
    }
}
