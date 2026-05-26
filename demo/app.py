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

# ── Free demo state ────────────────────────────────────────────────────────────
_jobs:        dict  = {}
_demo_lock         = threading.Lock()
_demo_running      = False

FREE_COST_ESTIMATE  = 0.10   # conservative upper bound per run (Haiku × 3)
FREE_MONTHLY_BUDGET = 5.00   # ~50 free runs per month
FREE_IP_COOLDOWN    = 86400  # one free run per IP per day

_free_run_count = 0
_free_run_lock  = threading.Lock()
_ip_last_free: dict = defaultdict(float)


def _free_rate_check(ip: str) -> tuple[bool, str]:
    now = time.time()
    wait = FREE_IP_COOLDOWN - (now - _ip_last_free[ip])
    if wait > 0:
        hours = int(wait // 3600)
        mins  = int((wait % 3600) // 60)
        label = f"{hours}h {mins}m" if hours else f"{mins} minutes"
        return False, f"Free demo is limited to once per day per visitor. Try again in ~{label}."
    with _free_run_lock:
        if _free_run_count * FREE_COST_ESTIMATE >= FREE_MONTHLY_BUDGET:
            return False, "Free demo has reached its monthly limit. Check back next month."
    return True, ""


# ── Custom demo state ──────────────────────────────────────────────────────────
_custom_jobs:   dict  = {}
_custom_lock         = threading.Lock()
_custom_running      = False
_CUSTOM_TIMEOUT_SECS = 1800  # release lock if user never clicks Reveal after 30 min


def _server_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPICAPIKEY", "")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/demo')
def demo_page():
    return Response(_DEMO_HTML, mimetype='text/html')


# Free demo ────────────────────────────────────────────────────────────────────

@app.route('/demo/run', methods=['POST'])
def demo_run():
    global _demo_running, _free_run_count

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    allowed, reason = _free_rate_check(ip)
    if not allowed:
        return jsonify({"status": "rate_limited", "message": reason}), 429

    with _demo_lock:
        if _demo_running:
            return jsonify({
                "status":  "busy",
                "message": "Demo in progress — check back in ~2 minutes",
            }), 409
        _demo_running = True

    _ip_last_free[ip] = time.time()
    with _free_run_lock:
        _free_run_count += 1

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"step": 0, "status": "running", "result": None, "error": None}

    threading.Thread(target=_run_free_job, args=(job_id,), daemon=True).start()
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


def _run_free_job(job_id: str):
    global _demo_running
    job = _jobs[job_id]
    try:
        import demo_runner
        job["step"] = 1
        readme, data_hash, _ = demo_runner.load_study()
        job["step"] = 2
        output  = demo_runner.execute_study()
        metrics = demo_runner.parse_metrics(output)
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


# Custom demo ──────────────────────────────────────────────────────────────────

@app.route('/demo/custom/run', methods=['POST'])
def custom_run():
    global _custom_running

    body        = request.get_json(silent=True) or {}
    claim       = (body.get("claim")        or "").strip()
    user_answer = (body.get("user_answer")  or "").strip()
    api_key     = (body.get("user_api_key") or "").strip()

    if not claim:
        return jsonify({"error": "claim is required"}), 400
    if not user_answer:
        return jsonify({"error": "user_answer is required"}), 400
    if not api_key:
        return jsonify({"error": "An Anthropic API key is required for the custom demo"}), 400
    if not api_key.startswith("sk-ant-"):
        return jsonify({"error": "Custom demo requires an Anthropic API key (starts with sk-ant-)"}), 400

    with _custom_lock:
        if _custom_running:
            # Expire stale lock if the previous user never clicked Reveal
            return jsonify({
                "status":  "busy",
                "message": "A custom demo run is in progress. Check back in a few minutes.",
            }), 409
        _custom_running = True

    job_id = str(uuid.uuid4())
    _custom_jobs[job_id] = {
        "phase":               "starting",
        "validators_committed": 0,
        "external_hash_b64":   None,
        "verdicts":            None,
        "metrics":             None,
        "status":              "running",
        "result":              None,
        "error":               None,
        "_claim":              claim,
        "_user_answer":        user_answer,
        "_api_key":            api_key,
        "_started_at":         time.time(),
    }

    threading.Thread(
        target=_run_custom_commit_phase, args=(job_id,), daemon=True,
    ).start()
    return jsonify({"job_id": job_id}), 202


@app.route('/demo/custom/result/<job_id>')
def custom_result(job_id):
    job = _custom_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    # Never return _user_answer/_claim/_api_key in poll responses
    return jsonify({
        "phase":               job["phase"],
        "validators_committed": job["validators_committed"],
        "status":              job["status"],
        "result":              job["result"],
        "error":               job["error"],
    })


@app.route('/demo/custom/reveal/<job_id>', methods=['POST'])
def custom_reveal(job_id):
    job = _custom_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job"}), 404
    if job["phase"] != "awaiting_reveal":
        return jsonify({"error": f"Not ready to reveal (phase: {job['phase']})"}), 409

    threading.Thread(
        target=_run_custom_reveal_phase, args=(job_id,), daemon=True,
    ).start()
    return jsonify({"status": "revealing"}), 202


def _run_custom_commit_phase(job_id: str):
    global _custom_running
    job = _custom_jobs[job_id]
    try:
        import custom_runner
        custom_runner.start_commit_phase(
            job["_claim"], job["_user_answer"], job["_api_key"], job,
        )
        # Lock is intentionally NOT released here — held until reveal completes.
        # If the user never reveals, _CUSTOM_TIMEOUT_SECS background check releases it.
    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
        job["phase"]  = "error"
        _custom_running = False


def _run_custom_reveal_phase(job_id: str):
    global _custom_running
    job = _custom_jobs[job_id]
    try:
        import custom_runner
        custom_runner.finish_reveal_phase(
            job["_claim"], job["_user_answer"], job, job["_api_key"],
        )
    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
        job["phase"]  = "error"
    finally:
        _custom_running = False


def _custom_timeout_watchdog():
    """Release the custom demo lock if the user never clicks Reveal."""
    global _custom_running
    while True:
        time.sleep(60)
        if _custom_running:
            for job in _custom_jobs.values():
                if (
                    job.get("phase") == "awaiting_reveal"
                    and time.time() - job.get("_started_at", 0) > _CUSTOM_TIMEOUT_SECS
                ):
                    job["phase"]  = "error"
                    job["status"] = "error"
                    job["error"]  = "Session expired — reveal not triggered within 30 minutes."
                    _custom_running = False


threading.Thread(target=_custom_timeout_watchdog, daemon=True).start()


# ── HTML ───────────────────────────────────────────────────────────────────────

_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ValiChord — Live Demo</title>
<style>
:root{--bg:#07070f;--surface:#0b0b18;--border:#141424;--text:#c8c4bc;--dim:#6b6880;--accent:#4a90d9;--green:#4caf50;--yellow:#ffc107;--red:#e57373;--r:14px}
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
/* Tabs */
.tabs{display:flex;gap:.5rem;margin-bottom:1.5rem}
.tab-btn{background:var(--surface);border:1px solid var(--border);color:var(--dim);padding:.5rem 1.25rem;border-radius:8px;cursor:pointer;font-size:.875rem;font-family:inherit;transition:all .2s}
.tab-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
/* Cards */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:1.5rem;margin-bottom:1.5rem}
.card h2{font-size:1rem;margin-bottom:.75rem}
.card p{color:var(--dim);font-size:.875rem;line-height:1.6;margin-bottom:.5rem}
.card p:last-child{margin-bottom:0}
.steps-explainer{list-style:none;margin:.5rem 0}
.steps-explainer li{color:var(--dim);font-size:.85rem;line-height:1.6;padding:.2rem 0 .2rem 1.2rem;position:relative}
.steps-explainer li::before{content:'→';position:absolute;left:0;color:var(--accent)}
/* Buttons */
.btn{background:var(--accent);color:#fff;border:none;padding:.65rem 1.5rem;border-radius:8px;cursor:pointer;font-size:.9rem;font-family:inherit;margin-top:1rem;transition:background .2s}
.btn:disabled{opacity:.35;cursor:not-allowed;animation:none!important}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--dim);padding:.45rem 1rem;border-radius:6px;cursor:pointer;font-size:.8rem;font-family:inherit;margin-top:.75rem}
.btn-ghost:hover{border-color:var(--accent);color:var(--text)}
/* Free demo progress */
.steps{list-style:none;margin-top:1rem}
.steps li{display:flex;align-items:center;gap:.75rem;padding:.4rem 0;font-size:.875rem;color:var(--dim)}
.dot{width:18px;height:18px;border-radius:50%;border:2px solid var(--border);flex-shrink:0;transition:all .3s}
li.active .dot{border-color:var(--accent);background:var(--accent);animation:pulse 1s infinite}
li.done .dot{border-color:var(--green);background:var(--green)}
li.active,li.done{color:var(--text)}
/* Custom demo form */
.field-label{display:block;font-size:.8rem;color:var(--dim);margin:.85rem 0 .3rem}
textarea,input[type=password]{width:100%;background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.55rem .75rem;color:var(--text);font-size:.85rem;font-family:inherit;resize:vertical;outline:none}
textarea:focus,input[type=password]:focus{border-color:var(--accent)}
textarea{min-height:80px}
.key-note{font-size:.75rem;color:var(--dim);margin-top:.3rem}
.rate-note{font-size:.75rem;color:var(--dim);margin-top:.3rem}
/* Custom demo commit progress */
.commit-row{display:flex;align-items:center;gap:.75rem;padding:.4rem 0;font-size:.875rem;color:var(--dim)}
.commit-row.done{color:var(--text)}
.vdot{width:14px;height:14px;border-radius:50%;border:2px solid var(--border);flex-shrink:0;transition:all .3s}
.vdot.active{border-color:var(--accent);background:var(--accent);animation:pulse 1s infinite}
.vdot.done{border-color:var(--green);background:var(--green)}
.reveal-prompt{font-size:.875rem;color:var(--green);margin:.75rem 0 .25rem;font-weight:500}
/* Reveal button ready state */
@keyframes readyPulse{0%,100%{box-shadow:0 0 0 0 rgba(76,175,80,.75)}50%{box-shadow:0 0 0 14px rgba(76,175,80,0)}}
.btn-ready{background:var(--green)!important;animation:readyPulse 1.2s ease-in-out infinite}
/* Results */
.result-box{background:var(--bg);border:1px solid var(--green);border-radius:10px;padding:1rem 1.25rem;margin-top:1rem}
.outcome{font-size:1.1rem;font-weight:600;color:var(--green)}
.detail{font-size:.8rem;color:var(--dim);margin-top:.2rem}
.comparison-summary{font-size:.875rem;color:var(--text);margin:.6rem 0;line-height:1.5}
.verdicts{margin-top:.6rem}
.vrow{font-size:.8rem;color:var(--dim);padding:.2rem 0}
.researcher-reveal{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.6rem .8rem;margin:.6rem 0;font-size:.8rem;color:var(--text);line-height:1.5}
.researcher-reveal strong{color:var(--dim);display:block;margin-bottom:.25rem;font-size:.75rem}
.share{margin-top:.75rem;font-size:.8rem;color:var(--dim)}
.share a{color:var(--accent);word-break:break-all}
.verify-section{margin-top:1rem;padding-top:1rem;border-top:1px solid var(--border)}
.verify-section p{font-size:.8rem;color:var(--dim);line-height:1.6;margin-bottom:.5rem}
.curl-cmd{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.6rem .8rem;font-family:monospace;font-size:.75rem;color:#a0c8ff;word-break:break-all;margin:.5rem 0}
.raw-json{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.75rem;font-family:monospace;font-size:.75rem;color:var(--text);white-space:pre-wrap;word-break:break-all;margin-top:.5rem;display:none}
.err{background:#1a0a0a;border:1px solid #5c2020;border-radius:10px;padding:1rem;margin-top:1rem;color:var(--red);font-size:.875rem}
.busy{color:var(--yellow);font-size:.85rem;margin-top:.6rem}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}
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
  <p class="lead">Can an independent party arrive at the same result as the researcher — without anyone being able to change their answer after seeing others'? ValiChord answers that with a commit-reveal protocol on a peer-to-peer network.</p>

  <div class="card">
    <h2>How it works</h2>
    <ul class="steps-explainer">
      <li><strong>Commit (blind):</strong> Every party hashes and seals their verdict before anyone reveals. No one can see each other's result during this phase.</li>
      <li><strong>Reveal:</strong> All parties reveal simultaneously. The network verifies each reveal matches its prior commitment hash. No last-mover advantage is possible.</li>
      <li><strong>HarmonyRecord:</strong> A permanent, content-addressed record is written to the DHT. The hash is unique to the run and independently fetchable from any node.</li>
    </ul>
  </div>

  <div class="tabs">
    <button class="tab-btn active" id="tab-free" onclick="showTab('free')">Free Demo</button>
    <button class="tab-btn" id="tab-custom" onclick="showTab('custom')">Your Hypothesis</button>
  </div>

  <!-- ── Free demo ─────────────────────────────────────────────────────────── -->
  <div id="section-free">
    <div class="card">
      <h2>Study: Temperature–Species Richness</h2>
      <p>Linear regression across 20 sampling sites. The researcher claims slope ≈ 2.4086, R² ≈ 0.9991. Three AI validators independently reproduce the computation and commit their verdicts blind before anyone reveals.</p>
      <p class="rate-note">Free · uses the server's API key · limited to once per visitor per day</p>
      <button class="btn" id="runBtn" onclick="startDemo()">Run Protocol (~2 min)</button>
      <div id="busyMsg" class="busy" style="display:none"></div>
    </div>

    <div class="card" id="progressCard" style="display:none">
      <h2>Protocol progress</h2>
      <ul class="steps">
        <li id="s1"><span class="dot"></span>Loading study deposit</li>
        <li id="s2"><span class="dot"></span>Executing study code</li>
        <li id="s3"><span class="dot"></span>Forming 3 independent verdicts</li>
        <li id="s4"><span class="dot"></span>Committing to DHT — blind phase</li>
        <li id="s5"><span class="dot"></span>All commitments sealed</li>
        <li id="s6"><span class="dot"></span>Researcher + validators revealed</li>
        <li id="s7"><span class="dot"></span>HarmonyRecord written</li>
      </ul>
      <div id="resultArea"></div>
    </div>
  </div>

  <!-- ── Custom demo ───────────────────────────────────────────────────────── -->
  <div id="section-custom" style="display:none">
    <div class="card" id="customInputCard">
      <h2>State your hypothesis</h2>
      <p>Enter any factual, evaluable claim. Three AI validators will independently research it with web search and commit their verdicts blind — without seeing your answer or each other's. You control the reveal.</p>

      <label class="field-label">Hypothesis or claim</label>
      <textarea id="customClaim" rows="3" placeholder="e.g. Regular aerobic exercise reduces resting heart rate in healthy adults" oninput="checkCustomReady()"></textarea>

      <label class="field-label">Your answer <span style="color:var(--dim);font-weight:400">(sealed as a commitment before validators start)</span></label>
      <textarea id="customAnswer" rows="4" placeholder="State your position and reasoning. This is hashed and committed to the DHT before the validators begin — they cannot see it until you click Reveal." oninput="checkCustomReady()"></textarea>

      <label class="field-label">Your Anthropic API key</label>
      <input id="customKey" type="password" placeholder="sk-ant-…" oninput="checkCustomReady()">
      <p class="key-note">CMA validators (web search, multi-step reasoning). Charges go to your account (~$0.50–1.50 per run). Your key is sent over HTTPS, used only for this run, and never stored.</p>

      <button class="btn" id="customSubmitBtn" onclick="startCustomDemo()" disabled>
        Seal my answer and start validation
      </button>
      <div id="customBusyMsg" class="busy" style="display:none"></div>
    </div>

    <div class="card" id="customProgressCard" style="display:none">
      <h2>Commit phase</h2>

      <div class="commit-row done" id="researcherCommitRow">
        <span class="vdot done"></span> Your answer sealed on DHT
      </div>
      <div class="commit-row" id="v1row">
        <span class="vdot active" id="cv1"></span>
        <span id="v1label">Validator 1 researching…</span>
      </div>
      <div class="commit-row" id="v2row">
        <span class="vdot" id="cv2"></span>
        <span id="v2label">Validator 2 waiting…</span>
      </div>
      <div class="commit-row" id="v3row">
        <span class="vdot" id="cv3"></span>
        <span id="v3label">Validator 3 waiting…</span>
      </div>

      <p class="reveal-prompt" id="revealPrompt" style="display:none">
        All 3 validators have committed. No one can change their verdict now. Click to reveal your answer.
      </p>
      <button class="btn" id="revealBtn" disabled onclick="triggerReveal()">
        Reveal my answer
      </button>

      <div id="customResultArea"></div>
    </div>
  </div>

</main>
<script>
// ── Tab switching ─────────────────────────────────────────────────────────────
function showTab(t) {
  ['free','custom'].forEach(id => {
    document.getElementById('tab-'+id).classList.toggle('active', id===t);
    document.getElementById('section-'+id).style.display = id===t ? 'block' : 'none';
  });
}

// ── Free demo ─────────────────────────────────────────────────────────────────
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
    if(d.status==='busy'||d.status==='rate_limited'){
      document.getElementById('busyMsg').textContent=d.message;
      document.getElementById('busyMsg').style.display='block';
      btn.disabled=false;pc.style.display='none';return;
    }
    if(!d.job_id){showErr('resultArea','Failed to start: '+JSON.stringify(d));btn.disabled=false;return;}
    poll=setInterval(()=>doPoll(d.job_id),2000);
  }).catch(e=>{showErr('resultArea','Network error: '+e.message);btn.disabled=false;});
}
function doPoll(id){
  fetch('/demo/result/'+id).then(r=>r.json()).then(j=>{
    setSteps(j.step,false);
    if(j.status==='done'){clearInterval(poll);setSteps(7,true);showFreeResult(j.result);document.getElementById('runBtn').disabled=false;}
    else if(j.status==='error'){clearInterval(poll);showErr('resultArea',j.error||'Unknown error');document.getElementById('runBtn').disabled=false;}
  }).catch(e=>console.error('poll:',e));
}
function setSteps(cur,done){
  for(let i=1;i<=7;i++){
    const li=document.getElementById('s'+i),dot=li.querySelector('.dot');
    if(i<cur){li.className='done';dot.className='dot';}
    else if(i===cur&&!done){li.className='active';dot.className='dot';}
    else if(i===cur&&done){li.className='done';dot.className='dot';}
    else{li.className='';dot.className='dot';}
  }
}

