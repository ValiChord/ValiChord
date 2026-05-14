# ValiChord Desktop App — Kangaroo-Electron Packaging Plan

**Created:** 2026-05-14  
**Status:** Pending — user is deciding whether to proceed  
**Goal:** Package ValiChord as a cross-platform desktop app so validators can install and run their own Holochain conductor locally.

---

## What kangaroo-electron does

Template repo: https://github.com/holochain/kangaroo-electron (branch: `main-0.6`)

Bundles `.webhapp` + Holochain 0.6.1 conductor + Lair keystore into a single redistributable binary (`.deb`, `.dmg`, `.exe`). End users download and run — no conductor setup required. Ships with system tray, auto-updates via GitHub releases, multi-profile support.

---

## Current prerequisite status

| Prerequisite | Status |
|---|---|
| Browser UI (`valichord-ui/`) wired to conductor | ✓ Done |
| Holochain 0.6.1 | ✓ Done |
| `.happ` build working | ✓ Done (`workdir/valichord.happ`) |
| Bootstrap/relay servers | ✗ Needed for production; dev servers usable for pilot |

The dev servers (`dev-test-bootstrap2.holochain.org`, `iroh-relay-hc.holochain.org`) work fine for a small trusted-validator pilot. For production, run `kitsune2-bootstrap-srv` on Oracle or use `holochain/network-services` Pulumi.

---

## Decisions needed before starting

These are open questions the user needs to resolve first.

### Decision 1 — Single app or separate validator/researcher builds?

The current UI has three views: ResearcherView, ValidatorView, GovernanceView. Kangaroo ships one binary to one person. Options:

- **Single app, role picker on first run** — simpler to maintain; one binary for everyone
- **Separate `valichord-researcher` and `valichord-validator` builds** — cleaner UX; separate CI jobs

Recommendation: single app with role picker for the pilot. Split later if UX demands it.

### Decision 2 — Are any integrity zome changes expected?

Once a build ships, any integrity zome change (new entry/link types, validation rule changes, `CertificationTier` changes) means users must reinstall — kangaroo does not wire the `UpdateCoordinators` admin API. Coordinator-only changes are safe and ship silently via auto-update.

**If integrity changes are likely soon, do them first.** Otherwise the DNA hash is locked for all installed users until the next major version.

### Decision 3 — Membrane proof strategy

Dev setup bypasses membrane proofs with `0x42×64` + `authorized_joining_certificate_issuer: ''`. For a packaged build, pick one:

- **Keep bypass** — open network, any install can join. Fine for a pilot with trusted validators.
- **Implement joining-service** — validators get a signed membrane proof on registration. See Unyt joining-service memory entry. Do this before onboarding untrusted validators.

### Decision 4 — Network seed

The network seed is set at app pack time and determines which DHT peers can find each other. Pick something intentional (e.g. `valichord-pilot-1`) rather than leaving the demo value (`valichord-demo-multi`). All builds for the same pilot must use the same seed.

---

## Implementation steps

### Step 1 — Resolve the four decisions above

No code until these are answered.

### Step 2 — Build a `.webhapp` file

A `.webhapp` bundles the `.happ` + the built UI assets. The current `valichord-ui/` is a Vite/Svelte app.

```bash
# Build the UI
cd valichord-ui && npm run build   # outputs to dist/

# Pack the webhapp
hc web-app pack \
  --output workdir/valichord.webhapp \
  workdir/valichord.happ \
  valichord-ui/dist
```

Check `hc web-app pack --help` for exact syntax — may need a `web-happ.yaml` manifest.

### Step 3 — Refactor `valichord-ui/src/lib/holochain.ts` (the main technical work)

**Current behaviour:** reads `VITE_HC_TOKEN` (base64) and `VITE_HC_SIGNING_CREDENTIALS` (base64 JSON) from Vite env vars written by `dev-setup.mjs`.

**Required behaviour in kangaroo:** read the app port and auth token from kangaroo's preload IPC bridge. The kangaroo preload script (`src/preload/happ.ts`) exposes these to the renderer — check exact API after cloning `main-0.6`.

Likely change in `holochain.ts`:
```typescript
// OLD — reads from Vite env (dev-setup.mjs writes these)
const tokenB64 = import.meta.env.VITE_HC_TOKEN
const credJson = import.meta.env.VITE_HC_SIGNING_CREDENTIALS

// NEW — reads from kangaroo preload IPC
const { appPort, authToken, signingCredentials } = window.__KANGAROO__
```

Also remove the `setSigningCredentials` call from `holochain.ts` if kangaroo handles it internally (check preload source).

The dev setup path (`dev.sh` + `dev-setup.mjs`) must continue to work for local development — keep the env-var path as a fallback, gated on `import.meta.env.DEV`.

### Step 4 — Clone kangaroo-electron and configure

```bash
git clone -b main-0.6 https://github.com/holochain/kangaroo-electron valichord-desktop
cd valichord-desktop
```

Edit `kangaroo.config.ts`:
```typescript
appId: 'com.valichord.validator'
productName: 'ValiChord'
version: '0.1.0'
// Leave bootstrapUrl/signalUrl/relayUrl as defaults for pilot (dev servers)
// Override these when moving to production servers
```

Place files:
```bash
cp workdir/valichord.webhapp pouch/valichord.webhapp
cp Images/valichord-icon-256.png pouch/icon.png   # check actual icon path
```

### Step 5 — Local test

```bash
yarn setup   # downloads Holochain binaries, unpacks pouch
yarn dev     # runs dev build — Electron window should open
```

Verify: all three views (researcher, validator, governance) work end-to-end. Run the full commit-reveal flow manually.

### Step 6 — Production build + CI release

```bash
yarn build:linux   # local .deb
```

For cross-platform CI: push to `release` branch of the new repo — GitHub Actions builds `.deb`, `.dmg` (arm64 + x64), `.exe` and publishes to GitHub Releases.

---

## File locations to know

| Path | What it is |
|---|---|
| `valichord-ui/src/lib/holochain.ts` | Conductor connection + signing credentials — needs refactoring (Step 3) |
| `valichord-ui/src/lib/types.ts` | Shared Holochain types |
| `valichord-ui/dev.sh` | Dev conductor startup — must keep working after Step 3 |
| `valichord-ui/dev-setup.mjs` | Writes auth token to `.env.local` — dev-only path |
| `workdir/valichord.happ` | Current built hApp |
| `valichord/happ.yaml` | App manifest (network seed, DNA roles) |

---

## Risks summary

| Risk | Severity | Mitigation |
|---|---|---|
| Dev bootstrap servers go down | Low (pilot only) | Fall back to running kitsune2-bootstrap-srv on Oracle |
| Integrity zome change after shipping | Medium | Decide Decision 2 before packaging; batch all integrity changes |
| UI refactor breaks dev workflow | Low | Gate kangaroo IPC path on `import.meta.env.PROD` |
| Wrong network seed | Medium | Set seed explicitly in happ.yaml before pack; document it |
| macOS quarantine on unsigned build | Low (pilot) | Validators run `xattr -r -d com.apple.quarantine` or use Linux/Windows first |

---

## What to read before starting

- `valichord-ui/src/lib/holochain.ts` — understand the current connection flow
- `valichord-ui/dev-setup.mjs` — understand what the dev path does
- kangaroo `src/preload/happ.ts` (after cloning) — understand what the IPC bridge exposes
- `valichord/happ.yaml` — current network seed and DNA role names
