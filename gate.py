"""
MediVision AI — Website Access Gate
-----------------------------------
A password-protected entry page that fronts the entire website. Only /api/*
(mobile app) and static assets bypass it, so the phone still works normally.

Every submission (name, purpose, IP, timestamp) is appended to
/var/log/medivision-gate.log for audit.

Imported by wsgi.py after `from app import app`, so its side-effects
(before_request + /gate route) register on the same Flask app.
"""
import os
import logging
import hashlib
from datetime import datetime
from flask import request, redirect, session, render_template_string
from app import app

GATE_PASSWORD = os.environ.get("GATE_PASSWORD", "")
GATE_LOG = os.environ.get("GATE_LOG", "/var/log/medivision-gate.log")

# ──────────────────────────────────────────────────────────────
#  TEAM CREDITS
#  Replace the placeholder names / bios / photo URLs with the real
#  people. Photos: leave `photo` empty and an auto-generated initial
#  avatar is drawn client-side. Set `photo` to a full URL to use a
#  real headshot (upload to /static/team/ and reference it as
#  "/static/team/<file>.jpg").
# ──────────────────────────────────────────────────────────────
FRIENDS = [
    {
        "name": "Rishiikesh",
        "role": "Founder & Full-stack lead",
        "bio":  "Idea, product direction, backend + mobile — the whole system runs on his shoulders.",
        "photo": "",
        "link": "",
    },
    {
        "name": "<Friend Name 1>",
        "role": "Frontend / UX",
        "bio":  "Shaped the pharmacy dashboards, billing flow and the mobile app screens users see every day.",
        "photo": "",
        "link": "",
    },
    {
        "name": "<Friend Name 2>",
        "role": "Backend / Database",
        "bio":  "Wrote the API layer, the stock engine and the reporting queries that power the numbers.",
        "photo": "",
        "link": "",
    },
]

STUDENTS = [
    {
        "name": "<Student 1>",
        "role": "Testing & QA",
        "bio":  "Ran real-shop test bills, caught the edge cases before customers did.",
        "photo": "",
    },
    {
        "name": "<Student 2>",
        "role": "Content & copy",
        "bio":  "Wrote the help text, the WhatsApp templates and the onboarding scripts.",
        "photo": "",
    },
]

THANKS_TO = [
    "Selvam Medicals — for being the first shop willing to run this in production.",
    "Dr. friends in the pharma network who reviewed the drug register + narcotic workflow.",
    "Everyone who quietly tested and reported bugs without asking for credit.",
]

_EXEMPT_PATHS = (
    "/gate", "/static/", "/api/", "/license",
    "/sw.js", "/manifest.json", "/offline",
)


def _is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in _EXEMPT_PATHS)


def _safe_next(url: str) -> str:
    if not url or not url.startswith("/") or url.startswith("//"):
        return "/"
    return url


@app.before_request
def _access_gate():
    if not GATE_PASSWORD:
        return None
    if session.get("gate_ok"):
        return None
    path = request.path or "/"
    if _is_exempt(path):
        return None
    return redirect("/gate?next=" + path)


