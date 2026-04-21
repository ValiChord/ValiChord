# ValiChord — Claude Code Instructions

## Always read at session start
- `PROJECT_STATUS.md` — current project phase, what's live, how Feynman uses ValiChord, open work
- `docs/Holochain_complete.md` — complete Holochain Build Guide knowledge base
- `docs/7_ValiChord_4-DNA_architecture_technical.md` — four-DNA architecture

## Pending upgrade checks (run at every session start)

### Holochain 0.6.1 + tryorama 0.19.1 upgrade
Run `holochain --version` at session start.
- If still `0.6.0`: do nothing, report status to user.
- If `0.6.1` or later is installed, OR if `cargo search holochain` / GitHub releases shows 0.6.1 available: perform the following automatically:
  1. Install: `cargo install holochain --version 0.6.1 --locked`
  2. In `valichord/tests/package.json` change `"@holochain/tryorama": "0.19.0"` → `"0.19.1"`
  3. Run `cd valichord/tests && npm install`
  4. Verify tests still pass: `pkill -f holochain; pkill -f lair-keystore; sleep 2 && cd valichord/tests && npm test`
  5. Report outcome to user.

**Why:** tryorama 0.19.1 switches transport from WebRTC/tx5 → iroh/QUIC, requiring Holochain 0.6.1 (iroh 0.6.1). Currently pinned at tryorama 0.19.0 to avoid breakage. `valichord/tests/package.json` has `"@holochain/tryorama": "0.19.0"` (exact pin, not `^`).

**Note:** Check https://github.com/holochain/holochain/releases if `holochain --version` is ambiguous.

---

## What Holochain is — read this before writing anything about ValiChord

**Holochain is NOT a blockchain.** Never use the words blockchain, distributed ledger, on-chain, or any crypto-currency framing. The user is actively de-cryptoing this project and this mistake is a serious one.

Holochain is **agent-centric distributed computing**:
- Every agent (user/node) maintains their own **source chain** — a personal append-only log of their own actions, cryptographically signed by them
- Shared state lives in a **DHT (Distributed Hash Table)** — a peer-to-peer data store where each node holds a slice of the data and validates what it holds
- There is no global ledger, no miners, no tokens, no consensus mechanism across all nodes
- Validation is **local**: each node validates the data it receives against the integrity zome rules
- This makes Holochain fundamentally different from Ethereum, Bitcoin, or any blockchain — it scales with the number of users rather than being bottlenecked by global consensus

**What ValiChord uses Holochain for:**
- DNA 1 (Researcher Repository) — researcher's private source chain; stores the deposit commitment
- DNA 2 (Validator Workspace) — each validator's private source chain; stores their sealed verdict before reveal
- DNA 3 (Attestation) — shared DHT; coordination space for requests, commitment anchors, and reveals
- DNA 4 (Governance) — shared DHT; permanent public HarmonyRecord once validation is complete

**What ValiChord is — core meaning, do not corrupt:**
- ValiChord asks: *can an independent party arrive at the same result as the researcher?*
- "Reproduced" means the validator got the **same result as the researcher** — NOT that the result is correct
- A study can be reproducible and scientifically wrong. A study can be correct but not reproducible. ValiChord only answers the reproducibility question, never the correctness question.
- The commit-reveal protocol means no validator can change their verdict after seeing what others found, and the researcher cannot change their claim after seeing what validators found

---

## Hard separation — ValiChord proper vs valichord_at_home

**These are two completely separate projects. Never conflate them.**

| Project | Path | What it does | Deployed |
|---|---|---|---|
| **ValiChord proper** | `valichord/` | Holochain commit-reveal protocol — 4 DNAs, blind attestation, HarmonyRecord on DHT | Dev only (local conductor) — NOT live |
| **valichord_at_home** | `valichord_at_home/` | Standalone deposit quality checker — 80+ detectors, cleaning reports, draft generation | Live on Render via `backend/app.py` |

Rules:
- When describing ValiChord's architecture → talk about the 4 DNAs, commit-reveal, Holochain. Do NOT mention detectors or ASSESSMENT.md.
- When asked what's deployed/live → valichord_at_home analysis is live on Render. ValiChord protocol is NOT deployed to a live network.
- `backend/app.py` integrates both (runs analysis then optionally calls Holochain bridge) — that is an integration choice, not a definition of either project.
- Before any response touching both, stop and verify you are not conflating them.

---

## Hard constraints
- Never use `pack_dna.py` to build DNAs — it is broken (embeds the same DNA bytes for all four roles)
- Always use `hc dna pack` + `hc app pack` (see `.claude/skills/integration-testing.md`)
- Before running tests: `pkill -f holochain; pkill -f lair-keystore; sleep 2`

## Upgrading ValiChord coordinator code (zero DNA hash change)
Changes to coordinator zomes only (no integrity zome changes) can be deployed without changing the DNA hash via the Holochain admin API `UpdateCoordinators` call:
```
AdminRequest::UpdateCoordinators { dna_hash, coordinator_bundle }
```
- Pack only the coordinator: `hc dna pack --coordinator-only` (outputs a `.dna` without integrity)
- Send `AdminRequest::UpdateCoordinators` with the new coordinator bundle
- All running cells on that DNA immediately use the new coordinator; no reinstall required
- **DNA hash stays identical** — existing source chains and DHT data are unaffected
- Use this for: bug fixes, new read functions, schedule() additions, warrant-gate changes
- **Do NOT use** for: integrity zome changes, new entry/link types, `cache_at_agent_activity` toggles — those require a new DNA hash and network migration
