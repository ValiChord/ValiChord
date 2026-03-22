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
            let original_record = must_get_valid_record(action.deletes_address.clone())?;
            if let Some(EntryType::App(app_def)) = original_record.action().entry_type() {
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
            if action.author != *original_record.action().author() {
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
