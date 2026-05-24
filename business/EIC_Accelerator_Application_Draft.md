# EIC Accelerator — ValiChord Application Draft
**Grant Only (UK applicant) | Maximum €2,499,999 | Open Call**
**Version:** Draft 0.2 — May 2026 (reviewed and corrected)

> **Note on a common misconception:** Some sources suggest UK applicants should apply for "Grant First" (blended finance). This is incorrect for 2026. The EIC Accelerator guide states explicitly: *"Applicants from the United Kingdom can apply for the Accelerator, but can only request and receive funding in the form of 'grant only'."* Grant Only is not a limitation — it is the correct and only option. Maximum grant: €2,499,999.

---

## BEFORE YOU START — Critical first steps

These must happen before submitting, in this order:

1. **Incorporate a UK Ltd company FIRST** — Companies House, £12, 24 hours online
   - Do this before anything else — submitting as an incorporated entity carries significantly more credibility with evaluators than applying as a natural person
   - The company name becomes the applicant on the proposal and the PIC registration
   - Takes 24 hours. There is no reason to delay this.

2. **Register the company on the EU Funding & Tenders Portal** → https://ec.europa.eu/info/funding-tenders/opportunities/portal/
   - Register as a **legal entity (SME)**, not a natural person
   - You will receive a 9-digit **Participant Identification Code (PIC)** — keep this safe
   - SME validation takes a few days, so do steps 1 and 2 immediately

3. **Give consent to share data** with National Contact Points and other funding bodies
   - This is what activates the Seal of Excellence if you score 13/15+ but aren't selected
   - The Seal of Excellence on its own is valuable — it unlocks other funding streams

---

## KEY FACTS FOR THIS APPLICATION

| Item | Detail |
|---|---|
| Funding type | Grant Only (UK — not eligible for blended finance or equity) |
| Maximum grant | €2,499,999 (70% of eligible costs) |
| TRL required | Must have completed all aspects of TRL 5 (validation in relevant environment) |
| Short proposal batching | First Tuesday of every month, 5pm Brussels time |
| Submission limit | Maximum 3 attempts across entire Horizon Europe programme |
| Video | 3 minutes, on camera, you + up to 2 others |
| Pitch deck | Max 10 slides, PDF |
| Questionnaire | 12 pages max |

---

## PART 1 — PROPOSAL INFORMATION (Part A)

### Suggested Acronym
**VALICHORD** (or **VERICORE** — "Verification Infrastructure for Claims and Outcomes: Reproducibility Engine")

### Suggested Title
*ValiChord: Universal Trust Infrastructure for Independent Claim Verification*

### Abstract (approx. 200 words — for the portal form)

> The global cost of irreproducible research is estimated at $28 billion per year in the US alone — before counting clinical trial failures, financial model mis-statements, and contested forensic evidence. The root cause is structural: claims are verified by parties who are paid by, employed by, or otherwise dependent on the party making the claim. No protocol currently exists to make independent verification mathematically enforceable.
>
> ValiChord is that protocol. Using a cryptographic commit-reveal mechanism on a distributed peer-to-peer network, ValiChord ensures that multiple independent validators commit to their findings before any reveal phase begins — making post-hoc coordination structurally impossible. The result is a HarmonyRecord: a tamper-evident, permanently readable verification record controlled by no single party.
>
> ValiChord does not determine truth. It provides mathematical proof of independent agreement — which is the highest verification standard achievable without omniscience, and the one that institutional trust currently fails to deliver.
>
> The protocol is live, operational, and validated in the AI safety evaluation domain with integration into the UK AI Security Institute's toolchain. EIC support will fund the team, security hardening, and commercial validation across three priority verticals: scientific publishing, clinical research, and financial model auditing — completing the journey from TRL 6 to TRL 8.

### Keywords (select up to 3 parent + descriptors)

