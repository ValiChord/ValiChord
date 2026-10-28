# Oracle: hot-swap #60 onto the live nodes — runbook

✅ **Run 2026-10-28 by Ceri, from a Windows PC over SSH, step by step with Claude.** All four nodes
swapped; see the [Run record](#run-record). Rehearsed the same day (see
[Rehearsal](#rehearsal-2026-10-28)). Run it from a machine that holds the Oracle SSH key.

## What this does, and what it does not

It replaces the **attestation coordinator** on the four Oracle nodes (the researcher and three
validators on `132.145.23.78`) with the one in the committed bundles, which were repacked after #60
(`get_linked_agents_for`). It uses `AdminRequest::UpdateCoordinators` through
`demo/hotswap-coordinators.mjs`, the same tool as the first live swap on 2026-07-08.

- **No DNA-hash change, no container restart, no `down -v`.** Published HarmonyRecord URLs keep
  working. The integrity WASMs in the repacked bundles are byte-identical to the installed ones.
- **It does not add `get_linked_agents_for` to the `public-read` grant.** `init()` wrote that grant
  at the 2026-10-19 install and does not re-run. The node's own callers (the node API and the demo
  bridges, which use signing credentials covering every function) can call the new function. A
  caller relying on `public-read` is refused. Nothing calls it that way today; see
  `PROJECT_STATUS.md`, "What is left", item 4.

⚠️ **Do not use `docs/ORACLE_0.7.1_UPGRADE.md` for this.** Its `down -v` destroys the live network,
and nothing here changes a DNA hash.

## 1. Take the code

```bash
ssh -i ~/.ssh/valichord_oracle opc@132.145.23.78
R=$(for d in /home/*/ValiChord /root/ValiChord /opt/ValiChord; do [ -f "$d/demo/docker-compose.yml" ] && echo "$d"; done)
git -C "$R" status --short            # ANY output: stop and read it first
git -C "$R" pull --ff-only origin main
sha256sum "$R"/valichord/workdir/*.happ
```

**Gate.** The checksums must be exactly:

```
c9ddaaf43dd8148073e820a4f993668312223dfc12392dbd089baa9eb2e9c29e  researcher.happ
1bab687f66d7e6291eaab55210fbb853dc080f6a6455236e8e812044a9a8968b  valichord.happ
1e895bb027286790b5a70b57801053b164616abdcea61d134c2cbb5bf4347081  validator.happ
```

Anything else: stop.

## 2. Find the four node containers

```bash
docker ps --format '{{.Names}}'       # prefix sudo if docker needs it
```

Expect the bootstrap container and the four nodes. With the stack started from `demo/`, the node
names are `demo-researcher-1` and `demo-validator-1-1` to `demo-validator-3-1` (confirmed on the
2026-10-28 run); use what `docker ps` prints.

## 3. Write the two helper scripts on the host

`extract-60.mjs` writes the attestation coordinator out of a bundle and prints its checksum.
`check-60.mjs` calls `get_linked_agents_for` on the node's own attestation cell.

```bash
cat > /tmp/extract-60.mjs <<'EOF'
// Write attestation_coordinator.wasm out of a .happ and print its size and sha256.
// HAPP=/tmp/new.happ OUT=/tmp/attestation_coordinator.wasm node extract-60.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
const { decode } = createRequire(process.env.MODULES_FROM || '/app/demo/')('@msgpack/msgpack');
const happ = decode(gunzipSync(readFileSync(process.env.HAPP)));
const dna = decode(gunzipSync(happ.resources['attestation.dna']));
const wasm = dna.resources['attestation_coordinator.wasm'];
writeFileSync(process.env.OUT, wasm);
console.log(`${wasm.length} bytes sha256=${createHash('sha256').update(wasm).digest('hex')}`);
EOF

cat > /tmp/check-60.mjs <<'EOF'
// After the #60 hot-swap: call get_linked_agents_for on this node's attestation cell.
// ADMIN_PORT=4444 node check-60.mjs   (finds the app the same way hotswap-coordinators.mjs does)
import { pathToFileURL } from 'node:url';
const { AdminWebsocket, AppWebsocket, encodeHashToBase64 } = await import(
  pathToFileURL(process.env.CLIENT_PATH || '/app/demo/node_modules/@holochain/client/lib/index.js').href
);
const admin = await AdminWebsocket.connect({
  url: new URL(`ws://127.0.0.1:${process.env.ADMIN_PORT || 4444}`),
  wsClientOptions: { origin: 'valichord-hotswap' },
});
const app = (await admin.listApps({})).find((a) => a.installed_app_id.startsWith('valichord'));
const info = app.cell_info['attestation']?.[0];
const cell_id = info?.value?.cell_id ?? info?.cell_id;
const port = (await admin.listAppInterfaces())
  .find((i) => i.installed_app_id == null || i.installed_app_id === app.installed_app_id)?.port;
