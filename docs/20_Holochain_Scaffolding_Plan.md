# ValiChord — Holochain Scaffolding Plan

**Author:** Generated from full document analysis (Technical Reference v12, Scaffold v10, Holochain Build Guide knowledge base)
**Date:** March 2026
**Status:** Engineering specification — ready for Shin Sakamoto / Phase 1 implementation

---

## Directory Structure

```
valichord/
├── happ.yaml                          # hApp bundle: four DNA roles
├── shared_types/                      # Common Rust crate (not a zome)
│   ├── Cargo.toml
│   └── src/lib.rs                     # ExternalHash, Discipline, AgentId aliases
├── dnas/
│   ├── researcher_repository/
│   │   ├── dna.yaml
│   │   └── zomes/
│   │       ├── researcher_integrity/  # hdi crate — entry/link types, validate
│   │       │   ├── Cargo.toml
│   │       │   └── src/lib.rs
│   │       └── researcher_coordinator/ # hdk crate — CRUD, init, post_commit
│   │           ├── Cargo.toml
│   │           └── src/lib.rs
│   ├── validator_workspace/
│   │   ├── dna.yaml
│   │   └── zomes/
│   │       ├── workspace_integrity/
│   │       │   ├── Cargo.toml
│   │       │   └── src/lib.rs
│   │       └── workspace_coordinator/
│   │           ├── Cargo.toml
│   │           └── src/lib.rs
│   ├── attestation/
│   │   ├── dna.yaml                   # DNA properties baked in here
│   │   └── zomes/
│   │       ├── attestation_integrity/
│   │       │   ├── Cargo.toml
│   │       │   └── src/lib.rs
│   │       └── attestation_coordinator/
│   │           ├── Cargo.toml
│   │           └── src/lib.rs
│   └── governance/
│       ├── dna.yaml                   # DNA properties baked in here
│       └── zomes/
│           ├── governance_integrity/
│           │   ├── Cargo.toml
│           │   └── src/lib.rs
│           └── governance_coordinator/
│               ├── Cargo.toml
│               └── src/lib.rs
└── ui/                                # Front end (React / Svelte / Lit)
    └── src/
```

**happ.yaml roles:**

```yaml
roles:
  - name: researcher_repository
    provisioning: { strategy: create, deferred: false }
    dna:
      path: dnas/researcher_repository/workdir/researcher_repository.dna
  - name: validator_workspace
    provisioning: { strategy: create, deferred: false }
    dna:
      path: dnas/validator_workspace/workdir/validator_workspace.dna
  - name: attestation
    provisioning: { strategy: create, deferred: false }
    dna:
      path: dnas/attestation/workdir/attestation.dna
  - name: governance
    provisioning: { strategy: create, deferred: false }
    dna:
      path: dnas/governance/workdir/governance.dna
```

---

## Shared Types Crate

Imported by all four integrity zomes. Keeps type definitions DRY and consistent across DNAs.

```rust
// shared_types/src/lib.rs

/// SHA-256 digest — for research file fingerprints only.
/// Holochain's internal addressing uses BLAKE2b (not SHA-256).
/// Compute via `sha2` crate compiled to WASM. Store as ExternalHash.
pub type ExternalHash = [u8; 32];

/// In real implementation: use HDK's native AgentPubKey (39 bytes).
/// This alias is for readability in the scaffold.
pub type AgentId = Vec<u8>;

pub type ValidatorId = AgentId;

/// Extensible via governance decision — not by code change.
#[derive(Debug, Clone, Hash, Eq, PartialEq, Serialize, Deserialize)]
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AttestationOutcome {
    Reproduced,
    PartiallyReproduced { details: String },
    FailedToReproduce   { details: String },
    UnableToAssess      { reason: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AttestationConfidence { High, Medium, Low }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeBreakdown {
    pub environment_setup_secs: u64,
    pub data_acquisition_secs:  u64,
    pub code_execution_secs:    u64,
    pub troubleshooting_secs:   u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DeviationType {
    DataAccess       { reason: String, impact: EpistemicImpact },
    EthicalConcern   { review_board: String },
    ModelFailure     { attempted_model: String, fallback_model: String, justification: String },
    ComputationalLimit { planned_method: String, actual_method: String, reason: String },
    SampleSizeAdjustment { original_n: usize, revised_n: usize, power_analysis: String },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EpistemicImpact { Minimal, Moderate, Substantial }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Severity { Minor, Moderate, Major, Critical }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputationalResources {
    pub personal_hardware_sufficient:  bool,
    pub hpc_required:                  bool,
    pub gpu_required:                  bool,
    pub cloud_compute_required:        bool,
    pub estimated_compute_cost_pence:  Option<u64>,
}
```

---

## DNA 1 — Researcher Repository

**Membrane:** Private — researcher only. No other agent can join.
**Purpose:** Hold research materials locally. Only a SHA-256 hash travels outward to DNA 3.
**GDPR:** Enforced architecturally — sensitive data cannot enter the shared DHT.

### dna.yaml

```yaml
manifest_version: "1"
name: researcher_repository
integrity:
  network_seed: ~        # set per deployment
  properties: ~          # no properties needed — single-agent private DNA
  origin_time: ~
  zomes:
    - name: researcher_integrity
      bundled: ./zomes/researcher_integrity.wasm
coordinator_zomes:
  - name: researcher_coordinator
    bundled: ./zomes/researcher_coordinator.wasm
    dependencies:
      - name: researcher_integrity  # always explicit per known Holochain bug
```

### Integrity Zome — Entry Types

