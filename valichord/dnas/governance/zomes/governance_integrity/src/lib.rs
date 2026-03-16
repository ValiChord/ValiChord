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
