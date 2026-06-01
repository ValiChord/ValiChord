# Maintainer-facing CORE-Bench demo doc — design

**Date:** 2026-06-01
**Status:** design approved (pending written-spec review)
**Output artifact:** `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` (written in the implementation step)

## Purpose

A thorough, in-repo, linkable document that we point inspect_evals maintainers
at from a warm introduction (LinkedIn / email). It describes the CORE-Bench ×
ValiChord demo — what it does, what it does not yet do, what needs doing, and the
gap it fills in the eval-framework space — in a register of **composition, not
competition.** The reader has opted in by clicking a link, so the doc can be
thorough; it is not a cold-open issue body.

## Audience and constraints

- **Primary reader:** inspect_evals maintainers (AISI / UKGovernmentBEIS). CORE-Bench
  appears only as the concrete task the demo is built on, not as a separate
  audience addressed in its own section.
- **Register:** respectful, collaborative, technically precise. The audience is
  exactly the people equipped to spot an overclaim, so honesty is load-bearing.
- **Exclude (these stay in the internal `docs/CORE_BENCH_INTEGRATION.md`):**
  - outreach *tactics* ("lead with the demo not the issue", "open warm not cold",
    "demote the schema field") — never show the reader how we plan to pitch them;
  - operational specifics that read as inside-baseball or that point at our infra
    by default — Oracle IP addresses as the default run target, per-run dollar
    costs, Codespace disk sizes, the GPG password for the ground-truth dataset.
- **Relationship to existing docs:** this is a *re-framing* of material already in
  `docs/CORE_BENCH_INTEGRATION.md` (internal strategy) and `demo/CORE_BENCH_DEMO.md`
  (internal run guide) for a new reader — not a third overlapping source of truth.
  The new doc cross-links to those two; it does not duplicate their internal parts.

## Honesty constraints (must hold in the prose)

1. **No claim of a verified clean local end-to-end run.** The `/record`
   numeric-convergence panel and the gossip-free outcome echo were unit-tested and
   `node --check`'d but never exercised against a live conductor. The last *full*
   run (2026-05-31) used our Oracle nodes for the commit-reveal half, not a
   freshly-built local stack. The doc states the local-stack path as the intended
   independent route and lists "verify the local end-to-end with the new node
   code" as an explicit to-do — it does **not** assert we have run it.
2. **Claim the right guarantee.** For deterministic code, commit-reveal prevents
   *result-copying and fabrication*, not *opinion-anchoring*. State it narrowly.
3. **Do not overclaim independence.** N runs of the same model by the same operator
   are correlated, not independent; genuine independence comes from diversity
   across the validator set. Say which claim the demo's configuration supports.
4. The §2 artifact (the public Oracle HarmonyRecord
   `uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT`) predates the `/record`
   panel. Use it to demonstrate the commit-reveal record; show the panel as
   *sample* JSON described in §3, never as live output on that record.

## Document structure

B spine (gap-first) · C artifact (a real record up front) · A headings (the four
pillars as navigable sections).

1. **The gap — one paragraph.** A `.eval` log is single-author and self-attested:
   nothing in it proves a second party would get the same output, or stops the
   producer re-running until the number looks right, or gives a multi-party,
   blinded, tamper-evident record. Inspect *runs* the reproduction; ValiChord
   makes the result *independently checkable*. Composition, not competition.
2. **What you'd actually see.** A short annotated run (the demo's step output) plus
   a `curl` of the real public HarmonyRecord on the Oracle DHT. Concrete artifact
   first. Honest note that the record predates the `/record` panel (see honesty
   constraint 4).
3. **What it does.** N blind agents reproduce the same capsule in isolated Docker
   sandboxes; commit-reveal; the verdict is **arithmetic** (`lower ≤ value ≤ upper`
   against the researcher's *committed* interval — inclusive bounds), not model
   opinion; the **blinding gate** aborts the round if the committed answer is
   readable from any retained file; the record is recomputable from a `curl`.
   Includes the `/record` numeric-convergence panel shown as sample JSON.
4. **What it doesn't do yet.** Candid list: single pre-verified deterministic
   capsule (`capsule-0851068`); manual validator self-claim (Phase 0); reputation
   and badges are `Provisional` in production; no automated `.eval`→protocol
   handoff; the `/record` panel is unit-tested but not yet run live; the last full
   run used our Oracle nodes for the DHT half.
5. **How it fills the gap.** The CORE-Bench-alone / ValiChord-alone / combined
   comparison; "what N independent runs actually prove" (the precise, narrow
   guarantee); the two precision rules (claim the right guarantee; don't overclaim
   independence) woven in as trust-builders, not disclaimers buried at the end.
6. **Reproduce it yourself** (local-stack default — nothing depends on our servers).
   - Prerequisites stated plainly: privileged Docker (the inspect sandbox sets
     `privileged: true`); a paid provider API key (free tiers can't do agentic
     reproduction); ~30 GB free disk; `git` on the host (the inspect_evals pin is a
     `git+` URL).
   - `pip install -r demo/requirements-core-bench.txt`.
   - `docker compose -f demo/docker-compose.yml up --build -d` — uses the
     **prebuilt** `valichord/workdir/*.happ`, so **no Rust / Holochain toolchain is
     required**.
   - `export VALICHORD_RESEARCHER_URL=http://localhost:3001` (+ 3002–3004) so the
     commit-reveal half runs on *their* stack, not ours.
   - The all-Sonnet run command (cheapest, one key); then `curl` their own local
     `/record`.
   - Expected wall-clock and that runs are sequential (one sandbox at a time).
7. **What needs doing.** Flip the runner default to localhost (or a one-command
   `make demo`) so a maintainer never accidentally writes to our nodes; verify the
   local end-to-end with the new node code; broaden to a stochastic capsule;
   **optional follow-on, clearly demoted:** a `valichord_attestation_uri` register
   field would make the integration discoverable from inspect_evals — presented as
   "a possible future step, entirely optional", not an ask the doc is making.
8. **Short respectful close.** The one sentence neither part can say alone:
   several agents ran the code in isolated environments, none could see the others'
   results before committing, the record on a network no single party controls
   shows what each got, and you can verify it yourself with one `curl`.

## What this is not

- Not the body of a GitHub issue (that would be short and cold-open-safe).
- Not a CORE-Bench-authors outreach doc (inspect_evals only).
- Not a replacement for `CORE_BENCH_DEMO.md` (the internal run guide) or
  `CORE_BENCH_INTEGRATION.md` (the internal strategy doc) — it links to and reframes
  them.

## Success criteria

- A maintainer can read it top-to-bottom and understand what the demo proves, what
  it does not, and how to run it on their own machine with Docker + a paid key.
- Contains no internal outreach tactics and no instruction that defaults to our
  infrastructure.
- Every limitation in scope is stated plainly; no claim is made that we have not
  verified.
- The register-field ask is present but unmistakably optional.
