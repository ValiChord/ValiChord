# ValiChord UI — Frontend Guide

**Version:** 0.5.0 — May 2026  
**Stack:** Svelte 5 + TypeScript + Vite 8  
**Connects to:** Holochain 0.6.1 conductor (local or Launcher) via WebSocket

---

## Setup

### Prerequisites

- Node.js 18+
- Holochain CLI on your PATH — `cargo install holochain_cli --locked`
- `valichord/workdir/valichord.happ` built (see `valichord/tests/README.md`)

### Local dev — two terminals

**Terminal 1: start the conductor**

```bash
cd valichord-ui
npm install          # first time only
bash dev.sh
```

`dev.sh` starts a single-agent conductor (admin on `:4444`), installs the hApp with dev-mode bypass, and writes an auth token + per-cell signing credentials to `.env.local`. Wait for the line:

```
Token + signing credentials written to …/valichord-ui/.env.local
```

**Terminal 2: start the UI**

```bash
cd valichord-ui
npm run dev
```

Open **http://localhost:5173**.

The conductor is wiped and recreated on every `dev.sh` run (fresh agent identity). To reuse the same identity across restarts you would need to persist `/tmp/valichord-dev-data` — not necessary for dev.

### Holochain Launcher

When running inside Holochain Launcher, no `.env` file is needed. Launcher injects the app port and auth token via the URL hash automatically. `holochain.ts` reads them from `window.location.hash` first.

### Build

```bash
npm run build   # outputs to dist/
```

The `dist/` folder is a static site that can be bundled into a `.webhapp` for Launcher packaging.

---

## Visual design

### Brand

The **ValiChord logo** (`public/valichord-logo.jpeg`) is displayed in the header on every tab — a dark navy card with the chord-graph mark, wordmark, and "Harmony from Dissonance" tagline.

### Colour palette

All colours are CSS custom properties defined in `src/app.css`. Key tokens:

| Token | Value | Meaning |
|---|---|---|
| `--accent` | `#3dcfa8` | Teal — drawn from the logo's validator-node colour; used for links, focus rings, active tabs |
| `--accent-bright` | `#6de8c0` | Bright teal — active nav labels |
| `--accent-solid` | `#0d9972` | Dark teal — primary button backgrounds |
| `--warn-bg` | `#78350f` | Amber — finalise/destructive actions; echoes the logo's gold connecting lines |
| `--color-success` | `#86efac` | Green — reproduced outcomes, sealed phase |
| `--color-error` | `#fca5a5` | Coral — errors; mirrors the logo's researcher-node colour |
| `--bg-base` | `#0f1117` | Deep navy — page background |

### Typography

Loaded via Google Fonts (see `index.html`):

- **DM Serif Display** — `h1`, `h2` headings
- **IBM Plex Sans** — body text, form inputs, buttons
- **JetBrains Mono** — hashes, hex strings, JSON textareas

### Phase progress strip (Validator)

The Validator commit and reveal screens show a horizontal **Commit → Reveal → Harmony** progress strip. Completed steps render with green (teal) styling; the active step uses the primary accent; future steps are dimmed. Implemented with plain CSS — no animation library.

---

## Role detection

When the app connects, it calls `get_validator_profile` on the `attestation` DNA with the current agent's public key. If a `ValidatorProfile` is found, the active tab defaults to **Validator**. Otherwise it defaults to **Researcher**. You can switch between all three tabs (Researcher, Validator, Governance) at any time.

---

## Researcher workflow

Researchers use ValiChord to submit their work for independent validation and to participate in the blind commit-reveal protocol.

### Step 1 — Submit a validation request

Navigate to the **Researcher** tab.

