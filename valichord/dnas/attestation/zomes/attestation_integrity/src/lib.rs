use hdi::prelude::*;
use valichord_shared_types::{CertificationTier, Discipline, ValidationAttestation, ValidationPhase};

// ---------------------------------------------------------------------------
// DNA Properties (baked into DNA hash — immutable per network instance)
// ---------------------------------------------------------------------------
//
// #[dna_properties] auto-derives: Serialize, Deserialize, SerializedBytes, Debug.
// Do NOT add those in a separate #[derive] — they would conflict.

#[dna_properties]
pub struct DnaProperties {
    /// Stored as a base58 HoloHash string in happ.yaml modifiers.
    /// The conductor passes YAML values as msgpack strings, so AgentPubKey
    /// (which expects binary bytes) cannot be used here directly.
    pub authorized_joining_certificate_issuer: String,
    pub discipline: String,
    pub minimum_validators: u32,
}

// ---------------------------------------------------------------------------
// Entry Types
// ---------------------------------------------------------------------------
//
// #[hdk_entry_helper] auto-derives: Serialize, Deserialize, SerializedBytes, Debug.
// Only add extra derives that the macro does NOT provide (e.g. Clone).

/// A request to validate a study.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidationRequest {
    pub protocol_ref:            Option<ExternalHash>,
    pub data_hash:               ExternalHash,
    /// URL where validators can download the dataset (OSF, Zenodo, institutional repo, etc.).
    pub data_access_url:         String,
    /// DOI or URL of the pre-registered analysis plan (OSF, AsPredicted, ClinicalTrials, etc.).
    pub protocol_access_url:     Option<String>,
    pub num_validators_required: u8,
    pub validation_tier:         ValidationTier,
    pub discipline:              Discipline,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ValidationTier { Basic, Enhanced, Comprehensive }

// ValidationAttestation, OutcomeSummary, MetricResult, AgreementLevel are
// defined in valichord_shared_types — imported above.
// This avoids cdylib→cdylib dependency issues with validator_workspace and governance.

#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidatorProfile {
    pub institution:          String,
    pub disciplines:          Vec<Discipline>,
    pub certification_tier:   CertificationTier,
    pub available:            bool,
    pub max_concurrent_tasks: u8,
    pub orcid:                Option<String>,
}

// CertificationTier is defined in valichord_shared_types — imported above.

#[hdk_entry_helper]
#[derive(Clone)]
pub struct DifficultyAssessment {
    pub request_ref:            ExternalHash,
    pub code_volume:            u8,
    pub dependency_count:       u8,
    pub documentation_quality:  u8,
    pub data_accessibility:     u8,
    pub environment_complexity: u8,
    pub study_age_years:        u8,
    pub predicted_tier:         DifficultyTier,
    pub predicted_min_secs:     u64,
    pub predicted_max_secs:     u64,
    pub confidence:             AssessmentConfidence,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum DifficultyTier {
    Standard, Moderate, Complex, Extreme, Excluded,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AssessmentConfidence { High, Medium, Low }

/// Public commitment anchor — proof a validator sealed their private attestation.
/// IMMUTABLE after publication.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct CommitmentAnchor {
    pub request_ref: ExternalHash,
    pub validator:   AgentPubKey,
}

/// DHT-persisted record of the current validation phase.
/// IMMUTABLE — phase history is append-only.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct PhaseMarker {
    pub request_ref: ExternalHash,
    pub phase:       ValidationPhase,
}

// ---------------------------------------------------------------------------
// Entry Types Enum
// ---------------------------------------------------------------------------
//
// required_validations=7 goes on the ENUM VARIANT here, not on the struct.

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    ValidationRequest(ValidationRequest),
    #[entry_type(required_validations = 7)]
    ValidationAttestation(ValidationAttestation),
    ValidatorProfile(ValidatorProfile),
    DifficultyAssessment(DifficultyAssessment),
    CommitmentAnchor(CommitmentAnchor),
    PhaseMarker(PhaseMarker),
}

// ---------------------------------------------------------------------------
// Link Types
// ---------------------------------------------------------------------------

#[hdk_link_types]
pub enum LinkTypes {
    StudyToValidation,
    ValidatorToAttestation,
    AgentToProfile,
    StatusPath,
    InstitutionPath,
    DisciplinePath,
    RequestToCommitment,
    RequestToPhaseMarker,
    /// Indexes ValidatorProfile entries under "validators.{discipline_tag}" paths.
    ValidatorTierPath,
    /// Links request_ref (ExternalHash) → DifficultyAssessment ActionHash.
    /// Allows get_difficulty_assessment to retrieve the most recent assessment
    /// for a given request without scanning the source chain.
    DifficultyPath,
}

