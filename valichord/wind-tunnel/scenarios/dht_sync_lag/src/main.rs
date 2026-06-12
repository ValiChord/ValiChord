//! Wind-Tunnel scenario: dht_sync_lag (ValiChord)
//!
//! What this measures
//! ------------------
//! True cross-agent DHT propagation latency of a real ValiChord entry. One or
//! more `write` agents author `ValidationRequest`s; one or more `record_lag`
//! reader agents discover them via the global pending-requests anchor and record
//! how long each took to become visible:
//!
//!     sync_lag = reader_observed_time - request_author_action_timestamp
//!
//! The reader knows nothing in advance — `get_pending_request_refs` returns every
//! request ref that has gossiped to that agent, so everything it sees arrived via
//! the DHT. The send-time is the authoring conductor's Action timestamp, so no
//! `created_at` field (and therefore no integrity/DNA-hash change) is needed.
//!
//! Relationship to the other scenarios
//! -----------------------------------
//! * kitsune_dht_propagation — raw kitsune2 substrate, no ValiChord code.
//! * phase_observation_latency — single agent observes its OWN write becoming a
//!   PhaseMarker (app-logic latency, not cross-agent gossip).
//! * dht_sync_lag (this one) — cross-agent gossip of an actual ValiChord entry.
//!
//! Run (one writer, two readers):
//!   cargo run -p dht_sync_lag -- --agents 3 --duration 60 \
//!     --behaviour=write:1 --behaviour=record_lag:2
//!
//! Single-host assumption: all agents share a wall clock, so `now - authored_at`
//! needs no clock-skew correction.

use holochain_wind_tunnel_runner::prelude::*;
use holo_hash::{ActionHash, ExternalHash};
use holochain_types::prelude::Record;
use std::collections::HashSet;
use std::time::SystemTime;

use attestation_integrity::{ValidationRequest, ValidationTier};
use valichord_shared_types::Discipline;

// ---------------------------------------------------------------------------
// Per-agent state
// ---------------------------------------------------------------------------

#[derive(Debug, Default)]
struct ScenarioValues {
    /// Writer: monotonically increasing per-agent iteration counter.
    iteration: u32,
    /// Writer: total ValidationRequests submitted.
    sent_count: u32,
    /// Reader: request refs already measured, so each is counted once.
    seen: HashSet<ExternalHash>,
}

impl UserValuesConstraint for ScenarioValues {}

// ---------------------------------------------------------------------------
// Pure helpers (unit-tested below — no conductor required)
// ---------------------------------------------------------------------------

/// Derive a unique 32-byte ExternalHash from (agent_index, iteration).
/// Bytes 0-3: agent index (LE u32). Bytes 4-7: iteration (LE u32). Rest: zero.
/// Collision-free per (agent, iteration), so the per-data_hash idempotency guard
/// in submit_validation_request never trips.
fn unique_data_hash(agent_index: usize, iteration: u32) -> ExternalHash {
    let mut bytes = [0u8; 32];
    bytes[..4].copy_from_slice(&(agent_index as u32).to_le_bytes());
    bytes[4..8].copy_from_slice(&iteration.to_le_bytes());
    ExternalHash::from_raw_32(bytes.to_vec())
}

/// Propagation latency in seconds from author time to observation time, both in
/// microseconds since the Unix epoch. Saturating so that any residual skew (an
/// entry whose Action timestamp is marginally ahead of the reader's clock) reads
/// as 0 rather than a spurious negative.
fn propagation_lag_s(observed_us: u128, authored_us: u128) -> f64 {
    observed_us.saturating_sub(authored_us) as f64 / 1e6
}

fn make_validation_request(data_hash: ExternalHash) -> ValidationRequest {
    ValidationRequest {
        protocol_ref: None,
        data_hash,
        data_access_url: "https://osf.io/wind-tunnel-test".into(),
        deposit_access_type: Default::default(),
        deposit_token: None,
        protocol_access_url: None,
        // Irrelevant here — this scenario never reaches commit/reveal, so the
        // request simply stays pending and discoverable.
        num_validators_required: 2,
        validation_tier: ValidationTier::Basic,
        discipline: Discipline::ComputationalBiology,
        researcher_institution: "Wind Tunnel Lab".into(),
    }
}

fn valichord_happ_path() -> std::path::PathBuf {
    std::env::var("VALICHORD_HAPP_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| {
            std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../../workdir/valichord.happ")
        })
}

// ---------------------------------------------------------------------------
// Lifecycle hooks
// ---------------------------------------------------------------------------

fn agent_setup(
    ctx: &mut AgentContext<HolochainRunnerContext, HolochainAgentContext<ScenarioValues>>,
) -> HookResult {
    start_conductor_and_configure_urls(ctx)?;
    install_app(ctx, valichord_happ_path(), &"valichord".to_string())?;
    Ok(())
}