```rust
// No creator_id or created_at fields — Holochain Actions carry these natively.

#[hdk_entry_helper]
pub struct VerifiedDataSnapshot {
    pub sha256_hash:       ExternalHash,       // the integrity fingerprint
    pub storage_locations: Vec<StorageLocation>,
    pub size_bytes:        u64,
}

pub enum StorageLocation {
    Zenodo       { deposit_id: String },
    Figshare     { article_id: String },
    Osf          { project_id: String },
    GitHub       { repo: String, commit_sha: String },
    Institutional { url: String },
    S3           { bucket: String, region: String },
    Other        { provider: String, location: String },
}

#[hdk_entry_helper]
pub struct PreRegisteredProtocol {
    pub analysis_plan_description: String,
    pub hypotheses:                Vec<Hypothesis>,
    pub analysis_type:             AnalysisType,
    pub primary_outcomes:          Vec<OutcomeMeasure>,
    pub secondary_outcomes:        Vec<OutcomeMeasure>,
    pub stopping_rules:            String,
    pub sample_size_n:             usize,
    pub sample_size_justification: String,
    pub allowed_deviation_types:   Vec<DeviationType>,
    pub institutional_approval:    Option<Vec<u8>>,  // signature bytes
    pub external_links:            ExternalLinks,
}

/// Separate entry, not an update to PreRegisteredProtocol.
/// Holochain's source chain already provides immutable modification history
/// via update_entry — DeclaredDeviation provides the *structured reason*.
#[hdk_entry_helper]
pub struct DeclaredDeviation {
    pub protocol_action_hash: ActionHash,   // links to the specific protocol version
    pub deviation_type:       DeviationType,
    pub justification:        String,
    pub epistemic_impact:     EpistemicImpact,
}

// Supporting types
pub struct Hypothesis {
    pub statement:   String,
    pub formal_spec: Option<FormalClaim>,
    pub claim_type:  ClaimType,
}
pub struct FormalClaim {
    pub null_hypothesis:        String,
    pub alternative_hypothesis: String,
    pub significance_threshold: f64,
    pub test_statistic:         String,
    pub direction:              Direction,
}
pub enum Direction    { TwoSided, GreaterThan, LessThan }
pub enum ClaimType    { Primary, Secondary, Exploratory { disclosed: bool }, Robustness }
pub enum AnalysisType { Confirmatory, Exploratory, Mixed }
pub struct OutcomeMeasure { pub name: String, pub specification: String }
pub struct ExternalLinks {
    pub osf_project:          Option<String>,
    pub github_repo:          Option<String>,
    pub preregistration_doi:  Option<String>,
    pub trial_registry:       Option<String>,
    pub publication_doi:      Option<String>,
}

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    VerifiedDataSnapshot(VerifiedDataSnapshot),
    PreRegisteredProtocol(PreRegisteredProtocol),
    DeclaredDeviation(DeclaredDeviation),
}
```

### Integrity Zome — Link Types

```rust
#[hdk_link_types]
pub enum LinkTypes {
    /// protocol ActionHash → snapshot ActionHash
    ProtocolToSnapshot,
    /// protocol ActionHash → deviation ActionHash (modification history)
    ProtocolToDeviation,
    /// study ExternalHash anchor → protocol ActionHash
    StudyToProtocol,
}
```

### Integrity Zome — Validate

Standard Holochain source chain integrity only. The researcher is the sole participant — no custom membrane rules or cross-agent validation needed. Use default `ValidateCallbackResult::Valid` for all ops. Holochain enforces sequence ordering, author signatures, and append-only history natively.

### Coordinator Zome — Functions

```rust
// Public API:
#[hdk_extern] pub fn submit_protocol(p: PreRegisteredProtocol) -> ExternResult<ActionHash>
#[hdk_extern] pub fn declare_deviation(d: DeclaredDeviation)   -> ExternResult<ActionHash>
#[hdk_extern] pub fn upload_snapshot(s: VerifiedDataSnapshot)  -> ExternResult<ActionHash>
#[hdk_extern] pub fn get_protocol(hash: ActionHash)            -> ExternResult<Option<Record>>
#[hdk_extern] pub fn get_protocol_history(hash: ActionHash)    -> ExternResult<Vec<Record>>
// get_protocol_history: calls get_details(hash) and traverses update chain

// No init() needed — single-agent private DNA, no capability grants required.
// No post_commit signals needed from this DNA.
```

---

## DNA 2 — Validator Workspace

**Membrane:** Private — one validator only. Each validator runs their own instance.
**Purpose:** Isolated reproduction environment. Private attestation sealed here (the commit phase). Only the signed outcome summary leaves this space.

### dna.yaml

Same structure as researcher_repository. No DNA properties needed — single-agent.

### Integrity Zome — Entry Types

```rust
#[hdk_entry_helper]
pub struct ValidationTask {
    /// ExternalHash of the task assignment from Attestation DNA
    pub task_id:               ExternalHash,
    /// References the ValidationRequest entry in Attestation DNA
    pub request_ref:           ExternalHash,
    pub validation_focus:      ValidationFocus,
    pub time_cap_secs:         u64,
    pub estimated_min_secs:    u64,
    pub estimated_max_secs:    u64,
    pub compensation_tier:     CompensationTier,
}

/// THE COMMIT PHASE — private visibility.
/// Stored only on this validator's local source chain.
/// Invisible to peers and to the shared DHT.
/// Its *existence* is verifiable; its *contents* are not visible
/// until the validator participates in the countersigning reveal.
#[hdk_entry_helper]
#[entry_type(visibility = "private")]
pub struct ValidatorPrivateAttestation {
    pub task_ref:               ExternalHash,
    pub outcome:                AttestationOutcome,
    pub detailed_report:        String,
    pub time_invested_secs:     u64,
    pub time_breakdown:         TimeBreakdown,
    pub confidence:             AttestationConfidence,
    pub deviation_flags:        Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
}

pub struct UndeclaredDeviation {
    pub deviation_type: DeviationType,
    pub severity:       Severity,
    pub evidence:       String,
}

pub enum ValidationFocus {
    ComputationalReproducibility,
    PreCommitmentAdherence,
    MethodologicalReview,
}

/// PLACEHOLDER amounts — Phase 0 evidence determines real values.
pub enum CompensationTier {
    Tier1 { amount_pence: u64 },   // ~1–2 hours: £50–100
    Tier2 { amount_pence: u64 },   // ~4–8 hours: £200–400
    Tier3 { amount_pence: u64 },   // ~16+ hours: £800–1600
}

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    ValidationTask(ValidationTask),
    #[entry_type(visibility = "private")]
    ValidatorPrivateAttestation(ValidatorPrivateAttestation),
}
```