Fill in:
- **Data hash** — SHA-256 of the dataset as a 64-character hex string (use `compute_data_hash` from the researcher_repository DNA, or compute externally)
- **Data access URL** — where validators will download the dataset (OSF, Zenodo, institutional repo, etc.)
- **Deposit access type** — `PublicUrl` (default) or `TokenGated` (token will be included in the request)
- **Deposit token** — only if `TokenGated`; a secret credential validators use to fetch the data
- **Protocol access URL** — optional; DOI or URL of a pre-registered analysis plan
- **Institution** — your institution name (used for conflict-of-interest checking)
- **Discipline** — select from the dropdown
- **Validation tier** — `Basic`, `Enhanced`, or `Comprehensive`
- **Number of validators** — how many independent validators you require

Click **Submit request**. This calls `submit_validation_request` on the `attestation` DNA and creates a `ValidationRequest` entry on the shared DHT.

### Step 2 — Lock your result metrics

Before validators finish, you must commit to your expected result values. This seals the blind: validators cannot see your values during the commit phase, and you cannot change them after seeing validator findings.

In the **Lock result** panel:
- Enter your `request_ref` (data hash hex, same as submission)
- Add your key metrics as JSON array:
  ```json
  [
    {
      "metric_name": "model_accuracy",
      "produced_value": "0.847",
      "expected_value": "0.847",
      "within_tolerance": true
    }
  ]
  ```
- Click **Lock result**

This calls `lock_researcher_result` on the `researcher_repository` DNA (stores a private `LockedResult` entry with nonce locally) then `publish_researcher_commitment` on the `attestation` DNA (publishes only the hash to the shared DHT).

**Do this before validators finish committing.** Once the reveal phase opens you can no longer change your locked metrics.

### Step 3 — Reveal your result

When the validation round completes (you may see a notification when a `RevealOpen` signal arrives), navigate to the **Reveal result** panel:

- Enter your `request_ref`
- Click **Load locked result** — this fetches your stored metrics and nonce from the `researcher_repository` DNA
- Confirm the metrics look correct
- Click **Reveal result**

This calls `reveal_researcher_result` on the `attestation` DNA with your original metrics plus the stored nonce. The network cryptographically verifies that your revealed values match your earlier commitment hash.

---

## Validator workflow

Validators use ValiChord to discover studies, reproduce the work, and submit blind attestations.

### Setup — create a validator profile

On first use, navigate to the **Validator** tab. If you have no profile, you will see the **Setup Profile** screen.

Fill in:
- **Institution** — your organisation name
- **ORCID** — optional; your researcher identifier
- **Disciplines** — select all disciplines you can validate
- **Certification tier** — `Provisional`, `Standard`, `Advanced`, or `Certified` (your current accreditation level)
- **Agent type** — `Individual`, `Institution`, or `AutomatedTool`
- **Maximum concurrent tasks** — how many studies you can work on simultaneously
- **Available** — toggle on to appear in the validator pool

Click **Publish profile**. This calls `publish_validator_profile` on the `attestation` DNA.

### Screen 1 — Dashboard

The dashboard shows:
- Your profile status and availability
- A **Pending reveals** badge if there are studies ready for you to reveal (triggered by `RevealOpen` signals)
- Buttons to browse studies or go to the reveal screen

### Screen 2 — Browse open studies

Click **Browse studies** from the dashboard.

The app loads open `ValidationRequest` entries matching your declared disciplines via `get_pending_requests_for_discipline`. Each card shows:
- Discipline, validation tier, number of validators required
- Data access URL
- Institution and protocol URL if provided
- Conflict-of-interest warning if your institution matches the researcher's

Click **Claim study** on a card. This calls `claim_study(request_ref)` on the `attestation` DNA, then immediately calls `receive_task` on the `validator_workspace` DNA to create a `ValidationTask` locally. The returned `task_hash` is stored in your browser session for use during attestation.

### Screen 3 — Attest (commit phase)

After claiming a study you are taken to the **Attest** screen. Download the data from the URL shown, reproduce the study, and fill in the attestation form:

