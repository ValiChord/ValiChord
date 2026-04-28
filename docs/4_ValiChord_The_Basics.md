<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord: The Basics

*What it is, what it does, and where it applies — no technical background required*

---

## The Problem

When a researcher publishes a study, the results are reviewed by peers. Those reviewers read the paper and assess whether the methods are sound and the conclusions are logical. What they almost never do is sit down with the researcher's code and data and actually run it themselves.

That gap — between "the logic seems right" and "an independent party reproduced the result" — is where a great deal of science quietly breaks down. Estimates suggest that roughly 70% of researchers have failed to reproduce another scientist's published results. The cost of this, in wasted follow-on research, misled clinical decisions, and abandoned replication attempts, is estimated at around $200 billion a year.

The problem is not that scientists are dishonest. It is that there is no infrastructure for systematic, independent verification — and no neutral record of what was found when someone tried.

ValiChord builds that infrastructure.

---

## What ValiChord Does

ValiChord is a system that lets independent validators attempt to reproduce a computational study, and then creates a permanent public record of what they found — including disagreement.

The key word is *independent*. ValiChord is specifically designed to prevent the two most common ways that verification systems fail:

**Gaming:** a validator who knows what result they are expected to find is not truly independent. ValiChord uses a *commit-reveal protocol* — described below — to ensure that every validator locks in their finding before seeing anyone else's, and before seeing what the researcher claimed.

**Institutional capture:** organisations that fund, conduct, or depend on research have an interest in favourable verification outcomes. ValiChord's governance framework is designed to resist the slow institutional pressure that has undermined every previous attempt at systematic reproducibility checking.

---

## The Sealed Envelope Protocol

The core of ValiChord can be understood without any technical background.

Imagine three independent reviewers, each given the same study to examine. The traditional approach: they compare notes, discuss, and produce a joint verdict. The problem is obvious — whoever speaks first anchors the conversation. The last person to commit has seen everyone else's position and can adjust accordingly.

ValiChord's approach: each reviewer writes their verdict on a piece of paper, seals it in an envelope, and hands it to a trusted neutral party. Once all envelopes are sealed, they are opened simultaneously. Nobody could see anyone else's verdict before committing to their own.

ValiChord implements this electronically with a cryptographic guarantee: it is mathematically impossible to alter a sealed verdict after the reveal begins, and mathematically impossible for one validator to see another's sealed verdict before committing their own. The envelope cannot be opened, replaced, or backdated. This guarantee holds even if a validator, the researcher, or ValiChord's own operators wanted to cheat.

The same guarantee applies to the researcher. When a study is submitted, the researcher locks their claimed result metrics with a cryptographic seal. The validators can confirm the seal exists before accepting the work — but they cannot see the actual values. The researcher is bound to their claim from the moment of submission. They cannot revise their numbers after seeing what the validators found.

This is the core anti-gaming guarantee. Neither side can move the goalposts once the envelopes are sealed.

---

## What a Harmony Record Is

Once all validators have revealed their findings — and the researcher has revealed their claimed results — ValiChord assembles a **Harmony Record**.

A Harmony Record is a permanent, publicly readable summary of what happened:

- What was the outcome? (*Reproduced, Partially Reproduced, Failed to Reproduce*)
- How closely did the validators agree with each other?
- How many validators participated, and what were their credentials?
- Did the researcher's revealed values match what they committed to at submission?

The record is stored on a distributed network — not on a single server controlled by ValiChord or anyone else. Nobody can alter or delete it after it is written, including ValiChord's own operators. It is readable by anyone with a web browser, without an account or any technical infrastructure.

Critically, the Harmony Record preserves disagreement. If two validators reproduced the results and one did not, the record says exactly that. It does not average the findings away or produce a single binary verdict that discards the minority view. The full picture is preserved.

---

## What "Reproduced" Means — and Doesn't Mean

ValiChord answers a precise question: *did independent validators, working from the same code and data, arrive at the same result as the researcher?*

It does not answer whether the result is *correct*. A study can be perfectly reproducible and scientifically wrong. A study can be correct but impossible to reproduce from the materials the researcher provided. These are different questions.

ValiChord answers only the reproducibility question. Whether the science is good, whether the conclusions are valid, whether the methodology is appropriate — those are scientific questions that remain for scientists to judge. The Harmony Record does not judge the research. It verifies whether the computational claim holds up to independent scrutiny.

This precision matters. A claim that says "three credentialed independent validators reproduced this result" is a specific, verifiable statement. It is more meaningful than "the paper passed peer review" — and more honest than "the result is correct."

---

## Who the Validators Are

