use hdi::prelude::*;
use valichord_shared_types::{
    CertificationTier, Discipline, JoiningCertificate, MetricResult, ValidationAttestation,
    ValidationPhase, ValidatorType,
};

// ---------------------------------------------------------------------------
// DNA Properties (baked into DNA hash — immutable per network instance)
// ---------------------------------------------------------------------------
//
// #[dna_properties] auto-derives: Serialize, Deserialize, SerializedBytes, Debug.
// Do NOT add those in a separate #[derive] — they would conflict.

#[dna_properties]
pub struct DnaProperties {
    /// Base64url-encoded `AgentPubKey` of the institutional credential issuer
    /// (`uhCAk...` format — standard Holochain hash string representation).
    /// Stored as `String` because the conductor passes YAML modifiers as msgpack
    /// strings; `AgentPubKey` (which expects 39 binary bytes) cannot be used here.
    /// **Encoding contract:** the coordinator's `verify_membrane_proof` decodes this
    /// with `.parse::<HoloHashB64<hash_type::Agent>>()`.  Any change
    /// to the issuer key requires coordinated updates to: (1) `happ.yaml` modifiers,
    /// (2) the membrane-proof issuer in all test fixtures, and (3) any production
    /// onboarding tooling that signs joining credentials.
    /// Empty string = dev/test bypass (membrane proof not verified).
    pub authorized_joining_certificate_issuer: String,
    /// Base64url-encoded `AgentPubKey` of the operator who signs AI-validator
    /// joining certificates.  AI validators don't have institutional affiliations,
    /// so the ValiChord operator vouches for them directly.
    /// Empty string = use `authorized_joining_certificate_issuer` for AI certs too
    /// (single-key mode), or bypass entirely when that field is also empty.
    #[serde(default)]
    pub ai_validator_issuer: String,
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
    /// URL where validators can download the deposit.
    ///
    /// For `PublicUrl`: a direct public link (Zenodo, OSF, institutional repo, etc.).
    /// For `TokenGated`: the researcher's private deposit endpoint —
    ///   validators append `?token={deposit_token}` to authenticate.
    pub data_access_url:         String,
    /// How validators should access the deposit.
    /// Defaults to `PublicUrl` — existing entries without this field deserialise correctly.
    #[serde(default)]
    pub deposit_access_type:     DepositAccessType,
    /// One-time access token for `TokenGated` deposits.
    /// `None` when `deposit_access_type` is `PublicUrl`.
    /// Protected by the Attestation DHT membrane — only credentialed validators can read it.
    #[serde(default)]
    pub deposit_token:           Option<String>,
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

/// Soft-delete marker for a StudyClaim.
///
/// Claims and their `RequestToClaim` / `ValidatorToClaim` links are immutable
/// (prevents validators from self-retracting to game capacity or collude).
/// `StudyClaimRelease` records that a claim was intentionally vacated —
/// either by the validator themselves via `release_claim`, or by a third party
/// via `reclaim_abandoned_claim` after the claim timeout has elapsed.
///
/// Query functions (`get_claims_for_request`, `get_my_claimed_studies`) and the
/// `claim_study` capacity check filter out claims that have a `ClaimToRelease`
/// link pointing to a `StudyClaimRelease` entry.
#[hdk_entry_helper]
#[derive(Clone, PartialEq)]
pub struct StudyClaimRelease {
    pub claim_hash: ActionHash,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ValidationTier { Basic, Enhanced, Comprehensive }

/// How validators should access the deposit for this study.
///
/// Stored in `ValidationRequest` on the shared Attestation DHT.
/// The DHT is membrane-gated (credentialed validators only), so a
/// `deposit_token` value here is protected by the joining rules —
/// only agents who hold a valid membrane proof can read it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub enum DepositAccessType {
    /// `data_access_url` is publicly reachable — no credential required.
    /// Suitable for deposits already published on Zenodo, OSF, institutional repos, etc.
    #[default]
    PublicUrl,
    /// `data_access_url` is a private endpoint.
    /// Validators authenticate by appending `?token={deposit_token}` to the URL.
    /// Appropriate when the researcher's institution hosts the deposit internally
    /// and the researcher's node is always-on.
    TokenGated,
}

// ValidationAttestation, OutcomeSummary, MetricResult, AgreementLevel are
// defined in valichord_shared_types — imported above.
// This avoids cdylib→cdylib dependency issues with validator_workspace and governance.

/// Re-exported from `valichord_shared_types` — moved there so governance_integrity
/// can embed ValidatorAgentType in HarmonyRecord without a cdylib→cdylib dependency.
pub use valichord_shared_types::ValidatorAgentType;

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
    /// The author's joining certificate (their membrane proof), carried so every
    /// peer can check `certification_tier` against what the issuer granted (#8).
    ///
    /// WHY (2026-10-17). Until then `certification_tier` was whatever the caller
    /// wrote — `publish_validator_profile` takes the whole profile — and no
    /// validate() rule covered profiles at all, so any validator could call
    /// themselves Certified. And the tier an issuer granted an AI validator in its
    /// certificate was never read anywhere. The coordinator fills this field from
    /// the author's own AgentValidationPkg; callers need not supply it. Not secret:
    /// it is a signature over the agent's own key, already on their public chain.
    ///
    /// `None` only on a dev network (empty issuer key), where the credential
    /// system is off and the tier is not checked — the same bypass as everywhere.
    #[serde(default)]
    pub joining_certificate:  Option<MembraneProof>,
}

