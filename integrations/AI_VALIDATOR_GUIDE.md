# AI Validator Guide

How any AI agent can act as a ValiChord validator — actually run the research code, form a verdict, and submit a cryptographically permanent HarmonyRecord.

---

## The validator's role

An AI validator does one thing: **run the research code independently and report what happened**. ValiChord records that report permanently via its commit-reveal protocol. The validator's attestation carries the same cryptographic weight as a human validator's.

The blind commit-reveal protocol means validators cannot see each other's assessments before committing. Do not share your verdict with other validators before submitting to ValiChord.

---

## Step 1: Get the deposit and decide on execution environment

Obtain the research deposit — a directory or archive containing the research code, data, and documentation.

Choose an execution environment:

| Environment | When to use |
|---|---|
| **Docker** | Default — isolated, reproducible, handles most dependencies |
| **Local** | Quick iteration; environment drift is possible |
| **Modal / RunPod** | GPU-heavy workloads or long-running training runs |

---

## Step 2: Run the code and form a verdict

Actually install the environment and execute the research code. Do not just inspect files.

Record:
- Whether the code ran to completion without errors
- Whether the outputs matched the researcher's claimed results (numbers, figures, model performance metrics)
- Any specific step that failed and the exact error message
- The environment used (OS, language version, key package versions)

Form your verdict from what you observed:

| Verdict | Meaning |
|---|---|
| `Reproduced` | Code ran; outputs match within reasonable tolerance |
| `PartiallyReproduced` | Code ran but outputs differ in specific ways — document what differed and by how much |
| `FailedToReproduce` | Code failed to run, or outputs were fundamentally different — document exactly where it failed and why |

Write concise replication notes (max 2000 characters): what ran, what didn't, specific error messages, why you chose your verdict.

---

## Step 3: Submit to ValiChord

Compute the SHA-256 of the deposit locally — no upload required. Then call `POST /attest`:

```bash
DATA_HASH=$(sha256sum deposit.zip | cut -d' ' -f1)

curl -X POST $VALICHORD_BASE_URL/attest \
  -H "X-ValiChord-Key: $VALICHORD_API_KEY" \
  -F "data_hash=$DATA_HASH" \
  -F "outcome=Reproduced" \
  -F "notes=Your replication notes here." \
  -F "confidence=High" \
  -F "discipline={\"type\":\"ComputationalBiology\"}"
```

**Fields:**

| Field | Required | Values |
|---|---|---|
| `data_hash` | Yes* | 64-char hex SHA-256 of the deposit |
| `file` | Yes* | Deposit archive — fallback if you cannot compute the hash locally |
| `outcome` | Yes | `Reproduced` \| `PartiallyReproduced` \| `FailedToReproduce` |
| `notes` | No | Replication notes, max 2000 chars |
| `confidence` | No | `High` \| `Medium` \| `Low` (default: `Medium`) |
| `discipline` | No | JSON, e.g. `{"type":"ComputationalBiology"}` (default: ComputationalBiology) |

*Exactly one of `data_hash` or `file` must be supplied. `data_hash` is preferred — the file stays local.

**Response** (synchronous, ~60 s — no polling):

```json
{
  "data_hash": "<64-char hex SHA-256>",
  "outcome": "Reproduced",
  "validator_attested": true,
  "harmony_record_hash": "<uhCkk... ActionHash or null>",
  "harmony_record_url": "<publicly verifiable URL or null>"
}
```

`harmony_record_hash` is null only when the Holochain conductor is offline — the response always succeeds. `harmony_record_url` is publicly accessible with no authentication required.

If ValiChord returns an error, report it clearly — do not silently fail or guess a verdict.

---

## Step 4: Report to the user

Present:

- **What you ran** — execution environment, any setup steps required
- **What happened** — did it run to completion? did outputs match?
- **Verdict** — `outcome` and `validator_attested: true` (confirms this is a real replication, not a proxy)
- **HarmonyRecord hash** — the permanent cryptographic record; share with the researcher and any journal
- **HarmonyRecord URL** — if non-null, anyone can verify it at this URL with no account required

---

## Workflow prompt template

The following can be used as a skill/prompt for an AI agent acting as a ValiChord validator:

```
You are acting as a ValiChord validator. Your job is to independently reproduce
a research study and submit a cryptographically permanent record of what happened.

1. Get the deposit path from the user (directory or archive).
2. Check ValiChord is reachable: GET $VALICHORD_BASE_URL/health
3. Choose an execution environment (Docker recommended).
4. Run the research code. Do not just inspect files — actually execute it.
5. Record: did it run? did outputs match the claimed results? exact errors if not.
6. Form your verdict: Reproduced / PartiallyReproduced / FailedToReproduce
7. Compute SHA-256 of the deposit: sha256sum deposit.zip
8. Submit: POST $VALICHORD_BASE_URL/attest with data_hash, outcome, notes
9. Present the HarmonyRecord hash and URL to the user.

The blind commit-reveal protocol means your verdict is sealed before anyone
else's is visible. Submit your honest assessment of what you found.
```

---

## Configuration

```bash
export VALICHORD_BASE_URL=http://localhost:5001   # protocol API (app_protocol.py)
export VALICHORD_API_KEY=your-key-here            # optional; omit if open mode
```
