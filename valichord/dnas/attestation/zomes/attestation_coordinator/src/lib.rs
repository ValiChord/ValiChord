use hdk::prelude::*;
use attestation_integrity::{
    AssessmentConfidence, CommitmentAnchor, DifficultyAssessment, DifficultyTier,
    DnaProperties, EntryTypes, LinkTypes, PhaseMarker, ValidatorProfile,
    ValidationAttestation, ValidationRequest,
};
use valichord_shared_types::{Discipline, ValidationPhase, discipline_tag};
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
        "get_validators_for_discipline",
        "get_validator_profile",
        "check_all_commitments_sealed",
        "get_current_phase",
        "get_difficulty_assessment",
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
    Ok(InitCallbackResult::Pass)
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
/// IMMUTABLE after write. post_commit triggers HarmonyRecord assembly.
#[hdk_extern]
pub fn submit_attestation(
    attestation: ValidationAttestation,
) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_initial_pubkey;
    let disc_tag = attestation.discipline_tag();
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

    Ok(attestation_hash)
}

#[hdk_extern]
pub fn publish_validator_profile(
    profile: ValidatorProfile,
) -> ExternResult<ActionHash> {
    let agent = agent_info()?.agent_initial_pubkey;
    let profile_hash = create_entry(EntryTypes::ValidatorProfile(profile))?;
    create_link(agent, profile_hash.clone(), LinkTypes::AgentToProfile, ())?;
    Ok(profile_hash)
}

#[hdk_extern]
pub fn assess_difficulty(
    request_ref: ExternalHash,
) -> ExternResult<ActionHash> {
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
    create_entry(EntryTypes::DifficultyAssessment(assessment))
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn get_validation_request(hash: ActionHash) -> ExternResult<Option<Record>> {
    get(hash, GetOptions::network())
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
                    .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
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
    _discipline: Discipline,
) -> ExternResult<Vec<Record>> {
    Ok(Vec::new())
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
    _request_ref: ExternalHash,
) -> ExternResult<Option<Record>> {
    Ok(None)
}

// ---------------------------------------------------------------------------
// Protocol coordination — commit-reveal
// ---------------------------------------------------------------------------

/// Called by validator's Workspace DNA post_commit via call(OtherRole("attestation")).
/// NOT in Unrestricted cap grant — called under author grant.
#[hdk_extern]
pub fn notify_commitment_sealed(
    request_ref: ExternalHash,
) -> ExternResult<()> {
    let agent = agent_info()?.agent_initial_pubkey;

    // Step 1: write CommitmentAnchor to shared DHT.
    let anchor = CommitmentAnchor {
        request_ref: request_ref.clone(),
        validator:   agent,
    };
    let anchor_hash = create_entry(EntryTypes::CommitmentAnchor(anchor))?;

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
    let props = DnaProperties::try_from_dna_properties()?;
    Ok(commitment_links.len() >= props.minimum_validators as usize)
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

#[hdk_extern(infallible)]
pub fn post_commit(committed_actions: Vec<SignedActionHashed>) {
    for action in committed_actions {
        if let Action::Create(_create) = action.action() {
            // TODO: detect ValidationAttestation entries, check if all
            // attestations for this request are submitted, then call:
            //   call(
            //       CallTargetCell::OtherRole("governance".into()),
            //       "governance_coordinator",
            //       "check_and_create_harmony_record",
            //       None,
            //       request_ref,
            //   )
        }
    }
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
