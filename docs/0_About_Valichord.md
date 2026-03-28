
<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>


# ValiChord: A Validation Layer for Scientific Research

**Created by:** Ceri John
**Origin date:** 2025
**Repository:** https://github.com/topeuph-ai/ValiChord

---

## What ValiChord is

ValiChord is a distributed system for scientific reproducibility verification. It answers a question that science has struggled with for decades: *how do you prove that a research finding was independently verified, without any single party being able to manipulate the outcome?*

The answer is a cryptographic commit-reveal protocol running on a peer-to-peer network. Validators seal their findings before seeing anyone else's assessment — then reveal simultaneously. No validator can adjust their verdict after seeing others'. No central authority mediates the process. The outcome is a **HarmonyRecord**: a tamper-evident entry on a distributed ledger that permanently records the consensus verdict on a piece of research.

---

## The core concepts

These terms and their definitions were originated by Ceri John as part of the ValiChord design:

**HarmonyRecord** — the final consensus entry written to the Governance DHT after all validators have revealed their sealed attestations. It contains the reproducibility outcome, the data hash of the deposit, and a summary of validator findings. Once written, it cannot be altered or deleted.

**Validation Round** — a structured, time-bounded process in which multiple validators independently assess a research deposit, seal their findings cryptographically, and then reveal in a single phase. The round is complete only when all required validators have participated.

**Attestation** — a single validator's sealed finding, containing their reproducibility verdict (`Reproduced`, `PartiallyReproduced`, or `FailedToReproduce`), their confidence level, and their supporting evidence. Sealed before any reveal; cryptographically bound to the validator's identity.

**Research Deposit** — a ZIP archive submitted by a researcher containing the code, data, and documentation required to reproduce their findings. ValiChord treats this as the unit of verification.

**Validator** — any agent — human or AI — holding a valid membrane proof credential on the ValiChord network. Validators are neutral: the protocol makes no distinction between a human scientist and an AI research agent.

---

## Why it matters

The reproducibility crisis in science is well-documented. Studies fail to replicate. Data is lost. Code doesn't run. Methods are underspecified. Existing solutions (peer review, data availability statements) are centralised, manually administered, and gameable.

ValiChord is designed to be none of those things. The verification record exists on a distributed network — no journal, institution, or company controls it. The commit-reveal protocol prevents collusion between validators. The cryptographic outcome can be verified by anyone, without trusting any intermediary.

The intended use: a researcher publishes a study. Multiple validators — some human, some AI — independently attempt to reproduce the findings. ValiChord records the consensus outcome as a HarmonyRecord. The researcher receives a permanent, publicly verifiable link. Journals, funders, and institutions can query it independently.

---

## The architecture

ValiChord uses four Holochain DNAs operating in concert:

1. **Researcher Repository DNA** — stores research deposits and manages deposit metadata
2. **Attestation DNA** — manages the shared validation request pool and the commit-reveal protocol
3. **Validator Workspace DNA** — each validator's private workspace for sealing attestations before reveal
4. **Governance DNA** — writes the final HarmonyRecord after consensus and maintains reproducibility badges

Each DNA has a distinct sovereignty boundary. The Governance DNA cannot be written to by any single party — it only accepts a HarmonyRecord when the Attestation DNA confirms all validators have revealed.

---

## Current state (March 2026)

ValiChord is operational. The full stack — Holochain conductor, Node.js bridge, Flask REST API, and HTTP Gateway — runs end-to-end in a GitHub Codespace. A complete validation round (submit → commit → reveal → HarmonyRecord) takes under 60 seconds. The HTTP Gateway exposes HarmonyRecord lookup at a public URL that anyone can query without running a node.

The REST API (`POST /validate`, `GET /result/<job_id>`) provides an integration surface for any external system. The first integration is with [Feynman](https://github.com/getcompanion-ai/feynman), an open-source AI research agent, which uses ValiChord as its verification layer when running replication studies. Feynman PR #13 (merged into Feynman 0.2.15) and PR #14 implement this integration.

A second integration is in design with Nondominium, Sensorica's open-value accounting framework, to record validated contributions to open science projects.

---

## What ValiChord is not

ValiChord does not perform the replication itself. It records the outcome of a replication that has already been performed — by a human, by an AI agent, or by an automated pipeline. ValiChord is the integrity layer, not the analysis layer.

ValiChord does not replace peer review. It augments it: peer review assesses scientific merit; ValiChord verifies computational reproducibility. They operate at different levels of the research lifecycle.

---

## Origin and authorship

ValiChord was conceived and built by Ceri John. The original motivation was the observation that reproducibility verification in science suffers from the same structural problem as any centralised trust system: whoever controls the record controls the truth. The application of Holochain's agent-centric architecture to this problem — specifically the use of a private Validator Workspace DNA to enforce blind attestation — is the core design insight of ValiChord.

The system name, the concept of a HarmonyRecord as a consensus reproducibility verdict, and the four-DNA sovereignty model are original to this project.

---

*This document was written by Ceri John in March 2026 to establish a clear, authoritative record of ValiChord's authorship, design concepts, and current state.*
