# Oracle upgrade to Holochain 0.7.1 — runbook

**Written 2026-10-17. Not yet run.** Follows the shape of `docs/ORACLE_0.7.0_UPGRADE.md`, which
holds the background (why this is a rebuild, failure modes, risks). Read that once; this file
carries only what is different.

## What is different from the 0.7.0 runbook

| | 0.7.0 (2026-08-24) | 0.7.1 (this) |
|---|---|---|
| Host | `132.145.23.78` (that runbook still names the old `152.67.153.149` — ignore it) | same |
| Access | SSH as `opc`, key `~/.ssh/valichord_oracle` | same |
| Docker pins | `HOLOCHAIN_VERSION=0.7.0`, `KITSUNE2_VERSION=0.5.0` | **`0.7.1`, `0.5.1`** |
| Bundles | packed 2026-08-03 | **packed in CI 2026-10-17**, run `39059468490` (`repack-bundles.yml`) |
| Gate | DNA-hash table | **sha256 of the bundle files** (below), then record the DNA hashes |

⚠️ **kitsune2-bootstrap-srv is 0.5.1, not 0.5.2.** The kitsune2 *library* crates resolve to 0.5.2,
but the binary the 0.7.1 release ships reports `kitsune2_bootstrap_srv 0.5.1` (observed in CI, and
in holochain's own `Cargo.lock` at the tag). The Docker build greps for that string and stops with
`FATAL` if it does not match.

## Why this is a rebuild, not a patch

Same reason as last time, plus one more. The DNA hash is expected to change (the capability-grant
types are part of the integrity types), so the 0.7.1 stack is a separate network: **every
HarmonyRecord published since 2026-08-24 stops resolving**, including the live record in
`PROJECT_STATUS.md`. And even without a hash change, 0.7.1 **cannot read capability grants written
by 0.7.0** (#5820), and `init` does not re-run — so an in-place upgrade would come up with no
`public-read` grant. **`down -v` is required, not optional.**

## The upgrade

`$R` is the repo directory on the server; find it with
`for d in /home/*/ValiChord /root/ValiChord /opt/ValiChord; do [ -f "$d/demo/docker-compose.yml" ] && echo "$d"; done`.

### 1. Starting state

```bash
git -C "$R" fetch origin
git -C "$R" status --short            # ANY output: stop and read it first
docker ps --format '{{.Names}}={{.Status}}'
df -h / | tail -1; free -m | head -2
```

### 2. Take the code

```bash
git -C "$R" pull --ff-only origin main
grep -n 'ARG HOLOCHAIN_VERSION\|ARG KITSUNE2_VERSION' "$R/demo/Dockerfile.node"   # expect 0.7.1 and 0.5.1
sha256sum "$R"/valichord/workdir/*.happ
```

### 3. Gate — are these the bundles CI built?

The checksums must be **exactly**:

```
602506bdbb177477ac64bdae961f5339459a14f96914107cfe06e935b38450bb  researcher.happ
10d88b7b87e4332bff5cb684f4a209897a70bf1e72ae982bf01be16c181b01cc  valichord.happ
4903e8c3dd1e7752068cb2a59f1d593b1c3a1d85e9d4d17d79917c47c2e0b501  validator.happ
```

Any difference means the pull did not land or the files were changed on the server. **Stop.**
⚠️ If git on the server converts line endings in binary files these will differ for that reason —
`git -C "$R" check-attr -a valichord/workdir/researcher.happ` will say; fix that rather than
proceeding.

### 4. Destroy the old network — the irreversible step

```bash
docker compose -f "$R/demo/docker-compose.yml" down -v
docker volume ls | grep -i valichord   # expect nothing
```

### 5. Rebuild and start

```bash
docker compose -f "$R/demo/docker-compose.yml" build --no-cache
docker compose -f "$R/demo/docker-compose.yml" up -d
```

`--no-cache` matters: the version guard is a `RUN` layer, and a cached layer skips it.

### 6. Verify

```bash
docker compose -f "$R/demo/docker-compose.yml" ps          # 5 containers, no restart loops
docker compose -f "$R/demo/docker-compose.yml" logs --tail=40 bootstrap
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3001/phase   # 400 = alive
```

Then **run a real round end to end** — the only proof that counts — and:

1. **Record the four DNA hashes** the running conductor reports, here and in
   `docs/Holochain_complete.md` §44.5. Confirm they **differ** from the 0.7.0 table in
   `docs/ORACLE_0.7.0_UPGRADE.md`. If they are identical, the "network break" this whole upgrade
   was planned around did not happen, and that is worth knowing before anyone repeats the claim.
2. Replace the live record link in `PROJECT_STATUS.md` with one from the new network.

## Not covered here

- The old `152.67.153.149` instance on 0.6.2 is still a hazard (it answers healthily on a dead
  network). Unchanged by this upgrade; switching it off remains the fix.
