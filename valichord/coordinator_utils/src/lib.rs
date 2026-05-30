use hdk::prelude::*;

/// Fetch records for a list of links whose targets are ActionHashes (network).
/// Skips links with non-ActionHash targets and missing records.
///
/// Issues a single batched `get` host call for all targets instead of one call
/// per link. The conductor resolves the batch together (parallel network
/// fetches), cutting WASM↔host boundary crossings from N to 1 — a meaningful
/// saving on fan-out reads like `get_attestations_for_discipline` (up to 500
/// links). Semantics are identical to N sequential `get(.., network())` calls:
/// non-ActionHash targets are skipped, missing records are filtered out, and
/// the surviving records stay in link order.
///
/// `HDK.with(|h| h.borrow().get(inputs))` is exactly what the single-hash
/// `get()` wraps internally (see hdk::entry::get) — this is the idiomatic
/// batched form, not a workaround.
pub fn records_for_links(links: Vec<Link>) -> ExternResult<Vec<Record>> {
    let inputs: Vec<GetInput> = links
        .into_iter()
        .filter_map(|link| link.target.into_action_hash())
        .map(|hash| GetInput::new(AnyDhtHash::from(hash), GetOptions::network()))
        .collect();
    if inputs.is_empty() {
        return Ok(Vec::new());
    }
    let results = HDK.with(|h| h.borrow().get(inputs))?;
    Ok(results.into_iter().flatten().collect())
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
