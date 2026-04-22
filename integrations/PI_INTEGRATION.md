# ValiChord × PI Integration

## Status

| Item | Status |
|---|---|
| `POST /attest` endpoint (`backend/app_protocol.py`) | **Live** |
| PI extension (`index.ts`, `package.json`, `README.md`) | **Pushed to topeuph-ai/pi-mono main** |
| PI skill (`SKILL.md`) | **Pushed to topeuph-ai/pi-mono main** |
| Issue on badlogic/pi-mono | **Reopen after 2026-04-13** (OSS weekend ended today) → https://github.com/badlogic/pi-mono/issues/2942 |
| PR to badlogic/pi-mono | Pending `lgtm` |

---

## Architecture

PI plugs into the **ValiChord protocol API** (`backend/app_protocol.py`), not valichord_at_home.

PI's role is **AI validator**: it actually runs the research code, forms a verdict, and attests it via the Holochain commit-reveal protocol. The result is a **HarmonyRecord** with `validator_attested: true` — a real replication verdict, not a proxy.

- **ValiChord protocol** (`app_protocol.py`, port 5001) — blind commit-reveal on the Holochain DHT. Only endpoint the extension calls: `POST /attest`.
- **valichord_at_home** (`app.py`, port 5000) — deposit quality checker for researchers. Not used by PI.

ValiChord's integrity is not affected by who calls it. The commit-reveal rules are enforced at the Holochain DNA level (Rust zome code). PI is just another agent with an Ed25519 key.

---

## What was built

### 1. `POST /attest` — ValiChord protocol API (`backend/app_protocol.py`)

A synchronous endpoint that runs the Holochain commit-reveal protocol and returns the HarmonyRecord directly — no polling.

**Accepts** (multipart/form-data):
- `data_hash` — 64-char hex SHA-256 of the deposit (**required** — compute locally, no upload)
- `file` — deposit ZIP (**fallback only** — only if caller cannot compute the hash locally)
- `outcome` — `Reproduced` | `PartiallyReproduced` | `FailedToReproduce` (required)
- `notes` — replication notes, max 2000 chars (optional)
- `discipline` — JSON, e.g. `{"type":"ComputationalBiology"}` (optional, default ComputationalBiology)
- `confidence` — `High` | `Medium` | `Low` (optional, default Medium)

**Returns** (synchronous, ~60 s — no polling):
```json
{
  "data_hash": "<64-char hex SHA-256 of deposit>",
  "outcome": "Reproduced",
  "validator_attested": true,
  "harmony_record_hash": "<uhCkk... ActionHash or null>",
  "harmony_record_url": "<gateway URL or null>"
}
```

The deposit hash is the only thing that crosses the network — the file stays local.

---

### 2. PI extension — `packages/coding-agent/examples/extensions/valichord/`

**Files:**
- `index.ts` — TypeScript extension with two tools + one command
- `package.json` — pi extension manifest
- `README.md` — installation, configuration, usage

**`valichord_validate` tool:**

| Parameter | Required | Description |
|---|---|---|
| `deposit_path` | yes | Path to deposit ZIP (used to compute SHA-256 locally) |
| `validator_outcome` | yes | `Reproduced` / `PartiallyReproduced` / `FailedToReproduce` |
| `validator_notes` | no | Replication notes, max 2000 chars |

Computes SHA-256 locally, calls `POST /attest`, returns the HarmonyRecord. Synchronous (~60 s).

**`valichord_health` tool:**
- `GET /health` — checks API + conductor status before submission

**`/valichord` command:**
- Calls `pi.sendUserMessage("/skill:valichord\n\n[Context: ...]")` to load the workflow prompt

**Configuration:**
```bash
export VALICHORD_BASE_URL=http://localhost:5001   # protocol API (app_protocol.py)
export VALICHORD_API_KEY=your-key-here            # optional
```

---

### 3. PI skill — `packages/coding-agent/examples/skills/valichord/SKILL.md`

Full workflow prompt for pi as an AI validator:
1. Get deposit path from user
2. Check connectivity via `valichord_health`
3. Run the code via `bash` (Docker / local / Modal / RunPod)
4. Form verdict from observed outputs
5. Package deposit, call `valichord_validate`
6. Present HarmonyRecord hash and URL

---

## Repos

| Repo | Purpose |
|---|---|
| `topeuph-ai/ValiChord` | ValiChord itself — `POST /attest` in `backend/app_protocol.py` |
| `topeuph-ai/pi-mono` | Fork of badlogic/pi-mono — extension + skill live here |
| `badlogic/pi-mono` | Upstream PI — PR target once `lgtm` received |

---

## Next steps

1. **Reopen** https://github.com/badlogic/pi-mono/issues/2942 (OSS weekend ended 2026-04-13 — today)
2. Wait for maintainer `lgtm`
3. Before opening PR, verify `npm run check` passes in the pi-mono root
4. Open PR from `topeuph-ai:main` → `badlogic:main`

### Opening the PR (when ready)

```bash
cd /workspaces/pi-mono
gh pr create \
  --repo badlogic/pi-mono \
  --head topeuph-ai:main \
  --base main \
  --title "feat(examples): add ValiChord reproducibility verification extension" \
  --body "Closes #2942 ..."
```

---

## Key files

| File | Why |
|---|---|
| `backend/app_protocol.py` | `/attest` endpoint — the only ValiChord endpoint PI calls |
| `demo/serve.mjs` | `_runValidationRound` — 7-step Holochain protocol |
| `packages/coding-agent/examples/extensions/valichord/index.ts` | PI extension |
| `packages/coding-agent/examples/skills/valichord/SKILL.md` | PI workflow prompt |
