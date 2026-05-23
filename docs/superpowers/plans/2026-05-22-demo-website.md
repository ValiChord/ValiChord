# ValiChord Demo Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public demo page at `GET /demo` (served via Render) that runs the full ValiChord commit-reveal protocol end-to-end when a visitor clicks "Run Protocol", showing live 7-step progress and a permanent shareable HarmonyRecord URL.

**Architecture:** New Flask app (`demo/app.py`) + business logic (`demo/demo_runner.py`). Render calls Oracle's HTTP node APIs (researcher + 3 validators on `132.145.34.27:3001–3004`) from a background thread. Claude Haiku forms the three validator verdicts. Browser polls `GET /demo/result/<job_id>` every 2 s. `render.yaml` already points to `demo/Dockerfile` — we just need to create it.

**Tech Stack:** Python 3.12, Flask 3.1, anthropic SDK, gunicorn, pytest; HTML/CSS/JS inline in `app.py`; Docker for Render.

---

## File Map

| Path | Purpose |
|---|---|
| `demo/demo_runner.py` | All business logic: load study, run study.py, parse metrics, call Claude, call Oracle node APIs |
| `demo/app.py` | Flask routes, in-memory job store, demo lock (threading), inline HTML page |
| `demo/requirements.txt` | Python deps for Docker image |
| `demo/Dockerfile` | Render container (already referenced in `render.yaml`) |
| `demo/tests/__init__.py` | Empty package marker |
| `demo/tests/test_demo_runner.py` | Tests for pure functions + mocked network/Claude calls |
| `demo/tests/test_app.py` | Flask route tests via test client |
| `render.yaml` | Add Oracle URL env vars (key is already set; `ANTHROPIC_API_KEY` goes in Render dashboard) |

---

### Task 1: demo_runner.py — pure functions + tests

**Files:**
- Create: `demo/demo_runner.py`
- Create: `demo/tests/__init__.py`
- Create: `demo/tests/test_demo_runner.py`

- [ ] **Step 1: Install test dependencies**

```bash
cd /workspaces/ValiChord && pip install pytest flask flask-cors anthropic -q
```

Expected: no errors.

- [ ] **Step 2: Write failing tests**

Create `demo/tests/__init__.py` (empty file), then create `demo/tests/test_demo_runner.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /workspaces/ValiChord && python -m pytest demo/tests/test_demo_runner.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'demo_runner'`

- [ ] **Step 4: Write demo_runner.py (pure functions only)**

Create `demo/demo_runner.py`:

