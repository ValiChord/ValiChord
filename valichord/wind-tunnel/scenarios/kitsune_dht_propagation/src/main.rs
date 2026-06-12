//! PROTOTYPE — Kitsune2 substrate propagation benchmark for ValiChord.
//!
//! Modelled on upstream wind-tunnel's `kitsune_continuous_flow` scenario, which
//! is the reference example for the Kitsune2 bindings (`kitsune_wind_tunnel_runner`).
//!
//! Each agent creates an instrumented "chatter" instance, joins a shared Kitsune2
//! network (via the bootstrap server + Iroh relay passed on the CLI), and then
//! repeatedly broadcasts short messages to every other peer. Each message embeds
//! the publishing agent's index and a millisecond UNIX timestamp at send time:
//!
//!     message_<agent_index>_<send_timestamp_ms>_<counter>
//!
//! The instrumented chatter records send/receive events through the wind-tunnel
//! reporter, so cross-peer propagation latency is recoverable from the captured
//! metrics (receive_time - embedded send_timestamp). This is the raw gossip
//! substrate underneath ValiChord's DHT — no ValiChord DNA, zome, or
//! commit-reveal code runs here. See Cargo.toml for the full rationale and scope.
//!
//! FOLLOW-UP (not this file): for ValiChord-*entry* cross-agent propagation
//! (e.g. how long until a CommitmentAnchor written by agent A is visible to
//! agent B), the right shape is a Holochain-layer `dht_sync_lag` scenario —
//! one named "write" behaviour committing a timestamped ValiChord entry and a
//! second "record_lag" behaviour reading it back on other agents and emitting a
//! `sync_lag` metric. That measures our DNA + network together; this prototype
//! measures the network alone, giving the baseline to subtract.

use kitsune_wind_tunnel_runner::prelude::*;
use rand::Rng;
use std::time::Duration;

/// Per-agent setup: stand up the instrumented chatter and join the network.
fn agent_setup(ctx: &mut AgentContext<KitsuneRunnerContext, KitsuneAgentContext>) -> HookResult {
    create_chatter(ctx)?;
    join_chatter_network(ctx)
}

/// One behaviour iteration: broadcast a batch of timestamped messages, then
/// back off a random 10–1000 ms so agents don't march in lockstep.
fn behaviour(
    ctx: &mut AgentContext<KitsuneRunnerContext, KitsuneAgentContext>,
) -> anyhow::Result<()> {
    // Messages per interval — configurable via NUM_MESSAGES (default 3).
    let number_of_messages: u8 = std::env::var("NUM_MESSAGES")
        .unwrap_or_else(|_| "3".to_string())
        .parse()
        .expect("NUM_MESSAGES must be a number < 256");

    let timestamp = std::time::UNIX_EPOCH
        .elapsed()
        .expect("time went backwards")
        .as_millis();

    let mut messages = Vec::with_capacity(number_of_messages as usize);
    for i in 0..number_of_messages {
        // agent_index + send timestamp + counter — the timestamp is what makes
        // propagation latency recoverable from the captured receive events.
        messages.push(format!("message_{}_{}_{}", ctx.agent_index(), timestamp, i));
    }

    say(ctx, messages)?;

    let interval = rand::rng().random_range(10..1000);
    ctx.runner_context().executor().execute_in_place(async move {
        tokio::time::sleep(Duration::from_millis(interval)).await;
        Ok(())
    })
}

fn main() -> WindTunnelResult<()> {
    let builder = KitsuneScenarioDefinitionBuilder::<
        KitsuneRunnerContext,
        KitsuneAgentContext,
    >::new_with_init("kitsune_dht_propagation")?
    .into_std()
    .add_capture_env("NUM_MESSAGES")
    .use_agent_setup(agent_setup)
    .use_agent_behaviour(behaviour)
    .with_default_duration_s(30);

    run(builder)?;
    Ok(())
}
