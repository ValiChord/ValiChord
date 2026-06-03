import json
import pytest

pytest.importorskip("valichord_attestation")
pytest.importorskip("inspect_evals")  # core_bench_bundle imports CAPSULE_CHECKSUMS
import core_bench_bundle as cbb


_CLAIM = {
    "Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"},
    "R": {"value": 0.5, "lower": 0.49, "upper": 0.51, "basis": "explicit_tolerance"},
}


def test_metrics_from_report_uses_panel_values():
    report = {"Q": 96.125, "R": "0.5"}
    metrics = cbb._metrics_from_report("V1", report, _CLAIM)
    assert {"key": "Q", "value": 96.125} in metrics
    assert {"key": "R", "value": 0.5} in metrics


def test_metrics_from_report_skips_missing_keys():
    report = {"Q": 96.125}  # R absent
    metrics = cbb._metrics_from_report("V1", report, _CLAIM)
    assert metrics == [{"key": "Q", "value": 96.125}]


def _result():
    return {
        "record_url": "http://oracle/record?hash=uhC8kEXT",
        "harmony_record_hash": "uhC8kHARM",
        "external_hash_b64": "uhC8kEXT",
        "outcome": "Reproduced",
        "agreement_level": "ExactMatch",
        "committed_claim": _CLAIM,
    }


def test_emit_writes_one_bundle_per_validator(tmp_path, monkeypatch):
    monkeypatch.setattr(cbb, "_samples_from_eee_log",
                        lambda path: [{"sample_id": "1", "input": "i",
                                       "target": "t", "model_answer": "a", "correct": True}])
    validator_reports = [("V1-opus", {"Q": 96.125, "R": 0.5}),
                         ("V2-gpt", {"Q": 96.13, "R": 0.5}),
                         ("V3-gemini", {"Q": 96.12, "R": 0.5})]
    paths = cbb.emit_core_bench_bundles(
        capsule_id="capsule-0851068",
        researcher_model="anthropic/claude-opus-4-8",
        validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-2.5-pro"],
        validator_reports=validator_reports,
        validator_eval_logs=["/l/v1.eval", "/l/v2.eval", "/l/v3.eval"],
        result=_result(),
        out_dir=tmp_path,
    )
    assert len(paths) == 3
    doc = json.loads(paths[0].read_text())
    assert doc["bundle"]["model_id"] == "anthropic/claude-opus-4-8"
    assert doc["bundle"]["task_id"] == "inspect_evals/core_bench:capsule-0851068"
    assert doc["bundle"]["meta"]["attestation_uri"] == "http://oracle/record?hash=uhC8kEXT"
    assert doc["bundle"]["meta"]["validator_model"] == "anthropic/claude-opus-4-8"
    assert doc["samples"]  # non-empty
    assert len(doc["_source"]["bundle_sha256"]) == 64
    assert doc["bundle"]["harness_version"].startswith("inspect_ai==")
    assert "sample_0_proof" in doc["_source"]
    names = sorted(p.name for p in paths)
    assert names == [
        "bundle_capsule-0851068_v1_anthropic_claude-opus-4-8.json",
        "bundle_capsule-0851068_v2_openai_gpt-4o.json",
        "bundle_capsule-0851068_v3_google_gemini-2.5-pro.json",
    ]


def test_emit_same_model_round_writes_distinct_files(tmp_path, monkeypatch):
    """A same-model round must still write one distinct file per validator.

    Regression: filenames were keyed by model alone, so three sonnet validators
    collided onto one path and only the last bundle survived on disk."""
    monkeypatch.setattr(cbb, "_samples_from_eee_log",
                        lambda path: [{"sample_id": "1", "input": "i",
                                       "target": "t", "model_answer": "a", "correct": True}])
    model = "anthropic/claude-sonnet-4-6"
    validator_reports = [("V1-sonnet", {"Q": 96.125, "R": 0.5}),
                         ("V2-sonnet", {"Q": 96.13, "R": 0.5}),
                         ("V3-sonnet", {"Q": 96.12, "R": 0.5})]
    paths = cbb.emit_core_bench_bundles(
        capsule_id="capsule-0851068",
        researcher_model=model,
        validator_models=[model, model, model],
        validator_reports=validator_reports,
        validator_eval_logs=["/l/v1.eval", "/l/v2.eval", "/l/v3.eval"],
        result=_result(),
        out_dir=tmp_path,
    )
    names = sorted(p.name for p in paths)
    assert len(names) == 3
    assert len(set(names)) == 3, f"filenames collided: {names}"
    assert all(p.exists() for p in paths)          # none overwritten
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_samples_from_eee_log_maps_jsonl(monkeypatch):
    """_samples_from_eee_log drives EEE's adapter, which writes per-sample JSONL
    into parent_eval_output_dir; we map those records to bundle samples."""
    from pathlib import Path as _P

    class FakeAdapter:
        def transform_from_file(self, path, metadata_args=None):
            outdir = _P(metadata_args["parent_eval_output_dir"])
            rec = {
                "sample_id": "1",
                "input": {"raw": "compute the AUC", "reference": ["0.9158"]},
                "output": {"raw": ["0.9158"]},
                "evaluation": {"is_correct": True},
            }
            (outdir / "samples.jsonl").write_text(json.dumps(rec) + "\n")
            return object()

    monkeypatch.setattr(cbb, "_eee_adapter", lambda: FakeAdapter())
    samples = cbb._samples_from_eee_log("/ignored/path.eval")
    assert samples == [{
        "sample_id": "1",
        "input": "compute the AUC",
        "target": "0.9158",
        "model_answer": "0.9158",
        "correct": True,
    }]


def test_samples_from_eee_log_orders_by_numeric_sample_id(monkeypatch):
    from pathlib import Path as _P

    class FakeAdapter:
        def transform_from_file(self, path, metadata_args=None):
            outdir = _P(metadata_args["parent_eval_output_dir"])
            lines = []
            for sid in ("10", "2", "1"):
                lines.append(json.dumps({
                    "sample_id": sid,
                    "input": {"raw": f"q{sid}", "reference": ["t"]},
                    "output": {"raw": ["a"]},
                    "evaluation": {"is_correct": True},
                }))
            (outdir / "samples.jsonl").write_text("\n".join(lines) + "\n")
            return object()

    monkeypatch.setattr(cbb, "_eee_adapter", lambda: FakeAdapter())
    samples = cbb._samples_from_eee_log("/ignored.eval")
    assert [s["sample_id"] for s in samples] == ["1", "2", "10"]


def test_eee_adapter_raises_actionable_error_when_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def blocked_import(name, *a, **k):
        if name.startswith("every_eval_ever"):
            raise ImportError("no every_eval_ever")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(RuntimeError) as exc:
        cbb._eee_adapter()
    assert "every-eval-ever" in str(exc.value) and "pip install" in str(exc.value)
