# Check Holochain Upstream Updates

Run this skill periodically (suggested: before any upgrade, or monthly) to get a current picture of upstream changes that affect ValiChord.

---

## Step 1 — Check current versions in use

Read `valichord/Cargo.toml` and note the current `hdk` and `hdi` version constraints.

Current baseline (last checked 2026-03-21):
- `hdk = "0.6"` → stable channel
- `hdi = "0.7"` → stable channel

---

## Step 2 — Check latest published versions

Fetch these URLs and note the latest stable and dev versions:

- https://crates.io/crates/hdk — latest stable hdk
- https://crates.io/crates/hdi — latest stable hdi

Compare against the versions in `Cargo.toml`. If a new minor or major version is available, flag it and check the changelog before upgrading.

---

## Step 3 — Check the specific issues ValiChord tracks

Fetch the following GitHub issues and note: open/closed, current project status column, whether a PR is now linked, any milestone assignment.

| Issue | What it affects | Last known status |
|---|---|---|
| https://github.com/holochain/holochain/issues/5010 | validate() API breaking change (0.8) | Open, Ready for refinement, no PR (2026-03-21) |
| https://github.com/holochain/holochain/issues/5131 | Validate memproofs on demand — credential revocation | Open, Ready for refinement, no assignee (2026-03-21) |
| https://github.com/holochain/holochain/issues/5132 | Kitsune2 Access module — transport-layer membrane enforcement | Open, Ready for refinement, no assignee (2026-03-21) |
| https://github.com/holochain/holochain/issues/4345 | Private entry hash collision bug | Open, Ready for refinement, no fix (2026-03-21) |
| https://github.com/holochain/holochain/issues/4911 | Coordinator updates: capability tokens | Open, Ready for refinement, no PR (2026-03-21) |
| https://github.com/holochain/holochain/issues/4912 | Coordinator updates: remote calls | Open, Ready for refinement, no PR (2026-03-21) |
| https://github.com/holochain/holochain/issues/4126 | Agent migration / Deepkey InstallApp | Open, no milestone, no PR (2026-03-21) |

**Flag if any issue has moved from "Ready for refinement" to "In Progress", gained a PR, or been closed.** These are the trigger events that require action.

---

## Step 4 — Check latest Holochain releases

Fetch https://github.com/holochain/holochain/releases and note:
- Latest stable release and date
- Latest dev release and date
- Any new release since the last check

Releases to watch:
- **0.6.1 stable** — safe upgrade when released, no API changes
- **0.7.0 stable** — requires hdk/hdi version bump + network config review (iroh transport)
- **0.8.x** — validate() API breaking change; do not upgrade without migration plan

---

## Step 5 — Update the handover doc

If anything has changed, update the "Holochain Upgrade Radar" section of `docs/13_Valichord_Engineer_Handover.md`:
- Update the "as of" date
- Correct any issue statuses that have moved
- Add notes on any new releases
