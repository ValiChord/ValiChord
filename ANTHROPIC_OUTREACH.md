# ValiChord × Anthropic: Outreach Strategy & Email

**Prepared by:** Claude Code (analysis of ValiChord codebase + live Anthropic website research)
**Date:** March 2026

---

## Best Fit: The Anthropic Institute

**Why:** The Anthropic Institute launched March 11, 2026 — 12 days before this analysis. Its stated mission is to "confront the most significant challenges that powerful AI will pose to our societies." It combines three research teams: Societal Impacts, Economic Research, and Frontier Red Team. It is led by Jack Clark (Anthropic co-founder, Head of Public Benefit).

ValiChord is a direct answer to one of those most significant challenges: AI is accelerating scientific publication faster than any existing institution can verify it. Without a verification infrastructure, Anthropic's own scientific AI partnerships (Allen Institute + HHMI, February 2026; DOE Genesis Mission, December 2025) will accelerate the reproducibility crisis rather than solve it. ValiChord is the verification layer those partnerships need.

ValiChord's internal strategic document (doc 12) explicitly identifies AI model auditing as a future application of its architecture — making this not a stretch but a direct alignment.

---

## Secondary Targets

| Target | Route | Timing |
|---|---|---|
| **The Anthropic Institute** (Jack Clark) | `https://www.anthropic.com/contact` — ask specifically for Institute team | Primary — send now |
| **Claude Partner Network** | `https://claude.com/partners` — free application, just launched | This week — independent of primary |
| **Scientific partnerships team** | `https://www.anthropic.com/contact` — pitch as verification layer for Allen/HHMI/DOE work | After Institute contact made |
| **Claude for Nonprofits/API credits** | `https://claude.com/contact-sales` | When API usage needed |

---

## The Email

**To:** Jack Clark, Head of Public Benefit / The Anthropic Institute
**Delivery:** Via `https://www.anthropic.com/contact` (select "Research / Partnership" or equivalent) or via LinkedIn (Jack Clark is publicly reachable). If a mutual connection exists through the Holochain Foundation or UK research networks, a warm introduction is preferable.
**Subject:** ValiChord — verification infrastructure for AI-accelerated science

---

Dear Jack,

The Anthropic Institute launched at exactly the right moment for this conversation.

My name is Ceri John. I have spent the past several years building ValiChord — a distributed, cryptographically verifiable infrastructure for scientific reproducibility. The four-DNA Holochain implementation is complete and integration-tested (89 tests passing). I am writing because ValiChord addresses a challenge that your Institute's mission puts directly in frame, and because Anthropic's scientific AI partnerships have made the challenge more urgent, not less.

**The problem in one sentence:** AI is accelerating scientific publication faster than any institution can verify it, and the reproducibility crisis — already costing $200 billion annually — will scale with the acceleration unless verification infrastructure exists.

The Allen Institute and HHMI are right that "transforming data into validated biological insights remains a fundamental bottleneck." But the bottleneck is not just speed — it is trust. An AI system that generates insights ten times faster than before generates ten times more unverified claims. Without a structural verification layer, you have not solved the reproducibility crisis. You have automated it.

**What ValiChord does:**

ValiChord uses a blind commit-reveal protocol built on Holochain — an agent-centric distributed framework — to record cryptographically permanent, tamper-evident validation outcomes. Validators cannot see each other's assessments before committing their own. Researchers cannot adjust their claimed results after seeing validators' findings. The Harmony Record that emerges is not a binary pass/fail — it preserves the full texture of expert agreement and disagreement, permanently, in a format queryable by any journal, funder, or researcher worldwide.

The architecture is GDPR-compliant by design. Patient data and sensitive research data stay local; only cryptographic validation proofs traverse the shared network. This is why every blockchain-based reproducibility project failed — immutable public ledgers violate data protection law. Holochain's agent-centric model solves this structurally, not by policy.

The technical architecture has been reviewed by Arthur Brock (Holochain co-founder), Paul D'Aoust (Holochain Foundation), and Joel Marcey (Technical Director, Rust Foundation). It is not a whitepaper.

