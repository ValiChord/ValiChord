<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Valichord%20logo-standard%20v2-1.5x.jpeg" width="500px" alt="Valichord Logo">
</div>

# A Validation Round: From Submission to Harmony Record

*Following a single computational study through the ValiChord process*

---

## The Study

Dr. Sarah Chen has spent eighteen months developing a computational model of protein folding behaviour under oxidative stress. Her paper has been accepted for publication. The code is on GitHub. The data is archived. The reviewers were satisfied.

But Sarah knows that "reviewers were satisfied" and "the results can be independently reproduced" are two different things. Peer review checked the logic of her methodology. Nobody has sat down with her code and data and actually run it.

She submits her study to ValiChord.

---

## Step 1: Submission

Sarah opens her Researcher Repository — her private, local ValiChord workspace. Nothing she stores here will ever leave her machine. She registers her study, uploads her pre-registered protocol (which is immediately locked and immutable — she cannot change it after this point), and takes a verified snapshot of her dataset.

ValiChord does not store any of this. It computes a SHA-256 cryptographic fingerprint — a 39-byte hash — of her data. That fingerprint, and only that fingerprint, will travel to the shared network. Sarah's proprietary data stays exactly where it is.

She submits a Validation Request to the shared network, attaching the fingerprint, specifying her discipline (Computational Biology), and indicating the number of validators required. The request appears on the shared network — visible to credentialed validators in her field.

<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Validator%20round%201.jpeg" width="800px" alt="Validator Round 1">
</div>
---

## Step 2: Validator Assignment

Three credentialed validators are assigned to Sarah's study. Each holds an institutional credential — a cryptographic proof, signed by an authorised issuer, that they are a verified computational researcher. Without this credential, they cannot join the validation network at all. The credential is checked mathematically, not administratively.

The validators are:
- **Dr. James Okoye** — research software engineer, University of Edinburgh
- **Dr. Fatima Al-Rashid** — computational biologist, ETH Zürich
- **Marcus Webb** — senior research associate, Wellcome Sanger Institute

None of them know what the others will find. That is the point.

Each validator receives a ValidationTask in their own private workspace. They download Sarah's code and data from the public archive, set up the computational environment as documented, and begin work.

<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Validator%20round%202.jpeg" width="800px" alt="Validator Round 2">
</div>

---

## Step 3: The Commit Phase

This is where ValiChord differs from any previous validation system.

James finishes his reproduction attempt first. He ran the code, compared the outputs against Sarah's published figures, and reached a conclusion. Before he can submit anything publicly, ValiChord asks him to **seal** his finding in his private workspace.

His assessment — *Reproduced, high confidence, 14 hours* — is written to his local machine as a `ValidatorPrivateAttestation`. It is cryptographically locked the moment it is created. He cannot change it. He cannot delete it. And crucially, **nobody else can see it**.

The moment James seals his assessment, something happens automatically: his workspace fires a signal to the shared network, writing a `CommitmentAnchor` — a public, zero-content proof that James has committed. The network can see that James has acted. It cannot see what he found.

Fatima completes her work two days later and seals her assessment. Another CommitmentAnchor appears on the network.

Marcus finishes on day six. A third CommitmentAnchor is written.

All three validators have committed. None of them knows what the others found.

<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Validator%20Round%203.jpeg" width="800px" alt="Validator Round 3">
</div>

---

## Step 4: The Reveal Opens

The moment the third CommitmentAnchor appears, ValiChord writes a `PhaseMarker` to the shared network: **Reveal Open**.

James, Fatima, and Marcus each discover this by checking the network — not by receiving a message. This matters: if reveal timing were signal-driven, a fast internet connection could give one validator a head start on seeing others' results before submitting their own. The poll-driven design means the reveal window opens simultaneously for everyone, regardless of network speed or time zone.

<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Validator%20Round%204.jpeg" width="800px" alt="Validator Round 4">
</div>

---

## Step 5: The Reveal

James submits his public `ValidationAttestation`. It is permanent the moment it is written — immutable, tamper-proof, recorded on the shared distributed network. He cannot revise it.

Fatima submits hers. Marcus submits his.

