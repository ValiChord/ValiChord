use hdk::prelude::*;
use attestation_integrity::{
    AgentIdentityAttestation,
    AssessmentConfidence, CommitmentAnchor, CommitmentSealedInput, DifficultyAssessment,
    DifficultyTier, DnaProperties, EntryTypes, LinkTypes, PhaseMarker,
    ResearcherCommitmentInput, ResearcherResultCommitment, ResearcherReveal, ResearcherRevealInput,
    StudyClaim, StudyClaimRelease, ValidatorAgentType, ValidatorProfile, ValidationRequest,
};
use valichord_shared_types::{
    Discipline, JoiningCertificate, ValidatorType, ValidationAttestation, ValidationPhase,
    ValiChordError, ValiChordResult, discipline_tag, metric_results_msgpack_bytes,
};
use sha2::{Digest, Sha256};
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
    if let Err(e) = verify_membrane_proof() {
        return Ok(InitCallbackResult::Fail(e.to_string()));
    }

    Ok(InitCallbackResult::Pass)
}

// ---------------------------------------------------------------------------
// Membrane proof — Ed25519 verification (coordinator-side, HDK only)
// ---------------------------------------------------------------------------

fn verify_membrane_proof() -> ValiChordResult<()> {
    let props = DnaProperties::try_from_dna_properties()?;

    // Dev/test bypass: when the human issuer key is empty the whole credential
    // system is inactive (ai_validator_issuer is also irrelevant).
    if props.authorized_joining_certificate_issuer.is_empty() {
        return Ok(());
    }

    // Find the AgentValidationPkg action on our own source chain (genesis action 2).
    let records = query(ChainQueryFilter::new())?;
    let mut avp_result: Option<Option<MembraneProof>> = None;
    for record in &records {
        if let Action::AgentValidationPkg(avp) = record.action() {
            avp_result = Some(avp.membrane_proof.clone());
            break;
        }
    }
    let proof = avp_result
        .ok_or_else(|| ValiChordError::Guest("AgentValidationPkg not found on source chain".into()))?
        .ok_or_else(|| ValiChordError::Guest("Attestation DNA requires a membrane proof".into()))?;

    // Decode the JoiningCertificate to determine validator_type before choosing
    // which issuer key to verify against.
    let cert = JoiningCertificate::from_proof_bytes(proof.bytes())
        .map_err(|e| ValiChordError::Guest(format!("invalid joining certificate: {e}")))?;

    // Route to the correct issuer key based on validator type:
    //   Human → authorized_joining_certificate_issuer (institutional credential)
    //   AI    → ai_validator_issuer if set, else fall back to the human issuer key
    //           (single-key deployments can reuse one key for both paths).
    let issuer_str = match cert.validator_type {
        ValidatorType::AI if !props.ai_validator_issuer.is_empty() => {
            props.ai_validator_issuer.clone()
        }
        _ => props.authorized_joining_certificate_issuer.clone(),
    };
    let issuer_key = AgentPubKey::from(
        issuer_str
            .parse::<HoloHashB64<hash_type::Agent>>()
            .map_err(|_| ValiChordError::Guest(
                "issuer key in DNA properties is not a valid AgentPubKey".into(),
            ))?,
    );

    // Signed payload = agent raw pubkey bytes (39) || proof meta bytes (if present).
    let joining_agent = agent_info()?.agent_initial_pubkey;
    let mut signed_data: Vec<u8> = joining_agent.get_raw_39().to_vec();
    if proof.bytes().len() > 64 {
        signed_data.extend_from_slice(&proof.bytes()[64..]);
    }

    let signature = Signature::from(cert.signature);
    if !verify_signature(issuer_key, signature, signed_data)? {
        return Err(ValiChordError::Guest(
            "Membrane proof signature is invalid — not signed by the authorized issuer".into(),
        ));
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

    // Idempotency guard: one ValidationRequest per data_hash.
    // ensure() is called once here and reused for link creation below —
    // a second ensure() after create_entry would be a wasted DHT write.
    let study_path = Path::from(format!("study.{}", data_hash))
        .typed(LinkTypes::StudyToValidation)?;
    study_path.ensure()?;
    let existing = get_links(
        LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "A ValidationRequest already exists for this data_hash — \
             each study deposit may only be submitted once".into()
        )));
    }

    let request_hash = create_entry(EntryTypes::ValidationRequest(request))?;

    // study_path already ensure()'d above.
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
    let mut attestation = input.attestation;
    let disc_tag = attestation.discipline_tag();
    let request_ref = attestation.request_ref.clone();

    // Find the CommitmentAnchor written for this agent during the commit phase.
    // Always required — both for hash verification (production) and for embedding
    // commitment_anchor_hash in the stored entry (inductive validation chain).
    // CommitmentAnchors were written during the commit phase (minutes ago) and
    // are in the local DHT cache — Local avoids redundant WebRTC round-trips.
    let commit_path = Path::from(format!("commitments.{}", request_ref))
        .typed(LinkTypes::RequestToCommitment)?;
    let commit_links = get_links(
        LinkQuery::try_new(commit_path.path_entry_hash()?, LinkTypes::RequestToCommitment)?,
        GetStrategy::Local,
    )?;
    let (anchor_action_hash, prior_commitment_hash) = commit_links
        .into_iter()
        .find_map(|link| {
            let hash = link.target.clone().into_action_hash()?;
            let record = get(hash.clone(), GetOptions::local()).ok()??;
            let anchor: CommitmentAnchor = record.entry().to_app_option().ok()??;
            if anchor.validator == agent {
                Some((hash, anchor.commitment_hash))
            } else {
                None
            }
        })
        .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "No CommitmentAnchor found for this validator and study — \
             seal_private_attestation must be committed before reveal".into()
        )))?;

    // Production: verify SHA-256(msgpack(attestation) || nonce) == CommitmentAnchor.commitment_hash.
    // commitment_msgpack_bytes() normalises commitment_anchor_hash to None before serialising,
    // matching exactly what seal_private_attestation hashed in the Validator Workspace.
    //
    // Dev/test bypass: skipped when authorized_joining_certificate_issuer is empty.
    let reveal_props = DnaProperties::try_from_dna_properties()?;
    if !reveal_props.authorized_joining_certificate_issuer.is_empty() {
        let msgpack_bytes = attestation.commitment_msgpack_bytes()?;
        let mut hasher = Sha256::new();
        hasher.update(&msgpack_bytes);
        hasher.update(&input.nonce);
        let computed_hash: Vec<u8> = hasher.finalize().to_vec();

        if computed_hash != prior_commitment_hash {
            return Err(wasm_error!(WasmErrorInner::Guest(
                "Hash mismatch — attestation and nonce do not match the previously \
                 committed hash. The reveal must be identical to the sealed commit.".into()
            )));
        }
    }

    // Inject CommitmentAnchor ActionHash for inductive validation chain.
    attestation.commitment_anchor_hash = Some(anchor_action_hash);

    // Duplicate submission guard: O(1) — tag-prefix query returns non-empty
    // iff this agent has already attested for this study.  The 39-byte
    // request_ref is stored as the link tag so no entry fetch is needed.
    // Local is safe: if we attested before, the link is in our own source chain.
    let dup_links = get_links(
        LinkQuery::try_new(agent.clone(), LinkTypes::ValidatorToAttestation)?
            .tag_prefix(LinkTag::new(request_ref.as_ref().to_vec())),
        GetStrategy::Local,
    )?;
    if !dup_links.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Validator has already submitted an attestation for this study — \
             duplicate reveals are not permitted".into()
        )));
    }

    // Commitment verified — write the public attestation (move: not used after this).
    let attestation_hash =
        create_entry(EntryTypes::ValidationAttestation(attestation))?;

    // Tag = request_ref bytes — enables O(1) duplicate check and O(1) per-validator
    // lookup in get_attestations_for_request without deserializing entries.
    create_link(
        agent,
        attestation_hash.clone(),
        LinkTypes::ValidatorToAttestation,
        LinkTag::new(request_ref.as_ref().to_vec()),
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

    // Attempt to finalise the round.  A failed governance call does not
    // invalidate the attestation itself.  Emit FinalizationFailed so the
    // local UI can surface a retry path (e.g. prompt for force_finalize_round).
    if !call_governance_fire_and_forget(
        "check_and_create_harmony_record",
        request_ref.clone(),
    ) {
        let _ = emit_signal(&Signal::FinalizationFailed { request_ref });
    }

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
    let existing: Option<ValidatorProfile> = get_latest_validator_profile(agent.clone())?;

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
    Ok(get_latest_validator_profile(agent)?.and_then(|p| p.agent_type))
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

    // Idempotency guard: one assessment per (assessor, study).
    // Without this, any credentialed agent could continuously overwrite the
    // difficulty estimate, affecting which validators choose to claim the study.
    // link.author is set by the DHT host — no entry fetch needed.
    let caller = agent_info()?.agent_initial_pubkey;
    let existing = get_links(
        LinkQuery::try_new(input.request_ref.clone(), LinkTypes::DifficultyPath)?,
        GetStrategy::Network,
    )?;
    if existing.iter().any(|l| l.author == caller) {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "A difficulty assessment already exists for this study from this assessor — \
             one assessment per assessor is permitted".into()
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
    // max_by_key(timestamp) is deterministic under concurrent gossip;
    // first() is DHT-order-dependent and unreliable if two requests share the same path.
    match links.iter().max_by_key(|l| l.timestamp) {
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
// Warrant gating
// ---------------------------------------------------------------------------

/// Reject the calling agent if they have any outstanding warrants.
///
/// Called at coordinator entry points only — never inside validate(), which
/// must not make network calls.  Warranted agents can still write ops to the
/// DHT; this gate controls whether ValiChord accepts them into protocol flow.
fn reject_if_warranted(agent: &AgentPubKey) -> ExternResult<()> {
    let activity = get_agent_activity(
        agent.clone(),
        ChainQueryFilter::new(),
        ActivityRequest::Full,
    )?;
    if !activity.warrants.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Agent has outstanding warrants — protocol participation refused".into()
        )));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Validator self-assignment (current model)
// ---------------------------------------------------------------------------
//
// Current design: pull-based, human-initiated.
//   Validators browse `get_pending_requests_for_discipline` and voluntarily
//   call `claim_study` to self-assign.  Conflict-of-interest checks (shared
//   institution with the researcher) are enforced by `validate()` at the
//   network layer; capacity limits are enforced here in the coordinator.
//
// ---------------------------------------------------------------------------
// FUTURE DESIGN DIRECTION — AI validator pool with random selection
// ---------------------------------------------------------------------------
//
// When AI validators become the primary validation path, the pull model above
// would be replaced (or supplemented) by a push-based pool-draw:
//
//   1. Volunteer nodes join the pool.
//      Any operator downloads the ValiChord validator installer — a bundled
//      package that includes the Holochain conductor, a pre-configured AI
//      analysis pipeline, and this hApp.  On startup the node registers via
//      a membrane proof (issued automatically by the onboarding service) with
//      `validator_type = AI` and an issuer-granted `CertificationTier`.  No
//      institutional affiliation is required — independence comes from pool
//      diversity rather than credentialing.
//
//   2. Studies trigger a pool draw.
//      When a researcher submits a `ValidationRequest`, the protocol randomly
//      selects `num_validators_required` AI nodes from the live pool instead
//      of waiting for volunteers to claim.  "Live" means the node's profile
//      is present on the DHT and no recent warrant has been issued against it.
//      Randomness must be derived from a seed that no single party controls
//      (e.g. the request's data_hash XOR a VDF output, or a commit-reveal
//      scheme among a small quorum of seed contributors).
//
//   3. Selected nodes receive a remote signal.
//      The requesting conductor sends a `recv_remote_signal` to each selected
//      node's cell, carrying the `request_ref`.  The AI pipeline wakes, fetches
//      the deposit, runs analysis, seals its private attestation, and calls
//      `notify_commitment_sealed` — all without human interaction.
//
//   4. Independence guarantee.
//      Because volunteers are anonymous, geographically distributed, and
//      randomly drawn per round, no single actor can bias the validator set.
//      The AI does the computational work; the volunteer provides the
//      independent execution environment.  Institutional diversity (the
//      current basis for COI checks) is replaced by operational diversity
//      across the volunteer pool.
//
// Implementation prerequisites before this can replace the current model:
//   - A "live pool" index (e.g. a DHT path updated by periodic heartbeat links,
//     with stale entries pruned by `reclaim_abandoned_claim`-style timeout logic).
//   - A provably fair on-chain randomness scheme for the pool draw.
//   - The ValiChord installer bundling the AI pipeline alongside the conductor.
//   - Revision of the COI validation rule in `attestation_integrity` to skip
//     institution checks for `validator_type = AI` profiles.
//
// Until these prerequisites are met, the pull model below remains in use.
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
pub fn claim_study(request_ref: ExternalHash) -> ExternResult<Option<ActionHash>> {
    let agent = agent_info()?.agent_initial_pubkey;
    reject_if_warranted(&agent)?;

    // Resolve the ValidationRequest ActionHash from the study path.
    let (vr_action_hash, vr) = {
        let study_path = Path::from(format!("study.{}", request_ref))
            .typed(LinkTypes::StudyToValidation)?;
        let links = get_links(
            LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
            GetStrategy::Network,
        )?;
        // max_by_key(timestamp) is deterministic under concurrent gossip;
        // first() is DHT-order-dependent if two requests share the same path.
        let link = links.iter().max_by_key(|l| l.timestamp).ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
            "No ValidationRequest found for this data_hash — submit_validation_request first"
                .into(),
        )))?;
        let hash = link.target.clone().into_action_hash().ok_or_else(|| {
            wasm_error!(WasmErrorInner::Guest(
                "StudyToValidation link target is not an ActionHash".into(),
            ))
        })?;
        let record = match get(hash.clone(), GetOptions::network())? {
            Some(r) => r,
            None => return Ok(None), // record not yet propagated — caller should retry
        };
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

    // Fetch all released claim hashes for this study in one call, then count
    // active claims in memory — 2 network calls instead of N+1.
    let release_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToRelease)?,
        GetStrategy::Network,
    )?;
    let released: HashSet<ActionHash> = release_links
        .iter()
        .filter_map(|l| (l.tag.0.len() == 39).then(|| ActionHash::from_raw_39(l.tag.0.clone())))
        .collect();

    let claim_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    let mut active_claim_count = 0usize;
    let mut already_claimed = false;
    for link in &claim_links {
        if let Some(claim_hash) = link.target.clone().into_action_hash() {
            if !released.contains(&claim_hash) {
                active_claim_count += 1;
                if link.author == agent {
                    already_claimed = true;
                }
            }
        }
    }
    if active_claim_count >= vr.num_validators_required as usize {
        return Err(wasm_error!(WasmErrorInner::Guest(format!(
            "Study is at capacity ({}/{} validators already claimed)",
            active_claim_count,
            vr.num_validators_required,
        ))));
    }
    if already_claimed {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Validator has already claimed this study".into(),
        )));
    }

    // Resolve the validator's institution from their profile.
    let validator_institution = get_latest_validator_profile(agent.clone())?
        .map(|p| p.institution)
        .unwrap_or_default();

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

    Ok(Some(claim_hash))
}

