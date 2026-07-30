# GitHub Sponsors profile — source text

Working copies of what's on (or going on) **[github.com/sponsors/topeuph-ai](https://github.com/sponsors/topeuph-ai)**, kept here so the live profile has a versioned source rather than existing only in a web form.

| File | What it is |
|---|---|
| [`introduction.md`](introduction.md) | The **Introduction** field. 4,949 characters against GitHub's 5,000 limit. Paste whole. |
| [`introduction_without_disclosure.md`](introduction_without_disclosure.md) | Identical minus the "Who I am" section (4,655) — the alternative if the AI-tooling disclosure comes out. |
| [`tiers.md`](tiers.md) | Tier names and descriptions, current dashboard state, and which suggestion checkboxes to tick or avoid. |
| `NOTES.md` | Working notes — **local only, gitignored.** URL verification, why ValiChord is given prominence, pre-publish checks, and the claims deliberately kept out. Deliberately not committed: it's candid positioning reasoning, not published material. |

## Short bio (250-character field)

> Published results are taken on trust. I build ValiChord: a Holochain protocol where independent validators reproduce a claim blind, then reveal at once — so no one can change their verdict after seeing yours. Apache-2.0, no tokens.

231 characters.

## Goal

**10 monthly sponsors** — a count rather than a revenue target, because "many small sponsors" is the funding shape the project's independence actually requires. A count also reads as *early* rather than *failing* when the bar is mostly empty, which a revenue target does not.

> Ten sponsors is my first milestone, and a specific one: enough to move the live network off a single machine and onto paid, redundant hosting — so a published Harmony Record stays fetchable for as long as anyone cites it. I'm counting sponsors rather than pounds deliberately: a protocol that verifies other people's results shouldn't lean on any single funder.

## The constraint that governs all of it

No tier reward may touch the protocol's outputs — no priority validation, no sponsor mark on a Harmony Record, no influence over thresholds or validator selection. See [`../../SPONSORS.md`](../../SPONSORS.md), which states this publicly, and `tiers.md` for why the standard sponsorship playbook is the wrong guide here.

## If the character count changes

The Introduction has **51 characters of headroom**. Re-measure before publishing any edit:

```bash
python3 -c "print(len(open('docs/sponsors/introduction.md').read().strip()))"
```