// ---------------------------------------------------------------------------
// Validate Callback — HDI 0.7
// ---------------------------------------------------------------------------
//
// CRITICAL HDI 0.7 API FACTS:
// - op.flattened() consumes `op` — never call op.action() after flattened().
// - OpUpdate<ET> is an ENUM: OpUpdate::Entry { app_entry: ET, action: Update }
//   app_entry is the NEW entry. The new type MUST match the original type
//   (Holochain enforces this), so checking app_entry type is sufficient.
// - OpDelete is a STRUCT: OpDelete { action: Delete }
//   Use must_get_action(action.deletes_address) to check original type.
// - Membrane proof is in OpActivity::AgentValidationPkg { membrane_proof, .. }

#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- Update immutability guards (checked before generic update arm) ---

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ValidationAttestation(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidationAttestation is immutable — the public record cannot be changed".into(),
        )),

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::CommitmentAnchor(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "CommitmentAnchor is immutable — commitments cannot be retracted".into(),
        )),

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::PhaseMarker(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "PhaseMarker is immutable — phase history is append-only".into(),
        )),

        // Generic update: only the original author may update other entry types.
        FlatOp::RegisterUpdate(OpUpdate::Entry { action, .. }) => {
            let original = must_get_action(action.original_action_address.clone())?;
            if action.author != *original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // Reject private entry updates (no private entries in this DNA).
        FlatOp::RegisterUpdate(OpUpdate::PrivateEntry { .. }) => Ok(
            ValidateCallbackResult::Invalid(
                "This DNA has no private entries".into(),
            ),
        ),

        // Other update variants: accept.
        FlatOp::RegisterUpdate(_) => Ok(ValidateCallbackResult::Valid),

        // --- Delete: look up original to check entry type ---
        FlatOp::RegisterDelete(OpDelete { action }) => {
            let original_action = must_get_action(action.deletes_address.clone())?;
            // If original is an app entry, check immutability via deserialization.
            if let Some(EntryType::App(app_def)) = original_action.action().entry_type() {
                let original_record =
                    must_get_valid_record(action.deletes_address.clone())?;
                if let Some(entry) = original_record.entry().as_option() {
                    let entry_type = EntryTypes::deserialize_from_type(
                        app_def.zome_index,
                        app_def.entry_index,
                        entry,
                    )?;
                    match entry_type {
                        Some(EntryTypes::ValidationAttestation(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "ValidationAttestation is immutable — cannot be deleted".into(),
                            ));
                        }
                        Some(EntryTypes::CommitmentAnchor(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "CommitmentAnchor is immutable — cannot be deleted".into(),
                            ));
                        }
                        Some(EntryTypes::PhaseMarker(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "PhaseMarker is immutable — cannot be deleted".into(),
                            ));
                        }
                        _ => {}
                    }
                }
            }
            // Author check for non-immutable entries.
            if action.author != *original_action.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- Membrane proof — full credential check (after network join) ---
        FlatOp::RegisterAgentActivity(OpActivity::AgentValidationPkg {
            membrane_proof, ..
        }) => validate_membrane_proof(membrane_proof),

        // All other ops: valid.
        _ => Ok(ValidateCallbackResult::Valid),
    }
}

fn validate_membrane_proof(
    membrane_proof: Option<MembraneProof>,
) -> ExternResult<ValidateCallbackResult> {
    let proof = match membrane_proof {
        None => {
            return Ok(ValidateCallbackResult::Invalid(
                "Attestation DNA requires a membrane proof (institutional credential)".into(),
            ))
        }
        Some(p) => p,
    };
    if proof.bytes().len() < 64 {
        return Ok(ValidateCallbackResult::Invalid(
            "Membrane proof is too short to be a valid credential signature".into(),
        ));
    }
    // TODO: verify signature over joining agent's key using
    // DnaProperties::try_from_dna_properties()?.authorized_joining_certificate_issuer
    Ok(ValidateCallbackResult::Valid)
}

// ---------------------------------------------------------------------------
// genesis_self_check — format-only, runs BEFORE network join
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn genesis_self_check(
    data: GenesisSelfCheckData,
) -> ExternResult<ValidateCallbackResult> {
    match data.membrane_proof {
        None => Ok(ValidateCallbackResult::Invalid(
            "Attestation DNA requires a membrane proof".into(),
        )),
        Some(ref proof) if proof.bytes().len() < 64 => Ok(ValidateCallbackResult::Invalid(
            "Membrane proof is too short".into(),
        )),
        _ => Ok(ValidateCallbackResult::Valid),
    }
}