Validators are credentialed researchers — computational scientists, research software engineers, data analysts — who have been issued a cryptographic credential by an authorised body (a journal, a funder, a professional body, or ValiChord in its Phase 0 pilot).

The credential is not a username and password. It is a cryptographic proof, mathematically signed, that this person is a verified researcher. Without it, a node cannot join the validation network at all. This eliminates anonymous participation and makes it structurally impossible for someone to multiply their influence by creating extra identities — each identity requires a separate institutional credential.

---

## The Fields Where ValiChord Applies

Computation is the first and most tractable instance of ValiChord's pattern, because computational claims are the most directly verifiable: given the same code and data, a validator can check whether they get the same numbers.

Within computation, every scientific discipline is in scope:

- **Computational biology and genomics** — protein folding models, gene expression analyses, drug-target interaction studies
- **Climate and environmental science** — emissions models, biodiversity analyses, ecological projections
- **Economics and social science** — statistical analyses, policy impact models, public health studies
- **Psychology and neuroscience** — behavioural experiment analyses, imaging pipelines, reproducibility of statistical claims
- **Physics and engineering** — simulation outputs, materials science computations, hardware performance claims
- **Machine learning and AI research** — model performance claims on stated benchmarks, reproducibility of training pipelines

Any field where the core claim takes the form "we ran this computation on this data and got this result" is in scope for ValiChord.

Beyond computational science, the same structural pattern — seal a commitment before seeing others' findings, reveal simultaneously, record the full picture including disagreement — applies wherever independent verification of a consequential claim carries weight:

**Clinical trial pre-registration.** Outcome-switching — pre-specifying one primary endpoint and quietly changing it after seeing the data — is identical in structure to the problem ValiChord solves for research results. A commitment on the trial protocol, sealed before enrolment begins on a distributed network, would make protocol modification detectable in a way that existing centralised registries cannot guarantee.

**Carbon credit verification.** Sequestration claims are computational: a model applied to satellite and sensor data produces a figure. Independent validators can reproduce that computation. The Harmony Record preserves disagreement — including the case where independent validators produce materially different sequestration estimates from the same stated inputs.

**Government policy modelling.** Policy decisions in infrastructure, public health, and economic planning are often based on computational models that are never independently reproduced. The UK Government's Aqua Book already recommends independent model assurance; ValiChord provides the infrastructure to make that assurance verifiable rather than procedural.

**AI model auditing.** Whether a model actually achieves its claimed accuracy on the stated test set is a computational question. Independent validators can reproduce the evaluation. A Harmony Record shows whether auditors agreed — and where they did not.

**Audit and assurance.** The commit-reveal protocol applies wherever independent parties need to demonstrate they formed their view before seeing management's preferred narrative. The Harmony Record transforms an audit from a signed opinion letter into a verifiable claim about what independent parties found when working from the same evidence.

ValiChord's Phase 0 focus is computational science. The architecture is designed from the ground up to be domain-agnostic, so that extensions to new fields are configuration choices rather than architectural rebuilds.

---

## What ValiChord Is Not

**It is not a blockchain.** ValiChord is built on Holochain — an agent-centric distributed network where each participant maintains their own data locally, and only cryptographic proofs are shared across the network. There are no tokens, no miners, no global consensus mechanism, and no cryptocurrency of any kind. Researcher data never leaves the researcher's own environment. Validator findings never leave the validator's own environment. Only sealed commitments and revealed records travel to the shared network.

**It is not a peer review replacement.** Peer review assesses whether science is worth publishing. ValiChord assesses whether a computational result can be independently reproduced. These are complementary functions. ValiChord sits alongside peer review, not in place of it.

**It is not a correctness checker.** The Harmony Record does not say a study is right. It says independent validators, working from the stated materials, got the same answer. That is a precise and useful claim. It is not a claim about truth.

---

## Further Reading

| Document | What it covers |
| :--- | :--- |
| [A Validation Round, Step by Step](15_How_a_Validation_Round_Works.md) | Follows a single study through the full process, from submission to Harmony Record |
| [Vision & Architecture](1_ValiChord_Vision&Architecture.md) | The full case for why ValiChord matters and how it is designed |
| [Governance Framework](2_ValiChord_Governance_Framework.md) | How ValiChord resists institutional capture and validator gaming |
| [Harmony Records](10_Harmony_Records.md) | What the permanent record contains and why it matters |
| [Why Holochain?](11_Why_Holochain?.md) | Plain English explanation of the network architecture and why it was chosen |
| [Open Design Questions](6_ValiChord_Open_Design_Questions.md) | Sixteen unresolved questions ValiChord acknowledges openly |
