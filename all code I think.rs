use hdk::prelude::*;
use attestation_integrity::{
    AssessmentConfidence, CommitmentAnchor, CommitmentSealedInput, DifficultyAssessment,
    DifficultyTier, DnaProperties, EntryTypes, LinkTypes, PhaseMarker,
    ResearcherCommitmentInput, ResearcherResultCommitment, ResearcherReveal, ResearcherRevealInput,
    StudyClaim, ValidatorProfile, ValidationRequest,
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
    // verify_signature serialises data via rmp_serde, which encodes Vec<u8> as
    // a msgpack array of unsigned integers. The JS test must match by signing
    // encode(Array.from(agentPubKey)) rather than the raw Uint8Array.
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
    let request_hash = create_entry(EntryTypes::ValidationRequest(request.clone()))?;

    // Index by study data hash for discovery.
    let study_path = Path::from(format!("study.{}", request.data_hash))
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

/// Submit a public attestation — THE REVEAL PHASE.
/// IMMUTABLE after write.
///
/// After writing the attestation this function attempts to finalise the
/// validation round by calling check_and_create_harmony_record on the
/// Governance DNA.  The call is fire-and-forget: if the round is not yet
/// complete (fewer attestations than num_validators_required) the governance
/// function returns null silently.  If the round is complete, any validator
/// who submits last triggers the HarmonyRecord write — no designated
/// coordinator node required.
#[hdk_extern]
pub fn submit_attestation(
    attestation: ValidationAttestation,
) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_initial_pubkey;
    let disc_tag = attestation.discipline_tag();
    let request_ref = attestation.request_ref.clone();
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

    // Attempt to finalise the round.  The governance coordinator's idempotency
    // guard ensures at most one HarmonyRecord is written even if multiple
    // validators trigger this simultaneously.  Errors are swallowed — a failed
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
    create_link(agent, profile_hash.clone(), LinkTypes::AgentToProfile, ())?;

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

#[hdk_extern]
pub fn assess_difficulty(
    request_ref: ExternalHash,
) -> ExternResult<ActionHash> {
    let link_base = request_ref.clone();
    let assessment = DifficultyAssessment {
        request_ref,
        code_volume:            3,
        dependency_count:       3,
        documentation_quality:  3,
        data_accessibility:     3,
        environment_complexity: 3,
        study_age_years:        2,
        predicted_tier:         DifficultyTier::Moderate,
        predicted_min_secs:     28_800,
        predicted_max_secs:     57_600,
        confidence:             AssessmentConfidence::Low,
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

    // Capacity check: count existing live claims for this request.
    let existing_claims = get_claims_for_request(request_ref.clone())?;
    if existing_claims.len() >= vr.num_validators_required as usize {
        return Err(wasm_error!(WasmErrorInner::Guest(format!(
            "Study is at capacity ({}/{} validators already claimed)",
            existing_claims.len(),
            vr.num_validators_required,
        ))));
    }

    // Duplicate check: has this agent already claimed this study?
    let existing_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    if existing_links.iter().any(|l| l.author == agent) {
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
            .last()
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

/// Return all studies this validator has claimed (live ValidatorToClaim links).
#[hdk_extern]
pub fn get_my_claimed_studies(_: ()) -> ExternResult<Vec<Record>> {
    let agent = agent_info()?.agent_initial_pubkey;
    let links = get_links(
        LinkQuery::try_new(agent, LinkTypes::ValidatorToClaim)?,
        GetStrategy::Network,
    )?;
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
    if elapsed_secs < input.timeout_secs as i64 {
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

#[hdk_extern]
pub fn get_validator_profile(agent: AgentPubKey) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(agent, LinkTypes::AgentToProfile)?,
        GetStrategy::Network,
    )?;
    match links.first() {
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

    // Guard 2: one commitment per validator per study.
    // Prevents a single validator from pushing multiple CommitmentAnchors
    // and skewing the quorum check that opens the reveal phase.
    let commit_path = Path::from(format!("commitments.{}", request_ref))
        .typed(LinkTypes::RequestToCommitment)?;
    commit_path.ensure()?;
    let existing_links = get_links(
        LinkQuery::try_new(
            commit_path.path_entry_hash()?,
            LinkTypes::RequestToCommitment,
        )?,
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

    create_link(
        commit_path.path_entry_hash()?,
        anchor_hash,
        LinkTypes::RequestToCommitment,
        (),
    )?;

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
    let commitment = ResearcherResultCommitment {
        request_ref:            input.request_ref.clone(),
        result_commitment_hash: input.result_commitment_hash,
    };
    let commitment_hash = create_entry(EntryTypes::ResearcherResultCommitment(commitment))?;

    // Index under a deterministic path so validators can retrieve the
    // commitment by request_ref without knowing the entry's ActionHash.
    let path = Path::from(format!("researcher_commitment.{}", input.request_ref))
        .typed(LinkTypes::RequestToResearcherCommitment)?;
    path.ensure()?;
    create_link(
        path.path_entry_hash()?,
        commitment_hash.clone(),
        LinkTypes::RequestToResearcherCommitment,
        (),
    )?;

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

    let path = Path::from(format!("researcher_reveal.{}", input.request_ref))
        .typed(LinkTypes::RequestToResearcherReveal)?;
    path.ensure()?;
    create_link(
        path.path_entry_hash()?,
        reveal_hash.clone(),
        LinkTypes::RequestToResearcherReveal,
        (),
    )?;

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
    let required = get_num_validators_required(request_ref)?;
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
/// post_commit MUST NOT write data (Holochain constraint). The governance
/// DNA's check_and_create_harmony_record is called explicitly by the
/// assembly coordinator after all attestations are confirmed — never from
/// here. A cross-DNA write from post_commit creates a per-cell re-entry
/// deadlock: attestation post_commit → governance → attestation.get_attestations_for_request
/// → blocked waiting for attestation to finish post_commit.
///
/// This function is intentionally a no-op: it validates that the committed
/// action is a ValidationAttestation (for future signal emission) and returns.
fn post_commit_on_create(action_hash: ActionHash) -> ExternResult<()> {
    // Retrieve the full record from local storage (it was just written —
    // no network hop needed).
    let record = match get(action_hash, GetOptions::local())? {
        Some(r) => r,
        None => return Ok(()),
    };

    // Confirm the entry is a ValidationAttestation. Any other entry type
    // (ValidatorProfile, CommitmentAnchor, PhaseMarker, etc.) is silently
    // skipped. Future: emit a local UI signal here if desired.
    let _attestation: ValidationAttestation =
        match record
            .entry()
            .to_app_option()
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
        {
            Some(a) => a,
            None => return Ok(()),
        };

    Ok(())
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

// Note: getrandom 0.3 custom backend for wasm32-unknown-unknown is enabled
// via .cargo/config.toml (--cfg getrandom_backend="custom"). The required
// __getrandom_v03_custom stub is provided by hdk itself.

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

        // --- Membrane proof — format check (after network join) ---
        //
        // The integrity zome can only run the format check here because
        // `verify_signature` is an HDK host function that is NOT available in
        // HDI integrity zomes. The full Ed25519 signature verification against the
        // DNA-properties issuer key runs in the coordinator's `init()` callback,
        // which fails the cell if the proof is invalid and prevents any subsequent
        // writes. An agent with a forged proof can join the DHT (their genesis
        // actions pass format validation) but cannot write any protocol data
        // because init() never succeeds.
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
use hdk::prelude::*;
use std::collections::HashSet;
use governance_integrity::{
    BadgeType, DnaProperties, EntryTypes, GovernanceDecision, HarmonyRecord, LinkTypes,
    ReproducibilityBadge, ValidatorReputation,
};
use valichord_shared_types::{AgreementLevel, AttestationOutcome, CertificationTier, Discipline, ValidationAttestation, discipline_tag};

// ---------------------------------------------------------------------------
// init() — capability grants for public read functions
// ---------------------------------------------------------------------------
//
// ALL read functions are unrestricted — this DNA is the HTTP Gateway target.
// Write functions are NOT listed here; they are validated by validate() author
// checks (harmony_record_creator_key / system_coordinator_key). Only the
// authorised conductor may successfully call them.

#[hdk_extern]
pub fn init(_: ()) -> ExternResult<InitCallbackResult> {
    let zome = zome_info()?.name;
    let mut public_fns: HashSet<GrantedFunction> = HashSet::new();
    // force_finalize_round is intentionally NOT listed here — it is a write
    // function (creates a HarmonyRecord) and must not be callable by anonymous
    // HTTP Gateway clients.  Participants call it via the author grant from
    // their own conductor (same-agent cross-DNA call from the attestation cell).
    for fn_name in &[
        "get_harmony_record",
        "get_harmony_records_by_discipline",
        "get_validator_reputation",
        "get_badges_for_study",
        "get_badges_by_type",
        "get_all_governance_decisions",
    ] {
        public_fns.insert((zome.clone(), FunctionName::from(*fn_name)));
    }
    create_cap_grant(ZomeCallCapGrant {
        tag: "public-read".into(),
        access: CapAccess::Unrestricted,
        functions: GrantedFunctions::Listed(public_fns),
    })?;
    Ok(InitCallbackResult::Pass)
}

// ---------------------------------------------------------------------------
// Input structs
// ---------------------------------------------------------------------------

/// Input for update_validator_reputation — the coordinator derives all other
/// fields from existing reputation records + this delta.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReputationUpdateInput {
    pub validator:           AgentPubKey,
    pub discipline:          Discipline,
    pub outcome:             AttestationOutcome,
    pub time_invested_secs:  u64,
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

/// After this many seconds a stuck round is eligible for force-finalisation.
/// Default: 7 days. Override by calling force_finalize_round on a test network
/// with a shorter-lived ValidationRequest.
const ROUND_TIMEOUT_SECS: i64 = 7 * 24 * 3600;

/// Idempotent — called automatically from DNA 3 submit_attestation.
///
/// Algorithm:
///   1. Short-circuit if a HarmonyRecord already exists.
///   2. Fetch attestations from DNA 3.
///   3. Require ≥ num_validators_required attestations (completeness gate).
///   4-7. Delegate to write_harmony_record.
#[hdk_extern]
pub fn check_and_create_harmony_record(
    request_ref: ExternalHash,
) -> ExternResult<Option<ActionHash>> {
    // 1. Idempotency.
    let anchor_key = anchor_for_request(&request_ref)?;
    let existing = get_links(
        LinkQuery::try_new(anchor_key, LinkTypes::RequestToHarmonyRecord)?,
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Ok(None);
    }

    // 2. Fetch attestations from DNA 3.
    let response = call(
        CallTargetCell::OtherRole("attestation".into()),
        ZomeName::from("attestation_coordinator"),
        FunctionName::from("get_attestations_for_request"),
        None,
        request_ref.clone(),
    )?;
    let attestation_records: Vec<Record> = match response {
        ZomeCallResponse::Ok(extern_io) => extern_io
            .decode()
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?,
        _ => return Ok(None),
    };
    if attestation_records.is_empty() {
        return Ok(None);
    }

    // 3. Completeness gate: require all expected attestations before writing.
    // If the quorum count cannot be determined (ValidationRequest not found or
    // cross-DNA call fails), return None conservatively — do NOT default to 1,
    // as that would allow a single attestation to finalise any study.
    let min_validators: u8 = {
        let resp = call(
            CallTargetCell::OtherRole("attestation".into()),
            ZomeName::from("attestation_coordinator"),
            FunctionName::from("get_num_validators_required"),
            None,
            request_ref.clone(),
        )?;
        match resp {
            ZomeCallResponse::Ok(extern_io) => match extern_io.decode::<u8>() {
                Ok(n) => n,
                Err(_) => return Ok(None), // Cannot decode quorum — abort conservatively.
            },
            _ => return Ok(None), // Call failed — abort conservatively.
        }
    };
    if (attestation_records.len() as u8) < min_validators {
        return Ok(None);
    }

    // 4-7. Assemble and write.
    let hash = write_harmony_record(request_ref, attestation_records)?;
    Ok(Some(hash))
}

/// Force-finalise a stuck round after ROUND_TIMEOUT_SECS have elapsed.
///
/// Called by any participant (researcher, validator, or operator) when a round
/// is stuck because a validator claimed a study and then went dark.  The absent
/// validator's slot should first be freed via `reclaim_abandoned_claim` in DNA 3
/// so a replacement can be found; if no replacement arrives before the timeout,
/// this function closes the round with whatever attestations are present.
///
/// Requires:
///   - No HarmonyRecord already exists (idempotency).
///   - At least one attestation has been submitted.
///   - The ValidationRequest was created ≥ ROUND_TIMEOUT_SECS ago.
///
/// The resulting HarmonyRecord is identical in structure to one created by the
/// normal path. Readers can identify reduced-quorum completion by comparing
/// `participating_validators.len()` against the study's `num_validators_required`.
///
/// Returns None if the conditions above are not met.
#[hdk_extern]
pub fn force_finalize_round(
    request_ref: ExternalHash,
) -> ExternResult<Option<ActionHash>> {
    // 1. Idempotency.
    let anchor_key = anchor_for_request(&request_ref)?;
    let existing = get_links(
        LinkQuery::try_new(anchor_key, LinkTypes::RequestToHarmonyRecord)?,
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Ok(None);
    }

    // 2. Fetch attestations and apply min_attestations_for_finalization threshold.
    let response = call(
        CallTargetCell::OtherRole("attestation".into()),
        ZomeName::from("attestation_coordinator"),
        FunctionName::from("get_attestations_for_request"),
        None,
        request_ref.clone(),
    )?;
    let attestation_records: Vec<Record> = match response {
        ZomeCallResponse::Ok(extern_io) => extern_io
            .decode()
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?,
        _ => return Ok(None),
    };
    if attestation_records.is_empty() {
        return Ok(None);
    }
    let props = DnaProperties::try_from_dna_properties()?;
    let min_required = if props.min_attestations_for_finalization == 0 {
        1u32
    } else {
        props.min_attestations_for_finalization
    };
    if (attestation_records.len() as u32) < min_required {
        return Ok(None);
    }

    // 3. Check round age via the ValidationRequest's action timestamp.
    let vr_response = call(
        CallTargetCell::OtherRole("attestation".into()),
        ZomeName::from("attestation_coordinator"),
        FunctionName::from("get_validation_request_for_data_hash"),
        None,
        request_ref.clone(),
    )?;
    if let ZomeCallResponse::Ok(extern_io) = vr_response {
        let maybe_vr: Option<Record> = extern_io.decode().unwrap_or(None);
        if let Some(vr) = maybe_vr {
            let now = sys_time()?;
            let vr_time = vr.action().timestamp();
            let elapsed_secs = (now.0 - vr_time.0) / 1_000_000;
            if elapsed_secs < ROUND_TIMEOUT_SECS {
                return Ok(None); // Round has not timed out yet.
            }
        }
    }

    // 4-7. Assemble and write with whatever attestations are present.
    let hash = write_harmony_record(request_ref, attestation_records)?;
    Ok(Some(hash))
}

/// Core assembly: derive fields, write HarmonyRecord + links, issue badge,
/// update reputations.  Called by both check_and_create_harmony_record
/// (full quorum) and force_finalize_round (reduced quorum after timeout).
fn write_harmony_record(
    request_ref: ExternalHash,
    attestation_records: Vec<Record>,
) -> ExternResult<ActionHash> {
    // Derive structured attestation payloads.
    let attestations: Vec<ValidationAttestation> = attestation_records
        .iter()
        .filter_map(|r| {
            r.entry()
                .to_app_option::<ValidationAttestation>()
                .ok()
                .flatten()
        })
        .collect();

    let participating_validators: Vec<AgentPubKey> = attestation_records
        .iter()
        .map(|r| r.action().author().clone())
        .collect();

    let outcome             = derive_majority_outcome(&attestations);
    let agreement_level     = derive_agreement_level(&attestations);
    let validation_duration_secs = attestations
        .iter()
        .map(|a| a.time_invested_secs)
        .max()
        .unwrap_or(0);
    let discipline = attestations
        .first()
        .map(|a| a.discipline.clone())
        .unwrap_or(Discipline::Other("unknown".into()));

    // Write HarmonyRecord entry and indexes.
    let anchor_key = anchor_for_request(&request_ref)?;
    let record = HarmonyRecord {
        request_ref: request_ref.clone(),
        outcome,
        agreement_level: agreement_level.clone(),
        participating_validators: participating_validators.clone(),
        validation_duration_secs,
        discipline: discipline.clone(),
    };
    let record_hash = create_entry(EntryTypes::HarmonyRecord(record))?;

    create_link(anchor_key, record_hash.clone(), LinkTypes::RequestToHarmonyRecord, ())?;
    let disc_anchor = discipline_anchor(&discipline)?;
    create_link(disc_anchor, record_hash.clone(), LinkTypes::DisciplinePath, ())?;

    // Optionally issue badge.
    if let Some(badge_type) = evaluate_badge(&agreement_level, participating_validators.len()) {
        let issued_to = {
            let resp = call(
                CallTargetCell::OtherRole("attestation".into()),
                ZomeName::from("attestation_coordinator"),
                FunctionName::from("get_validation_request_for_data_hash"),
                None,
                request_ref.clone(),
            );
            match resp {
                Ok(ZomeCallResponse::Ok(extern_io)) => {
                    let maybe_record: Option<Record> = extern_io.decode().unwrap_or(None);
                    maybe_record
                        .map(|r| r.action().author().clone())
                        .unwrap_or_else(|| participating_validators
                            .first()
                            .cloned()
                            .unwrap_or_else(|| agent_info().map(|i| i.agent_initial_pubkey).unwrap()))
                }
                _ => participating_validators
                    .first()
                    .cloned()
                    .unwrap_or_else(|| agent_info().map(|i| i.agent_initial_pubkey).unwrap()),
            }
        };
        let type_anchor = badge_type_anchor(&badge_type)?;
        let badge = ReproducibilityBadge {
            study_ref:           request_ref.clone(),
            issued_to,
            badge_type,
            harmony_record_ref:  record_hash.clone(),
        };
        let badge_hash = create_entry(EntryTypes::ReproducibilityBadge(badge))?;
        create_link(request_ref.clone(), badge_hash.clone(), LinkTypes::StudyToBadge, ())?;
        create_link(type_anchor, badge_hash, LinkTypes::BadgePath, ())?;
    }

    // Update validator reputations.
    for (record, attestation) in attestation_records.iter().zip(attestations.iter()) {
        let _ = _update_reputation_internal(
            record.action().author().clone(),
            attestation.discipline.clone(),
            attestation.outcome.clone(),
            attestation.time_invested_secs,
        );
    }

    Ok(record_hash)
}

/// Record a governance vote outcome on-chain.
///
/// Only the harmony_record_creator_key agent may write GovernanceDecision
/// entries — validate() enforces the authorship check.  The entry is
/// immutable after creation (validate() blocks updates and deletes).
#[hdk_extern]
pub fn create_governance_decision(
    input: GovernanceDecision,
) -> ExternResult<ActionHash> {
    let hash = create_entry(EntryTypes::GovernanceDecision(input))?;
    // Index under a global anchor for bulk retrieval.
    let anchor = decisions_anchor()?;
    create_link(anchor, hash.clone(), LinkTypes::AllDecisions, ())?;
    Ok(hash)
}

/// Update a validator's reputation record.
///
/// Only the system_coordinator_key agent may call this successfully — the
/// validate() callback enforces the authorship check on-chain.
#[hdk_extern]
pub fn update_validator_reputation(
    input: ReputationUpdateInput,
) -> ExternResult<ActionHash> {
    _update_reputation_internal(
        input.validator,
        input.discipline,
        input.outcome,
        input.time_invested_secs,
    )
}

// ---------------------------------------------------------------------------
// Read functions (unrestricted — HTTP Gateway targets)
// ---------------------------------------------------------------------------

/// Look up the HarmonyRecord for a given ValidationRequest.
#[hdk_extern]
pub fn get_harmony_record(
    request_ref: ExternalHash,
) -> ExternResult<Option<Record>> {
    let anchor = anchor_for_request(&request_ref)?;
    let links = get_links(
        LinkQuery::try_new(anchor, LinkTypes::RequestToHarmonyRecord)?,
        GetStrategy::Network,
    )?;
    match links.first() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid RequestToHarmonyRecord link target".into()
                )))?;
            get(target, GetOptions::network())
        }
        None => Ok(None),
    }
}

/// Return all HarmonyRecords indexed under a discipline path.
#[hdk_extern]
pub fn get_harmony_records_by_discipline(
    discipline: Discipline,
) -> ExternResult<Vec<Record>> {
    let anchor = discipline_anchor(&discipline)?;
    let links = get_links(
        LinkQuery::try_new(anchor, LinkTypes::DisciplinePath)?,
        GetStrategy::Network,
    )?;
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

/// Return the most recent ValidatorReputation record for a given validator.
#[hdk_extern]
pub fn get_validator_reputation(
    validator: AgentPubKey,
) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(validator, LinkTypes::ValidatorToReputation)?,
        GetStrategy::Network,
    )?;
    match links.last() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid ValidatorToReputation link target".into()
                )))?;
            get(target, GetOptions::network())
        }
        None => Ok(None),
    }
}

