# Demo 2 — The Validator Challenge (Puzzle Game)
### Technical Explanation for Script / Social Media Adaptation

---

## What this demo is

A standalone browser game that lets one person — or ideally three people sharing the same computer — experience what it feels like to be three independent validators reaching a blind consensus. Each person takes a turn at the keyboard, picks their answer in their tab, then steps aside so the next person can't see what they chose. No server-side state. No login. No shared infrastructure beyond localStorage. And at the end, the panel's majority verdict is sealed on a real Holochain network.

The page is at the same Codespace URL as Demo 1, on the path `/puzzle.html`.

---

## The core idea

The biggest challenge in peer review and scientific validation is **independence**. Validators must not know what other validators think before they commit to their own verdict. If they can see each other's answers first, the review is compromised — the second and third validators are not independently verifying, they are agreeing with the first.

ValiChord solves this with a cryptographic commit-reveal protocol (explained in Demo 1). This puzzle game makes that abstract mechanism visible and tangible. The viewer is not just watching a protocol — they are the protocol.

---

## The setup

Open `puzzle.html` in **three browser tabs**. Each tab is a validator. They share the same game state via `localStorage` — a browser storage mechanism that is shared across tabs on the same origin (same URL). There is no server involved in coordinating the three tabs at all.

Each tab gets a unique identity (`MY_ID`) stored in `sessionStorage` — a storage mechanism that is isolated per tab, so each tab has a different ID even though they share the same localStorage.

---

## The puzzle

Each game presents one of three research-themed maths questions. The puzzles are deliberately about statistical reasoning — the kinds of calculations a validator would actually do when checking a paper:

**Puzzle 1 — Checking a reported mean**
A researcher reports an average reaction time of 245 ms across 8 participants. Total recorded time: 1,960 ms. Does the arithmetic check out? (1,960 ÷ 8 = 245. Yes.)

**Puzzle 2 — Tracking a sample through filtering**
A dataset starts with 500 samples. 20% removed as outliers, then 25% of the remainder removed as duplicates. How many remain? (500 × 0.80 = 400; 400 × 0.75 = 300.)

**Puzzle 3 — False positive rate**
A paper runs 5 independent statistical tests each at p < 0.05. How many false positives would you expect by chance? (5 × 0.05 = 0.25 — not zero, and not one, but a quarter of one on average.)

Each answer option maps to a verdict: Reproduced, Partially Reproduced, or Failed to Reproduce. The viewer does not see which answer maps to which verdict until the reveal.

---

## The researcher's answer

When the game loads, a "researcher's answer" is randomly assigned — it is one of the three options, chosen at random regardless of which one is correct. This is important: the researcher may be right or wrong. The validators' job is to find out independently.

This random assignment is stored in `localStorage` so all three tabs see the same researcher answer — they are all looking at the same study.

---

## Phase 1 — Sealing (blind commitment)

Each tab shows the puzzle and the three answer options. The viewer picks one answer in each tab, independently, without seeing what the other tabs picked. When they click an answer:

- Their choice is appended to the `seals` array in `localStorage` as `{ id: MY_ID, answer: 'A' }` (or B or C).
- The option buttons are disabled in that tab — the answer is locked.
- A 400ms polling loop in every tab detects the change in `localStorage` and updates the validator status panel across all three tabs in real time.

The validator status panel shows three rows — Validator 1, Validator 2, Validator 3 — with a badge showing "waiting…", "sealed", or "you — sealed" depending on each tab's state. Validators are assigned slots by order of sealing: the first tab to pick gets slot 1, the second gets slot 2, and so on.

At this point no tab can see what any other tab picked. The answers are in `localStorage` but the reveal section is hidden. This is the commit phase: all verdicts are fixed before any are shown.

---

## Phase 2 — Reveal

When all three tabs have sealed (i.e. `seals.length === 3`), the phase in `localStorage` changes from `'sealing'` to `'revealing'`. The 400ms poll detects this in all three tabs simultaneously and the reveal section appears.

The reveal shows:
- The **researcher's answer** — the randomly assigned option with its full text.
- Each **validator's answer** — tab by tab, showing which option they chose and the corresponding verdict label (Reproduced / Partially Reproduced / Failed to Reproduce).
- The **correct answer** — with the explanation. This lets the viewer see whether the validators were right, wrong, or split.
- A **"Seal panel verdict on Holochain →"** button.

