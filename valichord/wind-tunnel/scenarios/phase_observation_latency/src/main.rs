//! Wind-Tunnel scenario: phase_observation_latency
//!
//! What this measures
//! ------------------
//! The delay between writing a CommitmentAnchor and observing the resulting
//! PhaseMarker(RevealOpen) via a DHT read.
//!
//! Uses `num_validators_required: 1` so a single `notify_commitment_sealed`
//! call is sufficient to trigger the PhaseMarker write inside
//! `check_all_commitments_sealed_inner`.  After committing, the agent polls
//! `get_current_phase` in a tight loop and records how many milliseconds
//! elapsed before RevealOpen becomes visible.
//!
//! This end-to-end path exercises:
//!   CommitmentAnchor write → DHT gossip → PhaseMarker write → DHT gossip →
//!   get_current_phase returns Some("RevealOpen")
//!
//! Key metrics (custom):
//!   `phase_observation_ms` — time from notify_commitment_sealed returning to
//!                            first RevealOpen observation (ms)
//!   `poll_count`           — number of get_current_phase calls per iteration
//!
//! Run:
//!   cargo run -p phase_observation_latency -- --agents 2 --duration 60
//!   cargo run -p phase_observation_latency -- --agents 4 --duration 120 --reporter=influx-file

use std::time::Instant;

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
}

impl UserValuesConstraint for ScenarioValues {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn unique_data_hash(agent_index: usize, iteration: u32) -> ExternalHash {
    let mut bytes = [0u8; 32];
    bytes[..4].copy_from_slice(&(agent_index as u32).to_le_bytes());
    bytes[4..8].copy_from_slice(&iteration.to_le_bytes());
    ExternalHash::from_raw_32(bytes.to_vec())
}

fn make_single_validator_request(data_hash: ExternalHash) -> ValidationRequest {
    ValidationRequest {
        protocol_ref: None,
        data_hash,
        data_access_url: "https://osf.io/wind-tunnel-test".into(),
        deposit_access_type: Default::default(),
        deposit_token: None,
        protocol_access_url: None,
        // Single validator: one commit triggers PhaseMarker immediately.
        num_validators_required: 1,
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

    // Step 1: register a new ValidationRequest with num_validators_required=1.
    let _: ActionHash = call_zome(
        ctx,
        "attestation_coordinator",
        "submit_validation_request",
        make_single_validator_request(data_hash.clone()),
    )?;

    // Step 2: commit.  Because num_validators_required=1, the
    // check_all_commitments_sealed_inner logic will write a
    // PhaseMarker(RevealOpen) immediately.
    let _: () = call_zome(
        ctx,
        "attestation_coordinator",
        "notify_commitment_sealed",
        CommitmentSealedInput {
            request_ref: data_hash.clone(),
            commitment_hash: vec![0u8; 32],
        },
    )?;

    // Step 3: poll get_current_phase until RevealOpen appears.
    // Poll for up to 10 s.  If it doesn't appear, report a timeout_count
    // increment instead of a latency — a high timeout rate is the indicator
    // of DHT performance problems.
    let poll_start = Instant::now();
    let mut poll_count: u32 = 0;
    let mut phase_observed = false;
    const MAX_POLL_MS: u64 = 10_000;

    loop {
        let phase: Option<String> = call_zome(
            ctx,
            "attestation_coordinator",
            "get_current_phase",
            data_hash.clone(),
        )?;

        poll_count += 1;

        if phase.as_deref() == Some("RevealOpen") {
            phase_observed = true;
            break;
        }

        if poll_start.elapsed().as_millis() as u64 > MAX_POLL_MS {
            break;
        }

        std::thread::sleep(std::time::Duration::from_millis(50));
    }

    let elapsed_ms = poll_start.elapsed().as_millis() as f64;
    let reporter = ctx.runner_context().reporter().clone();

    if phase_observed {
        reporter.add_custom(
            ReportMetric::new("phase_observation_ms").with_field("value", elapsed_ms),
        );
        reporter.add_custom(
            ReportMetric::new("poll_count").with_field("value", poll_count as f64),
        );
    } else {
        // Count timeouts separately; aggregating them with successful
        // latency measurements would skew the distribution.
        reporter.add_custom(ReportMetric::new("phase_timeout_count").with_field("value", 1.0));
    }

    ctx.get_mut().scenario_values.iteration += 1;

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
