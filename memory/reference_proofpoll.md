# ProofPoll + Flowsta agent_linking — reference

Reference notes on `WeAreFlowsta/ProofPoll` and the `agent_linking` zome in `WeAreFlowsta/flowsta-identity-dna`, both relevant to ValiChord's validator-desktop-app and `person_key` roadmap. Same org as `flowsta-vault-app`. Last reviewed: 2026-06-13.

## ProofPoll — Tauri v2 + Qwik desktop app on our exact stack

`WeAreFlowsta/ProofPoll` is a desktop polling app: Tauri v2 + Qwik frontend, local Holochain **0.6.1** conductor, sybil-resistant ("one vote per real person") via Flowsta identity, censorship-resistant via DHT. DNA pins `hdk=0.6.0`/`hdi=0.7.0` (conductor binaries are 0.6.1). Written as an explicit **fork template** — every `src-tauri/src/` file has a "keep as-is / replace your data model" header.

**Key difference from `flowsta-vault-app`:** that one *embeds* the conductor as a library; ProofPoll **ships official `holochain` + `lair-keystore` binaries as Tauri sidecars** (renamed with a `proofpoll-` prefix to avoid collision) and manages them as child processes (`conductor.rs`, `lair.rs`, `sidecar.rs`). A **third concrete option** for the validator desktop app, alongside kangaroo-electron and darksoil/unyt `tauri-plugin-holochain`.

Patterns worth lifting:

1. **`conductor.rs` generates conductor-config.yaml with the exact 0.6.1 iroh/QUIC fields** (`bootstrap_url`, `signal_url`, `relay_url`, `base64_auth_material_bootstrap`/`_relay`, `db_sync_strategy: Resilient`) — a working instance of §40 in `docs/Holochain_complete.md`, including authenticated bootstrap (the kangaroo bootstrap/relay blocker). **Compile-time config** via `option_env!` + an empty-string-as-unset macro: the official release bakes in Flowsta servers, a fork falls back to the public dev bootstrap. Documented gotcha: auth material is base64 **STANDARD-with-padding, NOT URL_SAFE_NO_PAD** (Holochain's own docstring is wrong about its decoder). **SQLCipher `hmac check failed` recovery** (nuke-state + regenerate vs generic retry-once) and proactive wiping of stale lair `store_file`/`pid_file`/`socket` on first run (orphaned-keystore-after-uninstall crash). **Windows-relevant** (the user is on Windows): single-quoted YAML paths (double-quoted dies on `C:\…` `\U` escape), named-pipe async-readiness retry loop, macOS percent-decoded socket paths. `libc::kill(pid,0)` health monitor emits status to the UI.

2. **Frontend has NO `@holochain/client` — every zome call is `invoke()` → a Rust Tauri command** (`src/lib/holochain.ts`). Rust owns the AppWebsocket + signing credentials; the TS side is thin typed wrappers. For a desktop ValiChord this dissolves the valichord-ui pain set (signing-credentials dance, the `/hc-ws` Vite proxy hack, manual msgpack `decode()`, hand-maintained `types.ts` serde mirrors). Types live once in Rust command signatures.

3. **`crypto.rs` self-encryption via lair `crypto_box_xsalsa_by_sign_pub_key`** (sender = recipient = self; lair does Ed25519→X25519 internally, reuse the agent key, no separate keypair) — the working API path for our **Open Audit mode** (encrypt dataset on the DHT) and private drafts/rationales.

4. **`migration.rs` + `MigrationState` — multi-version DNA migration**: installs the new DNA alongside the old, holds v1.0–v1.3 app clients simultaneously for read-back, anchor-links old→new hashes (`MigratedPoll`), background-retries pending writes whose authors haven't migrated. This is exactly the **integrity-zome-change / new-DNA-hash upgrade path that coordinator-only hot-swap does NOT cover** — directly relevant to the eventual 0.7 upgrade (CLAUDE.md: no migration path).

5. **Flag = hide-not-delete** (data stays on the DHT forever) — moderation without compromising immutability; consistent with our "no party can erase."

## Flowsta `agent_linking` zome = our `person_key`, and we already half-built it

Source: `WeAreFlowsta/flowsta-identity-dna`, `v1.4/zomes/agent_linking/{integrity,coordinator}/src/lib.rs`. The prebuilt wasm in ProofPoll's hApp comes from here. It is **fully generic — "no Flowsta-specific fields, any Holochain app can include it."**

**Big finding: ValiChord's existing `AgentIdentityAttestation` (DNA 3) is structurally identical to Flowsta's `IsSamePersonEntry`** — sorted key pair (`agent_a` < `agent_b`), both agents sign the sorted-pair bytes, either may author, both signatures verified in `validate()`, revoke-by-Delete, lookup links from both pubkeys (`AgentToIdentityAttestation` ≈ `AgentToIsSamePerson`). We arrived at the same primitive independently; our `link_agent_identity` / `revoke_agent_identity_link` / `get_linked_agents` already exist (covered by attestation sweettests 19).

What Flowsta adds that we don't have:

- **`create_direct_link(DirectLinkInput)` — the API-mediated desktop linking ceremony.** The desktop agent signs `sorted_agent_pair_bytes` locally and sends *just its signature*; the web/caller agent verifies it, signs its own half via `sign()`, sorts the pair into canonical order, commits the `IsSamePersonEntry` with both signatures, and creates `AgentToIsSamePerson` links from **both** pubkeys. This is the concrete mechanism a ValiChord validator-desktop ↔ web link would need.
- **`created_at: i64`** field, and a declared `PendingLinkRequest` link type for an async ceremony when both agents aren't online together (coordinator fn for it not in v1.4).

**The architectural insight (from `get_linked_agents` + ProofPoll's `loadMyAgentSet`): identity linking is hub-and-spoke, NOT a transitive graph walk.** `get_linked_agents` walks only **one hop** (direct pairs). It enumerates all of a person's keys because every device links to the *same* canonical Vault/identity agent — a star topology around the hub, not a transitive cluster. Revoked links are filtered via `get_details` → `record_details.deletes.is_empty()`.

**→ Path to populate ValiChord's stubbed `person_key`:** designate the Flowsta/Vault identity agent as the hub; link every validator device to it via the `create_direct_link` pattern; `get_linked_agents(hub)` enumerates all the person's keys; reputation-dedup = group `CommitmentAnchor`s by hub agent; cross-key COI = "do any of these linked keys share the researcher's institution?". **Critical constraint:** linking is for RECOGNITION (reads) only — update/delete stays bound to the current local agent (Holochain only lets the original author mutate), so dedup/aggregation must be read-only.

**Decision to make later:** drop in the generic `agent_linking` zome wholesale and retire our bespoke `AgentIdentityAttestation`, OR keep ours and just add `create_direct_link` + `created_at`. Either way: recompile the zome `0.6.0`→`0.6.1` hdi and compat-check before it goes into our hApp.

## Other Flowsta repos (noted, not yet inspected)

`flowsta-identity-dna` (DID profiles + agent_linking), `flowsta-private-dna` (encrypted personal data, zero-knowledge access), `flowsta-signing-dna` ("Sign It" — Ed25519 sigs over file hashes on a public DHT — conceptually close to ValiChord's own attestation framing), `flowsta-sdk` (JS SDK), `flowsta-vault-app` (see its own reference doc — PR_SET_PDEATHSIG auto-reap + BIP39 key derivation).
