"""Step 2 — the pre-registration record, canonicalised and hashed.

Fixed and hashed BEFORE any party runs anything. See plan §3.2.

`lambda_rule` is the load-bearing field. Pre-registering a *rule* rather than a
*value* is what forecloses lambda-shopping: each party derives their own lambda
from their own resample by the agreed procedure. `lambda_rule_impl_hash` is what
stops that guarantee being prose only — it pins the rule as executable code.

Canonicalisation uses JCS (RFC 8785) via the same `jcs` dependency the
valichord_attestation library uses, so the protocol hash is computed the same
way bundle hashes are.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jcs

import lambda_rule
from generate import SPEC, feature_names, write_dataset

N_VALIDATORS = 5
RESAMPLE_SCHEME = "bootstrap, n=500, with replacement"
SUPPORT_DEFINITION = "coef != 0"
ESTIMATOR = "sklearn.linear_model.LassoCV"

# Pre-registered bundle timestamp. `generated_at` is a top-level Bundle field
# and therefore inside content_hash — if each party let it default to wall-clock
# now(), no two parties could ever share a content_hash however identical their
# results. Fixing it here, in the pre-registration, is what makes the
# "same features selected?" comparison possible at all. See plan §3.5.
BUNDLE_GENERATED_AT = "2026-07-27T00:00:00+00:00"


def build_protocol(dataset_hash: str) -> dict:
    """Assemble the pre-registration record.

    Every field here is fixed before any resampling happens. Nothing derived
    from a run may enter this dict — that is the entire point of the artefact.
    """
    return {
        "dataset_hash": dataset_hash,
        "estimator": ESTIMATOR,
        "lambda_rule": lambda_rule.LAMBDA_RULE_DESCRIPTION,
        "lambda_rule_impl_hash": lambda_rule.impl_hash(),
        "resample_scheme": RESAMPLE_SCHEME,
        "n_validators": N_VALIDATORS,
        "support_definition": SUPPORT_DEFINITION,
        "feature_names": feature_names(),
        "cv_folds": lambda_rule.CV_FOLDS,
        "bundle_generated_at": BUNDLE_GENERATED_AT,
    }


def protocol_hash(protocol: dict) -> str:
    """SHA-256 over the JCS-canonical encoding of the protocol record."""
    raw = jcs.canonicalize(protocol)
    encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_protocol(out_dir: Path) -> dict:
    """Generate the dataset, build the pre-registration, hash it, persist it."""
    manifest = write_dataset(out_dir, SPEC)
    protocol = build_protocol(manifest["dataset_hash"])
    digest = protocol_hash(protocol)

    record = {"protocol": protocol, "protocol_hash": digest}
    (out_dir / "protocol.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )
    return record


def load_protocol(out_dir: Path) -> dict:
    """Read protocol.json back, re-verifying its hash and the rule's source.

    Two checks, both of which must hold before any party is allowed to run:
      1. the recorded protocol_hash still matches the recorded protocol
      2. lambda_rule.py on disk still hashes to the recorded impl hash

    The second is the one that matters. Without it, the pre-registration says
    "we used the 1-SE rule" while the code on disk says something else, and
    nothing detects the difference.
    """
    record = json.loads((out_dir / "protocol.json").read_text())
    protocol = record["protocol"]

    recomputed = protocol_hash(protocol)
    if recomputed != record["protocol_hash"]:
        raise ValueError(
            f"protocol hash mismatch: recorded {record['protocol_hash']}, recomputed {recomputed}"
        )

    current_impl = lambda_rule.impl_hash()
    if current_impl != protocol["lambda_rule_impl_hash"]:
        raise ValueError(
            "lambda_rule.py has changed since pre-registration: "
            f"recorded {protocol['lambda_rule_impl_hash']}, current {current_impl}"
        )

    return record


def main() -> None:
    out_dir = Path(__file__).parent / "artifacts"
    record = write_protocol(out_dir)

    print("Pre-registration fixed before any party runs:")
    for key, value in sorted(record["protocol"].items()):
        if key == "feature_names":
            value = f"[{len(value)} names: {value[0]} … {value[-1]}]"
        print(f"  {key}: {value}")
    print(f"\nprotocol_hash: {record['protocol_hash']}")


if __name__ == "__main__":
    main()
