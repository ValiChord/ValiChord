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
    decoded = urllib.parse.unquote(hash_b64)
    url = f'{demo_runner.RESEARCHER_URL}/record?hash={urllib.parse.quote(decoded)}'
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
    <p>Linear regression across 20 sampling sites. Claims: slope ≈ 2.4086, R² ≈ 0.9991. Validators reproduce the computation independently and commit their verdict before seeing each other's result.</p>
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
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function showResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>`<div class="vrow">Validator ${escHtml(String(v.validator))}: ${escHtml(v.outcome)} (${escHtml(v.confidence)}) — ${escHtml(v.reasoning)}</div>`).join('');
  const shareUrl=r.record_url||'';
  const shareHtml=shareUrl?`<div class="share">Permanent record: <a href="${escHtml(shareUrl)}" target="_blank">${escHtml(shareUrl)}</a></div>`:'';
  document.getElementById('resultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${escHtml(r.outcome)} — ${escHtml(r.agreement_level)}</div>
    <div class="detail">${escHtml(String(r.validator_count))}/3 validators · ComputationalBiology</div>
    <div class="verdicts">${rows}</div>
    ${shareHtml}
  </div>`;
}
function showErr(msg){const d=document.createElement('div');d.className='err';d.textContent=msg;document.getElementById('resultArea').replaceChildren(d);}
</script>
</body>
</html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
