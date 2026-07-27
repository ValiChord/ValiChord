# Unyt ecosystem tools — reference

Reference notes on tools from **Unyt** (`unytco`, [unyt.co](https://unyt.co) — Unyt Accounting LTD, decentralized cryptographic accounting on Holochain) that are relevant to ValiChord's roadmap. Referenced from `CLAUDE.md`. Last reviewed: 2026-06-13.

## tauri-plugin-holochain — **now public** (was "not yet open-source")

`unytco/tauri-plugin-holochain` is a public **fork of the canonical `darksoil-studio/tauri-plugin-holochain`** (darksoil-studio = Guillem Córdoba's studio, the maintaining home). Tagline: *"Ship cross-platform p2p apps."*

This **supersedes the earlier CLAUDE.md note that it was "not yet open-source."** It is the **lighter-than-Electron** path for packaging a Holochain app as a desktop app: a Tauri plugin that bundles and manages the conductor for you.

Relevance to the **validator desktop app** decision:
- This is the plugin that `flowsta-vault-app` deliberately did **not** use (it rolled its own conductor lifecycle in `src-tauri/`), and that Moss/Weave builds on for its Tauri target.
- It is now a real alternative to the **kangaroo-electron** packaging path tracked in `docs/KANGAROO_PACKAGING_PLAN.md`. Evaluate Tauri-plugin-holochain vs kangaroo-electron when the validator desktop app work begins. Use **canonical `darksoil-studio/tauri-plugin-holochain`** as the source of truth (Unyt's is a fork).

### Closer look (2026-06-13) — the strongest desktop candidate

- **Use canonical `darksoil-studio/tauri-plugin-holochain`.** `unytco`'s fork is `behind_by: 3, ahead_by: 0` with no Unyt-specific commits (all authored by the darksoil dev) — just a stale mirror. Confirmed canonical 2026-06-13: **both `lightningrodlabs/tauri-plugin-holochain` AND `unytco/tauri-plugin-holochain` are forks of `darksoil-studio`** (lightningrodlabs' is older, pushed Feb). darksoil-studio is the source of truth. (lightningrodlabs also has the older single-binary `holochain-runner` conductor wrapper — key-gen + install + clean SIGTERM — but it has no membrane-proof/roles_settings input and is 0.4-era in its README, so tauri-plugin-holochain is the better-fit primitive for us.)
- **On our exact stack:** commit history goes `0.6.1-rc.6 → rc.7 → "upgrade Holochain to 0.6.1 stable"` (2026-05-18). Supports **Holochain 0.6.1 stable** — no version gap. Active development (many feature branches), real polish (e.g. *"cache AdminWebsocket in HolochainRuntime to stop per-call connect/disconnect"*). It's a full runtime: bundles lair + conductor, with `web_happ_window_builder`/`main_window_builder` for the UI window.
- **DECISIVE — its install API solves the membrane-proof problem that sank hc-spin.** `HolochainRuntime::install_app` / `install_web_app` (`crates/tauri-plugin-holochain/src/lib.rs`) take `roles_settings: Option<HashMap<String, RoleSettings>>` (per-role **membrane_proof + DNA `modifiers.properties`**) **+ `membrane_proofs` + `network_seed`** — exactly what `valichord-ui/dev-setup.mjs` uses. Where **hc-spin** only exposed `--network-seed` (couldn't override properties or supply a proof → needed a pre-baked dev happ, see auto-memory `reference-hc-spin-devtools`), tauri-plugin-holochain can: (a) **reproduce our dev bypass directly** (attestation role: `membrane_proof: 0x42×64` + `modifiers.properties.authorized_joining_certificate_issuer: ""`), and (b) **supply a real joining-service membrane proof** for production — feeding straight into our existing `authorized_joining_certificate_issuer` Ed25519 gate.
- **Verdict:** when the validator desktop app starts, evaluate **tauri-plugin-holochain (darksoil-studio) FIRST**, kangaroo-electron second. It gives flowsta's bundled-conductor result with far less custom code, on 0.6.1, and natively handles both the dev bypass and real onboarding proofs.

## joining-service — membrane-proof issuer (institutional validator onboarding)

`unytco/joining-service` is a **fork of the canonical `Holo-Host/joining-service`** ("Reference implementation of a joining service"). It is the **membrane-proof issuer** + read-gateway provider for onboarding agents onto a live Holochain network.

Why it matters to ValiChord: the attestation DNA already has an `authorized_joining_certificate_issuer` DNA property and a `verify_membrane_proof()` Ed25519 check in the coordinator `init()` — i.e. the credential gate is built, but only ever exercised via the dev bypass (empty issuer + `0x42×64` proof). A joining service is the **operational layer that issues real proofs**, replacing that bypass and enabling institutional validator onboarding.

REST flow (canonical Holo-Host impl): `/.well-known/holo-joining` (discovery) → `POST /v1/join` (agent key + identity claims) → `POST /v1/join/{session}/verify` (if verification required) → `GET /v1/join/{session}/provision` (returns `membrane_proofs`, linker URLs, bundle URL). Ships a `joining-cli` for headless node provisioning (membrane proofs, hc-auth, roles-settings YAML — the production form of what `valichord-ui/dev-setup.mjs` does by hand). Alpha — *"not yet recommended for production"*. Consumed in the wild by `GeekGene/mewsfeed` via `@holo-host/web-conductor-client`'s `connectWithJoiningUI`.

## heart — node setup/management toolkit

`unytco/heart` — **H**olochain **E**nvironment & **A**gent **R**untime **T**oolkit. WIP toolkit for quickly setting up and managing Holochain nodes (automated setup, configuration, testing). Broader than "DigitalOcean + Pulumi conductor provisioning"; relevant to ValiChord production-node deployment alongside `holochain/network-services` (Pulumi bootstrap-srv + sbd-server recipe). Marked work-in-progress.

---

# Org re-survey — 2026-07-27

Full sweep of all 22 public `unytco` repos. Four findings that change the picture above.

## 1. `heart` is now the fleet deployer — and it hardcodes full arc

Rebuilt in **Go** as a Pulumi program: one stack per release (`heart:release v0-7-0` is the README's own example), provisioning Ubuntu 22.04 DigitalOcean droplets via cloud-init with pinned Holochain + Lair and Telegraf → InfluxDB. Now has **dedicated node types** — `progenitor` (PR #15, self-designates via `progenitor_pubkey`) and `notary` (PR #10, "migration notary hosts") — with the fleet default shrunk to 4 droplets per release (#14). Cloud-init on Holochain 0.6.2-rc.0.

**`cloudinit/cloud-config.yaml:66` sets `target_arc_factor: 1`.** Every droplet HEART provisions is a full-arc node, hardcoded in the template. This is the production arc policy, in public code — the most concrete "kitsune2 #160 in production" artifact we have, and the exact line a redundancy-aware controller would replace. Directly usable in the polite-shrink conversation (see auto-memory `reference_cognisee_schutte_2026-07-20`).

Same file carries `signal_url` and `db_sync_strategy: Fast` — both **removed in 0.7, where `NetworkConfig` rejects unknown fields and the conductor refuses to start**. They are staging a `v0-7-0` stack, so they will hit this. Low-stakes, genuinely useful technical opener.

## 2. `migration-service` — a working DNA-migration pipeline (the thing 0.7 says doesn't exist)

New repo (created 2026-05-29, active to 2026-07-23). The official 0.7 upgrade guide states there is **no data migration path** across a DNA-hash change; Unyt built one off-chain anyway, on the `close_chain`/`open_chain` HDK primitives (our `docs/Holochain_complete.md` §29).

- **`migration-router/`** (Cloudflare Worker, TS) — validates `(from_dna_hash, to_dna_hash)` against an `upgrades_from` chain, random-order failover across notary daemons, returns the package **verbatim**; holds no keys, never interprets the payload.
- **`notary-daemon/`** (Rust/axum + `ham`) — `/healthz` + `/v1/fetch-close` behind bearer auth; calls `read_predecessor_close`, a pure read. **No signing capability at all** — trust lives in M-of-N notary signatures collected *on-chain before* the close. Error codes defined once in Rust and mirrored in the router's TS union; client errors get a distinct 4xx so the router hard-stops rather than retrying a malformed request across every notary.
- **`headless-migrator/`** (Rust/clap + `ham`) — close service on the old server, open service on the new, as supervised systemd units, probe-first and idempotent, exiting 0 only on success so `Restart=on-failure` drives the loop.

**Open side mechanism:** install the app **for the carried key** with the fetched package as the migrating role's **`init_properties`**, so the DNA's `init` opens the chain at genesis — *no post-install `migration_init` call, no first-zome-call ordering window*. (This is the same `init_properties` field added to `RoleSettings::Provisioned` in holochain_types 0.6.2 that broke our wind-tunnel build on 2026-07-27, commit `41cb5a4`. It is load-bearing migration infrastructure, not an incidental addition.)

Two traps documented there that bite **any** programmatic install, migration or not:
- **DNA modifiers must be overridden completely.** `network_seed` *and* `properties` are both hashed into the DNA hash. Overriding only the seed lands the cell on a different DNA than the network — "its own empty DHT, no peers, no gossip, and an `init` that can never resolve the GD." Silent and fatal. Our own installers override both; keep it that way.
- **Idempotency across teardown.** `safe_to_teardown` is persisted at verify success so a restart after the old side is gone short-circuits from persisted state without a router fetch — otherwise the idempotent restart hard-requires a fetch and spins forever.

**How much this helps ValiChord — precisely.** It carries *an agent's own source chain* across a hash boundary. It does **not** republish other-authored public entries, so it does **not** save our published HarmonyRecord URLs (DNA 4 entries authored by participating validators). And it depends on notaries and gossip, neither of which exists in DNA 1 or DNA 2 — our single-agent private DNAs. Net: it would preserve validator/researcher *identity continuity* through the 0.7 migration and nothing more. Same boundary that limits source-chain restore.

⚠️ **Licence: Cryptographic Autonomy License v1.0 (CAL-1.0)**, not Apache-2.0. Strong copyleft with a user-data provision. **Design source only — do not copy code into Apache-2.0 ValiChord.**

## 3. ⭐ `headless-migrator/src/policy.rs` is the algorithm `select_validators()` needs

The highest-value transfer in the whole org, and it has nothing to do with migration. Strip the notary framing and `policy.rs` is a tested implementation of *choose M participants at random from N, substitute on failure, distinguish "catching up" from "faulty", hard-stop on a warrant*:

- Request from only **M** of the N, chosen **at random** — never all N.
- Per-request timeout (default 120 s) counts as failure → substitute a random not-yet-tried member.
- `UnableToVerify` → transient → substitute.
- `StateMismatch` → retry the **same** member with backoff (2 s → 30 s cap, 5 consecutive) before substituting — its DHT view is catching up, not faulty.
- A merely-slow responder is **never** substituted; slowness only surfaces as `TimedOut`, and one that eventually returns `Signed` is honoured.
- List exhausted below M → whole attempt fails, nothing committed, retry later. **No overall deadline.**
- `Warranted` → hard stop for the entire operation.

Written pure over an injected signer + RNG, so it is exhaustively unit-testable with no conductor — the "mocked-seam pattern".

**Why this matters to us:** `select_validators()` in DNA 3 is a documented stub returning empty (`docs/7_ValiChord_4-DNA_architecture_technical.md` → Known Gaps), and Phase 1 owes us randomisation, institutional balance and conflict-of-interest detection. This is that algorithm with the failure taxonomy already worked out — including the distinction we would otherwise learn the hard way, that a *slow* validator and a *dead* validator need opposite handling. It also matches a warrant hard-stop to our existing `reject_if_warranted` gate. **Design source, not code source** (CAL-1.0).

## 4. `ham` — signing without a committed cap grant

`unytco/ham` (public, Rust) is the `AppWebsocket` wrapper behind the daemon, headless-migrator, bridge orchestrator, pricing oracle and watchtower. Notable: it can sign **via lair as the cell's own agent key, committing no capability grant to the chain** (`HamConfig::try_lair_signing_from_node` / `with_lair_signing`), falling back to a throwaway grant otherwise. Our Node bridges commit signing credentials. Not urgent, but the cleaner pattern if we revisit that.

## Other repos — current state

`unyt-sandbox` (★11, the shipped product) describes participants as *"if operating as a **full arc node**, validates peers directly"* — the full/zero-arc split in user-facing copy. `wind-tunnel-unyt` is **stale** (last push 2026-01-14) — not where their perf work happens. `joining-service` unchanged since 2026-06-30. `tauri-plugin-holochain` last pushed 2026-06-08, no change to the verdict above. `smart_agreement_library` (★5) active; `rave_engine` is published on crates.io and is where the migration wire types live.

---

## Off-domain Unyt repos (not relevant to ValiChord)

Unyt's core is mutual-credit / accounting, so most of the org is off-domain for ValiChord's reproducibility protocol:
- `smart_agreement_library` (RAVEs), `pricing_oracle` — accounting agreement / pricing primitives
- `raindex-orders` — Unyt↔blockchain bridge (explicitly blockchain; off ValiChord's de-crypto framing)
- `circulo-tx5` — p2p payments
- `unyt-moss` — Unyt's Moss/Weave deployment; `wind-tunnel-unyt` — Unyt's wind-tunnel variant; `ham`/`old-ham`, `unyt-sandbox`/`unyt-sandbox-iroh`

## Bottom line

The live takeaway is **tauri-plugin-holochain is now public** — the trigger to evaluate the Tauri desktop path (vs kangaroo-electron) for the validator desktop app. `joining-service` and `heart` are the onboarding and node-provisioning pieces for the eventual production / institutional-onboarding phase. Everything else in the org is accounting-domain and off-topic.