**Outcome:**
- `Reproduced` — you obtained the same result
- `PartiallyReproduced` — with details of what differed
- `FailedToReproduce` — with details of the failure
- `UnableToAssess` — with reason (e.g. data access problems)

**Outcome summary:**
- Key metrics (metric name, your produced value, expected value, within tolerance)
- Effect direction match and confidence interval overlap (optional)
- Overall agreement level: `ExactMatch`, `WithinTolerance`, `DirectionalMatch`, `Divergent`, or `UnableToAssess`

**Time and resources:**
- Total time invested (seconds), with breakdown by phase
- Computational resources used (personal hardware, HPC, GPU, cloud)

**Confidence and deviations:**
- Your confidence in the outcome: `High`, `Medium`, or `Low`
- Any undeclared deviations from the published protocol (data access issues, model failures, computational limits, sample size adjustments)

Click **Submit attestation (seal)**. This calls `seal_private_attestation({ task_hash, attestation })` on the `validator_workspace` DNA. The nonce is generated internally — you never handle it directly. `post_commit` in the workspace DNA automatically notifies the attestation DNA; do not call `notify_commitment_sealed` manually.

Your attestation is now sealed. It is stored privately on your device. No other participant can see it.

### Screen 4 — Reveal phase

When all validators in the round have sealed their attestations, the protocol opens the reveal window. You will see a notification: *"Reveal phase open — you can now publish your attestation."*

Click **Pending reveals** on the dashboard (or wait on the reveal screen). The app:
1. Calls `get_all_tasks` on the `validator_workspace` DNA
2. Matches tasks whose `request_ref` appears in the pending reveals list
3. Calls `get_private_attestation_for_task(task_hash)` to retrieve your sealed attestation including the stored nonce

You will see a summary of your sealed attestation outcome. Click **Reveal attestation** to call `submit_attestation({ attestation, nonce })` on the `attestation` DNA. The network verifies your nonce against the commitment hash stored in your `CommitmentAnchor`.

Once all validators have revealed, `check_and_create_harmony_record` is triggered automatically by the last validator to submit. The `HarmonyRecord` and `ReproducibilityBadge` appear on the Governance tab.

---

## Governance view

The **Governance** tab is read-only. It shows the permanent public record of completed validation rounds.

### Browse harmony records

Select a discipline from the dropdown and click **Load records**. This calls `get_harmony_records_by_discipline` on the `governance` DNA.

Each record card shows:
- Agreement level and outcome
- Inferred badge: **Gold** (≥7 exact matches), **Silver** (≥5 exact/within-tolerance), **Bronze** (≥3 positive), **Failed** (≥3 divergent/unable-to-assess)
- Validator count and type breakdown (Individual / Institution / AutomatedTool)
- Round duration

### Force-finalize a stuck round (advanced)

If a round is stuck (a validator dropped out and the timeout has passed), expand the **Force finalise round** panel at the bottom of the Governance tab.

Enter the `request_ref` as a hex string and click **Force finalise**. This calls `force_finalize_round` on the `governance` DNA with whatever attestations are currently present. The resulting `HarmonyRecord` will have a lower validator count than the study required, identifiable as a reduced-quorum outcome.

This is a last-resort function. Use only after the `round_timeout_secs` DNA property has elapsed (default: 7 days in production, 0 in tests). The governance DNA enforces `min_attestations_for_finalization` — the function will abort if insufficient attestations are present.

---

## Architecture notes for developers

### WebSocket connection and the Vite proxy

In local dev the conductor's app interface listens on `ws://localhost:8888`. In a Codespace (or any setup where the UI is served from a forwarded HTTPS URL), the browser cannot open a plain `ws://` connection — it resolves `localhost` to the user's machine, not the Codespace.

The fix is a Vite dev-server WebSocket proxy (`vite.config.ts`):

```
browser  →  wss://<codespace>/hc-ws  →  Vite proxy  →  ws://localhost:8888
```

