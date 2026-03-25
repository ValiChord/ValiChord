use hdk::prelude::*;
use attestation_integrity::{
    AgentIdentityAttestation,
    AssessmentConfidence, CommitmentAnchor, CommitmentSealedInput, DifficultyAssessment,
    DifficultyTier, DnaProperties, EntryTypes, LinkTypes, PhaseMarker,
    ResearcherCommitmentInput, ResearcherResultCommitment, ResearcherReveal, ResearcherRevealInput,
    StudyClaim, ValidatorAgentType, ValidatorProfile, ValidationRequest,
};
use valichord_shared_types::{Discipline, ValidationAttestation, ValidationPhase, discipline_tag};
use sha2::{Digest, Sha256};
use rmp_serde as rmps;
use std::collections::HashSet;

// ---------------------------------------------------------------------------
// init — capability grants
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
    let zome = zome_info()?.name;
    // GrantedFunction = (ZomeName, FunctionName) — it is a tuple alias.
    let mut public_fns: HashSet<GrantedFunction> = HashSet::new();
    for fn_name in &[
        "recv_remote_signal",
        "get_validation_request",
        "get_attestations_for_request",
        "get_attestations_for_discipline",
        "get_validators_for_discipline",
        "get_validators_for_institution",
        "get_pending_requests_for_discipline",
        "get_validator_profile",
        "check_all_commitments_sealed",
        "get_current_phase",
        "get_difficulty_assessment",
        "get_validation_request_for_data_hash",
        "get_num_validators_required",
        "get_claims_for_request",
        "get_my_claimed_studies",
        "reclaim_abandoned_claim",
        "get_researcher_commitment",
        "get_researcher_reveal",
        "get_validator_agent_type",
        "get_linked_agents",
    ] {
        public_fns.insert((zome.clone(), FunctionName::from(*fn_name)));
    }
    create_cap_grant(ZomeCallCapGrant {
        tag: "public-read".into(),
        access: CapAccess::Unrestricted,
        functions: GrantedFunctions::Listed(public_fns),
    })?;

    // notify_commitment_sealed is intentionally NOT listed — it is a write
    // function called via call(OtherRole("attestation")) from DNA 2's
    // post_commit. Same-agent cross-DNA calls run under author grant.

    // Verify the membrane proof cryptographically (Ed25519 signature check).
    // This runs lazily on the first zome call, after the agent has joined the
    // DHT and the AgentValidationPkg action is on the source chain.
    // verify_signature is an HDK host function not available in integrity zomes.
    // Empty issuer = dev/test bypass (matches the governance DNA pattern).
    if let Err(reason) = verify_membrane_proof() {
        return Ok(InitCallbackResult::Fail(reason));
    }

    Ok(InitCallbackResult::Pass)
}

// ---------------------------------------------------------------------------
// Membrane proof — Ed25519 verification (coordinator-side, HDK only)
// ---------------------------------------------------------------------------

