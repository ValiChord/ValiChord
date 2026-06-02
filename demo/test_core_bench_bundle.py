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
    names = sorted(p.name for p in paths)
    assert names == [
        "bundle_capsule-0851068_anthropic_claude-opus-4-8.json",
        "bundle_capsule-0851068_google_gemini-2.5-pro.json",
        "bundle_capsule-0851068_openai_gpt-4o.json",
    ]
