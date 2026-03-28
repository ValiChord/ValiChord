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

## Hard constraints
- Never use `pack_dna.py` to build DNAs — it is broken (embeds the same DNA bytes for all four roles)
- Always use `hc dna pack` + `hc app pack` (see `.claude/skills/integration-testing.md`)
- Before running tests: `pkill -f holochain; pkill -f lair-keystore; sleep 2`