fn verify_membrane_proof() -> Result<(), String> {
    let props = DnaProperties::try_from_dna_properties().map_err(|e| e.to_string())?;

    // Empty string = dev/test bypass: skip crypto verification.
    if props.authorized_joining_certificate_issuer.is_empty() {
        return Ok(());
    }

    // Parse the issuer's AgentPubKey from the base64url string in DNA properties.
    let issuer_b64 = props
        .authorized_joining_certificate_issuer
        .parse::<HoloHashB64<hash_type::Agent>>()
        .map_err(|_| {
            "authorized_joining_certificate_issuer is not a valid AgentPubKey".to_string()
        })?;
    let issuer_key = AgentPubKey::from(issuer_b64);

    // Find the AgentValidationPkg action on our own source chain (genesis action 2).
    let records = query(ChainQueryFilter::new()).map_err(|e| e.to_string())?;
    // Use Option<Option<MembraneProof>>: outer None = AVP not found;
    // inner None = AVP found but membrane_proof field is absent.
    let mut avp_result: Option<Option<MembraneProof>> = None;
    for record in &records {
        if let Action::AgentValidationPkg(avp) = record.action() {
            avp_result = Some(avp.membrane_proof.clone());
            break;
        }
    }
    let proof = avp_result
        .ok_or_else(|| "AgentValidationPkg not found on source chain".to_string())?
        .ok_or_else(|| "Attestation DNA requires a membrane proof".to_string())?;

    if proof.bytes().len() < 64 {
        return Err("Membrane proof too short — must be at least 64 bytes".to_string());
    }

    // Extract the 64-byte Ed25519 signature from the start of the proof.
    let sig_bytes: [u8; 64] = proof.bytes()[0..64]
        .try_into()
        .map_err(|_| "proof slice wrong size".to_string())?;
    let signature = Signature::from(sig_bytes);

    // Signed data = joining agent's raw 39-byte pubkey as Vec<u8>.
    // verify_signature serialises the data parameter via rmp_serde (SerializedBytes).
    // rmp_serde encodes Vec<u8> using serialize_bytes → msgpack BIN format (not a
    // fixarray of fixints). The JS issuer tool must therefore sign the msgpack-bin-
    // encoded key, e.g. encode(Buffer.from(agentPubKey)) with a msgpack library
    // that treats Buffer/Uint8Array as bytes — NOT encode(Array.from(agentPubKey)),
    // which would produce a fixarray and fail verification.
    let joining_agent = agent_info().map_err(|e| e.to_string())?.agent_initial_pubkey;
    let raw_bytes: Vec<u8> = joining_agent.get_raw_39().to_vec();
    let valid = verify_signature(issuer_key, signature, raw_bytes)
        .map_err(|e| e.to_string())?;

    if !valid {
        return Err(
            "Membrane proof signature is invalid — not signed by the authorized issuer"
                .to_string(),
        );
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn submit_validation_request(
    request: ValidationRequest,
) -> ExternResult<ActionHash> {
    let discipline = request.discipline.clone();
    let data_hash  = request.data_hash.clone();
    let request_hash = create_entry(EntryTypes::ValidationRequest(request))?;

    // Index by study data hash for discovery.
    let study_path = Path::from(format!("study.{}", data_hash))
        .typed(LinkTypes::StudyToValidation)?;
    study_path.ensure()?;
    create_link(
        study_path.path_entry_hash()?,
        request_hash.clone(),
        LinkTypes::StudyToValidation,
        (),
    )?;

    // Index by status + discipline for queue management.
    let status_path = Path::from(format!(
        "requests.pending.{}",
        discipline_tag(&discipline)
    ))
    .typed(LinkTypes::StatusPath)?;
    status_path.ensure()?;
    create_link(
        status_path.path_entry_hash()?,
        request_hash.clone(),
        LinkTypes::StatusPath,
        (),
    )?;

    Ok(request_hash)
}

/// Input for `submit_attestation` — the validator's public reveal.
///
/// The `nonce` is the same 32-byte value generated by `seal_private_attestation`
/// in the validator's local Workspace DNA and stored in `ValidatorPrivateAttestation`.
/// The UI retrieves it via `get_private_attestation_for_task` before calling here.
///
/// The nonce is used to verify the commitment binding:
///   SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash
///
/// The nonce is NOT written to the DHT — it is only used for this verification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRevealInput {
    pub attestation: ValidationAttestation,
    /// The 32-byte private nonce from `seal_private_attestation`.
    pub nonce: Vec<u8>,
}

/// Submit a public attestation — THE REVEAL PHASE.
/// IMMUTABLE after write.
///
/// Verifies that the revealed attestation matches the commitment written during
/// the commit phase: SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash.
/// The call is rejected if no prior CommitmentAnchor exists for this validator,
/// or if the hash does not match — closing the adaptive-reveal attack surface.
///
/// After writing the attestation this function attempts to finalise the
/// validation round by calling check_and_create_harmony_record on the
/// Governance DNA.  The call is fire-and-forget: if the round is not yet
/// complete the governance function returns null silently.  If the round is
/// complete, any validator who submits last triggers the HarmonyRecord write.
#[hdk_extern]
pub fn submit_attestation(input: AttestationRevealInput) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_initial_pubkey;
    let attestation = input.attestation;
    let disc_tag = attestation.discipline_tag();
    let request_ref = attestation.request_ref.clone();

    // Verify: SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash.
    // The serialisation codec matches seal_private_attestation exactly —
    // SerializedBytes::try_from uses rmp_serde::to_vec_named internally.
    //
    // Dev/test bypass: skipped entirely when authorized_joining_certificate_issuer
    // is empty (same pattern as the membrane-proof and Guard-1 bypasses). In
    // production the issuer key is always set, so commit-reveal is always enforced.
    let reveal_props = DnaProperties::try_from_dna_properties()?;
    if !reveal_props.authorized_joining_certificate_issuer.is_empty() {
        let msgpack_bytes: Vec<u8> = SerializedBytes::try_from(&attestation)
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
            .bytes()
            .to_vec();
        let mut hasher = Sha256::new();
        hasher.update(&msgpack_bytes);
        hasher.update(&input.nonce);
        let computed_hash: Vec<u8> = hasher.finalize().to_vec();

        // Find the CommitmentAnchor written for this agent during the commit phase.
        let commit_path = Path::from(format!("commitments.{}", request_ref))
            .typed(LinkTypes::RequestToCommitment)?;
        let commit_links = get_links(
            LinkQuery::try_new(commit_path.path_entry_hash()?, LinkTypes::RequestToCommitment)?,
            GetStrategy::Network,
        )?;
        let prior_commitment_hash = commit_links
            .into_iter()
            .find_map(|link| {
                let hash = link.target.into_action_hash()?;
                let record = get(hash, GetOptions::network()).ok()??;
                let anchor: CommitmentAnchor = record.entry().to_app_option().ok()??;
                if anchor.validator == agent { Some(anchor.commitment_hash) } else { None }
            })
            .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                "No CommitmentAnchor found for this validator and study — \
                 seal_private_attestation must be committed before reveal".into()
            )))?;

        if computed_hash != prior_commitment_hash {
            return Err(wasm_error!(WasmErrorInner::Guest(
                "Hash mismatch — attestation and nonce do not match the previously \
                 committed hash. The reveal must be identical to the sealed commit.".into()
            )));
        }
    }

    // Duplicate submission guard: a validator with a single CommitmentAnchor
    // could call submit_attestation multiple times with the same attestation+nonce,
    // writing N identical entries and gaining N-fold vote weight in the
    // HarmonyRecord plurality tally.
    let existing_att_links = get_links(
        LinkQuery::try_new(agent.clone(), LinkTypes::ValidatorToAttestation)?,
        GetStrategy::Network,
    )?;
    let already_attested = existing_att_links.iter().any(|link| {
        link.target
            .clone()
            .into_action_hash()
            .and_then(|h| get(h, GetOptions::network()).ok().flatten())
            .and_then(|r| r.entry().to_app_option::<ValidationAttestation>().ok().flatten())
            .map(|a| a.request_ref == request_ref)
            .unwrap_or(false)
    });
    if already_attested {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Validator has already submitted an attestation for this study — \
             duplicate reveals are not permitted".into()
        )));
    }

    // Commitment verified — write the public attestation.
    let attestation_hash =
        create_entry(EntryTypes::ValidationAttestation(attestation.clone()))?;

    create_link(
        agent,
        attestation_hash.clone(),
        LinkTypes::ValidatorToAttestation,
        (),
    )?;

    let disc_path =
        Path::from(format!("attestations.{}", disc_tag)).typed(LinkTypes::DisciplinePath)?;
    disc_path.ensure()?;
    create_link(
        disc_path.path_entry_hash()?,
        attestation_hash.clone(),
        LinkTypes::DisciplinePath,
        (),
    )?;

    // Attempt to finalise the round.  Errors are swallowed — a failed
    // finalisation attempt does not invalidate the attestation itself.
    let _ = call(
        CallTargetCell::OtherRole("governance".into()),
        ZomeName::from("governance_coordinator"),
        FunctionName::from("check_and_create_harmony_record"),
        None,
        request_ref,
    );

    Ok(attestation_hash)
}

#[hdk_extern]
pub fn publish_validator_profile(
    profile: ValidatorProfile,
) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_initial_pubkey;
    // Extract fields before profile is consumed by create_entry.
    let disciplines = profile.disciplines.clone();
    let institution = profile.institution.clone();
    let profile_hash = create_entry(EntryTypes::ValidatorProfile(profile))?;
    // Tag = 8-byte big-endian microsecond timestamp — enables deterministic
    // max_by_key ordering in all profile reads (get_validator_profile,
    // update_validator_profile, get_validator_agent_type, claim_study).
    // Old links with no tag return i64::MIN in profile_link_ts(), so they
    // always sort below any tagged link — backwards-compatible.
    let profile_ts: i64 = sys_time()?.as_micros();
    create_link(agent, profile_hash.clone(), LinkTypes::AgentToProfile, LinkTag::new(profile_ts.to_be_bytes().to_vec()))?;

    // Index under each discipline path so get_validators_for_discipline can find this profile.
    for disc in &disciplines {
        let disc_path = Path::from(format!("validators.{}", discipline_tag(disc)))
            .typed(LinkTypes::ValidatorTierPath)?;
        disc_path.ensure()?;
        create_link(
            disc_path.path_entry_hash()?,
            profile_hash.clone(),
            LinkTypes::ValidatorTierPath,
            (),
        )?;
    }

    // Index by institution so get_validators_for_institution can find this profile.
    // Used for conflict-of-interest detection in validator assignment.
    let inst_path = Path::from(format!("institution.{}", institution))
        .typed(LinkTypes::InstitutionPath)?;
    inst_path.ensure()?;
    create_link(
        inst_path.path_entry_hash()?,
        profile_hash.clone(),
        LinkTypes::InstitutionPath,
        (),
    )?;

    Ok(profile_hash)
}

/// Input for `update_validator_profile`.
///
/// All fields are `Option` — supply only the fields you want to change.
/// `None` fields are copied from the validator's current profile.
/// If no current profile exists, `None` fields fall back to sensible defaults
/// (empty string, empty vec, Provisional tier, false, 0, None).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateValidatorProfileInput {
    pub institution:          Option<String>,
    pub disciplines:          Option<Vec<Discipline>>,
    pub available:            Option<bool>,
    pub max_concurrent_tasks: Option<u8>,
    pub orcid:                Option<Option<String>>,
    pub agent_type:           Option<Option<ValidatorAgentType>>,
    #[serde(default)]
    pub person_key:           Option<Option<AgentPubKey>>,
}