### Integrity Zome — Link Types

```rust
#[hdk_link_types]
pub enum LinkTypes {
    /// task ActionHash → private attestation ActionHash
    TaskToPrivateAttestation,
}
```

### Integrity Zome — Validate

Standard source chain integrity only — single agent. No custom rules.

### Coordinator Zome — Functions

```rust
#[hdk_extern] pub fn receive_task(task: ValidationTask) -> ExternResult<ActionHash>
#[hdk_extern] pub fn seal_private_attestation(a: ValidatorPrivateAttestation) -> ExternResult<ActionHash>
// seal_private_attestation writes a private entry — never enters DHT.
#[hdk_extern] pub fn get_task(task_ref: ExternalHash)  -> ExternResult<Option<Record>>
#[hdk_extern] pub fn get_my_attestation(task_ref: ExternalHash) -> ExternResult<Option<Record>>

// post_commit callback — fires AFTER private attestation is confirmed written:
// Send remote signal to Attestation DNA coordinator that this validator's
// commitment is sealed and ready. Signals are notification only — the
// Attestation DNA must poll DHT state, not rely on signal delivery.
#[hdk_extern(infallible)]
pub fn post_commit(actions: Vec<SignedActionHashed>) -> ExternResult<()> {
    // For each ValidatorPrivateAttestation action in the batch:
    //   call(OtherRole("attestation"), "notify_commitment_sealed", task_ref)
    Ok(())
}
```

---

## DNA 3 — Attestation

**Membrane:** Shared DHT — credentialed participants only (institutional credential required).
**Purpose:** The coordination layer. Records the *act* of validation. All inter-validator `call_remote` happens here.

### dna.yaml — DNA Properties

These are baked into the DNA hash — immutable per network instance.

```yaml
properties:
  authorized_joining_certificate_issuer: "uhCAk..."  # AgentPubKey of credential issuer
  discipline: "genomics"                              # one network per discipline
  minimum_validators: 3
```

Access in code:

```rust
#[dna_properties]
pub struct DnaProperties {
    pub authorized_joining_certificate_issuer: AgentPubKey,
    pub discipline:         String,
    pub minimum_validators: u32,
}
// DnaProperties::try_from_dna_properties()?
```

### Integrity Zome — Entry Types

```rust
/// Submitted by researcher to kick off a validation round.
#[hdk_entry_helper]
pub struct ValidationRequest {
    /// ActionHash of PreRegisteredProtocol in researcher's private DNA,
    /// transmitted as ExternalHash (SHA-256 of the protocol entry bytes).
    pub protocol_ref:           Option<ExternalHash>,
    /// SHA-256 hash of study data — the ONLY thing from the private DNA
    /// that travels to this shared network.
    pub data_hash:              ExternalHash,
    pub num_validators_required: u8,
    pub validation_tier:        ValidationTier,
    pub discipline:             Discipline,
}

pub enum ValidationTier { Basic, Enhanced, Comprehensive }

/// THE REVEAL PHASE — written to shared DHT during the reveal session.
/// IMMUTABLE after publication — enforced by validate() callback.
/// Written once all validators have sealed private attestations and
/// the reveal window has opened.
#[hdk_entry_helper]
#[entry_type(required_validations = 7)]  // higher threshold for critical entries
pub struct ValidationAttestation {
    pub request_ref:             ExternalHash,
    pub outcome:                 AttestationOutcome,
    pub outcome_summary:         OutcomeSummary,  // structured for agreement detection
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub confidence:              AttestationConfidence,
    pub deviation_flags:         Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
}

/// Structured outcome for agreement detection across validators.
/// Agreement is assessed on these summaries — NOT on raw result hashes
/// (because reproduction almost never produces bit-identical outputs).
pub struct OutcomeSummary {
    pub key_metrics:                Vec<MetricResult>,
    pub effect_direction_matches:   Option<bool>,
    pub confidence_interval_overlap: Option<f64>,
    pub overall_agreement:          AgreementLevel,
}

pub struct MetricResult {
    pub metric_name:     String,
    pub produced_value:  String,
    pub expected_value:  String,
    pub within_tolerance: bool,
}

pub enum AgreementLevel {
    ExactMatch,
    WithinTolerance,
    DirectionalMatch,
    Divergent,
    UnableToAssess,
}

/// Published to the shared DHT so the assignment engine can query availability.
#[hdk_entry_helper]
pub struct ValidatorProfile {
    pub institution:         String,
    pub disciplines:         Vec<Discipline>,
    pub certification_tier:  CertificationTier,
    pub available:           bool,
    pub max_concurrent_tasks: u8,
}

pub enum CertificationTier {
    Provisional,  // < 10 completed validations
    Certified,    // ≥ 10 in good standing
    Senior,       // ≥ 50 in excellent standing
}

/// Surface-feature scoring for difficulty prediction.
/// PLACEHOLDER weights — Phase 0 regression determines real values.
#[hdk_entry_helper]
pub struct DifficultyAssessment {
    pub request_ref:             ExternalHash,
    pub code_volume:             u8,  // 1–5
    pub dependency_count:        u8,  // 1–5
    pub documentation_quality:   u8,  // 1–5 (5 = excellent)
    pub data_accessibility:      u8,  // 1–5 (5 = fully open)
    pub environment_complexity:  u8,  // 1–5
    pub study_age_years:         u8,  // 1–5 (5 = very old)
    pub predicted_tier:          DifficultyTier,
    pub predicted_min_secs:      u64,
    pub predicted_max_secs:      u64,
    pub confidence:              AssessmentConfidence,
}

pub enum DifficultyTier {
    Standard,   // ~4–8 hours
    Moderate,   // ~8–16 hours
    Complex,    // ~16–30 hours
    Extreme,    // ~30+ hours — flag for triage
    Excluded,   // Fails minimum criteria
}

pub enum AssessmentConfidence { High, Medium, Low }

pub struct UndeclaredDeviation {
    pub deviation_type: DeviationType,
    pub severity:       Severity,
    pub evidence:       String,
}

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    ValidationRequest(ValidationRequest),
    ValidationAttestation(ValidationAttestation),
    ValidatorProfile(ValidatorProfile),
    DifficultyAssessment(DifficultyAssessment),
}
```