/// Return all ReproducibilityBadge records of a given type across all studies.
///
/// Uses the BadgePath index (written by check_and_create_harmony_record).
/// Useful for analytics: "how many Gold badges have been issued globally?".
#[hdk_extern]
pub fn get_badges_by_type(badge_type: BadgeType) -> ExternResult<Vec<Record>> {
    let anchor = badge_type_anchor(&badge_type)?;
    let links = get_links(
        LinkQuery::try_new(anchor, LinkTypes::BadgePath)?,
        GetStrategy::Network,
    )?;
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

/// Return all GovernanceDecision records (insertion order).
#[hdk_extern]
pub fn get_all_governance_decisions(_: ()) -> ExternResult<Vec<Record>> {
    let anchor = decisions_anchor()?;
    let links = get_links(
        LinkQuery::try_new(anchor, LinkTypes::AllDecisions)?,
        GetStrategy::Network,
    )?;
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

/// Return all badges linked from a study_ref.
#[hdk_extern]
pub fn get_badges_for_study(
    study_ref: ExternalHash,
) -> ExternResult<Vec<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_ref, LinkTypes::StudyToBadge)?,
        GetStrategy::Network,
    )?;
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
// Internal helpers
// ---------------------------------------------------------------------------

/// Compute the DHT anchor entry hash for a given request_ref.
///
/// Path format: "request.{hex_encoded_core_32_bytes}"
fn anchor_for_request(request_ref: &ExternalHash) -> ExternResult<EntryHash> {
    let hex: String = request_ref
        .get_raw_32()
        .iter()
        .map(|b| format!("{:02x}", b))
        .collect();
    let path = Path::from(format!("request.{}", hex))
        .typed(LinkTypes::RequestToHarmonyRecord)?;
    path.ensure()?;
    path.path_entry_hash()
}