/// Update the calling agent's validator profile.
///
/// Fetches the current profile (via the latest `AgentToProfile` link) and
/// merges `UpdateValidatorProfileInput` on top of it — only supplied
/// (`Some`) fields are changed.  Then calls `publish_validator_profile` with
/// the merged result, which creates a new entry and updates all discovery
/// indexes (discipline paths, institution path).
///
/// Called via the author grant (same-agent only).
#[hdk_extern]
pub fn update_validator_profile(
    input: UpdateValidatorProfileInput,
) -> ExternResult<ActionHash> {
    use valichord_shared_types::CertificationTier;

    let agent = agent_info()?.agent_initial_pubkey;

    // Resolve the existing profile (if any) to merge against.
    let existing: Option<ValidatorProfile> = {
        let profile_links = get_links(
            LinkQuery::try_new(agent.clone(), LinkTypes::AgentToProfile)?,
            GetStrategy::Network,
        )?;
        profile_links
            .iter()
            .max_by_key(|l| profile_link_ts(l))
            .and_then(|l| l.target.clone().into_action_hash())
            .and_then(|h| get(h, GetOptions::network()).ok().flatten())
            .and_then(|r| r.entry().to_app_option::<ValidatorProfile>().ok().flatten())
    };

    let base = existing.unwrap_or_else(|| ValidatorProfile {
        institution:          String::new(),
        disciplines:          Vec::new(),
        certification_tier:   CertificationTier::Provisional,
        available:            false,
        max_concurrent_tasks: 0,
        orcid:                None,
        agent_type:           None,
        person_key:           None,
    });

    let merged = ValidatorProfile {
        institution:          input.institution.unwrap_or(base.institution),
        disciplines:          input.disciplines.unwrap_or(base.disciplines),
        certification_tier:   base.certification_tier, // tier is computed, not editable directly
        available:            input.available.unwrap_or(base.available),
        max_concurrent_tasks: input.max_concurrent_tasks.unwrap_or(base.max_concurrent_tasks),
        orcid:                input.orcid.unwrap_or(base.orcid),
        agent_type:           input.agent_type.unwrap_or(base.agent_type),
        person_key:           input.person_key.unwrap_or(base.person_key),
    };

    publish_validator_profile(merged)
}

/// Return the `ValidatorAgentType` for a given agent (if declared).
///
/// Convenience read function — fetches the latest profile and extracts
/// the `agent_type` field.  Returns `None` if no profile exists or the
/// field was not set on profile creation.
#[hdk_extern]
pub fn get_validator_agent_type(
    agent: AgentPubKey,
) -> ExternResult<Option<ValidatorAgentType>> {
    let profile_links = get_links(
        LinkQuery::try_new(agent, LinkTypes::AgentToProfile)?,
        GetStrategy::Network,
    )?;
    Ok(profile_links
        .iter()
        .max_by_key(|l| profile_link_ts(l))
        .and_then(|l| l.target.clone().into_action_hash())
        .and_then(|h| get(h, GetOptions::network()).ok().flatten())
        .and_then(|r| r.entry().to_app_option::<ValidatorProfile>().ok().flatten())
        .and_then(|p| p.agent_type))
}

/// Caller-provided input for a difficulty assessment.
///
/// The coordinator does NOT compute these values — it stores what the assessor
/// supplies and indexes for retrieval.  Automated prediction (ML model, feature
/// extraction from the repository) is Phase 1 work; Phase 0 validates whether
/// the surface features correlate with actual validation workload at all.
///
/// Constraints per field: all `u8` scores are on a 1–5 scale (1 = trivial,
/// 5 = extreme).  `predicted_min_secs` must be ≤ `predicted_max_secs`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssessDifficultyInput {
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

/// Store a difficulty assessment for a validation request.
///
/// The assessor supplies all fields — no hardcoded prediction model.
/// Phase 0 will use the collected assessments to determine whether surface
/// features actually predict validation workload, at which point a real
/// prediction model can be substituted.
///
/// Only one assessment per request is expected (idempotency not enforced —
/// `get_difficulty_assessment` returns the latest via `DifficultyPath`).
/// Add a per-agent guard here when real assessment logic is implemented.
#[hdk_extern]
pub fn assess_difficulty(
    input: AssessDifficultyInput,
) -> ExternResult<ActionHash> {
    if input.predicted_min_secs > input.predicted_max_secs {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "predicted_min_secs must not exceed predicted_max_secs".into()
        )));
    }
    let link_base = input.request_ref.clone();
    let assessment = DifficultyAssessment {
        request_ref:            input.request_ref,
        code_volume:            input.code_volume,
        dependency_count:       input.dependency_count,
        documentation_quality:  input.documentation_quality,
        data_accessibility:     input.data_accessibility,
        environment_complexity: input.environment_complexity,
        study_age_years:        input.study_age_years,
        predicted_tier:         input.predicted_tier,
        predicted_min_secs:     input.predicted_min_secs,
        predicted_max_secs:     input.predicted_max_secs,
        confidence:             input.confidence,
    };
    let assessment_hash = create_entry(EntryTypes::DifficultyAssessment(assessment))?;
    // Index directly from request_ref (ExternalHash is a valid DHT base address).
    // Using request_ref as base is consistent with how governance indexes badges,
    // and avoids a path intermediate for a simple one-to-one lookup.
    create_link(
        link_base,
        assessment_hash.clone(),
        LinkTypes::DifficultyPath,
        (),
    )?;
    Ok(assessment_hash)
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn get_validation_request(hash: ActionHash) -> ExternResult<Option<Record>> {
    get(hash, GetOptions::network())
}

/// Return the ValidationRequest record for a given data hash (study identifier).
///
/// The path "study.{data_hash}" is written by submit_validation_request.
/// Used by governance to identify the researcher who submitted the study
/// (record author = issued_to for ReproducibilityBadge).
#[hdk_extern]
pub fn get_validation_request_for_data_hash(
    data_hash: ExternalHash,
) -> ExternResult<Option<Record>> {
    let study_path = Path::from(format!("study.{}", data_hash))
        .typed(LinkTypes::StudyToValidation)?;
    let links = get_links(
        LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
        GetStrategy::Network,
    )?;
    match links.first() {
        Some(link) => {
            let hash = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid StudyToValidation link target".into()
                )))?;
            get(hash, GetOptions::network())
        }
        None => Ok(None),
    }
}

/// Return the num_validators_required for the ValidationRequest identified by
/// data_hash.  Called by the Governance DNA's check_and_create_harmony_record
/// to enforce completeness before writing a HarmonyRecord.
///
/// Returns an error if the ValidationRequest is not found or has not yet
/// propagated.  Callers must treat this error conservatively — do NOT default
/// to 1, as that would allow a single attestation to finalise any study
/// regardless of the agreed quorum.
#[hdk_extern]
pub fn get_num_validators_required(data_hash: ExternalHash) -> ExternResult<u8> {
    get_validation_request_for_data_hash(data_hash)?
        .and_then(|r| r.entry().to_app_option::<ValidationRequest>().ok().flatten())
        .map(|vr| vr.num_validators_required)
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "ValidationRequest not found — cannot determine num_validators_required".into()
        )))
}

// ---------------------------------------------------------------------------
// Validator self-assignment
// ---------------------------------------------------------------------------

