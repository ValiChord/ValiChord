"""Shared node HTTP helpers and Oracle URL config.

Named for the free public demo this module used to run. Those routes were
deleted; the study logic, the Claude calls and the protocol runner went
unreachable with them and sat here untouched until 2026-08-27, when they were
removed — `load_study`, `execute_study`, `parse_metrics`, `_parse_verdict`,
`form_verdicts`, `run_protocol`, and the `MODEL` / `_EXPECTED_METRICS` /
`DEMO_DIR` / `STUDY_DIR` constants that only they used. None had a caller
outside its own test file. The study helpers live on in `ai_validator_cma.py`,
which carries its own copies and says so.

⚠️ The module itself is NOT dead and must not be deleted. Two live callers:

  * `core_bench_runner.py:22` — `_node_post`, `_node_get`, `RESEARCHER_URL`,
    `VALIDATOR_URLS`
  * `app.py:106` — `RESEARCHER_URL`, for the `/demo/record/<hash>` viewer

The name now undersells the contents, and is kept anyway: renaming would break
both call sites to buy nothing.
"""
import json
import os
import urllib.error
import urllib.request

RESEARCHER_URL = os.environ.get('VALICHORD_RESEARCHER_URL', 'http://localhost:3001')
VALIDATOR_URLS = [
    os.environ.get('VALICHORD_VALIDATOR_1_URL', 'http://localhost:3002'),
    os.environ.get('VALICHORD_VALIDATOR_2_URL', 'http://localhost:3003'),
    os.environ.get('VALICHORD_VALIDATOR_3_URL', 'http://localhost:3004'),
]


def _node_post(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode()
    headers = {'Content-Type': 'application/json'}
    node_key = os.environ.get('VALICHORD_NODE_KEY', '')
    if node_key:
        headers['X-ValiChord-Node-Key'] = node_key
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Node API {url} returned {e.code}: {body}')
    except OSError as e:
        raise RuntimeError(f'Cannot reach {url}: {e}')
    if 'error' in result:
        raise RuntimeError(f'Node API error from {url}: {result["error"]}')
    return result


def _node_get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'ValiChord-Demo/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Node API {url} returned {e.code}: {body}')
    except OSError as e:
        raise RuntimeError(f'Cannot reach {url}: {e}')
