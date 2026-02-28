<div align="center">
  <img src="../Valichord logo-standard v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">
</div>
# ValiChord Complete — Governance Framework
## How the System Resists Corruption, Capture, and Domestication

**Author:** Ceri John
**Date:** February 2026

**© 2026 Ceri John. All Rights Reserved.**

**Contact:** topeuph@gmail.com

---

## Why This Document Exists

If ValiChord fails, it won't fail technically. The architecture is sound. The cryptography works. The distributed systems are proven.

It will fail because it gets slowly domesticated.

Institutions will want clean metrics. Funders will want simple scores. Journals will want unambiguous signals. High-status researchers will want their work validated, not questioned. And the natural trajectory of every system that starts by speaking uncomfortable truths is toward a system that stops — not because anyone makes a dramatic decision, but because a hundred small accommodations accumulate until there's nothing left worth defending.

Every previous reproducibility initiative has followed this trajectory. Journal data mandates that nobody enforces. Repository requirements that produce unusable deposits. Peer review that never attempts reproduction. The policies exist. They have been domesticated.

This governance framework is ValiChord's immune system. It is designed before it's needed — not retrofitted after institutional pressures are already embedded — because governance structures bolted on after powerful actors are involved always get shaped to serve those actors.

The framework is organised in three tiers, activated progressively as the system grows. Tier 1 operates from day one. Tier 2 activates as the system matures. Tier 3 is the complete architecture, designed now so that the mature system inherits the right DNA.

---

## The Core Insight

> "ValiChord's true adversaries are: coordinated legitimacy, career incentives, institutional dominance, and human risk aversion. Silence, ambiguity, and selective participation are more dangerous than outright fraud."

This is the threat model. Not hackers. Not technical failure. The slow, procedurally correct erosion of epistemic integrity by actors who benefit from polite uncertainty.

The governance philosophy follows from this:

**Detection over prevention.** You can't prevent all gaming. You can make it detectable and costly.

**Transparency over perfection.** Better to admit uncertainty than fake certainty.

**Process over outcomes.** Good process yields good outcomes over time.

**Community over control.** Governance serves the community, not itself.

**Discomfort over comfort.** Some discomfort is necessary for integrity. Especially when powerful actors find it uncomfortable.

---

## TIER 1: ACTIVE GOVERNANCE
### Operates from Phase 0 onward

This is what actually runs during the pilot and early operations. It is deliberately minimal — governance overhead must match operational scale. Building full committee structures for 16–20 validations would consume resources better spent proving the core model works.

### 1.1 Decision Authority

**Phase 0:** Project Lead (Ceri John) + Academic PI make operational decisions. All decisions logged with rationale. No decisions behind closed doors.

**Simple appeals process:** Any participant can challenge a decision in writing. PI reviews within 10 business days. Response with rationale published. If unresolved, external reviewer (from advisory network) provides binding decision within 15 business days.

### 1.2 Conflict of Interest Screening

Before any validation assignment:
- Validator declares institutional affiliations
- Cross-checked against study authors and institutions
- Co-authorship within 5 years = disqualification
- Same department = disqualification
- Same institution = permitted only if different department and no collaboration history

COI declarations logged. False declarations = immediate removal from pilot.

### 1.3 Basic Transparency

- All governance decisions published with rationale
- Aggregate pilot results shared with participants
- No selective reporting of outcomes
- Disagreement between validators documented, not hidden

### 1.4 Participant Protection

- Informed consent with clear explanation of study design
- Right to withdraw without penalty
- Anonymity in publications
- Time caps (40 hours maximum per task)
- Fairness adjustment for disproportionately difficult assignments
- GDPR-compliant data storage at host institution

### 1.5 The Six Non-Negotiable Commitments

These apply from day one. They are not "aspirational goals for the mature system." They are the minimum conditions under which ValiChord operates at any scale.

**Commitment 1: Forced Disagreement Visibility.**
When validators disagree on a study's reproducibility, that disagreement is documented prominently. It cannot be hidden, averaged away, or relegated to a footnote. In the pilot, this means the final report includes all validator assessments for each study, including divergent ones, with no editorial smoothing.

**Commitment 2: Institutional Attribution.**
Validators are identified by institution in internal records. This creates accountability — if an institution's validators systematically produce soft reviews, the pattern becomes visible. In the pilot, this is recorded in the dataset (anonymised in publications but available for pattern analysis).

**Commitment 3: No Guaranteed Closure.**
Some studies may produce genuinely ambiguous results. The system does not force a clean verdict where the evidence doesn't support one. In the pilot, "unable to determine" is a legitimate and valued outcome, not a failure.