**Suggested keywords:**
- **Digital Technologies** → Trust infrastructure / Cryptographic protocols
- **Health and Life Sciences** → Research integrity / Clinical validation
- **Society** → Institutional trust / Verification systems

*Note: Review the full EIC keyword list at https://eic.ec.europa.eu — these are indicative. Choose keywords that match the expert pool you want evaluating your proposal.*

---

## PART 2 — THE 12-PAGE QUESTIONNAIRE

*These are draft answers. Review, personalise, and adjust tone — the voice must be yours.*

---

### Section 1: THE INNOVATION

**Q: What is the problem or opportunity you are addressing?**

The world has a trust crisis that is structural, not episodic. Across every field where claims matter — science, medicine, finance, law, politics, environment — the verification of those claims is controlled by parties with an interest in the outcome. Peer review is slow and opaque. Regulatory audits are performed by auditors paid by the regulated entity. Expert witnesses are hired by the side they support. Manifesto costings are produced by the party making the promises.

The result is a reproducibility crisis that spans every discipline. Nature's 2026 special issue found only half of published claims could be replicated. Fewer than one-third of breast cancer cell biology trials are reproducible. 54% of infectious disease physicians report witnessing misconduct by colleagues. The FDA estimates 50–90% of published preclinical results cannot be reproduced. Financial models submitted to regulators produce convenient results. Building safety inspections are performed by assessors contracted by building owners — a conflict that contributed to the Grenfell tragedy.

Existing responses — fact-checkers, peer reviewers, independent auditors — all share a structural flaw: they are institutions that can be pressured, discredited, or simply disbelieved. In an era of declining institutional trust and AI-generated misinformation, "trust us, we checked" is no longer sufficient.

**Q: What is your innovation and how does it address this problem?**

ValiChord is a universal trust infrastructure protocol. It replaces institutional authority with mathematical proof.

The core mechanism is a cryptographic commit-reveal protocol running on a distributed peer-to-peer network (Holochain). When a claim requires verification:

1. The claimant commits to their result — a cryptographic hash — before any validator sees it
2. Independent validators each assess the claim and commit to their verdicts cryptographically, before seeing any other validator's commitment
3. All parties reveal simultaneously — no last-mover advantage, no coordination possible
4. The result is recorded as a HarmonyRecord on a distributed DHT (hash table) — tamper-evident, permanently readable, controlled by no single party

ValiChord does not determine what is true. It provides cryptographic proof that multiple independent parties reached the same conclusion without the ability to coordinate. This is the highest verification standard achievable without omniscience — and it is mathematically verifiable by anyone.

**Q: How is your innovation different from existing solutions?**

| Approach | Limitation | ValiChord difference |
|---|---|---|
| Peer review | Slow, opaque, reviewers can communicate | Cryptographic independence — mathematically provable |
| Blockchain provenance | Proves WHO made a claim and WHEN, not WHETHER it was independently verified | Commit-reveal proves independent verification |
| Fact-checkers | Institutional — distrusted by the side being checked | Protocol-based — no institution to distrust |
| Independent auditors | Paid by regulated entity, single assessment | Multiple validators who demonstrably couldn't coordinate |
| Pre-registration | Voluntary, weakly enforced, no verification of replication | Enforced cryptographically, verification is recorded |

No existing solution provides field-agnostic, cryptographically enforced, multi-party independent verification where coordination is structurally impossible. ValiChord is the first.

**Q: What is the current Technology Readiness Level (TRL) of your innovation?**

**Current TRL: 5–6** — Validation in relevant environment complete; prototype demonstrated.

The EIC grant funds the journey from TRL 6 to **TRL 8** (system complete and qualified for commercial deployment). This is exactly what the application is for.

