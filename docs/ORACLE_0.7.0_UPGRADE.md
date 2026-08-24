# Oracle upgrade to Holochain 0.7.0 — runbook

**Written 2026-08-24, blocked on access — see [Access](#access) first.**

The Oracle demo host still runs Holochain **0.6.2** while `main` has been on **0.7.0** since
2026-08-03. This document is the sequence to close that gap. It exists because the person who
prepared it could not execute it: the instance has no reachable shell.

Everything here about the code was verified against the repo. Everything about the *server* is
marked as verified or assumed, and the assumptions are called out.

---

## Access

⚠️ **There is currently no way to run a command on `152.67.153.149`.**

| Route | State |
|---|---|
| SSH | ❌ The private key from instance creation (2026-07-07) is lost. Oracle shows a private key once and never stores it. |
| Compute Instance Run Command | ❌ Plugin reports Enabled/Running, commands are Accepted and their content stored, **the agent never collects them** ("No response received yet"). Unchanged by a reboot (2026-08-24). Cause not found. **Ruled out:** VCN egress — the security list allows all protocols on all ports to 0.0.0.0/0, so the agent is not being firewalled off from Oracle's endpoints. |
| Instance console (serial) connection | ⚪ Untried. Needs a freshly generated key pair and still lands at a login prompt. |
| Boot-volume detach → edit `authorized_keys` → reattach | ⚪ Untried. Works, but it is surgery. |

**Recommended instead: rebuild the instance.** This is far less drastic than it sounds, because
**the upgrade destroys all DHT state anyway** (see [Why this is a rebuild](#why-this-is-a-rebuild-not-a-patch)).
What a fresh instance costs is the server setup, and that setup is thin — Docker, a git clone,
`docker compose up`. There is no database to migrate, no Rust toolchain needed, and the `.happ`
bundles are committed to the repo. You would come out of it holding the SSH key, which ends
this problem permanently rather than working around it.

### Server facts (verified from the Oracle console, 2026-08-24)

| | |
|---|---|
| Instance | `instance-20260707-1610`, `uk-london-1`, compartment `topeuph (root)` |
| Shape | `VM.Standard.A1.Flex` — **ARM64 (aarch64)** |
| Size | **1 OCPU**, 6 GB RAM |
| OS | **Oracle Linux 9**, login user `opc` |
| Public IP | `152.67.153.149` |

⚠️ **`demo/oracle_setup.sh` did not build this box.** It targets Ubuntu 20.04, uses `apt-get`,
installs Holochain **0.6.1**, and twice tells you to run `demo/start_oracle.sh` — a script
deleted in `9738fe1`. Do not follow it. Treat it as historical.

⚠️ **The repo path on the server is unknown.** The diagnostic that would have found it could not
run. Locate it first:
`for d in /home/*/ValiChord /root/ValiChord /opt/ValiChord; do [ -f "$d/demo/docker-compose.yml" ] && echo "$d"; done`

---

## Why this is a rebuild, not a patch

All four DNA hashes changed between 0.6.2 and 0.7.0, because `reproduction_bundle_hash` lives in
`shared_types` and every DNA depends on it.

**A DNA hash change forks the network.** Agents on the old hash and the new one cannot see each
other. Every HarmonyRecord URL published from the old stack dies permanently. `docker compose
down -v` is mandatory — the named volumes hold 0.6.2 conductor state that a 0.7.0 conductor
cannot use.

`PROJECT_STATUS.md` already records this consequence as accepted. Confirm it is still accepted
before starting, and check whether any live record URL has been sent to anyone recently.

---

## What is already done — do not redo it

The 0.7 port is merged. So are the four breakages found on 2026-08-02 when the demo stack was
first *started* rather than edited blind. Verified present in `main` on 2026-08-24:

| Fixed | Where |
|---|---|
| `HOLOCHAIN_VERSION=0.7.0`, `KITSUNE2_VERSION=0.5.0` | `demo/Dockerfile.node:13,16` |
| Bundled-binary check matches the **version string**, with a hard post-check that fails the build | `demo/Dockerfile.node` |
| `--sbd-disable-rate-limiting` removed (whole `--sbd-*` family gone in kitsune2 0.5.0) | `demo/docker-compose.yml` |
| `relay_url` on `http://` + `advanced.irohTransport.relayAllowPlainText: true`; `db_sync_level: Off`; no `signal_url` | `demo/conductor-config-node.yaml` |

Also checked: the config's placeholders (`__ADMIN_PORT__`, `__BOOTSTRAP_URL__`) exactly match what
`node-entrypoint.sh` substitutes, with no orphaned `__SIGNAL_URL__`; and the 0.7.0 release ships
`aarch64-unknown-linux-gnu` builds of both `holochain` and `kitsune2-bootstrap-srv`, which this
ARM host needs.

**No compilation happens on the server.** `Dockerfile.node` has no Rust or WASM step — the three
`.happ` bundles are committed and copied into the image. That matters on a 1-OCPU box.

---

## The upgrade

Run from the repo directory on the server. `$R` is that directory.

### 1. Confirm the starting state

```bash
git -C "$R" fetch origin
git -C "$R" status --short          # ANY output = someone edited files on the server; stop and read them
git -C "$R" log -1 --format='%h %ad %s' --date=short
docker ps --format '{{.Names}}={{.Status}}'
nproc; free -m | head -2; df -h / | tail -1
```

**Do not proceed if `git status` is dirty.** A `git pull` will either clobber those edits or
refuse. Find out what they are first — a change made directly on the server is a change nobody
wrote down.

### 2. Take the code

```bash
git -C "$R" pull --ff-only origin main
git -C "$R" log -1 --format='%h %ad %s' --date=short
grep -n 'ARG HOLOCHAIN_VERSION\|ARG KITSUNE2_VERSION' "$R/demo/Dockerfile.node"
```

Expect `0.7.0` and `0.5.0`. If not, the pull did not land.

### 3. Destroy the old network — the irreversible step

```bash
docker compose -f "$R/demo/docker-compose.yml" down -v
docker volume ls | grep -i valichord     # expect nothing left
```

Everything published from the 0.6.2 stack is now gone. There is no undo.

### 4. Rebuild and start

```bash
docker compose -f "$R/demo/docker-compose.yml" build --no-cache
docker compose -f "$R/demo/docker-compose.yml" up -d
```

`--no-cache` is deliberate: the binary-version guard runs in a `RUN` layer, and a cached layer
would skip the very check that catches a wrong-version `kitsune2-bootstrap-srv`.

The build downloads two binaries and runs `npm install`. On 1 OCPU expect this to be slow.

### 5. Gate — are the DNAs the ones we think they are?

Before trusting anything, compare the hashes inside the running happ against the table below. A
0.6.2 bundle on a 0.7.0 conductor, or vice versa, is the failure mode most worth catching.

| DNA | Expected 0.7.0 hash |
|---|---|
| attestation | `uhC0kHA0WhADQPl5QCjt46s0FF4n3Ow31GB8mboTVZ6ATLm1-h7ha` |
| researcher_repository | `uhC0k0yKAcW_9d23GcZ_NqKkQ8S8qYzAUFEUR6INXTUiQL-jXQTw7` |
| validator_workspace | `uhC0kf_nk5PLP_sCHC6IeLEML1xiIQTM6n---e5tPhChKB0Mmy5l4` |
| governance | `uhC0kRrX19H1PP-lfWYhBc6vRUIDAG1CkI7zMWVOD9AZ15xoGwZSC` |

Source: `docs/Holochain_complete.md` §44.5. Those are the hashes **after** the validator→bundle
binding and the `DataLocalityMode` field, which is the state actually committed.

⚠️ The commit history says the committed bundles are the 0.7 ones (`f8e3ac7`, 2026-08-02, *"commit
the repacked happ"*; rebuilt again in `bc3ed82`). **That is history, not a hash comparison.** This
gate is what turns belief into knowledge.

### 6. Verify

```bash
docker compose -f "$R/demo/docker-compose.yml" ps        # 5 containers, no restart loops
docker compose -f "$R/demo/docker-compose.yml" logs --tail=40 bootstrap
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3001/phase   # 400 = alive (missing params)
```

From anywhere: ports 3001–3004 on `152.67.153.149` should answer — `3001/phase` returns **400**,
validators return **404**. Those are the healthy responses, confirmed against the 0.6.2 stack on
2026-08-24 before the upgrade.

Then run a real round end to end. That is the only proof that counts.

---

## Risks that this upgrade does *not* retire

**1 OCPU and SQLite contention — the live unknown.** `docs/Holochain_complete.md` §44.12 records
recurring `SqliteError { code: 5 / 517, "database is locked" }` from `integrate_dht_ops_consumer`
across the conductors, in both a manual and an AI round. Nothing failed and every assertion held.
The doc's own hypothesis is contention from *"five conductors on a 2-core Codespace"* — and it is
explicit that this is **a hypothesis, not a finding**, and says to check it on Oracle before the
demo is relied on there.

**Oracle has one core.** It is half the machine on which the symptom was already visible.
`VM.Standard.A1.Flex` is resizable and the Ampere allowance (4 OCPUs / 24 GB) is free even on a
paid account. Resizing needs a reboot — the same reboot a rebuild needs anyway.

**The relay binary variant.** The 0.7.0 release ships both `kitsune2-bootstrap-srv` and a separate
`kitsune2-bootstrap-srv-iroh-relay`. `Dockerfile.node` pulls the plain one, and the verified run
reported zero relay errors — **on x86_64**. If relay warnings appear on ARM, check this first.

**`relayAllowPlainText: true` is unconditional** in a config shared by the local demo and Oracle.
Correct while the relay is a local container on plain HTTP. If a real TLS relay is ever put in
front, this must come off.

**The viewer warning is not a defect.** `ai_validator.py:582` rewrites `localhost` to a detected
public IP so the printed URL is shareable, then fetches its own URL to self-verify. On Oracle that
address is genuinely reachable, so unlike in a Codespace it should not time out. If it does, that
is worth reading — it means the public IP is not reaching itself.

---

## Two failure modes worth recognising on sight

From §44.12, because they sit at opposite ends of the loud/quiet axis:

- **`ws://` relay URL** — iroh rejects the scheme, but the conductor **starts and the happ
  installs**. The only symptom is a warning repeating every few hundred milliseconds while relay
  connectivity is quietly degraded. Easy to ship without noticing.
- **`http://` relay without the opt-in** — kitsune2 0.5.0 refuses a plaintext relay and the
  conductor **crashes** with `K2Error(Other { ctx: "Disallowed plaintext relay URL" })`.

The second is strictly better despite looking worse. A wrong `NetworkConfig` behaves the same way:
**exit 42, not degraded operation.** If a conductor starts, its network config parsed.
