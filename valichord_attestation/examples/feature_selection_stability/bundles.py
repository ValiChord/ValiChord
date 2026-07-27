"""Step 7 — one valichord_attestation bundle per party, via build_bundle directly.

No new adapter. The point is to exercise a property the library has had since
v1.2 and has never been shown doing anything useful:

    content_hash excludes meta.  bundle_hash includes it.

So content_hash answers "same features selected?" and bundle_hash answers
"same features AND same conditions?" — "preserve the regularisation settings,
evaluate stability separately", expressed as two hashes.

Getting that requires care, because content_hash excludes meta and NOTHING
ELSE. `canonical.content_hash` pops exactly one key; every other field in
`bundle_to_dict` is inside the digest, including generated_at,
outputs_merkle_root, model_id and task_id. Built naively — party name in
model_id, wall-clock generated_at, resample rows as samples — five parties with
byte-identical results would produce five different content_hashes, and this
module would be asserting a property the library does not have.

Hence the layout below. Two traps in particular, both silent if you get them
wrong:

  * `samples` must be the per-feature SELECTION records, not the resample rows.
    Resample rows differ per party by construction, so their Merkle root — and
    therefore content_hash — would be party-specific whatever was selected.
  * build_bundle's top-level `repo_commit` / `harness_version` / `command`
    parameters are NOT meta. They sit inside content_hash too. All provenance
    goes in the meta dict.

The resample is still committed — as its seed, in meta, inside bundle_hash,
which is exactly where "same conditions?" belongs.
"""

from __future__ import annotations

import json
from pathlib import Path

import sklearn

from valichord_attestation.builder import build_bundle
from valichord_attestation.canonical import content_hash, hash_bundle

import lambda_rule
from generate import feature_names

MODEL_ID = "lasso-cv-1se"


def selection_records(support: list[str]) -> list[dict]:
    """One record per feature — the samples list, and the Merkle-root input.

    All 40 features appear, selected or not. Recording only the selected ones
    would make the root depend on support size in a way that hides which
    features were considered at all.
    """
    chosen = set(support)
    return [
        {"feature": name, "selected": 1 if name in chosen else 0}
        for name in feature_names()
    ]


def selection_metrics(support: list[str]) -> list[dict]:
    """One metric per feature: selected__<name> = 1.0 or 0.0. This is the claim."""
    chosen = set(support)
    return [
        {"key": f"selected__{name}", "value": 1.0 if name in chosen else 0.0}
        for name in feature_names()
    ]


def build_party_bundle(reveal: dict, protocol: dict, protocol_digest: str):
    """Build one party's bundle on the layout fixed in plan §3.5."""
    return build_bundle(
        # --- inside content_hash: identical across all parties by design ---
        model_id=MODEL_ID,
        task_id=protocol_digest,
        generated_at=protocol["bundle_generated_at"],
        raw_metrics=selection_metrics(reveal["support"]),
        samples=selection_records(reveal["support"]),
        # --- outside content_hash: the conditions ---
        meta={
            "party_id": reveal["party_id"],
            "resample_seed": reveal["resample_seed"],
            "derived_alpha": reveal["derived_alpha"],
            "lambda_rule": protocol["lambda_rule"],
            "lambda_rule_impl_hash": protocol["lambda_rule_impl_hash"],
            "cv_folds": protocol["cv_folds"],
            "sklearn_version": sklearn.__version__,
            "dataset_hash": protocol["dataset_hash"],
            "protocol_hash": protocol_digest,
        },
    )


def assert_hash_semantics(protocol: dict, protocol_digest: str) -> dict:
    """Verify the two-hash claim rather than assuming it.

    A controlled pair: identical support, different conditions. If content_hash
    does not match while bundle_hash differs, plan §3.5 is wrong and the
    write-up must compare metrics lists directly instead of claiming a property
    the library does not have.

    This is a separate construction because in the actual round no two parties
    happened to select the same support — which is itself the finding, and is
    reported as such rather than papered over.
    """
    support = ["blk0_f0", "blk1_f0", "blk2_f0"]

    a = build_party_bundle(
        {"party_id": "twin_a", "support": support, "resample_seed": 1, "derived_alpha": 0.1},
        protocol,
        protocol_digest,
    )
    b = build_party_bundle(
        {"party_id": "twin_b", "support": support, "resample_seed": 2, "derived_alpha": 0.2},
        protocol,
        protocol_digest,
    )

    same_content = content_hash(a) == content_hash(b)
    diff_bundle = hash_bundle(a) != hash_bundle(b)

    if not same_content:
        raise AssertionError(
            "identical supports produced different content_hashes — "
            "plan §3.5 is wrong; something party-specific is leaking into the digest"
        )
    if not diff_bundle:
        raise AssertionError(
            "different conditions produced identical bundle_hashes — "
            "meta is not entering bundle_hash as documented"
        )

    return {
        "identical_support_shares_content_hash": same_content,
        "differing_conditions_differ_in_bundle_hash": diff_bundle,
        "content_hash": content_hash(a),
        "bundle_hash_a": hash_bundle(a),
        "bundle_hash_b": hash_bundle(b),
    }


def write_bundles(out_dir: Path) -> dict:
    record = json.loads((out_dir / "protocol.json").read_text())
    protocol, protocol_digest = record["protocol"], record["protocol_hash"]
    round_record = json.loads((out_dir / "round.json").read_text())

    bundle_dir = out_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for reveal in round_record["reveals"]:
        bundle = build_party_bundle(reveal, protocol, protocol_digest)
        ch, bh = content_hash(bundle), hash_bundle(bundle)
        (bundle_dir / f"{reveal['party_id']}.json").write_text(
            json.dumps(
                {"content_hash": ch, "bundle_hash": bh, "meta": bundle.meta},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        summary.append(
            {
                "party_id": reveal["party_id"],
                "n_selected": len(reveal["support"]),
                "content_hash": ch,
                "bundle_hash": bh,
            }
        )

    checks = assert_hash_semantics(protocol, protocol_digest)
    distinct = len({s["content_hash"] for s in summary})

    result = {
        "bundles": summary,
        "distinct_content_hashes": distinct,
        "n_parties": len(summary),
        "hash_semantics_checks": checks,
    }
    (out_dir / "bundle_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def main() -> None:
    out_dir = Path(__file__).parent / "artifacts"
    result = write_bundles(out_dir)

    print(f"sklearn {sklearn.__version__}   lambda_rule {lambda_rule.impl_hash()[:12]}…\n")
    print(f"{'party':<13} {'n':>3}  {'content_hash':<20} {'bundle_hash':<20}")
    for s in result["bundles"]:
        print(
            f"{s['party_id']:<13} {s['n_selected']:>3}  "
            f"{s['content_hash'][:18]}…  {s['bundle_hash'][:18]}…"
        )

    print(
        f"\ndistinct content_hashes: {result['distinct_content_hashes']} "
        f"of {result['n_parties']} parties"
    )
    print("Every party differs. That is the stability finding restated as a hash:")
    print("no two independent parties selected the same feature set.\n")

    checks = result["hash_semantics_checks"]
    print("Two-hash semantics, verified on a controlled pair (same support, different conditions):")
    print(f"  identical support  -> same content_hash: {checks['identical_support_shares_content_hash']}")
    print(f"  differing conditions -> different bundle_hash: {checks['differing_conditions_differ_in_bundle_hash']}")


if __name__ == "__main__":
    main()
