# ValiChord × PI Integration

## Status

| Item | Status |
|---|---|
| `POST /attest` endpoint (backend/app.py) | **Merged to main** |
| PI extension (index.ts, package.json, README.md) | **Pushed to topeuph-ai/pi-mono main** |
| PI skill (SKILL.md) | **Pushed to topeuph-ai/pi-mono main** |
| Issue on badlogic/pi-mono | **Auto-closed (OSS weekend pause) — reopen after 2026-04-13** → https://github.com/badlogic/pi-mono/issues/2942 |
| PR to badlogic/pi-mono | Pending `lgtm` |

---

## What was built

### 1. `POST /attest` — ValiChord backend (`backend/app.py`)

A new synchronous endpoint for validators who have already run the research code.

**Accepts** (multipart/form-data):
- `file` — deposit ZIP (required, max 100 MB)
- `outcome` — `Reproduced` | `PartiallyReproduced` | `FailedToReproduce` (required)
- `notes` — replication notes, max 2000 chars (optional)
- `discipline` — JSON, e.g. `{"type":"ComputationalBiology"}` (optional, default ComputationalBiology)
- `confidence` — `High` | `Medium` | `Low` (optional, default Medium)

**Returns** (synchronous, under 2 min — no polling needed):
```json
{
  "data_hash": "<64-char hex SHA-256 of deposit ZIP>",
  "outcome": "Reproduced",
  "validator_attested": true,
  "harmony_record_hash": "<uhCkk... ActionHash or null>",
  "harmony_record_url": "<gateway URL or null>"
}
```

**Why not `POST /validate`:** `/validate` runs the full valichord_at_home structural analysis pipeline (detectors, cleaning report, 5–20 min). That is a researcher tool for deposit quality — not needed when a validator already has a real execution verdict. `/attest` skips the analysis and goes straight to the Holochain commit-reveal round.

---

### 2. PI extension — `packages/coding-agent/examples/extensions/valichord/`

**Files:**
- `index.ts` — TypeScript extension with two tools + one command
- `package.json` — pi extension manifest
- `README.md` — installation, configuration, usage

**`valichord_validate` tool — two modes:**

| Mode | Trigger | Endpoint | Timing |
|---|---|---|---|
| Validator | `validator_outcome` supplied | `POST /attest` | Synchronous, under 2 min |
| Researcher | No `validator_outcome` | `POST /validate` + poll `GET /result/<job_id>` | 5–20 min |

**`valichord_health` tool:**
- `GET /health` — checks API + conductor status before submission

**`/valichord` command:**
- Calls `pi.sendUserMessage("/skill:valichord\n\n[Context: ...]")` to load the workflow prompt

**Configuration:**
```bash
export VALICHORD_BASE_URL=https://valichord.example.org   # default: http://localhost:5000
export VALICHORD_API_KEY=your-key-here                    # optional
```

---

### 3. PI skill — `packages/coding-agent/examples/skills/valichord/SKILL.md`

Full workflow prompt. When `/valichord` is run:
1. pi asks: researcher or validator?
2. Validator → pi runs the code via bash, forms a verdict, calls `valichord_validate(..., validator_outcome, validator_notes)`
3. Researcher → pi calls `valichord_validate(deposit_path)` only

---

## Architecture decision

PI plugs into **ValiChord proper** (the Holochain commit-reveal protocol), not valichord_at_home.

- **valichord_at_home** = structural analysis of deposit quality (100+ checks). Answers: *does the repo look reproducible?* This is a researcher tool.
- **ValiChord protocol** = blind commit-reveal on the Holochain DHT. Answers: *did an independent party get the same result?* This is what PI as a validator participates in.

ValiChord's independence is not affected. The commit-reveal rules are enforced at the Holochain DNA level (Rust zome code). PI is just another agent with an Ed25519 key — it cannot bypass the protocol.

---

## Repos

| Repo | Purpose |
|---|---|
| `topeuph-ai/ValiChord` | ValiChord itself — the `POST /attest` endpoint lives here |
| `topeuph-ai/pi-mono` | Fork of badlogic/pi-mono — extension + skill live here |
| `badlogic/pi-mono` | Upstream PI — PR target once `lgtm` received |

---

## Next steps

1. **Reopen** https://github.com/badlogic/pi-mono/issues/2942 after 2026-04-13 (auto-closed during OSS weekend pause), then wait for maintainer `lgtm`
2. Open PR from `topeuph-ai:main` → `badlogic:main`
3. Before opening PR, verify `npm run check` and `./test.sh` pass in the pi-mono monorepo (requires `npm install` in the monorepo root first)

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

## Key files to read at session start

| File | Why |
|---|---|
| `backend/app.py` | `/attest` endpoint (lines ~607–686) |
| `backend/holochain_bridge.py` | `run_validation_round` — wraps the Node bridge |
| `demo/serve.mjs` | `_runValidationRound` — 7-step Holochain protocol |
| `packages/coding-agent/examples/extensions/valichord/index.ts` | PI extension |
| `packages/coding-agent/examples/skills/valichord/SKILL.md` | PI workflow prompt |