```python
"""ValiChord demo runner — business logic for the public demo website."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

DEMO_DIR   = Path(__file__).parent
STUDY_DIR  = DEMO_DIR / 'synthetic_study'
MODEL      = 'claude-haiku-4-5-20251001'

RESEARCHER_URL = os.environ.get('VALICHORD_RESEARCHER_URL', 'http://132.145.34.27:3001')
VALIDATOR_URLS = [
    os.environ.get('VALICHORD_VALIDATOR_1_URL', 'http://132.145.34.27:3002'),
    os.environ.get('VALICHORD_VALIDATOR_2_URL', 'http://132.145.34.27:3003'),
    os.environ.get('VALICHORD_VALIDATOR_3_URL', 'http://132.145.34.27:3004'),
]

_EXPECTED_METRICS = {
    'slope':     '2.4086',
    'intercept': '1.1742',
    'r2':        '0.9991',
}


def load_study():
    """Return (readme_text, data_hash_hex, zip_path). Each call produces a unique hash via random salt."""
    readme = (STUDY_DIR / 'README.md').read_text()
    data_bytes = (STUDY_DIR / 'data.csv').read_bytes()
    run_id = uuid.uuid4().bytes
    data_hash = hashlib.sha256(data_bytes + run_id).hexdigest()
    tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(STUDY_DIR.iterdir()):
            zf.write(f, f.name)
    return readme, data_hash, tmp.name


def execute_study():
    """Run synthetic study.py and return stdout. Raises RuntimeError on non-zero exit."""
    script = STUDY_DIR / 'study.py'
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f'Study script failed (exit {result.returncode}): {result.stderr}')
    return result.stdout.strip()


def parse_metrics(output: str) -> list:
    """Extract structured MetricResult list from study.py stdout."""
    values = {}
    for line in output.splitlines():
        if m := re.match(r'Slope \(coefficient\):\s*([\d.]+)', line):
            values['slope'] = m.group(1)
        elif m := re.match(r'Intercept:\s*([\d.]+)', line):
            values['intercept'] = m.group(1)
        elif m := re.match(r'R[²2]:\s*([\d.]+)', line):
            values['r2'] = m.group(1)
    return [
        {
            'metric_name':      name,
            'produced_value':   values.get(name, 'N/A'),
            'expected_value':   expected,
            'within_tolerance': values.get(name, '') == expected,
        }
        for name, expected in _EXPECTED_METRICS.items()
    ]


def _parse_verdict(raw: str) -> dict:
    """Parse and validate a Claude verdict JSON string. Raises ValueError on bad input."""
    text = raw.strip()
    for prefix in ('```json', '```'):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    verdict = json.loads(text)
    missing = {'outcome', 'confidence', 'reasoning'} - verdict.keys()
    if missing:
        raise ValueError(f'Missing required keys: {sorted(missing)}')
    if verdict['outcome'] not in {'Reproduced', 'PartiallyReproduced', 'FailedToReproduce', 'UnableToAssess'}:
        raise ValueError(f'Invalid outcome {verdict["outcome"]!r}')
    if verdict['confidence'] not in {'High', 'Medium', 'Low'}:
        raise ValueError(f'Invalid confidence {verdict["confidence"]!r}')
    return verdict
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /workspaces/ValiChord && python -m pytest demo/tests/test_demo_runner.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/ValiChord add demo/demo_runner.py demo/tests/__init__.py demo/tests/test_demo_runner.py
git -C /workspaces/ValiChord commit -m "feat(demo): demo_runner pure functions with tests"
```

---

### Task 2: Flask app scaffold + job store + demo lock

**Files:**
- Create: `demo/app.py`
- Create: `demo/tests/test_app.py`

- [ ] **Step 1: Write failing Flask route tests**

Create `demo/tests/test_app.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /workspaces/ValiChord && python -m pytest demo/tests/test_app.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write demo/app.py**

Create `demo/app.py`:

```python
"""ValiChord demo website — Flask server."""
import os
import threading
import urllib.parse
import urllib.request
import uuid

from flask import Flask, Response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

_jobs: dict = {}
_demo_lock = threading.Lock()
_demo_running = False


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/demo')
def demo_page():
    return Response(_DEMO_HTML, mimetype='text/html')


@app.route('/demo/run', methods=['POST'])
def demo_run():
    global _demo_running
    with _demo_lock:
        if _demo_running:
            return jsonify({
                'status': 'busy',
                'message': 'Demo in progress — check back in ~2 minutes',
            }), 409
        _demo_running = True

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {'step': 0, 'status': 'running', 'result': None, 'error': None}

    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return jsonify({'job_id': job_id}), 202


@app.route('/demo/result/<job_id>')
def demo_result(job_id):
    job = _jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Unknown job'}), 404
    return jsonify(job)


@app.route('/demo/record/<path:hash_b64>')
def demo_record(hash_b64):
    import demo_runner
    url = f'{demo_runner.RESEARCHER_URL}/record?hash={urllib.parse.quote(hash_b64)}'
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return Response(resp.read(), mimetype='application/json')
    except Exception as e:
        return jsonify({'error': str(e)}), 502