**Evidence of TRL 5 completion (validation in relevant environment):**
- Live deployment on Oracle Cloud: 4 independent Holochain nodes running continuously — this is a real network, not a lab simulation
- Public web demo at valichord-demo.onrender.com — full commit-reveal protocol operating end-to-end
- Four-DNA Holochain architecture fully operational: attestation, researcher repository, validator workspace, governance
- 20 automated integration tests (attestation DNA) + 17 governance tests, all passing in CI
- Integration with UK AI Security Institute's inspect_ai evaluation framework — real-world domain validation
- Cited as Pattern 13 in the falsify-cookbook — independent peer-reviewed recognition

**What the grant funds (TRL 6 → TRL 8):**
- Independent security audit and cryptographic hardening (required for enterprise/regulatory use)
- Multi-vertical validation: scaling from proof-of-concept to qualified deployment in science, clinical research, and finance
- Enterprise-grade infrastructure (SLA, API, compliance documentation)
- Commercial pilot completions that constitute TRL 8 evidence

> **Critical framing note:** The live demo proves TRL 5 is complete and TRL 6 is underway. It is evidence that the grant is not speculative — not a claim that development is finished. The product the grant funds (enterprise-qualified, multi-vertical, security-audited) does not yet exist.

**Q: What is your IP strategy?**

ValiChord's IP strategy is based on three pillars:

1. **Protocol know-how and first-mover advantage** — ValiChord is the only operational implementation of field-agnostic commit-reveal verification on a distributed network. The protocol design, four-DNA architecture, and commit-reveal implementation represent substantial know-how that is not easily replicable.

2. **Open-core model** — The core protocol is open source (MIT licence), consistent with the approach of successful infrastructure companies (RedHat, HashiCorp, Elastic). Openness drives adoption and trust — a verification protocol that is itself opaque would undermine its own value proposition. The competitive moat is in the network (validator community), integrations, and managed services — not the code itself.

3. **Network effects** — The value of ValiChord increases with every validator who joins the network and every domain that integrates with it. First-mover advantage in building this validator network is a durable competitive barrier that cannot be replicated by copying the code.

*[Note: Before full proposal stage, seek a brief IP consultation — Innovate UK Business Growth can signpost free IP advice for SMEs. Consider whether any specific protocol innovations are patentable.]*

---

### Section 2: THE MARKET

**Q: What is the total addressable market? What is your realistic market share expectation?**

ValiChord addresses a horizontal need — independent verification — that exists across every field where claims are contested. The total addressable market is therefore very large; the realistic near-term opportunity is in three priority verticals.

**Priority Vertical 1: Scientific Research and Academic Publishing**
- Global scientific publishing market: ~$28 billion annually
- Reproducibility failure costs an estimated $28 billion per year in the US alone in preclinical research (Freedman et al., PLOS Biology)
- Growing regulatory and funder requirement for pre-registration and independent replication
- Target customers: research funders (Wellcome, UKRI, NIH), journals (Nature, Science, PLOS), universities
- Realistic 5-year market share: 1–2% of reproducibility-related services = €50–100M opportunity

**Priority Vertical 2: Clinical Research and Pharmaceutical**
- Global CRO (Contract Research Organisation) market: ~$70 billion, growing at 12% annually
- FDA guidance on reproducibility in drug development creates regulatory demand
- A single Phase III trial costs £500M–£2B — reproducibility disputes at this scale justify significant verification spend
- Target customers: CROs (IQVIA, Parexel, Covance), pharmaceutical sponsors, regulatory bodies
- Realistic 5-year market share: <0.5% = €100–300M opportunity

**Priority Vertical 3: Financial Model Validation**
- EU AI Act (effective August 2026) mandates comprehensive traceability for high-risk AI systems
- UK/US model risk management regulations (SR 11-7, SS1/23) require independent model validation
- Target customers: banks, asset managers, insurance companies, regulators
- Realistic 5-year market share: Small but high-value contracts = €50–150M opportunity

**Total realistic 5-year revenue target: €50–100M ARR** from a combination of SaaS platform fees, professional services, and API licensing.

**Q: What is your business model and revenue strategy?**

