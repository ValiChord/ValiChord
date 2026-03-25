use hdi::prelude::*;
use valichord_shared_types::{CertificationTier, Discipline, MetricResult, ValidationAttestation, ValidationPhase};

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
    /// Minimum seconds that must elapse since a StudyClaim was created before
    /// reclaim_abandoned_claim may free that slot.
    /// 0 = no minimum (dev/test bypass — same pattern as empty issuer key).
    #[serde(default)]
    pub min_claim_timeout_secs: u64,
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

/// Discriminates between human validators, institutional accounts, and
/// automated tools.  Stored as `Option` so profiles created before this
/// field was introduced deserialise as `None` (backwards-compatible).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ValidatorAgentType {
    /// A human individual acting under their own identity.
    Individual,
    /// An institutional or group account (e.g. a lab or review committee).
    Institution,
    /// An automated tool or pipeline (e.g. a CI-based reproducer).
    AutomatedTool,
}

#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidatorProfile {
    pub institution:          String,
    pub disciplines:          Vec<Discipline>,
    pub certification_tier:   CertificationTier,
    pub available:            bool,
    pub max_concurrent_tasks: u8,
    pub orcid:                Option<String>,
    /// Agent type — `None` for profiles created before this field was added.
    #[serde(default)]
    pub agent_type:           Option<ValidatorAgentType>,
    /// Stable person identity across devices — `None` until a cross-device
    /// identity system (e.g. Flowsta, Deepkey) links this device key to a
    /// canonical person key.  When set, profile lookup and deduplication
    /// should use this key rather than the author `AgentPubKey`.
    ///
    /// `#[serde(default)]` ensures records written before this field was added
    /// deserialise as `None` without error (backwards-compatible).
    #[serde(default)]
    pub person_key:           Option<AgentPubKey>,
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
    pub request_ref:             ExternalHash,
    pub validator:               AgentPubKey,
    /// SHA-256 of (msgpack(ValidationAttestation) || nonce). Verified on reveal.
    pub commitment_hash:         Vec<u8>,
    /// ActionHash of the ValidationRequest this commitment is for.
    /// Inductive validation chain: CommitmentAnchor → ValidationRequest.
    pub validation_request_hash: ActionHash,
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
///
/// **Membrane boundary — do NOT add fields here.**
/// This struct crosses from the private Validator Workspace DNA to the shared
/// Attestation DHT via a cross-DNA call in post_commit.  Any field added to
/// this struct is automatically transmitted to the shared network.  The only
/// safe fields are public identifiers (request_ref) and opaque hashes
/// (commitment_hash).  Never add assessment content, scores, or any data
/// derived from the private `ValidatorPrivateAttestation`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitmentSealedInput {
    pub request_ref:     ExternalHash,
    pub commitment_hash: Vec<u8>,
}

/// Payload sent from researcher_repository `lock_result` to attestation
/// `publish_researcher_commitment`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearcherCommitmentInput {
    pub request_ref:            ExternalHash,
    pub result_commitment_hash: Vec<u8>,
}

/// Payload for `reveal_researcher_result`.
///
/// The coordinator verifies `SHA-256(msgpack(metrics) || nonce) == result_commitment_hash`
/// before writing the `ResearcherReveal` entry to the DHT.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearcherRevealInput {
    pub request_ref: ExternalHash,
    pub metrics:     Vec<MetricResult>,
    pub nonce:       Vec<u8>,
}

/// Researcher's verified reveal — the structured metrics that were hashed into
/// `ResearcherResultCommitment.result_commitment_hash`, now published on the
/// shared DHT after all validators have committed.
///
/// Only accepted by the coordinator once `check_all_commitments_sealed` returns
/// true and the SHA-256 hash of `msgpack(metrics) || nonce` matches the
/// previously published commitment.
/// IMMUTABLE after publication.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ResearcherReveal {
    pub request_ref: ExternalHash,
    /// The structured per-metric results the researcher produced originally.
    /// Validators can compare their own `produced_value` fields against these.
    pub metrics:     Vec<MetricResult>,
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
// AgentIdentityAttestation — native multi-device identity linking
// ---------------------------------------------------------------------------
//
// Two agents (devices) jointly assert they share a single logical identity.
// Both agents sign a canonical 78-byte payload: the two AgentPubKey raw bytes
// (39 bytes each) concatenated in lexicographic order.  Storing both
// signatures in a single DHT entry means any third party can verify the
// claim without trusting either agent individually.
//
// Naming convention: agent_a is the lexicographically smaller key; agent_b
// is the larger.  The coordinator's `sorted_agent_pair_bytes()` enforces this.
//
// Either agent may revoke the link by deleting the entry.  The coordinator
// validates authorship at the call level; the integrity zome allows deletion
// by either of the two named agents.

