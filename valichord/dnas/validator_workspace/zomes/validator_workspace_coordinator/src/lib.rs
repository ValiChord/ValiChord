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

/// Return all ValidatorPrivateAttestation records from the local source chain.
///
/// Uses query() + deserialization filter — avoids hardcoded ZomeIndex which
/// breaks silently if entry ordering changes.
#[hdk_extern]
pub fn get_all_private_attestations(_: ()) -> ExternResult<Vec<Record>> {
    let records = query(ChainQueryFilter::new().include_entries(true))?;
    let attestations = records
        .into_iter()
        .filter(|r| {
            r.entry()
                .to_app_option::<ValidatorPrivateAttestation>()
                .ok()
                .flatten()
                .is_some()
        })
        .collect();
    Ok(attestations)
}

/// Return all ValidationTask records from the local source chain.
///
/// Queries all private entries and filters by successful deserialization as
/// ValidationTask — avoids hardcoded ZomeIndex/EntryDefIndex which break
/// silently if entry ordering ever changes.
#[hdk_extern]
pub fn get_all_tasks(_: ()) -> ExternResult<Vec<Record>> {
    let records = query(ChainQueryFilter::new().include_entries(true))?;
    let tasks = records
        .into_iter()
        .filter(|r| {
            r.entry()
                .to_app_option::<ValidationTask>()
                .ok()
                .flatten()
                .is_some()
        })
        .collect();
    Ok(tasks)
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
            // Fetch the entry and try to deserialize as ValidatorPrivateAttestation.
            // This avoids hardcoded ZomeIndex/EntryDefIndex which break silently
            // if entry ordering changes.
            let record = get(create.entry_hash.clone(), GetOptions::local())?;
            if let Some(rec) = record {
                if let Some(attestation) = rec
                    .entry()
                    .to_app_option::<ValidatorPrivateAttestation>()
                    .ok()
                    .flatten()
                {
                    let request_ref = attestation.request_ref.clone();
                    // Fire-and-forget — notify DNA 3 that this validator's
                    // commitment is now sealed.
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
    Ok(())
}