/// Check a ValidatorProfile's tier against its author's joining certificate (#8).
/// `Some(reason)` if invalid. Used for creates AND updates — an update arm that
/// skipped it would let the tier be forged by editing instead.
fn check_profile_certification(
    author: &AgentPubKey,
    profile: &ValidatorProfile,
) -> ExternResult<Option<String>> {
    let props = DnaProperties::try_from_dna_properties()?;
    if props.authorized_joining_certificate_issuer.is_empty() {
        return Ok(None); // dev bypass — credential system off
    }
    // Is it a genuine certificate, issued to THIS author? Same function every peer
    // runs on the AgentValidationPkg (#37), so a certificate copied from another
    // agent fails here exactly as it would at the membrane.
    if let Err(reason) = check_joining_certificate(author, profile.joining_certificate.as_ref())? {
        return Ok(Some(format!("ValidatorProfile joining_certificate: {reason}")));
    }
    let granted = match profile.joining_certificate.as_ref() {
        Some(proof) => match JoiningCertificate::from_proof_bytes(proof.bytes()) {
            Ok(c) => c.granted_tier(),
            Err(e) => return Ok(Some(format!("ValidatorProfile joining_certificate: {e}"))),
        },
        None => return Ok(Some("ValidatorProfile requires a joining_certificate".into())),
    };
    if profile.certification_tier != granted {
        return Ok(Some(format!(
            "ValidatorProfile certification_tier must be the tier its joining certificate \
             grants ({granted:?}), not {:?}",
            profile.certification_tier,
        )));
    }
    Ok(None)
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
/// Re-exported from `valichord_shared_types` so downstream code that already
/// imports from `attestation_integrity` continues to compile unchanged.
pub use valichord_shared_types::{CommitmentSealedInput, ResearcherCommitmentInput};

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
    pub request_ref:           ExternalHash,
    pub phase:                 ValidationPhase,
    /// ActionHash of the CommitmentAnchor written by the validator who detected quorum.
    /// Inductive validation chain: PhaseMarker → CommitmentAnchor → ValidationRequest.
    /// Prevents any agent from forging a RevealOpen signal without having committed.
    pub commitment_anchor_hash: ActionHash,
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
// is the larger.  `sorted_agent_pair_bytes()` (below) builds the payload; both
// the coordinator and validate() use it.
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

/// The canonical 78-byte payload both agents sign for an AgentIdentityAttestation:
/// the two raw 39-byte pubkeys concatenated in lexicographic order, so it is the
/// same whichever agent calls first.
///
/// Passed to `verify_signature` as a `Vec<u8>`, which msgpack-encodes it — the same
/// encoding `sign()` used. Do not switch either side to the `_raw` variants alone.
pub fn sorted_agent_pair_bytes(a: &AgentPubKey, b: &AgentPubKey) -> Vec<u8> {
    let raw_a = a.get_raw_39();
    let raw_b = b.get_raw_39();
    if raw_a <= raw_b {
        [raw_a, raw_b].concat()
    } else {
        [raw_b, raw_a].concat()
    }
}

// ---------------------------------------------------------------------------
// Entry Types Enum
// ---------------------------------------------------------------------------
//
// required_validations=7 goes on the ENUM VARIANT here, not on the struct.

#[derive(Serialize, Deserialize)]
#[serde(tag = "type")]
#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    // cache_at_agent_activity=true: stores the entry alongside RegisterAgentActivity ops
    // at the author's DHT neighbourhood, halving hop count in must_get_agent_activity
    // calls during validation. Safe because ValidationRequest is immutable after creation.
    #[entry_type(cache_at_agent_activity = true)]
    ValidationRequest(ValidationRequest),
    #[entry_type(required_validations = 7)]
    ValidationAttestation(ValidationAttestation),
    ValidatorProfile(ValidatorProfile),
    DifficultyAssessment(DifficultyAssessment),
    // TODO: raise to required_validations = 7 once Oracle runs with a
    // production-scale agent count.  Deferred because the current demo uses
    // 5 apps on one conductor; with hundreds of AI validators this threshold
    // is trivially met and CommitmentAnchor should carry the same redundancy
    // guarantee as ValidationAttestation.
    // cache_at_agent_activity=true: commitment anchors are fetched by every validator
    // who participates in the same round; caching reduces gossip pressure on busy rounds.
    #[entry_type(cache_at_agent_activity = true)]
    CommitmentAnchor(CommitmentAnchor),
    PhaseMarker(PhaseMarker),
    StudyClaim(StudyClaim),
    StudyClaimRelease(StudyClaimRelease),
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
    /// Links StudyClaim ActionHash → StudyClaimRelease ActionHash.
    /// Presence of this link marks a claim as vacated (soft-delete).
    ClaimToRelease,
    /// Links request_ref (ExternalHash) → StudyClaimRelease ActionHash.
    /// Tag = claim_hash raw bytes (39 bytes).
    /// Allows claim_study and get_claims_for_request to fetch all releases for a
    /// study in a single network call instead of one call per claim (N→2 calls).
    RequestToRelease,
    /// Links AgentPubKey → StudyClaimRelease ActionHash.
    /// Tag = claim_hash raw bytes (39 bytes).
    /// Allows get_my_claimed_studies to fetch all releases for an agent in one call.
    ValidatorToRelease,
    /// Global pending-studies index.
    /// Base: "requests.pending" path anchor.
    /// Target: ValidationRequest ActionHash.
    /// Tag: request_ref (ExternalHash) raw 39 bytes.
    /// Covers all disciplines including Discipline::Other so sweep_timed_out_rounds
    /// can finalize any stuck round regardless of discipline.
    PendingStudiesPath,
}

