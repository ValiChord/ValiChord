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
    /// Researcher's institution — used for conflict-of-interest checks when
    /// validators claim the study.  Empty string = COI check bypassed.
    pub researcher_institution:  String,
}

/// A validator's self-assignment to a validation study.
///
/// Written by the validator when they claim a study from the pending queue.
/// The coordinator enforces capacity limits and duplicate prevention.
/// validate() enforces the conflict-of-interest rule: validator and researcher
/// must not be from the same institution.
///
/// Links written alongside this entry:
///   RequestToClaim:  request_ref  → StudyClaim ActionHash
///   ValidatorToClaim: AgentPubKey → StudyClaim ActionHash
#[hdk_entry_helper]
#[derive(Clone)]
pub struct StudyClaim {
    pub request_ref:             ExternalHash,
    /// ActionHash of the ValidationRequest — used by validate() to fetch
    /// researcher_institution for the COI check without a link traversal.
    pub validation_request_hash: ActionHash,
    /// Validator's institution at claim time (copied from their ValidatorProfile
    /// by the coordinator).  Empty string = COI check bypassed.
    pub validator_institution:   String,
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
///
/// `commitment_hash` = SHA-256(msgpack(ValidationAttestation) || nonce)
/// computed in the validator's local Workspace DNA before any content leaves
/// their device. The hash is the ONLY piece of their assessment that ever
/// touches the shared DHT during the commit phase.
/// IMMUTABLE after publication.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct CommitmentAnchor {
    pub request_ref:     ExternalHash,
    pub validator:       AgentPubKey,
    /// SHA-256 of (msgpack(ValidationAttestation) || nonce). Verified on reveal.
    pub commitment_hash: Vec<u8>,
}

/// Cryptographic commitment to the researcher's result.
///
/// Published to the shared Attestation DHT at the same time as the
/// ValidationRequest — before any validator begins work.  The actual result
/// stays in the researcher's local Researcher Repository DNA (private entry).
/// Only revealed (and verified against this hash) after all validators have
/// submitted their reveals.
/// IMMUTABLE after publication.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ResearcherResultCommitment {
    pub request_ref:           ExternalHash,
    /// SHA-256 of (result_data.as_bytes() || nonce). Verified on researcher reveal.
    pub result_commitment_hash: Vec<u8>,
}

// ---------------------------------------------------------------------------
// Cross-DNA input structs (defined here so coordinator zomes on both sides
// can import the same type without a coordinator→coordinator dependency).
// ---------------------------------------------------------------------------

/// Payload sent from validator_workspace post_commit to attestation
/// `notify_commitment_sealed`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitmentSealedInput {
    pub request_ref:     ExternalHash,
    pub commitment_hash: Vec<u8>,
}

/// Payload sent from researcher_repository `lock_result` to attestation
/// `publish_researcher_commitment`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearcherCommitmentInput {
    pub request_ref:           ExternalHash,
    pub result_commitment_hash: Vec<u8>,
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
    StudyClaim(StudyClaim),
    ResearcherResultCommitment(ResearcherResultCommitment),
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
    DifficultyPath,
    /// Links request_ref (ExternalHash) → StudyClaim ActionHash.
    /// Base: the study's data_hash (ExternalHash used as DHT address).
    /// Allows get_claims_for_request to enumerate all validators who claimed a study.
    RequestToClaim,
    /// Links AgentPubKey → StudyClaim ActionHash.
    /// Allows get_my_claimed_studies to enumerate a validator's active claims.
    ValidatorToClaim,
    /// Links path("researcher_commitment.{request_ref}") → ResearcherResultCommitment ActionHash.
    RequestToResearcherCommitment,
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

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ResearcherResultCommitment(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ResearcherResultCommitment is immutable — the locked result commitment cannot be changed".into(),
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
                        Some(EntryTypes::ResearcherResultCommitment(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "ResearcherResultCommitment is immutable — cannot be deleted".into(),
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

        // --- StudyClaim create: conflict-of-interest check ------------------
        //
        // Fetch the ValidationRequest via the embedded ActionHash and compare
        // institutions.  Empty institution on either side bypasses the check
        // (dev mode / researcher didn't declare institution).
        //
        // Capacity and duplicate checks live in the coordinator — they require
        // link counting, which is not available in validate().
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::StudyClaim(ref claim), ..
        }) => {
            let req_record =
                must_get_valid_record(claim.validation_request_hash.clone())?;
            let req: ValidationRequest = req_record
                .entry()
                .to_app_option()
                .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
                .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                    "StudyClaim.validation_request_hash does not point to a ValidationRequest"
                        .into(),
                )))?;
            if !claim.validator_institution.is_empty()
                && !req.researcher_institution.is_empty()
                && claim.validator_institution == req.researcher_institution
            {
                return Ok(ValidateCallbackResult::Invalid(format!(
                    "Conflict of interest: validator institution '{}' matches \
                     researcher institution — claim rejected",
                    claim.validator_institution,
                )));
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
