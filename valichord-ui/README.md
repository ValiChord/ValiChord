# valichord-ui

Svelte 5 + TypeScript browser UI for the ValiChord reproducibility validation protocol.

Connects directly to a local Holochain conductor via WebSocket and exposes three role-based dashboards: **Researcher**, **Validator**, and **Governance**.

For the full UX walkthrough, type mapping, and architecture notes see [FRONTEND.md](./FRONTEND.md).

---

## Quick start (local dev)

### Prerequisites

- Node.js 18+
- Holochain CLI (`hc`) on your PATH — install via `cargo install holochain_cli --locked`
- `valichord/workdir/valichord.happ` built (see `valichord/tests/README.md`)

### Terminal 1 — conductor

```bash
cd valichord-ui
npm install          # first time only
bash dev.sh
```

`dev.sh` does three things in sequence:
1. Starts a single-agent Holochain conductor (admin on `:4444`, in-process lair)
2. Installs `valichord.happ` with dev-mode bypass (no real credential check)
3. Issues an auth token and per-cell signing credentials, writes them to `.env.local`

Wait for the line `Token + signing credentials written to …env.local` before continuing.

### Terminal 2 — UI

```bash
cd valichord-ui
npm run dev
```

Open **http://localhost:5173**.

The UI connects to the conductor on `:8888`, reads the auth token and signing credentials from `.env.local` (injected by Vite at build time), and shows the Researcher dashboard.

### Type-check

```bash
npm run check
```

### Build for production / Launcher packaging

```bash
npm run build   # outputs to dist/
```

The `dist/` folder is a static site that can be bundled into a `.webhapp` for Holochain Launcher.

---

## Environment variables

| Variable | Source | Purpose |
|---|---|---|
| `VITE_HC_PORT` | `.env.local` (written by `dev-setup.mjs`) | App WebSocket port (default 8888) |
| `VITE_HC_TOKEN` | `.env.local` | Auth token (base64) for `AppWebsocket.connect` |
| `VITE_HC_SIGNING_CREDENTIALS` | `.env.local` | Per-cell Ed25519 key pairs (base64 JSON) for zome call signing |

All three are written automatically by `bash dev.sh`. Do not edit `.env.local` by hand.

For Holochain Launcher, none of these are needed — Launcher injects the token and port via the URL hash automatically.

---

## How dev.sh works

```
dev.sh
  └─ starts holochain --config-path dev-conductor.yaml --piped  (admin :4444)
  └─ node dev-setup.mjs
        ├─ waits for admin port to be ready
        ├─ installs valichord.happ with membrane-proof bypass
        │     attestation role:  membrane_proof=0x42×64, authorized_joining_certificate_issuer=''
        │     governance role:   system_coordinator_key='', harmony_record_creator_key=''
        ├─ enables the app
        ├─ attaches app interface on :8888
        ├─ issues a no-expiry reusable auth token
        ├─ calls admin.authorizeSigningCredentials(cellId) for each of the 4 cells
        └─ writes VITE_HC_PORT, VITE_HC_TOKEN, VITE_HC_SIGNING_CREDENTIALS to .env.local
```

Conductor data lives in `/tmp/valichord-dev-data` and is wiped each time `dev.sh` runs (fresh agent identity on every restart).

---

## Files

```
valichord-ui/
├── dev.sh                  # start script (conductor + setup)
├── dev-conductor.yaml      # conductor config (admin :4444, in-proc lair, /tmp data)
├── dev-setup.mjs           # Node.js: install app, issue token, write .env.local
├── .env.example            # template (committed); .env.local is gitignored
├── src/
│   ├── main.ts
│   ├── App.svelte          # connection bootstrap, role detection, tab nav
│   └── lib/
│       ├── holochain.ts    # AppWebsocket singleton, callZome, token/creds loading
│       ├── store.ts        # Svelte stores (connection state, role, notifications)
│       ├── types.ts        # TypeScript mirrors of Rust types; entryFromRecord (msgpack decode)
│       ├── ResearcherView.svelte
│       ├── ValidatorView.svelte
│       └── GovernanceView.svelte
└── FRONTEND.md             # full UX walkthrough and architecture notes
```