### Integrity Zome — Link Types

```rust
#[hdk_link_types]
pub enum LinkTypes {
    /// ExternalHash (study data hash) anchor → ValidationRequest ActionHash
    StudyToValidation,
    /// AgentPubKey → ValidationAttestation ActionHash (all attestations by this validator)
    ValidatorToAttestation,
    /// ExternalHash (request ref) anchor → HarmonyRecord ActionHash in Governance DNA
    RequestToHarmonyRecord,
    /// AgentPubKey → ValidatorProfile ActionHash
    AgentToProfile,
    /// Path anchor → ValidationRequest ActionHash (queryable by status)
    /// Path: "requests.{status}.{discipline}"
    StatusPath,
    /// Path anchor → ValidationRequest ActionHash (queryable by institution)
    /// Path: "institutions.{institution_id}"
    InstitutionPath,
    /// Path anchor → ValidationAttestation ActionHash (queryable by discipline)
    /// Path: "attestations.{discipline}.{year_month}"
    DisciplinePath,
}
```

### Integrity Zome — Validate Callback

**Critical:** guarded arms (attestation immutability) MUST precede unguarded arms in the match. Rust evaluates match arms in order — an unguarded arm earlier in the list would swallow everything below it silently.

```rust
#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- ARM 1: ValidationAttestation is IMMUTABLE after publication ---
        // Must be first. Guards check entry type before the generic arms below.
        FlatOp::RegisterUpdate(OpUpdate { original_action, .. })
            if is_attestation(&original_action) =>
        {
            Ok(ValidateCallbackResult::Invalid(
                "ValidationAttestation cannot be updated — the record is permanent".into()
            ))
        }
        FlatOp::RegisterDelete(OpDelete { original_action, .. })
            if is_attestation(&original_action) =>
        {
            Ok(ValidateCallbackResult::Invalid(
                "ValidationAttestation cannot be deleted — the record is permanent".into()
            ))
        }

        // --- ARM 2: ValidationRequest — only original author may update/delete ---
        FlatOp::RegisterUpdate(OpUpdate { original_action, .. }) => {
            let original = must_get_action(original_action)?;
            if op.action().author() != original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original requester may update a ValidationRequest".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }
        FlatOp::RegisterDelete(OpDelete { original_action, .. }) => {
            let original = must_get_action(original_action)?;
            if op.action().author() != original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original requester may delete a ValidationRequest".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ARM 3: Membrane proof — full credential check after network join ---
        // genesis_self_check() handles format-only check before join (no DHT access).
        // This arm handles the DHT-dependent full verification:
        //   - Does the issuing authority exist on the DHT?
        //   - Is the credential signed by authorized_joining_certificate_issuer?
        //   - Is the signature over the joining agent's key correct?
        FlatOp::RegisterAgentActivity(OpActivity::CreateAgent { membrane_proof, .. }) => {
            validate_membrane_proof(membrane_proof)
        }

        _ => Ok(ValidateCallbackResult::Valid),
    }
}

#[hdk_extern]
pub fn genesis_self_check(data: GenesisSelfCheckData) -> ExternResult<GenesisSelfCheckCallbackResult> {
    // Format-only check — no DHT access. Runs before network join.
    // Verify membrane_proof is present and is the correct byte length for a credential.
    match data.membrane_proof {
        None => Ok(GenesisSelfCheckCallbackResult::Invalid(
            "Attestation DNA requires a membrane proof (institutional credential)".into()
        )),
        Some(proof) if proof.bytes().len() < 64 => Ok(GenesisSelfCheckCallbackResult::Invalid(
            "Membrane proof is too short to be a valid credential signature".into()
        )),
        _ => Ok(GenesisSelfCheckCallbackResult::Valid),
    }
}
```

### Coordinator Zome — init() Capability Grants

```rust
#[hdk_extern]
pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
    // Unrestricted: public read functions + remote signal receiver
    let mut public_fns = BTreeSet::new();
    public_fns.insert((zome_info()?.name, "recv_remote_signal".into()));
    public_fns.insert((zome_info()?.name, "get_validation_request".into()));
    public_fns.insert((zome_info()?.name, "get_attestations_for_request".into()));
    public_fns.insert((zome_info()?.name, "get_validators_for_discipline".into()));
    public_fns.insert((zome_info()?.name, "check_all_commitments_sealed".into()));
    public_fns.insert((zome_info()?.name, "notify_commitment_sealed".into()));
    create_cap_grant(ZomeCallCapGrant {
        tag: "public-read".into(),
        access: CapAccess::Unrestricted,
        functions: GrantedFunctions::Listed(public_fns),
    })?;

    // Write functions (submit_attestation, submit_validation_request) require
    // a valid membrane proof — access controlled via membrane, not capability.
    // They are not unrestricted.

    Ok(InitCallbackResult::Pass)
}
```

