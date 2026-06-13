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

## Off-domain Unyt repos (not relevant to ValiChord)

Unyt's core is mutual-credit / accounting, so most of the org is off-domain for ValiChord's reproducibility protocol:
- `smart_agreement_library` (RAVEs), `pricing_oracle` — accounting agreement / pricing primitives
- `raindex-orders` — Unyt↔blockchain bridge (explicitly blockchain; off ValiChord's de-crypto framing)
- `circulo-tx5` — p2p payments
- `unyt-moss` — Unyt's Moss/Weave deployment; `wind-tunnel-unyt` — Unyt's wind-tunnel variant; `ham`/`old-ham`, `unyt-sandbox`/`unyt-sandbox-iroh`

## Bottom line

The live takeaway is **tauri-plugin-holochain is now public** — the trigger to evaluate the Tauri desktop path (vs kangaroo-electron) for the validator desktop app. `joining-service` and `heart` are the onboarding and node-provisioning pieces for the eventual production / institutional-onboarding phase. Everything else in the org is accounting-domain and off-topic.
