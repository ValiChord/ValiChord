"""Run PiSessionAdapter over a directory of REAL pi session files and report.

Why (2026-10-19): the adapter's tests use hand-built fixtures only. The pi
project publishes real sessions on Hugging Face (dataset
``badlogicgames/pi-mono``), so this checks the adapter against data it did not
write. Usage::

    python scripts/check_pi_real_sessions.py <dir-with-.jsonl-files>

Prints a summary and exits non-zero only if the script itself breaks; adapter
failures are findings to read, not a crash. It never prints session content —
only entry types, counts and error classes — because sessions are other
people's work.
"""
from __future__ import annotations

import collections
import json
import random
import sys
import traceback
from pathlib import Path

from valichord_attestation import content_hash, hash_bundle
from valichord_attestation.adapters import PiSessionAdapter
from valichord_attestation.adapters import pi_session_adapter as psa
from valichord_attestation.merkle import merkle_proof, merkle_root, verify_faithfulness

# Entry types and message roles the adapter's code explicitly handles.
KNOWN_ENTRY_TYPES = {"session", "message", "model_change", "session_info", "compaction"}
KNOWN_ROLES = {"user", "assistant", "toolResult"}


def main(root: Path) -> int:
    files = sorted(root.rglob("*.jsonl"))
    print(f"sessions found: {len(files)}")
    rng = random.Random(20261019)
    adapter = PiSessionAdapter()

    outcome = collections.Counter()
    errors = collections.Counter()
    error_examples: dict[str, str] = {}
    versions = collections.Counter()
    entry_types = collections.Counter()
    roles = collections.Counter()
    unknown_types = collections.Counter()
    unknown_roles = collections.Counter()
    metric_problems = collections.Counter()
    proofs_checked = proofs_failed = 0
    nondeterministic = root_mismatch = 0
    branch_ratio: list[float] = []

    for f in files:
        # Survey raw entry types first, independent of the adapter.
        try:
            lines = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        except Exception as e:  # unreadable file: a finding about the data, not the adapter
            outcome["unreadable_json"] += 1
            errors[f"json:{type(e).__name__}"] += 1
            continue
        if lines and isinstance(lines[0], dict):
            versions[str(lines[0].get("version", "none"))] += 1
        for e in lines:
            if not isinstance(e, dict):
                continue
            t = e.get("type")
            entry_types[t] += 1
            if t not in KNOWN_ENTRY_TYPES:
                unknown_types[t] += 1
            if t == "message" and isinstance(e.get("message"), dict):
                r = e["message"].get("role")
                roles[r] += 1
                if r not in KNOWN_ROLES:
                    unknown_roles[r] += 1

        try:
            b1 = adapter.to_bundle(f, repo_commit="")
            b2 = adapter.to_bundle(f, repo_commit="")
        except Exception as e:
            key = f"{type(e).__name__}: {str(e)[:120]}"
            errors[key] += 1
            error_examples.setdefault(key, f.name)
            outcome["adapter_error"] += 1
            continue
        outcome["ok"] += 1

        if hash_bundle(b1) != hash_bundle(b2) or content_hash(b1) != content_hash(b2):
            nondeterministic += 1

        for m in b1.metrics:
            v = m.value
            if v is None or v != v or v < 0:  # None, NaN or negative
                metric_problems[m.key] += 1

        # Rebuild the leaves the adapter committed to (every line of the file since
        # 2026-10-19) and check the root + sample proofs.
        header, entries = psa._parse_session(f)
        branch = psa._resolve_branch(header, entries)
        leaves = psa._file_leaves(f)
        branch_ratio.append(len(branch) / max(1, len(entries)))
        fv = b1.format_version
        if merkle_root(leaves, format_version=fv) != b1.outputs_merkle_root:
            root_mismatch += 1
            continue
        for i in rng.sample(range(len(leaves)), min(3, len(leaves))):
            proofs_checked += 1
            proof = merkle_proof(leaves, i, format_version=fv)
            if not verify_faithfulness(b1.outputs_merkle_root, i, leaves[i], proof, format_version=fv):
                proofs_failed += 1

    print("\n== outcome")
    for k, v in outcome.most_common():
        print(f"  {k}: {v}")
    print("\n== adapter errors (class: message) — count — example file")
    for k, v in errors.most_common(15):
        print(f"  {v:4d}  {k}  [{error_examples.get(k, '')}]")
    print("\n== session header versions:", dict(versions))
    print("== entry types:", dict(entry_types.most_common()))
    print("== message roles:", dict(roles.most_common()))
    print("== entry types the adapter does not name:", dict(unknown_types.most_common()))
    print("== message roles the adapter does not name:", dict(unknown_roles.most_common()))
    print("== metrics that were None/NaN/negative:", dict(metric_problems))
    print(f"== nondeterministic bundles: {nondeterministic}")
    print(f"== Merkle root != rebuilt leaves: {root_mismatch}")
    print(f"== sample proofs checked: {proofs_checked}, failed: {proofs_failed}")
    if branch_ratio:
        branch_ratio.sort()
        mid = branch_ratio[len(branch_ratio) // 2]
        print(f"== active-branch share of entries (all lines are now committed regardless): min {branch_ratio[0]:.2f}, median {mid:.2f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(Path(sys.argv[1])))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
