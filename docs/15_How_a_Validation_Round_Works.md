<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="500px" alt="Valichord Logo">
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

ValiChord does not store any of this. It computes a SHA-256 cryptographic fingerprint of her data (carried as a 39-byte Holochain hash). That fingerprint, and only that fingerprint, will travel to the shared network. Sarah's proprietary data stays exactly where it is.

She submits a Validation Request to the shared network, attaching the fingerprint, specifying her discipline (Computational Biology), and indicating the number of validators required (she chooses three; each study sets its own number, which must not be below the network's minimum). The request appears on the shared network — visible to credentialed validators in her field.

There is one more step that happens at submission, invisible to the validators: Sarah **locks her result**. ValiChord generates a random nonce and computes a cryptographic hash of her structured result metrics — the exact numbers from her paper. Only that hash travels to the shared network, recorded as a `ResearcherResultCommitment`. The metrics and nonce stay sealed in Sarah's private workspace. The validators cannot see what Sarah found. Sarah cannot change what she claimed to have found. The envelope is sealed. (On a production network this lock is compulsory: no validator can seal a finding until the researcher's commitment is on the network.)

<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Validator%20round%201.jpeg" width="800px" alt="Validator Round 1">
</div>
---

## Step 2: Validators Claim the Study

Nobody assigns validators. Three credentialed validators browse the queue of open requests in their discipline and each **claims** a place on Sarah's study. Once three places are taken, the study is full and no one else can claim it. A validator who shares an institution with Sarah is refused by the network (a conflict-of-interest rule every peer checks). If a validator drops out, their place can be released and claimed by someone else. (Drawing validators at random from a pool is a possible future design, not how it works today.)

Each validator holds a joining credential — a cryptographic proof, signed by an authorised issuer, that they are allowed on the validation network. Without this credential, they cannot join the validation network at all. The credential is checked mathematically, not administratively, and every peer on the network checks it, not just the validator's own node.

The validators are:
- **Dr. James Okoye** — research software engineer, University of Edinburgh
- **Dr. Fatima Al-Rashid** — computational biologist, ETH Zürich
- **Marcus Webb** — senior research associate, Wellcome Sanger Institute

None of them know what the others will find. That is the point.

Each validator records a ValidationTask in their own private workspace. They download Sarah's code and data from the public archive, set up the computational environment as documented, and begin work.

<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Validator%20round%202.jpeg" width="800px" alt="Validator Round 2">
</div>

---

## Step 3: The Commit Phase

This is where ValiChord differs from any previous validation system.

James finishes his reproduction attempt first. He ran the code, compared the outputs against Sarah's published figures, and reached a conclusion. Before he can submit anything publicly, ValiChord asks him to **seal** his finding in his private workspace.

His assessment — *Reproduced, high confidence, 14 hours* — is written to his local machine as a `ValidatorPrivateAttestation`. It is cryptographically locked the moment it is created. He cannot change it. He cannot delete it. And crucially, **nobody else can see it**.

The moment James seals his assessment, something happens automatically: his workspace calls across to the shared network, writing a `CommitmentAnchor` — a public, zero-content proof that James has committed. The network can see that James has acted. It cannot see what he found.

Fatima completes her work two days later and seals her assessment. Another CommitmentAnchor appears on the network.

Marcus finishes on day eight. A third CommitmentAnchor is written.

All three validators have committed. None of them knows what the others found.

<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Validator%20Round%203.jpeg" width="800px" alt="Validator Round 3">
</div>

---

## Step 4: The Reveal Opens