### Coordinator Zome — Functions

```rust
// Write functions (membrane-gated):
#[hdk_extern] pub fn submit_validation_request(r: ValidationRequest) -> ExternResult<ActionHash>
#[hdk_extern] pub fn submit_attestation(a: ValidationAttestation)    -> ExternResult<ActionHash>
#[hdk_extern] pub fn publish_validator_profile(p: ValidatorProfile)  -> ExternResult<ActionHash>
#[hdk_extern] pub fn assess_difficulty(request_ref: ExternalHash)    -> ExternResult<ActionHash>

// Read functions (unrestricted):
#[hdk_extern] pub fn get_validation_request(hash: ActionHash)        -> ExternResult<Option<Record>>
#[hdk_extern] pub fn get_attestations_for_request(r: ExternalHash)   -> ExternResult<Vec<Record>>
#[hdk_extern] pub fn get_validators_for_discipline(d: Discipline)    -> ExternResult<Vec<Record>>
#[hdk_extern] pub fn get_validator_profile(agent: AgentPubKey)       -> ExternResult<Option<Record>>

// Protocol coordination:
#[hdk_extern] pub fn notify_commitment_sealed(task_ref: ExternalHash) -> ExternResult<()>
// Called by a validator's Workspace DNA via post_commit → call(OtherRole("attestation"), ...).
// Checks if all expected validators have sealed their commitments.
// If yes: writes a PhaseMarker entry to the DHT opening the reveal window.
// Signals are notification only — this DHT-poll check is the real gate.

#[hdk_extern] pub fn check_all_commitments_sealed(r: ExternalHash)   -> ExternResult<bool>
// Polls get_agent_activity for each assigned validator.
// Returns true when all have a ValidatorPrivateAttestation action on their chain.

#[hdk_extern] pub fn recv_remote_signal(signal: SerializedBytes)      -> ExternResult<()>

// post_commit: after a ValidationAttestation is confirmed written,
// signal the Governance DNA coordinator to check if all attestations are in.
#[hdk_extern(infallible)]
pub fn post_commit(actions: Vec<SignedActionHashed>) -> ExternResult<()> {
    // For each ValidationAttestation action:
    //   call(OtherRole("governance"), "check_and_create_harmony_record", request_ref)
    Ok(())
}
```

### Gaming & Collusion Detection

Runs in coordinator zome — NOT in validate(). Validation callbacks must be deterministic; gaming detection is statistical and cross-agent.

```rust
// Called before accepting an attestation into the reveal window:
pub fn detect_gaming_patterns(validator: AgentPubKey, history: Vec<ValidationAttestation>) -> Vec<GamingFlag>

pub enum GamingFlag {
    SuspiciousAgreementPattern { with_validator: AgentPubKey, agreement_rate: f64 },
    UnrealisticallyFast        { expected_min_secs: u64, actual_secs: u64 },
    RubberStamping             { approval_rate: f64, avg_time_secs: u64 },
    SocialProximity            { distance: u8, shared_publications: u32 },
}
// Thresholds: PLACEHOLDER — Phase 0 empirical data required to calibrate.
// Example: SuspiciousAgreementPattern fires at >90% match over 20+ events.
// On confirmed gaming: any peer issues a Warrant DHT op via get_agent_activity.
// Application layer checks warrants before accepting protocol participation.
```

### Validator Assignment Logic

```rust
pub struct AssignmentConstraints {
    pub max_institutional_share: f64,   // default 0.4 (40%)
    pub min_validators:          u8,    // default 3 (from DNA properties)
    pub require_domain_expert:   bool,  // default true
    pub double_blind:            bool,  // default true — validators never see author identity
}

// Selection algorithm:
// 1. Filter available ValidatorProfile entries by discipline + certification tier
// 2. Apply institutional cap (max 40% from same institution)
// 3. Exclude validators with social proximity to study authors (co-authorship graph)
// 4. Weight by ValidatorReputation score from Governance DNA
// 5. Require at least one domain expert
// 6. Randomly sample from weighted pool
```

---

## DNA 4 — Governance & Harmony Records

**Membrane:** Public DHT — governance-controlled writing, open reading.
**Purpose:** Final outputs: Harmony Records, badges, governance decisions, reputation. What journals, funders, and institutions query.
**External access:** HTTP Gateway (Holochain v0.2+) — journals/funders reach this DNA over standard HTTP/REST without running a Holochain node.

### dna.yaml — DNA Properties

```yaml
properties:
  system_coordinator_key: "uhCAk..."  # only this AgentPubKey may write reputation scores
```

### Integrity Zome — Entry Types

