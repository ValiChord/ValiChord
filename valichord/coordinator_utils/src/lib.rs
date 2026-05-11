use hdk::prelude::*;

/// Fetch records for a list of links whose targets are ActionHashes (network).
/// Skips links with non-ActionHash targets and missing records.
pub fn records_for_links(links: Vec<Link>) -> ExternResult<Vec<Record>> {
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

/// Call a zome function on another role in this hApp and decode the response.
///
/// Returns `Ok(None)` on any cross-DNA failure (network error, unauthorized,
/// decode error) — callers use the None path to abort conservatively without
/// failing the calling function.
///
/// Use this as the base for named, role-specific wrappers (e.g.
/// `call_attestation_zome_opt`) that add context to the role string and
/// document the calling conventions for each cross-DNA boundary.
pub fn call_other_role_opt<I, O>(
    role: &str,
    zome: &str,
    fn_name: &str,
    input: I,
) -> ExternResult<Option<O>>
where
    I: serde::Serialize + std::fmt::Debug,
    O: serde::de::DeserializeOwned + std::fmt::Debug,
{
    let response = call(
        CallTargetCell::OtherRole(role.into()),
        ZomeName::from(zome),
        FunctionName::from(fn_name),
        None,
        input,
    )?;
    match response {
        ZomeCallResponse::Ok(extern_io) => match extern_io.decode::<O>() {
            Ok(v) => Ok(Some(v)),
            Err(e) => {
                warn!("call_other_role_opt({role}/{fn_name}): decode failed: {e}");
                Ok(None)
            }
        },
        other => {
            warn!("call_other_role_opt({role}/{fn_name}): non-Ok response: {other:?}");
            Ok(None)
        }
    }
}
