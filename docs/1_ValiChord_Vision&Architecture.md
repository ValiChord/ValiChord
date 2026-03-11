
<div align="center">
  <img src="../Valichord logo-standard v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord
## Vision & Architecture for End-to-End Scientific Reproducibility Infrastructure

**Author:** Ceri John
**Date:** March 2026
**Version:** 11

**© 2026 Ceri John. All Rights Reserved.**

Shared with Holochain Foundation, funding bodies, and potential institutional partners. Not for public distribution without permission.

**Contact:** topeuph@gmail.com

---

## What This Document Is

This is the vision and architecture document for ValiChord Complete. It explains what ValiChord is, why it matters, and how it works — in plain language, for anyone who wants to understand the project.

It is the source document from which grant applications, partnership pitches, and technical briefings are drawn. It is not itself a grant application.

**Companion documents:**
- *ValiChord Technical Reference* — Illustrative architecture sketches for engineering discussion
- *ValiChord Governance Framework* — How the system resists corruption and institutional capture
- *ValiChord Open Design Questions* — Precedents, likely approaches, and resolution phases for fourteen unresolved design problems
- *ValiChord Phase 0 Proposal* — The specific funding ask and pilot design

---

## The Problem

### The Scale of It

Most published scientific research cannot be independently verified. The evidence for this is now overwhelming:

- 70% of researchers have failed to reproduce another scientist's experiments, and 50% have failed to reproduce their own (Nature survey, 2016)
- Of 53 "landmark" cancer studies, only 6 could be reproduced — an 11% success rate (Amgen, Begley & Ellis, 2012)
- 65% of published findings could not be reproduced internally (Bayer, Prinz et al., 2011)
- Only 36 of 100 psychology studies reproduced successfully (Open Science Collaboration, 2015)
- Only 26% of published R packages can reproduce their own documentation (Trisovic et al., 2022)

This costs an estimated $28 billion annually in the United States alone, and over $200 billion globally. It delays drug development by years when researchers build on false leads. It harms patients when treatment decisions rest on unreliable evidence. And it feeds declining public trust in science at a time when that trust matters enormously.

The US White House Office of Science and Technology Policy prioritised reproducibility in July 2025. The NIH now requires data sharing but has no mechanism to verify it happens or that shared data is actually usable. Major journals face an accelerating retraction crisis, with over 10,000 papers retracted in 2023.

### Why It Happens

The crisis has five root causes, and they reinforce each other. Ioannidis (2005) demonstrated that most published research findings are false due to structural incentives in the research system; computational research has inherited these problems while adding new verification challenges of its own.

**Perverse incentives.** Academic careers reward novelty over reliability. "Publish or perish" means researchers need striking positive results, not careful replications. Negative results don't get published. Attempting to replicate someone else's work is widely seen as career-limiting. There is no formal credit for validation work.

**Methodological flexibility.** Researchers have enormous freedom in how they analyse data — which statistical tests to run, which outliers to exclude, when to stop collecting data, which results to report. This isn't necessarily fraud; it's human nature. But it means the published literature is systematically biased toward results that look significant, whether or not they're real. The technical terms for these practices — p-hacking, HARKing (Hypothesising After Results Known), selective reporting — describe a spectrum from unconscious bias to deliberate manipulation.

**Data unavailability.** Even when journals require data sharing, 70% of deposited data turns out to be unusable — missing documentation, broken links, incompatible formats, missing software dependencies. Sharing a dataset is not the same as making it reproducible.

**No validation infrastructure.** There is no systematic way to validate computational research. Peer review doesn't include reproduction attempts. Journals don't have the resources. Funders mandate data sharing but don't fund anyone to actually check the data. The infrastructure simply doesn't exist. The sources of computational irreproducibility are well documented — lack of detailed protocols, insufficient documentation of data and metadata, missing code sections, undescribed software dependencies, and differences in hardware environments (Schultze et al., 2025, UKRN primer on computational reproducibility) — yet no systematic infrastructure exists to check for these factors. Where validation work does happen — in conference artifact evaluation or journal reproducibility checking — it is chronically under-resourced: artifact reviewers report that evaluating reproducibility takes significantly more time than reviewing papers, yet receive less time to do it (Keahey et al., 2025, NSF REPETO workshop report). Journal reproducibility editors cite the need to "keep the review workload manageable" as a reason for limiting what they check (Hornung et al., 2025). The labour is real, skilled, and unmeasured.

**Social dynamics.** Challenging the findings of a high-status researcher at a prestigious institution is career-limiting. Institutions protect their prestigious names. What one AI reviewer of this project called "coordinated legitimacy" — the tendency of scientific communities to maintain polite consensus rather than pursue uncomfortable truths — is often more powerful than any individual's commitment to rigour.

ValiChord exists because no previous attempt has addressed all five of these causes together.

---

## Why Every Previous Solution Failed

### Centralised Repositories: The Data Graveyard Problem

Dryad, Figshare, Zenodo, and institutional repositories were built to make data available. They succeeded at storage but failed at usability. Researchers upload datasets to satisfy funder requirements, not to enable someone else to reproduce their work. The result is what might fairly be called "dark archives" — millions of datasets that technically exist but that nobody can actually use. Compliance is achieved. Reproducibility is not.

### Blockchain: GDPR Violation Machines

Multiple blockchain-based reproducibility projects launched between 2018 and 2023. All failed or were abandoned. The fundamental problem is that blockchain's core feature — immutability — creates severe tension with the EU's General Data Protection Regulation. The GDPR's data minimisation principle requires that sensitive data not be shared beyond what is necessary; putting patient data on a public immutable ledger violates this at the point of storage, not merely on request for erasure. Patient data cannot go on an immutable public ledger. Beyond the legal problem, blockchain solutions were prohibitively expensive ($500K–2M to implement, $50–200K per year for validator nodes) and too slow for large-dataset validation. Universities couldn't justify the costs.

### Journal Policies: Mandates Without Enforcement