The three attestations are now public, permanent, and independently verifiable by anyone on the network.

<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Validator%20Round%205.jpeg" width="800px" alt="Validator Round 5">
</div>


---

## Step 6: The Harmony Record

ValiChord's Governance layer detects that all three attestations are present. It retrieves them, calculates the consensus outcome and the level of agreement among the validators, and assembles a **Harmony Record**.

In this case:
- James found: *Reproduced, Within Tolerance*
- Fatima found: *Reproduced, Exact Match*
- Marcus found: *Reproduced, Within Tolerance*

The Harmony Record captures all of this:

```
Outcome:         Reproduced
Agreement Level: Within Tolerance
Validators:      3
Duration:        collective 38 hours
Discipline:      Computational Biology
Badge:           Bronze Reproducible
```

The record is written to the public DHT. It is permanent. Nobody can alter it — not Sarah, not the validators, not ValiChord's operators. It exists now as an immutable fact about Sarah's study.

Because three validators all independently reproduced the results, a **Bronze Reproducible** badge is automatically issued and linked to the record.

---

## Step 7: The Public Record

Sarah's Harmony Record is now publicly readable by anyone — a journal editor, a funder, another researcher, a science journalist. No Holochain node required. No institutional membership. A standard web request returns the record.

The record does not say Sarah's science is correct. It says three independent credentialed validators, working without knowledge of each other's findings, each reproduced her computational results. That is a different and more specific claim — and it is one that can now be made with cryptographic certainty.

<div align="center">
  <img src="https://github.com/topeuph-ai/ValiChord/blob/main/Validator%20Round%206.jpeg" width="800px" alt="Validator Round 6">
</div>

---

## What If the Validators Disagreed?

Not every round ends in consensus. Suppose Marcus had found something different — his environment produced results that diverged from Sarah's published figures. He seals that finding honestly during the commit phase. He cannot change it after the reveal opens.

The Harmony Record would then reflect:
- James: *Reproduced*
- Fatima: *Reproduced*
- Marcus: *Divergent*

The Agreement Level would be `DirectionalMatch` — two out of three agreed. The divergence is recorded in full. The record does not hide Marcus's finding or average it away. A reader can see exactly what happened: two validators reproduced, one did not, and here is the full picture.

This is what "harmony from dissonance" means. The record captures the truth of what the validators found — including the disagreement — rather than forcing a binary verdict that discards information.

---

## What the Process Guarantees

By the time a Harmony Record exists, the following are mathematically true:

- Each validator committed their finding before seeing anyone else's
- No validator could change their finding after the reveal window opened
- The validators' credentials were cryptographically verified — they are who they claim to be
- The Harmony Record was assembled automatically by the network, not by a human administrator
- The record cannot be altered or deleted by anyone

What the process does not guarantee: that the validators were right. That Sarah's methodology is sound. That the study is significant. Those are scientific questions, not verification questions. ValiChord answers the verification question precisely and leaves the scientific questions to scientists.

---

## The Timeline

| Day | Event |
|---|---|
| Day 1 | Sarah submits Validation Request |
| Day 1–2 | Validators assigned, tasks received |
| Days 2–8 | Validators work independently |
| Day 4 | James seals his assessment (CommitmentAnchor 1 written) |
| Day 6 | Fatima seals her assessment (CommitmentAnchor 2 written) |
| Day 8 | Marcus seals his assessment (CommitmentAnchor 3 written) |
| Day 8 | PhaseMarker(RevealOpen) written — reveal window opens |
| Days 8–9 | All three validators submit public attestations |
| Day 9 | Harmony Record assembled and written to public DHT |
| Day 9 | Bronze Reproducible badge issued |
| Permanent | Record publicly readable — no infrastructure required |

---

*For the technical implementation of this process, see [Technical Architecture](7_ValiChord_4-DNA_architecture_technical.md).*

*For the governance principles that make this process trustworthy, see [Governance Framework](2_ValiChord_Governance_Framework.md).*

*For a plain English explanation of the four-DNA structure, see [4-DNA Architecture — Plain English](7a_ValiChord_4-DNA_architecture_nontechnical.md).*