/// Claim a study from the pending queue.
///
/// The validator passes the data_hash (ExternalHash) they see in
/// get_pending_requests_for_discipline.  The coordinator resolves the
/// ValidationRequest ActionHash and their own institution from their
/// ValidatorProfile, then writes the StudyClaim entry and two link indexes.
///
/// Enforced here (coordinator layer):
///   - Capacity: cannot claim if num_validators_required claims already exist.
///   - Duplicate: cannot claim the same study twice.
///
/// Enforced by validate() (network layer):
///   - COI: validator and researcher must not share institution.
#[hdk_extern]
pub fn claim_study(request_ref: ExternalHash) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_initial_pubkey;

    // Resolve the ValidationRequest ActionHash from the study path.
    let (vr_action_hash, vr) = {
        let study_path = Path::from(format!("study.{}", request_ref))
            .typed(LinkTypes::StudyToValidation)?;
        let links = get_links(
            LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
            GetStrategy::Network,
        )?;
        let link = links.first().ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "No ValidationRequest found for this data_hash — submit_validation_request first"
                .into(),
        )))?;
        let hash = link.target.clone().into_action_hash().ok_or_else(|| {
            wasm_error!(WasmErrorInner::Guest(
                "StudyToValidation link target is not an ActionHash".into(),
            ))
        })?;
        let record = get(hash.clone(), GetOptions::network())?.ok_or_else(|| {
            wasm_error!(WasmErrorInner::Guest(
                "ValidationRequest record not found on DHT".into(),
            ))
        })?;
        let vr = record
            .entry()
            .to_app_option::<ValidationRequest>()
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
            .ok_or_else(|| {
                wasm_error!(WasmErrorInner::Guest(
                    "Link target is not a ValidationRequest".into(),
                ))
            })?;
        (hash, vr)
    };

    // Single get_links call serves both capacity and duplicate checks.
    let claim_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    if claim_links.len() >= vr.num_validators_required as usize {
        return Err(wasm_error!(WasmErrorInner::Guest(format!(
            "Study is at capacity ({}/{} validators already claimed)",
            claim_links.len(),
            vr.num_validators_required,
        ))));
    }
    if claim_links.iter().any(|l| l.author == agent) {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Validator has already claimed this study".into(),
        )));
    }

    // Resolve the validator's institution from their profile.
    let validator_institution = {
        let profile_links = get_links(
            LinkQuery::try_new(agent.clone(), LinkTypes::AgentToProfile)?,
            GetStrategy::Network,
        )?;
        profile_links
            .iter()
            .max_by_key(|l| profile_link_ts(l))
            .and_then(|l| l.target.clone().into_action_hash())
            .and_then(|h| get(h, GetOptions::network()).ok().flatten())
            .and_then(|r| r.entry().to_app_option::<ValidatorProfile>().ok().flatten())
            .map(|p| p.institution)
            .unwrap_or_default()
    };

    // Write the claim entry and indexes.
    let claim = StudyClaim {
        request_ref: request_ref.clone(),
        validation_request_hash: vr_action_hash,
        validator_institution,
    };
    let claim_hash = create_entry(EntryTypes::StudyClaim(claim))?;

    // RequestToClaim: base = request_ref (ExternalHash as DHT address).
    create_link(
        request_ref.clone(),
        claim_hash.clone(),
        LinkTypes::RequestToClaim,
        (),
    )?;

    // ValidatorToClaim: base = this agent's pubkey.
    create_link(
        agent,
        claim_hash.clone(),
        LinkTypes::ValidatorToClaim,
        (),
    )?;

    Ok(claim_hash)
}

/// Release a previously claimed study.
///
/// Deletes the RequestToClaim and ValidatorToClaim links so the slot becomes
/// available again.  The StudyClaim entry itself remains on the DHT as an
/// immutable audit record.
#[hdk_extern]
pub fn release_claim(request_ref: ExternalHash) -> ExternResult<()> {
    let agent = agent_info()?.agent_initial_pubkey;

    // Delete the RequestToClaim link authored by this agent.
    let request_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    for link in request_links.iter().filter(|l| l.author == agent) {
        delete_link(link.create_link_hash.clone(), GetOptions::network())?;
    }

    // Delete the corresponding ValidatorToClaim link.
    let validator_links = get_links(
        LinkQuery::try_new(agent, LinkTypes::ValidatorToClaim)?,
        GetStrategy::Network,
    )?;
    for link in validator_links {
        if let Some(hash) = link.target.clone().into_action_hash() {
            if let Some(record) = get(hash, GetOptions::local())? {
                if let Some(claim) = record
                    .entry()
                    .to_app_option::<StudyClaim>()
                    .ok()
                    .flatten()
                {
                    if claim.request_ref == request_ref {
                        delete_link(link.create_link_hash, GetOptions::network())?;
                    }
                }
            }
        }
    }

    Ok(())
}

