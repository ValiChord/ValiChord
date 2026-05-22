# ValiChord Live Demo — Public Web Interface

**Live at: [valichord-demo.onrender.com/demo](https://valichord-demo.onrender.com/demo)**

---

## What it is

A one-click browser interface to the full ValiChord commit-reveal protocol. Click **Run Protocol** and watch the live Holochain network on Oracle Cloud run a real reproducibility validation — researcher and three validators committing blind and revealing simultaneously. Takes about two minutes because that is real network time, not a timer.

The page includes a skeptic-proof section at the end: the HarmonyRecord hash is unique to each run, generated on the Oracle DHT, and fetchable from any machine independently. The page shows you the exact `curl` command to verify it yourself.

---

## What the demo runs

The study is a linear regression across 20 climate sampling sites, implemented from scratch in pure Python with no libraries. The researcher claims slope ≈ 2.4086, intercept ≈ 3.1, R² ≈ 0.9991.

Three Claude Haiku agents act as independent validators. Each reads the study README and execution output and forms a reproducibility verdict — without seeing each other's response. The verdicts are committed blind to the DHT before any reveal happens.

---

## How it works

The web server is a Flask app (`demo/app.py`) deployed on Render. It talks to four Holochain nodes running permanently on Oracle Cloud (132.145.34.27) via the Node.js HTTP bridges (`researcher-node.mjs`, `validator-node.mjs`).

### Request flow

```
Browser → POST /demo/run
        ← { job_id }

Browser → GET /demo/result/<job_id>  (polled every 2 s)
        ← { step, status, result }

Browser → GET /demo/record/<hash>    (skeptic verify button)
        ← raw HarmonyRecord JSON from Oracle DHT
```

### Protocol steps (reflected in the progress bar)

| Step | What happens |
|---|---|
| 1 | Load study deposit — README + data hash with per-run UUID salt |
| 2 | Execute `synthetic_study/study.py`, parse slope/intercept/R² |
| 3 | Form 3 independent verdicts via Claude Haiku (5-retry correction loop each) |
| 4 | Researcher locks result on DNA 1; all 3 validators commit blind to DNA 3 |
| 5 | All 3 CommitmentAnchors confirmed on DHT |
| 6 | Researcher + all 3 validators reveal; each side cryptographically verified |
| 7 | HarmonyRecord written to DNA 4; shareable URL returned |

### Concurrency design

Only one protocol run at a time — enforced by a `threading.Lock()` + `_demo_running` bool. A second visitor hitting **Run Protocol** while one is in flight gets a 409 with a "check back in ~2 minutes" message. The lock is always released in a `finally` block.

Job state is held in a process-level dict (`_jobs`). Render runs gunicorn with `--workers 1 --threads 4`, so all threads share the same process and the in-memory job dict works correctly.

---

## Running locally

```bash
cd demo
pip install flask flask-cors anthropic gunicorn

export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001
export VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002
export VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003
export VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004

python app.py
# opens at http://localhost:8080/demo
```

This runs against the live Oracle nodes — no local Docker setup needed.

To run a fully local stack instead, start the Docker demo first:

```bash
docker compose -f demo/docker-compose.yml up --build -d
# wait for 4x "node API →" in logs, then:
export VALICHORD_RESEARCHER_URL=http://localhost:3001
# etc.
python app.py
```

---

## Deploying to Render

The repo contains a `render.yaml` that configures the service automatically.

1. Connect the `topeuph-ai/ValiChord` repo to Render
2. Render picks up `render.yaml` and builds from `demo/Dockerfile` (context: repo root)
3. Set `ANTHROPIC_API_KEY` manually in the Render dashboard under **Environment** — do not commit it to `render.yaml`
4. Every push to `main` triggers a redeploy

The Oracle node URLs are hardcoded in `render.yaml` — they are not secrets.

**Dockerfile notes:**
- Built from `python:3.12-slim`
- Runs as a non-root `appuser`
- Gunicorn: `--workers 1 --threads 4 --timeout 180` (180 s covers the full protocol round-trip)
- Static files (logo) served from `demo/static/`
- Health check: `GET /health` → `{"status": "ok"}`

---

## Files

| File | Purpose |
|---|---|
| `demo/app.py` | Flask server — routes, background job runner, HTML |
| `demo/demo_runner.py` | Protocol logic — load study, execute, form verdicts, run protocol |
| `demo/synthetic_study/study.py` | The actual study code validators reproduce |
| `demo/static/valichord-logo.jpeg` | Logo served at `/static/valichord-logo.jpeg` |
| `demo/requirements.txt` | `flask`, `flask-cors`, `anthropic`, `gunicorn` |
| `demo/Dockerfile` | Container definition for Render deployment |
| `render.yaml` | Render service configuration |

---

## Verifying the result independently

At the end of a run, the page shows a `curl` command like:

```bash
curl "http://132.145.34.27:3001/record?hash=uhC8k…"
```

Run that from any machine. The response is the raw HarmonyRecord JSON from the Oracle DHT — not served by the demo website. The hash is unique to the run (derived from a per-run UUID salt on the data hash) so it cannot be pre-computed or reused.

The **Fetch raw record from Oracle** button on the page does the same fetch live in the browser via `GET /demo/record/<hash>`, which proxies to the Oracle node and returns the JSON unmodified.