`App.svelte`'s `resolveWsUrl()` detects that `VITE_HC_PORT` is set and returns `wss://<page-host>/hc-ws` instead of `ws://localhost:8888`. The conductor is never exposed to the outside network.

In Holochain Launcher, `APP_PORT` is injected via the URL hash and `resolveWsUrl()` returns `ws://localhost:<port>` as before — the proxy is not involved.

### Holochain 0.6.1 — `relay_url` required

Holochain 0.6.1 switched from tx5/WebRTC to iroh/QUIC transport. The `NetworkConfig` YAML now requires a `relay_url` field (a non-null URL string). `dev-conductor.yaml` sets it to the Holochain dev relay server. Running without it causes the conductor to crash with `ENXIO` during network initialisation.

### Zome name map

The UI maps role names to zome names in `src/lib/holochain.ts`:

| Role | Zome |
|---|---|
| `attestation` | `attestation_coordinator` |
| `researcher_repository` | `researcher_repository_coordinator` |
| `validator_workspace` | `validator_workspace_coordinator` |
| `governance` | `governance_coordinator` |

### Type encoding

All types in `src/lib/types.ts` mirror Rust serde encoding exactly. Key rules:

- `Discipline`, `AttestationOutcome`, `DeviationType` use adjacent-tag serde: unit variants → `{ type: "Reproduced" }`, struct variants → `{ type: "PartiallyReproduced", content: { details: "..." } }`
- `ValidatorAgentType`, `CertificationTier`, `ValidationTier`, `AttestationConfidence`, `AgreementLevel`, `ValidationFocus` are plain strings: `"Individual"`, `"Gold"`, `"Basic"`
- `CompensationTier` uses external-tag (default serde): `{ Tier1: { amount_pence: 5000 } }`
- `ExternalHash` is a 39-byte `Uint8Array` — always construct via `hashFrom32AndType(core32, HoloHashType.External)` from `@holochain/client`; never fill raw bytes

### Signal payload

The `Signal` enum in `attestation_coordinator` uses `#[serde(tag = "type", content = "content")]` (adjacent-tag). Signals arrive over the AppWebsocket as msgpack maps:

| Signal | Payload shape |
|---|---|
| `RevealOpen` | `{ type: "RevealOpen", content: { request_ref: Uint8Array } }` |
| `FinalizationFailed` | `{ type: "FinalizationFailed", content: { request_ref: Uint8Array } }` |

`RevealOpen` fires when all required validators have committed — the reveal window is now open.

`FinalizationFailed` fires locally when `submit_attestation` succeeds but the cross-DNA call to `check_and_create_harmony_record` on the governance DNA fails. The attestation **is** written to the DHT; only round finalisation is affected. Prompt the user to retry via `force_finalize_round` (Governance tab).

The TypeScript union type is `AppHcSignal` in `src/lib/types.ts`. Check via `payload.type === "RevealOpen"` — **not** `"RevealOpen" in payload`, which was the previous (incorrect) external-tag check.

### Signal handler cleanup

The global signal handler in `App.svelte` is registered in an `async onMount`. Because async `onMount` cannot return a cleanup function (Svelte ignores the returned Promise), use `onDestroy` instead:

```typescript
let unsubscribeSignal: (() => void) | undefined;
onDestroy(() => { unsubscribeSignal?.(); });
onMount(async () => {
  // ...
  unsubscribeSignal = onSignal(handler);
});
```

Without this, each component remount stacks another handler onto `_signalHandlers` and validators receive duplicate notifications.

### post_commit is automatic

The `validator_workspace` DNA's `post_commit` hook automatically calls `notify_commitment_sealed` on the `attestation` DNA after `seal_private_attestation` succeeds. The UI must never call `notify_commitment_sealed` directly.

### AppWebsocket.connect()

The `url` option must be a `URL` object:

```typescript
await AppWebsocket.connect({ url: new URL(`ws://localhost:${port}`) });
```

A plain string will cause a type error at connection time.
