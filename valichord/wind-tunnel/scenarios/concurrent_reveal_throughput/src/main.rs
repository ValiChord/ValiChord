//! Wind-Tunnel scenario: concurrent_reveal_throughput
//!
//! What this measures
//! ------------------
//! The full commit-reveal protocol round trip under concurrent load from N agents
//! running simultaneously.  Each agent independently completes one full validation
//! round per iteration (request → commit → poll RevealOpen → reveal), exercising:
//!
//!   - DHT write throughput under concurrent multi-agent load
//!   - ChainTopOrdering::Relaxed: three sequential source-chain writes per
//!     iteration (ValidationRequest, CommitmentAnchor, ValidationAttestation)
//!     without HeadMoved errors
//!   - Full DNA3 entry lifecycle in one pass
//!
//! Uses `num_validators_required: 1` so each agent drives its own round to
//! completion without waiting for others.  Real 2-validator rounds can be
//! measured by combining this scenario's output with phase_observation_latency.
//!
//! Key metrics (Wind-Tunnel auto-captures per-call latency for every
//! `call_zome` invocation by fn name; this scenario adds):
//!   `round_total_ms` — wall time from request submission to reveal returning
//!   `reveal_count`   — running total of successful reveals per agent
//!
//! If the scenario reports HeadMoved errors in the Wind-Tunnel log, that
//! indicates ChainTopOrdering::Relaxed is not enabled on the AttestationDNA
//! write paths — check `create_entry` calls in attestation_coordinator.
//!
//! Run:
//!   cargo run -p concurrent_reveal_throughput -- --agents 4 --duration 90
//!   cargo run -p concurrent_reveal_throughput -- --agents 8 --duration 120 --reporter=influx-file

use std::time::Instant;

use holochain_wind_tunnel_runner::prelude::*;
use holo_hash::{ActionHash, ExternalHash};

use attestation_coordinator::AttestationRevealInput;
use attestation_integrity::{ValidationRequest, ValidationTier};
use valichord_shared_types::{
    AgreementLevel, AttestationConfidence, AttestationOutcome, CommitmentSealedInput,
    ComputationalResources, Discipline, OutcomeSummary, TimeBreakdown, ValidationAttestation,
};

// ---------------------------------------------------------------------------
// Per-agent state
// ---------------------------------------------------------------------------

#[derive(Debug, Default)]
struct ScenarioValues {
    iteration: u32,
    reveal_count: u32,
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
        num_validators_required: 1,
        validation_tier: ValidationTier::Basic,
        discipline: Discipline::ComputationalBiology,
        researcher_institution: "Wind Tunnel Lab".into(),
    }
}

fn make_attestation(request_ref: ExternalHash) -> ValidationAttestation {
    ValidationAttestation {
        request_ref,
        outcome: AttestationOutcome::Reproduced,
        outcome_summary: OutcomeSummary {
            key_metrics: vec![],
            effect_direction_matches: None,
            confidence_interval_overlap: None,
            overall_agreement: AgreementLevel::ExactMatch,
        },
        time_invested_secs: 3_600,
        time_breakdown: TimeBreakdown {
            environment_setup_secs: 900,
            data_acquisition_secs: 600,
            code_execution_secs: 1_800,
            troubleshooting_secs: 300,
        },
        confidence: AttestationConfidence::High,
        deviation_flags: vec![],
        computational_resources: ComputationalResources {
            personal_hardware_sufficient: true,
            hpc_required: false,
            gpu_required: false,
            cloud_compute_required: false,
            estimated_compute_cost_pence: None,
        },
        discipline: Discipline::ComputationalBiology,
        commitment_anchor_hash: None,
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

    let round_start = Instant::now();

    // ── Step 1: submit ValidationRequest ────────────────────────────────
    let _: ActionHash = call_zome(
        ctx,
        "attestation_coordinator",
        "submit_validation_request",
        make_single_validator_request(data_hash.clone()),
    )?;

    // ── Step 2: write CommitmentAnchor (num_validators_required=1 means
    //    check_all_commitments_sealed_inner writes PhaseMarker immediately) ──
    let _: () = call_zome(
        ctx,
        "attestation_coordinator",
        "notify_commitment_sealed",
        CommitmentSealedInput {
            request_ref: data_hash.clone(),
            commitment_hash: vec![0u8; 32],
        },
    )?;

    // ── Step 3: poll until RevealOpen ────────────────────────────────────
    // The PhaseMarker is written by check_all_commitments_sealed_inner inside
    // the notify_commitment_sealed call (same agent, same conductor).  On a
    // local conductor this is typically already visible when we start polling,
    // but on a loaded multi-agent network it may require one or two polls.
    // Skip reveal and report a timeout count if it doesn't appear within 15 s.
    const MAX_POLL_MS: u64 = 15_000;
    let mut reveal_open = false;
    loop {
        let phase: Option<String> = call_zome(
            ctx,
            "attestation_coordinator",
            "get_current_phase",
            data_hash.clone(),
        )?;

        if phase.as_deref() == Some("RevealOpen") {
            reveal_open = true;
            break;
        }

        if round_start.elapsed().as_millis() as u64 > MAX_POLL_MS {
            break;
        }

        std::thread::sleep(std::time::Duration::from_millis(50));
    }

    if !reveal_open {
        ctx.runner_context()
            .reporter()
            .clone()
            .add_custom(ReportMetric::new("reveal_timeout_count").with_field("value", 1.0));
        ctx.get_mut().scenario_values.iteration += 1;
        return Ok(());
    }

    // ── Step 4: reveal ──────────────────────────────────────────────────
    // Wind-Tunnel auto-captures submit_attestation latency.
    // nonce = [] activates the dev bypass (authorized_joining_certificate_issuer="")
    // which skips commit-hash verification.
    let _: ActionHash = call_zome(
        ctx,
        "attestation_coordinator",
        "submit_attestation",
        AttestationRevealInput {
            attestation: make_attestation(data_hash),
            nonce: vec![],
        },
    )?;

    let round_ms = round_start.elapsed().as_millis() as f64;

    ctx.get_mut().scenario_values.iteration += 1;
    ctx.get_mut().scenario_values.reveal_count += 1;

    let reveal_count = ctx.get().scenario_values.reveal_count;
    let reporter = ctx.runner_context().reporter().clone();

    reporter.add_custom(ReportMetric::new("round_total_ms").with_field("value", round_ms));
    reporter.add_custom(
        ReportMetric::new("reveal_count").with_field("value", reveal_count as f64),
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
    .with_default_duration_s(90)
    .use_agent_setup(agent_setup)
    .use_agent_behaviour(agent_behaviour)
    .use_agent_teardown(agent_teardown);

    run(builder)?;
    Ok(())
}