```rust
/// The canonical output of ValiChord.
/// "Harmony" = preserving agreement AND disagreement.
/// A 2-success-1-failure record is more informative than a forced pass/fail.
///
/// Written via countersigning session — all assigned validators simultaneously
/// countersign this single entry. This IS the reveal: all findings become
/// visible simultaneously. No validator can see others' results before signing.
#[hdk_entry_helper]
#[entry_type(required_validations = 7)]
pub struct HarmonyRecord {
    pub request_ref:       ExternalHash,  // links back to ValidationRequest in DNA 3
    pub validation_summary: ValidationSummary,
    pub validators:        Vec<ValidatorSummary>,
    pub disagreements:     Vec<Disagreement>,  // always visible — governance commitment
    pub confidence_level:  ConfidenceLevel,
    pub status:            ReproducibilityStatus,
    pub valid_until_secs:  u64,  // 24-month minimum per governance policy
    pub provenance_link:   String,
}

pub struct ValidationSummary {
    pub total_validators:          u8,
    pub successful_validations:    u8,
    pub partial_validations:       u8,
    pub failed_validations:        u8,
    pub inconclusive_validations:  u8,
    // successful + partial + failed + inconclusive MUST equal total_validators
    // Enforced by validate() callback.
    pub agreement_level:           f64,
    pub outlier_count:             u8,
}

pub struct ValidatorSummary {
    pub validator_id:    ValidatorId,
    pub outcome:         AttestationOutcome,
    pub time_invested_secs: u64,
    pub confidence:      String,
}

pub struct Disagreement {
    pub description:          String,
    pub validators_involved:  Vec<ValidatorId>,
    pub resolution:           Option<String>,
}

pub enum ConfidenceLevel {
    High   { agreement: f64, reasoning: String },
    Medium { concerns: Vec<String>, reasoning: String },
    Low    { substantial_disagreement: bool, reasoning: String },
}

/// ValiChord refuses to force a verdict where evidence doesn't support one.
pub enum ReproducibilityStatus {
    ExactMatch      { validator_count: u8 },
    DirectionalMatch { validator_count: u8, variance_explanation: String },
    PartialMatch    { successful_aspects: Vec<String>, failed_aspects: Vec<String> },
    Failed          { failure_reasons: Vec<String>, validator_count: u8 },
    Inconclusive    { reasons: Vec<String> },
    PersistentlyIndeterminate {
        time_elapsed_secs:    u64,
        validator_count:      u8,
        disagreement_summary: String,
    },
}

/// Reproducibility badge. Cannot be reduced to a single gameable number.
#[hdk_entry_helper]
pub struct ReproducibilityBadge {
    pub harmony_record_ref: ExternalHash,
    pub badge_type:         BadgeType,
    pub level:              BadgeLevel,
    pub discipline:         Discipline,
}

pub enum BadgeType {
    ComputationalReproducible,
    PreRegisteredAndValidated  { adherence_score: f64 },
    OpenDataValidated,
    MultiLabValidated          { lab_count: u8 },
}

pub enum BadgeLevel {
    Bronze,  // ≥3 validators, ≥60% success
    Silver,  // ≥5 validators, ≥70%, pre-registered
    Gold,    // ≥7 validators, ≥80%, multi-institutional
}

/// Every governance decision is logged immutably.
#[hdk_entry_helper]
pub struct GovernanceDecision {
    pub decision_type: DecisionType,
    pub made_by:       GovernanceBody,
    pub rationale:     String,
    pub vote_tally:    Option<VoteTally>,
}

pub enum DecisionType {
    DeviationApproved   { protocol_ref: ExternalHash },
    DeviationDenied     { protocol_ref: ExternalHash, reason: String },
    StandardUpdated     { discipline: Discipline },
    ValidatorSanctioned { validator_id: ValidatorId, reason: String },
    PolicyChanged       { policy: String, old_value: String, new_value: String },
}

pub enum GovernanceBody {
    DeviationReviewBoard,
    DisciplinaryStandardsCommittee { discipline: Discipline },
    SteeringCommittee,
    CommunityVote,
}

pub struct VoteTally { pub for_votes: u32, pub against_votes: u32, pub abstentions: u32 }

/// Multi-dimensional reputation. No single gameable score.
/// Only system_coordinator_key may write — enforced by validate().
#[hdk_entry_helper]
pub struct ValidatorReputation {
    pub validator_id:                  ValidatorId,
    pub validation_score:              f64,
    pub preregistration_quality:       f64,
    pub deviation_handling:            f64,
    pub time_investment_consistency:   f64,
    pub peer_endorsements:             u32,
    pub expertise_areas:               Vec<(Discipline, ExpertiseLevel)>,
    pub total_validations:             u32,
    pub total_score:                   f64,
}

pub enum ExpertiseLevel { Novice, Competent, Expert, Authority }

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    HarmonyRecord(HarmonyRecord),
    ReproducibilityBadge(ReproducibilityBadge),
    GovernanceDecision(GovernanceDecision),
    ValidatorReputation(ValidatorReputation),
}
```

### Integrity Zome — Link Types

```rust
#[hdk_link_types]
pub enum LinkTypes {
    /// AgentPubKey → ValidatorReputation ActionHash
    ValidatorToReputation,
    /// ExternalHash (request_ref) anchor → HarmonyRecord ActionHash
    RequestToHarmonyRecord,
    /// GovernanceDecision ActionHash → affected target ActionHash
    DecisionToTarget,
    /// Path anchor → HarmonyRecord (for discipline-based queries)
    /// Path: "harmony.{discipline}.{year_month}"
    DisciplinePath,
    /// Path anchor → ReproducibilityBadge
    BadgePath,
}
```

### Integrity Zome — Validate Callback

```rust
#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- HarmonyRecord: all validators must have participated ---
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            entry_type: EntryTypes::HarmonyRecord(record), ..
        }) => {
            let s = &record.validation_summary;
            let count = s.successful_validations
                + s.partial_validations
                + s.failed_validations
                + s.inconclusive_validations;
            if count != s.total_validators {
                return Ok(ValidateCallbackResult::Invalid(
                    format!("HarmonyRecord: {} outcomes submitted but {} validators assigned",
                            count, s.total_validators)
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- HarmonyRecord is IMMUTABLE after publication ---
        FlatOp::RegisterUpdate(OpUpdate { original_action, .. })
            if is_harmony_record(&original_action) =>
        {
            Ok(ValidateCallbackResult::Invalid(
                "HarmonyRecord cannot be updated — the record is permanent".into()
            ))
        }

        // --- ValidatorReputation: only system_coordinator_key may write ---
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            entry_type: EntryTypes::ValidatorReputation(_), ..
        }) => {
            let props = DnaProperties::try_from_dna_properties()?;
            if op.action().author() != props.system_coordinator_key {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the system coordinator may write reputation scores".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        _ => Ok(ValidateCallbackResult::Valid),
    }
}
```

