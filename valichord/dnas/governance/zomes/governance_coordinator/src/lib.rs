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
// checks (system_coordinator_key). Only the authorised conductor may
// successfully call them.

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

// ---------------------------------------------------------------------------
// Cross-DNA call helper
// ---------------------------------------------------------------------------

/// Call a function on the attestation coordinator and decode the response.
///
/// Returns `Ok(None)` on any cross-DNA failure (network error, unauthorized,
/// decode error) rather than propagating errors — callers use the None path
/// to abort conservatively without failing the calling function.
///
/// This matches the documented design intent: "if the quorum count cannot be
/// determined, return None conservatively — do NOT default to 1."
fn call_attestation_zome_opt<I, O>(fn_name: &str, input: I) -> ExternResult<Option<O>>
where
    I: serde::Serialize + std::fmt::Debug,
    O: serde::de::DeserializeOwned + std::fmt::Debug,
{
    let response = call(
        CallTargetCell::OtherRole("attestation".into()),
        ZomeName::from("attestation_coordinator"),
        FunctionName::from(fn_name),
        None,
        input,
    )?;
    match response {
        ZomeCallResponse::Ok(extern_io) => {
            extern_io
                .decode::<O>()
                .map(Some)
                .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))
        }
        _ => Ok(None), // Network error / unauthorized — abort conservatively.
    }
}

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
        LinkQuery::try_new(anchor_key.clone(), LinkTypes::RequestToHarmonyRecord)?,
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Ok(None);
    }

    // 2. Fetch attestations from attestation DNA.
    let attestation_records: Vec<Record> =
        match call_attestation_zome_opt("get_attestations_for_request", request_ref.clone())? {
            Some(records) => records,
            None => return Ok(None),
        };
    if attestation_records.is_empty() {
        return Ok(None);
    }

    // 3. Completeness gate: require all expected attestations before writing.
    // If the quorum count cannot be determined (ValidationRequest not found or
    // cross-DNA call fails), return None conservatively — do NOT default to 1,
    // as that would allow a single attestation to finalise any study.
    let min_validators: u8 =
        match call_attestation_zome_opt("get_num_validators_required", request_ref.clone())? {
            Some(n) => n,
            None => return Ok(None), // Cannot determine quorum — abort conservatively.
        };
    if (attestation_records.len() as u8) < min_validators {
        return Ok(None);
    }

    // 4-7. Assemble and write.
    let hash = write_harmony_record(request_ref, attestation_records, anchor_key)?;
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
        LinkQuery::try_new(anchor_key.clone(), LinkTypes::RequestToHarmonyRecord)?,
        GetStrategy::Network,
    )?;
    if !existing.is_empty() {
        return Ok(None);
    }

    // 2. Fetch attestations and apply min_attestations_for_finalization threshold.
    let attestation_records: Vec<Record> =
        match call_attestation_zome_opt("get_attestations_for_request", request_ref.clone())? {
            Some(records) => records,
            None => return Ok(None),
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
    // If the VR cannot be found or the call fails, abort conservatively —
    // we cannot verify the round has timed out, so we must not finalise.
    let maybe_vr: Option<Record> = call_attestation_zome_opt(
        "get_validation_request_for_data_hash",
        request_ref.clone(),
    )?
    .flatten(); // call_attestation_zome_opt returns Option<Option<Record>> here
    match maybe_vr {
        Some(vr) => {
            let now = sys_time()?;
            let vr_time = vr.action().timestamp();
            let elapsed_secs = (now.0 - vr_time.0) / 1_000_000;
            if elapsed_secs < ROUND_TIMEOUT_SECS {
                return Ok(None); // Round has not timed out yet.
            }
            // Age check passed — fall through to write.
        }
        None => return Ok(None), // VR not found — cannot verify age; abort conservatively.
    }

    // 4-7. Assemble and write with whatever attestations are present.
    let hash = write_harmony_record(request_ref, attestation_records, anchor_key)?;
    Ok(Some(hash))
}