/// Compute the DHT anchor entry hash for a badge-type path.
fn badge_type_anchor(badge_type: &BadgeType) -> ExternResult<EntryHash> {
    let tag = match badge_type {
        BadgeType::GoldReproducible   => "gold",
        BadgeType::SilverReproducible => "silver",
        BadgeType::BronzeReproducible => "bronze",
        BadgeType::FailedReproduction => "failed",
    };
    let path = Path::from(format!("badge.{}", tag)).typed(LinkTypes::BadgePath)?;
    path.ensure()?;
    path.path_entry_hash()
}

/// Compute the DHT anchor entry hash for the global decisions index.
fn decisions_anchor() -> ExternResult<EntryHash> {
    let path = Path::from("decisions.all").typed(LinkTypes::AllDecisions)?;
    path.ensure()?;
    path.path_entry_hash()
}

/// Compute the DHT anchor entry hash for a discipline path.
fn discipline_anchor(discipline: &Discipline) -> ExternResult<EntryHash> {
    let path = Path::from(format!("harmony.{}", discipline_tag(discipline)))
        .typed(LinkTypes::DisciplinePath)?;
    path.ensure()?;
    path.path_entry_hash()
}

/// Plurality-vote majority outcome across attestations.
fn derive_majority_outcome(attestations: &[ValidationAttestation]) -> AttestationOutcome {
    let (mut reproduced, mut partial, mut failed, mut unable) = (0u32, 0u32, 0u32, 0u32);
    for a in attestations {
        match &a.outcome {
            AttestationOutcome::Reproduced => reproduced += 1,
            AttestationOutcome::PartiallyReproduced { .. } => partial += 1,
            AttestationOutcome::FailedToReproduce { .. } => failed += 1,
            AttestationOutcome::UnableToAssess { .. } => unable += 1,
        }
    }
    let max = reproduced.max(partial).max(failed).max(unable);
    if reproduced == max {
        AttestationOutcome::Reproduced
    } else if partial == max {
        AttestationOutcome::PartiallyReproduced {
            details: "Majority partially reproduced".into(),
        }
    } else if failed == max {
        AttestationOutcome::FailedToReproduce {
            details: "Majority failed to reproduce".into(),
        }
    } else {
        AttestationOutcome::UnableToAssess {
            reason: "Majority unable to assess".into(),
        }
    }
}

/// Derive AgreementLevel from the success rate of the attestation set.
fn derive_agreement_level(attestations: &[ValidationAttestation]) -> AgreementLevel {
    if attestations.is_empty() {
        return AgreementLevel::UnableToAssess;
    }
    let successes = attestations
        .iter()
        .filter(|a| {
            matches!(
                &a.outcome,
                AttestationOutcome::Reproduced | AttestationOutcome::PartiallyReproduced { .. }
            )
        })
        .count();
    let rate = successes as f64 / attestations.len() as f64;
    if rate >= 0.90 {
        AgreementLevel::ExactMatch
    } else if rate >= 0.70 {
        AgreementLevel::WithinTolerance
    } else if rate >= 0.50 {
        AgreementLevel::DirectionalMatch
    } else if successes > 0 {
        AgreementLevel::Divergent
    } else {
        AgreementLevel::UnableToAssess
    }
}

/// Return a BadgeType if the validator count and agreement level meet thresholds.
fn evaluate_badge(
    agreement: &AgreementLevel,
    validator_count: usize,
) -> Option<BadgeType> {
    match agreement {
        AgreementLevel::ExactMatch if validator_count >= 7 => {
            Some(BadgeType::GoldReproducible)
        }
        AgreementLevel::ExactMatch | AgreementLevel::WithinTolerance
            if validator_count >= 5 =>
        {
            Some(BadgeType::SilverReproducible)
        }
        AgreementLevel::ExactMatch
        | AgreementLevel::WithinTolerance
        | AgreementLevel::DirectionalMatch
            if validator_count >= 3 =>
        {
            Some(BadgeType::BronzeReproducible)
        }
        AgreementLevel::Divergent | AgreementLevel::UnableToAssess => {
            Some(BadgeType::FailedReproduction)
        }
        _ => None,
    }
}

/// Internal reputation update — creates a new ValidatorReputation entry that
/// supersedes the previous one (links accumulate; latest = most recent).
fn _update_reputation_internal(
    validator: AgentPubKey,
    discipline: Discipline,
    outcome: AttestationOutcome,
    time_invested_secs: u64,
) -> ExternResult<ActionHash> {
    // Fetch existing reputation if any.
    let links = get_links(
        LinkQuery::try_new(validator.clone(), LinkTypes::ValidatorToReputation)?,
        GetStrategy::Network,
    )?;

    let (total_validations, agreement_rate, avg_time_secs, tier) =
        if let Some(link) = links.last() {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid ValidatorToReputation link target".into()
                )))?;
            if let Some(record) = get(target, GetOptions::network())? {
                if let Some(existing) = record
                    .entry()
                    .to_app_option::<ValidatorReputation>()
                    .ok()
                    .flatten()
                {
                    let new_total = existing.total_validations + 1;
                    let prev_successes =
                        (existing.agreement_rate * existing.total_validations as f64) as u32;
                    let is_success = matches!(
                        &outcome,
                        AttestationOutcome::Reproduced
                            | AttestationOutcome::PartiallyReproduced { .. }
                    );
                    let new_successes = prev_successes + if is_success { 1 } else { 0 };
                    let new_rate = new_successes as f64 / new_total as f64;
                    let new_avg = (existing.avg_time_secs * existing.total_validations as u64
                        + time_invested_secs)
                        / new_total as u64;
                    let new_tier = cert_tier(new_total, new_rate);
                    (new_total, new_rate, new_avg, new_tier)
                } else {
                    (1, initial_rate(&outcome), time_invested_secs, CertificationTier::Provisional)
                }
            } else {
                (1, initial_rate(&outcome), time_invested_secs, CertificationTier::Provisional)
            }
        } else {
            (1, initial_rate(&outcome), time_invested_secs, CertificationTier::Provisional)
        };

    let rep = ValidatorReputation {
        validator: validator.clone(),
        discipline,
        total_validations,
        agreement_rate,
        avg_time_secs,
        tier,
    };
    let rep_hash = create_entry(EntryTypes::ValidatorReputation(rep))?;
    create_link(
        validator,
        rep_hash.clone(),
        LinkTypes::ValidatorToReputation,
        (),
    )?;
    Ok(rep_hash)
}

fn initial_rate(outcome: &AttestationOutcome) -> f64 {
    match outcome {
        AttestationOutcome::Reproduced | AttestationOutcome::PartiallyReproduced { .. } => 1.0,
        _ => 0.0,
    }
}