#[hdk_entry_helper]
#[derive(Clone)]
pub struct AgentIdentityAttestation {
    /// Lexicographically smaller AgentPubKey (raw 39 bytes).
    pub agent_a:     AgentPubKey,
    /// agent_a's Ed25519 signature over the sorted 78-byte payload.
    pub signature_a: Signature,
    /// Lexicographically larger AgentPubKey (raw 39 bytes).
    pub agent_b:     AgentPubKey,
    /// agent_b's Ed25519 signature over the same sorted 78-byte payload.
    pub signature_b: Signature,
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
    ResearcherReveal(ResearcherReveal),
    AgentIdentityAttestation(AgentIdentityAttestation),
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
    /// Links path("researcher_reveal.{request_ref}") → ResearcherReveal ActionHash.
    RequestToResearcherReveal,
    /// Links AgentPubKey → AgentIdentityAttestation ActionHash.
    /// Written from BOTH agents' pubkeys for symmetric lookup.
    AgentToIdentityAttestation,
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

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ResearcherReveal(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ResearcherReveal is immutable — the verified reveal cannot be changed".into(),
        )),

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::AgentIdentityAttestation(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "AgentIdentityAttestation is immutable — use delete to revoke".into(),
        )),

        // ValidationRequest is immutable after submission — researchers cannot
        // silently lower num_validators_required to bypass the quorum gate.
        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ValidationRequest(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidationRequest is immutable — the study submission cannot be altered".into(),
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
            // must_get_valid_record returns both action and entry — no need for a
            // separate must_get_action call.
            let original_record = must_get_valid_record(action.deletes_address.clone())?;
            if let Some(EntryType::App(app_def)) = original_record.action().entry_type() {
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
                        Some(EntryTypes::ResearcherReveal(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "ResearcherReveal is immutable — cannot be deleted".into(),
                            ));
                        }
                        Some(EntryTypes::ValidationRequest(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "ValidationRequest is immutable — cannot be deleted".into(),
                            ));
                        }
                        // AgentIdentityAttestation: either named agent may revoke.
                        // The normal "only author may delete" check below is bypassed
                        // because both agent_a and agent_b are equally authorised —
                        // but some third-party impostor must not be able to delete.
                        Some(EntryTypes::AgentIdentityAttestation(ref att)) => {
                            if action.author == att.agent_a
                                || action.author == att.agent_b
                            {
                                return Ok(ValidateCallbackResult::Valid);
                            }
                            return Ok(ValidateCallbackResult::Invalid(
                                "Only one of the two named agents may revoke \
                                 an AgentIdentityAttestation".into(),
                            ));
                        }
                        _ => {}
                    }
                }
            }
            // Author check for non-immutable entries.
            if action.author != *original_record.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ValidationRequest create: enforce minimum validator quorum ------
        //
        // The DNA property `minimum_validators` is the network-wide lower bound
        // baked into the DNA hash.  A researcher cannot submit a request with a
        // lower quorum than the network allows — doing so would let a single
        // (potentially colluding) validator satisfy the commitment gate and
        // open the reveal window unilaterally.
        //
        // If minimum_validators is 0 (dev/test bypass, same pattern as the
        // empty issuer), the check is skipped.
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidationRequest(ref vr), ..
        }) => {
            let props = DnaProperties::try_from_dna_properties()?;
            if props.minimum_validators > 0
                && (vr.num_validators_required as u32) < props.minimum_validators
            {
                return Ok(ValidateCallbackResult::Invalid(format!(
                    "num_validators_required ({}) is below the DNA minimum ({}) — \
                     increase the quorum or reconfigure the network",
                    vr.num_validators_required, props.minimum_validators,
                )));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- StudyClaim create: conflict-of-interest check ------------------
        //
        // Fetch the ValidationRequest via the embedded ActionHash and compare
        // institutions.
        //
        // Validators must always declare their institutional affiliation —
        // an undeclared validator institution cannot be checked for conflicts
        // and is therefore rejected outright.
        //
        // Empty researcher_institution is permitted (independent researchers
        // have no institutional affiliation to conflict with).
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
            // Cross-check: claim.request_ref must equal the ValidationRequest's
            // data_hash.  Prevents a claim referencing a benign ValidationRequest
            // for COI-check purposes while actually targeting a different study.
            if req.data_hash != claim.request_ref {
                return Ok(ValidateCallbackResult::Invalid(
                    "StudyClaim.request_ref does not match \
                     ValidationRequest.data_hash — the claim is for a different study".into(),
                ));
            }
            if claim.validator_institution.trim().is_empty() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Validators must declare an institutional affiliation \
                     before claiming a study".into(),
                ));
            }
            if !req.researcher_institution.is_empty()
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

        // --- CommitmentAnchor create: verify it links to a real ValidationRequest ---
        //
        // Inductive validation chain: CommitmentAnchor → ValidationRequest.
        // `validator` must equal the action author (no impersonation).
        // `request_ref` must equal the ValidationRequest's `data_hash`.
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::CommitmentAnchor(ref anchor),
            action,
        }) => {
            let req_record = must_get_valid_record(anchor.validation_request_hash.clone())?;
            let req: ValidationRequest = req_record
                .entry()
                .to_app_option()
                .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
                .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                    "CommitmentAnchor.validation_request_hash does not point to \
                     a ValidationRequest".into(),
                )))?;
            if req.data_hash != anchor.request_ref {
                return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.request_ref does not match \
                     ValidationRequest.data_hash".into(),
                ));
            }
            if anchor.validator != action.author {
                return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.validator must equal the author of \
                     the create action".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ValidationAttestation create: verify it links to a CommitmentAnchor ---
        //
        // Inductive validation chain: ValidationAttestation → CommitmentAnchor.
        // Checked only when commitment_anchor_hash is Some (always set by the
        // coordinator on new entries; None only for entries predating this field).
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidationAttestation(ref att),
            action,
        }) => {
            if let Some(ref anchor_hash) = att.commitment_anchor_hash {
                let anchor_record = must_get_valid_record(anchor_hash.clone())?;
                let anchor: CommitmentAnchor = anchor_record
                    .entry()
                    .to_app_option()
                    .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
                    .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                        "ValidationAttestation.commitment_anchor_hash does not point \
                         to a CommitmentAnchor".into(),
                    )))?;
                if anchor.validator != action.author {
                    return Ok(ValidateCallbackResult::Invalid(
                        "CommitmentAnchor.validator does not match the \
                         attestation author".into(),
                    ));
                }
                if anchor.request_ref != att.request_ref {
                    return Ok(ValidateCallbackResult::Invalid(
                        "CommitmentAnchor.request_ref does not match \
                         ValidationAttestation.request_ref".into(),
                    ));
                }
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- AgentIdentityAttestation create: reject self-links ---------------
        //
        // Canonical ordering (agent_a < agent_b) is enforced by the coordinator
        // before the entry is committed.  Full signature verification also runs
        // in the coordinator (verify_signature is HDK-only, unavailable here).
        // The integrity zome enforces the one rule it can: a key cannot attest
        // to itself.
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::AgentIdentityAttestation(ref att), ..
        }) => {
            if att.agent_a == att.agent_b {
                return Ok(ValidateCallbackResult::Invalid(
                    "AgentIdentityAttestation requires two distinct agents".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- Commitment links are immutable — block deletions ----------------
        //
        // A validator who deletes their own RequestToCommitment link can
        // re-open the commitment phase gate and block reveal_researcher_result
        // indefinitely.  Commitment links must be as permanent as the
        // CommitmentAnchor entry itself.
        FlatOp::RegisterDeleteLink {
            link_type: LinkTypes::RequestToCommitment,
            ..
        } => Ok(ValidateCallbackResult::Invalid(
            "RequestToCommitment links are immutable — \
             validator commitments cannot be retracted".into(),
        )),

        // --- Membrane proof — format check (after network join) ---
        //
        // The integrity zome can only run the format check here because
        // `verify_signature` is an HDK host function not exposed by HDI.
        // The full Ed25519 signature verification against the DNA-properties
        // issuer key runs in the coordinator's `init()` callback, which fails
        // the cell if the proof is invalid and prevents any subsequent writes.
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
    // Architecture note: this callback can only perform format validation.
    // `verify_signature` is an HDK host function that is NOT available in
    // HDI integrity zomes. The full Ed25519 credential check (issuer key from
    // DNA properties, signature over the joining agent's pubkey) is implemented
    // in `verify_membrane_proof()` in the coordinator's `init()` callback.
    // If that check fails, `init()` returns `InitCallbackResult::Fail`, the
    // cell cannot be used to write any protocol data, and the agent is
    // effectively a read-only observer on the DHT.
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
            "Membrane proof is too short to contain a 64-byte Ed25519 signature".into(),
        ));
    }
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
