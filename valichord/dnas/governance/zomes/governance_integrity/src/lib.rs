use hdi::prelude::*;
use valichord_shared_types::{AgreementLevel, AttestationOutcome, BadgeType, CertificationTier, Discipline, ValidatorAgentType};

// ---------------------------------------------------------------------------
// DNA Properties — one key, baked into the DNA hash.
//
// system_coordinator_key gates GovernanceDecision AND ValidatorReputation
// writes — governance decisions represent human deliberation outcomes, and
// reputation records are authoritative system data; both require a designated
// key-holder.
//
// HarmonyRecord and ReproducibilityBadge are NOT author-gated: any
// participant who was part of the round can trigger finalisation. Content
// correctness is enforced in the coordinator (completeness check +
// idempotency) rather than by trusting a single agent. This keeps the system
// consistent with Holochain's decentralised model —
// no single node is a required coordinator for protocol completion.
//
// Remaining limitation (Phase 1): validate() cannot perform cross-DNA lookups
// to cryptographically verify HarmonyRecord content against the Attestation
// DHT. Content correctness is currently enforced in the coordinator layer
// only, not at the network validation layer.
// ---------------------------------------------------------------------------

fn default_round_timeout() -> u64 { 604_800 } // 7 days

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
    /// #[serde(default)] allows omitting this field in DNA properties YAML.
    #[serde(default)]
    pub min_attestations_for_finalization: u32,
    /// Seconds after ValidationRequest creation before force_finalize_round
    /// may close the round with partial attestations. Default: 604800 (7 days).
    /// Set to 0 in tests to bypass the clock constraint.
    #[serde(default = "default_round_timeout")]
    pub round_timeout_secs: u64,
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
    /// Agent type of each participating validator, parallel to
    /// `participating_validators` — position [i] is the type for validator [i].
    /// `None` if the validator had no profile or the field was not set.
    /// `#[serde(default)]` ensures records written before this field was added
    /// deserialise without error (backwards-compatible).
    #[serde(default)]
    pub validator_types:          Vec<Option<ValidatorAgentType>>,
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
    pub validator:              AgentPubKey,
    pub discipline:             Discipline,
    pub total_validations:      u32,
    /// Integer count of successful outcomes (Reproduced or PartiallyReproduced).
    /// Stored explicitly so agreement_rate can be recomputed exactly without
    /// floating-point reconstruction (which would drift via (rate * total) as u32).
    ///
    /// `#[serde(default)]` ensures records written before this field was added
    /// deserialise as `0` without error (backwards-compatible).
    #[serde(default)]
    pub successful_validations: u32,
    /// 0.0–1.0 rate of outcomes agreeing with the majority.
    /// Derived: successful_validations / total_validations. Stored for read convenience.
    pub agreement_rate:         f64,
    pub avg_time_secs:          u64,
    pub tier:                   CertificationTier,
    /// Stable person identity across devices — `None` until a cross-device
    /// identity system (e.g. Flowsta, Deepkey) links this device key to a
    /// canonical person key.  When set, reputation aggregation uses this key
    /// rather than `validator` (device key), so a validator who rotates or
    /// replaces a device does not lose reputation continuity.
    ///
    /// `#[serde(default)]` ensures records written before this field was added
    /// deserialise as `None` without error (backwards-compatible).
    #[serde(default)]
    pub person_key:        Option<AgentPubKey>,
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

