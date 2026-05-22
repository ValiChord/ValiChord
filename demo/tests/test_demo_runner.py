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


from unittest.mock import patch, MagicMock
import json as _json


# ── form_verdicts ─────────────────────────────────────────────────────────────

def test_form_verdicts_calls_claude_three_times():
    good_text = '{"outcome":"Reproduced","confidence":"High","reasoning":"All matched."}'
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=good_text)]
    with patch('anthropic.Anthropic') as MockClient:
        instance = MockClient.return_value
        instance.messages.create.return_value = mock_msg
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            verdicts = demo_runner.form_verdicts('readme', 'output')
    assert len(verdicts) == 3
    assert instance.messages.create.call_count == 3
    assert all(v['outcome'] == 'Reproduced' for v in verdicts)


def test_form_verdicts_retries_on_invalid_json():
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text='not json at all')]
    good_msg = MagicMock()
    good_msg.content = [MagicMock(text='{"outcome":"Reproduced","confidence":"High","reasoning":"ok"}')]
    # Each validator: first call is bad, second is good  → 2 calls × 3 validators = 6 total
    with patch('anthropic.Anthropic') as MockClient:
        instance = MockClient.return_value
        instance.messages.create.side_effect = [bad_msg, good_msg] * 3
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            verdicts = demo_runner.form_verdicts('readme', 'output')
    assert len(verdicts) == 3


def test_form_verdicts_raises_without_api_key():
    env_copy = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
    with patch.dict(os.environ, env_copy, clear=True):
        with pytest.raises(RuntimeError, match='ANTHROPIC_API_KEY'):
            demo_runner.form_verdicts('readme', 'output')


# ── run_protocol ──────────────────────────────────────────────────────────────

def _make_urlopen_mock(responses: dict):
    """Returns a urlopen side_effect that dispatches by URL substring."""
    def fake_urlopen(req, timeout=30):
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        for pattern, body in responses.items():
            if pattern in url:
                m = MagicMock()
                m.read.return_value = _json.dumps(body).encode()
                m.__enter__ = lambda s: s
                m.__exit__ = MagicMock(return_value=False)
                return m
        raise RuntimeError(f'No mock for URL: {url}')
    return fake_urlopen


_ORACLE_RESPONSES = {
    '/lock-result':           {'external_hash_b64': 'uhC8kABC123=='},
    '/submit-request':        {'ok': True},
    '/commit':                {'ok': True},
    '/phase':                 {'phase': 'RevealOpen'},
    '/reveal':                {'researcher_reveal_hash': 'uhCkkREV456=='},
    '/create-harmony-record': {'harmony_record_hash': 'uhCEkHRM789=='},
}

_THREE_REPRODUCED = [
    {'outcome': 'Reproduced', 'confidence': 'High',   'reasoning': 'slope matched'},
    {'outcome': 'Reproduced', 'confidence': 'High',   'reasoning': 'r2 matched'},
    {'outcome': 'Reproduced', 'confidence': 'Medium', 'reasoning': 'within tolerance'},
]


def test_run_protocol_happy_path():
    job = {'step': 4}
    metrics = [{'metric_name': 'slope', 'produced_value': '2.4086',
                'expected_value': '2.4086', 'within_tolerance': True}]
    with patch('urllib.request.urlopen', side_effect=_make_urlopen_mock(_ORACLE_RESPONSES)):
        with patch('time.sleep'):
            result = demo_runner.run_protocol('deadbeef' * 8, metrics, _THREE_REPRODUCED, job)
    assert result['outcome'] == 'Reproduced'
    assert result['agreement_level'] == 'ExactMatch'
    assert result['harmony_record_hash'] == 'uhCEkHRM789=='
    assert result['validator_count'] == 3
    assert len(result['validator_verdicts']) == 3
    assert 'record_url' in result
    assert job['step'] == 6  # run_protocol advances to 5 and 6; caller sets 7


def test_run_protocol_failed_reproduction():
    verdicts = [
        {'outcome': 'FailedToReproduce', 'confidence': 'High',   'reasoning': 'mismatch'},
        {'outcome': 'FailedToReproduce', 'confidence': 'High',   'reasoning': 'mismatch'},
        {'outcome': 'Reproduced',        'confidence': 'Medium', 'reasoning': 'ok'},
    ]
    job = {'step': 4}
    with patch('urllib.request.urlopen', side_effect=_make_urlopen_mock(_ORACLE_RESPONSES)):
        with patch('time.sleep'):
            result = demo_runner.run_protocol('deadbeef' * 8, [], verdicts, job)
    assert result['outcome'] == 'FailedToReproduce'
    # rate = (0+1)/3 = 0.33 → n_reproduced+n_partial > 0 → Divergent
    assert result['agreement_level'] == 'Divergent'


def test_run_protocol_phase_timeout_raises():
    responses = dict(_ORACLE_RESPONSES)
    responses['/phase'] = {'phase': None}  # never opens
    job = {'step': 4}
    with patch('urllib.request.urlopen', side_effect=_make_urlopen_mock(responses)):
        with patch('time.sleep'):
            with pytest.raises(RuntimeError, match='Phase gate did not open'):
                demo_runner.run_protocol('deadbeef' * 8, [], _THREE_REPRODUCED, job)
    assert job['step'] == 5  # commits completed, step 6 not reached


def test_run_protocol_null_harmony_hash_raises():
    responses = dict(_ORACLE_RESPONSES)
    responses['/create-harmony-record'] = {'harmony_record_hash': None}
    job = {'step': 4}
    with patch('urllib.request.urlopen', side_effect=_make_urlopen_mock(responses)):
        with patch('time.sleep'):
            with pytest.raises(RuntimeError, match='HarmonyRecord was not written'):
                demo_runner.run_protocol('deadbeef' * 8, [], _THREE_REPRODUCED, job)
