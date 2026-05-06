# ValiChord — Integration Guide

ValiChord accepts research deposits (ZIP files containing code, data, and
documentation), analyses them for reproducibility issues, and returns a
structured verdict — including a **HarmonyRecord**, a cryptographically
permanent entry on a Holochain distributed network.

Any tool that can make HTTP requests can integrate with ValiChord.

---

## Quick start (3 steps)

```bash
# 1. Submit a deposit
curl -X POST https://your-valichord-instance/validate \
  -H "X-ValiChord-Key: your-api-key" \
  -F "file=@my-study.zip" \
  | jq .job_id

# 2. Poll until done
curl https://your-valichord-instance/result/<job_id> | jq .status

# 3. Read the verdict
curl https://your-valichord-instance/result/<job_id> \
  | jq '.harmony_record_draft | {outcome, validator_attested, harmony_record_hash}'
```

The interactive API docs (Swagger UI) are at `GET /docs`.
The machine-readable OpenAPI spec is at `GET /openapi.yaml`.

---

## Base URL

| Environment | URL |
|-------------|-----|
| Local / dev | `http://localhost:5000` |
| Codespace demo (sleeps when inactive) | `https://improved-space-couscous-5gjwpp546jrg27p5q-5000.app.github.dev` |

---

## Authentication

Authentication is **off by default** (open access for local/dev deployments).

When the server operator has configured API keys, include yours in every
write request:

```
X-ValiChord-Key: your-api-key
```

Read endpoints (`GET /result`, `GET /health`, `GET /download`) are always
open. Write endpoints (`POST /validate`, `POST /upload-chunk`) require a key
when authentication is enabled.

---

## Two modes of use

### Researcher mode — deposit submission

You are submitting your own study for pre-validation. ValiChord checks the
deposit structure and returns a provisional verdict. No one has run your code
yet — `validator_attested` will be `false`.

```bash
curl -X POST /validate \
  -H "X-ValiChord-Key: your-key" \
  -F "file=@my-study.zip"
```

### Validator mode — replication attestation