fn cert_tier(total: u32, rate: f64) -> CertificationTier {
    if total >= 20 && rate >= 0.80 {
        CertificationTier::Senior
    } else if total >= 5 && rate >= 0.60 {
        CertificationTier::Certified
    } else {
        CertificationTier::Provisional
    }
}
use hdi::prelude::*;
use valichord_shared_types::{AgreementLevel, AttestationOutcome, CertificationTier, Discipline};

// ---------------------------------------------------------------------------
// DNA Properties — one key, baked into the DNA hash.
//
// system_coordinator_key gates GovernanceDecision creation only — governance
// decisions represent human deliberation outcomes and require a designated
// recorder.
//
// HarmonyRecord, ReproducibilityBadge, and ValidatorReputation are NOT
// author-gated: any participant who was part of the round can trigger
// finalisation. Content correctness is enforced in the coordinator
// (completeness check + idempotency) rather than by trusting a single agent.
// This keeps the system consistent with Holochain's decentralised model —
// no single node is a required coordinator for protocol completion.
//
// Remaining limitation (Phase 1): validate() cannot perform cross-DNA lookups
// to cryptographically verify HarmonyRecord content against the Attestation
// DHT. Content correctness is currently enforced in the coordinator layer
// only, not at the network validation layer.
// ---------------------------------------------------------------------------

#[dna_properties]
pub struct DnaProperties {
    /// Only this key may write GovernanceDecision entries.
    /// Empty string = dev/test bypass (skips the check entirely).
    pub system_coordinator_key: String,
    /// Minimum attestations required for force_finalize_round to write a
    /// HarmonyRecord. Set equal to minimum_validators (attestation DNA) to
    /// disallow any dropout; set lower to permit reduced-quorum finalization
    /// after the reveal timeout. Typical values: 7 for an 8-validator panel,
    /// 4 for a 4-validator panel (no dropout). 0 = use at-least-one default.
    pub min_attestations_for_finalization: u32,
}

// ---------------------------------------------------------------------------
// Entry Types
// ---------------------------------------------------------------------------

/// The canonical output of ValiChord — the final validation outcome.
///
/// "Harmony" preserves the full texture of agreement AND disagreement.
/// Disagreements are always visible — a non-negotiable governance commitment.
///
/// IMMUTABLE after creation: validate() blocks all updates and deletes.
///
/// Note: creation time is available from the Action — created_at_secs is
/// not stored here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct HarmonyRecord {
    /// Links back to the ValidationRequest in the Attestation DNA.
    pub request_ref:              ExternalHash,
    /// Majority-vote outcome across all validators.
    pub outcome:                  AttestationOutcome,
    /// Agreement level computed from validator outcomes.
    pub agreement_level:          AgreementLevel,
    /// Agent keys of all validators who participated.
    pub participating_validators: Vec<AgentPubKey>,
    /// Max time invested across validators (Phase 0 data collection).
    pub validation_duration_secs: u64,
    pub discipline:               Discipline,
}

/// Per-validator reputation score.
///
/// Only the system_coordinator_key agent may write these entries.
/// Individual dimensions prevent gaming that a single total score would enable.
/// Updateable by creating a new entry (linked via ValidatorToReputation).
///
/// Note: update time is available from the Action — last_updated_secs is
/// not stored here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidatorReputation {
    pub validator:         AgentPubKey,
    pub discipline:        Discipline,
    pub total_validations: u32,
    /// 0.0–1.0 rate of outcomes agreeing with the majority.
    pub agreement_rate:    f64,
    pub avg_time_secs:     u64,
    pub tier:              CertificationTier,
}

/// Reproducibility badge issued to researchers.
///
/// IMMUTABLE after creation.
///
/// Note: issuance time is available from the Action — issued_at_secs is
/// not stored here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ReproducibilityBadge {
    pub study_ref:          ExternalHash,
    pub issued_to:          AgentPubKey,
    pub badge_type:         BadgeType,
    /// ActionHash of the HarmonyRecord that triggered this badge.
    pub harmony_record_ref: ActionHash,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum BadgeType {
    GoldReproducible,
    SilverReproducible,
    BronzeReproducible,
    FailedReproduction,
}

/// Governance vote outcome — every decision is logged immutably.
///
/// IMMUTABLE after creation.
///
/// Note: decision time is available from the Action — decided_at_secs is
/// not stored here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct GovernanceDecision {
    pub proposal:     String,
    pub decision:     String,
    pub votes_for:    u32,
    pub votes_against: u32,
}

// ---------------------------------------------------------------------------
// Entry Types Enum
// ---------------------------------------------------------------------------

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    HarmonyRecord(HarmonyRecord),
    ValidatorReputation(ValidatorReputation),
    ReproducibilityBadge(ReproducibilityBadge),
    GovernanceDecision(GovernanceDecision),
}

// ---------------------------------------------------------------------------
// Link Types
// ---------------------------------------------------------------------------

#[hdk_link_types]
pub enum LinkTypes {
    /// AgentPubKey → ValidatorReputation ActionHash (most recent = last)
    ValidatorToReputation,
    /// Path anchor (request_ref) → HarmonyRecord ActionHash
    RequestToHarmonyRecord,
    /// Path anchor (discipline) → HarmonyRecord ActionHash
    DisciplinePath,
    /// Path anchor (badge_type) → ReproducibilityBadge ActionHash
    BadgePath,
    /// ExternalHash (study_ref) → ReproducibilityBadge ActionHash
    StudyToBadge,
    /// Path anchor ("decisions.all") → GovernanceDecision ActionHash
    AllDecisions,
}

// ---------------------------------------------------------------------------
// Validate Callback
// ---------------------------------------------------------------------------
//
// CRITICAL design notes:
//   1. Guarded arms (specific entry type) MUST come before unguarded arms.
//   2. Author checks use action.author.to_string() vs the String keys
//      from DnaProperties (base64-encoded AgentPubKey).
//   3. All entries validated by validate() are PUBLIC — deletes are checked
//      by deserializing the original entry via must_get_valid_record().
//   4. No membrane proof: public DHT, open read.

#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- HarmonyRecord create: open to any participant -------------------
        //
        // Any validator who participated in the round may trigger finalisation.
        // Content correctness is enforced by the coordinator's completeness
        // check and idempotency guard, not by an author allowlist.
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::HarmonyRecord(_), ..
        }) => Ok(ValidateCallbackResult::Valid),

        // --- GovernanceDecision create: only system_coordinator_key ---------
        //
        // Governance decisions represent human deliberation outcomes. A
        // designated key-holder records the result of each governance vote.
        // Empty key = dev/test bypass.
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::GovernanceDecision(_),
            ref action,
            ..
        }) => {
            let props = DnaProperties::try_from_dna_properties()?;
            if !props.system_coordinator_key.is_empty()
                && action.author.to_string() != props.system_coordinator_key
            {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only system_coordinator_key may write GovernanceDecision entries".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ReproducibilityBadge create: open to any participant ------------
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ReproducibilityBadge(_), ..
        }) => Ok(ValidateCallbackResult::Valid),

        // --- ValidatorReputation create: open to any participant -------------
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidatorReputation(_), ..
        }) => Ok(ValidateCallbackResult::Valid),

        // --- Immutability: block updates to HarmonyRecord -------------------
        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::HarmonyRecord(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "HarmonyRecord is immutable — the public record cannot be changed".into(),
        )),

        // --- Immutability: block updates to GovernanceDecision --------------
        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::GovernanceDecision(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "GovernanceDecision is immutable — the decision history is append-only".into(),
        )),

        // --- Immutability: block updates to ReproducibilityBadge ------------
        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ReproducibilityBadge(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ReproducibilityBadge is immutable — badges cannot be altered after issuance".into(),
        )),

        // --- ValidatorReputation update: open to any participant -------------
        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ValidatorReputation(_), ..
        }) => Ok(ValidateCallbackResult::Valid),

        FlatOp::RegisterUpdate(_) => Ok(ValidateCallbackResult::Valid),

        // --- Deletes: HarmonyRecord, GovernanceDecision, Badge are immutable -
        FlatOp::RegisterDelete(OpDelete { ref action }) => {
            let original_action = must_get_action(action.deletes_address.clone())?;
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
                        Some(EntryTypes::HarmonyRecord(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "HarmonyRecord is immutable — cannot be deleted".into(),
                            ));
                        }
                        Some(EntryTypes::GovernanceDecision(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "GovernanceDecision is immutable — cannot be deleted".into(),
                            ));
                        }
                        Some(EntryTypes::ReproducibilityBadge(_)) => {
                            return Ok(ValidateCallbackResult::Invalid(
                                "ReproducibilityBadge is immutable — cannot be deleted".into(),
                            ));
                        }
                        _ => {}
                    }
                }
            }
            // Non-immutable entries: only original author may delete.
            if action.author != *original_action.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // All other ops: valid. Public DHT — open read is the design intent.
        _ => Ok(ValidateCallbackResult::Valid),
    }
}


// ---------------------------------------------------------------------------
// genesis_self_check — no membrane proof required (public DHT, open join)
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn genesis_self_check(
    _data: GenesisSelfCheckData,
) -> ExternResult<ValidateCallbackResult> {
    Ok(ValidateCallbackResult::Valid)
}
use hdk::prelude::*;
use researcher_repository_integrity::{
    DeclaredDeviation, EntryTypes, LinkTypes, LockedResult, PreRegisteredProtocol, ResearchStudy,
    VerifiedDataSnapshot,
};
use valichord_shared_types::{MetricResult, UndeclaredDeviation};
use attestation_integrity::ResearcherCommitmentInput;
use sha2::{Sha256, Digest};
use rmp_serde as rmps;

// ---------------------------------------------------------------------------
// No init() needed.
// Single-agent private DNA — author grant covers all calls automatically.
// No remote agents need capability access.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Input structs for multi-field write functions
// ---------------------------------------------------------------------------