def _run_job(job_id: str):
    global _demo_running
    job = _jobs[job_id]
    try:
        import demo_runner

        job['step'] = 1
        readme, data_hash, _ = demo_runner.load_study()

        job['step'] = 2
        output = demo_runner.execute_study()
        metrics = demo_runner.parse_metrics(output)

        job['step'] = 3
        verdicts = demo_runner.form_verdicts(readme, output)

        job['step'] = 4
        result = demo_runner.run_protocol(data_hash, metrics, verdicts, job)

        job['step'] = 7
        job['status'] = 'done'
        job['result'] = result
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
    finally:
        _demo_running = False


_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ValiChord — Live Demo</title>
<style>
:root{--bg:#07070f;--surface:#0b0b18;--border:#141424;--text:#c8c4bc;--dim:#6b6880;--accent:#4a90d9;--green:#4caf50;--yellow:#ffc107;--r:14px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,sans-serif;min-height:100vh}
header{background:var(--surface);border-bottom:1px solid var(--border);padding:0 2rem;height:56px;display:flex;align-items:center;gap:1rem}
.tag{font-size:.72rem;color:var(--dim)}
main{max-width:720px;margin:3rem auto;padding:0 1.5rem}
h1{font-family:'Newsreader',Georgia,serif;font-size:2rem;margin-bottom:.5rem}
.lead{color:var(--dim);margin-bottom:2rem;line-height:1.6;font-size:.95rem}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:1.5rem;margin-bottom:1.5rem}
.card h2{font-size:1rem;margin-bottom:.75rem}
.card p{color:var(--dim);font-size:.875rem;line-height:1.6}
.btn{background:var(--accent);color:#fff;border:none;padding:.65rem 1.5rem;border-radius:8px;cursor:pointer;font-size:.9rem;font-family:inherit;margin-top:1rem}
.btn:disabled{opacity:.4;cursor:not-allowed}
.steps{list-style:none;margin-top:1rem}
.steps li{display:flex;align-items:center;gap:.75rem;padding:.4rem 0;font-size:.875rem;color:var(--dim)}
.dot{width:18px;height:18px;border-radius:50%;border:2px solid var(--border);flex-shrink:0;transition:all .3s}
li.active{color:var(--text)} li.done{color:var(--text)}
.dot.active{border-color:var(--accent);background:var(--accent);animation:pulse 1s infinite}
.dot.done{border-color:var(--green);background:var(--green)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
.result-box{background:var(--bg);border:1px solid var(--green);border-radius:10px;padding:1rem 1.25rem;margin-top:1rem}
.outcome{font-size:1.1rem;font-weight:600;color:var(--green)}
.detail{font-size:.8rem;color:var(--dim);margin-top:.2rem}
.verdicts{margin-top:.6rem}
.vrow{font-size:.8rem;color:var(--dim);padding:.15rem 0}
.share{margin-top:.75rem}
.share a{color:var(--accent);font-size:.8rem;word-break:break-all}
.err{background:#1a0a0a;border:1px solid #5c2020;border-radius:10px;padding:1rem;margin-top:1rem;color:#e57373;font-size:.875rem}
.busy{color:var(--yellow);font-size:.85rem;margin-top:.6rem}
</style>
</head>
<body>
<header>
  <strong>ValiChord</strong>
  <span class="tag">Reproducibility Validation Protocol</span>
</header>
<main>
  <h1>Live Demo</h1>
  <p class="lead">Run the full ValiChord commit-reveal protocol live. A synthetic study is submitted, three independent AI validators each commit a blind verdict to a distributed hash table, all parties reveal simultaneously, and a tamper-evident HarmonyRecord is written. Neither the researcher nor any validator can alter their claim after the protocol begins.</p>
  <div class="card">
    <h2>Study: Temperature–Species Richness</h2>
    <p>Linear regression across 20 sampling sites. Claims: slope ≈ 2.4086, R² ≈ 0.9991. Validators reproduce the computation independently and commit their verdict before seeing each other’s result.</p>
    <button class="btn" id="runBtn" onclick="startDemo()">Run Protocol (~2 min)</button>
    <div id="busyMsg" class="busy" style="display:none"></div>
  </div>
  <div class="card" id="progressCard" style="display:none">
    <h2>Protocol progress</h2>
    <ul class="steps">
      <li id="s1"><span class="dot"></span>Loading study deposit</li>
      <li id="s2"><span class="dot"></span>Executing study code</li>
      <li id="s3"><span class="dot"></span>Forming 3 independent verdicts via Claude Haiku</li>
      <li id="s4"><span class="dot"></span>Committing to DHT — blind phase</li>
      <li id="s5"><span class="dot"></span>All commitments sealed</li>
      <li id="s6"><span class="dot"></span>Researcher + validators revealed</li>
      <li id="s7"><span class="dot"></span>HarmonyRecord written</li>
    </ul>
    <div id="resultArea"></div>
  </div>
</main>
<script>
let poll=null;
function startDemo(){
  const btn=document.getElementById('runBtn');
  btn.disabled=true;
  document.getElementById('busyMsg').style.display='none';
  const pc=document.getElementById('progressCard');
  pc.style.display='block';
  document.getElementById('resultArea').innerHTML='';
  for(let i=1;i<=7;i++){const li=document.getElementById('s'+i);li.className='';li.querySelector('.dot').className='dot';}
  fetch('/demo/run',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.status==='busy'){
      document.getElementById('busyMsg').textContent=d.message;
      document.getElementById('busyMsg').style.display='block';
      btn.disabled=false;pc.style.display='none';return;
    }
    if(!d.job_id){showErr('Failed to start: '+JSON.stringify(d));btn.disabled=false;return;}
    poll=setInterval(()=>doPoll(d.job_id),2000);
  }).catch(e=>{showErr('Network error: '+e.message);btn.disabled=false;});
}
function doPoll(id){
  fetch('/demo/result/'+id).then(r=>r.json()).then(j=>{
    setSteps(j.step,false);
    if(j.status==='done'){clearInterval(poll);setSteps(7,true);showResult(j.result);document.getElementById('runBtn').disabled=false;}
    else if(j.status==='error'){clearInterval(poll);showErr(j.error||'Unknown error');document.getElementById('runBtn').disabled=false;}
  }).catch(e=>console.error('poll:',e));
}
function setSteps(cur,done){
  for(let i=1;i<=7;i++){
    const li=document.getElementById('s'+i),dot=li.querySelector('.dot');
    if(i<cur){li.className='done';dot.className='dot done';}
    else if(i===cur&&!done){li.className='active';dot.className='dot active';}
    else if(i===cur&&done){li.className='done';dot.className='dot done';}
    else{li.className='';dot.className='dot';}
  }
}
function showResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>`<div class="vrow">Validator ${v.validator}: ${v.outcome} (${v.confidence}) — ${v.reasoning}</div>`).join('');
  const shareUrl=r.record_url||'';
  document.getElementById('resultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${r.outcome} — ${r.agreement_level}</div>
    <div class="detail">${r.validator_count}/3 validators · ComputationalBiology</div>
    <div class="verdicts">${rows}</div>
    ${shareUrl?`<div class="share">Permanent record: <a href="${shareUrl}" target="_blank">${shareUrl}</a></div>`:''}
  </div>`;
}
function showErr(msg){document.getElementById('resultArea').innerHTML=`<div class="err">${msg}</div>`;}
</script>
</body>
</html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /workspaces/ValiChord && python -m pytest demo/tests/test_app.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/ValiChord add demo/app.py demo/tests/test_app.py
git -C /workspaces/ValiChord commit -m "feat(demo): Flask scaffold with job store, demo lock, and HTML page"
```

---

### Task 3: form_verdicts + run_protocol + tests

**Files:**
- Modify: `demo/demo_runner.py` (append form_verdicts, _parse_verdict helpers, _node_post, _node_get, run_protocol)
- Modify: `demo/tests/test_demo_runner.py` (append tests for these functions)

- [ ] **Step 1: Write failing tests**

Append to `demo/tests/test_demo_runner.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /workspaces/ValiChord && python -m pytest demo/tests/test_demo_runner.py::test_form_verdicts_calls_claude_three_times demo/tests/test_demo_runner.py::test_run_protocol_happy_path -v 2>&1 | head -15
```

Expected: `AttributeError` — `form_verdicts` / `run_protocol` not defined.

- [ ] **Step 3: Append form_verdicts, _node_post, _node_get, run_protocol to demo_runner.py**

```python
def form_verdicts(readme: str, actual_output: str) -> list:
    """Call Claude Haiku once per validator. Returns list of 3 verdict dicts."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY not set')

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a scientific validator. A researcher submitted a computational study and you have just executed their code.

STUDY BRIEF (from README):
{readme}

ACTUAL EXECUTION OUTPUT:
{actual_output}

Compare the actual output against what the README claims.
Reply with ONLY a JSON object — no markdown, no explanation:
{{
  "outcome": "Reproduced" | "PartiallyReproduced" | "FailedToReproduce" | "UnableToAssess",
  "confidence": "High" | "Medium" | "Low",
  "reasoning": "<one sentence>"
}}"""

    verdicts = []
    for i in range(3):
        messages = [{'role': 'user', 'content': prompt}]
        last_raw = ''
        for attempt in range(5):
            msg = client.messages.create(model=MODEL, max_tokens=256, messages=messages)
            last_raw = msg.content[0].text.strip()
            try:
                verdicts.append(_parse_verdict(last_raw))
                break
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                if attempt == 4:
                    raise RuntimeError(
                        f'Validator {i + 1} failed to return valid JSON after 5 attempts. '
                        f'Last response: {last_raw}'
                    )
                messages.append({'role': 'assistant', 'content': last_raw})
                messages.append({
                    'role': 'user',
                    'content': f'That response could not be parsed. Error: {exc}. Reply with ONLY the corrected JSON.',
                })
    return verdicts


def _node_post(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={'Content-Type': 'application/json'}, method='POST',
    )
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


def run_protocol(data_hash: str, metrics: list, verdicts: list, job: dict) -> dict:
    """Run the decentralised commit-reveal protocol via Oracle node HTTP APIs."""
    disc = {'type': 'ComputationalBiology'}

    lock_resp = _node_post(f'{RESEARCHER_URL}/lock-result', {
        'data_hash_hex': data_hash, 'metrics': metrics,
    })
    external_hash_b64 = lock_resp['external_hash_b64']

    _node_post(f'{RESEARCHER_URL}/submit-request', {
        'external_hash_b64': external_hash_b64,
        'discipline': disc,
        'num_validators_required': 3,
    })

    time.sleep(20)  # let ValidationRequest propagate via DHT gossip

    for i, (vurl, verdict) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f'{vurl}/commit', {
            'external_hash_b64': external_hash_b64,
            'verdict': verdict,
            'metrics': metrics,
            'discipline': disc,
        })
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(30)

    job['step'] = 5

    phase_url = f'{RESEARCHER_URL}/phase?hash={urllib.parse.quote(external_hash_b64)}'
    for _ in range(120):
        phase_resp = _node_get(phase_url)
        if phase_resp.get('phase') is not None:
            break
        time.sleep(2)
    else:
        raise RuntimeError('Phase gate did not open after 240 seconds')

    reveal_resp = _node_post(f'{RESEARCHER_URL}/reveal', {
        'external_hash_b64': external_hash_b64, 'metrics': metrics,
    })
    researcher_reveal_hash = reveal_resp.get('researcher_reveal_hash')

    for i, (vurl, _verdict) in enumerate(zip(VALIDATOR_URLS, verdicts)):
        _node_post(f'{vurl}/reveal', {'external_hash_b64': external_hash_b64})
        if i < len(VALIDATOR_URLS) - 1:
            time.sleep(15)

    job['step'] = 6

    harmony_resp = _node_post(f'{VALIDATOR_URLS[0]}/create-harmony-record', {
        'external_hash_b64': external_hash_b64,
    })
    harmony_record_hash = harmony_resp.get('harmony_record_hash')

    outcomes = [v['outcome'] for v in verdicts]
    n_reproduced = outcomes.count('Reproduced')
    n_partial    = outcomes.count('PartiallyReproduced')
    rate = (n_reproduced + n_partial) / len(outcomes)
    agreement_level = (
        'ExactMatch'       if rate >= 0.90 else
        'WithinTolerance'  if rate >= 0.70 else
        'DirectionalMatch' if rate >= 0.50 else
        'Divergent'        if n_reproduced + n_partial > 0 else
        'UnableToAssess'
    )
    majority_outcome = (
        'Reproduced'          if n_reproduced >= 2 else
        'PartiallyReproduced' if n_partial    >= 2 else
        'FailedToReproduce'   if outcomes.count('FailedToReproduce') >= 2 else
        'UnableToAssess'
    )

    return {
        'harmony_record_hash':    harmony_record_hash,
        'external_hash_b64':      external_hash_b64,
        'outcome':                majority_outcome,
        'agreement_level':        agreement_level,
        'validator_count':        3,
        'researcher_reveal_hash': researcher_reveal_hash,
        'record_url':             f'http://132.145.34.27:3001/record?hash={urllib.parse.quote(external_hash_b64)}',
        'validator_verdicts': [
            {
                'validator':  i + 1,
                'outcome':    v['outcome'],
                'confidence': v['confidence'],
                'reasoning':  v['reasoning'],
            }
            for i, v in enumerate(verdicts)
        ],
    }
```

- [ ] **Step 4: Run all tests**

```bash
cd /workspaces/ValiChord && python -m pytest demo/tests/ -v
```

Expected: all tests PASS (20+ tests total).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/ValiChord add demo/demo_runner.py demo/tests/test_demo_runner.py
git -C /workspaces/ValiChord commit -m "feat(demo): form_verdicts and run_protocol with full test coverage"
```

---

### Task 4: Dockerfile + requirements.txt + render.yaml

**Files:**
- Create: `demo/requirements.txt`
- Create: `demo/Dockerfile`
- Modify: `render.yaml`

- [ ] **Step 1: Create demo/requirements.txt**

```
flask==3.1.0
flask-cors==5.0.0
anthropic>=0.28.0
gunicorn==22.0.0
```

- [ ] **Step 2: Create demo/Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY demo/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY demo/ /app/demo/

WORKDIR /app/demo
ENV PORT=8080
EXPOSE 8080

CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 app:app
```

- [ ] **Step 3: Update render.yaml with Oracle URLs and correct healthCheckPath**

Replace the existing `render.yaml`:

```yaml
services:
  - type: web
    name: valichord-demo
    runtime: docker
    dockerfilePath: ./demo/Dockerfile
    dockerContext: .
    healthCheckPath: /health
    envVars:
      - key: NODE_ENV
        value: production
      - key: VALICHORD_RESEARCHER_URL
        value: http://132.145.34.27:3001
      - key: VALICHORD_VALIDATOR_1_URL
        value: http://132.145.34.27:3002
      - key: VALICHORD_VALIDATOR_2_URL
        value: http://132.145.34.27:3003
      - key: VALICHORD_VALIDATOR_3_URL
        value: http://132.145.34.27:3004
```

Note: `ANTHROPIC_API_KEY` is a secret — add it in the Render dashboard under Environment, not here.

- [ ] **Step 4: Verify Docker build**

```bash
cd /workspaces/ValiChord && docker build -f demo/Dockerfile -t valichord-demo-web . 2>&1 | tail -5
```

Expected: `Successfully built ...`

- [ ] **Step 5: Verify container starts and /health responds**

```bash
docker run --rm -d -p 8081:8080 --name vc-demo-test valichord-demo-web
sleep 3
curl -s http://localhost:8081/health
docker stop vc-demo-test
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit and push**

```bash
git -C /workspaces/ValiChord add demo/requirements.txt demo/Dockerfile render.yaml
git -C /workspaces/ValiChord commit -m "feat(demo): Dockerfile and Render config"
git -C /workspaces/ValiChord push
```

---

### Task 5: Smoke test against live Oracle

This is a manual step — no automated test for the live Oracle round (~2 min).

- [ ] **Step 1: Start the Flask server locally pointing at Oracle**

```bash
cd /workspaces/ValiChord/demo && \
  VALICHORD_RESEARCHER_URL=http://132.145.34.27:3001 \
  VALICHORD_VALIDATOR_1_URL=http://132.145.34.27:3002 \
  VALICHORD_VALIDATOR_2_URL=http://132.145.34.27:3003 \
  VALICHORD_VALIDATOR_3_URL=http://132.145.34.27:3004 \
  ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  python app.py &
sleep 2 && curl -s http://localhost:8080/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 2: Trigger a run and poll to completion**

```bash
JOB=$(curl -s -X POST http://localhost:8080/demo/run | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB"

for i in $(seq 1 60); do
  STATUS=$(curl -s http://localhost:8080/demo/result/$JOB | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], 'step', d['step'])" 2>/dev/null)
  echo "[$i] $STATUS"
  echo "$STATUS" | grep -q "done" && break
  sleep 5
done
```

Expected: transitions through steps 1→7, final `done step 7`.

- [ ] **Step 3: Verify result fields and record URL**

```bash
curl -s http://localhost:8080/demo/result/$JOB | python3 -c "
import sys, json
d = json.load(sys.stdin)
r = d['result']
print('outcome:    ', r['outcome'])
print('agreement:  ', r['agreement_level'])
print('record_url: ', r['record_url'])
" && echo "---" && \
RECORD_URL=$(curl -s http://localhost:8080/demo/result/$JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['record_url'])") && \
curl -s "$RECORD_URL" | python3 -m json.tool
```

Expected: outcome `Reproduced`, agreement `ExactMatch`, record URL returns JSON with `outcome` and `validator_count`.

- [ ] **Step 4: Test busy lock (optional)**

In a second terminal while a run is active:
```bash
curl -s -X POST http://localhost:8080/demo/run | python3 -m json.tool
```
Expected: `{"message": "Demo in progress — check back in ~2 minutes", "status": "busy"}`

---

## Self-Review

**Spec coverage check (against DEMO_WEBSITE_PLAN.md Steps 1–3):**
- ✅ Step 1 (backend scaffold): Tasks 2 + 4 — `/health`, `/demo`, `/demo/run`, `/demo/result`, `/demo/record`, job store, demo lock, Dockerfile
- ✅ Step 2 (gallery flow): Task 3 — `form_verdicts` + `run_protocol` port from `ai_validator.py`
- ✅ Step 3 (simple UI for gallery): Task 2 — dark-theme HTML with 7-step progress animation
- ✅ Haiku model: `MODEL = 'claude-haiku-4-5-20251001'`
- ✅ One-at-a-time lock: `_demo_running` + `_demo_lock` in `app.py`
- ✅ Step progress (1–7): `job['step']` updated throughout `_run_job` and `run_protocol`
- ✅ Oracle URLs as env vars: `VALICHORD_RESEARCHER_URL` / `VALIDATOR_{1,2,3}_URL` with defaults pointing at Oracle
- ✅ `ANTHROPIC_API_KEY` not in `render.yaml`: documented as Render dashboard secret
- ✅ `healthCheckPath`: updated from `/` to `/health` in `render.yaml`
- ✅ TDD: tests written before implementation in every task
- ✅ Frequent commits: one commit per task

**Not in scope (deferred to future sessions):**
- Entry Point 2 (structured form) and 3 (auto-fix) — Steps 5–6 of DEMO_WEBSITE_PLAN
- Real Zenodo gallery studies — Step 4
- Geographic distribution across Fly.io — Option A in DEMO_WEBSITE_PLAN
