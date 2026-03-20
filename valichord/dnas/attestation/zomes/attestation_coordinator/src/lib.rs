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

    // Step 1: write CommitmentAnchor to shared DHT.
    let anchor = CommitmentAnchor {
        request_ref:     input.request_ref.clone(),
        validator:       agent,
        commitment_hash: input.commitment_hash,
    };
    let anchor_hash = create_entry(EntryTypes::CommitmentAnchor(anchor))?;

    let request_ref = input.request_ref;
    let commit_path = Path::from(format!("commitments.{}", request_ref))
        .typed(LinkTypes::RequestToCommitment)?;
    commit_path.ensure()?;
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
