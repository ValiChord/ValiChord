# ValiChord

**Harmony from Dissonance**

Distributed validation infrastructure for computational research reproducibility.

---

## What is ValiChord?

ValiChord is a proposed system for structured, independent verification of computational research. It coordinates multiple validators to reproduce published analyses, producing **Harmony Records** — reports that preserve the full texture of agreement and disagreement rather than a binary pass/fail verdict.

The name comes from music: a chord is multiple notes sounding together. Agreement is harmony. Disagreement is dissonance. Both carry information.

ValiChord is currently in the pre-funding stage, with a Phase 0 empirical study proposed to UKRI's Metascience funding programme.

## Current status

| Component | Status |
|---|---|
| Architecture & design | Complete (50,000+ words of documentation) |
| **ValiChord at Home** | **Live — [try it now](https://topeuph-ai.github.io/ValiChord/at-home.html)** |
| Holochain scaffold | Complete (1,488-line Rust type system) |
| Phase 0 proposal | Drafted for UKRI Metascience Round 2 |
| Technical validation | Confirmed by Holochain Foundation (Jan 2026) |
| Funding | Not yet secured |
| Working software | Not yet built |

## ValiChord at Home

The first public-facing tool from the ValiChord project.

A **reproducibility readiness check** for code repositories. 24 questions across 6 categories (Documentation, Dependencies, Environment, Data Access, Code Organisation, Self-Verification). Produces a diagnostic report — not a score — showing what a validator would need to find in your repository.

**[→ Use ValiChord at Home](https://topeuph-ai.github.io/ValiChord/at-home.html)**

- No account needed
- Nothing tracked, stored, or shared
- Works entirely in your browser
- Export your report as markdown

Based on FAIR principles, The Turing Way, and Software Sustainability Institute guidelines.

## Architecture overview

ValiChord is designed as an eight-layer system built on [Holochain](https://www.holochain.org/), an agent-centric distributed framework:

- **Layer 0:** Data & Integrity Foundation (content-addressed, tamper-evident snapshots)
- **Layer 1:** Intake & Pre-Commitment (structured protocols, time-locked analysis plans)
- **Layer 2:** Validation Engine (distributed coordination, commit-reveal protocol, gaming detection)
- **Layer 3:** Governance & Policy (transparent rule-setting, anti-capture mechanics)
- **Layer 4:** Audit & Provenance (tamper-evident event log, provenance graphs)
- **Layer 5:** Output & Certification (Harmony Records, reproducibility badges)
- **Layer 6:** Incentive & Reputation (multi-dimensional, non-gameable scoring)
- **Layer 7:** Integration & Interface (journal, funder, and repository APIs)

### Why Holochain, not blockchain?

Holochain is architecturally distinct from blockchain: where blockchain requires a single global ledger with energy-intensive consensus, Holochain keeps data local to each participant and distributes only cryptographic proofs. This means:

- **GDPR compliance** — sensitive research data never leaves institutional control
- **No transaction fees** — validation shouldn't cost money to record
- **No mining** — verification uses standard computing resources
- **Scalability** — each validation is independent, not competing for block space

## Planned development phases

| Phase | Focus | Duration | Estimated cost |
|---|---|---|---|
| **Phase 0** | Empirical measurement study — how long does validation actually take? | 12 months | ~£150K |
| Phase 1 | Build core Holochain infrastructure based on Phase 0 evidence | 18 months | ~£500K |
| Phase 2 | Scale to multiple disciplines, train difficulty prediction model | 24 months | ~£750K |
| Phase 3 | Full ecosystem integration with journals and funders | Ongoing | ~£500K |

Each phase has explicit design gates. Phase 0 can fail — and that failure would be informative.

## Repository contents

```
README.md               This file
docs/
  index.html            Project landing page (GitHub Pages)
  at-home.html          ValiChord at Home tool
scaffold/
  valichord_scaffold.rs Holochain architecture in Rust types (1,488 lines)
```

## Who is behind this?

ValiChord was conceived by **Ceri John** (Burry Port, Wales), a brass music teacher, documentary filmmaker, and independent researcher. The architecture has been technically validated by the Holochain Foundation.

The project is seeking a Principal Investigator and institutional home for the UKRI Phase 0 application.

## Contact

- GitHub: [topeuph-ai](https://github.com/topeuph-ai)
- Project: ValiChord — Harmony from Dissonance

## Licence

Architecture documents and ValiChord at Home are shared for review and evaluation. Full open-source licensing will be determined on funding.

---

*"Every initiative assumes verification is feasible at reasonable cost. That assumption has never been tested."*
