# Demo Handover — 2026-04-20

## TL;DR
The decentralised demo gets through commits and phase gate but a validator conductor crashes silently during the reveal phase. The latest WASM build (Local-strategy optimisations) was just compiled but **not yet tested**. Start there.

---

## Quick start for next session

```bash
cd /workspaces/ValiChord
docker compose -f demo/docker-compose.yml down -v
docker compose -f demo/docker-compose.yml up --build -d
# wait ~60s for all nodes
export ANTHROPIC_API_KEY=sk-ant-...
python3 demo/ai_validator.py --mode decentralised 2>&1
```

---

## What works

- All 4 node conductors start fine (researcher + 3 validators)
- Claude forms 3 verdicts (all Reproduced, High)
- Researcher locks result and submits ValidationRequest ✓
- All 3 validators commit blind ✓  
- Phase gate opens (RevealOpen) ✓
- Researcher reveals ✓
- Validator 1 reveals ✓
- **Validator 2 (port 3003) crashes before/during its reveal** ✗

---

## The crash

One Holochain conductor process dies silently — no panic in the log, no OOM kill message in dmesg, Docker reports `OOMKilled: false`. The conductor log ends with:

```
WARN holochain_sqlite::db::guard: PTxnGuard was held for 209ms   ← heavy SQLite contention
WARN holochain_websocket: WebsocketReceiver Error Close(...)
[process dies here]
```

**Root cause**: Brief memory spike during concurrent DHT operations. Not a sustained OOM — at crash time ~1.4 GB headroom remained. The spike happens when multiple conductors make simultaneous `GetStrategy::Network` DHT calls (each = WebRTC round-trip).

---

## Everything that's been done

### WASM changes (valichord proper — rebuilt, repacked)
All in `valichord/dnas/attestation/zomes/attestation_coordinator/src/lib.rs`:

**`notify_commitment_sealed`** (commit phase):
- Step 1 path lookup → `GetStrategy::Local` (VR was written before commits)
- Step 3 quorum check: replaced `check_all_commitments_sealed_inner()` (redundant Network get_links) with `existing_links.len() + 1 >= minimum_validators`

**`submit_attestation`** (validator reveal — applied last, not yet tested):
- CommitmentAnchor link fetch → `GetStrategy::Local`
- CommitmentAnchor entry fetch → `GetOptions::local()`
- Duplicate check → `GetStrategy::Local`

**`reveal_researcher_result`** (researcher reveal — applied last, not yet tested):
- Existing reveal idempotency check → `GetStrategy::Local`
- Study path VR lookup → `GetStrategy::Local`

### Demo/infra changes
- **Role-filtered happs**: `researcher.happ` (3 DNAs, 3.3 MB) and `validator.happ` (3 DNAs, 3.3 MB) instead of full 4-DNA bundle (4.3 MB). Each node only loads the DNAs it needs.
- `db_sync_strategy: Fast` and `tx5Transport.timeoutS: 20` in conductor config
- 20s wait after ValidationRequest before commits (DHT propagation)
- 30s stagger between validator commits (was 15s)
- 15s stagger between validator reveals (was 0s)
- Better RUST_LOG in node-entrypoint.sh

---

## If it still crashes — next steps in order

### 1. Increase reveal stagger
In `demo/ai_validator.py` around line 370, change `time.sleep(15)` → `time.sleep(30)`.

### 2. Watch memory in parallel
```bash
while true; do docker stats --no-stream --format "{{.Name}} {{.MemUsage}}"; sleep 5; done
```
Run this alongside the demo to see which conductor peaks before crashing.

### 3. Add Docker memory limits
In `demo/docker-compose.yml`, add to each conductor service:
```yaml
deploy:
  resources:
    limits:
      memory: 1g
```
This makes OOM kills show up as `OOMKilled: true` in `docker inspect`.

### 4. Fall back to 2 validators
If memory is genuinely the ceiling, drop to 2 validators temporarily:
- `demo/ai_validator.py`: `num_validators_required: 2`, remove VALIDATOR_3_URL, 2 Claude calls
- `demo/node-setup.mjs`: `minimum_validators: 2`
- `demo/docker-compose.yml`: comment out validator-3 service and volume

---

## Rebuild commands (if you change WASM)

```bash
cd /workspaces/ValiChord/valichord
export PATH="/home/codespace/.cargo/bin:$PATH"
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace -o workdir/validator_workspace.dna
hc dna pack dnas/governance -o workdir/governance.dna
hc app pack researcher -o workdir/researcher.happ
hc app pack validator -o workdir/validator.happ
# Then rebuild Docker images:
docker compose -f demo/docker-compose.yml down -v
docker compose -f demo/docker-compose.yml up --build -d
```

---

## Key files
| File | What it is |
|---|---|
| `demo/ai_validator.py` | Demo script — entry point |
| `demo/docker-compose.yml` | 5-container stack definition |
| `demo/node-entrypoint.sh` | Container startup (HAPP_PATH, RUST_LOG, conductor) |
| `demo/conductor-config-node.yaml` | Holochain conductor config template |
| `valichord/researcher/happ.yaml` | Role-filtered researcher happ manifest |
| `valichord/validator/happ.yaml` | Role-filtered validator happ manifest |
| `valichord/dnas/attestation/zomes/attestation_coordinator/src/lib.rs` | Main protocol logic — where the Local-strategy changes live |
