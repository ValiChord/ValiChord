use hdk::prelude::*;
use validator_workspace_integrity::{EntryTypes, LinkTypes, ValidationTask, ValidatorPrivateAttestation};

// ---------------------------------------------------------------------------
// No init() needed.
// Single-agent private DNA — author grant covers all calls automatically.
// No remote agents need capability access.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Input struct for seal_private_attestation
// ---------------------------------------------------------------------------

/// Input for seal_private_attestation: task to link from + the attestation to create.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SealAttestationInput {
    pub task_hash:   ActionHash,
    pub attestation: ValidatorPrivateAttestation,
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

/// Receive a validation task from the Attestation DNA and store it locally.
#[hdk_extern]
pub fn receive_task(task: ValidationTask) -> ExternResult<ActionHash> {
    create_entry(EntryTypes::ValidationTask(task))
}

/// Seal the validator's private attestation — the COMMIT PHASE.
///
/// Writes a private entry: visible only on this validator's own source chain.
/// post_commit fires after the write and notifies the Attestation DNA.
#[hdk_extern]
pub fn seal_private_attestation(input: SealAttestationInput) -> ExternResult<ActionHash> {
    let attestation_hash =
        create_entry(EntryTypes::ValidatorPrivateAttestation(input.attestation))?;
    create_link(
        input.task_hash,
        attestation_hash.clone(),
        LinkTypes::TaskToPrivateAttestation,
        (),
    )?;
    Ok(attestation_hash)
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn get_task(task_hash: ActionHash) -> ExternResult<Option<Record>> {
    get(task_hash, GetOptions::local())
}

/// Return the private attestation linked from a task, if any.
#[hdk_extern]
pub fn get_private_attestation_for_task(
    task_hash: ActionHash,
) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(task_hash, LinkTypes::TaskToPrivateAttestation)?,
        GetStrategy::Local,
    )?;
    match links.first() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid TaskToPrivateAttestation link target".into()
                )))?;
            get(target, GetOptions::local())
        }
        None => Ok(None),
    }
}

/// Return all ValidationTask records from the local source chain.
#[hdk_extern]
pub fn get_all_tasks(_: ()) -> ExternResult<Vec<Record>> {
    let filter = ChainQueryFilter::new()
        .entry_type(EntryType::App(AppEntryDef {
            zome_index: ZomeIndex(0),
            entry_index: EntryDefIndex(0), // ValidationTask is index 0
            visibility: EntryVisibility::Private,
        }))
        .include_entries(true);
    let records = query(filter)?;
    Ok(records)
}

// ---------------------------------------------------------------------------
// post_commit — notify Attestation DNA when a ValidatorPrivateAttestation
// is sealed to this source chain.
// ---------------------------------------------------------------------------
//
// `infallible` — failures are logged and silently dropped, never panic.
// The cross-DNA call uses the author grant; same-agent calls are always
// permitted without an explicit capability grant.

#[hdk_extern(infallible)]
pub fn post_commit(committed_actions: Vec<SignedActionHashed>) {
    if let Err(e) = _post_commit_inner(committed_actions) {
        debug!("post_commit error (non-fatal): {:?}", e);
    }
}

fn _post_commit_inner(committed_actions: Vec<SignedActionHashed>) -> ExternResult<()> {
    for signed in committed_actions {
        if let Action::Create(create) = signed.action() {
            // Private entries embed the entry in the Create action — check
            // the app entry def index to identify ValidatorPrivateAttestation.
            if let Some(EntryType::App(app_def)) = Some(create.entry_type.clone()) {
                // EntryDefIndex 1 = ValidatorPrivateAttestation (0 = ValidationTask)
                if app_def.entry_index == EntryDefIndex(1) {
                    // Fetch the entry to extract request_ref.
                    let record = get(create.entry_hash.clone(), GetOptions::local())?;
                    if let Some(rec) = record {
                        if let Some(entry) = rec.entry().as_option() {
                            if let Ok(Some(EntryTypes::ValidatorPrivateAttestation(
                                attestation,
                            ))) = EntryTypes::deserialize_from_type(
                                app_def.zome_index,
                                app_def.entry_index,
                                entry,
                            ) {
                                let request_ref = attestation.request_ref.clone();
                                // Fire-and-forget — notify DNA 3 that this
                                // validator's commitment is now sealed.
                                let _result: ExternResult<ZomeCallResponse> = call(
                                    CallTargetCell::OtherRole("attestation".into()),
                                    ZomeName::from("attestation_coordinator"),
                                    FunctionName::from("notify_commitment_sealed"),
                                    None,
                                    request_ref,
                                );
                                if let Err(e) = _result {
                                    debug!(
                                        "notify_commitment_sealed call failed (non-fatal): {:?}",
                                        e
                                    );
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    Ok(())
}