**Why this is relevant to the Anthropic Institute specifically:**

The Institute's Societal Impacts and AI & Rule of Law teams are working on exactly the governance questions ValiChord has already solved in a adjacent domain: how do you build infrastructure that cannot be captured by the interests it scrutinises? How do you preserve honest disagreement rather than forcing false consensus? How do you make verification independent of funding dependency?

ValiChord's anti-capture governance framework was designed to resist the same pressures that domesticated ClinicalTrials.gov, the carbon credit registries, and journal reproducibility mandates — not through policy, but through cryptographic architecture. That design is directly applicable to AI model auditing, which is one of the domains ValiChord's architecture was always intended to reach.

Additionally: the EU AI Act and emerging UK AI frameworks require independent auditing of AI models for accuracy, fairness, and reproducibility of claimed performance metrics. Today that auditing is done by developers or contracted auditors with financial ties to the developer. ValiChord's blind commit-reveal protocol and anti-conflict-of-interest governance are purpose-built for exactly this problem.

**Where we are:**

The infrastructure is built. The Phase 0 workload discovery study — measuring what computational validation actually costs, which nobody has measured — is submitted to UKRI Metascience Round 2 (April 2026, ~£158K). The Phase 1 MVP is ready to build the moment Phase 0 funding lands.

I am not asking for funding. I am asking for a conversation with the Institute's Societal Impacts team — and, if it seems relevant, with whoever at Anthropic is thinking about verification infrastructure for your scientific AI partnerships.

The reproducibility crisis is one of the most significant challenges AI poses to society — not despite AI's acceleration of science, but because of it. ValiChord is the infrastructure that makes AI-accelerated science trustworthy rather than a scaled version of existing problems.

I would welcome thirty minutes.

Ceri John
topeuph@gmail.com
https://github.com/topeuph-ai/ValiChord

---

## Notes on Delivery

- **Warm introduction preferred.** If any connection exists through the Holochain Foundation, UK research institutions (Cardiff University, UKRI networks), or AI safety/policy communities, a warm introduction to Jack Clark carries substantially more weight than a cold contact form submission.

- **LinkedIn is viable.** Jack Clark is publicly active on LinkedIn. A brief direct message with the subject line and first paragraph as a hook, offering to send the full letter, is a legitimate approach.

- **The contact form works.** `https://www.anthropic.com/contact` — select the most relevant category. The message will route internally. Be explicit in the subject field that you are writing about the Anthropic Institute specifically.

- **Do not lead with the technology.** The email above leads with the problem and the societal stakes. Holochain appears in the third paragraph. This is deliberate. Jack Clark is a policy and safety thinker, not primarily a distributed systems engineer. Lead with why it matters; earn the right to explain how it works.

- **Claude Partner Network is independent.** Apply at `https://claude.com/partners` regardless of whether the Institute contact proceeds. It is free, it just launched, and it establishes a formal relationship with Anthropic's partner team that can be escalated later.

---

## Why This Fit Is Strong (The Underlying Logic)

ValiChord and Anthropic share a structural problem: both are trying to build trustworthy systems in domains where the incentives actively reward dishonesty. Anthropic's answer is Constitutional AI, Responsible Scaling Policy, and now the Anthropic Institute. ValiChord's answer is cryptographic architecture, blind commit-reveal protocols, and anti-capture governance. The methods are different. The problem being solved is the same.

Anthropic's scientific AI partnerships generate more claims. ValiChord verifies them. That is not a pitch — it is a description of how these two things fit together.

The Anthropic Institute's newest focus areas — AI progress forecasting and AI's interaction with legal systems — both depend on reliable, independently verifiable data about what AI systems actually do. ValiChord is infrastructure for making computational claims independently verifiable. The overlap is direct.

Finally: the timing. The Institute launched 12 days ago. It is in the process of establishing its external relationships and research agenda. This is the moment to be in the room, not after the agenda has hardened.
