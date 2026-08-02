#!/usr/bin/env node
// pack-coordinators.mjs — Phase 1 of the coordinator auto-updater.
// Plan: docs/AUTO_UPDATER_SIDECAR_PLAN.md
//
// Produces a `coordinators-manifest.json` plus the raw coordinator WASMs,
// ready to be published as GitHub release assets. The manifest carries a
// monotonic `revision`, the pinned conductor version, and a sha256 over each
// raw WASM — the exact bytes the apply step consumes.
//
// The apply step (AdminRequest::UpdateCoordinators, see hotswap-coordinators.mjs)
// wraps the RAW coordinator WASM in an inline bundle:
//   manifest.zomes = [{ name, path, dependencies: [{ name: <integrity> }] }]
//   resources[path] = <wasm bytes>
// so the manifest records exactly {name (zome), integrity (dep), wasm (path),
// sha256} per cell — everything Phase 2 needs to rebuild that bundle and verify
// the download before applying it. NOTE: this is a raw WASM, NOT an
// `hc dna pack --coordinator-only` bundle.
//
// BUILD-SIDE TOOL ONLY. Reads built WASMs, writes output files. Never connects
// to a conductor. Never touches the running demo. No npm dependencies.
//
// Usage:
//   node demo/pack-coordinators.mjs [options]
//
// Options:
//   --wasm-dir <dir>   built WASM dir
//                      (default: valichord/target/wasm32-unknown-unknown/release)
//   --out <dir>        output dir (default: demo/coordinator-updates)
//   --revision <N>     manifest revision
//                      (default: existing revision in --out + 1, else 1)
//   --holochain <ver>  conductor version to pin
//                      (default: detected via `holochain --version`, else 0.6.2)
//   --only <roles>     comma-separated subset of roles (default: all four)
//   --dry-run          print the manifest, write nothing

import {
  readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync,
} from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// Coordinator map. Source of truth is each dnas/<role>/**/dna.yaml
// `coordinator.zomes` block. Kept explicit (only four stable DNAs) so the tool
// needs no YAML parser. If a DNA's coordinator zome or integrity dep is ever
// renamed, update it here.
const COORDINATORS = [
  { role: 'attestation',           zome: 'attestation_coordinator',           integrity: 'attestation_integrity' },
  { role: 'governance',            zome: 'governance_coordinator',            integrity: 'governance_integrity' },
  { role: 'researcher_repository', zome: 'researcher_repository_coordinator', integrity: 'researcher_repository_integrity' },
  { role: 'validator_workspace',   zome: 'validator_workspace_coordinator',   integrity: 'validator_workspace_integrity' },
];

// Fallback only — the version is normally detected from `holochain --version`.
// It pins the conductor version the manifest is valid for, and the updater
// refuses to apply a manifest whose pin does not match the running conductor,
// so a stale value here fails closed rather than dangerously. Bumped with the
// 0.7 migration. ⚠️ The auto-updater has NOT been re-rehearsed on 0.7 —
// see Holochain_complete.md §44.8.
const DEFAULT_HOLOCHAIN = '0.7.0';
const SCHEMA = 'valichord-coordinators-manifest/v1';

// ── arg parsing ───────────────────────────────────────────────────────────────
const argVal = (name, def) => {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
};
const hasFlag = (name) => process.argv.includes(name);

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const wasmDir = resolve(argVal('--wasm-dir', join(repoRoot, 'valichord/target/wasm32-unknown-unknown/release')));
const outDir = resolve(argVal('--out', join(repoRoot, 'demo/coordinator-updates')));
const dryRun = hasFlag('--dry-run');
const onlyArg = argVal('--only', null);
const only = onlyArg ? new Set(onlyArg.split(',').map((s) => s.trim()).filter(Boolean)) : null;

if (only) {
  const unknown = [...only].filter((r) => !COORDINATORS.some((c) => c.role === r));
  if (unknown.length) {
    console.error(`[error] unknown role(s): ${unknown.join(', ')}`);
    console.error(`        valid roles: ${COORDINATORS.map((c) => c.role).join(', ')}`);
    process.exit(1);
  }
}

