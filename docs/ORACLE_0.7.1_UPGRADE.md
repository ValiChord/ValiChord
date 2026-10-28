# Oracle upgrade to Holochain 0.7.1 — runbook

✅ **RUN 2026-10-19 by Ceri, from his Windows PC over SSH, step by step with Claude.** Result and
findings: see [**Run record**](#run-record-2026-10-19) at the end.

**Written 2026-10-17.** Follows the shape of `docs/ORACLE_0.7.0_UPGRADE.md`, which
holds the background (why this is a rebuild, failure modes, risks). Read that once; this file
carries only what is different.

**Updated 2026-10-18 after PR #47 merged.** #47 changed the integrity zomes of the attestation and
governance DNAs: peers now check joining credentials (#37), a HarmonyRecord's signed attestation
evidence (#11) and validator tiers (#8). That is a second DNA-hash change on top of 0.7.1's, so the
bundles were repacked and the checksums below replaced. **This one install pays for both** —
which is why it was held back until #47 landed. ⚠️ If any other integrity change merges before the
install, repack and update the checksums again first.

**Updated again 2026-10-19 after PR #55 merged.** #55 changed the attestation integrity zome again
(a RevealOpen marker must list the whole cohort; a researcher's reveal must name its request and
commitment — issues #51 and #53). Repacked and checksums replaced, as above. The one install still
pays for all three changes.

**Updated a third time 2026-10-19 after PR #57 merged.** #57 rode this same break with four more
integrity changes Ceri approved: record supersession (backlog 01), hardware disclosure (02),
hash-algorithm labels (#23) and the network name (#24, `valichord-public`). Repacked and checksums
replaced. The one install pays for all of it.

## What is different from the 0.7.0 runbook

| | 0.7.0 (2026-08-24) | 0.7.1 (this) |
|---|---|---|
| Host | `132.145.23.78` (that runbook still names the old `152.67.153.149` — ignore it) | same |
| Access | SSH as `opc`, key `~/.ssh/valichord_oracle` | same |
| Docker pins | `HOLOCHAIN_VERSION=0.7.0`, `KITSUNE2_VERSION=0.5.0` | **`0.7.1`, `0.5.1`** |
| Bundles | packed 2026-08-03 | **packed in CI 2026-10-19**, run `39273798429` (`repack-bundles.yml`), from `33bbb6c` — after #47, #55 and #57 |
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
0af5cc189148bf1dd7d614f7434fe1432f6a307ba78cd5710949d871a7fd2cc1  researcher.happ
798b237d6c867e0c707c576d532bb00e24815cee37b676616d69c4c0443333fa  valichord.happ
e0ca09120f9da17278fcd958317859d8ede800a2b2aef894edfe5a9c19fb0cfb  validator.happ
```

Any difference means the pull did not land or the files were changed on the server. **Stop.**
⚠️ If git on the server converts line endings in binary files these will differ for that reason —
`git -C "$R" check-attr -a valichord/workdir/researcher.happ` will say; fix that rather than
proceeding.

ℹ️ **These are the bundles of the 2026-10-19 install.** The committed bundles were repacked on
2026-10-27 after #60 (run `40602164694`) and now read:

```
c9ddaaf43dd8148073e820a4f993668312223dfc12392dbd089baa9eb2e9c29e  researcher.happ
1bab687f66d7e6291eaab55210fbb853dc080f6a6455236e8e812044a9a8968b  valichord.happ
1e895bb027286790b5a70b57801053b164616abdcea61d134c2cbb5bf4347081  validator.happ
```

Only the attestation coordinator differs. The integrity WASMs and DNA manifests are identical, so
the DNA hashes in the run record still hold. ⚠️ **Do not re-run this runbook to deliver #60:**
nothing changed the DNA hash, so step 4's `down -v` would destroy the live network for nothing.
#60 reaches Oracle by a coordinator hot-swap: [`ORACLE_HOTSWAP_60.md`](ORACLE_HOTSWAP_60.md)
(run 2026-10-28).

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

- The old `152.67.153.149` instance on 0.6.2 was still a hazard (it answered healthily on a dead
  network). Unchanged by this upgrade. ✅ Ceri switched it off on 2026-10-28.

## Run record 2026-10-19

**Outcome: done, and verified.** Gate passed (all three sha256 values matched), `down -v` removed
5 containers and 4 volumes with none left over, the `--no-cache` build passed the version guard
(no `FATAL`), and all four nodes reached `node API →`. A real round then ran end to end:
**Reproduced 3/3, ExactMatch**, read back from outside the server with HTTP 200.

**Live record:** `http://132.145.23.78:3001/record?hash=uhC8kczl-ObcLqHU21FmAnHxOw_qgWEHsq0kBqrOzGenu5bwCXwk-`

**DNA hashes, observed on the running conductors.** All four differ from the 0.7.0 table, so the
network break this upgrade was planned around is now **observed, not expected**. The researcher
and validator conductors report the same attestation and governance hashes, so they are on one
network.

| DNA | 0.7.1 hash (observed) |
|---|---|
| attestation | `uhC0kg1-EFqxTnOlNGU98cOHAHhXJkCWQ9eXHi6e9LBCWSy0e_JFI` |
| researcher_repository | `uhC0kyosyy9bHNyAN1dTYQeOEF3wRwuUlzxqvX4plSYRr8KQ8X7_J` |
| validator_workspace | `uhC0k0gM6sOJThk0M4nDF5qYYmsb3_vLQVtP65kmN5EY3kmaek_zX` |
| governance | `uhC0kQG8wTTQ1_o_O-jARmv6il29nV27VNfbrShMcXVxZpMDqa9NM` |

Read with a one-line Node call against each conductor's admin port (`listApps` →
`cell_info[role][0].value.cell_id[0]`), run inside the `researcher` and `validator-1` containers.

**What the run turned up. Fix these before relying on this runbook again:**

1. **Windows SSH refused the key file** ("UNPROTECTED PRIVATE KEY FILE"): it was readable by other
   local accounts, including an orphaned SID. Fixed with
   `icacls <key> /grant:r "$env:USERNAME:R"` then `icacls <key> /inheritance:r`.
2. **The server's `python3` is 3.9.** `demo/ai_validator.py` failed at import on a `dict | None`
   annotation; fixed in `2fc8974` (`from __future__ import annotations`). Other demo scripts may
   carry the same 3.10+ syntax.
3. **No pip and no `anthropic` package on the server.** `sudo dnf install -y python3-pip`, then
   `python3 -m pip install --user anthropic`.
4. **`ANTHROPIC_API_KEY` was not in `~/.bashrc`**, contrary to `demo/DECENTRALISED_DEMO.md`
   (corrected). It was set for the session only.
5. **Benign, not failures:** `Admin socket connection failed … Handshake not finished` is the
   entrypoint's port probe; `NoPeersForLocation` at first publish is a node with no peers yet.
   Nodes took about 4 minutes to reach `node API →` (four first-time WASM compiles on 1 OCPU).
6. A leftover, untracked `valichord/workdir/valichord/` (August `.dna` files and `happ.yaml`)
   sits on the server. Harmless: nothing references it, and the nodes load `*.happ` by name.