/// Core assembly: derive fields, write HarmonyRecord + links, issue badge,
/// update reputations.  Called by both check_and_create_harmony_record
/// (full quorum) and force_finalize_round (reduced quorum after timeout).
///
/// `anchor_key` is pre-computed by the caller (avoiding a redundant
/// `anchor_for_request` call — each call does `path.ensure()` on the DHT).
fn write_harmony_record(
    request_ref: ExternalHash,
    attestation_records: Vec<Record>,
    anchor_key: EntryHash,
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

    let outcome              = derive_majority_outcome(&attestations);
    let agreement_level      = derive_agreement_level(&attestations);
    let validation_duration_secs = attestations
        .iter()
        .map(|a| a.time_invested_secs)
        .max()
        .unwrap_or(0);
    let discipline = attestations
        .first()
        .map(|a| a.discipline.clone())
        .unwrap_or(Discipline::Other("unknown".into()));

    // Pre-compute before discipline/validators are moved into the struct.
    let disc_anchor    = discipline_anchor(&discipline)?;
    let validator_count = participating_validators.len();

    // Write HarmonyRecord entry and indexes.
    let record = HarmonyRecord {
        request_ref: request_ref.clone(),
        outcome,
        agreement_level,
        participating_validators,   // moved — no clone
        validation_duration_secs,
        discipline,                 // moved — no clone
    };
    let record_hash = create_entry(EntryTypes::HarmonyRecord(record))?;

    create_link(anchor_key, record_hash.clone(), LinkTypes::RequestToHarmonyRecord, ())?;
    create_link(disc_anchor, record_hash.clone(), LinkTypes::DisciplinePath, ())?;

    // Issue badge — skip if the researcher's identity cannot be resolved.
    // Falling back to a validator pubkey would issue a badge to the wrong
    // recipient; it is safer to skip issuance than to mis-attribute.
    if let Some(badge_type) = evaluate_badge(&agreement_level, validator_count) {
        let maybe_researcher: Option<AgentPubKey> = call_attestation_zome_opt::<_, Option<Record>>(
            "get_validation_request_for_data_hash",
            request_ref.clone(),
        )
        .ok()
        .flatten()   // Option<Option<Record>> → Option<Record>
        .flatten()
        .map(|r| r.action().author().clone());
        if let Some(issued_to) = maybe_researcher {
            let type_anchor = badge_type_anchor(&badge_type)?;
            let badge = ReproducibilityBadge {
                study_ref:          request_ref.clone(),
                issued_to,
                badge_type,
                harmony_record_ref: record_hash.clone(),
            };
            let badge_hash = create_entry(EntryTypes::ReproducibilityBadge(badge))?;
            create_link(request_ref.clone(), badge_hash.clone(), LinkTypes::StudyToBadge, ())?;
            create_link(type_anchor, badge_hash, LinkTypes::BadgePath, ())?;
        }
        // If researcher identity is unknown, skip badge issuance rather than
        // mis-attributing the badge to a validator.
    }

    // Automatic reputation update — only runs in dev/test mode (system_coordinator_key
    // is empty). In production the validate() gate on ValidatorReputation requires
    // system_coordinator_key authorship, so these calls would silently fail.
    // Explicit reputation updates go through update_validator_reputation().
    let coord_props = DnaProperties::try_from_dna_properties()?;
    if coord_props.system_coordinator_key.is_empty() {
        for (record, attestation) in attestation_records.iter().zip(attestations.iter()) {
            let _ = _update_reputation_internal(
                record.action().author().clone(),
                attestation.discipline.clone(),
                attestation.outcome.clone(),
                attestation.time_invested_secs,
            );
        }
    }

    Ok(record_hash)
}