Three revenue streams, developed in sequence:

1. **Professional Services (Year 1–2)** — Paid pilot implementations in each priority vertical. A researcher or organisation pays ValiChord to implement the protocol for a specific use case. Generates early revenue and domain-specific proof points. Indicative pricing: £20,000–£100,000 per implementation.

2. **SaaS Platform (Year 2–3)** — Hosted ValiChord network with subscription access. Organisations pay monthly/annual fees to submit validation requests and access the validator network. Tiered pricing by volume and validation tier. Indicative: £500–£5,000/month per organisation.

3. **API Licensing and Integration (Year 3+)** — White-label integration for CROs, journals, regulatory bodies, and legal firms. Per-validation or annual licence fees. Highest-volume, most scalable revenue stream.

**The "ValiChord Verified" credential** — analogous to an SSL certificate or UL certification — becomes the long-term value anchor. Organisations pay for the credential; the credential drives platform adoption.

---

### Section 3: THE TEAM

*This is the weakest section — be honest about gaps and credible about the plan to fill them.*

**Current team:**

**Ceri John — Founder and Chief Product Officer**
- Originated the ValiChord concept from a background in scientific reproducibility as a problem domain
- Directed development of all four protocol DNAs, the browser UI, the Python attestation library, the AI validator demo, and the decentralised Oracle deployment through human-AI collaboration (Claude Code)
- Established integrations with UK AI Security Institute toolchain (inspect_ai) and the falsify-cookbook peer-reviewed ecosystem
- Strengths: product vision, stakeholder communication, cross-domain problem framing, unconventional approaches
- Acknowledged gap: technical coding skills and business/commercial background