/// `write` behaviour: author one fresh ValidationRequest per iteration. No
/// notify_commitment_sealed — the request must stay pending so readers can
/// discover it via the global pending anchor.
fn agent_behaviour_write(
    ctx: &mut AgentContext<HolochainRunnerContext, HolochainAgentContext<ScenarioValues>>,
) -> HookResult {
    let agent_index = ctx.agent_index();
    let iteration = ctx.get().scenario_values.iteration;
    let data_hash = unique_data_hash(agent_index, iteration);

    let _: ActionHash = call_zome(
        ctx,
        "attestation_coordinator",
        "submit_validation_request",
        make_validation_request(data_hash),
    )?;

    ctx.get_mut().scenario_values.iteration += 1;
    ctx.get_mut().scenario_values.sent_count += 1;

    let sent = ctx.get().scenario_values.sent_count;
    let agent = ctx.get().cell_id().agent_pubkey().to_string();
    ctx.runner_context().reporter().clone().add_custom(
        ReportMetric::new("sent_count")
            .with_tag("agent", agent)
            .with_field("value", sent as f64),
    );

    Ok(())
}

/// `record_lag` behaviour: discover every pending request that has gossiped in,
/// and for each one not yet measured, emit its propagation latency.
fn agent_behaviour_record_lag(
    ctx: &mut AgentContext<HolochainRunnerContext, HolochainAgentContext<ScenarioValues>>,
) -> HookResult {
    let refs: Vec<ExternalHash> = call_zome(
        ctx,
        "attestation_coordinator",
        "get_pending_request_refs",
        (),
    )?;

    // Collect first so the immutable borrow is released before the loop's
    // mutable borrows / zome calls.
    let new_refs: Vec<ExternalHash> = refs
        .into_iter()
        .filter(|r| !ctx.get().scenario_values.seen.contains(r))
        .collect();

    let reporter = ctx.runner_context().reporter().clone();
    let agent = ctx.get().cell_id().agent_pubkey().to_string();

    for data_hash in new_refs {
        let record: Option<Record> = call_zome(
            ctx,
            "attestation_coordinator",
            "get_validation_request_for_data_hash",
            data_hash.clone(),
        )?;

        // The ref link can arrive slightly before the full record. If the record
        // isn't fetchable yet, leave it unseen and retry on a later iteration.
        if let Some(record) = record {
            let metric = ReportMetric::new("sync_lag");
            let observed_us = metric
                .timestamp
                .duration_since(SystemTime::UNIX_EPOCH)
                .expect("system clock before Unix epoch")
                .as_micros();
            let authored_us = record.action().timestamp().as_micros() as u128;
            let lag_s = propagation_lag_s(observed_us, authored_us);

            reporter.add_custom(
                metric
                    .with_tag("agent", agent.clone())
                    .with_field("value", lag_s),
            );
            ctx.get_mut().scenario_values.seen.insert(data_hash);
        }
    }

    let seen_count = ctx.get().scenario_values.seen.len();
    reporter.add_custom(
        ReportMetric::new("recv_count")
            .with_tag("agent", agent)
            .with_field("value", seen_count as f64),
    );

    Ok(())
}

fn agent_teardown(
    ctx: &mut AgentContext<HolochainRunnerContext, HolochainAgentContext<ScenarioValues>>,
) -> HookResult {
    uninstall_app(ctx, None).ok();
    Ok(())
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

fn main() -> WindTunnelResult<()> {
    let builder = ScenarioDefinitionBuilder::<
        HolochainRunnerContext,
        HolochainAgentContext<ScenarioValues>,
    >::new_with_init(env!("CARGO_PKG_NAME"))
    .with_default_duration_s(60)
    .use_agent_setup(agent_setup)
    .use_named_agent_behaviour("write", agent_behaviour_write)
    .use_named_agent_behaviour("record_lag", agent_behaviour_record_lag)
    .use_agent_teardown(agent_teardown);

    run(builder)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Unit tests — pure logic only, no conductor.
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unique_data_hash_is_collision_free_per_agent_and_iteration() {
        let a = unique_data_hash(0, 0);
        let b = unique_data_hash(0, 1);
        let c = unique_data_hash(1, 0);
        assert_ne!(a, b, "different iterations must differ");
        assert_ne!(a, c, "different agents must differ");
        assert_eq!(a, unique_data_hash(0, 0), "same inputs must be stable");
    }

    #[test]
    fn propagation_lag_is_positive_when_observed_after_authored() {
        // 250 ms later -> 0.25 s
        assert_eq!(propagation_lag_s(1_000_000 + 250_000, 1_000_000), 0.25);
    }

    #[test]
    fn propagation_lag_is_zero_when_observed_equals_authored() {
        assert_eq!(propagation_lag_s(1_000_000, 1_000_000), 0.0);
    }

    #[test]
    fn propagation_lag_saturates_to_zero_under_skew() {
        // Observed before authored (residual skew) -> clamped to 0, not negative.
        assert_eq!(propagation_lag_s(999_000, 1_000_000), 0.0);
    }
}