/// Input for register_protocol: study to link from + the protocol to create.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterProtocolInput {
    pub study_ref: ActionHash,
    pub protocol:  PreRegisteredProtocol,
}

/// Input for take_data_snapshot: study to link from + the snapshot to create.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TakeDataSnapshotInput {
    pub study_ref: ActionHash,
    pub snapshot:  VerifiedDataSnapshot,
}

/// Input for declare_deviation: study to link from + the deviation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeclareDeviationInput {
    pub study_ref: ActionHash,
    pub deviation: UndeclaredDeviation,
}

/// Input for lock_researcher_result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LockResultInput {
    /// The same ExternalHash used in the ValidationRequest.data_hash field
    /// (identifies the study on the shared Attestation DHT).
    pub request_ref: ExternalHash,
    /// The structured per-metric results from the researcher's original run.
    pub metrics:     Vec<MetricResult>,
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

/// Register a new research study.
#[hdk_extern]
pub fn register_study(study: ResearchStudy) -> ExternResult<ActionHash> {
    create_entry(EntryTypes::ResearchStudy(study))
}

/// Return all ResearchStudy records from this agent's local source chain.
///
/// Uses query() + deserialization filter — avoids hardcoded ZomeIndex which
/// breaks silently if entry ordering changes.
#[hdk_extern]
pub fn get_all_studies(_: ()) -> ExternResult<Vec<Record>> {
    let records = query(ChainQueryFilter::new().include_entries(true))?;
    let studies = records
        .into_iter()
        .filter(|r| {
            r.entry()
                .to_app_option::<ResearchStudy>()
                .ok()
                .flatten()
                .is_some()
        })
        .collect();
    Ok(studies)
}

/// Register a pre-registered protocol and link it from the parent study.
///
/// PreRegisteredProtocol is IMMUTABLE after this call — validate() enforces
/// that no updates or deletes are possible.
#[hdk_extern]
pub fn register_protocol(input: RegisterProtocolInput) -> ExternResult<ActionHash> {
    let protocol_hash =
        create_entry(EntryTypes::PreRegisteredProtocol(input.protocol))?;
    create_link(
        input.study_ref,
        protocol_hash.clone(),
        LinkTypes::StudyToProtocol,
        (),
    )?;
    Ok(protocol_hash)
}

/// Record a dataset snapshot and link it from the parent study.
///
/// Only the hash and metadata are stored — the data bytes themselves are
/// never passed to this function. Use compute_data_hash() first.
#[hdk_extern]
pub fn take_data_snapshot(input: TakeDataSnapshotInput) -> ExternResult<ActionHash> {
    let snapshot_hash =
        create_entry(EntryTypes::VerifiedDataSnapshot(input.snapshot))?;
    create_link(
        input.study_ref,
        snapshot_hash.clone(),
        LinkTypes::StudyToSnapshot,
        (),
    )?;
    Ok(snapshot_hash)
}

/// Record a declared deviation from the pre-registered plan.
///
/// Stored as a separate private DeclaredDeviation entry — the original
/// PreRegisteredProtocol is never modified, preserving immutability.
/// The deviation is linked from the study for structured discovery.
#[hdk_extern]
pub fn declare_deviation(input: DeclareDeviationInput) -> ExternResult<ActionHash> {
    let deviation_hash = create_entry(EntryTypes::DeclaredDeviation(
        DeclaredDeviation { deviation: input.deviation },
    ))?;
    create_link(
        input.study_ref,
        deviation_hash.clone(),
        LinkTypes::StudyToDeviation,
        (),
    )?;
    Ok(deviation_hash)
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn get_study(hash: ActionHash) -> ExternResult<Option<Record>> {
    get(hash, GetOptions::local())
}

/// Return the first (and typically only) protocol linked from a study.
#[hdk_extern]
pub fn get_protocol_for_study(study_hash: ActionHash) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_hash, LinkTypes::StudyToProtocol)?,
        GetStrategy::Local,
    )?;
    match links.first() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid StudyToProtocol link target".into()
                )))?;
            get(target, GetOptions::local())
        }
        None => Ok(None),
    }
}

#[hdk_extern]
pub fn get_snapshots_for_study(study_hash: ActionHash) -> ExternResult<Vec<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_hash, LinkTypes::StudyToSnapshot)?,
        GetStrategy::Local,
    )?;
    let mut records = Vec::new();
    for link in links {
        if let Some(hash) = link.target.into_action_hash() {
            if let Some(record) = get(hash, GetOptions::local())? {
                records.push(record);
            }
        }
    }
    Ok(records)
}

#[hdk_extern]
pub fn get_deviations_for_study(study_hash: ActionHash) -> ExternResult<Vec<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_hash, LinkTypes::StudyToDeviation)?,
        GetStrategy::Local,
    )?;
    let mut records = Vec::new();
    for link in links {
        if let Some(hash) = link.target.into_action_hash() {
            if let Some(record) = get(hash, GetOptions::local())? {
                records.push(record);
            }
        }
    }
    Ok(records)
}

// ---------------------------------------------------------------------------
// Commit-reveal — researcher side
// ---------------------------------------------------------------------------

/// Lock the researcher's result at study submission time.
///
/// Workflow:
///   1. Generate a 32-byte random nonce.
///   2. Compute `commitment_hash = SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`.
///   3. Store a private `LockedResult` entry on this device (metrics + nonce +
///      hash — never leaves this DNA).
///   4. Publish only the hash to the shared Attestation DHT via
///      `publish_researcher_commitment`.
///   5. Return the ActionHash of the private entry (used later to retrieve
///      the nonce for reveal).
///
/// Must be called BEFORE the validation round opens.  Validators can check that
/// a commitment exists via `get_researcher_commitment` on the Attestation DNA
/// before accepting a study claim.
#[hdk_extern]
pub fn lock_researcher_result(input: LockResultInput) -> ExternResult<ActionHash> {
    // 1. Random nonce.
    let nonce: Vec<u8> = random_bytes(32)?.to_vec();

    // 2. Commitment hash: SHA-256(msgpack(metrics) || nonce).
    let msgpack_bytes: Vec<u8> = rmps::to_vec_named(&input.metrics)
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?;
    let mut hasher = Sha256::new();
    hasher.update(&msgpack_bytes);
    hasher.update(&nonce);
    let commitment_hash: Vec<u8> = hasher.finalize().to_vec();

    // 3. Store privately.
    let locked = LockedResult {
        request_ref:     input.request_ref.clone(),
        metrics:         input.metrics,
        nonce:           nonce.clone(),
        commitment_hash: commitment_hash.clone(),
    };
    let locked_hash = create_entry(EntryTypes::LockedResult(locked))?;

    // Index so get_locked_result can find it by request_ref.
    create_link(
        input.request_ref.clone(),
        locked_hash.clone(),
        LinkTypes::RequestToLockedResult,
        (),
    )?;

    // 4. Publish only the hash to the shared Attestation DHT.
    let commitment_input = ResearcherCommitmentInput {
        request_ref:            input.request_ref,
        result_commitment_hash: commitment_hash,
    };
    let _ = call(
        CallTargetCell::OtherRole("attestation".into()),
        ZomeName::from("attestation_coordinator"),
        FunctionName::from("publish_researcher_commitment"),
        None,
        commitment_input,
    )?;

    Ok(locked_hash)
}

/// Retrieve the researcher's private locked result for a given request.
///
/// Returns the `LockedResult` record (containing metrics + nonce) so the
/// researcher can pass those fields to `reveal_researcher_result` on the
/// Attestation DNA once all validators have committed.
///
/// Returns `None` if no lock has been created for this request yet.
#[hdk_extern]
pub fn get_locked_result(request_ref: ExternalHash) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(request_ref, LinkTypes::RequestToLockedResult)?,
        GetStrategy::Local,
    )?;
    match links.last() {
        Some(link) => {
            let hash = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid RequestToLockedResult link target".into()
                )))?;
            get(hash, GetOptions::local())
        }
        None => Ok(None),
    }
}

/// Compute SHA-256 of data bytes and return as a Holochain ExternalHash.
///
/// Engineering constraint #6: SHA-256 for research file fingerprints.
/// BLAKE2b is Holochain-internal. The sha2 crate is compiled to WASM via
/// Cargo.toml. The resulting ExternalHash is what the researcher passes to
/// the Attestation DNA's ValidationRequest.data_hash field.
///
/// The data bytes NEVER leave this private DNA — only the hash travels.
/// This is the primary GDPR protection: membrane separation ensures sensitive
/// data cannot enter the shared DHT by architecture, not policy.
#[hdk_extern]
pub fn compute_data_hash(data: Vec<u8>) -> ExternResult<ExternalHash> {
    let sha256_bytes: Vec<u8> = Sha256::digest(&data).to_vec();
    // from_raw_32 prepends the External hash type prefix [0x84, 0x2F, 0x24]
    // and computes the 4-byte DHT location from the 32-byte SHA-256 core.
    Ok(ExternalHash::from_raw_32(sha256_bytes))
}
use hdi::prelude::*;
use valichord_shared_types::{Discipline, MetricResult, UndeclaredDeviation};

// ---------------------------------------------------------------------------
// Entry Types
// ---------------------------------------------------------------------------
//
// ALL entries are visibility = "private" — this is a single-agent private DNA.
// Nothing ever propagates to a shared DHT. GDPR compliance is architecturally
// enforced: raw research data cannot leave this membrane.

/// Top-level metadata about a research study.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ResearchStudy {
    pub title:                String,
    pub discipline:           Discipline,
    pub institution:          String,
    pub abstract_text:        String,
    /// DOI or URL of the pre-registration (OSF, AsPredicted, ClinicalTrials…).
    pub pre_registration_ref: Option<String>,
}

