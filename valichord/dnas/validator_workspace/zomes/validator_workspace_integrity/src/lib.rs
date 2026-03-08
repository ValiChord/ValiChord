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
#[hdk_entry_helper]
#[derive(Clone)]
pub struct ValidationTask {
    /// References the ValidationRequest entry in the Attestation DNA.
    pub request_ref:         ExternalHash,
    pub assigned_at_secs:    u64,
    pub discipline:          Discipline,
    pub deadline_secs:       u64,
    pub validation_focus:    ValidationFocus,
    pub time_cap_secs:       u64,
    pub compensation_tier:   CompensationTier,
}

/// THE COMMIT PHASE — the validator's sealed private attestation.
///
/// Stored as a private entry: invisible to all peers and the shared DHT.
/// Its *existence* is verifiable via `get_agent_activity` (the private action
/// appears in the source chain header sequence). Its *content* is not revealed
/// until the validator calls `reveal_attestation` on DNA 3.
///
/// IMMUTABLE after creation — validate() blocks all updates and deletes.
/// This guarantees the commitment is exactly what was filed before unblinding.
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
    pub sealed_at_secs:          u64,
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