**Commitment 4: Rapid Consequences.**
If a validator submits work that is clearly inadequate (e.g., completing a 20-hour task in 2 hours with a generic report), the consequence is immediate: the validation is flagged, the validator is contacted, and if the pattern continues, they are removed. No months-long committee review.

**Commitment 5: Pattern Visibility.**
Aggregate patterns are tracked even in the pilot. If validators from a particular background consistently produce different results than others, this is documented as a finding, not suppressed.

**Commitment 6: Legible Governance.**
Every decision about the pilot — study selection, validator assignment, difficulty classification, any changes to protocol — is logged with its reasoning and available to participants on request.

---

## TIER 2: ENHANCED GOVERNANCE
### Activates during Phase 1–2, when the system has real users and real stakes

These mechanisms are designed now but activated only when operational scale requires them. The trigger is not a calendar date but evidence of need: when the number of validators, validations, or institutional relationships creates governance demands that Tier 1 cannot handle.

### 2.1 Advisory Board

**Composition:** 5–7 members.
- At least 2 practising computational researchers (potential validators)
- At least 1 research integrity specialist
- At least 1 representative from a potential institutional partner
- No majority from a single institution
- 2-year terms, staggered rotation

**Authority:** Advisory, not executive. Provides guidance on policy questions, reviews appeals that exceed PI capacity, and flags emerging risks. Executive authority remains with the project team, accountable to funders.

**Transparency:** Meeting minutes published. Dissenting views recorded.

### 2.2 Research Integrity Office (Basic)

A designated function (not necessarily a separate office at this scale) responsible for:
- Investigating concerns about validator behaviour
- Reviewing flagged validations
- Maintaining the COI register
- Monitoring for gaming patterns
- Handling formal complaints

**Staffing:** Part-time governance lead + 3–5 advisory RIO members drawn from the advisory board and external network.

### 2.3 Validator Cartel Detection

As the validator pool grows, systematic monitoring for:

**Pattern 1: Collusion.** Cross-institutional agreement rates tracked. If two validators agree >90% of the time across 20+ validations, investigation triggered.

**Pattern 2: Institutional volume dominance.** Per-institution validator caps enforced: maximum 40% of validators from any single institution.

**Pattern 3: Rubber-stamping.** Time tracking compared to task complexity. Validators completing tasks in <10% of expected time flagged automatically.

**Pattern 4: Selective participation.** Complexity distribution analysis. Validators who only accept easy tasks have assignment priority reduced.

**Pattern 5: Homophily.** Agreement rates with specific institutions tracked. >90% agreement with a single institution over 20+ validations triggers reputation penalty.

**Response:** Automated flagging → manual review → decision → rationale published. Appeals to RIO.

### 2.4 Reputation System Governance

When the reputation system activates:
- Full algorithm published (open source)
- Weights for each factor disclosed
- Changes announced 3 months in advance
- Historical changes logged publicly

**Forbidden components in the reputation algorithm:**
- Volume bonuses (no rewarding quantity over quality)
- Speed bonuses (no racing incentives)
- Institutional prestige weighting (no halo effects)
- Personal network advantages

**Algorithm changes require:** Proposal → community feedback → 60% supermajority of algorithm committee.

### 2.5 Certification Standards

When Harmony Records become formal outputs:

**Required elements in every Harmony Record:**
1. Protocol identification
2. Validation summary (validator count, outcomes)
3. Epistemic confidence (High/Medium/Low + rationale)
4. Disagreement disclosure (if any, prominently displayed)
5. Limitations section (always included)
6. Link to full provenance
7. Valid dates (issue + expiration, minimum 24 months)

**Forbidden elements:**
- Single numerical "reproducibility score"
- Phrases like "guaranteed reproducible"
- Sensational language
- Omission of disagreements
- Selective presentation of outcomes

**Badge issuance rules:**

| Level | Minimum Validators | Success Rate | Additional Requirements |
|-------|-------------------|-------------|------------------------|
| Bronze | 3 | ≥60% | No substantial unresolved disagreements |
| Silver | 5 | ≥70% | Pre-registered, deviations disclosed |
| Gold | 7 | ≥80% | Multi-institutional, open data + code |

Badge criteria reviewed annually. Changes apply to new protocols only. Tightening requires 2-year notice.

### 2.6 Compensation Fairness

**Principles:**
- No bonuses for speed (prevents rushing)
- No penalties for thoroughness
- Quality multipliers, not quantity
- Rates reviewed annually against market rates for peer review
- Compensation rates published openly