/// Record a governance vote outcome on-chain.
///
/// Only the system_coordinator_key agent may write GovernanceDecision
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
    // Use last() — idempotency guard means there should be at most one record,
    // but defensive ordering ensures we surface the latest if a race ever
    // produced duplicates (links are gossip-ordered by timestamp).
    match links.last() {
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
    records_for_links(links)
}

/// Return the most recent ValidatorReputation record for a given validator.
///
/// Uses the `total_validations` count encoded as 8 big-endian bytes in the
/// link tag to find the highest-count record deterministically.  This avoids
/// a race condition where two concurrent reputation updates written in the
/// same DHT gossip batch could cause `.last()` to return a stale record
/// depending on non-deterministic gossip ordering.
///
/// Links written before this scheme (empty or short tags) are treated as
/// count = 0 and will always lose to any tagged link.
#[hdk_extern]
pub fn get_validator_reputation(
    validator: AgentPubKey,
) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(validator, LinkTypes::ValidatorToReputation)?,
        GetStrategy::Network,
    )?;
    // Find the link whose tag encodes the highest total_validations count.
    let best = links.iter().max_by_key(|l| reputation_link_count(l));
    match best {
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

/// Extract the total_validations count from a ValidatorToReputation link tag.
///
/// Tags are written as 8 big-endian bytes of the `u64` total_validations.
/// Old links (written before this scheme) have empty or short tags and
/// return 0, ensuring they sort below any tagged link.
fn reputation_link_count(link: &Link) -> u64 {
    let tag = link.tag.as_ref();
    if tag.len() >= 8 {
        if let Ok(bytes) = tag[..8].try_into() {
            return u64::from_be_bytes(bytes);
        }
    }
    0
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
    records_for_links(links)
}

/// Return all GovernanceDecision records (insertion order).
#[hdk_extern]
pub fn get_all_governance_decisions(_: ()) -> ExternResult<Vec<Record>> {
    let anchor = decisions_anchor()?;
    let links = get_links(
        LinkQuery::try_new(anchor, LinkTypes::AllDecisions)?,
        GetStrategy::Network,
    )?;
    records_for_links(links)
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
    records_for_links(links)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Fetch records for a list of links whose targets are ActionHashes (network).
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

/// Compute the DHT anchor entry hash for a given request_ref.
///
/// Path format: "request.{hex_encoded_core_32_bytes}"
fn anchor_for_request(request_ref: &ExternalHash) -> ExternResult<EntryHash> {
    use std::fmt::Write as FmtWrite;
    let mut hex = String::with_capacity(64);
    for b in request_ref.get_raw_32() {
        write!(hex, "{:02x}", b).ok();
    }
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
/// supersedes the previous one (links accumulate; highest count wins).
///
/// The link tag encodes `total_validations` as 8 big-endian bytes so that
/// `get_validator_reputation` can find the correct record by max-tag rather
/// than relying on gossip-ordering (.last()), which is non-deterministic
/// when two updates arrive in the same DHT batch.
fn _update_reputation_internal(
    validator: AgentPubKey,
    discipline: Discipline,
    outcome: AttestationOutcome,
    time_invested_secs: u64,
) -> ExternResult<ActionHash> {
    // Fetch existing reputation if any, using max-tag for correctness.
    let links = get_links(
        LinkQuery::try_new(validator.clone(), LinkTypes::ValidatorToReputation)?,
        GetStrategy::Network,
    )?;

    let (total_validations, agreement_rate, avg_time_secs, tier) =
        if let Some(link) = links.iter().max_by_key(|l| reputation_link_count(l)) {
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
        person_key: None,
    };
    let rep_hash = create_entry(EntryTypes::ValidatorReputation(rep))?;
    // Encode total_validations as 8 big-endian bytes in the link tag so
    // get_validator_reputation can find the highest-count record without
    // relying on non-deterministic gossip ordering.
    let tag = LinkTag::new(total_validations.to_be_bytes().to_vec());
    create_link(
        validator,
        rep_hash.clone(),
        LinkTypes::ValidatorToReputation,
        tag,
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