await admin.authorizeSigningCredentials(cell_id);
const { token } = await admin.issueAppAuthenticationToken({
  installed_app_id: app.installed_app_id, single_use: false, expiry_seconds: 0,
});
const ws = await AppWebsocket.connect({
  url: new URL(`ws://127.0.0.1:${port}`), token, wsClientOptions: { origin: 'valichord-hotswap' },
});
const res = await ws.callZome({
  cell_id, zome_name: 'attestation_coordinator', fn_name: 'get_linked_agents_for', payload: cell_id[1],
});
console.log(`${app.installed_app_id}: attestation DNA ${encodeHashToBase64(cell_id[0])}; get_linked_agents_for OK (${res.length} records)`);
await ws.client.close();
await admin.client.close();
process.exit(0);
EOF
```

## 4. Swap the researcher first

```bash
C=demo-researcher-1      # the name docker ps printed
ROLE=researcher
docker cp "$R/valichord/workdir/$ROLE.happ" "$C:/tmp/new.happ"
for f in "$R/demo/hotswap-coordinators.mjs" /tmp/extract-60.mjs /tmp/check-60.mjs; do docker cp "$f" "$C:/tmp/"; done
docker exec -e HAPP=/tmp/new.happ -e OUT=/tmp/attestation_coordinator.wasm "$C" node /tmp/extract-60.mjs
```

**Gate.** It must print exactly
`4056369 bytes sha256=ac2e5f334d9fd4dd6f57d071449ee110efe49094978109cf179b409fcb9330b6`.
Anything else: stop.

```bash
docker exec -e WASM_PATH=/tmp/attestation_coordinator.wasm \
  -e CLIENT_PATH=/app/demo/node_modules/@holochain/client/lib/index.js \
  -e ADMIN_PORT=4444 "$C" node /tmp/hotswap-coordinators.mjs
docker exec -e ADMIN_PORT=4444 "$C" node /tmp/check-60.mjs
```

**Expect** `HOTSWAP COMPLETE`, then
`valichord-…: attestation DNA uhC0kg1-EFqxTnOlNGU98cOHAHhXJkCWQ9eXHi6e9LBCWSy0e_JFI; get_linked_agents_for OK (… records)`.
The DNA hash must be the attestation hash in the
[0.7.1 run record](ORACLE_0.7.1_UPGRADE.md#run-record-2026-10-19). If either command fails, roll
that node back (below) and stop. Rolling back a node that never changed is harmless: it swaps the
old coordinator over itself.

## 5. Then each validator, one at a time

Repeat step 4 with `ROLE=validator` and `C` set to each validator container in turn. Check each
output before starting the next node.

## 6. Afterwards

```bash
for p in 3001 3002 3003 3004; do curl -s "http://localhost:$p/health"; echo; done
```

All four should report `ok`. Then open the live record,
`http://132.145.23.78:3001/record?hash=uhC8kczl-ObcLqHU21FmAnHxOw_qgWEHsq0kBqrOzGenu5bwCXwk-`, and
check it still resolves. Record the result at the end of this file and in `PROJECT_STATUS.md`.
`database is locked` lines in the logs are expected on this host, not a failure.

## Rollback, for one node

The previous coordinator is in the bundles of `376755e`, the ones installed on 2026-10-19.

