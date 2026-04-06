use hdk::prelude::*;
use validator_workspace_integrity::{EntryTypes, LinkTypes, ValidationTask, ValidatorPrivateAttestation};
use valichord_shared_types::{CommitmentSealedInput, ValidationAttestation};
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// No init() needed.
// Single-agent private DNA — author grant covers all calls automatically.
// No remote agents need capability access.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Input struct for seal_private_attestation
// ---------------------------------------------------------------------------

/// Input for seal_private_attestation.
///
/// `attestation` is the EXACT `ValidationAttestation` that will be revealed
/// publicly during the reveal phase.  The coordinator serialises it and
/// hashes it (with a generated nonce) to produce the `commitment_hash` that
/// goes to the shared Attestation DHT.  The caller must NOT supply `nonce` or
/// `commitment_hash` — they are generated here.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SealAttestationInput {
    pub task_hash:   ActionHash,
    pub attestation: ValidationAttestation,
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
/// 1. Generates a random 32-byte nonce via Holochain's `random_bytes` host function.
/// 2. Serialises `input.attestation` to MessagePack (same encoding Holochain
///    uses for all DHT entries, so the commitment hash is reproducible at
///    reveal time using only the public attestation + nonce).
/// 3. Computes `commitment_hash = SHA-256(msgpack_bytes || nonce)`.
/// 4. Stores the full `ValidatorPrivateAttestation` (including nonce and hash)
///    as a PRIVATE entry — content never leaves this device.
/// 5. `post_commit` fires after the write and cross-calls the Attestation DNA's
///    `notify_commitment_sealed` with the commitment_hash so the shared DHT
///    records that this validator has committed (without revealing any content).
#[hdk_extern]
pub fn seal_private_attestation(input: SealAttestationInput) -> ExternResult<ActionHash> {
    // 1. Random 32-byte nonce — HDK host function, never available in validate().
    let nonce: Vec<u8> = random_bytes(32)?.to_vec();

    // 2. Serialise the public attestation to MessagePack.
    //    SerializedBytes uses rmp_serde::to_vec_named internally — the same
    //    codec the Attestation DNA will use when verifying the reveal.
    let msgpack_bytes: Vec<u8> = SerializedBytes::try_from(&input.attestation)
        .map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?
        .bytes()
        .to_vec();

    // 3. commitment_hash = SHA-256(msgpack_bytes || nonce)
    let mut hasher = Sha256::new();
    hasher.update(&msgpack_bytes);
    hasher.update(&nonce);
    let commitment_hash: Vec<u8> = hasher.finalize().to_vec();

    // 4. Build the private entry — destructure input.attestation to move
    //    each field directly (avoids 8 heap clones on String/Vec/enum fields).
    let ValidationAttestation {
        request_ref,
        outcome,
        outcome_summary,
        time_invested_secs,
        time_breakdown,
        deviation_flags,
        computational_resources,
        confidence,
        discipline,
        commitment_anchor_hash: _, // set by attestation coordinator after reveal
    } = input.attestation;
    let private_attestation = ValidatorPrivateAttestation {
        request_ref,
        outcome,
        outcome_summary,
        time_invested_secs,
        time_breakdown,
        deviation_flags,
        computational_resources,
        confidence,
        discipline,
        nonce,
        commitment_hash,
    };

    let attestation_hash =
        create_entry(EntryTypes::ValidatorPrivateAttestation(private_attestation))?;
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
            // Use query() instead of get() — query() is strictly scoped to
            // THIS agent's source chain and cannot cross cell boundaries.
            // get(target, GetOptions::local()) would find Alice's private entry
            // from Bob's cell in singleFork/test conductors because all cells
            // share the same local DB. query() is always source-chain-local.
            let records = query(ChainQueryFilter::new().action_type(ActionType::Create).include_entries(true))?;
            Ok(records.into_iter().find(|r| *r.action_address() == target))
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
    let records = query(ChainQueryFilter::new().action_type(ActionType::Create).include_entries(true))?;
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
    let records = query(ChainQueryFilter::new().action_type(ActionType::Create).include_entries(true))?;
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
                    // Pass both the request identifier AND the commitment_hash
                    // so the Attestation DNA can record a fully-formed
                    // CommitmentAnchor without knowing the private content.
                    let sealed_input = CommitmentSealedInput {
                        request_ref:     attestation.request_ref,
                        commitment_hash: attestation.commitment_hash,
                    };
                    let _result: ExternResult<ZomeCallResponse> = call(
                        CallTargetCell::OtherRole("attestation".into()),
                        ZomeName::from("attestation_coordinator"),
                        FunctionName::from("notify_commitment_sealed"),
                        None,
                        sealed_input,
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
