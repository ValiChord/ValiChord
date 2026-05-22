import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import app as demo_app


@pytest.fixture(autouse=True)
def reset_state():
    demo_app._jobs.clear()
    demo_app._demo_running = False
    yield
    demo_app._jobs.clear()
    demo_app._demo_running = False


@pytest.fixture
def client():
    demo_app.app.config['TESTING'] = True
    with demo_app.app.test_client() as c:
        yield c


def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.get_json()['status'] == 'ok'


def test_demo_page_returns_html(client):
    r = client.get('/demo')
    assert r.status_code == 200
    assert b'ValiChord' in r.data
    assert b'Run Protocol' in r.data


def test_demo_run_returns_202_and_job_id(client):
    with patch('threading.Thread') as mock_thread:
        mock_thread.return_value = MagicMock()
        r = client.post('/demo/run')
    assert r.status_code == 202
    data = r.get_json()
    assert 'job_id' in data
    assert data['job_id'] in demo_app._jobs


def test_demo_run_busy_when_running(client):
    demo_app._demo_running = True
    r = client.post('/demo/run')
    assert r.status_code == 409
    data = r.get_json()
    assert data['status'] == 'busy'
    assert 'message' in data


def test_demo_result_unknown_job(client):
    r = client.get('/demo/result/nonexistent-id')
    assert r.status_code == 404


def test_demo_result_returns_job_state(client):
    demo_app._jobs['test-job'] = {
        'step': 3, 'status': 'running', 'result': None, 'error': None,
    }
    r = client.get('/demo/result/test-job')
    assert r.status_code == 200
    data = r.get_json()
    assert data['step'] == 3
    assert data['status'] == 'running'


def test_demo_record_proxies_to_oracle(client):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"outcome": "Reproduced"}'
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch('urllib.request.urlopen', return_value=mock_resp):
        r = client.get('/demo/record/uhC8kABC123%3D%3D')
    assert r.status_code == 200
    assert b'Reproduced' in r.data


def test_demo_record_returns_502_on_network_error(client):
    with patch('urllib.request.urlopen', side_effect=OSError('unreachable')):
        r = client.get('/demo/record/uhC8kABC123%3D%3D')
    assert r.status_code == 502