```bash
git -C "$R" show 376755e:valichord/workdir/$ROLE.happ > /tmp/old-$ROLE.happ
docker cp /tmp/old-$ROLE.happ "$C:/tmp/old.happ"
docker exec -e HAPP=/tmp/old.happ -e OUT=/tmp/old_attestation_coordinator.wasm "$C" node /tmp/extract-60.mjs
# must print: 4053136 bytes sha256=a1db8e0468366813afd6ff000fffbab266e89acad253237b0dd339d9241057be
docker exec -e WASM_PATH=/tmp/old_attestation_coordinator.wasm \
  -e CLIENT_PATH=/app/demo/node_modules/@holochain/client/lib/index.js \
  -e ADMIN_PORT=4444 "$C" node /tmp/hotswap-coordinators.mjs
```

After a rollback, `check-60.mjs` fails with "a zome function that doesn't exist", which is the
pre-#60 state.

## Rehearsal (2026-10-28)

Run by Claude on a throwaway Holochain 0.7.1 conductor, once with `researcher.happ` and once with
`validator.happ`, each as Oracle has them now (the `376755e` bundles, checksums `0af5cc18…` and
`e0ca0912…`). Every command above was run, except the `docker` and `ssh` parts. Each run:

1. **Before the swap:** `get_linked_agents_for` failed with "Attempted to call a zome function that
   doesn't exist".
2. **Extract:** `extract-60.mjs` on the repacked bundle printed the checksum in the gate above.
3. **Swap:** `demo/hotswap-coordinators.mjs`, finding the app the way it will on Oracle, printed
   `HOTSWAP COMPLETE`. `get_my_claimed_studies` worked before and after.
4. **Check:** `check-60.mjs` succeeded, and the attestation DNA hash was the same as before the swap.
5. **Grant:** the `public-read` grant still listed its 21 functions without the new one.
6. **Rollback:** the step above restored the old coordinator, and the function was gone again.

Two differences from Oracle:

- **No IPv6 in the rehearsal container.** Holochain 0.7.1 aborts at startup when `socket(AF_INET6)`
  fails with "address family not supported", so the conductor ran under a small `LD_PRELOAD` shim
  that turned that error into "address not available", the case where it falls back to IPv4.
  Nothing on Oracle needs this.
- **`@msgpack/msgpack`** came from a fresh `npm install` of `@holochain/client` 0.21.1. The image's
  `/app/demo/node_modules` was installed the same way, but it was not checked.

## Run record

### 2026-10-28: done

**First, the server had been frozen for about a week.** From outside, SSH and the node APIs timed
out, although the console showed the instance *Running*. The console's monitoring had stopped at
about the evening of 2026-10-21, for every metric at once. In the day and a half before that, memory
use had climbed steadily from about 48% to about 85%. So the server most likely ran out of memory
and stopped responding. The public demo was down from then until this run, and nothing noticed. A
reboot from the console brought it back (it sat in *Stopping* for several minutes first), and all
five containers restarted by themselves. The journal is not persistent, so no log from before the
reboot survived to confirm the cause.

**Then the runbook, unchanged:**

- **Take the code:** the pull reached `d6b140e`, and the three bundle checksums matched the gate.
- **Helper scripts:** pasted, then checked by sha256 (`6b359f21…` and `76e20b75…`).
- **Extract:** printed the gated checksum on all four nodes. That also confirmed the image has
  `@msgpack/msgpack`.
- **Swap:** researcher first, then validator-1, -2 and -3. Each printed `HOTSWAP COMPLETE`.
  `get_my_claimed_studies` returned the same count before and after: 0 on the researcher, 1 on each
  validator.
- **Check:** `check-60.mjs` succeeded on all four, each reporting attestation DNA `uhC0kg1-EFqx…`,
  the hash in the 0.7.1 run record. The network did not change.
- **Afterwards:** the live record resolved from outside, in a browser: Reproduced, ExactMatch, 3 of
  3 validators.

**Found while doing it:**

1. 🔴 **The memory growth will come back.** At the rate seen, this 6 GB server would freeze again
   within a few days of each restart. The options are in `PROJECT_STATUS.md`, "What is left",
   item 5.
2. **Nobody noticed a week-long outage.** A monitoring alarm on memory, or an outside check of
   `/health`, would have.
3. `docker` works without `sudo` for `opc`.
4. In Windows PowerShell, the last line of a multi-line paste waits for Enter.