// ---------------------------------------------------------------------------
// Validate Callback — HDI 0.8 (hdi 0.8.1 since Holochain 0.7.1)
// ---------------------------------------------------------------------------
//
// CRITICAL HDI API FACTS (originally written for HDI 0.7; still hold on 0.8.1):
// - op.flattened() consumes `op` — never call op.action() after flattened().
// - OpUpdate<ET> is an ENUM: OpUpdate::Entry { app_entry: ET, action: Update }
//   app_entry is the NEW entry. The new type MUST match the original type
//   (Holochain enforces this), so checking app_entry type is sufficient.
// - OpDelete is a STRUCT: OpDelete { action: Delete }
//   Use must_get_action(action.deletes_address) to check original type.
// - Membrane proof is in OpActivity::AgentValidationPkg { membrane_proof, .. }

macro_rules! handle_error {
    ($e:expr) => {
        match $e {
            Ok(v) => v,
            Err(e) => return Ok(ValidateCallbackResult::Invalid(e.to_string())),
        }
    };
}

#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- Update immutability guards (checked before generic update arm) ---

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::ValidationAttestation(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidationAttestation is immutable — the public record cannot be changed".into(),
        )),

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::CommitmentAnchor(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "CommitmentAnchor is immutable — commitments cannot be retracted".into(),
        )),

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::PhaseMarker(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "PhaseMarker is immutable — phase history is append-only".into(),
        )),

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::ResearcherResultCommitment(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ResearcherResultCommitment is immutable — the locked result commitment cannot be changed".into(),
        )),

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::ResearcherReveal(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ResearcherReveal is immutable — the verified reveal cannot be changed".into(),
        )),

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::AgentIdentityAttestation(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "AgentIdentityAttestation is immutable — use delete to revoke".into(),
        )),

        // ValidationRequest is immutable after submission — researchers cannot
        // silently lower num_validators_required to bypass the quorum gate.
        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::ValidationRequest(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidationRequest is immutable — the study submission cannot be altered".into(),
        )),

        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::StudyClaimRelease(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "StudyClaimRelease is immutable — the release record cannot be altered".into(),
        )),

        // StudyClaim is immutable — a validator must not be able to rewrite
        // their claim (e.g. change validator_institution after the fact to
        // erase COI evidence).  Claims are vacated via StudyClaimRelease.
        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::StudyClaim(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "StudyClaim is immutable — claims are vacated via StudyClaimRelease, not edited".into(),
        )),

        // Generic update: only the original author may update other entry types.
        // ValidatorProfile edits: the generic arm below checks authorship only, which
        // would let an author edit a forged tier in. MUST stay above that arm (#8).
        FlatOp::Update(OpUpdate::Entry {
            app_entry: EntryTypes::ValidatorProfile(ref profile),
            action,
        }) => {
            let original = must_get_action(action.original_action_address.clone())?;
            if action.author() != original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update this entry".into(),
                ));
            }
            match check_profile_certification(action.author(), profile)? {
                Some(reason) => Ok(ValidateCallbackResult::Invalid(reason)),
                None => Ok(ValidateCallbackResult::Valid),
            }
        }

        FlatOp::Update(OpUpdate::Entry { action, .. }) => {
            let original = must_get_action(action.original_action_address.clone())?;
            if action.author() != original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // Reject private entry updates (no private entries in this DNA).
        FlatOp::Update(OpUpdate::PrivateEntry { .. }) => Ok(
            ValidateCallbackResult::Invalid(
                "This DNA has no private entries".into(),
            ),
        ),

        // Other update variants: accept.
        FlatOp::Update(_) => Ok(ValidateCallbackResult::Valid),

        // --- Delete: look up original to check entry type ---
        FlatOp::Delete(OpDelete { action }) => {
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
                        Some(EntryTypes::StudyClaimRelease(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "StudyClaimRelease is immutable — cannot be deleted".into(),
                            ));
                        }
                        Some(EntryTypes::StudyClaim(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "StudyClaim is immutable — claims are vacated via \
                                 StudyClaimRelease, not deleted".into(),
                            ));
                        }
                        // AgentIdentityAttestation: either named agent may revoke.
                        // The normal "only author may delete" check below is bypassed
                        // because both agent_a and agent_b are equally authorised —
                        // but some third-party impostor must not be able to delete.
                        Some(EntryTypes::AgentIdentityAttestation(ref att)) => {
                            if action.author() == &att.agent_a
                                || action.author() == &att.agent_b
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
            if action.author() != original_record.action().author() {
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
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidationRequest(ref vr), ..
        }) => {
            // Hard floor: 0 validators would let check_all_commitments_sealed_inner
            // fire immediately (0 >= 0), opening the reveal phase on the first
            // commitment regardless of actual quorum — never valid.
            if vr.num_validators_required == 0 {
                return Ok(ValidateCallbackResult::Invalid(
                    "num_validators_required must be at least 1".into(),
                ));
            }
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
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::StudyClaim(ref claim),
            action:    ref create_action,
        }) => {
            let req_record =
                must_get_valid_record(claim.validation_request_hash.clone())?;
            let maybe_req: Option<ValidationRequest> = handle_error!(req_record.entry().to_app_option());
            let req = match maybe_req {
                Some(r) => r,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "StudyClaim.validation_request_hash does not point to a ValidationRequest".into()
                )),
            };
            // Cross-check: claim.request_ref must equal the ValidationRequest's
            // data_hash.  Prevents a claim referencing a benign ValidationRequest
            // for COI-check purposes while actually targeting a different study.
            if req.data_hash != claim.request_ref {
                return Ok(ValidateCallbackResult::Invalid(
                    "StudyClaim.request_ref does not match \
                     ValidationRequest.data_hash — the claim is for a different study".into(),
                ));
            }
            // Self-claim prevention: the agent who submitted the ValidationRequest
            // (the researcher) cannot also claim it as a validator.  Independent
            // validation requires distinct agents on both sides of the protocol.
            if create_action.author() == req_record.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Researcher cannot claim their own study — \
                     the same agent may not both submit and validate a study".into(),
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
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::CommitmentAnchor(ref anchor),
            action,
        }) => {
            // commitment_hash must be exactly 32 bytes (SHA-256).
            // A malformed hash counts toward the quorum but can never match
            // at reveal time, silently consuming a validator slot.
            if anchor.commitment_hash.len() != 32 {
                return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.commitment_hash must be exactly 32 bytes (SHA-256)".into(),
                ));
            }
            let req_record = must_get_valid_record(anchor.validation_request_hash.clone())?;
            let maybe_req: Option<ValidationRequest> = handle_error!(req_record.entry().to_app_option());
            let req = match maybe_req {
                Some(r) => r,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.validation_request_hash does not point to a ValidationRequest".into()
                )),
            };
            if req.data_hash != anchor.request_ref {
                return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.request_ref does not match \
                     ValidationRequest.data_hash".into(),
                ));
            }
            if &anchor.validator != action.author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.validator must equal the author of \
                     the create action".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ValidationAttestation create: verify it links to a CommitmentAnchor ---
        //
        // Inductive validation chain: ValidationAttestation → CommitmentAnchor → ValidationRequest.
        // commitment_anchor_hash is required on all new entries — the coordinator
        // always sets it.  The field is Option<ActionHash> in the struct for
        // backwards-compatible deserialisation of any legacy entries, but network
        // validation now rejects entries where it is absent.
        //
        // Discipline consistency is now enforced here: the attestation's
        // discipline must match the study's declared discipline from the
        // ValidationRequest.  A mismatched discipline would cause the HarmonyRecord
        // to be indexed under the wrong discipline and pollute the governance indexes.
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidationAttestation(ref att),
            action,
        }) => {
            let anchor_hash = match att.commitment_anchor_hash.as_ref() {
                Some(h) => h,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation.commitment_anchor_hash is required — \
                     every public attestation must reference its CommitmentAnchor".into()
                )),
            };
            let anchor_record = must_get_valid_record(anchor_hash.clone())?;
            let maybe_anchor: Option<CommitmentAnchor> = handle_error!(anchor_record.entry().to_app_option());
            let anchor = match maybe_anchor {
                Some(a) => a,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation.commitment_anchor_hash does not point to a CommitmentAnchor".into()
                )),
            };
            if &anchor.validator != action.author() {
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
            // Shape only, mirroring the CommitmentAnchor.commitment_hash check above.
            // A wrong-length value is a malformed commitment, not a disagreement, and
            // it would otherwise sit in the record looking like a real binding.
            //
            // ⚠️ Do NOT attempt to validate the bundle itself here. The bundle lives
            // off-DHT; validate() cannot fetch it and must stay deterministic. What is
            // enforced is that the validator committed to *some specific* 32-byte
            // content_hash and cannot swap it afterwards — not that the bundle behind
            // it is genuine. That is the bundle's own faithfulness property.
            if let Some(h) = att.reproduction_bundle_hash.as_ref() {
                if h.len() != 32 {
                    return Ok(ValidateCallbackResult::Invalid(
                        "ValidationAttestation.reproduction_bundle_hash must be exactly \
                         32 bytes (SHA-256 content_hash)".into(),
                    ));
                }
            }
            // Discipline consistency: walk the inductive chain one step further
            // to the ValidationRequest and verify the study's declared discipline.
            let req_record =
                must_get_valid_record(anchor.validation_request_hash.clone())?;
            let maybe_req: Option<ValidationRequest> = handle_error!(req_record.entry().to_app_option());
            let req = match maybe_req {
                Some(r) => r,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "CommitmentAnchor.validation_request_hash does not point to a ValidationRequest".into()
                )),
            };
            if att.discipline != req.discipline {
                return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation.discipline does not match the study's \
                     declared discipline in the ValidationRequest".into(),
                ));
            }
            // The study's terms, stamped by the coordinator at reveal. Governance
            // trusts these (under the validator's signature) to tell a complete
            // round from a subset of one — so they must be the request's own values.
            if att.request_num_validators != Some(req.num_validators_required) {
                return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation.request_num_validators must equal the \
                     ValidationRequest's num_validators_required".into(),
                ));
            }
            if att.request_created_at != Some(req_record.action().timestamp()) {
                return Ok(ValidateCallbackResult::Invalid(
                    "ValidationAttestation.request_created_at must equal the \
                     ValidationRequest's creation timestamp".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ValidatorProfile create: tier must be the certificate's (#8) --------
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidatorProfile(ref profile),
            action,
        }) => match check_profile_certification(action.author(), profile)? {
            Some(reason) => Ok(ValidateCallbackResult::Invalid(reason)),
            None => Ok(ValidateCallbackResult::Valid),
        },

        // --- AgentIdentityAttestation create: authorship, self-link, SIGNATURES ---
        //
        // 1. The action author must be one of the two named agents (same pattern
        //    as CommitmentAnchor.validator == action.author).
        // 2. The two named agents must be distinct (no self-attestation).
        // 3. Both Ed25519 signatures must verify over the sorted 78-byte payload.
        //
        // Rule 3 was coordinator-only until 2026-10-17, under the same false
        // belief as the membrane check (#37) — the comment here said
        // verify_signature was "HDK-only". So a modified coordinator could link
        // any agent to itself without that agent's consent. Now every peer
        // checks. The coordinator's check in link_agent_identity stays, for an
        // early, specific error.
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::AgentIdentityAttestation(ref att),
            action,
        }) => {
            if &att.agent_a != action.author() && &att.agent_b != action.author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "AgentIdentityAttestation author must be one of the two named agents".into(),
                ));
            }
            if att.agent_a == att.agent_b {
                return Ok(ValidateCallbackResult::Invalid(
                    "AgentIdentityAttestation requires two distinct agents".into(),
                ));
            }
            let payload = sorted_agent_pair_bytes(&att.agent_a, &att.agent_b);
            for (agent, signature) in [(&att.agent_a, &att.signature_a), (&att.agent_b, &att.signature_b)] {
                if !verify_signature(agent.clone(), signature.clone(), payload.clone())? {
                    return Ok(ValidateCallbackResult::Invalid(format!(
                        "AgentIdentityAttestation signature by {agent} failed verification"
                    )));
                }
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- Commitment links are immutable — block deletions ----------------
        //
        // A validator who deletes their own RequestToCommitment link can
        // re-open the commitment phase gate and block reveal_researcher_result
        // indefinitely.  Commitment links must be as permanent as the
        // CommitmentAnchor entry itself.
        FlatOp::Link(OpLink::DeleteLink {
            link_type: LinkTypes::RequestToCommitment,
            ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "RequestToCommitment links are immutable — \
             validator commitments cannot be retracted".into(),
        )),

        // --- Claim links are immutable — block deletions ---------------------
        //
        // The coordinator enforces capacity limits and duplicate prevention by
        // counting RequestToClaim links.  A validator who deletes their own
        // RequestToClaim link after claiming could free a capacity slot for a
        // colluder or re-claim the same study.  ValidatorToClaim is the
        // complementary index — deleting it would hide the claim from
        // get_my_claimed_studies queries.  Both must be as permanent as the
        // StudyClaim entry itself.
        FlatOp::Link(OpLink::DeleteLink {
            link_type: LinkTypes::RequestToClaim,
            ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "RequestToClaim links are immutable — \
             study claims cannot be retracted via link deletion".into(),
        )),

        FlatOp::Link(OpLink::DeleteLink {
            link_type: LinkTypes::ValidatorToClaim,
            ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidatorToClaim links are immutable — \
             study claims cannot be retracted via link deletion".into(),
        )),

        FlatOp::Link(OpLink::DeleteLink {
            link_type: LinkTypes::RequestToRelease,
            ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "RequestToRelease links are immutable — \
             release records cannot be retracted".into(),
        )),

        FlatOp::Link(OpLink::DeleteLink {
            link_type: LinkTypes::ValidatorToRelease,
            ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidatorToRelease links are immutable — \
             release records cannot be retracted".into(),
        )),

        // --- PhaseMarker create: verify it was written by a committed validator ------
        //
        // Inductive validation chain: PhaseMarker → CommitmentAnchor → ValidationRequest.
        // The commitment_anchor_hash must point to a real CommitmentAnchor whose
        // `validator` field matches the PhaseMarker's action author.  This prevents
        // any agent from forging a RevealOpen signal: you must have already committed
        // (i.e. have a CommitmentAnchor on the DHT naming you as validator) before
        // you can write the PhaseMarker that opens the reveal window.
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::PhaseMarker(ref marker),
            action,
        }) => {
            let anchor_record = must_get_valid_record(marker.commitment_anchor_hash.clone())?;
            let maybe_anchor: Option<CommitmentAnchor> = handle_error!(anchor_record.entry().to_app_option());
            let anchor = match maybe_anchor {
                Some(a) => a,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "PhaseMarker.commitment_anchor_hash does not point to a CommitmentAnchor".into()
                )),
            };
            if &anchor.validator != action.author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "PhaseMarker author must be the validator named in the referenced \
                     CommitmentAnchor — only a committed validator may open the reveal phase".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ResearcherResultCommitment create: enforce 32-byte hash length --------------
        //
        // Matches the CommitmentAnchor.commitment_hash constraint: both are SHA-256 hashes
        // and must be exactly 32 bytes.  A short or empty hash would be accepted by the
        // coordinator but could never be matched at reveal time, permanently blocking the
        // researcher's reveal without any visible error.
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ResearcherResultCommitment(ref c),
            ..
        }) => {
            if c.result_commitment_hash.len() != 32 {
                return Ok(ValidateCallbackResult::Invalid(
                    "ResearcherResultCommitment.result_commitment_hash must be exactly 32 bytes (SHA-256)".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- StudyClaimRelease create: verify claim_hash points to a real StudyClaim ----
        //
        // Only a structural check: confirms the referenced claim exists and is a
        // StudyClaim.  Author authorisation is intentionally NOT enforced here because
        // two distinct code paths write StudyClaimRelease entries:
        //   (1) release_claim   — the validator releasing their own claim (author == claim author)
        //   (2) reclaim_abandoned_claim — a third party freeing a slot after timeout (author ≠ claim author)
        // The integrity zome cannot evaluate the timeout, so the timeout + non-attestation
        // guards in the coordinator are the appropriate authorisation layer for path (2).
        // This follows the AgentIdentityAttestation delete arm pattern: structural validity
        // in the integrity zome, authorisation logic in the coordinator.
        FlatOp::CreateEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::StudyClaimRelease(ref release),
            ..
        }) => {
            let claim_record = must_get_valid_record(release.claim_hash.clone())?;
            let maybe_claim: Option<StudyClaim> = handle_error!(claim_record.entry().to_app_option());
            if maybe_claim.is_none() {
                return Ok(ValidateCallbackResult::Invalid(
                    "StudyClaimRelease.claim_hash does not point to a StudyClaim".into()
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- Membrane proof — full credential check, PEER-ENFORCED (#37) ---
        //
        // Every peer holding this op runs the full Ed25519 check, against the
        // op's own author. Until 2026-10-17 this arm checked the proof's LENGTH
        // only, on the belief that `verify_signature` was HDK-only. It never was:
        // `hdi::ed25519::verify_signature` exists (hdk merely re-exports it) and
        // validate() is granted `keystore_deterministic`. Under that belief the
        // credential was enforced only by the joining agent's own init() — so a
        // modified hApp could skip it, and no peer would ever notice.
        FlatOp::AgentActivity(OpActivity::AgentValidationPkg {
            membrane_proof, action,
        }) => match check_joining_certificate(action.author(), membrane_proof.as_ref())? {
            Ok(()) => Ok(ValidateCallbackResult::Valid),
            Err(reason) => Ok(ValidateCallbackResult::Invalid(reason)),
        },

        // All other ops: valid.
        _ => Ok(ValidateCallbackResult::Valid),
    }
}

/// The full joining-credential check: the ONE definition, used in three places.
///
/// | Caller | Who runs it | What it buys |
/// |---|---|---|
/// | `validate()`, `AgentValidationPkg` arm | **every peer** holding the op | the security property — a modified hApp cannot skip it |
/// | `genesis_self_check` | the joining agent, before joining | a clear, early install failure for an honest agent with a bad credential |
/// | coordinator `init()` | the joining agent, on first call | defence in depth; costs nothing |
///
/// Only the first is peer-enforced. The other two are self-run, the same trust
/// level as each other — kept because they fail fast and legibly, not because they
/// protect anything.
///
/// Returns `Ok(Err(reason))` for an invalid credential and `Err(_)` only for a host
/// failure, so callers can map the first to `Invalid` and propagate the second.
///
/// ⚠️ THE SIGNED PAYLOAD — do not hand-roll it. It is `agent_raw_39 || meta_bytes`,
/// passed to `verify_signature` as a `Vec<u8>`, which msgpack-ENCODES it before
/// verifying (`VerifySignature::new`). That is how every certificate already issued
/// was signed. Reconstructing the bytes any other way invalidates all of them, and
/// the failure looks exactly like the guard working. See #37 and
/// `sweettest_integration/tests/membrane_proof.rs`.
pub fn check_joining_certificate(
    joining_agent: &AgentPubKey,
    membrane_proof: Option<&MembraneProof>,
) -> ExternResult<Result<(), String>> {
    let props = DnaProperties::try_from_dna_properties()?;

    // Dev/test bypass: an empty human issuer key switches the whole credential
    // system off (ai_validator_issuer is then irrelevant too). Unchanged from
    // before #37, in all three callers.
    if props.authorized_joining_certificate_issuer.is_empty() {
        return Ok(Ok(()));
    }

    let proof = match membrane_proof {
        None => {
            return Ok(Err(
                "Attestation DNA requires a membrane proof (institutional credential)".into(),
            ))
        }
        Some(p) => p,
    };
    if proof.bytes().len() < 64 {
        return Ok(Err(
            "Membrane proof is too short to contain a 64-byte Ed25519 signature".into(),
        ));
    }

    let cert = match JoiningCertificate::from_proof_bytes(proof.bytes()) {
        Ok(c) => c,
        Err(e) => return Ok(Err(format!("invalid joining certificate: {e}"))),
    };

    // Route to the issuer for this validator type:
    //   Human → authorized_joining_certificate_issuer (institutional credential)
    //   AI    → ai_validator_issuer if set, else the human issuer key
    //           (single-key deployments reuse one key for both paths).
    let issuer_str = match cert.validator_type {
        ValidatorType::AI if !props.ai_validator_issuer.is_empty() => props.ai_validator_issuer,
        _ => props.authorized_joining_certificate_issuer,
    };
    let issuer_key = match issuer_str.parse::<AgentPubKeyB64>() {
        Ok(k) => AgentPubKey::from(k),
        Err(_) => {
            return Ok(Err(
                "issuer key in DNA properties is not a valid AgentPubKey".into(),
            ))
        }
    };

    let mut signed_data: Vec<u8> = joining_agent.get_raw_39().to_vec();
    if proof.bytes().len() > 64 {
        signed_data.extend_from_slice(&proof.bytes()[64..]);
    }
    if !verify_signature(issuer_key, Signature::from(cert.signature), signed_data)? {
        return Ok(Err(
            "Membrane proof signature is invalid — not signed by the authorized issuer".into(),
        ));
    }
    Ok(Ok(()))
}

// ---------------------------------------------------------------------------
// genesis_self_check — runs BEFORE network join, on the joining agent only
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn genesis_self_check(
    data: GenesisSelfCheckData,
) -> ExternResult<ValidateCallbackResult> {
    // The full check, not just the format: `keystore_deterministic` is granted here
    // too (holochain guest_callback/genesis_self_check/v2.rs), and `agent_key` is the
    // key the AgentValidationPkg will be authored by. Self-run, so it protects
    // nothing — validate() does that — but it turns a bad credential into an install
    // error with a reason, instead of a cell that joins and then fails at init.
    match check_joining_certificate(&data.agent_key, data.membrane_proof.as_ref())? {
        Ok(()) => Ok(ValidateCallbackResult::Valid),
        Err(reason) => Ok(ValidateCallbackResult::Invalid(reason)),
    }
}