Nature, Science, PLOS, and hundreds of other journals now require data and code availability. In practice, compliance runs at roughly 30%. Journals don't have the resources to check whether authors actually shared usable data. Reviewers aren't rewarded for attempting reproduction. Authors post "available upon request" and then don't respond to requests. The policies exist on paper. They have not measurably improved reproducibility.

### NIH Data Sharing: Paperwork Without Verification

The NIH requires data management plans and, increasingly, data sharing. But there is no mechanism to verify that sharing actually happens, no validation that shared data enables reproduction, and no meaningful consequences for non-compliance. Researchers complete the paperwork. The reproducibility crisis continues.

### Registered Reports: Half the Solution

Registered Reports, pioneered by Professor Chris Chambers at Cardiff University and now adopted by over 300 journals, represent the most successful reproducibility innovation to date. By requiring researchers to commit to their hypotheses, methods, and analysis plans *before* seeing results, they eliminate front-end gaming — p-hacking, HARKing, and selective reporting.

But Registered Reports address only the front end of the research lifecycle. They ensure the research question is honestly specified. They do not ensure the results are computationally reproducible. A perfectly pre-registered study can still contain coding errors, use fabricated data, or produce results that no independent researcher can replicate.

Registered Reports are half the solution. ValiChord provides the other half — and integrates both.

### The Pattern

Every one of these attempts shares a common failure mode: they were softened by the system they were trying to reform. Mandates went unenforced. Policies were adopted in letter but not in spirit. Tools were built but not used. Requirements were met on paper while practices continued unchanged. ValiChord is a structural reform attempt in a system designed to resist structural reform. Its governance and architecture are built around that reality.

---

## What ValiChord Is

### The Core Idea

ValiChord is a system where independent researchers re-run other researchers' computational work, report whether they get the same results, and those reports are stored in a way that can't be tampered with.

That's the essence. Everything else — the eight layers, the Holochain architecture, the governance framework — serves that core function. Throughout this document, "validators" means scientific professionals paid to re-run computational studies — not blockchain validators securing a ledger.

### The Validation Lifecycle

A study moves through ValiChord in a clear sequence:

**Submission.** A researcher (or their institution) submits a published computational study — code, data, protocol, and documentation. The system generates cryptographic fingerprints of every file, ensuring all validators work from identical materials.

**Triage.** Automated checks assess the submission: are the files complete? Is the code executable? Are dependencies documented? Studies that fail basic checks receive structured feedback through the Researcher Support pipeline rather than entering the validation queue.

**Assignment.** Validators are selected through constrained randomness — matched for computational competence, screened for conflicts of interest, drawn from different institutions and geographies. Assignment is double-blind: validators don't know whose work they're assessing, and they don't know who else is validating the same study.

**Validation.** Each validator independently downloads the data, sets up the computational environment, runs the code, and records whether they get the same results. They document their process, time invested, barriers encountered, and confidence level. Results are submitted through a blind commitment protocol — each validator privately seals their findings before anyone else's are visible, then all findings are revealed simultaneously when every validator has committed.

**Author notification.** Before the Harmony Record is published, the original author is notified and given a defined response window. They can provide additional documentation, explain discrepancies, or flag issues the validators may have missed. Their response becomes part of the permanent record.

**Harmony Record.** The final record preserves everything: each validator's independent findings, statistical analysis of agreement, any disagreement details, hardware and software metadata, the author's response, and an overall reproducibility status. Disagreement is preserved, not averaged away.

**Appeal and correction.** If new information emerges — a previously undocumented dependency, a systematic error in the validation process, evidence of validator misconduct — the Harmony Record can be annotated and, if necessary, superseded. The original record remains visible; corrections are appended.

This lifecycle is the thread that connects every layer of the architecture described below.

### The Name

ValiChord combines "Validity" with "Chord." A chord requires multiple notes sounding together — no single note creates harmony. Reproducible validity requires multiple independent validators reaching their conclusions independently — no single researcher validates alone. The musical metaphor is deliberate: ValiChord's outputs are called Harmony Records because they preserve the full texture of agreement and disagreement — not a false unison where the evidence calls for a chord.

### What Makes It Different

Four things distinguish ValiChord from everything else in the reproducibility space.

**1. Front-end and back-end integration**

Every previous approach addresses one end of the research lifecycle. Pre-registration (Registered Reports) prevents gaming at the front end — ensuring the research question is honestly specified. Data repositories address the back end — storing results for potential verification. ValiChord connects both ends into a single system: pre-registered protocols flow into distributed validation, which produces permanent certification records. The research lifecycle is covered from hypothesis to verified result.

This matters because gaming either end is pointless if the other end catches you. A researcher who p-hacks their analysis will be caught by validators. A researcher who changes their data after submission will be caught by the cryptographic audit trail. The system's integrity comes from the integration, not from any single component.

**2. Harmony Records: Preserving Disagreement**

Most systems that aggregate expert opinions produce a single score or verdict. ValiChord deliberately does not. When validators disagree, that disagreement is preserved in the permanent record — visible to journals, funders, and the public for a minimum of 24 months.

This is a philosophical commitment, not a technical limitation. ValiChord takes the embarrassment out of inconclusive and failed results. Every outcome tells us something: a failed reproduction identifies where computation breaks down; a partial reproduction isolates a fragile dependency; a persistent disagreement signals that the field's own standards for what counts as "the same result" are unresolved. The Harmony Record preserves what each outcome tells us — not a verdict that papers over it. Science advances through productive disagreement. A study where six validators reproduce the results and one doesn't may be telling us something important — about hardware differences, software versions, implicit assumptions, or genuine fragility in the findings. Averaging that signal away produces a false sense of certainty. Preserving it produces honest science.

The Harmony Record is ValiChord's canonical output. It contains: the original protocol, each validator's independent results, statistical analysis of agreement and variance, any disagreement details, hardware and software metadata, and an overall reproducibility status that explicitly includes categories like "Indeterminate" and "Persistently Indeterminate" — because sometimes the honest answer is that we don't know, and forcing a binary verdict would be dishonest.

