from unittest import mock
import pytest

pytest.importorskip("inspect_ai")
pytest.importorskip("inspect_evals")
import core_bench_validator as cbv


def test_build_validator_task_uses_hard_blind_filters():
    """Blinding guard: hard difficulty + no-GPU + no-vision + the one capsule."""
    captured = {}

    def fake_read(**kwargs):
        captured.update(kwargs)
        return "DATASET"

    with mock.patch.object(cbv, "read_core_bench_dataset", fake_read), \
         mock.patch.object(cbv, "default_solver", lambda **k: "SOLVER"), \
         mock.patch.object(cbv, "capture_report", lambda: "SCORER"), \
         mock.patch.object(cbv, "Task", lambda **k: k) as _:
        task = cbv.build_validator_task("capsule-5507257")

    assert captured["difficulty"] == "hard"
    assert captured["capsule_ids"] == ["capsule-5507257"]
    assert captured["filter_out_gpu"] is True
    assert captured["filter_out_vision"] is True
    assert task["scorer"] == "SCORER"


def test_extract_report_from_log_reads_score_metadata():
    fake_score = mock.Mock(metadata={"report": {"Q": 1.0}})
    fake_sample = mock.Mock(scores={"capture_report": fake_score})
    fake_log = mock.Mock(samples=[fake_sample])
    assert cbv.extract_report_from_log([fake_log]) == {"Q": 1.0}


def test_extract_report_from_log_handles_no_samples():
    fake_log = mock.Mock(samples=[])
    assert cbv.extract_report_from_log([fake_log]) is None


def test_run_validator_eval_returns_report():
    with mock.patch.object(cbv, "build_validator_task", lambda cid: "TASK"), \
         mock.patch.object(cbv, "inspect_eval", lambda *a, **k: ["LOG"]) as ev, \
         mock.patch.object(cbv, "extract_report_from_log", lambda logs: {"Q": 2.0}):
        report = cbv.run_validator_eval("capsule-5507257", "anthropic/claude-opus-4-8")
    assert report == {"Q": 2.0}


def test_run_researcher_claim_runs_n_times_and_derives():
    calls = []

    def fake_eval(cid, model):
        calls.append(model)
        return {"Q": 96.125}

    with mock.patch.object(cbv, "run_validator_eval", fake_eval):
        claim = cbv.run_researcher_claim("capsule-5507257", "anthropic/claude-opus-4-8", n_runs=3)
    assert len(calls) == 3
    assert claim["Q"]["value"] == pytest.approx(96.125)


def test_run_researcher_claim_raises_on_failed_run():
    with mock.patch.object(cbv, "run_validator_eval", lambda c, m: None):
        with pytest.raises(RuntimeError):
            cbv.run_researcher_claim("capsule-5507257", "m", n_runs=2)