/// The researcher's locked analysis plan — committed before seeing results.
///
/// IMMUTABLE after creation: validate() blocks all updates and deletes.
/// This guarantees that the protocol on record is exactly what was filed
/// before unblinding, not a post-hoc revision.
///
/// Note: creation timestamp is available from the Action — do not add
/// registered_at_secs here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct PreRegisteredProtocol {
    pub analysis_plan:       String,
    pub hypotheses:          Vec<String>,
    pub statistical_methods: String,
}

/// A cryptographic snapshot of the dataset used for validation.
///
/// Only the hash and metadata travel anywhere — the data itself
/// stays inside this private membrane.
///
/// Note: snapshot time is available from the Action — do not add
/// snapshot_taken_at_secs here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct VerifiedDataSnapshot {
    /// ExternalHash (SHA-256 of the data files, wrapped in Holochain's
    /// 39-byte HoloHash format). This is what the researcher shares
    /// with the Attestation DNA's ValidationRequest.data_hash field.
    pub data_hash:        ExternalHash,
    pub file_count:       u32,
    pub total_size_bytes: u64,
}

/// The researcher's private locked result — created by `lock_researcher_result`
/// at study submission time.
///
/// Stores the structured metrics, the random nonce, and the pre-computed
/// commitment hash that was published to the Attestation DHT via
/// `publish_researcher_commitment`.  At reveal time the researcher calls
/// `reveal_researcher_result` (DNA 3) using these fields; the commitment hash
/// is verified on-chain before the structured metrics land on the shared DHT.
///
/// IMMUTABLE — the blanket `PrivateEntry` update guard in validate() covers this.
/// PRIVATE — never leaves this device; GDPR-safe.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct LockedResult {
    pub request_ref:           ExternalHash,
    /// The per-metric results from the researcher's original run.
    pub metrics:               Vec<MetricResult>,
    /// 32-byte random nonce generated at lock time.
    pub nonce:                 Vec<u8>,
    /// SHA-256(rmp_serde::to_vec_named(metrics) || nonce) — already published
    /// to the Attestation DHT.  Stored here for local reference only.
    pub commitment_hash:       Vec<u8>,
}

/// A deviation from the pre-registered plan that the researcher declares
/// before the validation round begins.
///
/// Stored as a separate private entry and linked from the study — the
/// original PreRegisteredProtocol is never modified, preserving the
/// full immutable audit trail.
#[hdk_entry_helper]
#[derive(Clone)]
pub struct DeclaredDeviation {
    pub deviation: UndeclaredDeviation,
}

// ---------------------------------------------------------------------------
// Entry Types Enum
// ---------------------------------------------------------------------------

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    // All entries are private — never enter the shared DHT.
    #[entry_type(visibility = "private")]
    ResearchStudy(ResearchStudy),
    #[entry_type(visibility = "private")]
    PreRegisteredProtocol(PreRegisteredProtocol),
    #[entry_type(visibility = "private")]
    VerifiedDataSnapshot(VerifiedDataSnapshot),
    #[entry_type(visibility = "private")]
    DeclaredDeviation(DeclaredDeviation),
    #[entry_type(visibility = "private")]
    LockedResult(LockedResult),
}

// ---------------------------------------------------------------------------
// Link Types
// ---------------------------------------------------------------------------

#[hdk_link_types]
pub enum LinkTypes {
    /// ResearchStudy ActionHash → PreRegisteredProtocol ActionHash
    StudyToProtocol,
    /// ResearchStudy ActionHash → VerifiedDataSnapshot ActionHash
    StudyToSnapshot,
    /// ResearchStudy ActionHash → DeclaredDeviation ActionHash
    StudyToDeviation,
    /// ExternalHash (request_ref) → LockedResult ActionHash
    RequestToLockedResult,
}

// ---------------------------------------------------------------------------
// Validate Callback
// ---------------------------------------------------------------------------
//
// Engineering constraint #7: guarded arms MUST precede unguarded arms.
// Rust evaluates match arms in order — an unguarded arm first silently
// swallows everything, breaking immutability guarantees without any error.

#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- PreRegisteredProtocol immutability (updates) ------------------
        //
        // Block all updates — the locked protocol must never be altered.
        // Declared deviations are separate DeclaredDeviation entries linked
        // from the study, preserving the original plan intact.

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::PreRegisteredProtocol(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "PreRegisteredProtocol is immutable — updates are not permitted".into(),
        )),

        // --- PreRegisteredProtocol immutability (deletes) ------------------
        //
        // Must be checked via must_get_action since OpDelete carries only
        // the deleting action, not the original entry type directly.

        FlatOp::RegisterDelete(OpDelete { ref action }) => {
            let original_action = must_get_action(action.deletes_address.clone())?;
            if let Some(EntryType::App(app_def)) = original_action.action().entry_type() {
                let original_record =
                    must_get_valid_record(action.deletes_address.clone())?;
                if let Some(entry) = original_record.entry().as_option() {
                    let entry_type = EntryTypes::deserialize_from_type(
                        app_def.zome_index,
                        app_def.entry_index,
                        entry,
                    )?;
                    if let Some(EntryTypes::PreRegisteredProtocol(_)) = entry_type {
                        return Ok(ValidateCallbackResult::Invalid(
                            "PreRegisteredProtocol is immutable — deletes are not permitted".into(),
                        ));
                    }
                }
            }
            // All other entries: only the original author may delete.
            if action.author != *original_action.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // Generic update for all other entry types: only original author may
        // update. Placed AFTER the guarded PreRegisteredProtocol arm so that
        // the guard fires first.
        FlatOp::RegisterUpdate(OpUpdate::Entry { action, .. }) => {
            let original = must_get_action(action.original_action_address.clone())?;
            if action.author != *original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        FlatOp::RegisterUpdate(OpUpdate::PrivateEntry { .. }) => Ok(
            ValidateCallbackResult::Invalid(
                "Private entry updates not supported in this DNA".into(),
            ),
        ),

        // All other update variants: accept.
        FlatOp::RegisterUpdate(_) => Ok(ValidateCallbackResult::Valid),

        // All remaining ops (creates, links, agent activity, etc.): accept.
        // Single-agent private DNA — source chain integrity is sufficient.
        _ => Ok(ValidateCallbackResult::Valid),
    }
}

// ---------------------------------------------------------------------------
// genesis_self_check — no membrane proof required
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn genesis_self_check(
    _data: GenesisSelfCheckData,
) -> ExternResult<ValidateCallbackResult> {
    // Single-agent private DNA — no credentialed joining requirement.
    Ok(ValidateCallbackResult::Valid)
}
use hdk::prelude::*;
use validator_workspace_integrity::{EntryTypes, LinkTypes, ValidationTask, ValidatorPrivateAttestation};
use valichord_shared_types::ValidationAttestation;
use attestation_integrity::CommitmentSealedInput;
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// No init() needed.
// Single-agent private DNA — author grant covers all calls automatically.
// No remote agents need capability access.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Input struct for seal_private_attestation
// ---------------------------------------------------------------------------

/// Input for seal_private_attestation.
///
/// `attestation` is the EXACT `ValidationAttestation` that will be revealed
/// publicly during the reveal phase.  The coordinator serialises it and
/// hashes it (with a generated nonce) to produce the `commitment_hash` that
/// goes to the shared Attestation DHT.  The caller must NOT supply `nonce` or
/// `commitment_hash` — they are generated here.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SealAttestationInput {
    pub task_hash:   ActionHash,
    pub attestation: ValidationAttestation,
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

/// Receive a validation task from the Attestation DNA and store it locally.
#[hdk_extern]
pub fn receive_task(task: ValidationTask) -> ExternResult<ActionHash> {
    create_entry(EntryTypes::ValidationTask(task))
}

/// Seal the validator's private attestation — the COMMIT PHASE.
///
/// 1. Generates a random 32-byte nonce via Holochain's `random_bytes` host function.
/// 2. Serialises `input.attestation` to MessagePack (same encoding Holochain
///    uses for all DHT entries, so the commitment hash is reproducible at
///    reveal time using only the public attestation + nonce).
/// 3. Computes `commitment_hash = SHA-256(msgpack_bytes || nonce)`.
/// 4. Stores the full `ValidatorPrivateAttestation` (including nonce and hash)
///    as a PRIVATE entry — content never leaves this device.
/// 5. `post_commit` fires after the write and cross-calls the Attestation DNA's
///    `notify_commitment_sealed` with the commitment_hash so the shared DHT
///    records that this validator has committed (without revealing any content).
#[hdk_extern]
pub fn seal_private_attestation(input: SealAttestationInput) -> ExternResult<ActionHash> {
    // 1. Random 32-byte nonce — HDK host function, never available in validate().
    let nonce: Vec<u8> = random_bytes(32)?.to_vec();

    // 2. Serialise the public attestation to MessagePack.
    //    SerializedBytes uses rmp_serde::to_vec_named internally — the same
    //    codec the Attestation DNA will use when verifying the reveal.
    let msgpack_bytes: Vec<u8> = SerializedBytes::try_from(&input.attestation)
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
        .bytes()
        .to_vec();

    // 3. commitment_hash = SHA-256(msgpack_bytes || nonce)
    let mut hasher = Sha256::new();
    hasher.update(&msgpack_bytes);
    hasher.update(&nonce);
    let commitment_hash: Vec<u8> = hasher.finalize().to_vec();

    // 4. Build the private entry — all public attestation fields are mirrored
    //    here so the full ValidationAttestation can be reconstructed at reveal
    //    time without a separate task lookup.
    let att = &input.attestation;
    let private_attestation = ValidatorPrivateAttestation {
        request_ref:             att.request_ref.clone(),
        outcome:                 att.outcome.clone(),
        outcome_summary:         att.outcome_summary.clone(),
        time_invested_secs:      att.time_invested_secs,
        time_breakdown:          att.time_breakdown.clone(),
        deviation_flags:         att.deviation_flags.clone(),
        computational_resources: att.computational_resources.clone(),
        confidence:              att.confidence.clone(),
        discipline:              att.discipline.clone(),
        nonce,
        commitment_hash,
    };

    let attestation_hash =
        create_entry(EntryTypes::ValidatorPrivateAttestation(private_attestation))?;
    create_link(
        input.task_hash,
        attestation_hash.clone(),
        LinkTypes::TaskToPrivateAttestation,
        (),
    )?;
    Ok(attestation_hash)
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn get_task(task_hash: ActionHash) -> ExternResult<Option<Record>> {
    get(task_hash, GetOptions::local())
}

/// Return the private attestation linked from a task, if any.
#[hdk_extern]
pub fn get_private_attestation_for_task(
    task_hash: ActionHash,
) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(task_hash, LinkTypes::TaskToPrivateAttestation)?,
        GetStrategy::Local,
    )?;
    match links.first() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid TaskToPrivateAttestation link target".into()
                )))?;
            get(target, GetOptions::local())
        }
        None => Ok(None),
    }
}