**3. Domestication Resistance: The Brutality Commitments**

The deepest insight in ValiChord's design is this: if the system fails, it won't fail technically. It will fail by being slowly domesticated by institutional pressure until it becomes, in the words of one reviewer, "a well-governed registry of polite uncertainty — a compliance artifact rather than an epistemic one."

Every reproducibility system faces pressure to soften its findings. Institutions want clean metrics. Funders want simple scores. Journals want unambiguous signals. High-status researchers want their work validated, not questioned. The natural trajectory is toward a system that looks rigorous but never actually says anything uncomfortable.

ValiChord resists this through what the project calls Epistemic Integrity Commitments (internally: "Brutality Commitments") — six non-negotiable principles that are designed into the system architecture, not just written into policy documents:

- **Forced disagreement visibility.** Material disagreement between validators cannot be hidden, averaged away, or footnoted. It appears prominently in the Harmony Record for a minimum of 24 months. This is enforced in code, not policy.
- **Institutional attribution.** Validators are identified by institution, creating accountability. If an institution's validators systematically produce soft reviews, the pattern becomes visible.
- **No guaranteed closure.** Some studies will remain "Persistently Indeterminate." The system refuses to force a verdict where the evidence doesn't support one, even if funders or journals want a clean answer.
- **Rapid reputation consequences.** Validators who game the system face immediate and significant reputation loss — not a gentle warning followed by a committee review months later. Holochain's built-in **warrant** mechanism means fraudulent attestations can be cryptographically proven and permanently recorded against a validator's agent identity, discoverable by any peer without central authority. Automatic network-wide blocking of warranted agents is on Holochain's roadmap; the current behaviour makes warrants persistent and queryable, allowing the system to gate further interactions — such as rejecting commitments from warranted validators before the reveal phase.
- **Institutional-level exposure.** Aggregate patterns of validator behaviour are published automatically. An institution can't hide behind individual anonymity.
- **Legible governance.** Every governance decision is logged publicly with its rationale. No decisions happen behind closed doors.

These commitments are designed to survive pressure. The Governance Framework includes specific "red lines" — things that cannot be conceded regardless of who asks — and worked scripts for negotiations with funders and institutions who push for softening. This is not paranoia; it's recognition that every previous reproducibility initiative has been domesticated by exactly these pressures.

**4. Holochain: The Right Architecture for the Right Problem**

ValiChord uses Holochain rather than blockchain, and the reasons matter.

Blockchain's fundamental design — a single global ledger where every node stores everything and consensus requires the entire network — creates three fatal problems for scientific reproducibility: GDPR incompatibility (you can't delete patient data from an immutable ledger), prohibitive cost (mining and consensus mechanisms are expensive), and poor performance (global consensus is too slow for large-dataset validation).

Holochain is architecturally different. It's agent-centric rather than data-centric: each participant maintains their own source chain of actions, and only cryptographic proofs are shared to a distributed hash table (DHT). Arthur Brock, Holochain's co-founder, describes the result as **intrinsic data integrity**: information is self-validating, packaged so that any tampering breaks the packaging and is immediately detectable by other participants. This means:

- **Privacy by architecture.** Sensitive data stays local with the researcher or institution and never enters the shared DHT. Only one-way cryptographic hashes travel to the network. The hash proves the data existed and hasn't been tampered with, but cannot be reversed to recover the data itself. This is data minimisation enforced structurally — not merely a policy commitment. Where erasure rights do apply under GDPR, they can be exercised against the researcher's private DNA without touching the shared attestation record. (Note: GDPR Article 17(3)(d) provides a research exemption — erasure rights can be overridden where compliance would render scientific research objectives impossible or seriously impaired — so most Harmony Records are likely exempt in any case. The architectural separation goes beyond what the law requires.)
- **No mining, no fees, no energy waste.** Holochain doesn't require global consensus or proof-of-work. Validation happens locally; proofs are shared globally. Universities run lightweight nodes at minimal cost.
- **Data sovereignty.** Each researcher controls their own data. No central authority can censor, modify, or gate-keep access. This aligns with scientific values of openness and autonomy.
- **Behavioural pattern analysis.** Because each validator maintains a source chain of all their actions, the system has the foundation to detect collusion patterns, rubber-stamping, and other gaming behaviours — by analysing the patterns in these chains over time. Holochain's `get_agent_activity` function makes individual agents' histories queryable; identifying coordinated patterns across multiple validators requires additional coordinator zome logic, but the underlying data is there by design.

This is not a technology choice made for novelty. It's the specific architecture that solves the specific problems that killed every previous blockchain-based reproducibility attempt. Paul D'Aoust (Documentation and Developer Community Lead, Holochain Foundation) has reviewed ValiChord's proposed architecture and confirmed it is implementable with the current Holochain framework. Arthur Brock (co-founder and architect, Holochain) conducted a solution engineering review in February 2026, confirming the overall direction and providing detailed implementation guidance. Joel Marcey (Tech Director, Rust Foundation) independently reviewed the architecture and confirmed the approach is sound.

**Integration is solved infrastructure.** Holochain released an HTTP Gateway in 2025 that allows external systems — journals, funders, university research offices — to query a running Holochain application via standard HTTP requests, without running a Holochain node. The integration challenge for institutional partners is therefore largely addressed by existing tooling rather than requiring custom development.