// ── Custom demo ───────────────────────────────────────────────────────────────
let customPoll=null, customJobId=null;

function checkCustomReady(){
  const ok=document.getElementById('customClaim').value.trim()
         &&document.getElementById('customAnswer').value.trim()
         &&document.getElementById('customKey').value.trim().startsWith('sk-ant-');
  document.getElementById('customSubmitBtn').disabled=!ok;
}

function startCustomDemo(){
  const claim  = document.getElementById('customClaim').value.trim();
  const answer = document.getElementById('customAnswer').value.trim();
  const key    = document.getElementById('customKey').value.trim();

  document.getElementById('customSubmitBtn').disabled=true;
  document.getElementById('customBusyMsg').style.display='none';
  document.getElementById('customInputCard').style.opacity='.5';

  const pc=document.getElementById('customProgressCard');
  pc.style.display='block';
  document.getElementById('customResultArea').innerHTML='';

  // Reset validator dots
  setCustomDots(0);
  document.getElementById('revealPrompt').style.display='none';
  const rb=document.getElementById('revealBtn');
  rb.disabled=true; rb.classList.remove('btn-ready'); rb.textContent='Reveal my answer';

  fetch('/demo/custom/run',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({claim,user_answer:answer,user_api_key:key}),
  }).then(r=>r.json()).then(d=>{
    if(d.status==='busy'){
      document.getElementById('customBusyMsg').textContent=d.message;
      document.getElementById('customBusyMsg').style.display='block';
      document.getElementById('customSubmitBtn').disabled=false;
      document.getElementById('customInputCard').style.opacity='1';
      pc.style.display='none'; return;
    }
    if(d.error||!d.job_id){
      showErr('customResultArea',d.error||'Failed to start: '+JSON.stringify(d));
      document.getElementById('customSubmitBtn').disabled=false;
      document.getElementById('customInputCard').style.opacity='1';
      return;
    }
    customJobId=d.job_id;
    customPoll=setInterval(()=>pollCustom(d.job_id),2000);
  }).catch(e=>{
    showErr('customResultArea','Network error: '+e.message);
    document.getElementById('customSubmitBtn').disabled=false;
    document.getElementById('customInputCard').style.opacity='1';
  });
}

