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

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"step": 0, "status": "running", "result": None, "error": None, "_ip": ip}

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
    global _demo_running, _free_run_count
    job = _jobs[job_id]
    ip  = job.pop("_ip", "")
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
        # Record usage only on success so failed runs don't burn the daily quota
        _ip_last_free[ip] = time.time()
        with _free_run_lock:
            _free_run_count += 1
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
    """Release the custom demo lock if a run gets stuck in any non-terminal phase."""
    global _custom_running
    while True:
        time.sleep(60)
        if _custom_running:
            for job in _custom_jobs.values():
                phase = job.get("phase", "")
                age   = time.time() - job.get("_started_at", 0)
                if phase not in ("done", "error") and age > _CUSTOM_TIMEOUT_SECS:
                    print(f"Watchdog: releasing stuck job in phase={phase!r} after {age:.0f}s", flush=True)
                    job["phase"]  = "error"
                    job["status"] = "error"
                    job["error"]  = (
                        f"Session timed out in phase '{phase}' after "
                        f"{_CUSTOM_TIMEOUT_SECS // 60} minutes."
                    )
                    _custom_running = False
                    break  # only one lock to release; re-check next minute


threading.Thread(target=_custom_timeout_watchdog, daemon=True).start()


# ── HTML ───────────────────────────────────────────────────────────────────────