### Coordinator Zome — init() Capability Grants

```rust
#[hdk_extern]
pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
    // ALL read functions are unrestricted — this is the HTTP Gateway target.
    // Public readability is the point of this DNA.
    let mut read_fns = BTreeSet::new();
    for fn_name in &[
        "get_harmony_record",
        "get_harmony_records_by_discipline",
        "get_badge",
        "get_validator_reputation",
        "get_governance_decisions",
        "recv_remote_signal",
    ] {
        read_fns.insert((zome_info()?.name, (*fn_name).into()));
    }
    create_cap_grant(ZomeCallCapGrant {
        tag: "public-read".into(),
        access: CapAccess::Unrestricted,
        functions: GrantedFunctions::Listed(read_fns),
    })?;

    // Write functions (create_harmony_record, issue_badge, etc.) are
    // gated by the membrane credential. Not unrestricted.

    Ok(InitCallbackResult::Pass)
}
```

### Coordinator Zome — Functions

```rust
// Write functions (membrane-gated):
#[hdk_extern] pub fn create_harmony_record(r: HarmonyRecord)        -> ExternResult<ActionHash>
#[hdk_extern] pub fn issue_badge(b: ReproducibilityBadge)            -> ExternResult<ActionHash>
#[hdk_extern] pub fn record_governance_decision(d: GovernanceDecision) -> ExternResult<ActionHash>
#[hdk_extern] pub fn update_validator_reputation(r: ValidatorReputation) -> ExternResult<ActionHash>

// Read functions (unrestricted — HTTP Gateway targets):
#[hdk_extern] pub fn get_harmony_record(request_ref: ExternalHash)  -> ExternResult<Option<Record>>
#[hdk_extern] pub fn get_harmony_records_by_discipline(d: Discipline) -> ExternResult<Vec<Record>>
#[hdk_extern] pub fn get_badge(request_ref: ExternalHash)            -> ExternResult<Option<Record>>
#[hdk_extern] pub fn get_validator_reputation(id: AgentPubKey)       -> ExternResult<Option<Record>>
#[hdk_extern] pub fn get_governance_decisions(limit: u32)            -> ExternResult<Vec<Record>>

// Called by Attestation DNA post_commit (via call(OtherRole("governance"), ...)):
#[hdk_extern] pub fn check_and_create_harmony_record(request_ref: ExternalHash) -> ExternResult<()>
// Checks if all ValidationAttestation entries are present for request_ref.
// If yes: assembles and creates the HarmonyRecord, then issues badge if thresholds met.

#[hdk_extern] pub fn recv_remote_signal(signal: SerializedBytes) -> ExternResult<()>
```

### HTTP Gateway REST Endpoints (Governance DNA only)

```
GET  /api/v1/harmony/{request_ref}           → get_harmony_record
GET  /api/v1/harmony/discipline/{discipline} → get_harmony_records_by_discipline
GET  /api/v1/badges/{request_ref}            → get_badge
GET  /api/v1/validators/{agent_id}           → get_validator_reputation
GET  /api/v1/governance/decisions            → get_governance_decisions
GET  /api/v1/query/doi/{doi}                 → (route via path link on DOI anchor)
GET  /api/v1/query/osf/{osf_id}              → (route via path link on OSF anchor)
```

Only the Governance DNA is exposed via the HTTP Gateway. Private DNAs (Researcher Repository, Validator Workspace) are never reachable externally.

---

## Commit-Reveal Protocol Flow

```
1. Researcher calls submit_validation_request() in Attestation DNA
   → ValidationRequest entry written to shared DHT
   → DifficultyAssessment computed and written
   → Validators selected (assignment engine)
   → Each validator notified via remote signal (notification only)

2. Validator receives task
   → receive_task() writes ValidationTask to Validator Workspace DNA
   → Validator runs reproduction work locally

3. Validator seals commitment (COMMIT PHASE)
   → seal_private_attestation() writes ValidatorPrivateAttestation (private entry)
   → Entry invisible to all peers; exists only on validator's local source chain
   → post_commit fires: call(OtherRole("attestation"), "notify_commitment_sealed", task_ref)

4. Attestation DNA coordinator checks state (DHT-POLL — not signal-driven)
   → check_all_commitments_sealed(): queries get_agent_activity for each assigned validator
   → When ALL validators have a ValidatorPrivateAttestation action: reveal window opens
   → Phase marker entry written to Attestation DHT (validators can poll this)
   → Any validator that missed the remote signal detects the phase marker on reconnect

5. Validators reveal (REVEAL PHASE)
   → submit_attestation() writes ValidationAttestation to shared Attestation DHT
   → Entry is IMMUTABLE — validate() callback blocks all updates and deletes
   → post_commit fires: call(OtherRole("governance"), "check_and_create_harmony_record", ...)

6. Governance DNA creates Harmony Record
   → check_and_create_harmony_record() waits until all ValidationAttestations present
   → Assembles ValidationSummary, ValidatorSummary[], Disagreement[]
   → create_harmony_record() writes HarmonyRecord to public DHT
   → validate() verifies: successful + partial + failed + inconclusive == total_validators
   → issue_badge() evaluates thresholds and writes ReproducibilityBadge if met
   → update_validator_reputation() called by system_coordinator_key

7. External access
   → Journals/funders query Governance DNA via HTTP Gateway
   → GET /api/v1/harmony/{request_ref} returns Harmony Record
```

---

## Cross-DNA Call Map