function pollCustom(id){
  fetch('/demo/custom/result/'+id).then(r=>r.json()).then(j=>{
    setCustomDots(j.validators_committed||0);

    if(j.phase==='awaiting_reveal'){
      clearInterval(customPoll);
      enableRevealBtn();
    } else if(j.phase==='revealing'){
      // Keep UI in "revealing" state while the background thread works
    } else if(j.status==='done'){
      clearInterval(customPoll);
      showCustomResult(j.result);
      document.getElementById('customInputCard').style.opacity='1';
      document.getElementById('customSubmitBtn').disabled=false;
    } else if(j.status==='error'){
      clearInterval(customPoll);
      showErr('customResultArea',j.error||'Unknown error');
      document.getElementById('customInputCard').style.opacity='1';
      document.getElementById('customSubmitBtn').disabled=false;
    }
  }).catch(e=>console.error('custom poll:',e));
}

function setCustomDots(count){
  const labels=['Validator 1','Validator 2','Validator 3'];
  for(let i=1;i<=3;i++){
    const dot=document.getElementById('cv'+i);
    const row=document.getElementById('v'+i+'row');
    const lbl=document.getElementById('v'+i+'label');
    if(i<=count){
      dot.className='vdot done'; row.className='commit-row done';
      lbl.textContent=labels[i-1]+' committed ✓';
    } else if(i===count+1){
      dot.className='vdot active'; row.className='commit-row';
      lbl.textContent=labels[i-1]+' researching…';
    } else {
      dot.className='vdot'; row.className='commit-row';
      lbl.textContent=labels[i-1]+' waiting…';
    }
  }
}