The panel verdict is computed by majority: whichever verdict appears most often among the three seals wins. If all three disagree, whichever verdict has the most votes wins (ties broken by the JavaScript sort, which is deterministic on the same array order).

---

## Phase 3 — Holochain round

One tab clicks "Seal panel verdict on Holochain →". This triggers a 5-step Holochain commit-reveal sequence using the panel's majority verdict. The steps are an abbreviated version of the 12-step flow in Demo 1:

**Step 1 — Submit validation request**
A request is created on the Attestation DHT with a fresh random `request_ref` (so the demo can be run multiple times without collision).

**Step 2 — Claim study and create task**
The validator claims the study and creates a private task on the Validator Workspace DNA.

**Step 3 — Seal verdict (Commit phase)**
The panel's majority verdict is written as a `PrivateAttestation` to the Validator Workspace DNA. The `post_commit` hook writes a `CommitmentAnchor` (the hash) to the shared Attestation DHT.

**Step 4 — Reveal verdict**
The full attestation is submitted to the shared DHT. The network verifies the hash matches the commitment. Verdict accepted.

**Step 5 — HarmonyRecord**
The final permanent record is written to the Governance DHT and displayed: outcome, agreement level, ActionHash.

After the Holochain round completes, the ActionHash is written back to `localStorage` and the phase is set to `'done'`. All three tabs detect this via the polling loop and a "New puzzle" button appears.

---

## What this demo proves

**The independence problem is real and visible.** When you pick your answer in Tab 1, you genuinely do not know what Tab 2 or Tab 3 will pick. That is not just a UI trick — the architecture enforces it. There is no server that could leak answers. The reveal is purely time-gated by the local polling loop.

**Consensus is not the point.** All three tabs might pick different answers. The system does not force agreement — it records what each validator found, independently, and then honestly reports whether they agreed or not. A split result is not a failure; it is a signal that the study is ambiguous and may warrant further scrutiny.

**The protocol connects to a real blockchain.** The final step is not cosmetic. A real Holochain conductor is running, real zome calls are being made, and the resulting HarmonyRecord ActionHash is a real cryptographic identifier on a real distributed ledger.

**No central authority.** No database, no login, no server-side session. The coordination between three tabs happens entirely in the browser, in localStorage, in real time.

---

## What this demo is not claiming

- The "three validators" are ideally three different people sharing one computer, each taking a turn. In a real deployment they would be on three different machines, with no shared localStorage.
- The puzzle answers are not real research findings. They are designed maths questions that map to verdict categories for demo purposes.
- The "researcher's answer" is random, not from a real paper. In production, the researcher does not submit an answer — they submit a deposit, and the validators reproduce the results independently.
- Phase 0: one conductor, one machine. Real inter-validator agreement requires multiple conductors, which is the next phase of the ValiChord project.

---

## Why this matters for the bigger picture

The hardest unsolved problem in scientific peer review is not catching fraud after the fact. It is making the review process **structurally honest** — building a system where it is architecturally impossible for a reviewer to change their mind after seeing what others said, or to be pressured by journal editors, or to game the outcome.

This little three-tab puzzle game is, in miniature, that system. The commit happens before the reveal. The reveal is verified against the commit. The record is permanent. That is the core of ValiChord — and everything else (the deposit analyser, the trust scores, the AI validators, the governance layer) is scaffolding around that one inviolable fact.

---

## Technology stack

| Component | Technology |
|---|---|
| Game state coordination | Browser localStorage (shared across tabs, same origin) |
| Per-tab identity | Browser sessionStorage (isolated per tab) |
| Cross-tab polling | setInterval at 400ms — lightweight, no WebSockets needed |
| Blockchain layer | Holochain 0.6.x, 4-DNA architecture |
| Holochain client | @holochain/client 0.20.2 (ES module) |
| Serialisation | MessagePack (@msgpack/msgpack 3.1.3) |
| UI | Vanilla HTML/CSS/JS, no framework |
| Runtime environment | GitHub Codespace (Linux) |