**Tiered compensation baselines** (subject to Phase 0 evidence):
- Tier 1 (1–2 hours): £50–100
- Tier 2 (4–8 hours): £200–400
- Tier 3 (16+ hours): £800–1,600

### 2.7 Institutional Capture Prevention

As institutional partnerships form, specific defences:

**Separation of powers.** No single institution can dominate governance, validation, or funding decisions simultaneously.

**Term limits and rotation.** All governance positions rotate on 2-year terms, staggered so no more than one-third of any body changes at once.

**Diverse representation required.** Advisory board, RIO, and any future committees must include representation from small institutions, early-career researchers, and non-UK perspectives (from Phase 2 onward). Geographic and institutional diversity in validator panels is not an equity add-on — it is an architectural requirement for epistemic credibility. A validation pool dominated by a small number of well-resourced institutions is insufficiently independent to produce trustworthy results. ValiChord needs qualified validators across regions and institutions; those validators need funded opportunities to build credibility and skills. This exchange is genuinely mutual, and the governance framework treats it as structural, not aspirational.

**Graph-based independence verification.** Co-authorship and funding relationship graphs used to verify that governance bodies are genuinely independent, not connected through shared networks.

**Power concentration monitoring.** Decision pattern analysis: is one institution winning all appeals? Is one perspective dominating all standards decisions? Tracked and published quarterly.

---

## TIER 3: COMPLETE GOVERNANCE ARCHITECTURE
### Designed for the mature system — Phase 2 and beyond

This tier specifies the full governance framework that a system operating at scale would need. It is designed now because the mature system must inherit the right principles. Governance designed after powerful actors are embedded always gets shaped to serve those actors.

Not all of this will be needed. The specific mechanisms activated will depend on evidence from earlier phases. But the architecture is ready.

### 3.1 Full Governance Structure

```
┌──────────────────────────────────────────────────────┐
│ RESEARCH INTEGRITY OFFICE (Central Governance)       │
│ • Final decision authority                           │
│ • Appeals adjudication                               │
│ • Standards evolution                                │
│ • Transparency oversight                             │
└──────────────────────────────────────────────────────┘
              ↓ (Sets standards for)
┌──────────────────────────────────────────────────────┐
│ PRE-COMMITMENT STANDARDS (Layer 1)                   │
│ • Deviation Review Board                             │
│ • Disciplinary standards committees                  │
│ • Pre-registration requirements                      │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ VALIDATION RULES (Layer 2)                           │
│ • Validator selection constraints                    │
│ • Gaming detection thresholds                         │
│ • Collusion pattern analysis                         │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ META-GOVERNANCE (Layer 3)                            │
│ • Rule evolution process                             │
│ • Appeals structure                                  │
│ • Separation of powers                               │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ CERTIFICATION STANDARDS (Layer 5)                    │
│ • Badge issuance rules                               │
│ • Harmony Record formatting                          │
│ • Narrative report quality control                   │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ INCENTIVE INTEGRITY (Layer 6)                        │
│ • Anti-gaming measures                               │
│ • Compensation fairness                              │
│ • Reputation algorithm transparency                  │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ ECOSYSTEM RULES (Layer 7)                            │
│ • API access policies                                │
│ • Integration requirements                           │
│ • Third-party usage guidelines                       │
└──────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────┐
│ TRANSPARENCY STANDARDS (Layer 8)                     │
│ • Public disclosure requirements                     │
│ • Dashboard accuracy standards                       │
│ • Privacy protections                                │
└──────────────────────────────────────────────────────┘
```

### 3.2 Pre-Commitment Governance (Layer 1)

**Pre-Registration Requirements Matrix:**

| Research Type | Pre-Registration Status |
|---|---|
| Computational (early adoption) | Recommended |
| Computational (mature system) | Required |
| Preclinical | Required |
| Clinical (low-risk) | Required |
| Clinical (high-risk) | Required + Enhanced |
| Qualitative | Optional |
| Theoretical | Not Applicable |
| Exploratory | Optional (but disclosed) |

**Deviation Review Board:** 5–7 members, disciplinary diversity required, no majority from single institution, 2-year rotating terms. Reviews deviations flagged as "Substantial" epistemic impact. Can approve, require additional validation, or require re-registration. Decisions published within 48 hours with rationale.

**Disciplinary Standards Committees:** One per major discipline (initially 5–8). Define what pre-registration looks like in their field — hypothesis formats, acceptable deviation types, outcome measure specifications. Committees cannot make pre-registration *less* stringent than baseline. Can add requirements, not remove them.