/// Release a previously claimed study.
///
/// Vacates the calling validator's claim on a study.
///
/// `RequestToClaim` / `ValidatorToClaim` links are immutable (prevents
/// self-retraction for colluder benefit), so the slot is freed by writing a
/// `StudyClaimRelease` marker and a `ClaimToRelease` link.  Query functions
/// and the `claim_study` capacity check skip claims that have this marker.
/// The `StudyClaim` entry itself remains on the DHT as a permanent audit record.
#[hdk_extern]
pub fn release_claim(request_ref: ExternalHash) -> ExternResult<()> {
    let agent = agent_info()?.agent_initial_pubkey;

    let request_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    // Each claim release is three create_link calls after a create_entry.
    // Holochain has no transactions — if a link write fails mid-release, the
    // StudyClaimRelease entry is on the DHT but the ClaimToRelease link may be
    // absent, leaving the claim appearing live.  A retry of release_claim is
    // safe: create_entry is content-addressed and idempotent; create_link
    // retries will eventually succeed.  Guard 1 in notify_commitment_sealed
    // uses ValidatorToRelease links (written last) as the authoritative release
    // signal — a partial write therefore never permits a phantom commitment.
    for link in request_links.iter().filter(|l| l.author == agent) {
        if let Some(claim_hash) = link.target.clone().into_action_hash() {
            // Skip if already released.
            let existing = get_links(
                LinkQuery::try_new(claim_hash.clone(), LinkTypes::ClaimToRelease)?,
                GetStrategy::Network,
            )?;
            if existing.is_empty() {
                let release_hash = create_entry(EntryTypes::StudyClaimRelease(
                    StudyClaimRelease { claim_hash: claim_hash.clone() },
                ))?;
                let claim_tag = claim_hash.get_raw_39().to_vec();
                create_link(claim_hash, release_hash.clone(), LinkTypes::ClaimToRelease, ())?;
                // Batch-query indexes: one call per study/agent instead of per claim.
                create_link(request_ref.clone(), release_hash.clone(), LinkTypes::RequestToRelease, claim_tag.clone())?;
                create_link(agent.clone(), release_hash, LinkTypes::ValidatorToRelease, claim_tag)?;
            }
        }
    }

    Ok(())
}

