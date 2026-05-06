//! Wind-Tunnel scenario: validation_request_throughput
//!
//! What this measures
//! ------------------
//! Concurrent write throughput for the ValiChord commit phase.  N agents each
//! call `submit_validation_request` followed by `notify_commitment_sealed` in a
//! tight loop, generating unique request_refs per (agent, iteration) so there
//! are no DHT collisions.
//!
//! Wind-Tunnel auto-captures per-call latency for every `call_zome` invocation
//! (labelled by fn name).  This scenario additionally reports a `commits_sent`
//! counter so the total throughput across all agents can be summed.
//!
//! Run:
//!   cargo run -p validation_request_throughput -- --agents 4 --duration 60
//!   cargo run -p validation_request_throughput -- --agents 8 --duration 120 --reporter=influx-file

use holochain_wind_tunnel_runner::prelude::*;
use holo_hash::{ActionHash, ExternalHash};

use attestation_integrity::{ValidationRequest, ValidationTier};
use valichord_shared_types::{CommitmentSealedInput, Discipline};

// ---------------------------------------------------------------------------
// Per-agent state
// ---------------------------------------------------------------------------

#[derive(Debug, Default)]
struct ScenarioValues {
    iteration: u32,
    commits_sent: u32,
}

impl UserValuesConstraint for ScenarioValues {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Derive a unique 32-byte ExternalHash from (agent_index, iteration).
/// Bytes 0-3: agent index (little-endian u32).
/// Bytes 4-7: iteration counter (little-endian u32).
/// Bytes 8-31: zero.
fn unique_data_hash(agent_index: usize, iteration: u32) -> ExternalHash {
    let mut bytes = [0u8; 32];
    bytes[..4].copy_from_slice(&(agent_index as u32).to_le_bytes());
    bytes[4..8].copy_from_slice(&iteration.to_le_bytes());
    ExternalHash::from_raw_32(bytes.to_vec())
}

fn make_validation_request(data_hash: ExternalHash) -> ValidationRequest {
    ValidationRequest {
        protocol_ref: None,
        data_hash,
        data_access_url: "https://osf.io/wind-tunnel-test".into(),
        deposit_access_type: Default::default(),
        deposit_token: None,
        protocol_access_url: None,
        // 2 validators required — same as production default.
        // CommitmentAnchor writes land on the DHT but RevealOpen is never
        // triggered (only one agent commits per request), so the scenario
        // exercises pure write throughput without triggering phase transitions.
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

fn agent_behaviour(
    ctx: &mut AgentContext<HolochainRunnerContext, HolochainAgentContext<ScenarioValues>>,
) -> HookResult {
    let agent_index = ctx.agent_index();
    let iteration = ctx.get().scenario_values.iteration;

    let data_hash = unique_data_hash(agent_index, iteration);

    // Write ValidationRequest to DNA3 (attestation_coordinator).
    // Wind-Tunnel auto-captures submit_validation_request call latency.
    let _: ActionHash = call_zome(
        ctx,
        "attestation_coordinator",
        "submit_validation_request",
        make_validation_request(data_hash.clone()),
    )?;

    // Write CommitmentAnchor to DNA3.
    // Wind-Tunnel auto-captures notify_commitment_sealed call latency.
    let _: () = call_zome(
        ctx,
        "attestation_coordinator",
        "notify_commitment_sealed",
        CommitmentSealedInput {
            request_ref: data_hash,
            // Zero hash: dev bypass — see attestation_integrity validate().
            commitment_hash: vec![0u8; 32],
        },
    )?;

    ctx.get_mut().scenario_values.iteration += 1;
    ctx.get_mut().scenario_values.commits_sent += 1;

    let commits_sent = ctx.get().scenario_values.commits_sent;
    ctx.runner_context()
        .reporter()
        .clone()
        .add_custom(ReportMetric::new("commits_sent").with_field("value", commits_sent as f64));

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
    .use_agent_behaviour(agent_behaviour)
    .use_agent_teardown(agent_teardown);

    run(builder)?;
    Ok(())
}