**Exploratory vs. Confirmatory Distinction:** Researchers must declare analysis type at registration. Confirmatory analyses assessed for adherence to pre-registered plan. Exploratory analyses assessed for methodological soundness. Mislabelling exploratory work as confirmatory triggers governance escalation.

### 3.3 Validation Rules (Layer 2)

All mechanisms from Tier 2 cartel detection, plus:

**Anti-calcification mechanisms** (preventing early adopters from locking in permanent advantage):
- Reputation decay: exponential, 180-day half-life (established validators must keep contributing)
- Domain-bounded reputation: credibility in oncology does not transfer to neuroscience. Authority is distributed across specialisms, preventing any validator from leveraging success in one field to claim authority in another
- Periodic reputation recalibration
- New validator boost (first 10 validations weighted more heavily to allow establishment)
- Blind validator selection: validators don't know who else is validating the same study, preventing coordination

**Campbell's Law resistance:**
- Context publication requirement (validation results must be presented with context)
- Anti-threshold guidance (explicit policy against reducing Harmony Records to simple pass/fail)
- Variance and uncertainty always reported alongside any summary metric

**Cross-disciplinary semantic drift prevention:**
- Standardised attestation taxonomy: Success / Partial / Failed / Inconclusive
- Annual standards review across disciplines
- Explicit acknowledgment that "success" means different things in different fields

### 3.4 Governance Hardening Mechanisms (Layer 3)

**3.4.1 Governance Load Asymmetry.** It should be harder to change governance rules than to operate within them. Rule changes require proposal, community consultation (30-day minimum), evidence-based justification, and supermajority approval. This prevents governance capture through procedural manipulation.

**3.4.2 Progressive Appeal Exhaustion.** Appeals require progressively more evidence at each level. First appeal: written statement. Second appeal: supporting evidence. Third appeal: external review. This prevents vexatious appeals from consuming governance capacity while ensuring legitimate concerns are heard.

**3.4.3 Event-Based Reputation Shocks.** A single serious gaming attempt can destroy reputation faster than years of good behaviour built it. Recovery is possible but slow. This makes the expected cost of gaming always exceed the expected benefit.

**3.4.4 Graph-Based Independence Verification.** Co-authorship graphs, funding relationship maps, and institutional affiliation networks used to verify that governance bodies, validator panels, and review committees are genuinely independent. Algorithmic checking, not self-declaration.

**3.4.5 Ethics Output Normalisation.** Validation outcomes compared across institutions and disciplines to detect systematic bias. If validators from Institution X consistently produce more favourable results than the field average, this is flagged for investigation.

**3.4.6 Silent Exit Detection.** When validators stop participating without explanation, patterns are analysed. If exits correlate with being assigned difficult studies or studies from prestigious institutions, this signals potential coercion or self-censorship.

### 3.5 Ecosystem Rules (Layer 7)

**API Access Tiers:**

| Tier | Authentication | Rate Limit | Access |
|---|---|---|---|
| Public | None | 100 req/hour | Public Harmony Records only |
| Partner | Required | 1,000 req/hour | Aggregate statistics |
| Administrative | Internal only | Unlimited | Full system access, audit-logged |

**Third-party usage restrictions:**
- Harmony Records cannot be used to create institutional league tables
- Reproducibility badges cannot be used as sole basis for hiring/firing decisions
- Partner agreements include acceptable use provisions
- Misuse monitoring operational

**Integration requirements:**
- Partners must display Harmony Records accurately (no selective presentation)
- Disagreements must be shown (cannot display badge without acknowledging disagreement)
- ValiChord retains right to revoke API access for misuse

### 3.6 Transparency Standards (Layer 8)

**Public disclosure requirements:**
- All governance decisions published within 48 hours
- Aggregate statistics published quarterly
- Algorithm changes announced 3 months in advance
- Annual transparency report

**Dashboard accuracy:**
- Numbers must match underlying data exactly
- Visualisations cannot distort (e.g., truncated axes)
- Summaries cannot omit material information
- 10% random sampling + manual review

