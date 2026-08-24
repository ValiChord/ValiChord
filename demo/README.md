# ValiChord — Demos

There are several demos in this folder and only **one** of them is public. This index exists
because it is easy — including for the people who wrote them — to reach for the wrong one.

## Which demo is which

| # | Demo | How you run it | Public? | What it proves |
|---|---|---|---|---|
| 1 | **"Your Hypothesis"** | [valichord-demo.onrender.com/demo](https://valichord-demo.onrender.com/demo) — in a browser | ✅ **the only public one** | You state a claim and seal your own answer; three Claude validators research it blind and commit before anyone reveals. Requires **your own** Anthropic key (`sk-ant-…`); the page estimates $0.50–1.50 per run. Code: `app.py` → `custom_runner.py`. |
| 2 | **Synthetic study, 7 steps** | `python3 demo/ai_validator.py --mode decentralised` | ❌ CLI | The original end-to-end protocol run over a fixed synthetic study. Validators are single-shot Claude calls. Runs against the Oracle nodes or a local Docker stack — **this document covers that setup.** |
| 3 | **Synthetic study, CMA validators** | `python3 demo/ai_validator_cma.py --mode decentralised` | ❌ CLI | Same protocol as #2, but each validator is a Managed Agents session doing multi-step analysis with live web search. |
| 4 | **CORE-Bench** | `demo/core_bench_runner.py` | ❌ CLI | Reproduction of a real published result from CORE-Bench. See [CORE_BENCH_DEMO.md](CORE_BENCH_DEMO.md). |
| 5 | **PEP Master** | `demo/pep_master_round.py` | ❌ CLI | That the protocol verifies **open-hardware measurement** reproducibility, not only computational results. See [PEP_MASTER_DEMO.md](PEP_MASTER_DEMO.md). |
| 6 | **EEE worked example** | `demo/eee_worked_example.py` | ❌ CLI | Produces EveryEvalEver-compatible attestation bundles from a real commit–reveal round. See [EEE_WORKED_EXAMPLE.md](EEE_WORKED_EXAMPLE.md). |

`demo_runner.py` is not a demo — it backs the `/demo/record/<hash>` record viewer on the public site.

### The documents, and what each is for

| Document | Purpose |
|---|---|
| **README.md** (this file) | The index, plus how to run demo #2 |
| [DEMO_EXPLAINER.md](DEMO_EXPLAINER.md) | Plain-English explanation of what ValiChord does. Not runnable — start here if you want the idea, not the code |
| [DEMO_WEBSITE.md](DEMO_WEBSITE.md) | Technical detail of the public web interface (demo #1) |
| [DECENTRALISED_DEMO.md](DECENTRALISED_DEMO.md) | Technical guide to the 4-conductor Docker setup |
| [CORE_BENCH_DEMO.md](CORE_BENCH_DEMO.md) · [PEP_MASTER_DEMO.md](PEP_MASTER_DEMO.md) · [EEE_WORKED_EXAMPLE.md](EEE_WORKED_EXAMPLE.md) | The three specialised demos above |
| [CMA_UPGRADE_PLAN.md](CMA_UPGRADE_PLAN.md) | Design record for the Managed Agents validator upgrade. Parts of it are marked **superseded** — read those markers before following it |

> **Status, 2026-08-24.** The Oracle nodes are pending the Holochain **0.7.0** upgrade, so demos
> that talk to them may not complete until that lands. The free server-key tier that once
> funded the public demo has been **withdrawn** — a user-supplied key is now required.

---

## The decentralised demo (demo #2)

Runs the full ValiChord commit-reveal protocol across **5 isolated Docker containers** — one researcher conductor, three validator conductors, and one kitsune2 bootstrap/DHT server — with no shared state between them.

Three independent Claude instances act as validators. **The validators are completely unaware of each other's verdicts before committing. The researcher is completely unaware of what the validators will conclude.** Neither side can change their result after the other has committed. A permanent **HarmonyRecord** is written to the Governance DHT at the end.

## Requirements

- Docker and Docker Compose
- Python 3.8+
- An Anthropic API key (`claude-sonnet-4-6` or better)
- Linux x86_64 (the Holochain binary is auto-downloaded for this platform)

> **Ubuntu 20.04 users:** `docker compose` (without a hyphen) requires a plugin not in Ubuntu 20.04's default repos. Either install docker-compose-plugin separately, or use the standalone `docker-compose` binary: `sudo apt-get install docker-compose`.

## Option A — Run against the live Oracle server (no Docker setup)

A permanent instance of the 5-container stack runs on Oracle Cloud (152.67.153.149). The containers restart automatically after any reboot. You only need an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VALICHORD_RESEARCHER_URL=http://152.67.153.149:3001
export VALICHORD_VALIDATOR_1_URL=http://152.67.153.149:3002
export VALICHORD_VALIDATOR_2_URL=http://152.67.153.149:3003
export VALICHORD_VALIDATOR_3_URL=http://152.67.153.149:3004
python3 demo/ai_validator.py --mode decentralised
```

The shareable HarmonyRecord URL in the output will point to `http://152.67.153.149:3001/record?hash=...` — publicly readable, no authentication required.

## Option B — Run locally with Docker

```bash
git clone https://github.com/ValiChord/ValiChord.git
cd ValiChord

export ANTHROPIC_API_KEY=sk-ant-...

docker compose -f demo/docker-compose.yml up --build -d
```

The first build downloads the Holochain binary (~50 MB) and installs Node dependencies. Subsequent builds use the Docker cache and are fast.

Wait for all four conductors to start (takes ~30 seconds):

```bash
until [ "$(docker compose -f demo/docker-compose.yml logs 2>/dev/null | grep -c 'node API →')" -ge 4 ]; do sleep 3; done && echo "Ready"
```

Then run the demo:

```bash
python3 demo/ai_validator.py --mode decentralised
```

## Expected output

```
[1/7] Loading study deposit…
[2/7] Executing study code…        Slope 2.4086 / R² 0.9991
[3/7] Forming 3 independent verdicts via Claude…
      Validator 1: Reproduced (High)
      Validator 2: Reproduced (High)
      Validator 3: Reproduced (High)
[4/7] Running decentralised commit-reveal protocol…
      (0) Researcher locks result
      (1) ValidationRequest submitted
      (2–4) 3 validators commit blind
      (5) Phase gate: RevealOpen
      (6a) Researcher reveals
      (6b) 3 validators reveal
      (7) HarmonyRecord written to Governance DHT
[7/7] Permanent record.
      HarmonyRecord:  uhCkk…
      Record confirmed. Outcome: Reproduced  Agreement: ExactMatch  Validators: 3
```

## What's happening

Each container runs a completely separate Holochain conductor with its own keypair and SQLite database. They discover each other via the kitsune2 bootstrap server and communicate only through the DHT — there is no shared memory, no shared filesystem, and no central coordinator.

**This is genuinely decentralised (within a single-machine limit).** In a real deployment, each conductor would be on a separate machine owned by a separate institution. The Docker containers here faithfully reproduce that isolation: separate processes, separate keystores, separate databases, DHT gossip as the only data channel.

The commit-reveal protocol guarantees:
- **Validators cannot see each other's verdicts** before committing their own — each validator's private attestation lives only in their own DNA 2 and never leaves until the reveal phase
- **The researcher cannot change their claimed result** after validators have committed — the result hash is sealed before any validator commits
- **No coordinator can alter the outcome** — the phase gate opens automatically when all commitment anchors are confirmed on the DHT; no trusted party triggers it
- **The HarmonyRecord is permanent** — written to the Governance DHT and cryptographically linked to both the researcher's commitment and all three validator attestations; readable at `GET /record?hash=<hash>` with no authentication

## Tear down (local Docker only)

```bash
docker compose -f demo/docker-compose.yml down -v
```

## Rebuilding from source

If you modify the Rust zome code, rebuild the happs before running:

```bash
cd valichord
export PATH="$HOME/.cargo/bin:$PATH"
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation   -o workdir/attestation.dna
hc dna pack dnas/governance    -o workdir/governance.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc app pack researcher -o workdir/researcher.happ
hc app pack validator  -o workdir/validator.happ
cd ..
docker compose -f demo/docker-compose.yml up --build -d
```

Requires: `cargo`, `wasm32-unknown-unknown` target, and `hc` CLI (`cargo install holochain_cli --version 0.6.1 --locked`).