// ── holochain version to pin ────────────────────────────────────────────────────
function detectHolochain() {
  const explicit = argVal('--holochain', null);
  if (explicit) return explicit;
  try {
    const out = execFileSync('holochain', ['--version'], { encoding: 'utf8' }).trim();
    const m = out.match(/(\d+\.\d+\.\d+)/);
    if (m) return m[1];
  } catch { /* holochain not on PATH — fall through */ }
  console.warn(`[warn] could not detect holochain version; defaulting to ${DEFAULT_HOLOCHAIN} (override with --holochain)`);
  return DEFAULT_HOLOCHAIN;
}

// ── revision (monotonic) ────────────────────────────────────────────────────────
const manifestPath = join(outDir, 'coordinators-manifest.json');
function nextRevision() {
  const explicit = argVal('--revision', null);
  if (explicit != null) {
    const n = Number(explicit);
    if (!Number.isInteger(n) || n < 1) {
      console.error('[error] --revision must be a positive integer');
      process.exit(1);
    }
    return n;
  }
  if (existsSync(manifestPath)) {
    try {
      const prev = JSON.parse(readFileSync(manifestPath, 'utf8'));
      if (Number.isInteger(prev.revision)) return prev.revision + 1;
    } catch { /* malformed prior manifest — start fresh */ }
  }
  return 1;
}

// ── build the manifest ──────────────────────────────────────────────────────────
const holochain = detectHolochain();
const revision = nextRevision();
const selected = COORDINATORS.filter((c) => !only || only.has(c.role));
if (selected.length === 0) {
  console.error('[error] no coordinators selected');
  process.exit(1);
}

const cells = [];
const toCopy = [];
for (const c of selected) {
  const wasmName = `${c.zome}.wasm`;
  const src = join(wasmDir, wasmName);
  if (!existsSync(src)) {
    console.error(`[error] missing WASM: ${src}`);
    console.error('        build first: (cd valichord && cargo build --target wasm32-unknown-unknown --release)');
    process.exit(1);
  }
  const bytes = readFileSync(src);
  const sha256 = createHash('sha256').update(bytes).digest('hex');
  cells.push({
    role: c.role,
    zomes: [{ name: c.zome, integrity: c.integrity, wasm: wasmName, sha256, bytes: bytes.length }],
  });
  toCopy.push({ src, dest: join(outDir, wasmName) });
}

const manifest = { schema: SCHEMA, revision, holochain, generated_at: new Date().toISOString(), cells };

// ── report ──────────────────────────────────────────────────────────────────────
console.log(`\ncoordinators-manifest revision ${revision}  (holochain ${holochain})`);
for (const cell of cells) {
  for (const z of cell.zomes) {
    console.log(`  ${cell.role.padEnd(22)} ${z.wasm.padEnd(40)} ${String(Math.round(z.bytes / 1024)).padStart(5)} KB  sha256:${z.sha256.slice(0, 12)}…`);
  }
}

if (dryRun) {
  console.log('\n[dry-run] nothing written. Manifest would be:\n');
  console.log(JSON.stringify(manifest, null, 2));
  process.exit(0);
}

// ── write ─────────────────────────────────────────────────────────────────────
mkdirSync(outDir, { recursive: true });
// Self-contained ignore so generated binaries + manifest never get committed
// (they are published as GitHub release assets). Only this .gitignore is tracked.
const ignorePath = join(outDir, '.gitignore');
if (!existsSync(ignorePath)) {
  writeFileSync(
    ignorePath,
    '# Generated coordinator-update artifacts (WASMs + manifest) — published as\n'
    + '# GitHub release assets, never committed. See docs/AUTO_UPDATER_SIDECAR_PLAN.md\n'
    + '*\n!.gitignore\n',
  );
}
for (const { src, dest } of toCopy) copyFileSync(src, dest);
writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);

console.log(`\nwrote ${manifestPath}`);
console.log(`wrote ${toCopy.length} WASM(s) to ${outDir}`);
console.log('\nNext: publish these as a GitHub release asset; Phase 2 polls the manifest.');