/// Return all live StudyClaim records for a given study (request_ref).
#[hdk_extern]
pub fn get_claims_for_request(request_ref: ExternalHash) -> ExternResult<Vec<Record>> {
    let links = get_links(
        LinkQuery::try_new(request_ref, LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
}

/// Return all studies this validator has claimed (live ValidatorToClaim links).
#[hdk_extern]
pub fn get_my_claimed_studies(_: ()) -> ExternResult<Vec<Record>> {
    let agent = agent_info()?.agent_initial_pubkey;
    let links = get_links(
        LinkQuery::try_new(agent, LinkTypes::ValidatorToClaim)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
}

/// Input for reclaim_abandoned_claim.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReclaimInput {
    /// The study's data_hash (ExternalHash) — same as used in claim_study.
    pub request_ref:  ExternalHash,
    /// ActionHash of the abandoned StudyClaim entry.
    pub claim_hash:   ActionHash,
    /// How old (in seconds) the claim must be before reclamation is allowed.
    /// Typical Phase 0 value: 604800 (7 days). Use a shorter value in tests.
    pub timeout_secs: u64,
}

/// Reclaim an abandoned validator slot on behalf of a validator who has gone dark.
///
/// Any participant may call this once `timeout_secs` have elapsed since the
/// claim was created AND the absent validator has not submitted an attestation
/// for this study. Deletes both link indexes, freeing the slot for a replacement.
/// The StudyClaim entry remains permanently as an audit record.
///
/// Returns `true` if the slot was reclaimed, `false` if ineligible
/// (claim too recent, or validator already attested).
#[hdk_extern]
pub fn reclaim_abandoned_claim(input: ReclaimInput) -> ExternResult<bool> {
    // 1. Fetch the claim record to determine the absent validator's pubkey.
    let claim_record = get(input.claim_hash.clone(), GetOptions::network())?
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "StudyClaim record not found".into(),
        )))?;
    let absent_validator = claim_record.action().author().clone();

    // 2. Check claim age — sys_time() and Timestamp are both microseconds since epoch.
    let now = sys_time()?;
    let claim_time = claim_record.action().timestamp();
    let elapsed_secs = (now.0 - claim_time.0) / 1_000_000;

    // Enforce DNA-property minimum to prevent callers from bypassing the timeout
    // by passing timeout_secs = 0.  min_claim_timeout_secs = 0 = dev/test bypass.
    let props = DnaProperties::try_from_dna_properties()?;
    let effective_timeout_secs = if props.min_claim_timeout_secs > 0 {
        input.timeout_secs.max(props.min_claim_timeout_secs)
    } else {
        input.timeout_secs
    };

    if elapsed_secs < effective_timeout_secs as i64 {
        return Ok(false); // Too recent — reclamation not yet permitted.
    }

    // 3. Verify the absent validator has not already attested for this study.
    let attestation_links = get_links(
        LinkQuery::try_new(absent_validator.clone(), LinkTypes::ValidatorToAttestation)?,
        GetStrategy::Network,
    )?;
    for link in &attestation_links {
        if let Some(hash) = link.target.clone().into_action_hash() {
            if let Some(record) = get(hash, GetOptions::network())? {
                if let Some(att) = record
                    .entry()
                    .to_app_option::<ValidationAttestation>()
                    .ok()
                    .flatten()
                {
                    if att.request_ref == input.request_ref {
                        return Ok(false); // Already attested — no reclamation needed.
                    }
                }
            }
        }
    }

    // 4. Delete the RequestToClaim link authored by the absent validator.
    let request_links = get_links(
        LinkQuery::try_new(input.request_ref.clone(), LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    for link in request_links.iter().filter(|l| l.author == absent_validator) {
        if link.target.clone().into_action_hash().as_ref() == Some(&input.claim_hash) {
            delete_link(link.create_link_hash.clone(), GetOptions::network())?;
        }
    }

    // 5. Delete the ValidatorToClaim link from the absent validator's pubkey.
    let validator_links = get_links(
        LinkQuery::try_new(absent_validator.clone(), LinkTypes::ValidatorToClaim)?,
        GetStrategy::Network,
    )?;
    for link in validator_links {
        if link.target.clone().into_action_hash().as_ref() == Some(&input.claim_hash) {
            delete_link(link.create_link_hash, GetOptions::network())?;
        }
    }

    Ok(true)
}

#[hdk_extern]
pub fn get_attestations_for_request(
    request_ref: ExternalHash,
) -> ExternResult<Vec<Record>> {
    // Discover validators who committed via CommitmentAnchor links on the path.
    let commit_path = Path::from(format!("commitments.{}", request_ref))
        .typed(LinkTypes::RequestToCommitment)?;
    let commit_links = get_links(
        LinkQuery::try_new(
            commit_path.path_entry_hash()?,
            LinkTypes::RequestToCommitment,
        )?,
        GetStrategy::Network,
    )?;

    let mut attestations = Vec::new();
    for link in commit_links {
        let anchor_hash = match link.target.into_action_hash() {
            Some(h) => h,
            None => continue,
        };
        let anchor_record = match get(anchor_hash, GetOptions::network())? {
            Some(r) => r,
            None => continue,
        };
        let anchor: CommitmentAnchor = match anchor_record
            .entry()
            .to_app_option()
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
        {
            Some(a) => a,
            None => continue,
        };
        let att_links = get_links(
            LinkQuery::try_new(anchor.validator, LinkTypes::ValidatorToAttestation)?,
            GetStrategy::Network,
        )?;
        for att_link in att_links {
            let att_hash = match att_link.target.into_action_hash() {
                Some(h) => h,
                None => continue,
            };
            if let Some(record) = get(att_hash, GetOptions::network())? {
                if let Some(att) = record
                    .entry()
                    .to_app_option::<ValidationAttestation>()
                    .map_err(|e: holochain_serialized_bytes::SerializedBytesError| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
                {
                    if att.request_ref == request_ref {
                        attestations.push(record);
                    }
                }
            }
        }
    }
    Ok(attestations)
}

#[hdk_extern]
pub fn get_validators_for_discipline(
    discipline: Discipline,
) -> ExternResult<Vec<Record>> {
    let disc_path = Path::from(format!("validators.{}", discipline_tag(&discipline)))
        .typed(LinkTypes::ValidatorTierPath)?;
    let links = get_links(
        LinkQuery::try_new(disc_path.path_entry_hash()?, LinkTypes::ValidatorTierPath)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
}

/// Return all ValidatorProfile records for validators affiliated with an institution.
///
/// The InstitutionPath index is written by publish_validator_profile under
/// "institution.{institution}" paths. Used for conflict-of-interest detection
/// in validator assignment — prevents assigning validators from the same
/// institution as the researcher.
#[hdk_extern]
pub fn get_validators_for_institution(institution: String) -> ExternResult<Vec<Record>> {
    let inst_path = Path::from(format!("institution.{}", institution))
        .typed(LinkTypes::InstitutionPath)?;
    let links = get_links(
        LinkQuery::try_new(inst_path.path_entry_hash()?, LinkTypes::InstitutionPath)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
}

/// Return all ValidationAttestation records for a given discipline.
///
/// The DisciplinePath index is written by submit_attestation under
/// "attestations.{discipline_tag}" paths. Useful for cross-study analytics
/// — e.g. aggregate outcomes across all ComputationalBiology validations.
#[hdk_extern]
pub fn get_attestations_for_discipline(discipline: Discipline) -> ExternResult<Vec<Record>> {
    let disc_path = Path::from(format!("attestations.{}", discipline_tag(&discipline)))
        .typed(LinkTypes::DisciplinePath)?;
    let links = get_links(
        LinkQuery::try_new(disc_path.path_entry_hash()?, LinkTypes::DisciplinePath)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
}

/// Return all pending ValidationRequest records indexed under a discipline.
///
/// The StatusPath index is written by submit_validation_request using the path
/// "requests.pending.{discipline_tag}". This function queries that path.
#[hdk_extern]
pub fn get_pending_requests_for_discipline(
    discipline: Discipline,
) -> ExternResult<Vec<Record>> {
    let status_path = Path::from(format!(
        "requests.pending.{}",
        discipline_tag(&discipline)
    ))
    .typed(LinkTypes::StatusPath)?;
    let links = get_links(
        LinkQuery::try_new(status_path.path_entry_hash()?, LinkTypes::StatusPath)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
}

#[hdk_extern]
pub fn get_validator_profile(agent: AgentPubKey) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(agent, LinkTypes::AgentToProfile)?,
        GetStrategy::Network,
    )?;
    // max_by_key on the timestamp tag returns the most recently published
    // profile. Old links written without a tag return i64::MIN from
    // profile_link_ts() and always lose — backwards-compatible.
    match links.iter().max_by_key(|l| profile_link_ts(l)) {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest("Invalid link target".into())))?;
            get(target, GetOptions::network())
        }
        None => Ok(None),
    }
}

#[hdk_extern]
pub fn get_difficulty_assessment(
    request_ref: ExternalHash,
) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(request_ref, LinkTypes::DifficultyPath)?,
        GetStrategy::Network,
    )?;
    // Return the most recently created assessment (links are append-only;
    // last() gives the newest, consistent with get_current_phase behaviour).
    match links.last() {
        Some(link) => {
            let hash = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid DifficultyPath link target".into()
                )))?;
            get(hash, GetOptions::network())
        }
        None => Ok(None),
    }
}

// ---------------------------------------------------------------------------
// Protocol coordination — commit-reveal
// ---------------------------------------------------------------------------