**ValiChord was built through human-AI collaboration.** The technical architecture, implementation decisions, and integration strategy were directed by the founder working with Claude Code (Anthropic's AI development tool). This is not a limitation — it is evidence that the protocol can be built, deployed, and maintained with a lean team, and it demonstrates the founder's ability to direct complex technical work without traditional engineering backgrounds.

**Plan to fill team gaps (funded by EIC grant):**

- **Technical Co-founder / CTO** (Month 1–3): Experienced distributed systems or cryptography engineer. Will own the technical roadmap, security audits, and engineering team growth. *Currently in discussions with Innovate UK Business Growth regarding co-founder matching.*
- **Head of Business Development** (Month 3–6): Domain expertise in at least one priority vertical (pharma, finance, or academic publishing). Will own the commercial pilot pipeline.
- **Advisory board** (ongoing): Domain experts in clinical research, financial regulation, and scientific publishing. Several individuals from the inspection_ai/AISI ecosystem have expressed interest.

**Gender balance note:** The founding team will be built with gender balance as an explicit hiring criterion, consistent with EIC guidance.

---

### Section 4: NEED FOR EU SUPPORT

**Q: Why is EIC support needed? Why can't the market finance this alone?**

ValiChord is deep tech infrastructure with a long value chain before returns are generated. Specific reasons market financing is insufficient at this stage:

1. **Protocol risk** — Distributed peer-to-peer protocols are notoriously difficult for conventional investors to value. The underlying technology (Holochain) is not a blockchain — it has no speculative token economy — which makes it opaque to most VC investors while making it more appropriate for trust infrastructure.

2. **Market creation, not market entry** — ValiChord is not entering an existing market. It is creating the category of cryptographic independent verification as a service. Category creation requires patient capital, long sales cycles, and the ability to develop multiple verticals simultaneously.

3. **Network effects require critical mass** — The validator network needs sufficient participants before it generates returns. Building that network requires upfront investment that market actors will not finance before returns are visible.

4. **Public good dimension** — The fields where ValiChord is most needed (science, medicine, democracy) are precisely the fields least able to pay early-stage market rates. EIC support allows these markets to be developed in parallel with the commercial verticals.

*The EIC Accelerator's "patient capital" principle is exactly what this innovation requires.*

**Q: What will the €2.499M grant fund over 24 months?**

*[This is indicative — adjust when you have real cost estimates]*

| Work Package | Activity | Indicative Budget |
|---|---|---|
| WP1: Team | CTO hire, BD hire, operations | €800,000 |
| WP2: Protocol hardening | Independent security audit, performance optimisation, TRL 8 completion | €400,000 |
| WP3: Vertical 1 — Science | 3 paid pilot implementations with research institutions/publishers | €300,000 |
| WP4: Vertical 2 — Clinical | 2 paid pilots with CROs, regulatory engagement | €400,000 |
| WP5: Vertical 3 — Finance | 2 paid pilots with financial institutions | €300,000 |
| WP6: Platform | SaaS platform development, API infrastructure | €200,000 |
| WP7: Project management | Reporting, milestones, coordination | €99,999 |
| **Total** | | **€2,499,999** |

**30% co-financing (~€1.07M) — this requires a real answer, not hand-waving.**

The total eligible project cost is ~€3.57M (grant covers 70%). The co-financing plan:

- **Pilot revenues (Year 1):** Early professional services pilots in each vertical at £20,000–£50,000 each. Three pilots in Year 1 = £60,000–£150,000 contributed to eligible costs.
- **UK seed investment:** The EIC grant award is used as leverage to raise a parallel seed round from UK investors (Innovate UK, angels, or early-stage VCs). A confirmed EIC grant substantially de-risks the investment case. Target: £500,000–£750,000 seed alongside the grant.
- **Innovate UK co-investment:** Innovate UK Business Growth has grant and loan instruments that can co-finance alongside Horizon Europe. Target: £200,000–£300,000.

*[This section needs firm commitments before the full proposal stage. The short proposal needs a credible stated plan; the full proposal needs Letters of Intent from co-investors or pilot customers.]*

---

## PART 3 — PITCH DECK OUTLINE (10 slides, PDF)

| Slide | Content |
|---|---|
| 1 | **The Problem** — Trust crisis. Quote: 50–90% of science can't be reproduced. The institutions we rely on to verify claims are themselves untrustworthy. |
| 2 | **The Insight** — ValiChord doesn't solve trust by building a better institution. It removes the need to trust any institution. Mathematics instead of authority. |
| 3 | **How it works** — Commit-reveal in plain language. Diagram: commit → seal → reveal → HarmonyRecord. "No party can see others' conclusions before committing their own." |
| 4 | **Live and working** — Screenshot of the demo. Oracle Cloud deployment. "This is not a whitepaper. It runs right now." |
| 5 | **Field agnostic** — Icon grid: Science / Clinical / Finance / Legal / Democracy / Environment. One protocol, every domain. |
| 6 | **Market** — TAM/SAM/SOM for the three priority verticals. Keep it honest — don't overclaim. |
| 7 | **Business model** — Professional services → SaaS → API licensing → "ValiChord Verified" credential. |
| 8 | **Traction** — AISI/inspect_ai integration. falsify-cookbook Pattern 13. Oracle live deployment. 37 passing integration tests. |
| 9 | **The team** — Founder photo + brief. Honest about gaps. "Building the team with EIC support." |
| 10 | **The ask** — €2.499M grant over 24 months. Milestones. "Join us in building the trust layer the world needs." |

---

## PART 4 — VIDEO SCRIPT (3 minutes)

*You speak directly to camera. Keep it simple. The guide says: "show the team behind the idea and your motivation." This is not a product demo.*

---

**[0:00–0:20] — Open with the problem**

"I'm Ceri John, founder of ValiChord. We are building trust infrastructure for a world that has stopped trusting institutions.

The global cost of irreproducible research is $28 billion a year. Clinical trials fail because results that couldn't be replicated drove billion-dollar development decisions. Expert witnesses reach opposite conclusions because there's no mechanism to prove they worked independently. We have a systemic verification failure — and it's getting worse."

**[0:20–1:00] — The insight**

"The question I kept coming back to was: what if we didn't need to trust any institution? What if the verification process itself was designed so that no single party could manipulate it — not even ValiChord?

ValiChord is a protocol. Not a fact-checker, not a watchdog. A cryptographic process where independent parties commit to their findings before seeing each other's — and that commitment is mathematically permanent. No one can change what they said after the fact. No one can coordinate before the fact. The result is a record that anyone can verify, that no one controls."

**[1:00–1:45] — Show it works**

"I built this — with AI as my technical co-author — and it runs right now on servers in Oracle Cloud. Three independent validators, committing and revealing in a real distributed network. Not a demo environment. A live network.

It started as an attempt to address the scientific reproducibility crisis. Then people in clinical research told me they needed it. Lawyers told me they needed it. People working in election integrity told me they needed it. It turns out the problem it solves is universal."

**[1:45–2:30] — The ask**

"I need EIC support to do three things: build the team I can't build alone, harden the protocol to enterprise standards, and develop three markets in parallel — scientific publishing, clinical research, and financial model validation — because they all need this now.

I'm not a coder. I'm not a businessman. What I am is someone who saw a problem clearly, found a way to solve it, and built a working implementation. The EIC Accelerator is patient capital for high-risk, high-impact deep tech. That's exactly what this is."

**[2:30–3:00] — Close**

"ValiChord doesn't make things true. It proves they were independently verified. In a world drowning in unverifiable claims, that might be the most valuable thing you can build.

I'm Ceri John. And I'd like your help to build it properly."

---

## GAPS TO ADDRESS BEFORE SUBMISSION

These are the known weaknesses in this draft. They need honest answers, not spin:

| Gap | Priority | Plan |
|---|---|---|
| Not yet incorporated | **DO THIS FIRST** | Incorporate UK Ltd, £12, 24 hours at Companies House — before anything else |
| TRL framing | **Critical** | Use TRL 5-6 (current) → TRL 8 (funded destination). Live demo = TRL 5 evidence, not completion claim. |
| Co-financing (30% = ~€1.07M) | **Critical** | Pilot revenues + UK seed round leveraging EIC grant + Innovate UK co-investment. Needs firm LOIs by full proposal stage. |
| Letters of Intent | **High** | Approach: (1) AISI/inspect_ai team, (2) a UK university research office, (3) a CRO or journal. These are warm relationships — ask now. |
| Solo founder | **High** | Be explicit: CTO search underway, Innovate UK Business Growth engaged, advisory interest from AISI ecosystem. Name names where possible. |
| Financial projections | **High** | 5-year model needed before full proposal. Revenue assumptions → cost assumptions → growth path. Build with Claude Code. |
| IP strategy | **Medium** | Frame as open-core (MIT licence) with competitive moat via network effects, know-how, and first-mover position. Get a free IP consultation via Innovate UK Business Growth before full proposal. |
| No revenue | **Medium** | Pre-revenue is normal for EIC deep tech. Live demo + AISI integration + falsify-cookbook citation = credible traction signals. Frame these explicitly. |

---

## USEFUL CONTACTS

- **EU Funding & Tenders Portal**: https://ec.europa.eu/info/funding-tenders/opportunities/portal/
- **UK National Contact Point for EIC**: https://iuk-business-connect.org.uk/programme/european/horizon-europe/
- **Innovate UK Business Growth** (formerly EDGE): https://iuk-business-connect.org.uk
- **EIC helpdesk**: EC-FUNDING-TENDER-SERVICE-DESK@ec.europa.eu
- **Companies House incorporation**: https://www.gov.uk/limited-company-formation/register-your-company

---

*This document is a working draft. It will be revised as the application develops. The 12-page questionnaire on the F&T Portal will have specific question fields — this draft maps to the evaluation criteria rather than the exact form fields, which you will only see after registering and starting a submission.*