function enableRevealBtn(){
  setCustomDots(3);
  document.getElementById('revealPrompt').style.display='block';
  const btn=document.getElementById('revealBtn');
  btn.disabled=false;
  btn.classList.add('btn-ready');
}

function triggerReveal(){
  const btn=document.getElementById('revealBtn');
  btn.disabled=true;
  btn.classList.remove('btn-ready');
  btn.textContent='Revealing…';
  document.getElementById('revealPrompt').style.display='none';

  fetch('/demo/custom/reveal/'+customJobId,{method:'POST'})
    .then(r=>r.json())
    .then(d=>{
      if(d.error){showErr('customResultArea',d.error);return;}
      customPoll=setInterval(()=>pollCustom(customJobId),2000);
    })
    .catch(e=>showErr('customResultArea','Network error: '+e.message));
}

// ── Result rendering ──────────────────────────────────────────────────────────
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

const OUTCOME_LABEL={
  'Reproduced':         'Aligned with validators',
  'PartiallyReproduced':'Partially aligned',
  'NotReproduced':      'Diverged from validators',
  'FailedToReproduce':  'Failed to reproduce',
  'UnableToAssess':     'Unable to assess',
};

function showFreeResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>
    `<div class="vrow">Validator ${esc(v.validator)}: ${esc(v.outcome)} (${esc(v.confidence)}) — ${esc(v.reasoning)}</div>`
  ).join('');
  const shareUrl=esc(r.record_url||'');
  const curlCmd=r.record_url?'curl '+JSON.stringify(r.record_url):'';
  const hashB64=encodeURIComponent(r.external_hash_b64||'');
  document.getElementById('resultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${esc(r.outcome)} — ${esc(r.agreement_level)}</div>
    <div class="detail">${esc(r.validator_count)}/3 validators · ComputationalBiology</div>
    <div class="verdicts">${rows}</div>
    ${shareUrl?`<div class="share">Permanent record: <a href="${shareUrl}" target="_blank">${shareUrl}</a></div>`:''}
    <div class="verify-section">
      <p><strong>Is this real?</strong> The hash is unique to this run — generated on the Oracle DHT, not by this page. Fetch it yourself:</p>
      ${curlCmd?`<div class="curl-cmd">${esc(curlCmd)}</div>`:''}
      ${hashB64?`<button class="btn-ghost" onclick="fetchRaw('resultArea','${hashB64}')">Fetch raw record from Oracle →</button>`:''}
      <pre class="raw-json" id="rawJson"></pre>
    </div>
  </div>`;
}

function showCustomResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>
    `<div class="vrow">Validator ${esc(v.validator)}: ${esc(v.outcome)} (${esc(v.confidence)}) — ${esc(v.reasoning)}</div>`
  ).join('');
  const shareUrl=esc(r.record_url||'');
  const curlCmd=r.record_url?'curl '+JSON.stringify(r.record_url):'';
  const hashB64=encodeURIComponent(r.external_hash_b64||'');
  const outcomeLabel=OUTCOME_LABEL[r.outcome]||esc(r.outcome);
  document.getElementById('customResultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${outcomeLabel} — ${esc(r.agreement_level)}</div>
    <div class="detail">${esc(r.validator_count)}/3 validators · your hypothesis</div>
    ${r.comparison_summary?`<div class="comparison-summary">${esc(r.comparison_summary)}</div>`:''}
    <div class="researcher-reveal">
      <strong>Your sealed answer (revealed now):</strong>
      ${esc(r.researcher_answer||'')}
    </div>
    <div class="verdicts">${rows}</div>
    ${shareUrl?`<div class="share">Permanent record: <a href="${shareUrl}" target="_blank">${shareUrl}</a></div>`:''}
    <div class="verify-section">
      <p><strong>Is this real?</strong> Your answer hash was committed to the Oracle DHT before the validators started. The record is independently fetchable:</p>
      ${curlCmd?`<div class="curl-cmd">${esc(curlCmd)}</div>`:''}
      ${hashB64?`<button class="btn-ghost" onclick="fetchRaw('customResultArea','${hashB64}')">Fetch raw record from Oracle →</button>`:''}
      <pre class="raw-json" id="customRawJson"></pre>
    </div>
  </div>`;
}

function fetchRaw(areaId,hashB64){
  const jsonId=areaId==='resultArea'?'rawJson':'customRawJson';
  const pre=document.getElementById(jsonId);
  pre.style.display='block'; pre.textContent='Fetching…';
  fetch('/demo/record/'+hashB64).then(r=>r.json())
    .then(d=>{pre.textContent=JSON.stringify(d,null,2);})
    .catch(e=>{pre.textContent='Error: '+e.message;});
}

function showErr(areaId,msg){
  const d=document.createElement('div');
  d.className='err'; d.textContent=msg;
  document.getElementById(areaId).replaceChildren(d);
}
</script>
</body>
</html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
