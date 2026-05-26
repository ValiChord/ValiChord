"""ValiChord demo website — Flask server."""
import os
import threading
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

_jobs: dict = {}
_demo_lock    = threading.Lock()
_demo_running = False

# Rate limiting — only applied when the user provides no key (server key is used)
_ip_last_run      = defaultdict(float)
_cma_run_count    = 0
_cma_run_lock     = threading.Lock()
CMA_COST_ESTIMATE = 1.50   # dollars per CMA run
CMA_MONTHLY_BUDGET = 20.00


def _server_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPICAPIKEY", "")


def _cma_rate_check(ip: str) -> tuple[bool, str]:
    """Returns (allowed, reason). Only called when using the server key."""
    now = time.time()
    if now - _ip_last_run[ip] < 3600:
        return False, "CMA mode is limited to once per hour per visitor. Try again later or bring your own API key."
    with _cma_run_lock:
        if _cma_run_count * CMA_COST_ESTIMATE >= CMA_MONTHLY_BUDGET:
            return False, "CMA mode has reached its monthly demo budget. Standard mode is still available."
    return True, ""


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/demo')
def demo_page():
    return Response(_DEMO_HTML, mimetype='text/html')


@app.route('/demo/run', methods=['POST'])
def demo_run():
    global _demo_running, _cma_run_count

    # Optional user-provided key and model
    body       = request.get_json(silent=True) or {}
    user_key   = (body.get("user_api_key") or "").strip()
    user_model = (body.get("user_model")   or "").strip()

    # If no user key, use server key + rate limiting
    using_server_key = not user_key
    if using_server_key:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        allowed, reason = _cma_rate_check(ip)
        if not allowed:
            return jsonify({"status": "rate_limited", "message": reason}), 429
        _ip_last_run[ip] = time.time()
        with _cma_run_lock:
            _cma_run_count += 1

    with _demo_lock:
        if _demo_running:
            return jsonify({
                "status":  "busy",
                "message": "Demo in progress — check back in ~2 minutes",
            }), 409
        _demo_running = True

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"step": 0, "status": "running", "result": None, "error": None}

    t = threading.Thread(
        target=_run_job,
        args=(job_id, user_key, user_model),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id}), 202


@app.route('/demo/result/<job_id>')
def demo_result(job_id):
    job = _jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Unknown job'}), 404
    return jsonify(job)


@app.route('/demo/record/<path:hash_b64>')
def demo_record(hash_b64):
    import demo_runner
    decoded = urllib.parse.unquote(hash_b64)
    url = f'{demo_runner.RESEARCHER_URL}/record?hash={urllib.parse.quote(decoded)}'
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return Response(resp.read(), mimetype='application/json')
    except Exception as e:
        return jsonify({'error': str(e)}), 502


