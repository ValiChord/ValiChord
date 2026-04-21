# ValiChord — Decentralised Demo

Runs the full ValiChord commit-reveal protocol across **5 isolated Docker containers** — one researcher conductor, three validator conductors, and one kitsune2 bootstrap/DHT server — with no shared state between them.

Three independent Claude instances act as validators. Neither the researcher nor any validator can change their result after the other side has committed. A permanent **HarmonyRecord** is written to the Governance DHT at the end.

## Requirements

- Docker and Docker Compose
- Python 3.9+
- An Anthropic API key (`claude-sonnet-4-6` or better)
- Linux x86_64 (the Holochain binary is auto-downloaded for this platform)

## Run it

```bash
git clone https://github.com/topeuph-ai/ValiChord.git
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

The commit-reveal protocol guarantees:
- **Validators cannot see each other's verdicts** before committing their own
- **The researcher cannot change their claimed result** after validators have committed
- **The HarmonyRecord is permanent** — written to the DHT and cryptographically linked to both the researcher's commitment and all three validator attestations

## Tear down

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

Requires: `cargo`, `wasm32-unknown-unknown` target, and `hc` CLI (`cargo install holochain_cli --version 0.6.0 --locked`).
