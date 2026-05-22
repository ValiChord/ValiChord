use hdk::prelude::*;
use std::collections::HashSet;
use valichord_coordinator_utils::{call_other_role_opt, records_for_links};
use governance_integrity::{
    DnaProperties, EntryTypes, GovernanceDecision, HarmonyRecord, LinkTypes,
    ReproducibilityBadge, ValidatorReputation,
};
use valichord_shared_types::{
    AttestationOutcome, BadgeType, CertificationTier, Discipline,
    ValidationAttestation, ValidatorAgentType, ValidatorType,
    derive_agreement_level, derive_majority_outcome, evaluate_badge, discipline_tag,
};

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

    // Register the hourly sweep that finalises timed-out rounds without requiring
    // a live client.  schedule() is idempotent — safe to call on every init.
    // NOTE: init is lazy; the schedule fires only after the cell's first zome call.
    schedule("sweep_timed_out_rounds")?;

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
    /// `Human` → round-based tier progression (default).
    /// `AI`    → issuer-granted tier only; `initial_tier` sets the tier on the first call.
    /// `#[serde(default)]` allows callers written before this field was added to omit it
    /// (treated as Human — preserves existing behaviour).
    #[serde(default)]
    pub validator_type:      ValidatorType,
    /// Only used on the first call for an AI validator (when no reputation record exists).
    /// Ignored for Human validators and for AI validators who already have a record.
    /// `None` defaults to `Provisional` if no existing record is found.
    #[serde(default)]
    pub initial_tier:        Option<CertificationTier>,
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

// ROUND_TIMEOUT_SECS is now a DNA property (round_timeout_secs in DnaProperties).
// Default: 604800 s (7 days). Set to 0 in test DNA properties to bypass the clock.

// ---------------------------------------------------------------------------
// Cross-DNA call helper
// ---------------------------------------------------------------------------

/// Call a function on the attestation coordinator and decode the response.
///
/// Returns `Ok(None)` on any cross-DNA failure — callers use the None path to
/// abort conservatively without failing the calling function.  Matches the
/// documented design intent: "if the quorum count cannot be determined, return
/// None conservatively — do NOT default to 1."
fn call_attestation_zome_opt<I, O>(fn_name: &str, input: I) -> ExternResult<Option<O>>
where
    I: serde::Serialize + std::fmt::Debug,
    O: serde::de::DeserializeOwned + std::fmt::Debug,
{
    call_other_role_opt("attestation", "attestation_coordinator", fn_name, input)
}

/// Idempotent — called automatically from DNA 3 submit_attestation.
///
/// Algorithm:
///   1. Short-circuit if a HarmonyRecord already exists.
///   2. Fetch attestations from DNA 3.
///   3. Require ≥ num_validators_required attestations (completeness gate).
///   4-7. Delegate to write_harmony_record.
///
/// TOCTOU note: two concurrent last-validator submissions can both pass the
/// idempotency check and each write a HarmonyRecord.  write_harmony_record
/// sorts participating_validators by key bytes before writing, so two concurrent
/// calls that see the *same* set of attestations (regardless of gossip order)
/// produce identical entry content — content-addressing collapses them to the
/// same entry hash, making that case benign.  The remaining risk is two calls
/// that see *different* counts (N vs N+1): they write structurally different
/// entries and the N-validator record's badge may be orphaned.  Proper fix
/// (single-shot finalisation trigger or countersigning) is Phase 1 work.
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
        // Already exists — return the existing hash rather than None.
        let existing_hash = existing
            .into_iter()
            .max_by_key(|l| l.timestamp)
            .and_then(|l| l.target.into_action_hash());
        // Badge may be absent if the original write happened via the auto-call path
        // (submit_attestation → check_and_create_harmony_record → get_validation_request…)
        // where the back-call into DNA 3 fails because that cell is already executing
        // submit_attestation (Holochain prevents reentrant same-cell calls).
        // This retry runs from a direct governance call where DNA 3 is free, so it succeeds.
        if let Some(ref h) = existing_hash {
            let _ = issue_badge_if_missing(&request_ref, h);
        }
        return Ok(existing_hash);
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

    // Filter out attestations from warranted agents — a validator who received
    // warrants after claiming should not contribute to a permanent HarmonyRecord.
    //
    // unwrap_or(true) — include on activity-check failure — is intentionally
    // asymmetric with reject_if_warranted() in DNA 3 (which propagates errors).
    // At claim time a validator can retry; here a transient network failure that
    // excludes a legitimate validator could permanently strand a completed round
    // (no automatic retry trigger exists once all attestations are written).
    // Including on failure is the safer default at finalisation time.
    let attestation_records: Vec<Record> = attestation_records
        .into_iter()
        .filter(|r| {
            let author = r.action().author().clone();
            get_agent_activity(author, ChainQueryFilter::new(), ActivityRequest::Full, GetOptions::network())
                .map(|a| a.warrants.is_empty())
                .unwrap_or(true)
        })
        .collect();
    if (attestation_records.len() as u8) < min_validators {
        return Ok(None); // Not enough unwarranted attestations to meet quorum.
    }

    // Verify every attestation actually belongs to this study.
    // get_attestations_for_request should already enforce this, but an
    // extra check here prevents a forged or mismatched attestation set
    // from being written into a permanent HarmonyRecord.
    //
    // Deserialisation failure returns a hard Err — not Ok(None) — so it is
    // distinguishable from "quorum not yet met".  A None from to_app_option()
    // means the link points to a non-ValidationAttestation entry (DHT corruption),
    // not a gossip delay (missing records are filtered out by records_for_links).
    for r in &attestation_records {
        let att = r.entry()
            .to_app_option::<ValidationAttestation>()
            .map_err(|e| wasm_error!(WasmErrorInner::Guest(
                format!("Attestation deserialisation failed — possible DHT corruption: {e}")
            )))?
            .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                "An attestation index link points to a non-ValidationAttestation entry".into()
            )))?;
        if att.request_ref != request_ref {
            return Ok(None); // Forged or mismatched — abort conservatively.
        }
    }

    // 4-7. Assemble and write.
    let hash = write_harmony_record(request_ref, attestation_records, anchor_key)?;
    Ok(Some(hash))
}