def _run_job(job_id: str, user_key: str = "", user_model: str = ""):
    global _demo_running
    job = _jobs[job_id]
    try:
        import demo_runner
        import ai_validator_cma

        job["step"] = 1
        readme, data_hash, _ = demo_runner.load_study()

        job["step"] = 2
        output  = demo_runner.execute_study()
        metrics = demo_runner.parse_metrics(output)

        # Resolve key and routing
        api_key  = user_key or _server_api_key()
        key_type = ai_validator_cma.detect_key_type(api_key)
        model    = user_model or ai_validator_cma.default_model_for(key_type)

        if key_type == "anthropic":
            # Full CMA mode — agents research the study then commit to DHT
            result = ai_validator_cma.run_protocol_cma(
                data_hash, metrics, readme, output, job, api_key,
            )
        elif key_type in ("openai", "google", "groq", "unknown") and api_key:
            # Simple one-shot mode via litellm
            result = ai_validator_cma.run_protocol_simple(
                data_hash, metrics, readme, output, job, api_key, model,
            )
        else:
            # No usable key — fall back to existing demo_runner (also needs Anthropic key)
            job["step"] = 3
            verdicts = demo_runner.form_verdicts(readme, output)
            job["step"] = 4
            result = demo_runner.run_protocol(data_hash, metrics, verdicts, job)

        job["step"]   = 7
        job["status"] = "done"
        job["result"] = result
    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
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
header{background:var(--surface);border-bottom:1px solid var(--border);padding:0 2rem;height:64px;display:flex;align-items:center;gap:1rem}
header a.gh{color:var(--dim);font-size:.8rem;margin-left:auto;text-decoration:none}
header a.gh:hover{color:var(--text)}
.logo-img{height:44px;width:auto;border-radius:6px;display:block}
.tag{font-size:.72rem;color:var(--dim)}
main{max-width:720px;margin:3rem auto;padding:0 1.5rem}
h1{font-family:'Newsreader',Georgia,serif;font-size:2rem;margin-bottom:.5rem}
.lead{color:var(--dim);margin-bottom:2rem;line-height:1.6;font-size:.95rem}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:1.5rem;margin-bottom:1.5rem}
.card h2{font-size:1rem;margin-bottom:.75rem}
.card p{color:var(--dim);font-size:.875rem;line-height:1.6;margin-bottom:.5rem}
.card p:last-child{margin-bottom:0}
.steps-explainer{list-style:none;margin:.5rem 0}
.steps-explainer li{color:var(--dim);font-size:.85rem;line-height:1.6;padding:.2rem 0 .2rem 1.2rem;position:relative}
.steps-explainer li::before{content:'→';position:absolute;left:0;color:var(--accent)}
.btn{background:var(--accent);color:#fff;border:none;padding:.65rem 1.5rem;border-radius:8px;cursor:pointer;font-size:.9rem;font-family:inherit;margin-top:1rem}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--dim);padding:.45rem 1rem;border-radius:6px;cursor:pointer;font-size:.8rem;font-family:inherit;margin-top:.75rem}
.btn-ghost:hover{border-color:var(--accent);color:var(--text)}
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
.share{margin-top:.75rem;font-size:.8rem;color:var(--dim)}
.share a{color:var(--accent);word-break:break-all}
.verify-section{margin-top:1rem;padding-top:1rem;border-top:1px solid var(--border)}
.verify-section p{font-size:.8rem;color:var(--dim);line-height:1.6;margin-bottom:.5rem}
.curl-cmd{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.6rem .8rem;font-family:monospace;font-size:.75rem;color:#a0c8ff;word-break:break-all;margin:.5rem 0}
.raw-json{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.75rem;font-family:monospace;font-size:.75rem;color:var(--text);white-space:pre-wrap;word-break:break-all;margin-top:.5rem;display:none}
.err{background:#1a0a0a;border:1px solid #5c2020;border-radius:10px;padding:1rem;margin-top:1rem;color:#e57373;font-size:.875rem}
.busy{color:var(--yellow);font-size:.85rem;margin-top:.6rem}
</style>
</head>
<body>
<header>
  <img src="/static/valichord-logo.jpeg" alt="ValiChord" class="logo-img" />
  <span class="tag">Reproducibility Validation Protocol</span>
  <a class="gh" href="https://github.com/topeuph-ai/ValiChord" target="_blank">Source code →</a>
</header>
<main>
  <h1>Live Demo</h1>
  <p class="lead">Can an independent party arrive at the same result as the researcher — without anyone being able to change their answer after seeing others'? ValiChord answers that with a commit-reveal protocol running on a peer-to-peer network.</p>

  <div class="card">
    <h2>How it works</h2>
    <ul class="steps-explainer">
      <li><strong>Commit (blind phase):</strong> The researcher executes the study code and hashes the result. Three validators independently do the same and each post a cryptographic commitment to a distributed hash table — without seeing each other's result.</li>
      <li><strong>Reveal:</strong> All parties reveal simultaneously. The network verifies each reveal matches its prior commitment. No one can revise their verdict after seeing others'.</li>
      <li><strong>HarmonyRecord:</strong> A permanent, content-addressed record of the outcome is written to the DHT. The hash in the URL below is unique to this run and retrievable from any node on the network.</li>
    </ul>
    <p style="margin-top:.75rem">The two-minute runtime is real network time — DHT gossip delays, four separate HTTP roundtrips to Oracle nodes, and three Claude Haiku API calls. It is not a timer.</p>
  </div>

  <div class="card">
    <h2>Study: Temperature–Species Richness</h2>
    <p>Linear regression across 20 sampling sites. Claims: slope ≈ 2.4086, R² ≈ 0.9991. Validators reproduce the computation independently and commit their verdict before seeing each other's result.</p>
    <p style="margin-top:.75rem">Validators use Claude Haiku by default (3 minutes to research, no web search limit). Bring your own key and the cost runs against your account — not the demo budget.</p>
    <div style="margin-top:1rem">
      <label style="display:block;font-size:.8rem;color:var(--dim);margin-bottom:.3rem">Your API key (optional — any provider)</label>
      <input id="userKey" type="password" placeholder="sk-ant-… or sk-proj-… or AIzaSy… or gsk_…" style="width:100%;background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.5rem .75rem;color:var(--text);font-size:.85rem;font-family:monospace">
      <label style="display:block;font-size:.8rem;color:var(--dim);margin:.6rem 0 .3rem">Model hint (optional — for non-Anthropic keys)</label>
      <input id="userModel" type="text" placeholder="e.g. openai/gpt-4o  or  gemini/gemini-1.5-pro" style="width:100%;background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.5rem .75rem;color:var(--text);font-size:.85rem;font-family:monospace">
      <p style="font-size:.75rem;color:var(--dim);margin-top:.4rem">Your key is sent over HTTPS, used only for this run, and never logged or stored.</p>
    </div>
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
  const body={
    user_api_key:(document.getElementById('userKey').value||'').trim(),
    user_model:(document.getElementById('userModel').value||'').trim(),
  };
  fetch('/demo/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json()).then(d=>{
    if(d.status==='busy'||d.status==='rate_limited'){
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
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function showResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>`<div class="vrow">Validator ${escHtml(String(v.validator))}: ${escHtml(v.outcome)} (${escHtml(v.confidence)}) — ${escHtml(v.reasoning)}</div>`).join('');
  const shareUrl=escHtml(r.record_url||'');
  const hashB64=encodeURIComponent(r.external_hash_b64||'');
  const curlCmd=shareUrl?'curl '+JSON.stringify(r.record_url||''):'';
  document.getElementById('resultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${escHtml(r.outcome)} — ${escHtml(r.agreement_level)}</div>
    <div class="detail">${escHtml(String(r.validator_count))}/3 validators · ComputationalBiology</div>
    <div class="verdicts">${rows}</div>
    ${shareUrl?`<div class="share">Permanent record: <a href="${shareUrl}" target="_blank">${shareUrl}</a></div>`:''}
    <div class="verify-section">
      <p><strong>Is this real, or just an animation?</strong> The hash above is unique to this run — generated by the Holochain DHT on the Oracle node, not by this page. Fetch it yourself from any machine:</p>
      ${curlCmd?`<div class="curl-cmd">${escHtml(curlCmd)}</div>`:''}
      ${hashB64?`<button class="btn-ghost" onclick="fetchRaw('${hashB64}')">Fetch raw record from Oracle →</button>`:''}
      <pre class="raw-json" id="rawJson"></pre>
    </div>
  </div>`;
}
function fetchRaw(hashB64){
  const pre=document.getElementById('rawJson');
  pre.style.display='block';
  pre.textContent='Fetching…';
  fetch('/demo/record/'+hashB64)
    .then(r=>r.json())
    .then(d=>{pre.textContent=JSON.stringify(d,null,2);})
    .catch(e=>{pre.textContent='Error: '+e.message;});
}
function showErr(msg){const d=document.createElement('div');d.className='err';d.textContent=msg;document.getElementById('resultArea').replaceChildren(d);}
</script>
</body>
</html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
