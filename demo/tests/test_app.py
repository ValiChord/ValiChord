import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import app as demo_app


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
    assert b'Seal my answer and start validation' in r.data


def test_free_demo_routes_removed(client):
    # The free demo used the server's API key; it has been removed entirely.
    assert client.post('/demo/run').status_code == 404
    assert client.get('/demo/result/any-id').status_code == 404
    assert b'Run Protocol' not in client.get('/demo').data
    assert b'Free demo' not in client.get('/demo').data


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
