import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import demo_runner


# ── parse_metrics ──────────────────────────────────────────────────────────────

def test_parse_metrics_nominal():
    output = "Slope (coefficient): 2.4086\nIntercept:           1.1742\nR²:                  0.9991"
    metrics = demo_runner.parse_metrics(output)
    assert len(metrics) == 3
    assert metrics[0] == {
        'metric_name': 'slope', 'produced_value': '2.4086',
        'expected_value': '2.4086', 'within_tolerance': True,
    }
    assert metrics[1] == {
        'metric_name': 'intercept', 'produced_value': '1.1742',
        'expected_value': '1.1742', 'within_tolerance': True,
    }
    assert metrics[2] == {
        'metric_name': 'r2', 'produced_value': '0.9991',
        'expected_value': '0.9991', 'within_tolerance': True,
    }

def test_parse_metrics_r2_ascii():
    output = "Slope (coefficient): 2.4086\nIntercept: 1.1742\nR2: 0.9991"
    metrics = demo_runner.parse_metrics(output)
    assert metrics[2]['produced_value'] == '0.9991'

def test_parse_metrics_missing_metric():
    output = "Slope (coefficient): 2.4086"
    metrics = demo_runner.parse_metrics(output)
    assert len(metrics) == 3
    assert metrics[1]['produced_value'] == 'N/A'
    assert metrics[1]['within_tolerance'] is False

def test_parse_metrics_empty():
    metrics = demo_runner.parse_metrics("")
    assert all(m['produced_value'] == 'N/A' for m in metrics)
    assert all(m['within_tolerance'] is False for m in metrics)

def test_parse_metrics_preserves_order():
    output = "R²: 0.9991\nSlope (coefficient): 2.4086\nIntercept: 1.1742"
    metrics = demo_runner.parse_metrics(output)
    assert [m['metric_name'] for m in metrics] == ['slope', 'intercept', 'r2']


# ── load_study ─────────────────────────────────────────────────────────────────

def test_load_study_returns_readme_and_hash():
    readme, data_hash, zip_path = demo_runner.load_study()
    import os as _os
    assert isinstance(readme, str) and len(readme) > 10
    assert isinstance(data_hash, str) and len(data_hash) == 64
    assert _os.path.exists(zip_path)
    _os.unlink(zip_path)

def test_load_study_unique_hash_each_call():
    _, h1, z1 = demo_runner.load_study()
    _, h2, z2 = demo_runner.load_study()
    import os as _os
    _os.unlink(z1); _os.unlink(z2)
    assert h1 != h2


# ── execute_study ───────────────────────────────────────────────────────────────

def test_execute_study_returns_expected_output():
    output = demo_runner.execute_study()
    assert 'Slope (coefficient): 2.4086' in output
    assert 'Intercept:           1.1742' in output
    assert 'R²:                  0.9991' in output


# ── _parse_verdict ─────────────────────────────────────────────────────────────

def test_parse_verdict_valid():
    raw = '{"outcome": "Reproduced", "confidence": "High", "reasoning": "All metrics matched."}'
    v = demo_runner._parse_verdict(raw)
    assert v == {'outcome': 'Reproduced', 'confidence': 'High', 'reasoning': 'All metrics matched.'}

def test_parse_verdict_strips_markdown_fence():
    raw = '```json\n{"outcome": "Reproduced", "confidence": "High", "reasoning": "ok"}\n```'
    v = demo_runner._parse_verdict(raw)
    assert v['outcome'] == 'Reproduced'

def test_parse_verdict_invalid_outcome():
    raw = '{"outcome": "NotAVerdict", "confidence": "High", "reasoning": "ok"}'
    with pytest.raises(ValueError, match='Invalid outcome'):
        demo_runner._parse_verdict(raw)

def test_parse_verdict_missing_key():
    raw = '{"outcome": "Reproduced", "reasoning": "ok"}'
    with pytest.raises(ValueError, match='Missing required keys'):
        demo_runner._parse_verdict(raw)