You have actually run the research code (e.g. using Feynman's `/replicate`)
and are submitting your genuine verdict. Include `validator_outcome` and
`validator_notes`. The HarmonyRecord will reflect what you found when you ran
it — `validator_attested` will be `true`.

```bash
curl -X POST /validate \
  -H "X-ValiChord-Key: your-key" \
  -F "file=@study-deposit.zip" \
  -F "validator_outcome=PartiallyReproduced" \
  -F "validator_notes=Code ran to completion. Figure 3 values differ by 8% from paper (seed not fixed)."
```

Valid `validator_outcome` values: `Reproduced`, `PartiallyReproduced`,
`FailedToReproduce`.

---

## Polling for results

Poll `GET /result/<job_id>` every 10 seconds. Typical analysis takes 1–5
minutes; allow up to 25 minutes for large deposits.

```
GET /result/<job_id>
```

Possible responses:

```json
{ "status": "running" }

{ "status": "error", "error": "Processing timed out after 20 minutes." }

{
  "status": "done",
  "findings": [...],
  "harmony_record_draft": {
    "outcome": { "type": "PartiallyReproduced", "content": { "details": "..." } },
    "validator_attested": true,
    "data_hash": "e3b0c44...",
    "findings_summary": { "critical": 0, "significant": 2, "low_confidence": 3, "total": 5 },
    "harmony_record_hash": "uhCkk7mXy...",
    "harmony_record_url": "https://gateway.valichord.org/..."
  },
  "top_findings": [
    { "mode": "B", "severity": "SIGNIFICANT", "title": "No requirements file found" }
  ],
  "download_url": "/download/<job_id>"
}
```

---

## Webhooks (push notifications)

Instead of polling, supply a `callback_url` when submitting. ValiChord will
POST the result to that URL once when the job finishes.

```bash
curl -X POST /validate \
  -H "X-ValiChord-Key: your-key" \
  -F "file=@study.zip" \
  -F "callback_url=https://your-tool.example.com/valichord-callback"
```

The callback POST includes:
- `Content-Type: application/json`
- `X-ValiChord-Job-Id: <job_id>` header
- Body: same structure as `GET /result/<job_id>` when done

ValiChord retries once after 5 seconds on failure. If both attempts fail,
fall back to polling.

---

## Downloading the full report

```
GET /download/<job_id>
```

Returns a ZIP containing:

| File | Contents |
|------|----------|
| `CLEANING_REPORT.md` | Human-readable summary of all findings (CRITICAL / SIGNIFICANT / LOW CONFIDENCE) |
| `README_DRAFT.md` | Suggested README — installation, usage, entry points |
| `LICENCE_DRAFT.txt` | Suggested licence file |
| `INVENTORY_DRAFT.md` | Full file inventory with type classifications |
| `ASSESSMENT.md` | Verification questions for the researcher |
| `VALICHORD_LOG.json` | Machine-readable event log (all detector codes) |

The job is removed from server memory after this call.

---

## The HarmonyRecord

When the Holochain conductor is running, ValiChord writes the verdict
permanently to the Governance DHT. The response includes:

- `harmony_record_hash` — a `uhCkk...` string uniquely identifying the record.
  Share this with researchers, journals, and funders as permanent proof.
- `harmony_record_url` — a public HTTP Gateway URL where anyone can verify
  the record independently, without an account or login. Null until a
  permanent gateway is deployed.

`harmony_record_hash` is null when the conductor is offline. The analysis
results are always returned regardless.

---

## Code examples

### Python

```python
import time
import requests

BASE_URL = "https://your-valichord-instance"
API_KEY = "your-api-key"
HEADERS = {"X-ValiChord-Key": API_KEY}

def validate_deposit(zip_path: str, validator_outcome: str = None,
                     validator_notes: str = "") -> dict:
    # Submit
    with open(zip_path, "rb") as f:
        data = {}
        if validator_outcome:
            data["validator_outcome"] = validator_outcome
            data["validator_notes"] = validator_notes
        resp = requests.post(
            f"{BASE_URL}/validate",
            headers=HEADERS,
            files={"file": f},
            data=data,
        )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    print(f"Job started: {job_id}")

    # Poll
    for _ in range(150):   # 25 min max
        time.sleep(10)
        result = requests.get(f"{BASE_URL}/result/{job_id}").json()
        if result["status"] == "done":
            return result
        if result["status"] == "error":
            raise RuntimeError(result["error"])

    raise TimeoutError("ValiChord job timed out")


result = validate_deposit(
    "my-study.zip",
    validator_outcome="Reproduced",
    validator_notes="All 3 figures reproduced within numerical tolerance.",
)
draft = result["harmony_record_draft"]
print(f"Outcome:  {draft['outcome']['type']}")
print(f"Attested: {draft['validator_attested']}")
print(f"Record:   {draft['harmony_record_hash']}")
```

### TypeScript / JavaScript

```typescript
const BASE_URL = "https://your-valichord-instance";
const API_KEY = "your-api-key";

async function validateDeposit(
  zipBlob: Blob,
  validatorOutcome?: "Reproduced" | "PartiallyReproduced" | "FailedToReproduce",
  validatorNotes?: string,
): Promise<object> {
  // Submit
  const form = new FormData();
  form.append("file", zipBlob, "deposit.zip");
  if (validatorOutcome) {
    form.append("validator_outcome", validatorOutcome);
    form.append("validator_notes", validatorNotes ?? "");
  }

  const submit = await fetch(`${BASE_URL}/validate`, {
    method: "POST",
    headers: { "X-ValiChord-Key": API_KEY },
    body: form,
  });
  const { job_id } = await submit.json();
  console.log("Job started:", job_id);

  // Poll
  for (let i = 0; i < 150; i++) {
    await new Promise((r) => setTimeout(r, 10_000));
    const result = await fetch(`${BASE_URL}/result/${job_id}`).then((r) => r.json());
    if (result.status === "done") return result;
    if (result.status === "error") throw new Error(result.error);
  }
  throw new Error("ValiChord job timed out");
}

// Usage
const result = await validateDeposit(zipBlob, "FailedToReproduce",
  "Script failed at step 2 — missing CUDA driver.");
const draft = (result as any).harmony_record_draft;
console.log("Outcome:", draft.outcome.type);
console.log("Record:", draft.harmony_record_hash);
```

---

## Checking the server

```bash
curl https://your-valichord-instance/health
# { "status": "ok", "version": "1.0", "conductor": "live" }
```

`conductor: "live"` means HarmonyRecords will be written to the DHT.
`conductor: "offline"` means analysis runs but no record is written.

---

## Large deposits (> 100 MB)

For deposits over 100 MB, use the chunked upload endpoint `POST /upload-chunk`.
Split your file into ~1 MB chunks and POST them with:
- `upload_id` — a client-generated UUID for the session
- `chunk_index` — 0-based
- `total_chunks` — total number of chunks
- `chunk` — binary data

When the last chunk arrives, the job starts and the response includes
`{ "status": "processing", "job_id": "..." }`. Poll `GET /result/<job_id>`
as normal.

---

## Environment variables (server operators)

| Variable | Default | Purpose |
|----------|---------|---------|
| `VALICHORD_API_KEYS` | *(empty — open)* | Comma-separated list of valid API keys |
| `HOLOCHAIN_GATEWAY_URL` | *(empty)* | Base URL of the HTTP Gateway for public HarmonyRecord lookups |
| `HOLOCHAIN_GOVERNANCE_DNA_HASH` | *(empty)* | Governance DNA hash (from `hc app info`) |
| `HOLOCHAIN_APP_ID` | `valichord-demo` | Installed app ID in the conductor |
| `PORT` | `5000` | Flask listen port |

---

## AI evaluation attestation (`valichord_attestation`)

For AI pipelines submitting benchmark claims (e.g. model accuracy on a public dataset),
ValiChord provides a standalone Python library — **`valichord_attestation`** — that does not
require the full Holochain protocol.

The library builds a cryptographically deterministic bundle from an AI evaluation run:
a stable SHA-256 hash of the complete run (via RFC 8785 / JCS encoding), a Merkle tree over
per-sample outputs for selective disclosure, and a probabilistic challenge-response protocol
so a verifier can spot-check any subset of samples without holding the full log.

A bundle is the *evidence layer*. A researcher publishes the bundle hash as their claim.
Independent validators run the same evaluation, build their own bundles, and compare. When a
full ValiChord validation round is required (commit-reveal on the Holochain DHT), the bundle
hash becomes the `data_hash` passed into the attestation DNA.

```python
from valichord_attestation import build_bundle, hash_bundle

bundle = build_bundle(
    model_id="mistralai/Mistral-7B-Instruct-v0.3",
    task_id="gsm8k",
    raw_metrics=[{"key": "exact_match,flexible-extract", "value": 0.35}],
    samples=[{"doc_id": 0, "target": "42", "filtered_resps": [["42"]]}],
    samples_total=500,   # declare total so partial runs are detectable
)
print(hash_bundle(bundle))   # stable SHA-256 across implementations
```

See `valichord_attestation/README.md` for the full API and
`valichord_attestation/examples/` for a worked Mistral-7B / GSM8K walkthrough.

---

## Further reading

- **Interactive docs:** `GET /docs` (Swagger UI)
- **OpenAPI spec:** `GET /openapi.yaml`
- **`valichord_attestation` library:** `valichord_attestation/README.md`
- **4-DNA architecture:** `docs/7_ValiChord_4-DNA_architecture_technical.md`
- **How a validation round works:** `docs/15_How_a_Validation_Round_Works.md`