**Update strategy.** Within each DNA *(in Holochain, a DNA is a self-contained application — think of it as a separate department, with its own rules, data, and list of who's allowed in)*, Holochain distinguishes integrity zomes *(zomes are the functional units inside a DNA — integrity zomes define the fixed core rules, like a constitution: changing them requires setting up a new network)* from coordinator zomes *(coordinator zomes contain the working logic, like bylaws: these can be updated without disruption)*. For ValiChord, this means disciplinary standards and governance rules can be updated through governance decisions in Phase 2 without forcing every participant to re-install, as long as the core data structures are designed carefully from the start.

**Membrane architecture.** ValiChord is structured as four distinct Holochain applications (DNAs) rather than a single app. Each DNA has its own *membrane* — the access boundary that controls who can join its network and what data is shared within it *(like a door with a specific lock: you can only enter if you hold the right key)*. The Researcher Repository DNA is private to the researcher and their institution; the Validator Workspace DNA is private to each individual validator; the Attestation DNA is shared among credentialed participants; the Governance and Harmony Records DNA is publicly readable. This makes data locality not merely a policy commitment but an architectural guarantee: sensitive data cannot enter the shared network because it lives in a DNA with a membrane that prevents it. The separation is absolute — even where two DNAs share identical code, a **network seed** (a unique property baked into each instance) makes them genuinely different organisms that will only synchronise among their own participants. It also means the system is easier to update over time — each DNA is small and focused, so changes to governance rules in Phase 2 do not require every participant to upgrade the core attestation layer at the same time — participants must eventually upgrade to enter the new shared space, but the transition is not a hard synchronisation requirement.

A further property follows from the source chain structure: researchers can share a chain of **headers** — timestamps, sequence numbers, and entry hashes — to prove that a dataset existed at a particular time and has not been modified, without ever sharing the underlying data. For GDPR-sensitive studies, this means the Attestation layer can carry full chronological accountability while the data itself remains under the researcher's control.

ValiChord's architectural direction has independent academic support. Beyvers et al. (2026, *PLOS Computational Biology*) propose "FAIR and federated Data Ecosystems" (FFDEs) — layered architectures combining peer-to-peer networking, federated governance, and domain sovereignty for research data management. Their four-plane architecture (governance, data, service, application) maps directly onto ValiChord's eight-layer design: where they solve data *sharing* through federated infrastructure, ValiChord solves data *validation* through the same principles. They reach the same conclusion independently: "the technology already exists... the challenge isn't technical innovation but organizational coordination." Their work validates ValiChord's core thesis that decentralised, governance-aware architectures are the emerging consensus for research infrastructure — and that the missing piece is not better technology but better evidence about what validation actually involves.

### An Important Scope Boundary

ValiChord validates computation, not data provenance. Validators re-run code on provided data and verify whether the claimed results reproduce. If the raw data itself is fabricated — but internally consistent — validators would successfully reproduce the results and the study could receive a high confidence rating for science built on false foundations. ValiChord's cryptographic audit trail proves that data wasn't changed after submission; it cannot prove the data was truthful in the first place.

This is not a design flaw — it is a boundary. No computational validation system can verify that a researcher actually observed what they claim to have observed. ValiChord catches coding errors, analytical mistakes, undocumented dependencies, and post-hoc manipulation. It does not catch well-executed fraud at the data generation stage. The documents, the Harmony Records, and any public communications must be honest about this boundary.

---

## The Eight-Layer Architecture

**Note on structure:** The eight layers below are a conceptual framework — they describe what ValiChord does in functional terms. The actual engineering structure is the four-DNA membrane architecture described in the Holochain section above (Researcher Repository, Validator Workspace, Attestation, Governance & Harmony Records). Readers familiar with Holochain will recognise that these functional layers map across those four DNAs rather than sitting in a single application. The layer framework is retained here because it communicates the system's responsibilities clearly to non-technical audiences; it is not an implementation plan.

ValiChord's responsibilities are organised into eight functional areas, each addressing a specific aspect of the reproducibility infrastructure. They interact but can be activated progressively — the system doesn't need to be built all at once.

Think of them as concentric rings of responsibility rather than a stack of steps. At the centre, **Layer 0** ensures every validator works from provably identical materials — no layer above it can function without this guarantee. **Layer 1** brings research into the system with honest commitments made upfront, before results are known. **Layer 2** is where independent validation actually happens: validators reproduce the work in isolation, and the engine detects any attempt to game the process. **Layer 3** sets the rules — and is designed to resist the institutional pressures that have corrupted every previous reproducibility initiative. **Layer 4** remembers everything: a permanent, tamper-evident record of every action, auditable by anyone. **Layer 5** translates the work of the inner layers into the trust signals the outside world consumes — Harmony Records, badges, reports. **Layer 6** answers the question "why would anyone validate?" with real incentives, career credit, and reputation that compounds over time. And **Layers 7 and 8** connect ValiChord to the institutions, journals, and funders that need its outputs, without requiring them to replace their existing systems. Each layer can be built and proven independently; none of them is sufficient alone.

### Layer 0: Data & Integrity Foundation

*Everything rests on this.*

ValiChord's core claim is that multiple independent validators assessed the same study. For that claim to be verifiable — not just asserted — every validator must provably have worked from identical materials.

ValiChord solves this using content-addressed verification: when data is submitted, each participant's node generates a cryptographic fingerprint of every file. Research files — data, code, protocol documents — are fingerprinted using SHA-256, the standard used by academic repositories and broadly supported by verification tools. Holochain's own internal addressing uses BLAKE2b for its attestation records. These are separate but complementary layers: the SHA-256 fingerprint identifies the research materials; Holochain's addressing identifies the validation actions performed on them. Change a single bit of the original data and the fingerprint changes completely — so any tampering is immediately detectable. Anyone can verify, at any time, that their copy matches every other copy. The data itself can be stored on established academic repositories (Zenodo, Figshare, institutional repositories) or cloud storage — what matters is the fingerprint, not where the files live. Redundant storage across multiple providers ensures the materials outlive any single institution — a study validated in 2027 can still be checked in 2035.

### Layer 1: Intake & Pre-Registration

*Where research enters the system.*

This layer brings research into ValiChord in a structured, machine-readable format. For studies that include pre-registration, analysis plans are committed in advance with explicit hypotheses and pre-specified outcome measures. This is the front-end protection that complements back-end validation.

Critically, ValiChord includes a structured deviation typology. Real research requires flexibility — ethics boards require changes, planned analyses don't converge, unforeseen circumstances arise. ValiChord doesn't forbid deviations; it requires them to be declared, categorised by type, and assessed for their impact on the study's conclusions. A deviation that changes a plot library is different from a deviation that changes the statistical model. The system captures that distinction.

ValiChord can also accept protocols from existing systems — OSF pre-registrations, clinical trial registries, Registered Reports — adding its validation layer to work that's already been pre-registered elsewhere.

### Layer 2: Validation Engine

*The core of ValiChord.*

This is where independent validation actually happens. The engine handles validator selection (matching expertise to protocol requirements while enforcing diversity and screening for conflicts of interest), task assignment, execution tracking, and result collection.

Validator diversity isn't a policy preference — it's an architectural requirement. For a validation to be credible, validators must be genuinely independent: different institutions, different geographies, no co-authorship networks. Three validators from the same lab network doesn't constitute independent verification, regardless of their individual competence. This creates structural demand for distributed capability — ValiChord needs qualified validators across regions and institutions to produce epistemically valid results. At the same time, participation in validation work provides under-resourced labs with funded opportunities to build institutional credibility, develop methodological skills, and establish track records of demonstrated competence. This is genuinely mutual: ValiChord needs their independence, they need the opportunity, and both sides are stronger for it.

The blind commitment protocol is central: each validator privately seals their findings before seeing anyone else's, then all findings are revealed simultaneously once every validator has committed. This prevents the last validator from adjusting their results to match the majority — a well-known attack vector in any system where independent assessors can see each other's results before submitting. In plain terms: validators seal their findings in a tamper-proof private record first; only then does a joint session open where all findings become visible at once. This is the standard cryptographic pattern known as commit-reveal, implemented using Holochain's native private entries and countersigning mechanism.

When validators disagree significantly, the system escalates: minor disagreement is documented, moderate disagreement triggers additional validators, and substantial disagreement goes to expert panel review. Disagreement is never hidden.

Gaming-detection mechanisms identify manipulation — statistical outlier detection, collusion pattern analysis, social distance mapping (co-authorship graphs), access pattern monitoring, and time analysis for unrealistically fast or slow validations.

### Layer 3: Governance & Policy

*Who decides the rules — and what stops them from being captured.*

This is the layer most likely to fail. Every previous reproducibility initiative was undermined not by bad technology but by social dynamics — committees that softened standards under institutional pressure, governance bodies captured by the people they were supposed to oversee, rules quietly adjusted to keep powerful players comfortable.

ValiChord's governance includes discipline-specific standards committees, a Research Integrity Office, and appeals processes. All are protected by structural safeguards: enforced term limits and rotating membership prevent power accumulation; all decisions, rationales, and vote records are public by default, making quiet capture visible before it becomes structural; and funding concentration tripwires trigger automatic review if any single institution gains disproportionate influence across funding, validators, and governance seats simultaneously.

The core philosophy is **detection over prevention.** You can't stop a committee member from having a bias. You can make it extremely difficult to act on that bias invisibly. The governance framework — detailed in its own companion document — is designed so that capture is always more visible, more costly, and more self-defeating than honest participation.

### Layer 4: Audit & Provenance

*The memory of the system.*

Every action in ValiChord is recorded in tamper-evident, append-only logs — protocol registration, data uploads, validator assignments, attestation submissions, governance decisions, reputation changes. The complete provenance chain from hypothesis to certification is reconstructable at any time.

This serves two functions: accountability (any decision can be audited) and trust (external parties can independently verify the entire validation history of any study without trusting ValiChord itself).

### Layer 5: Output & Certification

*What the world sees.*

This layer produces Harmony Records, reproducibility badges (domain-specific, not gamified — they cannot be reduced to a single numerical score), and narrative reports tailored for different audiences (researchers, funders, journals, the public). These are the trust signals that external systems consume.

Integration examples: a journal queries ValiChord's API during manuscript review and sees "7 validators, 6 Success, 1 Partial, High confidence" with full disagreement details. A funder checks a PI's validation portfolio. An institution reviews its aggregate reproducibility metrics.

### Layer 6: Incentive & Reputation

*Why anyone participates.*

This layer tackles the "why would anyone validate?" problem through multi-dimensional reputation scoring, professional compensation, and formal academic credit using the CRediT (Contributor Roles Taxonomy) system. Validators receive recognition that counts toward their careers — not just a thank-you note.

The incentive design explicitly avoids perverse dynamics: no bonuses for speed (prevents rushing), no simple quantity metrics (prevents rubber-stamping), and high-quality disagreement is rewarded rather than penalised. The reputation algorithm is published openly and auditable.

The incentive layer must also address sustained participation, not just initial recruitment. Validators are working academics — postdocs face grant deadlines, faculty have teaching loads, research software engineers have institutional obligations. Peer review already suffers from reviewer fatigue, and ValiChord validation is more demanding than reading a paper. The design accounts for this in three ways: validators choose their own workload (no minimum commitment, tasks accepted not assigned); the pool is large enough that no individual is essential (at Phase 3 scale, 1,000+ validators means each might validate a handful of studies per year, not dozens); and validation work generates tangible career outputs (publications, CRediT credit, demonstrated methodological expertise) that compound over time rather than producing only one-off payments. Whether this is sufficient is an open question — Phase 0's exit survey captures early signals on sustainable participation, and Phase 1's larger pool provides the first real evidence on retention.

### Layer 7: Integration & Interface

*How ValiChord connects to the ecosystem.*

APIs for journal submission systems, funder dashboards, institutional HR systems, and existing platforms (OSF, GitHub, clinical trial registries). ValiChord is designed to be infrastructure that others plug into, not a silo that requires replacing existing systems.

### Layer 8: Access & Presentation

*How humans experience the system.*

Dashboards and portals for researchers (submit protocols, track validations), validators (receive assignments, submit results), funders (portfolio-level visibility), journals (query validation status), and the public (transparency portal).

### What Users Actually Experience

Eight layers sounds complicated. It isn't — for the people using it.

A researcher submitting a study for validation sees a form. They upload their data, describe their methods, specify their claims, and click submit. They don't know about content-addressed storage, cryptographic hashing, or DHT propagation. They uploaded a file and filled in some fields. Layer 0 handled the rest.

A validator receives an assignment. They see a clear brief: here's the study, here's the data, here's what they claimed, here's what you need to check. They download the data, run the code, write up what happened, and submit their assessment. They don't need to understand blind commitment protocols, collusion detection, or reputation scoring. They did a piece of professional work and got paid for it. Layers 2, 4, and 6 handled the rest.

A journal editor queries a DOI. They see a Harmony Record: seven validators, six successful reproductions, one partial, high confidence, one disagreement documented. They don't know about provenance graphs, governance hardening, or anti-gaming mechanisms. They got a clear, honest answer about whether the study reproduces. Layers 3, 5, and 7 handled the rest.

A researcher submits a study that doesn't pass triage. Instead of a bare rejection, they receive constructive feedback: what's missing, why it matters, and how to fix it. They address the issues and resubmit. The system didn't just reject their study — it made their research more reproducible.

Better still — a researcher runs *ValiChord at Home* (working name) before they ever submit. The tool sits on their own machine, scans their repository, and tells them where they stand — privately, at their own pace, with no one watching. Not every researcher who produces important science thinks in tidy file structures. Some of the most significant breakthroughs come from conceptual thinkers who are not naturally systematic in how they organise their work. *ValiChord at Home* bridges that gap: it takes brilliant ideas expressed in messy repositories and shows the researcher exactly how to make them reproducible, without requiring them to become a different kind of thinker. The full feedback pipeline — from pre-submission self-assessment through post-submission diagnostics to assisted correction — is detailed in the *ValiChord Researcher Support* companion document.

The sophistication is in the plumbing, not the taps. Every design decision about the user experience follows one principle: the complexity exists to protect the integrity of the system, not to be visible to the people using it. If a user needs to understand Holochain to submit a study, the UX has failed. If a validator needs to understand collusion-detection algorithms to do their job, the UX has failed. If a funder needs to read this document to interpret a Harmony Record, the UX has failed.

The eight layers are there so that the people who use ValiChord don't have to think about the eight layers.

---

## The Staged Approach

### Philosophy

ValiChord is designed as a complete system but activated in phases. This is evidence-led design, not indecision. Each phase generates the findings that shape the next. The project adapts based on what each phase discovers.

This matters because the most common failure mode for ambitious infrastructure projects is building everything before understanding what the system actually needs to accommodate. ValiChord discovers its operating conditions first.

### The Critical Unknown

Every layer of ValiChord depends on evidence that doesn't yet exist: how long validation takes, what makes it difficult, what it costs, and what validators need.

No one has measured this. Registered Reports assume validators will exist for back-end verification. Data sharing mandates assume someone will check the data. Journal policies assume reviewers will attempt reproduction. Funder requirements assume third-party verification is economically feasible.

None of these assumptions have empirical support. Phase 0 generates the evidence that turns assumptions into design constraints.

### The Phases

**Phase 0: Workload Discovery** — A focused pilot measuring how long validation actually takes, what makes it difficult, and what it costs. This generates the empirical evidence needed to design infrastructure that works in reality, not just in theory. Phase 0 also produces ValiChord's first public-facing product: a lightweight readiness checklist called *ValiChord at Home* (working name) — the version researchers use in their own space, on their own terms, before engaging with the formal system. Phase 0 is detailed in its own companion document.

**Phase 1: Core Infrastructure** — Designed around Phase 0 findings. Builds the Holochain-based distributed infrastructure, validator identity system, study submission and matching, validation execution and recording. Beta testing with validators and real studies.

**Phase 2: Integration & Adoption** — Designed around Phase 1 operational evidence. Adds journal submission system integrations, funder reporting dashboards, institutional analytics, validation standards and protocols. Scales to broader adoption.

**Phase 3: Scale & Sustainability** — Designed around Phase 2 adoption patterns. Scales globally, develops financial sustainability model, builds professional validator community, pursues policy impact. Global scaling is not simply expansion — it is essential to epistemic credibility. A validation pool dominated by well-resourced Western institutions is insufficiently independent to produce trustworthy results. Phase 3 actively develops distributed capability, where external funding (from bodies like Wellcome Trust or UKRI) catalyses participation from institutions in under-resourced research economies. This inverts the traditional aid dynamic: a lab that can reliably reproduce malaria research isn't receiving charity — it's providing a service the network cannot function without. Initial investment bootstraps capability; operational capacity earns through validation work; accumulated earnings can fund capability development elsewhere. A single well-structured grant generates ongoing, measurable, verified impact — each attestation on the DHT is auditable proof of both capability development and productive contribution.

**Beyond Phase 3:** ValiChord starts with computational reproducibility because it is the most tractable problem — validators download data, run code, and compare outputs from their own computers. The cost is modest, the timescales are hours to days, and disagreement between validators is relatively unambiguous.

But the core architecture — independent validators follow documented procedures, report results under blind conditions, and those results are permanently recorded with disagreement preserved — is not limited to computation. The same pattern applies to experimental laboratory science, where independent labs follow published protocols and report whether they achieve the same results. This is harder: it costs more (reagents, equipment, lab time), takes longer (weeks or months rather than hours), and produces more ambiguous disagreement (differing results may reflect protocol gaps, equipment differences, or genuine sensitivity to unstated conditions rather than outright failure). Projects like the Reproducibility Project: Cancer Biology have shown both the immense value and the immense difficulty of experimental replication at scale.

ValiChord's infrastructure would serve experimental reproducibility better than current ad hoc approaches. Blind assignment prevents deference to prestigious labs. Commit-reveal prevents coordination between replicators. Harmony Records preserve the full texture of agreement and disagreement rather than reducing complex experimental outcomes to pass/fail. Gaming detection identifies labs that systematically produce lenient replications. The "Persistently Indeterminate" category — designed for honest uncertainty — is arguably more valuable for experimental work, where ambiguity is the norm rather than the exception.

Experimental reproducibility is the longer-term aim. Computational reproducibility comes first because it proves the system works on the problem where success and failure are clearest. Once the architecture, governance, and validator community are established computationally, extending to experimental validation is an expansion of scope, not a redesign of the system.

Beyond science entirely, the same infrastructure could extend to any field where claims need independent verification: policy modelling, economic forecasting, regulatory submissions, software verification. These are possibilities to note, not promises to make — ValiChord must prove itself in its home domain first.

Each phase generates the evidence that shapes the next. The staged approach means ~£150K FEC (Phase 0) ensures that £1.9M of infrastructure investment is designed around empirical evidence rather than untested assumptions.

### Economic Model

ValiChord cannot specify precise costs or revenue at this stage because the foundational data doesn't exist — Phase 0 generates it. But the structural logic of who pays for what and when can be described honestly.

**Cost drivers.** ValiChord's operating costs have three components: validator compensation (the largest), compute infrastructure (variable by study complexity), and platform operations (engineering, governance, coordination). Validator compensation depends entirely on Phase 0 evidence — until someone measures how long validation takes, any per-study cost estimate is guesswork. Compute costs range from negligible (a script that runs on a laptop) to substantial (a climate model requiring HPC access). Platform operations scale with volume but have a fixed base.

**Revenue sources by phase.** Phase 0 and Phase 1 are grant-funded — this is research infrastructure development, not a commercial product. Phase 2 introduces the integration layer where funding flows begin to diversify: funders who mandate validation can fund it (validation as a condition of the grant, with costs built into the grant budget); journals that require validation can fund it (as part of publication processing, analogous to how journals fund peer review infrastructure); institutions that want portfolio-level reproducibility analytics can fund access to dashboards and aggregate data. Phase 3 targets a mixed model where grant funding covers capability development and equity access, while operational costs are substantially covered by institutional and funder contributions.

**The sustainability logic.** ValiChord does not need to become self-sustaining through market revenue. Research infrastructure rarely does — ORCID, Crossref, PubMed, and arXiv all operate through institutional membership, funder support, and grant funding in various combinations. The question is not "can ValiChord turn a profit?" but "can ValiChord demonstrate enough value that institutions and funders are willing to pay for its continued operation?" That is a question Phase 1 and Phase 2 answer through adoption evidence.

**What Phase 0 provides.** The single most important economic output of Phase 0 is the cost-per-validation estimate across the difficulty spectrum. If validation of a typical study takes 8 hours and costs £500 in validator time plus minimal compute, ValiChord is economically viable at modest scale. If validation routinely takes 40+ hours and requires expensive infrastructure, the economic model changes fundamentally — either toward selective validation of high-impact studies, or toward funder-subsidised validation of everything. Phase 0 provides the empirical foundation for this decision.

**What is not yet specified.** Pricing structures, volume projections, and detailed cost modelling depend on evidence that doesn't exist yet. Building financial projections before measuring the underlying costs would be exactly the kind of assumption-driven design that ValiChord's phased approach is designed to avoid.

---

## Why Would Researchers Submit?

The most common question about any validation system is: why would researchers voluntarily submit their work for independent scrutiny?

Some will submit because they want to. Researchers working in contested fields, where methods are routinely challenged and results disputed, gain something publication alone cannot provide: independent verification. "Three independent validators reproduced my results" is a stronger defence than "two peer reviewers read my paper and thought it looked fine."

Some will submit because it advantages them. When a funder reviews two grant applications and one carries independent computational verification, the verified applicant is more credible. Early submitters build a track record of openness — a researcher with ten validated studies, eight Gold and two Indeterminate, demonstrates both rigour and honesty. The Indeterminate results show transparent science, not failure.

Some will submit because institutions expect it. Researchers didn't voluntarily start sharing data — funders required it. They didn't voluntarily pre-register — journals incentivised it through Registered Reports. Every piece of research infrastructure that succeeded at scale did so because institutions made it expected, then normal, then required. ValiChord's Phase 2 integration strategy — journal partnerships, funder dashboards, institutional analytics — is designed to create exactly this trajectory.

And some will submit knowing their work might not reproduce — because that is also a contribution. In the current system, a failed replication is a career embarrassment. In ValiChord, a study that doesn't reproduce generates a Harmony Record documenting *why* — version dependencies, hardware sensitivities, undocumented steps, genuine fragility in the findings. That is valuable scientific knowledge. The researcher who submitted didn't fail; they helped the field understand the boundaries of their own work. This only holds if ValiChord's culture, governance, and public communications consistently treat non-reproduction as information rather than indictment — which is why the Harmony Record preserves context, not just verdicts.

The honest answer is that voluntary submission will drive early adoption, but institutional integration will drive scale. Phase 0 does not depend on solving the adoption question — it requires only 8-10 study authors willing to have their published work validated. Phase 1 is where adoption strategy becomes critical, informed by Phase 0 evidence about what validation actually involves.

---

## Open Design Questions

The following fourteen questions do not have complete answers yet. They are documented here because they are the questions that funders, ethics boards, journal editors, and institutional partners will ask first — and because honest acknowledgment of open problems is more credible than silence.

Each question has precedents in existing reproducibility initiatives, a likely ValiChord approach, and a phase that resolves it. The full treatment — precedents, reasoning, and resolution timelines — is in the companion document *ValiChord Open Design Questions*.

1. Do original authors need to consent to validation?
2. Who pays for compute?
3. What happens after a negative Harmony Record?
4. What is the original author's right of reply?
5. How are Phase 0 studies selected?
6. How is restricted and sensitive research handled?
7. What if Holochain stalls or fails?
8. How are validators trained and calibrated?
9. How is a flawed Harmony Record corrected?
10. How are records preserved long-term?
11. How is validator identity verified at scale?
12. What about submission-side cherry-picking?
13. How is cross-border data jurisdiction managed?
14. Who pays for persistently indeterminate validation outcomes?

*This is the most critical unresolved economic question in ValiChord's design and receives full treatment — including precedents, current thinking, and the re-submission pathway — in the companion document* ValiChord Open Design Questions.

---

## Where We Are Now

### What Exists

**A validated concept.** The architecture has been designed, reviewed, and confirmed as technically feasible by Paul D'Aoust (Documentation and Developer Community Lead, Holochain Foundation) and Shin Sakamoto, an independent Holochain application developer. Arthur Brock (co-founder and architect, Holochain) conducted a solution engineering review in February 2026, providing detailed implementation guidance including the multi-DNA membrane architecture. Joel Marcey (Tech Director, Rust Foundation) independently reviewed the Technical Reference and MVP Specification and confirmed the approach is sound. The individual technical components — content-addressed storage, blind commitment via private source chain entries and countersigned reveal (commit-reveal), distributed hash tables, collusion detection — are all established, proven patterns. What's novel is their combination for this specific purpose.

**Illustrative architecture and a Rust scaffold.** The Technical Reference contains detailed pseudocode sketches — data structures, system flows, and component interactions — developed across twelve months of architectural design. A Rust scaffold translating those sketches into the actual implementation language has been produced and, following Arthur Brock's solution engineering review in February 2026, substantially rebuilt. Brock identified that the original scaffold had been structured around the eight-layer conceptual framework rather than Holochain's four-DNA membrane architecture — entry types were not annotated correctly as Holochain entries, and one DNA had been invented (an "Identity" DNA) while another was missing (the Validator Workspace DNA, which Brock described as essential). The scaffold has been reorganised accordingly. Neither version has been compiled or tested; both are design intent documents. The corrected scaffold, and what the review process revealed about how to maintain architectural coherence as documents grow in complexity, is an honest part of this project's status.

**A governance framework.** The social layer — addressing institutional capture, validator gaming, domestication pressure, and the perverse incentives that killed previous attempts — has been designed and stress-tested through extensive adversarial analysis. This is detailed in its own companion document.

**Institutional conversations.** Discussions have been initiated with both Cardiff University and Swansea University regarding academic partnership and institutional hosting. The Holochain Foundation has confirmed technical feasibility. Potential partnerships with UKRN, Centre for Open Science, and the Software Sustainability Institute have been identified.

### What Doesn't Exist Yet

**No working software.** The Rust scaffold and pseudocode sketches in the Technical Reference are design intent documents, not functional code. Nothing has been compiled, tested, or deployed. They are the starting point for an engineering conversation, not the output of one.

**No confirmed team.** The lead engineer role is unfilled. Shin Sakamoto, an independent Holochain application developer, has been identified as a target candidate but has not been formally recruited. The academic PI for Phase 0 is to be determined. The project currently consists of one person — the author of this document.

**No confirmed partnerships.** University discussions (Cardiff and Swansea) are at an early stage. No letters of support have been secured. No institutional commitments exist beyond the Holochain Foundation's confirmation of technical feasibility.

**No empirical evidence.** The critical assumption — that validators will participate — is untested. Phase 0 exists specifically to test it.

This honesty matters. ValiChord's strength is in the quality of its thinking — about the problem, the architecture, the governance, and the social dynamics that defeated previous attempts. It is a thoroughly designed concept, not an operational system. The next step is to test its most critical assumption.

---

## The Competitive Landscape

ValiChord is complementary to, not competitive with, existing reproducibility initiatives:

**Registered Reports** pre-register hypotheses and methods. ValiChord adds back-end computational validation. Together, they cover the full lifecycle.

**OSF / Center for Open Science** stores data and manages projects. ValiChord validates what's stored. OSF is a potential integration partner, not a competitor.

**CodeCheck / ReproZip** provide technical reproducibility tooling. ValiChord provides the coordination, governance, and certification layer that these tools operate within.

**Automated CI/CD approaches** (Docker, containerised pipelines, GitHub Actions) can verify that code *runs* and produces *outputs*. They cannot assess whether those outputs *make sense*. Automated testing cannot flag physically impossible intermediate values, notice that a data preprocessing step is undocumented, identify that code ran but produced garbage because of an environment difference, or judge whether partial reproduction counts as success. The gap between "code executed without errors" and "results are scientifically reproducible" is precisely where human judgement is required. ValiChord uses human validators not as a limitation to be automated away, but because the assessment being made — does this study's computation actually reproduce its claimed findings? — requires the kind of contextual reasoning that automation cannot provide. Automated tools are valuable complements (and may handle triage and pre-screening in later phases), but they cannot replace the core validation function.

**UK Reproducibility Network** drives culture change and training. ValiChord provides the infrastructure that culture change needs in order to become operational.

**Journal data mandates** create policy requirements. ValiChord provides the missing mechanism for verifying compliance.

The specific gap ValiChord fills: if journals mandate validation, if funders require third-party verification, if repositories need computational checks — **will qualified researchers actually do this work, and at what cost?** No existing initiative answers this question. Phase 0 does.

---

## Why This Matters

The reproducibility crisis is not an abstract academic concern. It wastes hundreds of billions in research funding. It delays treatments that could save lives. It undermines public trust in science at a moment when that trust is essential.

Every previous attempt to address it has failed — not because the technology was wrong, but because the social dynamics were ignored. ValiChord is designed from the ground up to address both the technical and the social dimensions of the problem, across the entire research lifecycle, with explicit resistance to the institutional pressures that domesticated every previous attempt.

The technology is proven. The architecture is validated. The governance is designed. The critical unknown — will validators participate? — is testable.

The next step is to test it.

---

**Companion Documents:**
- *ValiChord Technical Reference* — Architecture sketches for engineering discussion
- *ValiChord Governance Framework* — Tiered governance from pilot to mature system
- *ValiChord Open Design Questions* — Precedents, likely approaches, and resolution phases
- *ValiChord Phase 0 Proposal* — Workload Discovery Pilot (~£150K FEC, 12 months)
- *ValiChord Researcher Support* — Feedback pipeline and pre-validation tools

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**

