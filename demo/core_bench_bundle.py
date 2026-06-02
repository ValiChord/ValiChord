"""Emit per-validator valichord_attestation bundles from a completed CORE-Bench
commit-reveal round.

Each bundle is a model x task record: the validator's reproduced metrics (from
report.json, via the same extraction as the numeric panel), samples parsed via
EveryEvalEver's InspectAIAdapter, and a meta.attestation_uri pointing at the
shared HarmonyRecord. Opt-in (called by core_bench_runner only under
--emit-bundles); a derived artifact that never affects the committed record."""
import json
import tempfile
from pathlib import Path

from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    _INSPECT_VERSION = _pkg_version("inspect_ai")
except PackageNotFoundError:  # pragma: no cover
    _INSPECT_VERSION = "unknown"

from valichord_attestation import build_bundle, hash_bundle, merkle_proof
from valichord_attestation.canonical import bundle_to_dict
from inspect_evals.core_bench.dataset import CAPSULE_CHECKSUMS

from report_to_verdict import build_numeric_panel

EEE_COMMIT = "dec1ae43e0741a37003425eafe6699d3296145ec"
EEE_INSTALL = (
    "every-eval-ever[inspect] @ "
    f"git+https://github.com/evaleval/every_eval_ever.git@{EEE_COMMIT}"
)
TASK_PREFIX = "inspect_evals/core_bench"


def _metrics_from_report(label, report, committed_claim):
    """raw_metrics for build_bundle from this validator's reproduced values,
    using the same extraction as build_numeric_panel (so the bundle's metrics
    equal the panel's values by construction). Skips keys the validator did not
    produce a parseable number for."""
    rows = build_numeric_panel([(label, report)], committed_claim)[0]["rows"]
    return [
        {"key": row["question"], "value": round(float(row["value"]), 6)}
        for row in rows if row["value"] is not None
    ]


def _eee_adapter():
    """Return an EEE InspectAIAdapter; raise a clear, actionable error if EEE is
    not installed. Isolated so unit tests can patch it."""
    try:
        from every_eval_ever.converters.inspect.adapter import InspectAIAdapter
    except ImportError as e:
        raise RuntimeError(
            "every-eval-ever[inspect] is required for --emit-bundles.\n"
            f"Install: pip install '{EEE_INSTALL}'"
        ) from e
    return InspectAIAdapter(strict_validation=False)


def _samples_from_eee_log(eval_log_path):
    """Parse a CORE-Bench .eval log into bundle samples via EEE's
    InspectAIAdapter. Real EEE call; unit tests monkeypatch this function.

    Records are ordered by numeric sample_id when possible (matching EEE's
    canonical extract_bundle_samples_from_eee), so outputs_merkle_root is
    stable regardless of JSONL file/line order."""
    adapter = _eee_adapter()
    records = []
    with tempfile.TemporaryDirectory() as tmpdir:
        adapter.transform_from_file(
            str(eval_log_path),
            metadata_args={
                "source_organization_name": "valichord_core_bench_demo",
                "evaluator_relationship": "third_party",
                "parent_eval_output_dir": tmpdir,
                "file_uuid": "valichord",
            },
        )
        for jf in sorted(Path(tmpdir).rglob("*.jsonl")):
            for line in jf.read_text().splitlines():
                if line.strip():
                    records.append(json.loads(line))

    def _sort_key(rec):
        sid = rec.get("sample_id", "")
        try:
            return (0, int(sid))
        except (ValueError, TypeError):
            return (1, str(sid))

    samples = []
    for rec in sorted(records, key=_sort_key):
        inp = rec.get("input") or {}
        out = rec.get("output") or {}
        ev = rec.get("evaluation") or {}
        reference = inp.get("reference") or []
        raw_outputs = out.get("raw") or []
        samples.append({
            "sample_id": rec.get("sample_id"),
            "input": (inp.get("raw") or "")[:200].strip(),
            "target": reference[0].strip() if reference else "",
            "model_answer": raw_outputs[0].strip() if raw_outputs else "",
            "correct": bool(ev.get("is_correct", False)),
        })
    return samples


def build_one_bundle(*, capsule_id, researcher_model, validator_model, label,
                     report, committed_claim, eval_log_path, result):
    """Return (bundle, samples) for one validator reproduction."""
    raw_metrics = _metrics_from_report(label, report, committed_claim)
    samples = _samples_from_eee_log(eval_log_path)
    meta = {
        "protocol": "valichord-commit-reveal",
        "attestation_uri": result["record_url"],
        "harmony_record_hash": result["harmony_record_hash"],
        "external_hash_b64": result["external_hash_b64"],
        "outcome": result["outcome"],
        "agreement_level": result["agreement_level"],
        "committed_claim": committed_claim,
        "capsule_id": capsule_id,
        "capsule_checksum": CAPSULE_CHECKSUMS[capsule_id],
        "researcher_model": researcher_model,
        "validator_model": validator_model,
        "validator_label": label,
        "eee_commit": EEE_COMMIT,
    }
    bundle = build_bundle(
        model_id=validator_model,
        task_id=f"{TASK_PREFIX}:{capsule_id}",
        raw_metrics=raw_metrics,
        samples=samples,
        harness_version=f"inspect_ai=={_INSPECT_VERSION}",
        meta=meta,
    )
    return bundle, samples


def emit_core_bench_bundles(*, capsule_id, researcher_model, validator_models,
                            validator_reports, validator_eval_logs, result, out_dir):
    """Write one bundle JSON per validator into out_dir. Returns the paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    committed_claim = result["committed_claim"]
    n = len(validator_reports)
    if not (len(validator_models) >= n and len(validator_eval_logs) >= n):
        raise ValueError(
            f"emit_core_bench_bundles: need >= {n} models and eval-log paths, "
            f"got {len(validator_models)} models and {len(validator_eval_logs)} logs"
        )
    paths = []
    for i, (label, report) in enumerate(validator_reports):
        validator_model = validator_models[i]
        bundle, samples = build_one_bundle(
            capsule_id=capsule_id, researcher_model=researcher_model,
            validator_model=validator_model, label=label, report=report,
            committed_claim=committed_claim,
            eval_log_path=validator_eval_logs[i], result=result,
        )
        wrapper = {
            "_source": {
                "note": (
                    f"CORE-Bench {capsule_id} reproduced by {validator_model}; "
                    "metrics from validator report.json, samples via EEE "
                    f"InspectAIAdapter @ {EEE_COMMIT[:12]}; "
                    "attestation_uri -> HarmonyRecord."
                ),
                "eee_commit": EEE_COMMIT,
                "bundle_sha256": hash_bundle(bundle),
                "sample_0_proof": merkle_proof(samples, 0),
            },
            "bundle": bundle_to_dict(bundle),
            "samples": samples,
        }
        safe_model = validator_model.replace("/", "_")
        p = out_dir / f"bundle_{capsule_id}_{safe_model}.json"
        p.write_text(json.dumps(wrapper, indent=2) + "\n")
        paths.append(p)
    return paths