#[derive(Serialize, Deserialize)]
#[serde(tag = "type")]
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

        // --- HarmonyRecord create: author + quorum integrity checks -----------
        //
        // Any validator who participated in the round may trigger finalisation,
        // but they must name themselves in participating_validators.  This prevents
        // non-participants from anonymously forging a record.
        //
        // Two additional checks are now enforced at the network layer:
        //
        //   1. No duplicate validator pubkeys — a fabricated list cannot pad the
        //      validator count past a badge threshold by repeating a single real key.
        //
        //   2. Minimum participant count from min_attestations_for_finalization DNA
        //      property — a single validator cannot unilaterally write a HarmonyRecord
        //      for a study that requires more participants.
        //
        // Full content verification against the Attestation DHT is a Phase 2 goal —
        // cross-DNA calls are not available in validate(), so the participating_validators
        // list itself cannot be cryptographically checked here.  Content correctness
        // is enforced by the coordinator's completeness check and idempotency guard.
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::HarmonyRecord(ref record),
            ref action,
            ..
        }) => {
            if !record.participating_validators.contains(&action.author) {
                return Ok(ValidateCallbackResult::Invalid(
                    "HarmonyRecord author must be listed in participating_validators — \
                     only validators who participated in the round may write the record"
                        .into(),
                ));
            }
            // Duplicate validator guard.
            let unique_count = record.participating_validators
                .iter()
                .collect::<std::collections::HashSet<_>>()
                .len();
            if unique_count < record.participating_validators.len() {
                return Ok(ValidateCallbackResult::Invalid(
                    "HarmonyRecord.participating_validators must not contain duplicate entries — \
                     each validator pubkey may appear at most once".into(),
                ));
            }
            // Parallel array length check: validator_types is serde(default) → empty vec
            // for old entries.  When present it must align with participating_validators so
            // position-based lookups in the UI can't panic or silently return the wrong type.
            if !record.validator_types.is_empty()
                && record.validator_types.len() != record.participating_validators.len()
            {
                return Ok(ValidateCallbackResult::Invalid(
                    "HarmonyRecord.validator_types must be empty or have the same length as \
                     participating_validators".into(),
                ));
            }
            // Minimum quorum from DNA properties.
            let props = DnaProperties::try_from_dna_properties()?;
            let min_required = if props.min_attestations_for_finalization == 0 {
                1u32
            } else {
                props.min_attestations_for_finalization
            };
            if (record.participating_validators.len() as u32) < min_required {
                return Ok(ValidateCallbackResult::Invalid(format!(
                    "HarmonyRecord requires at least {} participating validator(s) \
                     (min_attestations_for_finalization), got {}",
                    min_required,
                    record.participating_validators.len(),
                )));
            }
            Ok(ValidateCallbackResult::Valid)
        }

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

        // --- ReproducibilityBadge create: verify harmony_record_ref and author --
        //
        // Four network-verifiable constraints:
        //   1. harmony_record_ref must point to a live HarmonyRecord.
        //   2. badge.study_ref must match HarmonyRecord.request_ref.
        //   3. Badge author must be listed in participating_validators.
        //   4. badge_type must be consistent with agreement_level + validator count
        //      (mirrors evaluate_badge in the coordinator so the integrity zome
        //      enforces the badge-tier rules network-wide, not just per-coordinator).
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ReproducibilityBadge(ref badge),
            ref action,
            ..
        }) => {
            let hr_record = must_get_valid_record(badge.harmony_record_ref.clone())?;
            let maybe_hr: Option<HarmonyRecord> = handle_error!(hr_record.entry().to_app_option());
            let harmony_record = match maybe_hr {
                Some(hr) => hr,
                None => return Ok(ValidateCallbackResult::Invalid(
                    "badge.harmony_record_ref does not point to a HarmonyRecord".into()
                )),
            };
            if badge.study_ref != harmony_record.request_ref {
                return Ok(ValidateCallbackResult::Invalid(
                    "ReproducibilityBadge.study_ref does not match the \
                     referenced HarmonyRecord.request_ref".into(),
                ));
            }
            if !harmony_record.participating_validators.contains(&action.author) {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only validators who participated in the round may issue a badge".into(),
                ));
            }
            // Badge type must be consistent with agreement level + raw validator count.
            // Two checks (integrity cannot access tier/reputation data):
            //   1. Quorum: at least 3 validators must have participated.
            //   2. Ceiling: badge tier must not exceed what raw count warrants.
            //      The coordinator may issue Bronze when tier-qualified count is
            //      below the Silver threshold — that is expected and valid.
            let validator_count = harmony_record.participating_validators.len();
            match badge_ceiling(&harmony_record.agreement_level, validator_count) {
                None => {
                    return Ok(ValidateCallbackResult::Invalid(
                        "No badge may be issued for this HarmonyRecord — \
                         quorum not met for any badge tier".into(),
                    ));
                }
                Some(ref ceiling) => {
                    if badge_is_reproduced(&badge.badge_type) != badge_is_reproduced(ceiling) {
                        return Ok(ValidateCallbackResult::Invalid(
                            "ReproducibilityBadge.badge_type direction does not match \
                             the HarmonyRecord's agreement_level".into(),
                        ));
                    }
                    if badge_tier_rank(&badge.badge_type) > badge_tier_rank(ceiling) {
                        return Ok(ValidateCallbackResult::Invalid(
                            "ReproducibilityBadge.badge_type exceeds the ceiling \
                             permitted by raw validator count and agreement level".into(),
                        ));
                    }
                }
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- ValidatorReputation create: only system_coordinator_key --------
        //
        // Reputation records are authoritative system data — only the
        // designated system coordinator may mint or update them.
        // Empty key = dev/test bypass (same pattern as GovernanceDecision).
        FlatOp::StoreEntry(OpEntry::CreateEntry {
            app_entry: EntryTypes::ValidatorReputation(_),
            ref action,
            ..
        }) => {
            let props = DnaProperties::try_from_dna_properties()?;
            if !props.system_coordinator_key.is_empty()
                && action.author.to_string() != props.system_coordinator_key
            {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only system_coordinator_key may create ValidatorReputation entries".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

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

        // --- ValidatorReputation update: only system_coordinator_key --------
        FlatOp::RegisterUpdate(OpUpdate::Entry {
            app_entry: EntryTypes::ValidatorReputation(_),
            ref action,
            ..
        }) => {
            let props = DnaProperties::try_from_dna_properties()?;
            if !props.system_coordinator_key.is_empty()
                && action.author.to_string() != props.system_coordinator_key
            {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only system_coordinator_key may update ValidatorReputation entries".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        FlatOp::RegisterUpdate(_) => Ok(ValidateCallbackResult::Valid),

        // --- Deletes: HarmonyRecord, GovernanceDecision, Badge are immutable -
        FlatOp::RegisterDelete(OpDelete { ref action }) => {
            let original_record = must_get_valid_record(action.deletes_address.clone())?;
            if let Some(EntryType::App(app_def)) = original_record.action().entry_type() {
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
            if action.author != *original_record.action().author() {
                return Ok(ValidateCallbackResult::Invalid(
                    "Only the original author may delete this entry".into(),
                ));
            }
            Ok(ValidateCallbackResult::Valid)
        }

        // --- Block deletion of permanent index links -------------------------
        //
        // RequestToHarmonyRecord and StudyToBadge links are the primary
        // discoverability indexes for immutable entries. Allowing deletions
        // would let a validator who triggered finalisation hide the outcome
        // from all future queries (the entry itself is immutable, but the
        // index link is not).
        FlatOp::RegisterDeleteLink {
            link_type: LinkTypes::RequestToHarmonyRecord,
            ..
        } => Ok(ValidateCallbackResult::Invalid(
            "RequestToHarmonyRecord links are immutable — \
             the finalisation index cannot be removed".into(),
        )),

        FlatOp::RegisterDeleteLink {
            link_type: LinkTypes::StudyToBadge,
            ..
        } => Ok(ValidateCallbackResult::Invalid(
            "StudyToBadge links are immutable — \
             issued badges cannot be hidden".into(),
        )),

        FlatOp::RegisterDeleteLink {
            link_type: LinkTypes::AllDecisions,
            ..
        } => Ok(ValidateCallbackResult::Invalid(
            "AllDecisions links are immutable — \
             the governance decision index is append-only".into(),
        )),

        // All other ops: valid. Public DHT — open read is the design intent.
        _ => Ok(ValidateCallbackResult::Valid),
    }
}


// ---------------------------------------------------------------------------
// Badge-type derivation — mirrors evaluate_badge in valichord_shared_types.
// Kept here so the integrity zome can enforce badge-tier rules network-wide.
// Any change to tier thresholds MUST be applied to both functions identically.
// ---------------------------------------------------------------------------

/// Returns the MAXIMUM badge type the coordinator may issue for the given
/// agreement level and raw (unfiltered) validator count.
///
/// The integrity zome cannot perform DHT reputation lookups, so it cannot
/// enforce the tier-qualified thresholds that the coordinator applies
/// (standard_plus >= 5 for Silver, advanced_plus >= 7 for Gold).
/// Instead it enforces two network-verifiable constraints:
///   1. Quorum: at least 3 validators participated.
///   2. Ceiling: the issued badge tier must NOT exceed what raw count
///      warrants — the coordinator may downgrade (Bronze when tier-qualified
///      count is too low for Silver) but may never inflate above the ceiling.
/// Direction consistency (Reproduced ↔ positive agreement) is checked
/// separately by `badge_is_reproduced`.
fn badge_ceiling(
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
        AgreementLevel::Divergent | AgreementLevel::UnableToAssess
            if validator_count >= 3 =>
        {
            Some(BadgeType::FailedReproduction)
        }
        _ => None,
    }
}

fn badge_is_reproduced(bt: &BadgeType) -> bool {
    !matches!(bt, BadgeType::FailedReproduction)
}

/// Rank within the Reproduced track: Bronze=1, Silver=2, Gold=3.
/// FailedReproduction is on a separate track and returns 0 (unused for
/// cross-track comparisons since direction is checked first).
fn badge_tier_rank(bt: &BadgeType) -> u8 {
    match bt {
        BadgeType::BronzeReproducible => 1,
        BadgeType::SilverReproducible => 2,
        BadgeType::GoldReproducible   => 3,
        BadgeType::FailedReproduction => 0,
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