**Privacy protections:**
- Minimal data collection (only what's operationally necessary)
- Explicit consent for storage
- Right to deletion (GDPR Article 17)
- Data export available (GDPR Article 20)
- Breach notification within 72 hours (GDPR Article 33)
- Aggregate statistics anonymised (k=5 minimum)
- Validator harassment protection mechanisms

### 3.7 The Funding Flywheel

Traditional research capacity funding is consumed: a grant pays for equipment, training runs, the money is spent, and new funding is needed. ValiChord's structure creates a different dynamic where initial investment recycles through the network.

**The cycle:**

1. **External funding catalyses capability.** A grant from a body like Wellcome Trust or UKRI funds equipment, training, and infrastructure at an institution in an under-resourced research economy.
2. **Operational capability earns through validation work.** That institution's researchers, now equipped and trained, participate as validators — paid at professional rates, tiered by complexity, from ValiChord's operational budget.
3. **Accumulated earnings fund capability development elsewhere.** Revenue from validation work can be reinvested — either within the institution (expanding capacity, training more researchers) or directed toward bootstrapping capability at other institutions.
4. **The original investment recycles.** Rather than being consumed by a single grant cycle, the initial funding generates ongoing, measurable, verified returns. Each attestation on the DHT is auditable proof of both capability development and productive contribution.

**Why this works:** Validator diversity is an architectural requirement, not a charitable goal. ValiChord needs qualified validators across regions and institutions to produce epistemically credible results. Institutions in under-resourced economies need funded pathways to build credibility and methodological skills. Both needs are real. The exchange is genuinely mutual. Neither side is doing the other a favour — they are solving each other's problems.

**What makes it auditable:** Unlike traditional capacity-building programmes where impact is assessed by self-reported surveys years later, every validation completed is a cryptographically verified, timestamped record of demonstrated competence. Funders can see exactly what their investment produced, in real time, with no ambiguity.

**Governance constraint:** The funding flywheel must not create dependency. If a single external funder catalyses capability at multiple institutions, those institutions must not become beholden to that funder's priorities. The funding concentration tripwire (Mechanic 3 in Anti-Domestication Mechanics) applies here: if one funder's investment touches more than 25% of validator capacity, this triggers disclosure and review. The flywheel generates independence, not a new form of capture.

---

## THE DEFENCE PLAYBOOK

### Red Lines That Cannot Be Conceded

Regardless of who asks — funders, partner institutions, journal editors, government officials — the following cannot be conceded:

1. **Disagrement visibility cannot be removed.** The pressure will come as: "Can we just show the majority result?" or "Disagreement confuses non-experts." The answer is no. Disagreement is preserved for a minimum of 24 months. This is non-negotiable because hiding disagreement is exactly how the reproducibility crisis happened.

2. **Institutional attribution cannot be made anonymous.** The pressure will come as: "Our validators are concerned about retaliation." Individual validator anonymity is negotiable (see Safe Concessions below). Institutional-level attribution is not, because it creates the accountability that prevents rubber-stamping.

3. **No single numerical score.** The pressure will come as: "We need a number for our database" or "Reviewers don't have time to read Harmony Records." The answer is: provide a summary, provide a confidence level, provide a status — but never a single number that can be used as a threshold. Because thresholds get gamed, and gaming thresholds is exactly what p-hacking is.

4. **No forced closure on ambiguous results.** The pressure will come as: "We need a decision for this grant review" or "The paper is being held up." The answer is: the system provides the best evidence available, honestly described. If that evidence is ambiguous, the honest description is "ambiguous." Forcing certainty where none exists is the fundamental failure mode of the current system.

### Safe Concessions (Things That Can Be Negotiated)

- Individual validator anonymity (as long as institutional attribution is preserved)
- Timeline adjustments for Harmony Record publication (within the anti-delay constraint — extensions are permitted but must be public, bannered, and time-limited; see Anti-Domestication Mechanics)
- Discipline-specific adaptations of standards
- Presentation format changes (as long as content requirements are met)
- Partnership terms and pricing
- Governance committee composition details
- Technology implementation choices

### Scripts for Difficult Conversations

**When a funder says:** "We need a simple score for our database."
**Response:** "We can provide a structured summary — reproducibility status, confidence level, and validator count — in a machine-readable format that your systems can ingest. What we can't provide is a single number, because reducing complex validation evidence to a single score creates exactly the kind of metric that gets gamed. We've seen this with p-values, journal impact factors, and h-indices. We'd be creating the next version of the same problem."

**When an institution says:** "Our validators want full anonymity."
**Response:** "We protect individual validator identity by default. What we can't hide is institutional affiliation, because institutional patterns are how we detect systematic problems. If an institution's validators consistently produce soft reviews, that needs to be visible — not to shame the institution, but to maintain the system's integrity. Without this, we can't distinguish genuine validation from rubber-stamping."

**When a journal says:** "We just want to know pass or fail."
**Response:** "We can give you a clear reproducibility status — and for most studies, that will be straightforward. But for studies where validators genuinely disagree, we'll say so — because that disagreement might be the most important finding. A study where five validators succeed and one fails might be telling you something about hidden assumptions, software versions, or genuine fragility. That's information your editors need, not noise to be averaged away."

---

## ANTI-DOMESTICATION MECHANICS

### Why This Section Exists

The Defence Playbook above states what ValiChord will not concede. This section specifies *how* those commitments are enforced mechanically — through code-level constraints, API licence terms, and automatic tripwires that operate without requiring anyone to be brave in the moment.

These mechanisms are designed around two concrete failure scenarios that were stress-tested against the governance framework and revealed gaps between philosophical commitment and operational reality.

### Scenario A: Institutional Soft-Capture via Flagship Partnership

**The threat:** A large, respected institution becomes ValiChord's flagship partner. They provide funding, validators, and journal introductions. They are not hostile — they are enthusiastic. But over time, small accommodations accumulate: a "summary view" that buries disagreement behind a click, cautious language from their validators, polite requests to delay publication of inconvenient results. No rules are broken. The system is slowly hollowed out through procedural compliance.

**Why it's dangerous:** Every request is individually reasonable. Nobody acts in bad faith. The capture happens through structural dependency, not coercion.

#### Mechanic 1: Default Salience Rule (Code-Level)

If material disagreement exists in a Harmony Record, it must be visible in the first screen, first scroll, and first API response. Not behind tabs, summaries, confidence labels, or badges.

This is a UI governance constraint enforced in code, not a policy preference. Any interface — internal or partner-facing — that renders Harmony Records must pass a salience check: disagreement visible without user action.

**Rationale:** Default views define reality. Almost no one clicks through. A "summary-first" display that technically preserves disagreement behind a link is functionally indistinguishable from hiding it.

#### Mechanic 2: Anti-Delay Constraint

Harmony Records must be published within a defined maximum latency after final attestation (specific threshold to be set during Phase 1, informed by operational evidence).

Extensions require:

- Public rationale logged in the governance record
- A visible "Delayed by Governance Review" banner on the pending record
- Automatic publication if the extension period expires without resolution

Delay becomes louder, not quieter. Any actor requesting delay must accept that the delay itself is visible and documented.

**Rationale:** In fast-moving fields, sitting on a Harmony Record for three months while "awaiting clarification" is functionally equivalent to suppression. The anti-delay constraint ensures that the cost of delay is reputational transparency, not quiet burial.

#### Mechanic 3: Funding Concentration Tripwire

No single institution may simultaneously exceed two of the following three thresholds:

- More than 25% of operational funding
- More than 25% of active validators
- More than 25% of governance seats

Exceeding two of three triggers:

- Automatic public disclosure of the concentration
- Temporary intake throttling for new validations from that institution
- Mandatory governance review within 30 days

**Rationale:** Financial dependency is governance capture by another name. An institution that provides your funding, your validators, and your governance oversight doesn't need to make demands — everyone already knows what would happen if they withdrew. The tripwire makes concentration visible before it becomes structural.

#### Mechanic 4: Exit-with-Integrity Clause

ValiChord pre-commits publicly to the following statement, embedded in all partnership agreements and published on the project website:

> "If maintaining ValiChord's epistemic commitments becomes incompatible with continued funding or partnership, ValiChord will prefer contraction or suspension over compromise."

This is not a dramatic gesture. It is a filter. Good partners are not threatened by it. Partners who intend to exert influence through dependency will self-select out early, which is exactly the point.

### Scenario B: Journal-Led Capture via Workflow Integration

**The threat:** Journals integrate ValiChord's API into their editorial workflows. They use Harmony Records during peer review. This sounds like success. But journals control timing, framing, editorial thresholds, and reviewer instructions — all of which sit outside ValiChord's governance boundary. Without touching ValiChord's code or governance, a journal can: use ValiChord only at pre-submission triage (filtering out studies likely to show disagreement before they reach validation); instruct reviewers to defer to Harmony Records (turning them into shields rather than signals); display summarised badges to readers while editors see full records (asymmetric visibility); treat only pre-submission records as authoritative (shifting ValiChord from corrective to confirmatory); and eventually define "ValiChord-validated" in ways that exclude disagreement, ambiguity, and post-review validation.

**Why it's dangerous:** The capture happens entirely outside ValiChord's system boundary. Nobody touches the governance, the code, or the data. They control the context in which ValiChord's outputs are interpreted. ValiChord hasn't changed. Its meaning has.

#### Mechanic 5: API Display Requirements (Licence-Level)

ValiChord's API licence includes mandatory display terms. Any partner querying Harmony Records must:

- Display disagreement with the same visual prominence as agreement
- Include a mandatory, unfurlable link to the full Harmony Record
- Show the "last updated" timestamp (preventing stale snapshots being presented as current)
- Include a standard attribution line: "Full Harmony Record available at [link]"

Summarisation is permitted, but summarisation that omits material disagreement is a licence violation.

**Enforcement:** Violation of display terms results in written notice, 30-day remediation period, and API access revocation if unresolved. Revocation is public and includes the reason.

**Precedent:** This is how Creative Commons works — the licence travels with the content. ValiChord's outputs are public, but the terms of display are not optional.

#### Mechanic 6: Anti-Badge Clause

ValiChord does not issue binary pass/fail badges. The output is always the full Harmony Record or a structured summary that preserves disagreement.

If a journal or institution creates their own binary badge based on ValiChord data (e.g., "ValiChord Validated ✓"), ValiChord does not endorse it. The API terms require any such badge to include the statement: "This badge is not issued by ValiChord. Full validation record available at [link]."

**Rationale:** Binary badges are the mechanism through which nuanced evidence gets reduced to gatekeeping thresholds. ValiChord's entire design philosophy resists this reduction. If journals want a badge, they can create one — but ValiChord's name is not on it, and the full record is always one click away.

**Note:** This mechanic coexists with the existing badge system (Bronze/Silver/Gold) defined in Section 2.5 above. Those badges are multi-level, require specific validator counts and disagreement thresholds, and always link to the full Harmony Record. They are not binary pass/fail signals. The Anti-Badge Clause prevents *external actors* from collapsing ValiChord's multi-dimensional outputs into a binary that ValiChord itself would never issue.

#### Mechanic 7: Temporal Integrity

Harmony Records are living documents. ValiChord's API always returns the current state of a record, including any post-publication validations, updates, or new disagreements.

The API includes:

- `created_at` — when the record was first issued
- `last_updated` — when any component last changed
- `version` — incremented on every material change
- `post_publication_validations` — count and summary of validations added after initial publication

A journal can cache a snapshot, but ValiChord's API will always show when a cached version is stale. Any display of a Harmony Record that omits the `last_updated` field violates the API licence.

**Rationale:** Temporal freezing — treating a pre-submission Harmony Record as definitive and ignoring post-acceptance validations — is how journals would shift ValiChord from corrective to confirmatory. Making records living documents, with visible timestamps, ensures that new evidence cannot be quietly ignored.

#### Mechanic 8: Triage Misuse Detection

ValiChord monitors aggregate query patterns across API partners. Statistical analysis can detect:

- **Pre-screening bias:** A journal that only queries studies before editorial decision and never after acceptance
- **Selective querying:** A journal that queries studies from certain institutions but not others
- **Outcome filtering:** A pattern where studies queried pre-decision and showing disagreement are disproportionately rejected

Pattern detection findings are:

- Published in ValiChord's annual transparency report (anonymised by default)
- Shared privately with the partner for remediation
- Made public (with partner identified) if the pattern persists after notification

**Rationale:** ValiChord cannot control how journals use its data internally. But it can detect patterns in how the API is accessed, and it can make those patterns visible. Detection is the deterrent.

#### Mechanic 9: Public Delisting (Nuclear Option)

If a journal or institution is demonstrably using ValiChord in ways that systematically undermine its epistemic function — and remediation has failed — ValiChord publicly withdraws API access and publishes a detailed explanation of why.

This is the nuclear option. It is reputational, not legal. In science publishing, reputation is currency. The credible threat of public delisting is itself a governance mechanism.

**Threshold:** Delisting requires documented evidence of systematic misuse, failed remediation, and a governance vote (supermajority of RIO or equivalent body at the relevant tier). It cannot be triggered unilaterally.

### How These Mechanics Interact

The two scenarios target different attack surfaces — internal dependency (Scenario A) and external interpretation (Scenario B) — but the defences share a common logic:

**Make capture visible.** Funding concentration is disclosed. Delay is bannered. Query patterns are monitored. Display violations are public. The assumption is not that all partners are hostile, but that transparency prevents good partnerships from drifting into structural dependency.

**Make resistance automatic.** Code-level salience rules, API licence terms, and automatic tripwires operate without anyone needing to make a brave phone call. The point of mechanical governance is that it doesn't depend on the courage of whoever happens to be in charge when the pressure comes.

**Make the cost of capture exceed the cost of compliance.** Public delisting, visible delay banners, and funding tripwires all impose reputational costs on capture attempts. Partners who act in good faith never encounter these mechanisms. Partners who drift toward capture encounter them early, when correction is still easy and cheap.

---

## CRITICAL GOVERNANCE CHALLENGES

### Challenge 1: Governance Capacity vs. System Growth

As ValiChord scales, governance decisions increase. At 10–50 protocols, manual review works. At 500+, it doesn't.

**Mitigations:** Automated triage (most cases handled by rules, only edge cases escalated), clear decision frameworks that reduce deliberation time, delegation to disciplinary committees, and technology-assisted pattern detection.

**Risk:** If governance can't scale, the system bottlenecks. This is monitored and addressed before it becomes critical.

### Challenge 2: Maintaining Integrity Under Pressure

As ValiChord becomes infrastructure, pressure to soften commitments intensifies.

**Pressures:** Institutions want clean metrics. Funders want simple scores. Journals want certainty. Validators want protection.

**Defence:** The red lines above, the defence playbook, community backing, and the fundamental argument: "If we soften these commitments, we become the next version of the problem we're trying to solve."

**Risk:** If commitments erode, ValiChord becomes compliance theatre. This is the primary existential risk to the project — more dangerous than technical failure, funding shortfalls, or adoption challenges.

### Challenge 3: Disciplinary Differences

What counts as "good pre-registration" varies by field. Physics demands precise predictions. Ecology accommodates natural variation. Qualitative research has emergent themes that can't be pre-specified.

**Solution:** Disciplinary Standards Committees with genuine domain expertise. Variation allowed but documented. Cross-disciplinary learning encouraged.

**Balance:** Trust disciplinary expertise, but enforce transparency.

### Challenge 4: International Governance (Phase 3+)

Multi-jurisdictional operation creates legal complexity: GDPR (Europe) vs. CCPA (California) vs. PIPL (China). Research ethics standards vary. Cultural norms around transparency differ.

**Approach:** Minimum global standards (baseline), regional adaptations (where necessary), mutual recognition (federation model), shared principles (transparency, integrity).

### Challenge 5: Governance Capture

The most insidious risk. ValiChord governance could be captured by large institutions (volume dominance), funders (financial pressure), established researchers (prestige bias), or special interests (methodology wars).

**Defences:** The Anti-Domestication Mechanics section above provides nine specific mechanical defences against the two most plausible capture scenarios — institutional soft-capture and journal-led workflow capture. These complement the structural defences: graph-based independence verification, separation of powers, term limits and rotation, diverse representation requirements, the Epistemic Integrity Commitments, and active monitoring of decision patterns.

**Capture is insidious.** It happens gradually through procedurally correct means. The Anti-Domestication Mechanics are designed to make capture visible and costly before it becomes structural. Vigilance is not a phase — it's permanent.

---

## GOVERNANCE EVOLUTION

### Principle

Governance must evolve. The system learns from experience. Edge cases reveal gaps. Gaming strategies adapt. Community needs change.

### Process

1. **Identify need** — Pattern analysis, community feedback, governance bottlenecks, external changes
2. **Propose change** — Document current state, specify proposed change, explain rationale and evidence, identify risks
3. **Community input** — Public comment period (30 days minimum), stakeholder consultation, impact assessment
4. **Decision** — RIO deliberates, rationale published, implementation timeline if approved
5. **Monitor** — Track metrics post-change. Did it solve the problem? Did it create new ones? Adjust or revert if needed.

### Constraints on Evolution

- Changes must be evidence-based, not ideological
- Changes must be transparent — the community sees the reasoning
- Changes must be conservative — requiring justification proportional to impact
- Changes must be reversible where possible
- The six non-negotiable commitments cannot be weakened through the evolution process

---

## Conclusion

ValiChord's governance is not an afterthought. It is the immune system that determines whether the technical architecture serves its purpose or gets captured by the forces it was designed to resist.

The tiered approach means governance matches operational scale — minimal overhead during the pilot, enhanced mechanisms as the system grows, and a complete architecture designed in advance so the mature system inherits the right principles.

If governance fails, ValiChord fails. Not because of technical problems. Not because of adoption challenges. Because trust is lost.

This framework is designed to maintain that trust, even under pressure. Even when it's uncomfortable. Especially when it's uncomfortable.

That's what infrastructure requires.

---

**Companion Documents:**
- *ValiChord Vision & Architecture* — What ValiChord is and why it matters
- *ValiChord Technical Reference* — Architecture sketches for engineering discussion
- *ValiChord Phase 0 Proposal* — Workload Discovery Pilot (£69K, 6 months)
- *ValiChord Researcher Support* — Feedback pipeline and pre-validation tools

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**