/// Force-finalise a stuck round after `round_timeout_secs` (DNA property) have elapsed.
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
///   - The ValidationRequest was created ≥ `round_timeout_secs` ago.
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

    // Verify every attestation belongs to this study (same guard as full-quorum path).
    let all_match = attestation_records.iter().all(|r| {
        r.entry()
            .to_app_option::<ValidationAttestation>()
            .ok()
            .flatten()
            .map(|a| a.request_ref == request_ref)
            .unwrap_or(false)
    });
    if !all_match {
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
            if elapsed_secs < props.round_timeout_secs as i64 {
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
    // Build (validator, attestation) pairs in a single pass — guarantees that
    // participating_validators and attestations are always the same length so
    // the zip used for reputation updates is never silently misaligned.
    // Sort by validator key bytes before building the record.
    // Two concurrent calls that see the same attestation set but receive links
    // in different gossip orders would otherwise produce entries with different
    // content (and therefore different entry hashes).  Sorting makes the content
    // deterministic: Holochain's content-addressing then collapses concurrent
    // writes to the same entry hash, making the TOCTOU race on the idempotency
    // link check benign.
    let mut pairs: Vec<(AgentPubKey, ValidationAttestation)> = attestation_records
        .iter()
        .filter_map(|r| {
            let att = r.entry().to_app_option::<ValidationAttestation>().ok().flatten()?;
            Some((r.action().author().clone(), att))
        })
        .collect();
    pairs.sort_by(|(a, _), (b, _)| a.get_raw_39().cmp(b.get_raw_39()));

    let participating_validators: Vec<AgentPubKey> =
        pairs.iter().map(|(v, _)| v.clone()).collect();
    let attestations: Vec<ValidationAttestation> =
        pairs.into_iter().map(|(_, a)| a).collect();

    let outcome         = derive_majority_outcome(&attestations);
    let agreement_level = derive_agreement_level(&attestations);

    // Single pass for discipline (first) + max duration — avoids two separate iterations.
    let mut validation_duration_secs: u64 = 0;
    let mut discipline_opt: Option<Discipline> = None;
    for a in &attestations {
        validation_duration_secs = validation_duration_secs.max(a.time_invested_secs);
        if discipline_opt.is_none() {
            discipline_opt = Some(a.discipline.clone());
        }
    }
    let discipline = discipline_opt.unwrap_or_else(|| Discipline::Other("unknown".into()));

    // Look up each validator's declared agent type — parallel to participating_validators.
    // Wasm-level errors (host failure, decode error) propagate and fail the entire write —
    // an incomplete HarmonyRecord is immutable and the missing data can never be recovered.
    // Network timeouts within ZomeCallResponse are still mapped to Ok(None) by
    // call_attestation_zome_opt (validator may genuinely have no agent_type set).
    let validator_types: Vec<Option<ValidatorAgentType>> = participating_validators
        .iter()
        .map(|v| call_attestation_zome_opt::<AgentPubKey, ValidatorAgentType>(
            "get_validator_agent_type",
            v.clone(),
        ))
        .collect::<ExternResult<Vec<_>>>()?;

    // Pre-compute before discipline/validators are moved into the struct.
    let disc_anchor    = discipline_anchor(&discipline)?;
    let validator_count = participating_validators.len();

    // Write HarmonyRecord entry and indexes.
    // Clone validator_types before moving into the record so the rep update loop can use it.
    let record = HarmonyRecord {
        request_ref: request_ref.clone(),
        outcome,
        agreement_level,
        participating_validators: participating_validators.clone(),
        validator_types: validator_types.clone(),
        validation_duration_secs,
        discipline,                 // moved — no clone
    };
    let record_hash = create_entry(EntryTypes::HarmonyRecord(record))?;

    create_link(anchor_key, record_hash.clone(), LinkTypes::RequestToHarmonyRecord, ())?;
    create_link(disc_anchor, record_hash.clone(), LinkTypes::DisciplinePath, ())?;

    // Issue badge.  Delegates to try_issue_badge, which no-ops silently if the
    // researcher's identity cannot be resolved (3-hop reentrant call failure in the
    // auto-call path).  The idempotency return path in check_and_create_harmony_record
    // retries via issue_badge_if_missing when the badge is still absent.
    if let Some(badge_type) = evaluate_badge(&agreement_level, validator_count) {
        let _ = try_issue_badge(request_ref.clone(), record_hash.clone(), badge_type);
    }

    // Automatic reputation update — only runs in dev/test mode (system_coordinator_key
    // is empty). In production the validate() gate on ValidatorReputation requires
    // system_coordinator_key authorship, so these calls would silently fail.
    // Explicit reputation updates go through update_validator_reputation().
    let coord_props = DnaProperties::try_from_dna_properties()?;
    if coord_props.system_coordinator_key.is_empty() {
        // Use participating_validators + attestations (both sorted from pairs) so the
        // validator key and their assessment data are always aligned after the sort.
        // attestation_records is in original gossip order and would mismatch after sort.
        // validator_types[i] is parallel to participating_validators[i] (same sort order).
        for ((validator, attestation), vtype_opt) in participating_validators.iter()
            .zip(attestations.iter())
            .zip(validator_types.iter())
        {
            let vt = match vtype_opt {
                Some(ValidatorAgentType::AutomatedTool) => ValidatorType::AI,
                _ => ValidatorType::Human,
            };
            let _ = _update_reputation_internal(
                validator.clone(),
                attestation.discipline.clone(),
                attestation.outcome.clone(),
                attestation.time_invested_secs,
                vt,
                None, // initial_tier not available from round context; AI validators should
                      // already have an issuer-created record before participating in rounds
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
        input.validator_type,
        input.initial_tier,
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
    // max_by_key(timestamp) is deterministic under concurrent gossip;
    // last() is DHT-order-dependent and unreliable under concurrent writes.
    match links.iter().max_by_key(|l| l.timestamp) {
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

/// Issue a badge for `request_ref` if no badge link exists yet.
///
/// No-ops silently if: a badge already exists, the HarmonyRecord can't be fetched,
/// the quorum doesn't meet any badge threshold, or researcher identity is unknown.
/// Errors from DHT writes (create_entry, create_link) propagate so callers can log them.
fn issue_badge_if_missing(
    request_ref: &ExternalHash,
    record_hash: &ActionHash,
) -> ExternResult<()> {
    let badge_links = get_links(
        LinkQuery::try_new(request_ref.clone(), LinkTypes::StudyToBadge)?,
        GetStrategy::Network,
    )?;
    if !badge_links.is_empty() {
        return Ok(());
    }
    let Some(record) = get(record_hash.clone(), GetOptions::network())? else {
        return Ok(());
    };
    let Some(harmony) = record
        .entry()
        .to_app_option::<HarmonyRecord>()
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(
            format!("HarmonyRecord decode failed in issue_badge_if_missing: {e}")
        )))?
    else {
        return Ok(());
    };
    let validator_count = harmony.participating_validators.len();
    let Some(badge_type) = evaluate_badge(&harmony.agreement_level, validator_count) else {
        return Ok(());
    };
    try_issue_badge(request_ref.clone(), record_hash.clone(), badge_type)
}

/// Write a ReproducibilityBadge entry and its two index links.
///
/// Returns Ok(()) silently if the researcher's identity cannot be resolved via
/// the attestation DNA — mis-attributing a badge to a validator pubkey is worse
/// than skipping issuance.
fn try_issue_badge(
    request_ref: ExternalHash,
    record_hash: ActionHash,
    badge_type: BadgeType,
) -> ExternResult<()> {
    let maybe_researcher: Option<AgentPubKey> = call_attestation_zome_opt::<_, Option<Record>>(
        "get_validation_request_for_data_hash",
        request_ref.clone(),
    )
    .ok()
    .flatten()
    .flatten()
    .map(|r| r.action().author().clone());
    let Some(issued_to) = maybe_researcher else {
        return Ok(());
    };
    let type_anchor = badge_type_anchor(&badge_type)?;
    let badge = ReproducibilityBadge {
        study_ref:          request_ref.clone(),
        issued_to,
        badge_type,
        harmony_record_ref: record_hash,
    };
    let badge_hash = create_entry(EntryTypes::ReproducibilityBadge(badge))?;
    create_link(request_ref, badge_hash.clone(), LinkTypes::StudyToBadge, ())?;
    create_link(type_anchor, badge_hash, LinkTypes::BadgePath, ())?;
    Ok(())
}

/// Internal reputation update — creates a new ValidatorReputation entry that
/// supersedes the previous one (links accumulate; highest count wins).
///
/// AI validators bypass round-based progression entirely: if a reputation record
/// already exists, its hash is returned unchanged; if none exists, an initial
/// record is created with `initial_tier` (defaulting to Provisional).
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
    validator_type: ValidatorType,
    initial_tier: Option<CertificationTier>,
) -> ExternResult<ActionHash> {
    // AI validators use issuer-granted tier only — no round-based progression.
    if validator_type == ValidatorType::AI {
        let links = get_links(
            LinkQuery::try_new(validator.clone(), LinkTypes::ValidatorToReputation)?,
            GetStrategy::Network,
        )?;
        if let Some(link) = links.iter().max_by_key(|l| reputation_link_count(l)) {
            // Existing record — return its hash; tier is frozen.
            return link
                .target
                .clone()
                .into_action_hash()
                .ok_or_else(|| wasm_error!(WasmErrorInner::Guest(
                    "Invalid ValidatorToReputation link target".into()
                )));
        }
        // No record yet — create the initial reputation with the issuer-granted tier.
        let tier = initial_tier.unwrap_or(CertificationTier::Provisional);
        let rep = ValidatorReputation {
            validator: validator.clone(),
            discipline,
            total_validations:      0,
            successful_validations: 0,
            agreement_rate:         0.0,
            avg_time_secs:          0,
            tier,
            person_key: None,
        };
        let rep_hash = create_entry(EntryTypes::ValidatorReputation(rep))?;
        let tag = LinkTag::new(0u64.to_be_bytes().to_vec());
        create_link(validator, rep_hash.clone(), LinkTypes::ValidatorToReputation, tag)?;
        return Ok(rep_hash);
    }

    // Human validators: fetch existing reputation if any, using max-tag for correctness.
    let links = get_links(
        LinkQuery::try_new(validator.clone(), LinkTypes::ValidatorToReputation)?,
        GetStrategy::Network,
    )?;

    let is_success = matches!(
        &outcome,
        AttestationOutcome::Reproduced | AttestationOutcome::PartiallyReproduced { .. }
    );

    // (total_validations, successful_validations, agreement_rate, avg_time_secs, tier)
    let (total_validations, successful_validations, agreement_rate, avg_time_secs, tier) =
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
                    // Use the stored integer count directly — avoids floating-point
                    // reconstruction drift: (rate * total) as u32 truncates incorrectly,
                    // e.g. 2/3 → 0.666 * 3 = 1.999 → 1, losing a success permanently.
                    let new_successes =
                        existing.successful_validations + if is_success { 1 } else { 0 };
                    let new_rate = new_successes as f64 / new_total as f64;
                    let new_avg = (existing.avg_time_secs * existing.total_validations as u64
                        + time_invested_secs)
                        / new_total as u64;
                    let new_tier = cert_tier(new_total, new_rate);
                    (new_total, new_successes, new_rate, new_avg, new_tier)
                } else {
                    let s = if is_success { 1 } else { 0 };
                    (1, s, initial_rate(&outcome), time_invested_secs, CertificationTier::Provisional)
                }
            } else {
                let s = if is_success { 1 } else { 0 };
                (1, s, initial_rate(&outcome), time_invested_secs, CertificationTier::Provisional)
            }
        } else {
            let s = if is_success { 1 } else { 0 };
            (1, s, initial_rate(&outcome), time_invested_secs, CertificationTier::Provisional)
        };

    let rep = ValidatorReputation {
        validator: validator.clone(),
        discipline,
        total_validations,
        successful_validations,
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
    // Placeholder thresholds — to be calibrated with real-world data.
    if total >= 25 && rate >= 0.80 {
        CertificationTier::Certified
    } else if total >= 10 && rate >= 0.60 {
        CertificationTier::Advanced
    } else if total >= 3 {
        CertificationTier::Standard
    } else {
        CertificationTier::Provisional
    }
}

// ---------------------------------------------------------------------------
// Scheduled sweep — closes stuck rounds without a live client
// ---------------------------------------------------------------------------

/// Hourly background sweep that finalises validation rounds whose timeout has
/// elapsed but whose last validator went offline before triggering finalization.
///
/// Algorithm:
///   1. Read all completed HarmonyRecords to discover which disciplines are
///      active on this DHT instance.
///   2. For each discipline, fetch all ValidationAttestation records from the
///      attestation DNA and collect unique request_refs.
///   3. Call force_finalize_round for each — it is idempotent (returns None if
///      already finalised) and enforces the timeout gate internally, so no study
///      is closed prematurely.
///
/// Limitation: studies in a discipline where NO round has EVER completed will
/// not appear in step 1 and therefore will not be swept.  This is acceptable
/// for the current phase; a global "active studies" index is Phase 1 work.
///
/// The function is infallible: any error causes a silent no-op and the schedule
/// continues running on the next tick.  If the function call itself panics,
/// Holochain drops the schedule automatically — the conductor log will show the
/// reason.
#[hdk_extern(infallible)]
fn sweep_timed_out_rounds(schedule: Option<Schedule>) -> Option<Schedule> {
    let hourly = Some(Schedule::Persisted("0 0 * * * * *".into()));

    // Seed invocation (called from init() with None) — return the schedule
    // without doing any work.  The first real sweep runs on the next hourly tick.
    // Without this guard the seed fires immediately after init(), while the
    // calling agent's local DHT already holds their attestation, and the sweep
    // can write the HarmonyRecord before a direct force_finalize_round call.
    if schedule.is_none() {
        return hourly;
    }

    // Step 1: query attestation for each known named discipline.
    //
    // WHY not derive disciplines from get_all_governance_decisions():
    //   get_all_governance_decisions returns GovernanceDecision entries (governance
    //   votes), not HarmonyRecord entries — decoding them as HarmonyRecord always
    //   returns Ok(None) and disciplines would be permanently empty.  Using a static
    //   list of the known named variants is simpler, requires no new link type, and
    //   produces correct results: for disciplines with no attestations yet,
    //   get_attestations_for_discipline returns [] and no work is done.
    //
    // Limitation: studies submitted under Discipline::Other(String) are not covered
    // by this sweep.  Adding a global HarmonyRecord index (Phase 1) would close
    // this gap without enumerating disciplines at all.
    let disciplines = vec![
        Discipline::ComputationalBiology,
        Discipline::ClimateScience,
        Discipline::SocialScience,
        Discipline::Economics,
        Discipline::Psychology,
        Discipline::Neuroscience,
        Discipline::MachineLearning,
    ];

    // Step 2: for each discipline, collect unique request_refs from attestation records.
    let mut seen_refs: HashSet<Vec<u8>> = HashSet::new();
    let mut request_refs: Vec<ExternalHash> = Vec::new();
    for discipline in disciplines {
        let records: Vec<Record> = match call_attestation_zome_opt(
            "get_attestations_for_discipline",
            discipline,
        ) {
            Ok(Some(r)) => r,
            _ => continue,
        };
        for record in records {
            if let Ok(Some(att)) = record.entry().to_app_option::<ValidationAttestation>() {
                let key = att.request_ref.get_raw_32().to_vec();
                if seen_refs.insert(key) {
                    request_refs.push(att.request_ref);
                }
            }
        }
    }

    // Step 3: attempt finalization for each candidate study.
    // force_finalize_round is idempotent (returns Ok(None) for already-done or
    // not-yet-timed-out studies) and handles all precondition checks internally.
    for request_ref in request_refs {
        let _ = force_finalize_round(request_ref);
    }

    hourly
}
