//! Shared install helper for the ValiChord Holochain wind-tunnel scenarios.
//!
//! The attestation DNA is credential-gated. Live runs were never possible with
//! the plain `install_app(.., "valichord")` call the scenarios originally used:
//! there is no role named "valichord" (it's "attestation"), and the conductor
//! refuses to enable a credentialed app without a membrane proof
//! (`allow_deferred_memproofs: true` in the hApp manifest). This crate ports the
//! dev-mode bypass from valichord-ui's `dev-setup.mjs` — empty
//! `authorized_joining_certificate_issuer` (disables the credential system) plus
//! the 64×0x42 dummy membrane proof the conductor still requires — into a single
//! `install_valichord_app` every Holochain scenario calls.

use holochain_types::prelude::{
    DnaModifiersOpt, MembraneProof, RoleSettings, SerializedBytes, UnsafeBytes, YamlProperties,
};
use holochain_wind_tunnel_runner::prelude::*;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;

/// Path to the packed hApp. Override with `VALICHORD_HAPP_PATH`; otherwise
/// resolves to `valichord/workdir/valichord.happ` relative to this crate (which
/// sits at the same depth as the scenario crates).
pub fn valichord_happ_path() -> PathBuf {
    std::env::var("VALICHORD_HAPP_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../workdir/valichord.happ")
        })
}

/// Dev-mode role settings: attestation gets the bypass membrane proof + empty
/// issuer; governance gets empty coordinator keys (any agent may write). Other
/// roles use their packed defaults.
pub fn valichord_roles_settings() -> HashMap<String, RoleSettings> {
    let dev_memproof: MembraneProof =
        Arc::new(SerializedBytes::from(UnsafeBytes::from(vec![0x42u8; 64])));

    let attestation_props: serde_yaml::Value = serde_yaml::from_str(
        "minimum_validators: 1\ndiscipline: genomics\nauthorized_joining_certificate_issuer: \"\"",
    )
    .expect("static attestation properties");
    let governance_props: serde_yaml::Value =
        serde_yaml::from_str("system_coordinator_key: \"\"\nharmony_record_creator_key: \"\"")
            .expect("static governance properties");

    HashMap::from([
        (
            "attestation".to_string(),
            RoleSettings::Provisioned {
                membrane_proof: Some(dev_memproof),
                modifiers: Some(DnaModifiersOpt {
                    network_seed: None,
                    properties: Some(YamlProperties::new(attestation_props)),
                }),
            },
        ),
        (
            "governance".to_string(),
            RoleSettings::Provisioned {
                membrane_proof: None,
                modifiers: Some(DnaModifiersOpt {
                    network_seed: None,
                    properties: Some(YamlProperties::new(governance_props)),
                }),
            },
        ),
    ])
}

/// Install + enable the ValiChord hApp with the dev-mode bypass. The scenario's
/// `cell_id` is bound to the "attestation" role, which is where the scenarios
/// make their `attestation_coordinator` zome calls.
pub fn install_valichord_app<SV: UserValuesConstraint>(
    ctx: &mut AgentContext<HolochainRunnerContext, HolochainAgentContext<SV>>,
) -> WindTunnelResult<()> {
    install_app_custom(
        ctx,
        valichord_happ_path(),
        &"attestation".to_string(),
        None,
        Some(valichord_roles_settings()),
    )
}