| From | To | Mechanism | Auth |
|------|-----|-----------|------|
| Researcher UI → Researcher Repository DNA | Local WebSocket | `AppWebsocket.callZome` | Author grant |
| Researcher Repository DNA → Attestation DNA | Same hApp, same node | `call(OtherRole("attestation"), ...)` | Author grant |
| Validator Workspace DNA → Attestation DNA | Same hApp, same node | `call(OtherRole("attestation"), ...)` | Author grant (via post_commit) |
| Attestation DNA → Governance DNA | Same hApp, same node | `call(OtherRole("governance"), ...)` | Author grant (via post_commit) |
| Validator A Attestation → Validator B Attestation | Different nodes, SAME DNA network | `call_remote(pubkey, ...)` | Unrestricted cap grant |
| Journals/Funders → Governance DNA | External HTTP | HTTP Gateway REST | Open read |
| **BLOCKED:** Attestation DNA → Researcher Repository DNA | Different DNA networks | `call_remote` CANNOT cross networks | — |
| **BLOCKED:** Attestation DNA → Validator Workspace DNA | Different DNA networks | `call_remote` CANNOT cross networks | — |

---

## Path Index Design

All paths live in coordinator zomes (no effect on integrity zomes / DNA hash).

```
Attestation DNA paths:
  "requests.pending.{discipline}"     → ValidationRequest ActionHash[]
  "requests.in_progress.{discipline}" → ValidationRequest ActionHash[]
  "requests.complete.{discipline}"    → ValidationRequest ActionHash[]
  "institutions.{institution_id}"     → ValidationRequest ActionHash[]
  "attestations.{discipline}.{YYYY_MM}" → ValidationAttestation ActionHash[]

Governance DNA paths:
  "harmony.{discipline}.{YYYY_MM}"   → HarmonyRecord ActionHash[]
  "badges.{badge_type}"               → ReproducibilityBadge ActionHash[]
  "doi.{doi_prefix}"                  → HarmonyRecord ActionHash[]
  "osf.{project_id}"                  → HarmonyRecord ActionHash[]
```

**Phase 2+ sharding:** When institution or discipline paths accumulate thousands of links, use Holochain's built-in path sharding DSL: prefix with `<width>:<depth>#`. Example: `"2:1#cardiff_university"` distributes load across prefix nodes. Not needed at Phase 1 scale.

---

## Implementation Sequencing

### Step 1 — Scaffold the four DNAs
```bash
hc scaffold dna researcher_repository
hc scaffold dna validator_workspace
hc scaffold dna attestation
hc scaffold dna governance
```

### Step 2 — Shared types crate
Create `shared_types/` crate. Add as a dependency in each integrity zome's `Cargo.toml`. Do NOT put shared types in any DNA's integrity zome — changes to integrity zomes change the DNA hash, creating a new empty network.

### Step 3 — Implement in dependency order
1. DNA 1 (Researcher Repository) — no dependencies
2. DNA 2 (Validator Workspace) — no dependencies
3. DNA 4 (Governance) — no dependencies on other ValiChord DNAs
4. DNA 3 (Attestation) — depends on concepts from DNAs 1, 2, 4 but not their code

### Step 4 — Tryorama test priority order
1. Membrane proof acceptance/rejection for Attestation DNA
2. Commit-reveal round: validator seals private attestation → all sealed → reveal → HarmonyRecord
3. Phase transition driven by DHT polling (`check_all_commitments_sealed`), NOT signal delivery
4. Offline validator scenario: misses reveal signal, reconnects, learns phase from DHT
5. Immutability enforcement: attempt to update a ValidationAttestation → rejected
6. ValidatorReputation write by non-coordinator → rejected
7. HarmonyRecord count mismatch → rejected by validate()
8. Gaming detection: identical outcomes pattern flagged in coordinator

### Step 5 — HTTP Gateway configuration
Expose Governance DNA only. Configure `bootstrapUrl` and `signalUrl` in `kangaroo.config.ts`. Add always-on node(s) for Governance DNA availability.

---

## Key Engineering Constraints (do not lose these)

1. **Signals are fire-and-forget.** Phase transitions MUST be driven by DHT state polling. Signals are for UI notification only.

2. **`call_remote` cannot cross DNA networks.** All inter-validator coordination must happen within the Attestation DNA's shared network.

3. **Integrity zomes must stay small.** Every change (including dependency version bumps) creates a new DNA hash = new network. Keep integrity zomes to entry/link types and validate only.

4. **Collusion/gaming detection belongs in coordinator zomes.** The validate() callback must be deterministic — no historical queries, no statistical analysis, no time-dependent logic.

5. **AgentPubKey is 39 bytes, not 32.** Use the HDK's native `AgentPubKey` type — never `[u8; 32]` for agent identities.

6. **Holochain timestamps are self-reported.** Rate limiting via `must_get_agent_activity` with timestamp filters is useful but timestamps can be falsified by bad actors. Use as a soft guard, not a hard security boundary.

7. **Match arm ordering in validate().** Guarded arms (immutability checks for specific entry types) MUST come before unguarded arms. A misplaced unguarded arm silently swallows everything below it.

8. **SHA-256 for research file fingerprints; BLAKE2b is Holochain-internal.** Use the `sha2` crate (compiled to WASM) for ExternalHash computation. Do not use Holochain's `hash_entry()` for research file fingerprints — that produces BLAKE2b.

9. **Always list the coordinator zome's integrity dependency explicitly** in `dna.yaml`, even if there is only one. Known Holochain bug — implicit single dependency is unreliable.

10. **DNA properties are tamper-evident configuration.** The `authorized_joining_certificate_issuer` and `system_coordinator_key` baked into DNA properties cannot be changed without creating a new DNA hash (new network). This is the feature, not a limitation.
