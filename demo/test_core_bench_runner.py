import pytest

# core_bench_runner imports CAPSULE_CHECKSUMS from inspect_evals at module load.
pytest.importorskip("inspect_evals")
import core_bench_runner as cbr


def test_claim_to_metrics_encodes_committed_interval():
    claim = {"Q": {"value": 96.125, "lower": 96.0, "upper": 96.25, "basis": "explicit_tolerance"}}
    metrics = cbr.claim_to_metrics(claim)
    assert metrics[0]["metric_name"] == "Q"
    assert metrics[0]["produced_value"] == repr(96.125)
    # the committed interval is sealed in expected_value, on-chain & inspectable
    assert "96.0" in metrics[0]["expected_value"] and "96.25" in metrics[0]["expected_value"]
    assert metrics[0]["within_tolerance"] is True


def test_data_hash_binds_to_capsule_checksum():
    h1 = cbr.compute_capsule_data_hash("capsule-5507257", salt=b"\x00" * 16)
    h2 = cbr.compute_capsule_data_hash("capsule-5507257", salt=b"\x01" * 16)
    assert len(h1) == 64 and h1 != h2  # salted, fresh per run


def test_validate_model_keys_fails_fast_when_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    with pytest.raises(RuntimeError) as exc:
        cbr.validate_model_keys(["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"])
    assert "OPENAI_API_KEY" in str(exc.value)


def test_validate_model_keys_passes_when_all_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    cbr.validate_model_keys(["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-1.5-pro"])
