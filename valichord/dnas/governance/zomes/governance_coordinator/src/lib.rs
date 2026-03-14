use hdk::prelude::*;
use governance_integrity::{
    BadgeType, EntryTypes, HarmonyRecord, LinkTypes,
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
    for fn_name in &[
        "get_harmony_record",
        "get_harmony_records_by_discipline",
        "get_validator_reputation",
        "get_badges_for_study",
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

/// Idempotent — called from DNA 3 post_commit (may fire multiple times).
///
/// Algorithm:
///   1. Check if a HarmonyRecord already exists for request_ref — if yes, return None.
///   2. Call get_attestations_for_request on the attestation role.
///   3. If no attestations, return None (not yet ready).
///   4. Derive majority outcome, agreement level, participating validators.
///   5. Create HarmonyRecord, index via RequestToHarmonyRecord + DisciplinePath.
///   6. Issue badge if thresholds are met.
///   7. Update reputation for each validator.
#[hdk_extern]
pub fn check_and_create_harmony_record(
    request_ref: ExternalHash,
) -> ExternResult<Option<ActionHash>> {
    // --- 1. Idempotency check: bail early if record already exists ----------
    let anchor_key = anchor_for_request(&request_ref)?;
    let existing = get_links(
        LinkQuery::try_new(
            anchor_key.clone(),
            LinkTypes::RequestToHarmonyRecord,
        )?,
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Ok(None);
    }

    // --- 2. Fetch attestations from DNA 3 -----------------------------------
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

    // --- 3. No attestations yet — not ready ---------------------------------
    if attestation_records.is_empty() {
        return Ok(None);
    }

    // --- 4. Derive fields from attestations ---------------------------------
    let attestations: Vec<ValidationAttestation> = attestation_records
        .iter()
        .filter_map(|r| {
            r.entry()
                .to_app_option::<ValidationAttestation>()
                .ok()
                .flatten()
        })
        .collect();

    // Participating validators = authors of the records.
    let participating_validators: Vec<AgentPubKey> = attestation_records
        .iter()
        .map(|r| r.action().author().clone())
        .collect();

    // Majority outcome (plurality vote).
    let outcome = derive_majority_outcome(&attestations);

    // Agreement level from success rate.
    let agreement_level = derive_agreement_level(&attestations);

    // Total validation duration = max time invested.
    let validation_duration_secs = attestations
        .iter()
        .map(|a| a.time_invested_secs)
        .max()
        .unwrap_or(0);

    // Discipline from first attestation.
    let discipline = attestations
        .first()
        .map(|a| a.discipline.clone())
        .unwrap_or(Discipline::Other("unknown".into()));

    // --- 5. Create HarmonyRecord + links ------------------------------------
    let record = HarmonyRecord {
        request_ref: request_ref.clone(),
        outcome,
        agreement_level: agreement_level.clone(),
        participating_validators: participating_validators.clone(),
        validation_duration_secs,
        discipline: discipline.clone(),
    };
    let record_hash = create_entry(EntryTypes::HarmonyRecord(record))?;

    // Index by request_ref for direct lookup.
    create_link(
        anchor_key,
        record_hash.clone(),
        LinkTypes::RequestToHarmonyRecord,
        (),
    )?;

    // Index by discipline for analytics.
    let disc_anchor = discipline_anchor(&discipline)?;
    create_link(
        disc_anchor,
        record_hash.clone(),
        LinkTypes::DisciplinePath,
        (),
    )?;

    // --- 6. Optionally issue badge -------------------------------------------
    if let Some(badge_type) = evaluate_badge(&agreement_level, participating_validators.len()) {
        // issued_to = the researcher who submitted the ValidationRequest.
        // Cross-DNA call (author grant — same-agent cell). Falls back to the
        // first participating validator if the lookup fails for any reason.
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
                        .unwrap_or_else(|| {
                            participating_validators
                                .first()
                                .cloned()
                                .unwrap_or_else(|| {
                                    agent_info().map(|i| i.agent_initial_pubkey).unwrap()
                                })
                        })
                }
                _ => participating_validators
                    .first()
                    .cloned()
                    .unwrap_or_else(|| agent_info().map(|i| i.agent_initial_pubkey).unwrap()),
            }
        };
        let badge = ReproducibilityBadge {
            study_ref: request_ref.clone(),
            issued_to,
            badge_type,
            harmony_record_ref: record_hash.clone(),
        };
        let badge_hash = create_entry(EntryTypes::ReproducibilityBadge(badge))?;
        create_link(
            request_ref.clone(),
            badge_hash,
            LinkTypes::StudyToBadge,
            (),
        )?;
    }

    // --- 7. Update validator reputations ------------------------------------
    for (record, attestation) in attestation_records.iter().zip(attestations.iter()) {
        let _ = _update_reputation_internal(
            record.action().author().clone(),
            attestation.discipline.clone(),
            attestation.outcome.clone(),
            attestation.time_invested_secs,
        );
    }

    Ok(Some(record_hash))
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