/// Return all ValidatorPrivateAttestation records from the local source chain.
///
/// Uses query() + deserialization filter — avoids hardcoded ZomeIndex which
/// breaks silently if entry ordering changes.
#[hdk_extern]
pub fn get_all_private_attestations(_: ()) -> ExternResult<Vec<Record>> {
    let records = query(ChainQueryFilter::new().include_entries(true))?;
    let attestations = records
        .into_iter()
        .filter(|r| {
            r.entry()
                .to_app_option::<ValidatorPrivateAttestation>()
                .ok()
                .flatten()
                .is_some()
        })
        .collect();
    Ok(attestations)
}

/// Return all ValidationTask records from the local source chain.
///
/// Queries all private entries and filters by successful deserialization as
/// ValidationTask — avoids hardcoded ZomeIndex/EntryDefIndex which break
/// silently if entry ordering ever changes.
#[hdk_extern]
pub fn get_all_tasks(_: ()) -> ExternResult<Vec<Record>> {
    let records = query(ChainQueryFilter::new().include_entries(true))?;
    let tasks = records
        .into_iter()
        .filter(|r| {
            r.entry()
                .to_app_option::<ValidationTask>()
                .ok()
                .flatten()
                .is_some()
        })
        .collect();
    Ok(tasks)
}

// ---------------------------------------------------------------------------
// post_commit — notify Attestation DNA when a ValidatorPrivateAttestation
// is sealed to this source chain.
// ---------------------------------------------------------------------------
//
// `infallible` — failures are logged and silently dropped, never panic.
// The cross-DNA call uses the author grant; same-agent calls are always
// permitted without an explicit capability grant.

#[hdk_extern(infallible)]
pub fn post_commit(committed_actions: Vec<SignedActionHashed>) {
    if let Err(e) = _post_commit_inner(committed_actions) {
        debug!("post_commit error (non-fatal): {:?}", e);
    }
}

fn _post_commit_inner(committed_actions: Vec<SignedActionHashed>) -> ExternResult<()> {
    for signed in committed_actions {
        if let Action::Create(create) = signed.action() {
            // Fetch the entry and try to deserialize as ValidatorPrivateAttestation.
            // This avoids hardcoded ZomeIndex/EntryDefIndex which break silently
            // if entry ordering changes.
            let record = get(create.entry_hash.clone(), GetOptions::local())?;
            if let Some(rec) = record {
                if let Some(attestation) = rec
                    .entry()
                    .to_app_option::<ValidatorPrivateAttestation>()
                    .ok()
                    .flatten()
                {
                    // Pass both the request identifier AND the commitment_hash
                    // so the Attestation DNA can record a fully-formed
                    // CommitmentAnchor without knowing the private content.
                    let sealed_input = CommitmentSealedInput {
                        request_ref:     attestation.request_ref.clone(),
                        commitment_hash: attestation.commitment_hash.clone(),
                    };
                    let _result: ExternResult<ZomeCallResponse> = call(
                        CallTargetCell::OtherRole("attestation".into()),
                        ZomeName::from("attestation_coordinator"),
                        FunctionName::from("notify_commitment_sealed"),
                        None,
                        sealed_input,
                    );
                    if let Err(e) = _result {
                        debug!(
                            "notify_commitment_sealed call failed (non-fatal): {:?}",
                            e
                        );
                    }
                }
            }
        }
    }
    Ok(())
}
use hdi::prelude::*;
use valichord_shared_types::{
    AttestationConfidence, AttestationOutcome, ComputationalResources, Discipline,
    OutcomeSummary, TimeBreakdown, UndeclaredDeviation,
};

// ---------------------------------------------------------------------------
// Supporting types — local to DNA 2
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ValidationFocus {
    ComputationalReproducibility,
    PreCommitmentAdherence,
    MethodologicalReview,
}

/// Compensation tiers — Phase 0 empirical evidence will determine final values.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CompensationTier {
    Tier1 { amount_pence: u64 }, // ~1–2 hours: £50–100
    Tier2 { amount_pence: u64 }, // ~4–8 hours: £200–400
    Tier3 { amount_pence: u64 }, // ~16+ hours: £800–1600
}

// ---------------------------------------------------------------------------
// Entry Types
// ---------------------------------------------------------------------------
//
// ALL entries are visibility = "private" — single-agent private DNA.
// Nothing propagates to any shared DHT.

/// A validation assignment received from the Attestation DNA.
///
/// Note: assignment time is available from the Action — assigned_at_secs
/// is not stored here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidationTask {
    /// References the ValidationRequest entry in the Attestation DNA.
    pub request_ref:       ExternalHash,
    pub discipline:        Discipline,
    pub deadline_secs:     u64,
    pub validation_focus:  ValidationFocus,
    pub time_cap_secs:     u64,
    pub compensation_tier: CompensationTier,
}

/// THE COMMIT PHASE — the validator's sealed private attestation.
///
/// Stored as a private entry: invisible to all peers and the shared DHT.
/// Its *existence* is verifiable via `get_agent_activity` (the private action
/// appears in the source chain header sequence). Its *content* stays on this
/// device until the validator calls `submit_attestation` on the Attestation DNA.
///
/// `nonce` and `commitment_hash` are generated by `seal_private_attestation` in
/// the coordinator — the caller never provides them.  The commitment hash is what
/// goes to the shared DHT (CommitmentAnchor); the nonce is kept here so the
/// validator can retrieve it when constructing their public reveal.
///
/// IMMUTABLE after creation — validate() blocks all updates and deletes.
/// This guarantees the commitment is exactly what was filed before unblinding.
///
/// Note: sealing time is available from the Action — sealed_at_secs is not
/// stored here (self-reported, falsifiable, redundant).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidatorPrivateAttestation {
    /// References the ValidationRequest in the Attestation DNA.
    pub request_ref:             ExternalHash,
    pub outcome:                 AttestationOutcome,
    pub outcome_summary:         OutcomeSummary,
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub deviation_flags:         Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
    pub confidence:              AttestationConfidence,
    /// Discipline is stored here (copied from ValidationAttestation) so the
    /// full public ValidationAttestation can be reconstructed at reveal time
    /// without a separate task lookup.
    pub discipline:              Discipline,
    /// Random 32-byte nonce generated at seal time. Kept private.
    /// Provided alongside the public attestation at reveal time for hash verification.
    pub nonce:                   Vec<u8>,
    /// SHA-256(msgpack(ValidationAttestation) || nonce). Published to the
    /// CommitmentAnchor on the shared DHT; stored here as an audit record.
    pub commitment_hash:         Vec<u8>,
}

// ---------------------------------------------------------------------------
// Entry Types Enum
// ---------------------------------------------------------------------------

#[hdk_entry_types]
#[unit_enum(UnitEntryTypes)]
pub enum EntryTypes {
    #[entry_type(visibility = "private")]
    ValidationTask(ValidationTask),
    #[entry_type(visibility = "private")]
    ValidatorPrivateAttestation(ValidatorPrivateAttestation),
}

// ---------------------------------------------------------------------------
// Link Types
// ---------------------------------------------------------------------------

#[hdk_link_types]
pub enum LinkTypes {
    /// ValidationTask ActionHash → ValidatorPrivateAttestation ActionHash
    TaskToPrivateAttestation,
}

// ---------------------------------------------------------------------------
// Validate Callback
// ---------------------------------------------------------------------------
//
// Engineering constraint #7: guarded arms MUST precede unguarded arms.

#[hdk_extern]
pub fn validate(op: Op) -> ExternResult<ValidateCallbackResult> {
    match op.flattened::<EntryTypes, LinkTypes>()? {

        // --- ValidatorPrivateAttestation immutability (updates) -------------
        //
        // The sealed commitment must never be altered after creation.

        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ValidatorPrivateAttestation(_), ..
        }) => Ok(ValidateCallbackResult::Invalid(
            "ValidatorPrivateAttestation is immutable — updates are not permitted".into(),
        )),

        // --- ValidatorPrivateAttestation immutability (deletes) -------------

        FlatOp::RegisterDelete(OpDelete { ref action }) => {
            let original_action = must_get_action(action.deletes_address.clone())?;
            if let Some(EntryType::App(app_def)) = original_action.action().entry_type() {
                let original_record =
                    must_get_valid_record(action.deletes_address.clone())?;
                if let Some(entry) = original_record.entry().as_option() {
                    let entry_type = EntryTypes::deserialize_from_type(
                        app_def.zome_index,
                        app_def.entry_index,
                        entry,
                    )?;
                    if let Some(EntryTypes::ValidatorPrivateAttestation(_)) = entry_type {
                        return Ok(ValidateCallbackResult::Invalid(
                            "ValidatorPrivateAttestation is immutable — deletes are not permitted".into(),
                        ));
                    }
                }
            }
            // All other entries: only the original author may delete.
            if action.author != *original_action.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // Generic update for all other entry types: only original author may update.
        // Placed AFTER the guarded ValidatorPrivateAttestation arm.
        FlatOp::RegisterUpdate(OpUpdate::Entry { action, .. }) => {
            let original = must_get_action(action.original_action_address.clone())?;
            if action.author != *original.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may update this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        FlatOp::RegisterUpdate(OpUpdate::PrivateEntry { .. }) => Ok(
            ValidateCallbackResult::Invalid(
                "Private entry updates not supported in this DNA".into(),
            ),
        ),

        // All other update variants: accept.
        FlatOp::RegisterUpdate(_) => Ok(ValidateCallbackResult::Valid),

        // All remaining ops: accept.
        // Single-agent private DNA — source chain integrity is sufficient.
        _ => Ok(ValidateCallbackResult::Valid),
    }
}