/// Called by validator's Workspace DNA post_commit via call(OtherRole("attestation")).
/// NOT in Unrestricted cap grant — called under author grant.
///
/// Writes a `CommitmentAnchor` to the shared DHT containing only the
/// `commitment_hash` — the SHA-256 of the validator's serialised attestation
/// concatenated with a private nonce.  No assessment content leaves the
/// validator's device during this phase.
#[hdk_extern]
pub fn notify_commitment_sealed(
    input: CommitmentSealedInput,
) -> ExternResult<()> {
    let agent = agent_info()?.agent_initial_pubkey;
    let request_ref = input.request_ref.clone();

    // Guard 1: agent must hold a live StudyClaim for this study.
    // Prevents non-claimants from inflating the commitment count and
    // potentially triggering RevealOpen with phantom commitments.
    //
    // Dev/test bypass: skipped when authorized_joining_certificate_issuer is
    // empty (same pattern as the membrane-proof bypass).  In production the
    // issuer key is always set, so the check is always enforced.
    let guard1_props = DnaProperties::try_from_dna_properties()?;
    if !guard1_props.authorized_joining_certificate_issuer.is_empty() {
        let claim_links = get_links(
            LinkQuery::try_new(agent.clone(), LinkTypes::ValidatorToClaim)?,
            GetStrategy::Network,
        )?;
        let has_valid_claim = claim_links.into_iter().any(|link| {
            link.target
                .into_action_hash()
                .and_then(|h| get(h, GetOptions::network()).ok().flatten())
                .and_then(|r| r.entry().to_app_option::<StudyClaim>().ok().flatten())
                .map(|c| c.request_ref == request_ref)
                .unwrap_or(false)
        });
        if !has_valid_claim {
            return Err(wasm_error!(WasmErrorInner::Guest(
                "Validator does not hold a live claim for this study — \
                 call claim_study before sealing a commitment".into()
            )));
        }
    }

    // Guard 2: one commitment per validator per study.
    // Prevents a single validator from pushing multiple CommitmentAnchors
    // and skewing the quorum check that opens the reveal phase.
    let commit_path = Path::from(format!("commitments.{}", request_ref))
        .typed(LinkTypes::RequestToCommitment)?;
    commit_path.ensure()?;
    let commit_anchor = commit_path.path_entry_hash()?;
    let existing_links = get_links(
        LinkQuery::try_new(commit_anchor.clone(), LinkTypes::RequestToCommitment)?,
        GetStrategy::Network,
    )?;
    if existing_links.iter().any(|l| l.author == agent) {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Validator has already submitted a commitment for this study — \
             duplicate commitments are not permitted".into()
        )));
    }

    // Step 1: write CommitmentAnchor to shared DHT.
    let anchor = CommitmentAnchor {
        request_ref:     request_ref.clone(),
        validator:       agent,
        commitment_hash: input.commitment_hash,
    };
    let anchor_hash = create_entry(EntryTypes::CommitmentAnchor(anchor))?;

    create_link(commit_anchor, anchor_hash, LinkTypes::RequestToCommitment, ())?;

    // Step 2: check if all validators have now committed.
    if check_all_commitments_sealed_inner(request_ref.clone())? {
        let marker = PhaseMarker {
            request_ref: request_ref.clone(),
            phase:       ValidationPhase::RevealOpen,
        };
        let marker_hash = create_entry(EntryTypes::PhaseMarker(marker))?;

        let phase_path = Path::from(format!("phase.{}", request_ref))
            .typed(LinkTypes::RequestToPhaseMarker)?;
        phase_path.ensure()?;
        create_link(
            phase_path.path_entry_hash()?,
            marker_hash,
            LinkTypes::RequestToPhaseMarker,
            (),
        )?;

        // UI notification only — NOT a protocol gate.
        emit_signal(PhaseSignal {
            phase:       "RevealOpen".into(),
            request_ref: request_ref.clone(),
        })?;
    }

    Ok(())
}

/// Poll the current protocol phase for a request.
/// Returns None if no PhaseMarker exists yet (commit phase still in progress).
/// Engineering constraint #1: phase transitions are DHT-poll-driven.
#[hdk_extern]
pub fn get_current_phase(
    request_ref: ExternalHash,
) -> ExternResult<Option<ValidationPhase>> {
    let phase_path = Path::from(format!("phase.{}", request_ref))
        .typed(LinkTypes::RequestToPhaseMarker)?;
    let links = get_links(
        LinkQuery::try_new(
            phase_path.path_entry_hash()?,
            LinkTypes::RequestToPhaseMarker,
        )?,
        GetStrategy::Network,
    )?;
    match links.last() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid phase link target".into()
                )))?;
            let record = get(target, GetOptions::network())?
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "PhaseMarker record not found".into()
                )))?;
            let marker: PhaseMarker = record
                .entry()
                .to_app_option()
                .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Record is not a PhaseMarker".into()
                )))?;
            Ok(Some(marker.phase))
        }
        None => Ok(None),
    }
}

/// Publish the researcher's cryptographic commitment to their result.
///
/// Called by the researcher from their own Attestation cell (author grant —
/// no explicit capability grant required).  Must be called BEFORE the
/// validation round opens so validators cannot be influenced by the result.
///
/// Writes a `ResearcherResultCommitment` to the shared DHT containing only
/// `result_commitment_hash = SHA-256(result_data_bytes || nonce)`.  The actual
/// result stays in the researcher's local Researcher Repository DNA and is
/// only revealed (and verified against this hash) after all validators have
/// submitted their public reveals.
#[hdk_extern]
pub fn publish_researcher_commitment(
    input: ResearcherCommitmentInput,
) -> ExternResult<ActionHash> {
    // Idempotency guard: only one commitment may be published per study.
    // A second call would allow the researcher to change their locked prediction
    // after validators have already started work, breaking the commit-reveal
    // guarantee.
    let path = Path::from(format!("researcher_commitment.{}", input.request_ref))
        .typed(LinkTypes::RequestToResearcherCommitment)?;
    path.ensure()?;
    let path_anchor = path.path_entry_hash()?;
    let existing_links = get_links(
        LinkQuery::try_new(path_anchor.clone(), LinkTypes::RequestToResearcherCommitment)?,
        GetStrategy::Network,
    )?;
    if !existing_links.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "A researcher commitment already exists for this study — \
             the commitment cannot be replaced once published".into()
        )));
    }

    let commitment = ResearcherResultCommitment {
        request_ref:            input.request_ref.clone(),
        result_commitment_hash: input.result_commitment_hash,
    };
    let commitment_hash = create_entry(EntryTypes::ResearcherResultCommitment(commitment))?;

    // Index under a deterministic path so validators can retrieve the
    // commitment by request_ref without knowing the entry's ActionHash.
    create_link(path_anchor, commitment_hash.clone(), LinkTypes::RequestToResearcherCommitment, ())?;

    Ok(commitment_hash)
}

/// Return the researcher's committed result hash for a given request, if published.
///
/// Returns `None` if the researcher has not yet published their commitment —
/// validators can use this to guard the start of their work (the protocol
/// requires the researcher's commitment to precede any validation).
#[hdk_extern]
pub fn get_researcher_commitment(
    request_ref: ExternalHash,
) -> ExternResult<Option<Record>> {
    let path = Path::from(format!("researcher_commitment.{}", request_ref))
        .typed(LinkTypes::RequestToResearcherCommitment)?;
    let links = get_links(
        LinkQuery::try_new(
            path.path_entry_hash()?,
            LinkTypes::RequestToResearcherCommitment,
        )?,
        GetStrategy::Network,
    )?;
    match links.last() {
        Some(link) => {
            let hash = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid RequestToResearcherCommitment link target".into()
                )))?;
            get(hash, GetOptions::network())
        }
        None => Ok(None),
    }
}

