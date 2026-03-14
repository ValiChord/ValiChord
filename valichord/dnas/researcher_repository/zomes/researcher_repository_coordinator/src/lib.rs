use hdk::prelude::*;
use researcher_repository_integrity::{
    DeclaredDeviation, EntryTypes, LinkTypes, PreRegisteredProtocol, ResearchStudy,
    VerifiedDataSnapshot,
};
use valichord_shared_types::UndeclaredDeviation;
use sha2::{Sha256, Digest};

// ---------------------------------------------------------------------------
// No init() needed.
// Single-agent private DNA — author grant covers all calls automatically.
// No remote agents need capability access.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Input structs for multi-field write functions
// ---------------------------------------------------------------------------

/// Input for register_protocol: study to link from + the protocol to create.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisterProtocolInput {
    pub study_ref: ActionHash,
    pub protocol:  PreRegisteredProtocol,
}

/// Input for take_data_snapshot: study to link from + the snapshot to create.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TakeDataSnapshotInput {
    pub study_ref: ActionHash,
    pub snapshot:  VerifiedDataSnapshot,
}

/// Input for declare_deviation: study to link from + the deviation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeclareDeviationInput {
    pub study_ref: ActionHash,
    pub deviation: UndeclaredDeviation,
}

// ---------------------------------------------------------------------------
// Write functions
// ---------------------------------------------------------------------------

/// Register a new research study.
#[hdk_extern]
pub fn register_study(study: ResearchStudy) -> ExternResult<ActionHash> {
    create_entry(EntryTypes::ResearchStudy(study))
}

/// Return all ResearchStudy records from this agent's local source chain.
///
/// Uses query() + deserialization filter — avoids hardcoded ZomeIndex which
/// breaks silently if entry ordering changes.
#[hdk_extern]
pub fn get_all_studies(_: ()) -> ExternResult<Vec<Record>> {
    let records = query(ChainQueryFilter::new().include_entries(true))?;
    let studies = records
        .into_iter()
        .filter(|r| {
            r.entry()
                .to_app_option::<ResearchStudy>()
                .ok()
                .flatten()
                .is_some()
        })
        .collect();
    Ok(studies)
}

/// Register a pre-registered protocol and link it from the parent study.
///
/// PreRegisteredProtocol is IMMUTABLE after this call — validate() enforces
/// that no updates or deletes are possible.
#[hdk_extern]
pub fn register_protocol(input: RegisterProtocolInput) -> ExternResult<ActionHash> {
    let protocol_hash =
        create_entry(EntryTypes::PreRegisteredProtocol(input.protocol))?;
    create_link(
        input.study_ref,
        protocol_hash.clone(),
        LinkTypes::StudyToProtocol,
        (),
    )?;
    Ok(protocol_hash)
}

/// Record a dataset snapshot and link it from the parent study.
///
/// Only the hash and metadata are stored — the data bytes themselves are
/// never passed to this function. Use compute_data_hash() first.
#[hdk_extern]
pub fn take_data_snapshot(input: TakeDataSnapshotInput) -> ExternResult<ActionHash> {
    let snapshot_hash =
        create_entry(EntryTypes::VerifiedDataSnapshot(input.snapshot))?;
    create_link(
        input.study_ref,
        snapshot_hash.clone(),
        LinkTypes::StudyToSnapshot,
        (),
    )?;
    Ok(snapshot_hash)
}

/// Record a declared deviation from the pre-registered plan.
///
/// Stored as a separate private DeclaredDeviation entry — the original
/// PreRegisteredProtocol is never modified, preserving immutability.
/// The deviation is linked from the study for structured discovery.
#[hdk_extern]
pub fn declare_deviation(input: DeclareDeviationInput) -> ExternResult<ActionHash> {
    let deviation_hash = create_entry(EntryTypes::DeclaredDeviation(
        DeclaredDeviation { deviation: input.deviation },
    ))?;
    create_link(
        input.study_ref,
        deviation_hash.clone(),
        LinkTypes::StudyToDeviation,
        (),
    )?;
    Ok(deviation_hash)
}

// ---------------------------------------------------------------------------
// Read functions
// ---------------------------------------------------------------------------

#[hdk_extern]
pub fn get_study(hash: ActionHash) -> ExternResult<Option<Record>> {
    get(hash, GetOptions::local())
}

/// Return the first (and typically only) protocol linked from a study.
#[hdk_extern]
pub fn get_protocol_for_study(study_hash: ActionHash) -> ExternResult<Option<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_hash, LinkTypes::StudyToProtocol)?,
        GetStrategy::Local,
    )?;
    match links.first() {
        Some(link) => {
            let target = link
                .target
                .clone()
                .into_action_hash()
                .ok_or(wasm_error!(WasmErrorInner::Guest(
                    "Invalid StudyToProtocol link target".into()
                )))?;
            get(target, GetOptions::local())
        }
        None => Ok(None),
    }
}

#[hdk_extern]
pub fn get_snapshots_for_study(study_hash: ActionHash) -> ExternResult<Vec<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_hash, LinkTypes::StudyToSnapshot)?,
        GetStrategy::Local,
    )?;
    let mut records = Vec::new();
    for link in links {
        if let Some(hash) = link.target.into_action_hash() {
            if let Some(record) = get(hash, GetOptions::local())? {
                records.push(record);
            }
        }
    }
    Ok(records)
}

#[hdk_extern]
pub fn get_deviations_for_study(study_hash: ActionHash) -> ExternResult<Vec<Record>> {
    let links = get_links(
        LinkQuery::try_new(study_hash, LinkTypes::StudyToDeviation)?,
        GetStrategy::Local,
    )?;
    let mut records = Vec::new();
    for link in links {
        if let Some(hash) = link.target.into_action_hash() {
            if let Some(record) = get(hash, GetOptions::local())? {
                records.push(record);
            }
        }
    }
    Ok(records)
}

/// Compute SHA-256 of data bytes and return as a Holochain ExternalHash.
///
/// Engineering constraint #6: SHA-256 for research file fingerprints.
/// BLAKE2b is Holochain-internal. The sha2 crate is compiled to WASM via
/// Cargo.toml. The resulting ExternalHash is what the researcher passes to
/// the Attestation DNA's ValidationRequest.data_hash field.
///
/// The data bytes NEVER leave this private DNA — only the hash travels.
/// This is the primary GDPR protection: membrane separation ensures sensitive
/// data cannot enter the shared DHT by architecture, not policy.
#[hdk_extern]
pub fn compute_data_hash(data: Vec<u8>) -> ExternResult<ExternalHash> {
    let sha256_bytes: Vec<u8> = Sha256::digest(&data).to_vec();
    // from_raw_32 prepends the External hash type prefix [0x84, 0x2F, 0x24]
    // and computes the 4-byte DHT location from the 32-byte SHA-256 core.
    Ok(ExternalHash::from_raw_32(sha256_bytes))
}