// ---------------------------------------------------------------------------
// genesis_self_check — no membrane proof required
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn genesis_self_check(
    _data: GenesisSelfCheckData,
) -> ExternResult<ValidateCallbackResult> {
    // Single-agent private DNA — no credentialed joining requirement.
    Ok(ValidateCallbackResult::Valid)
}
use hdi::prelude::*;

// ---------------------------------------------------------------------------
// Core type alias
// ---------------------------------------------------------------------------

/// In real crates use `ExternalHash` from `hdi::prelude::*`.
/// ExternalHash serialises correctly through Holochain's MessagePack layer
/// and can be used as a DHT base address for links.
pub type ResearchHash = ExternalHash;

// ---------------------------------------------------------------------------
// Discipline enum
// ---------------------------------------------------------------------------

/// Scientific discipline. Extended by governance decision, not code change.
/// Kept in shared types so the same enum is used across all four DNAs.
#[derive(Debug, Clone, Hash, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
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

/// Converts a Discipline to the short path-key string used in DHT path anchors.
pub fn discipline_tag(d: &Discipline) -> String {
    match d {
        Discipline::ComputationalBiology => "computational_biology".into(),
        Discipline::ClimateScience       => "climate_science".into(),
        Discipline::SocialScience        => "social_science".into(),
        Discipline::Economics            => "economics".into(),
        Discipline::Psychology           => "psychology".into(),
        Discipline::Neuroscience         => "neuroscience".into(),
        Discipline::MachineLearning      => "machine_learning".into(),
        Discipline::Other(s)             => format!("other_{}", s.to_lowercase()),
    }
}

// ---------------------------------------------------------------------------
// Attestation outcome types
// ---------------------------------------------------------------------------

/// Structured outcome from a single validator's reproduction attempt.
/// Shared across DNA 2 (private commit) and DNA 3 (public reveal).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
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

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum AttestationConfidence { High, Medium, Low }

/// Phase 0's four-category time breakdown — the primary measurement goal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeBreakdown {
    pub environment_setup_secs: u64,
    pub data_acquisition_secs:  u64,
    pub code_execution_secs:    u64,
    pub troubleshooting_secs:   u64,
}

// ---------------------------------------------------------------------------
// Deviation types
// ---------------------------------------------------------------------------

/// Structured deviation type. Machine-readable, not free text.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
pub enum DeviationType {
    DataAccess            { reason: String, impact: EpistemicImpact },
    EthicalConcern        { review_board: String },
    ModelFailure          { attempted_model: String, fallback_model: String, justification: String },
    ComputationalLimit    { planned_method: String, actual_method: String, reason: String },
    SampleSizeAdjustment  { original_n: usize, revised_n: usize, power_analysis: String },
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EpistemicImpact {
    Minimal,
    Moderate,
    Substantial, // Triggers governance review
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Severity { Minor, Moderate, Major, Critical }

/// A deviation the validator observed that the researcher did NOT pre-declare.
/// Defined in shared types so the same struct is used in both Validator
/// Workspace DNA (private attestation) and Attestation DNA (public reveal).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UndeclaredDeviation {
    pub deviation_type: DeviationType,
    pub severity:       Severity,
    pub evidence:       String,
}

// ---------------------------------------------------------------------------
// Computational resources
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComputationalResources {
    pub personal_hardware_sufficient:  bool,
    pub hpc_required:                  bool,
    pub gpu_required:                  bool,
    pub cloud_compute_required:        bool,
    /// Integer pence to avoid floating-point rounding in financial values.
    pub estimated_compute_cost_pence:  Option<u64>,
}

// ---------------------------------------------------------------------------
// Validation phase (DNA 3 commit-reveal protocol state)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ValidationPhase {
    RevealOpen,
    Complete,
}

// ---------------------------------------------------------------------------
// Attestation agreement and certification types
// ---------------------------------------------------------------------------
//
// Defined here (not in attestation_integrity) so they can be imported by
// validator_workspace_integrity, governance_integrity, and governance_coordinator
// WITHOUT creating a cdylib→cdylib dependency — which would cause duplicate
// WASM symbol errors at link time.

/// Agreement level across validator outcomes for a given request.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum AgreementLevel {
    ExactMatch,
    WithinTolerance,
    DirectionalMatch,
    Divergent,
    UnableToAssess,
}

/// Per-validator certification tier used in ValidatorProfile and ValidatorReputation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum CertificationTier {
    Provisional,
    Certified,
    Senior,
}

/// Structured per-metric outcome — included in OutcomeSummary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricResult {
    pub metric_name:      String,
    pub produced_value:   String,
    pub expected_value:   String,
    pub within_tolerance: bool,
}

/// Agreement summary attached to every ValidationAttestation.
/// Agreement is assessed on summaries — NOT raw result hashes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutcomeSummary {
    pub key_metrics:                 Vec<MetricResult>,
    pub effect_direction_matches:    Option<bool>,
    pub confidence_interval_overlap: Option<f64>,
    pub overall_agreement:           AgreementLevel,
}

/// THE REVEAL PHASE public attestation entry — defined here so governance_coordinator
/// can deserialise cross-DNA records without importing attestation_integrity (cdylib).
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidationAttestation {
    pub request_ref:             ExternalHash,
    pub outcome:                 AttestationOutcome,
    pub outcome_summary:         OutcomeSummary,
    pub time_invested_secs:      u64,
    pub time_breakdown:          TimeBreakdown,
    pub confidence:              AttestationConfidence,
    pub deviation_flags:         Vec<UndeclaredDeviation>,
    pub computational_resources: ComputationalResources,
    pub discipline:              Discipline,
}

impl ValidationAttestation {
    pub fn discipline_tag(&self) -> String {
        discipline_tag(&self.discipline)
    }
}
---
manifest_version: "0"
name: attestation
integrity:
  network_seed: ~
  properties:
    # AgentPubKey of the certificate authority whose signatures are accepted
    # as valid JoiningCertificates for this network's membrane proof.
    authorized_joining_certificate_issuer: "uhCAkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    # Discipline this network serves (baked into DNA hash — change = new network).
    discipline: "genomics"
    # Minimum number of validator attestations required before a HarmonyRecord
    # can be minted for this discipline.
    minimum_validators: 3
  zomes:
    - name: attestation_integrity
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/attestation_integrity.wasm"
      dependencies: ~
coordinator:
  zomes:
    - name: attestation_coordinator
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/attestation_coordinator.wasm"
      dependencies:
        - name: attestation_integrity

        ---
manifest_version: "0"
name: governance
integrity:
  network_seed: ~
  # Two keys baked into DNA properties — any network with different keys is a
  # different DHT.  Change requires a new DNA hash (governance decision).
  properties:
    system_coordinator_key:      "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew"
    harmony_record_creator_key:  "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew"
  zomes:
    - name: governance_integrity
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/governance_integrity.wasm"
      dependencies: ~
coordinator:
  zomes:
    - name: governance_coordinator
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/governance_coordinator.wasm"
      dependencies:
        - name: governance_integrity

        ---
manifest_version: "0"
name: researcher_repository
integrity:
  network_seed: ~
  # No properties — single-agent private DNA needs no configuration.
  properties: ~
  zomes:
    - name: researcher_repository_integrity
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/researcher_repository_integrity.wasm"
      dependencies: ~
coordinator:
  zomes:
    - name: researcher_repository_coordinator
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/researcher_repository_coordinator.wasm"
      dependencies:
        - name: researcher_repository_integrity

        ---
manifest_version: "0"
name: validator_workspace
integrity:
  network_seed: ~
  # No properties — single-agent private DNA, one instance per validator.
  properties: ~
  zomes:
    - name: validator_workspace_integrity
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/validator_workspace_integrity.wasm"
      dependencies: ~
coordinator:
  zomes:
    - name: validator_workspace_coordinator
      hash: ~
      path: "../../target/wasm32-unknown-unknown/release/validator_workspace_coordinator.wasm"
      dependencies:
        - name: validator_workspace_integrity

        ---
manifest_version: "0"
name: valichord
description: "ValiChord — credentialed peer validation for scientific reproducibility"

roles:
  - name: attestation
    provisioning:
      strategy: create
      deferred: false
    dna:
      path: "workdir/attestation.dna"
      # DNA modifiers (can be overridden per-player in Tryorama via rolesSettings)
      modifiers:
        properties:
          # Placeholder issuer key — overridden in tests
          authorized_joining_certificate_issuer: "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew"
          discipline: "genomics"
          minimum_validators: 2
        network_seed: "valichord-test"

  - name: researcher_repository
    provisioning:
      strategy: create
      deferred: false
    dna:
      path: "workdir/researcher_repository.dna"
      modifiers:
        network_seed: "valichord-test"

  - name: validator_workspace
    provisioning:
      strategy: create
      deferred: false
    dna:
      path: "workdir/validator_workspace.dna"
      modifiers:
        network_seed: "valichord-test"

  - name: governance
    provisioning:
      strategy: create
      deferred: false
    dna:
      path: "workdir/governance.dna"
      modifiers:
        properties:
          # Placeholder keys — overridden per-player in Tryorama via rolesSettings.
          # In production these are the assembly coordinator and system coordinator keys.
          system_coordinator_key:     "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew"
          harmony_record_creator_key: "uhCAkWCnFzMFO9dSt04H6TcZWiEI3xHQkq1NV0JmqoB9i4p7Zn0Ew"
        network_seed: "valichord-test"

        