/// Return all active (non-released) StudyClaim records for a given study.
#[hdk_extern]
pub fn get_claims_for_request(request_ref: ExternalHash) -> ExternResult<Vec<Record>> {
    // One call for releases, one call for claims — filter in memory.
    let release_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::RequestToRelease)?,
        GetStrategy::Network,
    )?;
    let released: HashSet<ActionHash> = release_links
        .iter()
        .filter_map(|l| (l.tag.0.len() == 39).then(|| ActionHash::from_raw_39(l.tag.0.clone())))
        .collect();

    let claim_links = get_links(
        LinkQuery::try_new(request_ref, LinkTypes::RequestToClaim)?,
        GetStrategy::Network,
    )?;
    let mut records = Vec::new();
    for link in claim_links {
        if let Some(claim_hash) = link.target.into_action_hash() {
            if !released.contains(&claim_hash) {
                if let Some(record) = get(claim_hash, GetOptions::network())? {
                    records.push(record);
                }
            }
        }
    }
    Ok(records)
}

/// Return all active (non-released) studies this validator has claimed.
#[hdk_extern]
pub fn get_my_claimed_studies(_: ()) -> ExternResult<Vec<Record>> {
    let agent = agent_info()?.agent_initial_pubkey;
    // One call for releases, one call for claims — filter in memory.
    let release_links = get_links(
        LinkQuery::try_new(agent.clone(), LinkTypes::ValidatorToRelease)?,
        GetStrategy::Network,
    )?;
    let released: HashSet<ActionHash> = release_links
        .iter()
        .filter_map(|l| (l.tag.0.len() == 39).then(|| ActionHash::from_raw_39(l.tag.0.clone())))
        .collect();

    let claim_links = get_links(
        LinkQuery::try_new(agent, LinkTypes::ValidatorToClaim)?,
        GetStrategy::Network,
    )?;
    let mut records = Vec::new();
    for link in claim_links {
        if let Some(claim_hash) = link.target.into_action_hash() {
            if !released.contains(&claim_hash) {
                if let Some(record) = get(claim_hash, GetOptions::network())? {
                    records.push(record);
                }
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
/// for this study.  Writes a `StudyClaimRelease` marker so the slot is treated
/// as free by `get_claims_for_request` and `claim_study`.
/// `RequestToClaim` / `ValidatorToClaim` links are immutable and remain on the
/// DHT as a permanent audit record alongside the original `StudyClaim` entry.
///
/// Returns `true` if the slot was reclaimed, `false` if ineligible.
///
/// NOTE: `false` conflates three distinct conditions — claim too recent,
/// validator already attested, and claim already released.  A future API
/// version should return a typed enum (Reclaimed / TooRecent / AlreadyResolved
/// / NotFound) so callers can distinguish "retry later" from "no action needed".
/// Changing the return type is a breaking API change and is deferred to Phase 1.
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

    // 4. Write a StudyClaimRelease marker to vacate the abandoned slot.
    //    RequestToClaim / ValidatorToClaim links are immutable, so the soft-delete
    //    marker is the only way to free capacity.  Query functions and claim_study
    //    skip claims that carry this marker.
    let existing_release = get_links(
        LinkQuery::try_new(input.claim_hash.clone(), LinkTypes::ClaimToRelease)?,
        GetStrategy::Network,
    )?;
    if existing_release.is_empty() {
        let release_hash = create_entry(EntryTypes::StudyClaimRelease(
            StudyClaimRelease { claim_hash: input.claim_hash.clone() },
        ))?;
        let claim_tag = input.claim_hash.get_raw_39().to_vec();
        create_link(input.claim_hash.clone(), release_hash.clone(), LinkTypes::ClaimToRelease, ())?;
        // Batch-query indexes: one call per study/agent instead of per claim.
        create_link(input.request_ref.clone(), release_hash.clone(), LinkTypes::RequestToRelease, claim_tag.clone())?;
        create_link(absent_validator, release_hash, LinkTypes::ValidatorToRelease, claim_tag)?;
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

    // Each RequestToCommitment link is authored by the validator themselves —
    // link.author IS the validator pubkey. No per-anchor get() needed, saving
    // N network round-trips (one per validator) compared to fetching each
    // CommitmentAnchor entry to extract the validator field.
    let request_tag = LinkTag::new(request_ref.as_ref().to_vec());
    let mut attestations = Vec::new();
    for link in commit_links {
        let att_links = get_links(
            LinkQuery::try_new(link.author, LinkTypes::ValidatorToAttestation)?
                .tag_prefix(request_tag.clone()),
            GetStrategy::Network,
        )?;
        for att_link in att_links {
            let att_hash = match att_link.target.into_action_hash() {
                Some(h) => h,
                None => continue,
            };
            if let Some(record) = get(att_hash, GetOptions::network())? {
                attestations.push(record);
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
    // Every update_validator_profile call creates a new discipline-path link without
    // removing old ones, so the index accumulates historical versions. Group by
    // authoring agent and keep only the latest (newest action timestamp) per agent.
    let all_records = records_for_links(links)?;
    let mut latest_by_agent: std::collections::HashMap<AgentPubKey, Record> =
        std::collections::HashMap::new();
    for record in all_records {
        let author = record.action().author().clone();
        let ts = record.action().timestamp();
        let is_newer = latest_by_agent
            .get(&author)
            .map(|existing| ts > existing.action().timestamp())
            .unwrap_or(true);
        if is_newer {
            latest_by_agent.insert(author, record);
        }
    }
    Ok(latest_by_agent.into_values().collect())
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
    // Hard cap — prevents a single query from stalling a node on a popular
    // discipline and closes a DoS surface. Pagination is Phase 1 work.
    const MAX_RESULTS: usize = 500;
    records_for_links(links.into_iter().take(MAX_RESULTS).collect())
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
    // Return the most recently created assessment (max by timestamp is
    // deterministic under concurrent gossip; last() is DHT-order-dependent).
    match links.iter().max_by_key(|l| l.timestamp) {
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
    reject_if_warranted(&agent)?;
    let request_ref = input.request_ref.clone();

    // Phase gate: reject commitments after RevealOpen is already written.
    // Prevents a validator who claims a freed slot post-RevealOpen from writing
    // a CommitmentAnchor and potentially including their attestation in the
    // HarmonyRecord before it is finalised.
    if let Some(ValidationPhase::RevealOpen) = get_current_phase(request_ref.clone())? {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "Cannot commit after the reveal phase has opened — \
             the commitment window is closed for this study".into()
        )));
    }

    // Guard 3 (moved first): one commitment per validator per study.
    // Single path lookup — much cheaper than Guard 1's O(n) claim scan.
    // Catches the common duplicate-retry case before any per-claim DHT reads.
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

    // Guard 1: agent must hold a LIVE (unreleased) StudyClaim for this study.
    // Prevents non-claimants from inflating the commitment count and
    // potentially triggering RevealOpen with phantom commitments.
    //
    // IMPORTANT: StudyClaim entries are immutable — a released claim still
    // exists on the DHT.  This check therefore also fetches ValidatorToRelease
    // links and excludes any claim that has a matching release marker.
    // Without this exclusion a validator who called release_claim() could still
    // pass this guard and write a phantom CommitmentAnchor that would count
    // toward the quorum and prematurely open the reveal window.
    //
    // Dev/test bypass: skipped when authorized_joining_certificate_issuer is
    // empty (same pattern as the membrane-proof bypass).  In production the
    // issuer key is always set, so the check is always enforced.
    let guard1_props = DnaProperties::try_from_dna_properties()?;
    if !guard1_props.authorized_joining_certificate_issuer.is_empty() {
        // Build the released-claim set once — same pattern as get_my_claimed_studies.
        // Link tags are the 39-byte raw ActionHash of the released claim.
        let release_links = get_links(
            LinkQuery::try_new(agent.clone(), LinkTypes::ValidatorToRelease)?,
            GetStrategy::Network,
        )?;
        let released: HashSet<ActionHash> = release_links
            .iter()
            .filter_map(|l| {
                (l.tag.0.len() == 39).then(|| ActionHash::from_raw_39(l.tag.0.clone()))
            })
            .collect();

        let claim_links = get_links(
            LinkQuery::try_new(agent.clone(), LinkTypes::ValidatorToClaim)?,
            GetStrategy::Network,
        )?;
        let has_valid_claim = claim_links.into_iter().any(|link| {
            let claim_hash = match link.target.clone().into_action_hash() {
                Some(h) => h,
                None => return false,
            };
            if released.contains(&claim_hash) {
                return false; // Released — does not count as a live claim.
            }
            get(claim_hash, GetOptions::network())
                .ok()
                .flatten()
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

    // Guard 2: researcher must have published their commitment before any
    // validator commits.  Ensures result pre-registration precedes all
    // validation work, preventing the retroactive oracle attack where a
    // researcher reads all validator reveals and crafts matching metrics.
    // Dev/test bypass: skipped when authorized_joining_certificate_issuer is
    // empty (same pattern as Guard 1 and the hash-verification bypass).
    if !guard1_props.authorized_joining_certificate_issuer.is_empty() {
        if get_researcher_commitment(request_ref.clone())?.is_none() {
            return Err(wasm_error!(WasmErrorInner::Guest(
                "Researcher must publish their result commitment (publish_researcher_commitment) \
                 before validators may seal a commitment — this ensures the researcher's expected \
                 result is pre-registered before validators begin work".into()
            )));
        }
    }

    // Step 1: resolve the ValidationRequest ActionHash for the inductive chain.
    // study.{request_ref} is written by submit_validation_request and should
    // be in the local DHT store by the time any validator commits (the
    // researcher always submits the request before validators can claim).
    // Using Local avoids a network round-trip; falls back gracefully to an
    // error if the entry hasn't gossiped yet (caller can retry).
    let vr_action_hash: ActionHash = {
        let study_path = Path::from(format!("study.{}", request_ref))
            .typed(LinkTypes::StudyToValidation)?;
        let links = get_links(
            LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
            GetStrategy::Local,
        )?;
        links.iter().max_by_key(|l| l.timestamp)
            .and_then(|l| l.target.clone().into_action_hash())
            .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                "No ValidationRequest found for this study — \
                 call submit_validation_request before sealing a commitment".into(),
            )))?
    };

    // Step 2: write CommitmentAnchor to shared DHT.
    let anchor = CommitmentAnchor {
        request_ref:             request_ref.clone(),
        validator:               agent.clone(),
        commitment_hash:         input.commitment_hash,
        validation_request_hash: vr_action_hash,
    };
    let anchor_hash = create_entry(EntryTypes::CommitmentAnchor(anchor))?;

    create_link(commit_anchor, anchor_hash, LinkTypes::RequestToCommitment, ())?;

    // Step 3: check if all validators have now committed.
    // Use check_all_commitments_sealed_inner which reads the per-study
    // num_validators_required from the ValidationRequest.  The DNA-level
    // minimum_validators is a floor constraint, not the quorum target —
    // using it here would open reveal prematurely when a researcher requests
    // more validators than the DNA minimum.
    if check_all_commitments_sealed_inner(request_ref.clone()).unwrap_or(false) {
        let phase_path = Path::from(format!("phase.{}", request_ref))
            .typed(LinkTypes::RequestToPhaseMarker)?;
        phase_path.ensure()?;

        // Idempotency guard: two validators committing simultaneously both see
        // quorum met and race to write the PhaseMarker.  Check first so only
        // one link is ever written.  The entry itself is content-addressed so
        // a concurrent write would collapse to the same hash; the link table
        // is the only thing that could accumulate duplicates.
        let existing_phase = get_links(
            LinkQuery::try_new(phase_path.path_entry_hash()?, LinkTypes::RequestToPhaseMarker)?,
            GetStrategy::Network,
        )?;
        // Non-atomic TOCTOU: two validators detecting quorum simultaneously can
        // both reach this branch and each write a RequestToPhaseMarker link.
        // Content-addressing ensures both links point to the same PhaseMarker
        // entry hash (identical content → identical hash), so the protocol
        // remains correct with two links.  Any future code that assumes exactly
        // one PhaseMarker link per study must account for this.
        if existing_phase.is_empty() {
            let marker = PhaseMarker {
                request_ref: request_ref.clone(),
                phase:       ValidationPhase::RevealOpen,
            };
            let marker_hash = create_entry(EntryTypes::PhaseMarker(marker))?;
            create_link(
                phase_path.path_entry_hash()?,
                marker_hash,
                LinkTypes::RequestToPhaseMarker,
                (),
            )?;
        }

        // Signals fire regardless of who wrote the PhaseMarker — best-effort
        // UI notifications, not protocol gates.  Validators may be offline;
        // DHT state is always the authoritative source of truth.
        let reveal_signal = Signal::RevealOpen { request_ref: request_ref.clone() };
        emit_signal(&reveal_signal)?;

        // Collect pubkeys of the other committed validators (all commits
        // excluding the current agent, who already got the local signal).
        let others: Vec<AgentPubKey> = existing_links.iter()
            .filter(|l| l.author != agent)
            .map(|l| l.author.clone())
            .collect();
        if !others.is_empty() {
            // Send a flat struct — not the Signal enum — to avoid rmp-serde
            // adjacently-tagged enum round-trip failure in recv_remote_signal.
            if let Ok(bytes) = ExternIO::encode(&RevealOpenWire { request_ref: request_ref.clone() }) {
                let _ = send_remote_signal(bytes, others);
            }
        }
    }

    Ok(())
}

/// Poll the current protocol phase for a request.
/// Returns None if no PhaseMarker exists yet (commit phase still in progress).
/// Engineering constraint #1: phase transitions are DHT-poll-driven.
#[hdk_extern]
/// Returns `None` for two distinct conditions: (1) the study is still in the
/// commit phase — no PhaseMarker has been written yet, and (2) the
/// ValidationRequest hasn't fully propagated to this node yet.  UI code that
/// polls this immediately after study submission should treat `None` as
/// "commit phase or not yet visible" and not surface it as an error.  Always
/// cross-check with `check_all_commitments_sealed()` for a protocol-level gate.
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
    match links.iter().max_by_key(|l| l.timestamp) {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid phase link target".into()
                )))?;
            let record = match get(target, GetOptions::network())? {
                Some(r) => r,
                None => return Ok(None), // not yet propagated — caller should retry
            };
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

    // Authorship check: only the researcher who submitted the study may publish
    // its commitment.  Without this, any credentialed agent could pre-empt the
    // researcher, write a fake hash, and permanently block the real commitment
    // (the idempotency guard above then rejects the researcher's own call).
    // Dev/test bypass: skipped when authorized_joining_certificate_issuer is empty.
    // PRODUCTION: this key MUST be set — without it any agent can hijack any study.
    {
        let props = DnaProperties::try_from_dna_properties()?;
        if !props.authorized_joining_certificate_issuer.is_empty() {
            let caller = agent_info()?.agent_initial_pubkey;
            let study_path = Path::from(format!("study.{}", input.request_ref))
                .typed(LinkTypes::StudyToValidation)?;
            let vr_links = get_links(
                LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
                GetStrategy::Network,
            )?;
            let researcher = vr_links
                .iter()
                .max_by_key(|l| l.timestamp)
                .and_then(|l| l.target.clone().into_action_hash())
                .and_then(|h| get(h, GetOptions::network()).ok().flatten())
                .map(|r| r.action().author().clone());
            match researcher {
                Some(r) if r != caller => {
                    return Err(wasm_error!(WasmErrorInner::Guest(
                        "Only the researcher who submitted this study may publish its commitment".into()
                    )));
                }
                None => {
                    return Err(wasm_error!(WasmErrorInner::Guest(
                        "ValidationRequest not found — cannot verify researcher identity".into()
                    )));
                }
                _ => {}
            }
        }
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
    match links.iter().max_by_key(|l| l.timestamp) {
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
    // Local is safe: if we already revealed, the link is in our local DHT store.
    let existing_reveal_links = get_links(
        LinkQuery::try_new(reveal_anchor.clone(), LinkTypes::RequestToResearcherReveal)?,
        GetStrategy::Local,
    )?;
    if !existing_reveal_links.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "A researcher reveal already exists for this study — \
             the reveal cannot be published more than once".into()
        )));
    }

    // Gate: only the researcher who submitted the study may reveal its result.
    // Any credentialed agent can call this function, so we verify the caller
    // matches the author of the original ValidationRequest.
    // Dev/test bypass: skipped when authorized_joining_certificate_issuer is
    // empty (same pattern as the claim gate and hash-verification bypass).
    // PRODUCTION: authorized_joining_certificate_issuer MUST be set in the DNA
    // properties — without it, any agent can publish a researcher reveal.
    {
        let reveal_props = DnaProperties::try_from_dna_properties()?;
        if !reveal_props.authorized_joining_certificate_issuer.is_empty() {
            let caller = agent_info()?.agent_initial_pubkey;
            let study_path = Path::from(format!("study.{}", input.request_ref))
                .typed(LinkTypes::StudyToValidation)?;
            // VR was written at study submission (minutes ago) — Local is safe.
            let vr_links = get_links(
                LinkQuery::try_new(study_path.path_entry_hash()?, LinkTypes::StudyToValidation)?,
                GetStrategy::Local,
            )?;
            let researcher = vr_links
                .iter().max_by_key(|l| l.timestamp)
                .and_then(|l| l.target.clone().into_action_hash())
                .and_then(|h| get(h, GetOptions::network()).ok().flatten())
                .map(|r| r.action().author().clone());
            match researcher {
                Some(r) if r != caller => {
                    return Err(wasm_error!(WasmErrorInner::Guest(
                        "Only the researcher who submitted this study may reveal the result".into()
                    )));
                }
                None => {
                    return Err(wasm_error!(WasmErrorInner::Guest(
                        "ValidationRequest not found — cannot verify researcher identity".into()
                    )));
                }
                _ => {}
            }
        }
    }

    // Gate: phase must be RevealOpen (set by the last committing validator's
    // post_commit, which verified all commitments were sealed before writing it).
    // Trusting the PhaseMarker avoids a redundant link-count query that races
    // with gossip propagation and would give a false "not all committed" error.
    match get_current_phase(input.request_ref.clone())? {
        Some(ValidationPhase::RevealOpen) => {}
        Some(other) => {
            return Err(wasm_error!(WasmErrorInner::Guest(format!(
                "Cannot reveal — protocol is in phase {other:?}, expected RevealOpen"
            ))));
        }
        None => {
            return Err(wasm_error!(WasmErrorInner::Guest(
                "Cannot reveal — phase not yet set (validators may not have committed yet)".into()
            )));
        }
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
    // Uses metric_results_msgpack_bytes() — same SerializedBytes encoding as
    // commitment_msgpack_bytes() — so both hash paths stay byte-for-byte consistent.
    let msgpack_bytes: Vec<u8> = metric_results_msgpack_bytes(&input.metrics)?;
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
    match links.iter().max_by_key(|l| l.timestamp) {
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
pub fn recv_remote_signal(signal: ExternIO) -> ExternResult<()> {
    // Remote signals arrive double-encoded: ExternIO.0 = bin8(payload_msgpack).
    // Step 1: strip the outer bin8 to get the flat-struct bytes.
    let inner_bytes: Vec<u8> = signal.decode().map_err(|e| {
        wasm_error!(WasmErrorInner::Deserialize(e.to_string().into_bytes()))
    })?;
    // Step 2: decode as RevealOpenWire (plain struct) — avoids rmp-serde
    // adjacently-tagged enum round-trip failure — then re-emit as Signal.
    let wire: RevealOpenWire = rmp_serde::from_slice(&inner_bytes).map_err(|e| {
        wasm_error!(WasmErrorInner::Deserialize(e.to_string().into_bytes()))
    })?;
    emit_signal(Signal::RevealOpen { request_ref: wire.request_ref })?;
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
/// post_commit MUST NOT write data (Holochain constraint). Currently a no-op.
///
/// WARNING for future developers: any side effects added here are fire-and-forget —
/// failures are caught by the `post_commit` wrapper and logged at DEBUG only.
/// If you add cross-DNA calls or signal emissions, emit a local Signal variant
/// on failure so callers have a recovery path (see validator_workspace Signal::CommitmentNotifyFailed).
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

/// Fetch the most recently published ValidatorProfile for `agent`, or None.
///
/// Walks AgentToProfile links (sorted by the 8-byte big-endian microsecond
/// timestamp tag), fetches the highest-timestamp target, and deserializes.
/// Old links without a tag return i64::MIN from profile_link_ts() and always
/// lose — backwards-compatible.
fn get_latest_validator_profile(agent: AgentPubKey) -> ExternResult<Option<ValidatorProfile>> {
    let links = get_links(
        LinkQuery::try_new(agent, LinkTypes::AgentToProfile)?,
        GetStrategy::Network,
    )?;
    Ok(links
        .iter()
        .max_by_key(|l| profile_link_ts(l))
        .and_then(|l| l.target.clone().into_action_hash())
        .and_then(|h| get(h, GetOptions::network()).ok().flatten())
        .and_then(|r| r.entry().to_app_option::<ValidatorProfile>().ok().flatten()))
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
// Cross-DNA call helpers
// ---------------------------------------------------------------------------

/// Fire-and-forget call to the governance coordinator.
///
/// Symmetric to `call_attestation_zome_opt` in `governance_coordinator` —
/// but intentionally discards the result.  A failed governance call does not
/// invalidate the caller's own write; the governance DNA will be retried by
/// the next validator who calls `submit_attestation`.
///
/// Inspired by ad4m's `send_broadcast` / `send_signal` distinction.
/// Returns `true` if governance responded Ok, `false` on any failure.
/// Callers should emit a `Signal::FinalizationFailed` when this returns `false`
/// so the local UI can surface a retry path.
fn call_governance_fire_and_forget(
    fn_name: &str,
    input: impl serde::Serialize + std::fmt::Debug,
) -> bool {
    match call(
        CallTargetCell::OtherRole("governance".into()),
        ZomeName::from("governance_coordinator"),
        FunctionName::from(fn_name),
        None,
        input,
    ) {
        Ok(ZomeCallResponse::Ok(_)) => true,
        Ok(other) => {
            warn!(
                "call_governance_fire_and_forget({fn_name}): non-Ok response — \
                 round finalisation may be stuck: {:?}",
                other
            );
            false
        }
        Err(e) => {
            warn!(
                "call_governance_fire_and_forget({fn_name}): call failed — \
                 round finalisation may be stuck: {:?}",
                e
            );
            false
        }
    }
}

// ---------------------------------------------------------------------------
// Signal types
// ---------------------------------------------------------------------------
//
// All signals emitted by this DNA use the adjacent-tag serde encoding so the
// JS side sees `{ type: "RevealOpen", content: { request_ref: "uhCEk..." } }`.
// This mirrors the Discipline / AttestationOutcome enum encoding convention.
//
// Two emission paths:
//   • emit_signal(...)     — local only (the agent whose zome call just ran)
//   • send_remote_signal   — fire-and-forget push to other committed validators
//
// The receiving end is recv_remote_signal below, which simply re-emits locally
// so the receiving agent's UI / AppWebsocket subscriber sees the same payload.

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", content = "content")]
pub enum Signal {
    /// Emitted locally AND sent to all other committed validators the moment
    /// the reveal window opens (every required validator has committed).
    /// UI note: NOT a protocol gate — always verify via get_current_phase()
    /// or check_all_commitments_sealed().  Signals can be lost.
    RevealOpen { request_ref: ExternalHash },
    /// Emitted locally when the governance cross-DNA call fails after a
    /// successful submit_attestation.  The attestation IS written to the DHT;
    /// only round finalisation is affected.  The UI should prompt the user to
    /// retry via force_finalize_round or wait for another validator's reveal
    /// to trigger a retry.  Signals can be lost — always poll DHT state to confirm.
    FinalizationFailed { request_ref: ExternalHash },
}

/// Flat struct used as the over-the-wire payload for remote signals.
///
/// rmp-serde's deserializer does not reliably round-trip adjacently-tagged
/// enums (Signal) — it fails with "invalid type: map, expected a sequence"
/// because the generated Deserialize impl calls deserialize_seq for struct
/// variant content even when the bytes are in named (map) format.  A plain
/// struct round-trips correctly.  recv_remote_signal converts back to Signal.
#[derive(Debug, Serialize, Deserialize)]
struct RevealOpenWire {
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

    // Duplicate check: tag-prefix query — O(1), no get() calls needed.
    // Links are created with the other agent's raw bytes as the tag (see below),
    // so a non-empty result means this pair is already attested.
    let other_tag = LinkTag::new(input.other_agent.get_raw_39().to_vec());
    let existing = get_links(
        LinkQuery::try_new(caller.clone(), LinkTypes::AgentToIdentityAttestation)?
            .tag_prefix(other_tag),
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Err(wasm_error!(WasmErrorInner::Guest(
            "An AgentIdentityAttestation for this pair already exists — \
             revoke the existing one before creating a new link".into()
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

    // Symmetric links tagged with the OTHER agent's raw bytes — enables the
    // O(1) tag-prefix duplicate check in link_agent_identity.
    create_link(
        att.agent_a.clone(),
        hash.clone(),
        LinkTypes::AgentToIdentityAttestation,
        LinkTag::new(att.agent_b.get_raw_39().to_vec()),
    )?;
    create_link(
        att.agent_b.clone(),
        hash.clone(),
        LinkTypes::AgentToIdentityAttestation,
        LinkTag::new(att.agent_a.get_raw_39().to_vec()),
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