@app.route("/gate", methods=["GET", "POST"])
def _gate_page():
    error = ""
    next_url = _safe_next(request.args.get("next") or request.form.get("next") or "/")

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        purpose = (request.form.get("purpose") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not name or not purpose:
            error = "Name and purpose of visit are required."
        elif not GATE_PASSWORD:
            error = "Gate is not configured. Contact the administrator."
        elif password != GATE_PASSWORD:
            error = "Wrong password."
        else:
            session["gate_ok"] = True
            session.permanent = False
            try:
                ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
                ua = (request.headers.get("User-Agent") or "").replace("\t", " ")[:200]
                with open(GATE_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()}\t{ip}\t{name}\t{purpose}\t{ua}\n")
            except Exception as e:
                logging.warning("gate log write failed: %s", e)
            return redirect(next_url)

    # Derive a stable pastel colour + initials for every team member so
    # cards without a real headshot still look designed, not empty.
    def _decorate(person: dict) -> dict:
        p = dict(person)
        name = p.get("name", "?")
        # 2 letters max, skipping angle-brackets from placeholder names
        clean = name.replace("<", "").replace(">", "").strip()
        parts = [w for w in clean.split() if w]
        if len(parts) >= 2:
            initials = (parts[0][0] + parts[1][0]).upper()
        elif parts:
            initials = parts[0][:2].upper()
        else:
            initials = "??"
        # deterministic hue from name hash → same person always gets same colour
        h = int(hashlib.sha1(name.encode()).hexdigest(), 16) % 360
        p["initials"] = initials
        p["hue"] = h
        return p

    return render_template_string(
        _GATE_HTML,
        error=error,
        next_url=next_url,
        friends=[_decorate(f) for f in FRIENDS],
        students=[_decorate(s) for s in STUDENTS],
        thanks=THANKS_TO,
    )


_GATE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MediVision AI — Restricted Access</title>
<style>
  :root{--bg:#0E1117;--card:#161b25;--card-2:#1f2532;--line:#2a3344;--txt:#f3f6fc;
        --dim:#9CA3AF;--mut:#6b7488;--green:#22c55e;--green-d:#16a34a;
        --red:#ef4444;--yellow:#facc15;--blue:#3B82F6}
  *{box-sizing:border-box}
  html,body{margin:0;min-height:100%}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,system-ui,sans-serif;
    background:radial-gradient(1200px 600px at 50% -10%,#132420 0%,#0E1117 60%);
    color:var(--txt);
    display:flex;align-items:flex-start;justify-content:center;
    padding:36px 16px 60px;line-height:1.5;
  }
  .wrap{max-width:640px;width:100%}
  .brand{text-align:center;margin-bottom:24px}
  .logo{width:70px;height:70px;border-radius:18px;
        background:linear-gradient(135deg,var(--green),#0ea96b);
        display:inline-grid;place-items:center;color:#04140b;font-weight:900;font-size:40px;
        box-shadow:0 10px 28px rgba(34,197,94,.4);margin-bottom:14px}
  .brand h1{margin:0;font-size:28px;font-weight:800;letter-spacing:-.4px}
  .brand h1 .ai{color:var(--green)}
  .brand .tag{color:var(--dim);font-size:13.5px;margin-top:6px}

  .card{background:var(--card);border:1px solid var(--line);border-radius:18px;
        padding:24px;box-shadow:0 14px 40px rgba(0,0,0,.35);margin-bottom:16px}
  .lead{display:flex;align-items:center;gap:8px;color:var(--dim);
        font-size:12.5px;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
  .lead .dot{width:8px;height:8px;border-radius:50%;background:var(--yellow);box-shadow:0 0 6px var(--yellow)}

  .field{margin-bottom:12px}
  .field label{display:block;font-size:13px;color:var(--dim);margin-bottom:6px}
  .field input,.field select{
    width:100%;padding:12px 14px;border:1px solid var(--line);background:#141925;
    color:var(--txt);border-radius:10px;font-size:15px;-webkit-appearance:none}
  .field input:focus,.field select:focus{outline:none;border-color:var(--green)}
  .btn{width:100%;padding:13px;background:var(--green);color:#04140b;border:none;
       border-radius:12px;font-weight:800;font-size:15px;cursor:pointer;margin-top:4px}
  .btn:hover{background:var(--green-d)}
  .err{color:var(--red);font-size:13px;margin-bottom:10px;min-height:1em}

  .section-title{display:flex;align-items:center;justify-content:space-between;
                 margin:0 0 14px;color:var(--txt);font-size:15px;font-weight:700}
  .section-title .sub{color:var(--dim);font-size:12px;font-weight:400}

  .team{display:grid;grid-template-columns:1fr;gap:12px}
  @media (min-width:520px){.team{grid-template-columns:1fr 1fr}}
  .member{display:flex;gap:12px;padding:12px;background:var(--card-2);
          border:1px solid var(--line);border-radius:12px}
  .avatar{width:52px;height:52px;flex:0 0 52px;border-radius:14px;
          display:grid;place-items:center;font-weight:800;color:#fff;font-size:18px;
          box-shadow:0 4px 12px rgba(0,0,0,.25)}
  .avatar.hasimg{overflow:hidden;padding:0}
  .avatar.hasimg img{width:100%;height:100%;object-fit:cover;display:block}
  .m-body{flex:1;min-width:0}
  .m-name{font-weight:700;color:var(--txt);font-size:14.5px;margin:0 0 2px}
  .m-role{color:var(--green);font-size:12px;font-weight:600;margin-bottom:4px}
  .m-bio{color:var(--dim);font-size:12.5px;line-height:1.4}

  .thanks{padding:16px;background:var(--card-2);border:1px dashed var(--line);
          border-radius:12px}
  .thanks h3{margin:0 0 8px;font-size:13px;color:var(--green);text-transform:uppercase;letter-spacing:.6px}
  .thanks ul{margin:0;padding-left:20px;color:var(--dim);font-size:13px}
  .thanks li{margin:4px 0}

  .foot{text-align:center;color:var(--mut);font-size:12px;margin-top:10px}
  .foot .divider{margin:0 8px;color:#3a4457}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <div class="logo">+</div>
    <h1>MediVision <span class="ai">AI</span></h1>
    <div class="tag">India's #1 AI Pharmacy Platform</div>
  </div>

  <div class="card">
    <div class="lead"><span class="dot"></span> Restricted access &middot; authorised users only</div>

    <form method="POST" autocomplete="on">
      <input type="hidden" name="next" value="{{ next_url }}">
      <div class="err">{{ error }}</div>

      <div class="field">
        <label>Your name</label>
        <input name="name" required autocomplete="name" placeholder="e.g. Rishiikesh">
      </div>

      <div class="field">
        <label>Purpose of visit</label>
        <select name="purpose" required>
          <option value="">Select purpose…</option>
          <option>Owner / Admin access</option>
          <option>Demo</option>
          <option>Testing</option>
          <option>Support</option>
          <option>Investor / Partner</option>
          <option>Journalist / Media</option>
          <option>Other</option>
        </select>
      </div>

      <div class="field">
        <label>Access password</label>
        <input name="password" type="password" required autocomplete="current-password"
               placeholder="Ask the owner if you don't have this">
      </div>

      <button type="submit" class="btn">Enter</button>
    </form>
  </div>

  {% if friends %}
  <div class="card">
    <div class="section-title">
      Built by <span class="sub">the people behind MediVision AI</span>
    </div>
    <div class="team">
    {% for f in friends %}
      <div class="member">
        {% if f.photo %}
          <div class="avatar hasimg"><img src="{{ f.photo }}" alt="{{ f.name }}"></div>
        {% else %}
          <div class="avatar" style="background:hsl({{ f.hue }},55%,45%)">{{ f.initials }}</div>
        {% endif %}
        <div class="m-body">
          <div class="m-name">{{ f.name }}</div>
          <div class="m-role">{{ f.role }}</div>
          <div class="m-bio">{{ f.bio }}</div>
        </div>
      </div>
    {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if students %}
  <div class="card">
    <div class="section-title">
      With help from <span class="sub">student contributors</span>
    </div>
    <div class="team">
    {% for s in students %}
      <div class="member">
        {% if s.photo %}
          <div class="avatar hasimg"><img src="{{ s.photo }}" alt="{{ s.name }}"></div>
        {% else %}
          <div class="avatar" style="background:hsl({{ s.hue }},55%,45%)">{{ s.initials }}</div>
        {% endif %}
        <div class="m-body">
          <div class="m-name">{{ s.name }}</div>
          <div class="m-role">{{ s.role }}</div>
          <div class="m-bio">{{ s.bio }}</div>
        </div>
      </div>
    {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if thanks %}
  <div class="card">
    <div class="thanks">
      <h3>Thank you</h3>
      <ul>
        {% for t in thanks %}<li>{{ t }}</li>{% endfor %}
      </ul>
    </div>
  </div>
  {% endif %}

  <div class="foot">
    MediVision AI &copy; 2026
    <span class="divider">&middot;</span>
    Every entry is logged with your name, purpose, and IP.
  </div>
</div>
</body>
</html>"""