/// Verify the researcher's commitment and publish their structured results.
///
/// Protocol gate: all validators must have committed before the researcher can
/// reveal.  This prevents the researcher from updating their stated expected
/// values after seeing validator behaviour.
///
/// Verification: `SHA-256(msgpack(metrics) || nonce) == result_commitment_hash`
/// If the hash does not match, the call fails with a Guest error — the reveal
/// is NOT written to the DHT.
///
/// Once written, `ResearcherReveal` is immutable (enforced by validate()).
/// Validators can then fetch the reveal via `get_researcher_reveal` and compare
/// the researcher's `metrics[i].produced_value` against their own
/// `MetricResult.produced_value` for the same metric names.
#[hdk_extern]
pub fn reveal_researcher_result(
    input: ResearcherRevealInput,
) -> ExternResult<ActionHash> {
    // Idempotency guard: only one reveal may be published per study.
    // A second call would create a duplicate ResearcherReveal entry and an
    // additional RequestToResearcherReveal link, making get_researcher_reveal
    // non-deterministic (links.last() is DHT-order-dependent under concurrent
    // propagation). The hash check below would still force content to match
    // the commitment, but bloating the link table is unnecessary and confusing.
    let reveal_path = Path::from(format!("researcher_reveal.{}", input.request_ref))
        .typed(LinkTypes::RequestToResearcherReveal)?;
    reveal_path.ensure()?;
    let reveal_anchor = reveal_path.path_entry_hash()?;
    let existing_reveal_links = get_links(
        LinkQuery::try_new(reveal_anchor.clone(), LinkTypes::RequestToResearcherReveal)?,
        GetStrategy::Network,
    )?;
    if !existing_reveal_links.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "A researcher reveal already exists for this study — \
             the reveal cannot be published more than once".into()
        )));
    }

    // Gate: all validators must have committed first.
    if !check_all_commitments_sealed_inner(input.request_ref.clone())? {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Cannot reveal — not all validators have committed yet".into()
        )));
    }

    // Fetch the previously published commitment.
    let commitment_record = get_researcher_commitment(input.request_ref.clone())?
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "No ResearcherResultCommitment found for this request — \
             publish_researcher_commitment must be called before reveal".into()
        )))?;
    let commitment: ResearcherResultCommitment = commitment_record
        .entry()
        .to_app_option()
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "Record is not a ResearcherResultCommitment".into()
        )))?;

    // Verify: SHA-256(msgpack(metrics) || nonce) == result_commitment_hash
    let msgpack_bytes: Vec<u8> = rmps::to_vec_named(&input.metrics)
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?;
    let mut hasher = Sha256::new();
    hasher.update(&msgpack_bytes);
    hasher.update(&input.nonce);
    let computed: Vec<u8> = hasher.finalize().to_vec();

    if computed != commitment.result_commitment_hash {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Hash mismatch — the provided metrics and nonce do not match \
             the previously published commitment".into()
        )));
    }

    // Write the verified reveal to the shared DHT.
    let reveal = ResearcherReveal {
        request_ref: input.request_ref.clone(),
        metrics:     input.metrics,
    };
    let reveal_hash = create_entry(EntryTypes::ResearcherReveal(reveal))?;

    create_link(reveal_anchor, reveal_hash.clone(), LinkTypes::RequestToResearcherReveal, ())?;

    Ok(reveal_hash)
}

/// Return the researcher's verified reveal for a given request, if published.
///
/// Returns `None` if the researcher has not yet called `reveal_researcher_result`.
/// The `ResearcherReveal.metrics` field contains the structured per-metric
/// results from the researcher's original run, verified against the hash
/// committed in `ResearcherResultCommitment`.
#[hdk_extern]
pub fn get_researcher_reveal(
    request_ref: ExternalHash,
) -> ExternResult<Option<Record>> {
    let path = Path::from(format!("researcher_reveal.{}", request_ref))
        .typed(LinkTypes::RequestToResearcherReveal)?;
    let links = get_links(
        LinkQuery::try_new(
            path.path_entry_hash()?,
            LinkTypes::RequestToResearcherReveal,
        )?,
        GetStrategy::Network,
    )?;
    match links.last() {
        Some(link) => {
            let hash = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid RequestToResearcherReveal link target".into()
                )))?;
            get(hash, GetOptions::network())
        }
        None => Ok(None),
    }
}

#[hdk_extern]
pub fn check_all_commitments_sealed(
    request_ref: ExternalHash,
) -> ExternResult<bool> {
    check_all_commitments_sealed_inner(request_ref)
}

fn check_all_commitments_sealed_inner(
    request_ref: ExternalHash,
) -> ExternResult<bool> {
    let commit_path = Path::from(format!("commitments.{}", request_ref))
        .typed(LinkTypes::RequestToCommitment)?;
    let commitment_links = get_links(
        LinkQuery::try_new(
            commit_path.path_entry_hash()?,
            LinkTypes::RequestToCommitment,
        )?,
        GetStrategy::Network,
    )?;
    // If the ValidationRequest has not propagated yet (or does not exist),
    // treat the phase as not-yet-sealed rather than propagating an error.
    // This is conservative: no PhaseMarker is written until the quorum can
    // be verified.  In production the VR always exists before validators commit.
    let required = match get_num_validators_required(request_ref) {
        Ok(n) => n,
        Err(_) => return Ok(false),
    };
    Ok(commitment_links.len() >= required as usize)
}