_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ValiChord — Reproducibility Validation Protocol</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Newsreader:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{--bg:#07070f;--surface:#0b0b18;--surface2:#0e0e1c;--border:#141424;--border2:#1e1e30;--text:#c8c4bc;--dim:#6b6880;--accent:#4a90d9;--green:#4caf50;--yellow:#ffc107;--red:#e57373;--r:12px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',system-ui,sans-serif;min-height:100vh;-webkit-font-smoothing:antialiased}
header{background:var(--surface);border-bottom:1px solid var(--border);padding:0 2rem;height:64px;display:flex;align-items:center;gap:1rem}
.logo-img{height:40px;width:auto;border-radius:6px}
.tag{font-size:.72rem;color:var(--dim);letter-spacing:.04em}
header a.gh{color:var(--dim);font-size:.8rem;text-decoration:none;padding:.3rem .7rem;border:1px solid var(--border);border-radius:6px;transition:all .2s}
header a.gh:hover{border-color:var(--accent);color:var(--text)}
.holo-link{margin-left:auto;display:flex;flex-direction:column;align-items:center;gap:.1rem;text-decoration:none;padding:.2rem .5rem;border-radius:6px;transition:opacity .2s;flex-shrink:0}
.holo-link:hover{opacity:.75}
.holo-built{font-size:.58rem;color:var(--dim);text-transform:uppercase;letter-spacing:.09em}
.holo-logo{height:22px;width:auto}
main{max-width:680px;margin:0 auto;padding:3rem 1.5rem 5rem}
.hero{margin-bottom:2.5rem}
.hero h1{font-family:'Newsreader',Georgia,serif;font-size:2.2rem;font-weight:600;line-height:1.2;margin-bottom:.8rem;letter-spacing:-.01em}
.hero-lead{color:var(--dim);line-height:1.75;font-size:.95rem;max-width:580px}
.hero-lead em{color:var(--text);font-style:normal}
.section-label{display:flex;align-items:center;gap:.7rem;font-size:.68rem;text-transform:uppercase;letter-spacing:.12em;color:var(--accent);margin-bottom:.8rem;font-weight:600}
.section-label::after{content:'';flex:1;height:1px;background:var(--border2)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:1.5rem;margin-bottom:1rem}
.card-primary{border-color:var(--border2);background:linear-gradient(155deg,#0c0c20 0%,var(--surface) 60%)}
.card h2{font-size:1rem;font-weight:600;margin-bottom:.55rem}
.card p{color:var(--dim);font-size:.875rem;line-height:1.65;margin-bottom:.5rem}
.card p:last-child{margin-bottom:0}
.btn{background:var(--accent);color:#fff;border:none;padding:.65rem 1.4rem;border-radius:8px;cursor:pointer;font-size:.875rem;font-family:inherit;font-weight:500;transition:all .2s;display:inline-block;margin-top:1.1rem}
.btn:hover:not(:disabled){background:#5a9fe8}
.btn:disabled{opacity:.3;cursor:not-allowed;animation:none!important}
.btn-muted{background:var(--surface2);border:1px solid var(--border);color:var(--text)}
.btn-muted:hover:not(:disabled){border-color:var(--accent);background:var(--surface2)}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--dim);padding:.4rem .9rem;border-radius:6px;cursor:pointer;font-size:.8rem;font-family:inherit;transition:all .2s;margin-top:.5rem}
.btn-ghost:hover{border-color:var(--accent);color:var(--text)}
.field-label{display:block;font-size:.78rem;color:var(--dim);margin:.9rem 0 .3rem;letter-spacing:.02em}
textarea,input[type=password]{width:100%;background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.6rem .8rem;color:var(--text);font-size:.85rem;font-family:inherit;resize:vertical;outline:none;transition:border-color .2s}
textarea:focus,input[type=password]:focus{border-color:var(--accent)}
textarea{min-height:76px}
.key-note,.rate-note{font-size:.75rem;color:var(--dim);margin-top:.35rem;line-height:1.55}
.steps{list-style:none;margin-top:1rem}
.steps li{display:flex;align-items:center;gap:.75rem;padding:.35rem 0;font-size:.875rem;color:var(--dim)}
.dot{width:16px;height:16px;border-radius:50%;border:2px solid var(--border);flex-shrink:0;transition:all .3s}
li.active .dot{border-color:var(--accent);background:var(--accent);animation:pulse 1.2s infinite}
li.done .dot{border-color:var(--green);background:var(--green)}
li.active,li.done{color:var(--text)}
.commit-row{display:flex;align-items:center;gap:.75rem;padding:.35rem 0;font-size:.875rem;color:var(--dim)}
.commit-row.done{color:var(--text)}
.vdot{width:13px;height:13px;border-radius:50%;border:2px solid var(--border);flex-shrink:0;transition:all .3s}
.vdot.active{border-color:var(--accent);background:var(--accent);animation:pulse 1.2s infinite}
.vdot.done{border-color:var(--green);background:var(--green)}
.reveal-prompt{font-size:.875rem;color:var(--green);margin:.9rem 0 .25rem;font-weight:500;line-height:1.55}
@keyframes readyPulse{0%,100%{box-shadow:0 0 0 0 rgba(76,175,80,.75)}50%{box-shadow:0 0 0 14px rgba(76,175,80,0)}}
.btn-ready{background:var(--green)!important;animation:readyPulse 1.2s ease-in-out infinite}
.result-box{background:var(--bg);border:1px solid var(--green);border-radius:10px;padding:1.1rem 1.25rem;margin-top:1rem}
.outcome{font-size:1.05rem;font-weight:600;color:var(--green)}
.detail{font-size:.78rem;color:var(--dim);margin-top:.2rem}
.comparison-summary{font-size:.875rem;color:var(--text);margin:.65rem 0;line-height:1.6}
.verdicts{margin-top:.6rem}
.vrow{font-size:.78rem;color:var(--dim);padding:.2rem 0;line-height:1.55}
.researcher-reveal{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.65rem .9rem;margin:.6rem 0;font-size:.82rem;color:var(--text);line-height:1.55}
.researcher-reveal strong{color:var(--dim);display:block;margin-bottom:.3rem;font-size:.7rem;text-transform:uppercase;letter-spacing:.07em}
.share{margin-top:.75rem;font-size:.78rem;color:var(--dim)}
.share a{color:var(--accent);word-break:break-all}
.verify-section{margin-top:.9rem;padding-top:.9rem;border-top:1px solid var(--border)}
.verify-section p{font-size:.78rem;color:var(--dim);line-height:1.6;margin-bottom:.4rem}
.curl-cmd{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.5rem .8rem;font-family:monospace;font-size:.72rem;color:#a0c8ff;word-break:break-all;margin:.4rem 0}
.raw-json{background:#0d0d1a;border:1px solid var(--border);border-radius:6px;padding:.75rem;font-family:monospace;font-size:.72rem;color:var(--text);white-space:pre-wrap;word-break:break-all;margin-top:.5rem;display:none}
.err{background:#1a0a0a;border:1px solid #5c2020;border-radius:10px;padding:.9rem 1rem;margin-top:.75rem;color:var(--red);font-size:.85rem;line-height:1.5}
.busy{color:var(--yellow);font-size:.82rem;margin-top:.5rem;line-height:1.5}
/* accordion */
.explainers{margin:2rem 0}
details{border:1px solid var(--border);border-radius:var(--r);margin-bottom:.45rem;background:var(--surface);overflow:hidden}
summary{padding:.85rem 1.2rem;cursor:pointer;font-size:.88rem;font-weight:500;list-style:none;display:flex;justify-content:space-between;align-items:center;user-select:none}
summary::-webkit-details-marker{display:none}
summary::after{content:'▸';color:var(--dim);transition:transform .2s;font-size:.82rem;margin-left:.75rem;flex-shrink:0}
details[open]>summary{color:var(--accent)}
details[open]>summary::after{transform:rotate(90deg)}
.expand-body{padding:.1rem 1.2rem 1.1rem;border-top:1px solid var(--border)}
.expand-body p{color:var(--dim);font-size:.875rem;line-height:1.72;margin-top:.65rem}
.expand-body strong{color:var(--text);font-weight:500}
.expand-body em{color:var(--text);font-style:normal;font-weight:500}
/* section divider */
.section-divider{display:flex;align-items:center;gap:1rem;margin:2.5rem 0 1.25rem;color:var(--dim);font-size:.72rem;text-transform:uppercase;letter-spacing:.1em}
.section-divider::before,.section-divider::after{content:'';flex:1;height:1px;background:var(--border)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
</style>
</head>
<body>
<header>
  <img src="/static/valichord-logo.jpeg" alt="ValiChord" class="logo-img">
  <span class="tag">Reproducibility Validation Protocol</span>
  <a class="holo-link" href="https://www.holochain.org" target="_blank">
    <span class="holo-built">Built on</span>
    <img src="/static/holochain-logo.png" alt="Holochain" class="holo-logo">
  </a>
  <a class="gh" href="https://github.com/topeuph-ai/ValiChord" target="_blank">Source →</a>
</header>
<main>

<div class="hero">
  <h1>Prove it. Independently.</h1>
  <p class="hero-lead">ValiChord asks one question: <em>can an independent party arrive at the same result as the researcher — without anyone being able to change their answer after seeing others'?</em> State a hypothesis, seal your answer, and watch three AI validators research it blind. The reveal is yours to trigger.</p>
</div>

<!-- ── Your Hypothesis — PRIMARY ─────────────────────────────────────────── -->
<div class="section-label">Your Hypothesis</div>

<div class="card card-primary" id="customInputCard">
  <h2>State a hypothesis. Seal your answer. Let the validators run.</h2>
  <p>Enter any evaluable claim — scientific, empirical, philosophical, or evidence-based. Write your verdict in the answer field. That answer is cryptographically hashed and committed to the distributed network <em>before</em> the three AI validators begin their independent research. They cannot see your answer. They cannot see each other's. Only after all three have committed can you trigger the reveal.</p>

  <label class="field-label">Hypothesis or claim</label>
  <textarea id="customClaim" rows="3" placeholder="e.g. Regular aerobic exercise reduces resting heart rate in healthy adults" oninput="checkCustomReady()"></textarea>

  <label class="field-label">Your answer <span style="font-weight:400;color:var(--dim)">(sealed before validators start — they cannot see this)</span></label>
  <textarea id="customAnswer" rows="4" placeholder="State your position and reasoning. This is hashed and committed to the DHT before the validators begin." oninput="checkCustomReady()"></textarea>

  <label class="field-label">Your Anthropic API key</label>
  <input id="customKey" type="password" placeholder="sk-ant-…" oninput="checkCustomReady()">
  <p class="key-note">Runs 3 Claude validators with live web search and multi-step reasoning. Estimated cost: $0.50–1.50. Sent over HTTPS, used only for this run, never stored.</p>

  <button class="btn" id="customSubmitBtn" onclick="startCustomDemo()" disabled>Seal my answer and start validation</button>
  <div id="customBusyMsg" class="busy" style="display:none"></div>
</div>

<div class="card" id="customProgressCard" style="display:none">
  <h2>Commit phase — blind</h2>
  <div class="commit-row done" id="researcherCommitRow">
    <span class="vdot done"></span> Your answer sealed on DHT
  </div>
  <div class="commit-row" id="v1row"><span class="vdot active" id="cv1"></span><span id="v1label">Validator 1 researching…</span></div>
  <div class="commit-row" id="v2row"><span class="vdot" id="cv2"></span><span id="v2label">Validator 2 waiting…</span></div>
  <div class="commit-row" id="v3row"><span class="vdot" id="cv3"></span><span id="v3label">Validator 3 waiting…</span></div>
  <p class="reveal-prompt" id="revealPrompt" style="display:none">All 3 validators have committed. No one can change their verdict now.<br>Click below to unseal your answer.</p>
  <button class="btn" id="revealBtn" disabled onclick="triggerReveal()">Reveal my answer</button>
  <div id="customResultArea"></div>
</div>

<!-- ── Explainers ─────────────────────────────────────────────────────────── -->
<div class="explainers">

  <details>
    <summary>How does this ValiChord demo work?</summary>
    <div class="expand-body">
      <p>The mathematical engine at ValiChord's core is a <strong>commit-reveal protocol</strong> — a cryptographic primitive invented by Manuel Blum in 1981 to solve a deceptively simple problem: how can two people who don't trust each other flip a fair coin over a telephone? One person hashes their guess and shares the hash; the coin is flipped; then they reveal their guess. Neither can change their mind after seeing the outcome. ValiChord takes that primitive — invented for flipping coins — and turns it into a mirror for institutional truth.</p>
      <p>Every party — the researcher and each validator — cryptographically hashes and seals their verdict <em>before</em> anyone reveals anything. These commitments are stored on a Holochain DHT: a distributed hash table where no single node is in charge. Once all commitments are on the network, you trigger the reveal phase. Each reveal is verified against its prior hash — making it <strong>mathematically impossible</strong> to change your answer after seeing anyone else's. No last-mover advantage. No institutional pressure that could nudge a result retroactively.</p>
      <p>In this demo, the Holochain conductors run on a dedicated server so you don't need to install anything. In the full protocol, every participant runs their own conductor — the network is entirely peer-to-peer with no central infrastructure at all.</p>
      <p>The final HarmonyRecord is written to the DHT with a permanent, content-addressed hash you can fetch from any node, independently of this website. What you get is not just a verdict — it's <strong>proof of the process</strong>. The record shows who committed what, and in what order. That's what makes it trustworthy.</p>
    </div>
  </details>

  <details>
    <summary>Why is this remarkable?</summary>
    <div class="expand-body">
      <p>Throughout the history of computing, architectures have been built to answer one of two questions. The first: <em>"Is this data mathematically valid and unchanged?"</em> — solved by cryptography, hash trees, digital signatures. The second: <em>"What do the majority of nodes or humans say is true?"</em> — solved by Byzantine fault tolerance, voting systems, and peer review. ValiChord is the first architecture designed to use the mathematical tools of the <em>first</em> question to address the social dynamics of the <em>second</em>.</p>
      <p>The dynamic it addresses is well-documented in the literature: when reviewers can see each other's conclusions, they tend to converge — not always because the evidence demands it, but because professional context shapes interpretation. This is the same anchoring and information-cascade effect that motivated the invention of double-blind trials. ValiChord makes that convergence <strong>structurally impossible</strong> during the commit phase. There is no mechanism — technically, not just procedurally — by which a validator can adjust their verdict after seeing anyone else's.</p>
      <p>Science's reproducibility challenges are well-documented across disciplines — results that cannot be independently verified erode confidence in the research base over time. ValiChord adds a layer of <strong>cryptographic proof of process</strong> alongside institutional trust. The hash on the DHT is as permanent and tamper-evident as the laws of mathematics allow. Clinical trials. Economic forecasts. Environmental assessments. Policy research. Anywhere a verdict can be influenced by seeing other verdicts first, ValiChord provides a layer of structural independence that didn't previously exist at scale.</p>
    </div>
  </details>

  <details>
    <summary>Why Holochain — and not a blockchain?</summary>
    <div class="expand-body">
      <p>Between 2018 and 2023, dozens of decentralised science (DeSci) projects launched with the promise that blockchains would fix reproducibility. Essentially all of them failed or were quietly abandoned. The reasons were structural. Patient clinical data cannot be written to an un-erasable public ledger under GDPR. Blockchain fees make heavy computational workloads prohibitive. And most critically: proving <em>who</em> wrote data and <em>when</em> says nothing about whether the data is <em>reproducible</em>. The blockchain proved the ledger was immutable, not the science.</p>
      <p>ValiChord is built on <strong>Holochain</strong> — architecturally different from the ground up. Holochain is <strong>agent-centric</strong>: every participant maintains their own cryptographically signed source chain, and shared state lives in a DHT where each node holds and validates only a slice of the whole. There is no global ledger. No miners. No tokens. No gas fees. Sensitive data stays locked in private conductor cells; only un-invertible commitment hashes cross the public network. <strong>The network scales with its users</strong> — the more participants, the more resilient it becomes — rather than being bottlenecked by them.</p>
      <p>The Oracle DHT nodes you see during a run are live Holochain conductors. The HarmonyRecord they produce carries the same cryptographic guarantees as a blockchain record — tamper-evident, content-addressed, independently fetchable from any node — without the cost, latency, energy, or data-privacy penalties.</p>
    </div>
  </details>

  <details>
    <summary>Why not just use a central server?</summary>
    <div class="expand-body">
      <p>A central server is a single point of trust — and therefore a single point of vulnerability. It owns the timestamps, the commitment records, and the reveal log. It can be compromised, taken offline, or subject to legal or institutional pressures that have nothing to do with the science it's meant to protect. Even with the best intentions, no central system can offer independent proof of its own integrity.</p>
      <p>ValiChord stores commitments across a distributed network of independent nodes. The hash you receive after a run is <strong>independently fetchable from any node</strong> — it doesn't route through this website at all. You can verify it yourself with a single <code style="color:#a0c8ff;font-size:.85em">curl</code> command, from your own machine, right now. No login, no account, no trust in us required.</p>
      <p>That's the trust layer a centralised system structurally cannot offer: <strong>the ability to verify without asking permission</strong>. The record's integrity doesn't depend on trusting any single organisation.</p>
    </div>
  </details>

  <details>
    <summary>What if the validators disagree?</summary>
    <div class="expand-body">
      <p>That <em>is</em> the result. ValiChord doesn't determine who is <strong>right</strong> — it determines whether the process was <strong>independent</strong>.</p>
      <p>For roughly 350 years, the historical solution to verifying claims has been institutional: double-blind panels, expert auditors, centralised peer review. These systems share a well-known structural limitation — a tendency toward what might be called <em>coordinated legitimacy</em>. Reviewers naturally bring awareness of each other's reputations and institutional contexts. Panels that deliberate together tend to reach consensus — usually a strength, but one that can smooth over genuine disagreement. Systems that aggregate opinions often reduce them to a pass/fail metric, erasing the precise texture of where and why a dispute arose.</p>
      <p>ValiChord makes that smoothing impossible. When validators disagree, the HarmonyRecord archives the disagreement in full — the exact verdicts, confidence levels, and reasoning of each independent party — permanently and without the possibility of retrospective adjustment. A "Divergent" or "PartiallyReproduced" result is not a failure. It is the most accurate answer science can give when the evidence is genuinely mixed. <strong>Independent disagreement, preserved in full, is more scientifically valuable than consensus shaped by who was in the room.</strong></p>
    </div>
  </details>

</div>

<!-- ── Free demo — secondary ──────────────────────────────────────────────── -->
<div class="section-divider">Free demo — no API key needed</div>

<div class="card" id="section-free">
  <h2>Study: Temperature–Species Richness</h2>
  <p>A pre-loaded synthetic ecology study. Linear regression across 20 sampling sites — the researcher claims slope ≈ 2.4086, R² ≈ 0.9991. Three AI validators independently reproduce the computation and commit their verdicts blind before anyone reveals. Runs on the server's key at no cost to you.</p>
  <p class="rate-note">Free · once per visitor per day · uses the server's Anthropic key (~$0.10/run)</p>
  <button class="btn btn-muted" id="runBtn" onclick="startDemo()">Run Protocol (~2 min)</button>
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

</main>
<script>
// ── Free demo ─────────────────────────────────────────────────────────────────
let poll=null,pollStart=null;
const MAX_POLL_MS=8*60*1000;
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
    pollStart=Date.now();poll=setInterval(()=>doPoll(d.job_id),2000);
  }).catch(e=>{showErr('resultArea','Network error: '+e.message);btn.disabled=false;});
}
function doPoll(id){
  if(pollStart&&Date.now()-pollStart>MAX_POLL_MS){
    clearInterval(poll);
    showErr('resultArea','Demo timed out after 8 minutes. The run may still be processing — refresh to check.');
    document.getElementById('runBtn').disabled=false;
    return;
  }
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
let customPoll=null,customJobId=null,customPollStart=null;
function checkCustomReady(){
  const ok=document.getElementById('customClaim').value.trim()
         &&document.getElementById('customAnswer').value.trim()
         &&document.getElementById('customKey').value.trim().startsWith('sk-ant-');
  document.getElementById('customSubmitBtn').disabled=!ok;
}
function startCustomDemo(){
  const claim=document.getElementById('customClaim').value.trim();
  const answer=document.getElementById('customAnswer').value.trim();
  const key=document.getElementById('customKey').value.trim();
  document.getElementById('customSubmitBtn').disabled=true;
  document.getElementById('customBusyMsg').style.display='none';
  document.getElementById('customInputCard').style.opacity='.5';
  const pc=document.getElementById('customProgressCard');
  pc.style.display='block';
  document.getElementById('customResultArea').innerHTML='';
  setCustomDots(0);
  document.getElementById('revealPrompt').style.display='none';
  const rb=document.getElementById('revealBtn');
  rb.disabled=true;rb.classList.remove('btn-ready');rb.textContent='Reveal my answer';
  fetch('/demo/custom/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({claim,user_answer:answer,user_api_key:key})})
    .then(r=>r.json()).then(d=>{
      if(d.status==='busy'){
        document.getElementById('customBusyMsg').textContent=d.message;
        document.getElementById('customBusyMsg').style.display='block';
        document.getElementById('customSubmitBtn').disabled=false;
        document.getElementById('customInputCard').style.opacity='1';
        pc.style.display='none';return;
      }
      if(d.error||!d.job_id){
        showErr('customResultArea',d.error||'Failed to start: '+JSON.stringify(d));
        document.getElementById('customSubmitBtn').disabled=false;
        document.getElementById('customInputCard').style.opacity='1';return;
      }
      customJobId=d.job_id;
      customPollStart=Date.now();customPoll=setInterval(()=>pollCustom(d.job_id),2000);
    }).catch(e=>{
      showErr('customResultArea','Network error: '+e.message);
      document.getElementById('customSubmitBtn').disabled=false;
      document.getElementById('customInputCard').style.opacity='1';
    });
}
function pollCustom(id){
  if(customPollStart&&Date.now()-customPollStart>MAX_POLL_MS){
    clearInterval(customPoll);
    showErr('customResultArea','Demo timed out after 8 minutes. The run may still be processing — refresh to check.');
    document.getElementById('customSubmitBtn').disabled=false;
    document.getElementById('customInputCard').style.opacity='1';
    return;
  }
  fetch('/demo/custom/result/'+id).then(r=>r.json()).then(j=>{
    setCustomDots(j.validators_committed||0);
    if(j.phase==='awaiting_reveal'){clearInterval(customPoll);enableRevealBtn();}
    else if(j.phase==='revealing'){}
    else if(j.status==='done'){
      clearInterval(customPoll);showCustomResult(j.result);
      document.getElementById('customInputCard').style.opacity='1';
      document.getElementById('customSubmitBtn').disabled=false;
    } else if(j.status==='error'){
      clearInterval(customPoll);showErr('customResultArea',j.error||'Unknown error');
      document.getElementById('customInputCard').style.opacity='1';
      document.getElementById('customSubmitBtn').disabled=false;
    }
  }).catch(e=>console.error('custom poll:',e));
}
function setCustomDots(count){
  const labels=['Validator 1','Validator 2','Validator 3'];
  for(let i=1;i<=3;i++){
    const dot=document.getElementById('cv'+i),row=document.getElementById('v'+i+'row'),lbl=document.getElementById('v'+i+'label');
    if(i<=count){dot.className='vdot done';row.className='commit-row done';lbl.textContent=labels[i-1]+' committed ✓';}
    else if(i===count+1){dot.className='vdot active';row.className='commit-row';lbl.textContent=labels[i-1]+' researching…';}
    else{dot.className='vdot';row.className='commit-row';lbl.textContent=labels[i-1]+' waiting…';}
  }
}
function enableRevealBtn(){
  setCustomDots(3);
  document.getElementById('revealPrompt').style.display='block';
  const btn=document.getElementById('revealBtn');
  btn.disabled=false;btn.classList.add('btn-ready');
}
function triggerReveal(){
  const btn=document.getElementById('revealBtn');
  btn.disabled=true;btn.classList.remove('btn-ready');btn.textContent='Revealing…';
  document.getElementById('revealPrompt').style.display='none';
  fetch('/demo/custom/reveal/'+customJobId,{method:'POST'})
    .then(r=>r.json()).then(d=>{
      if(d.error){showErr('customResultArea',d.error);return;}
      customPollStart=Date.now();customPoll=setInterval(()=>pollCustom(customJobId),2000);
    }).catch(e=>showErr('customResultArea','Network error: '+e.message));
}

// ── Results ───────────────────────────────────────────────────────────────────
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
const OUTCOME_LABEL={'Reproduced':'Aligned with validators','PartiallyReproduced':'Partially aligned','NotReproduced':'Diverged from validators','FailedToReproduce':'Failed to reproduce','UnableToAssess':'Unable to assess'};
function showFreeResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>`<div class="vrow">Validator ${esc(v.validator)}: ${esc(v.outcome)} (${esc(v.confidence)}) — ${esc(v.reasoning)}</div>`).join('');
  const shareUrl=esc(r.record_url||''),curlCmd=r.record_url?'curl '+JSON.stringify(r.record_url):'',hashB64=encodeURIComponent(r.external_hash_b64||'');
  document.getElementById('resultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${esc(r.outcome)} — ${esc(r.agreement_level)}</div>
    <div class="detail">${esc(r.validator_count)}/3 validators · Temperature–Species Richness</div>
    <div class="verdicts">${rows}</div>
    ${shareUrl?`<div class="share">Permanent record: <a href="${shareUrl}" target="_blank">${shareUrl}</a></div>`:''}
    <div class="verify-section">
      <p><strong>Is this real?</strong> The hash lives on the Oracle DHT — not generated by this page. Fetch it yourself from any node:</p>
      ${curlCmd?`<div class="curl-cmd">${esc(curlCmd)}</div>`:''}
      ${hashB64?`<button class="btn-ghost" onclick="fetchRaw('resultArea','${hashB64}')">Fetch raw record from Oracle →</button>`:''}
      <pre class="raw-json" id="rawJson"></pre>
    </div></div>`;
}
function showCustomResult(r){
  const rows=(r.validator_verdicts||[]).map(v=>`<div class="vrow">Validator ${esc(v.validator)}: ${esc(v.outcome)} (${esc(v.confidence)}) — ${esc(v.reasoning)}</div>`).join('');
  const shareUrl=esc(r.record_url||''),curlCmd=r.record_url?'curl '+JSON.stringify(r.record_url):'',hashB64=encodeURIComponent(r.external_hash_b64||'');
  const outcomeLabel=OUTCOME_LABEL[r.outcome]||esc(r.outcome);
  document.getElementById('customResultArea').innerHTML=`<div class="result-box">
    <div class="outcome">${outcomeLabel} — ${esc(r.agreement_level)}</div>
    <div class="detail">${esc(r.validator_count)}/3 validators · your hypothesis</div>
    ${r.comparison_summary?`<div class="comparison-summary">${esc(r.comparison_summary)}</div>`:''}
    <div class="researcher-reveal"><strong>Your sealed answer (revealed now)</strong>${esc(r.researcher_answer||'')}</div>
    <div class="verdicts">${rows}</div>
    ${shareUrl?`<div class="share">Permanent record: <a href="${shareUrl}" target="_blank">${shareUrl}</a></div>`:''}
    <div class="verify-section">
      <p><strong>Is this real?</strong> Your answer hash was committed to the Oracle DHT before the validators started. Independently fetchable from any node:</p>
      ${curlCmd?`<div class="curl-cmd">${esc(curlCmd)}</div>`:''}
      ${hashB64?`<button class="btn-ghost" onclick="fetchRaw('customResultArea','${hashB64}')">Fetch raw record from Oracle →</button>`:''}
      <pre class="raw-json" id="customRawJson"></pre>
    </div></div>`;
}
function fetchRaw(areaId,hashB64){
  const jsonId=areaId==='resultArea'?'rawJson':'customRawJson',pre=document.getElementById(jsonId);
  pre.style.display='block';pre.textContent='Fetching…';
  fetch('/demo/record/'+hashB64).then(r=>r.json()).then(d=>{pre.textContent=JSON.stringify(d,null,2);}).catch(e=>{pre.textContent='Error: '+e.message;});
}
function showErr(areaId,msg){
  const d=document.createElement('div');d.className='err';d.textContent=msg;
  document.getElementById(areaId).replaceChildren(d);
}
</script>
</body>
</html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