When the third CommitmentAnchor is written, the same call (made from Marcus's node, as the last to commit) sees that every place has committed and writes a `PhaseMarker` to the shared network: **Reveal Open**. After that, no new commitments are accepted for this study.

James, Fatima, and Marcus may also get a quick notification, but that is only a courtesy: the PhaseMarker on the network is what counts, and each validator's software checks the network for it. This matters: if reveal timing depended on messages arriving, a fast or slow connection could change who knew first. Because the record on the network is the authority, the reveal window is the same for everyone, regardless of network speed or time zone.

<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Validator%20Round%204.jpeg" width="800px" alt="Validator Round 4">
</div>

---

## Step 5: The Reveal

James submits his public `ValidationAttestation`, together with the private nonce from his sealed envelope. The network recomputes the hash and refuses the attestation unless it matches his CommitmentAnchor exactly. The study's terms — how many validators it asked for, and when the request was made — are stamped into the attestation from Sarah's original request, and every peer checks them. It is permanent the moment it is written — immutable, tamper-proof, published to the shared network. He cannot revise it.

Fatima submits hers. Marcus submits his.

Once the reveal is open, Sarah can reveal too. She opens her private workspace, retrieves the nonce and metrics she locked at submission, and calls `reveal_researcher_result` (only the researcher who submitted the study may do this). ValiChord verifies the hash on the shared network — confirming that the metrics she is now publishing match exactly what she committed to before any validator started work — and writes her `ResearcherReveal` to the DHT.

The three validator attestations and Sarah's verified result are now all public, permanent, and independently verifiable by anyone on the network. Neither Sarah nor the validators could have adjusted their numbers after seeing anyone else's. The comparison is genuine.

<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Validator%20Round%205.jpeg" width="800px" alt="Validator Round 5">
</div>


---

## Step 6: The Harmony Record

When the last validator (here, Marcus) submits, his node automatically asks ValiChord's Governance layer to finish the round. It checks that all three attestations are present, retrieves them, works out the majority outcome and the level of agreement among the validators, and assembles a **Harmony Record**.

In this case:
- James found: *Reproduced*
- Fatima found: *Reproduced*
- Marcus found: *Partially Reproduced* (most figures matched; one fell outside the stated tolerance)

The agreement level is not chosen by anyone: it is calculated from the three findings. Two full reproductions and one partial reproduction give *Within Tolerance*. (Three full reproductions would have given *Exact Match*.)

The Harmony Record captures all of this:

```
Outcome:              Reproduced
Agreement Level:      Within Tolerance
Validators:           3 of 3 requested
Duration:             16 hours (the longest single validator's reported time)
Discipline:           Computational Biology
Attestation evidence: each validator's signed attestation
Badge:                Bronze Reproducible
```

The record carries each validator's signed attestation, and every peer that stores it checks those signatures, the request, the outcome, the agreement level and the number of validators against what was asked for. A record with fewer validators than requested is only accepted after the round's timeout. The record is written to the public DHT. It is permanent. Nobody can alter it — not Sarah, not the validators, not ValiChord's operators. It exists now as an immutable fact about Sarah's study.

Because three validators reached at least *Directional Match* agreement, a **Bronze Reproducible** badge is automatically issued and linked to the record. (The badge thresholds — 3, 5 and 7 validators for Bronze, Silver and Gold — are placeholders, to be calibrated with real data.)

If a validator had gone silent instead, the round would not hang for ever: once the round's timeout has passed and no one still holds a place, anyone can close it with the attestations that are present (`force_finalize_round`), and the record then reads, for example, "2 of 3 requested".

---

## Step 7: The Public Record

Sarah's Harmony Record is now publicly readable by anyone — a journal editor, a funder, another researcher, a science journalist. The reader needs no Holochain node of their own and no institutional membership: a standard web request to any node that offers a public read endpoint (the demo host does) returns the record.

The record does not say Sarah's science is correct. It says three independent credentialed validators, working without knowledge of each other's findings, each reproduced her computational results. That is a different and more specific claim — and it is one that can now be made with cryptographic certainty.

<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Validator%20Round%206.jpeg" width="800px" alt="Validator Round 6">
</div>

---

## What If the Validators Disagreed?

Not every round ends in consensus. Suppose Marcus had found something different — his environment produced results that diverged from Sarah's published figures. He seals that finding honestly during the commit phase. He cannot change it after the reveal opens.

The Harmony Record would then reflect:
- James: *Reproduced*
- Fatima: *Reproduced*
- Marcus: *Failed to Reproduce*

The Agreement Level would be `DirectionalMatch` — two out of three reproduced. (Under the current placeholder thresholds, a three-validator Directional Match still earns a Bronze badge; those thresholds are to be calibrated with real data.) The divergence is recorded in full. The record does not hide Marcus's finding or average it away. A reader can see exactly what happened: two validators reproduced, one did not, and here is the full picture.

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

### Cryptographic Guarantees

The commit-reveal protocol rests on three specific cryptographic choices:

**Hash function — SHA-256.** Every commitment hash is `SHA-256(serialised_data || nonce)`. SHA-256 is a one-way function: given only the commitment hash and nonce, it is computationally infeasible to recover or alter the underlying assessment. The 256-bit output is verified byte-for-byte at reveal time.

**Nonce — 32 random bytes from Holochain's host function.** Each commit generates a fresh nonce via `random_bytes(32)` — Holochain's cryptographically secure host-level random source. The nonce is never published; it travels only inside the private `ValidatorPrivateAttestation` entry and is submitted by the validator at reveal time. Without the nonce, an observer who intercepts the commitment hash cannot brute-force the small set of possible verdicts (Reproduced / PartiallyReproduced / FailedToReproduce / UnableToAssess).

**Serialisation — MessagePack named-field encoding (`rmp_serde::to_vec_named`).** The same function is used at commit time (to hash the attestation before sealing) and at reveal time (to verify the hash against the public attestation). Because the encoding is deterministic and field-order-stable, the byte string produced at reveal is identical to the byte string produced at commit — a property that does not hold for JSON serialisation with arbitrary key ordering. Both `seal_private_attestation` (DNA 2) and `submit_attestation` (DNA 3) call `ValidationAttestation::commitment_msgpack_bytes()`, the same shared function in `valichord_shared_types`, guaranteeing byte-for-byte consistency across DNA boundaries.

The full commitment formula for a validator is:

```
commitment_hash = SHA-256( rmp_serde::to_vec_named(ValidationAttestation) || nonce_32_bytes )
```

The full commitment formula for the researcher is:

```
commitment_hash = SHA-256( rmp_serde::to_vec_named(Vec<MetricResult>) || nonce_32_bytes )
```

Both hashes are written to the shared DHT before any reveal begins. At reveal time, `submit_attestation` and `reveal_researcher_result` recompute the hash from the submitted data and reject the reveal if the hashes do not match exactly.

---

## The Timeline

| Day | Event |
|---|---|
| Day 1 | Sarah submits Validation Request |
| Day 1–2 | Validators claim the study, tasks recorded |
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