// ---------------------------------------------------------------------------
// Remote signal receiver
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn recv_remote_signal(signal: SerializedBytes) -> ExternResult<()> {
    emit_signal(signal)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// post_commit
// ---------------------------------------------------------------------------
//
// #[hdk_extern(infallible)] — must NOT return an error. All fallible work is
// delegated to post_commit_on_create() which returns ExternResult<()>, allowing
// use of `?`. Any failure is caught here and logged with debug!().

#[hdk_extern(infallible)]
pub fn post_commit(committed_actions: Vec<SignedActionHashed>) {
    for signed_action in committed_actions {
        if let Action::Create(_) = signed_action.action() {
            if let Err(e) =
                post_commit_on_create(signed_action.hashed.hash.clone())
            {
                debug!("post_commit: {}", e);
            }
        }
    }
}

/// Called for every Create action confirmed on this agent's source chain.
///
/// post_commit MUST NOT write data (Holochain constraint). Currently a no-op;
/// placeholder for future local signal emission on ValidationAttestation creates.
fn post_commit_on_create(_action_hash: ActionHash) -> ExternResult<()> {
    Ok(())
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Extract the creation timestamp from an AgentToProfile link tag.
///
/// Tags are written as 8 big-endian bytes of the `i64` microsecond timestamp
/// from `sys_time()` at `publish_validator_profile` time.  Old links (written
/// before this scheme) have empty or short tags and return `i64::MIN`, ensuring
/// they always sort below any tagged link — backwards-compatible.
fn profile_link_ts(link: &Link) -> i64 {
    let tag = link.tag.as_ref();
    if tag.len() >= 8 {
        if let Ok(bytes) = tag[..8].try_into() {
            return i64::from_be_bytes(bytes);
        }
    }
    i64::MIN
}

/// Fetch records for a list of links whose targets are ActionHashes.
/// Skips links with non-ActionHash targets and records that are not found.
fn records_for_links(links: Vec<Link>) -> ExternResult<Vec<Record>> {
    let mut records = Vec::new();
    for link in links {
        if let Some(hash) = link.target.into_action_hash() {
            if let Some(record) = get(hash, GetOptions::network())? {
                records.push(record);
            }
        }
    }
    Ok(records)
}

// ---------------------------------------------------------------------------
// Gaming and collusion detection
// ---------------------------------------------------------------------------

pub fn detect_gaming_patterns(
    _validator: AgentPubKey,
    _history: Vec<ValidationAttestation>,
) -> Vec<GamingFlag> {
    Vec::new()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GamingFlag {
    SuspiciousAgreementPattern { with_validator: AgentPubKey, agreement_rate: f64 },
    UnrealisticallyFast        { expected_min_secs: u64, actual_secs: u64 },
    RubberStamping             { approval_rate: f64, avg_time_secs: u64 },
    SocialProximity            { distance: u8, shared_publications: u32 },
    /// Validator is persistently the outlier across diverse studies — not
    /// necessarily bad faith, but warrants investigation and support.
    /// Response is quality assurance (investigate cause, help correct) rather
    /// than punitive unless deliberate manipulation is established.
    PersistentOutlier          { divergence_rate: f64, rounds_analysed: u32 },
}

// ---------------------------------------------------------------------------
// Validator assignment
// ---------------------------------------------------------------------------

pub struct AssignmentConstraints {
    pub max_institutional_share: f64,
    pub min_validators:          u8,
    pub require_domain_expert:   bool,
    pub double_blind:            bool,
}

pub fn select_validators(
    _request: &ValidationRequest,
    _available_profiles: Vec<ValidatorProfile>,
    _constraints: &AssignmentConstraints,
) -> ExternResult<Vec<AgentPubKey>> {
    Ok(Vec::new())
}

// ---------------------------------------------------------------------------
// Signal type
// ---------------------------------------------------------------------------

#[derive(Debug, Serialize, Deserialize)]
struct PhaseSignal {
    phase:       String,
    request_ref: ExternalHash,
}

// ---------------------------------------------------------------------------
// Agent identity linking — native multi-device identity
// ---------------------------------------------------------------------------
//
// Two agents (devices/keys) assert they share a logical identity by jointly
// signing a canonical payload.  Either agent can later revoke.
//
// Payload: the two raw AgentPubKey bytes (39 bytes each) concatenated in
// lexicographic order — giving a stable 78-byte byte string regardless of
// which agent calls first.
//
// Signature encoding: sign() serialises its payload through SerializedBytes
// (msgpack BIN format).  verify_signature() uses the same encoding.

/// Return the canonical 78-byte payload both agents must sign:
/// the two raw 39-byte pubkeys concatenated in lexicographic order.
fn sorted_agent_pair_bytes(a: &AgentPubKey, b: &AgentPubKey) -> Vec<u8> {
    let raw_a = a.get_raw_39();
    let raw_b = b.get_raw_39();
    if raw_a <= raw_b {
        [raw_a, raw_b].concat()
    } else {
        [raw_b, raw_a].concat()
    }
}

/// Input for link_agent_identity.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkAgentIdentityInput {
    /// The other agent to link with.
    pub other_agent:  AgentPubKey,
    /// Caller's signature over `sorted_agent_pair_bytes(caller, other_agent)`.
    pub my_signature: Signature,
    /// Other agent's signature over the same payload.
    pub other_signature: Signature,
}

/// Commit an AgentIdentityAttestation joining `caller` and `other_agent`,
/// then write symmetric AgentToIdentityAttestation links from both pubkeys.
///
/// Both signatures are verified before anything is written to the DHT.
/// Returns the ActionHash of the new entry.
#[hdk_extern]
pub fn link_agent_identity(input: LinkAgentIdentityInput) -> ExternResult<ActionHash> {
    let caller = agent_info()?.agent_initial_pubkey;

    if caller == input.other_agent {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Cannot link an agent to itself".into(),
        )));
    }

    let payload = sorted_agent_pair_bytes(&caller, &input.other_agent);

    // Verify caller's own signature.
    let caller_ok = verify_signature(
        caller.clone(),
        input.my_signature.clone(),
        payload.clone(),
    )?;
    if !caller_ok {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "my_signature failed verification".into(),
        )));
    }

    // Verify other agent's signature.
    let other_ok = verify_signature(
        input.other_agent.clone(),
        input.other_signature.clone(),
        payload.clone(),
    )?;
    if !other_ok {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "other_signature failed verification".into(),
        )));
    }

    // Build canonical entry (agent_a = lex-smaller key).
    let raw_caller = caller.get_raw_39();
    let raw_other  = input.other_agent.get_raw_39();
    let (agent_a, signature_a, agent_b, signature_b) = if raw_caller <= raw_other {
        (caller.clone(), input.my_signature, input.other_agent.clone(), input.other_signature)
    } else {
        (input.other_agent.clone(), input.other_signature, caller.clone(), input.my_signature)
    };

    let att = AgentIdentityAttestation { agent_a, signature_a, agent_b, signature_b };
    let hash = create_entry(EntryTypes::AgentIdentityAttestation(att.clone()))?;

    // Symmetric links so either agent can look up the attestation.
    create_link(
        att.agent_a.clone(),
        hash.clone(),
        LinkTypes::AgentToIdentityAttestation,
        (),
    )?;
    create_link(
        att.agent_b.clone(),
        hash.clone(),
        LinkTypes::AgentToIdentityAttestation,
        (),
    )?;

    Ok(hash)
}

/// Return all live AgentIdentityAttestation records for the calling agent.
///
/// Only entries whose DHT details show no delete actions are returned —
/// this filters out revoked attestations without relying on link deletion.
#[hdk_extern]
pub fn get_linked_agents(_: ()) -> ExternResult<Vec<Record>> {
    let agent = agent_info()?.agent_initial_pubkey;
    let links = get_links(
        LinkQuery::try_new(agent, LinkTypes::AgentToIdentityAttestation)?,
        GetStrategy::Network,
    )?;

    let mut results = Vec::new();
    for link in links {
        let hash = match link.target.into_action_hash() {
            Some(h) => h,
            None => continue,
        };
        // Use get_details to distinguish live from deleted entries.
        match get_details(hash, GetOptions::network())? {
            Some(Details::Record(rd)) if rd.deletes.is_empty() => {
                results.push(rd.record);
            }
            _ => {}
        }
    }
    Ok(results)
}

/// Revoke an AgentIdentityAttestation by deleting its entry.
///
/// Only one of the two named agents may call this.  The coordinator enforces
/// that the caller is the agent identified by `agent_info()`; the integrity
/// zome's delete validation confirms the deleter is agent_a or agent_b.
#[hdk_extern]
pub fn revoke_agent_identity_link(attestation_hash: ActionHash) -> ExternResult<ActionHash> {
    let caller = agent_info()?.agent_initial_pubkey;

    let record = get(attestation_hash.clone(), GetOptions::network())?
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "AgentIdentityAttestation not found".into(),
        )))?;

    let att: AgentIdentityAttestation = record
        .entry()
        .to_app_option()
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "Record is not an AgentIdentityAttestation".into(),
        )))?;

    if caller != att.agent_a && caller != att.agent_b {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Only one of the two named agents may revoke this attestation".into(),
        )));
    }

    delete_entry(attestation_hash)
}

/// Sign the canonical payload for a prospective identity link with `other_agent`.
///
/// Used by tests so each agent can produce its half of the ceremony without
/// both conductors needing to be in the same process.  Production UIs should
/// call `sign()` directly via the app-call API.
#[hdk_extern]
pub fn sign_for_identity_link(other_agent: AgentPubKey) -> ExternResult<Signature> {
    let caller = agent_info()?.agent_initial_pubkey;
    let payload = sorted_agent_pair_bytes(&caller, &other_agent);
    sign(caller, payload)
}

// Note: getrandom 0.3 custom backend for wasm32-unknown-unknown is enabled
// via .cargo/config.toml (--cfg getrandom_backend="custom"). The required
// __getrandom_v03_custom stub is provided by hdk itself.
