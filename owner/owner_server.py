"""
MediVision — Owner Registry & Live Fleet Dashboard
==================================================
A small, self-contained service the FOUNDER runs (on a cheap VPS).

It does NOT touch any shop's billing data. Each shop's app sends a tiny
"heartbeat" (online + today's sales summary) and checks its license here.
You watch all shops live, track monthly fees, and suspend/activate access.

Run:   python owner_server.py        (listens on :5002)
Env:   OWNER_PASSWORD   dashboard login password (default: medivision)
       OWNER_DB_PATH    registry db path (default: owner_registry.db)
       PORT             port (default: 5002)
"""
import os
import sqlite3
import functools
from datetime import datetime, timezone, timedelta

from flask import (Flask, request, jsonify, session, redirect,
                   render_template_string, Response)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("OWNER_DB_PATH", os.path.join(BASE_DIR, "owner_registry.db"))
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "medivision")
ONLINE_WINDOW_SEC = 180          # "online now" if seen within 3 min
DEFAULT_DUE_DAY = 5              # monthly fee due on the 5th
PLAN_FEE = {"inventory": 200, "billing": 500, "smart": 700, "pro": 1000}

app = Flask(__name__)
app.secret_key = os.environ.get("OWNER_SECRET", "medivision-owner-secret-2026")


# ── DB ────────────────────────────────────────────────────────────────
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_key TEXT UNIQUE,
            name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            plan TEXT DEFAULT 'billing',
            monthly_fee REAL DEFAULT 0,
            due_day INTEGER DEFAULT 5,
            status TEXT DEFAULT 'active',          -- active | suspended
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS heartbeats (
            shop_key TEXT PRIMARY KEY,
            last_seen TEXT,
            app_version TEXT DEFAULT '',
            today_bills INTEGER DEFAULT 0,
            today_sales REAL DEFAULT 0,
            stock_count INTEGER DEFAULT 0,
            alerts INTEGER DEFAULT 0,
            ip TEXT DEFAULT ''
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_key TEXT,
            amount REAL,
            period_ym TEXT,                         -- 2026-06
            paid_on TEXT,
            method TEXT DEFAULT 'cash',
            note TEXT DEFAULT ''
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS signups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, phone TEXT, plan TEXT DEFAULT 'billing',
            status TEXT DEFAULT 'pending',          -- pending | approved | rejected
            created_at TEXT
        )""")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def this_period():
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ── auth ──────────────────────────────────────────────────────────────
def owner_only(f):
    @functools.wraps(f)
    def wrap(*a, **k):
        if not session.get("owner"):
            return jsonify({"status": "error", "message": "auth required"}), 401
        return f(*a, **k)
    return wrap


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC API — used by each shop's app
#  CORS is open on these three routes only: the mobile app calls them from
#  a Capacitor webview origin (capacitor://localhost / https://localhost),
#  which the browser treats as cross-origin from the VPS. They're already
#  unauthenticated-by-design (a shop only knows its own device code), so
#  this doesn't expose anything the routes weren't already exposing.
# ══════════════════════════════════════════════════════════════════════
_PUBLIC_CORS_PATHS = ("/api/heartbeat", "/api/license", "/api/signup")


@app.after_request
def _add_cors(resp):
    if request.path in _PUBLIC_CORS_PATHS:
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/api/heartbeat", methods=["OPTIONS"])
@app.route("/api/license", methods=["OPTIONS"])
@app.route("/api/signup", methods=["OPTIONS"])
def _cors_preflight():
    return ("", 204)


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    d = request.get_json(silent=True) or {}
    key = str(d.get("shop_key", "")).strip()
    if not key:
        return jsonify({"status": "error", "message": "shop_key required"}), 400
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    with conn() as c:
        row = c.execute("SELECT * FROM shops WHERE shop_key=?", (key,)).fetchone()
        if not row:
            plan = d.get("plan", "billing")
            c.execute("""INSERT INTO shops (shop_key, name, phone, plan, monthly_fee, due_day, status, created_at)
                         VALUES (?,?,?,?,?,?, 'active', ?)""",
                      (key, d.get("name", key), d.get("phone", ""), plan,
                       PLAN_FEE.get(plan, 0), DEFAULT_DUE_DAY, now_iso()))
            status = "active"
        else:
            status = row["status"]
            if d.get("name") and not row["name"]:
                c.execute("UPDATE shops SET name=? WHERE shop_key=?", (d.get("name"), key))
        c.execute("""INSERT INTO heartbeats (shop_key, last_seen, app_version, today_bills, today_sales, stock_count, alerts, ip)
                     VALUES (?,?,?,?,?,?,?,?)
                     ON CONFLICT(shop_key) DO UPDATE SET
                       last_seen=excluded.last_seen, app_version=excluded.app_version,
                       today_bills=excluded.today_bills, today_sales=excluded.today_sales,
                       stock_count=excluded.stock_count, alerts=excluded.alerts, ip=excluded.ip""",
                  (key, now_iso(), d.get("app_version", ""), int(d.get("today_bills", 0) or 0),
                   float(d.get("today_sales", 0) or 0), int(d.get("stock_count", 0) or 0),
                   int(d.get("alerts", 0) or 0), ip))
    return jsonify({"status": "success", "license": status})


@app.route("/api/license")
def license_check():
    key = request.args.get("shop_key", "").strip()
    with conn() as c:
        row = c.execute("SELECT status FROM shops WHERE shop_key=?", (key,)).fetchone()
    return jsonify({"license": row["status"] if row else "active"})


@app.route("/api/signup", methods=["POST"])
def signup():
    d = request.get_json(silent=True) or {}
    if not d.get("name") and not d.get("phone"):
        return jsonify({"status": "error", "message": "name or phone required"}), 400
    with conn() as c:
        c.execute("INSERT INTO signups (name, phone, plan, status, created_at) VALUES (?,?,?, 'pending', ?)",
                  (d.get("name", ""), d.get("phone", ""), d.get("plan", "billing"), now_iso()))
    return jsonify({"status": "success"})


# ══════════════════════════════════════════════════════════════════════
#  OWNER API — used by the dashboard (auth required)
# ══════════════════════════════════════════════════════════════════════
def _shop_view(c, s):
    hb = c.execute("SELECT * FROM heartbeats WHERE shop_key=?", (s["shop_key"],)).fetchone()
    online, last_seen, today_sales, today_bills, stock, alerts, ver = False, None, 0, 0, 0, 0, ""
    if hb:
        last_seen = hb["last_seen"]
        try:
            online = (datetime.now(timezone.utc) - datetime.fromisoformat(last_seen)).total_seconds() < ONLINE_WINDOW_SEC
        except Exception:
            online = False
        today_sales, today_bills = hb["today_sales"], hb["today_bills"]
        stock, alerts, ver = hb["stock_count"], hb["alerts"], hb["app_version"]
    pm = c.execute("SELECT COALESCE(SUM(amount),0) a FROM payments WHERE shop_key=? AND period_ym=?",
                   (s["shop_key"], this_period())).fetchone()["a"]
    fee = s["monthly_fee"] or 0
    paid = pm >= fee and fee > 0
    due = (s["status"] == "active" and fee > 0 and not paid)
    overdue = due and datetime.now(timezone.utc).day > (s["due_day"] or DEFAULT_DUE_DAY)
    # at-risk: active, online recently but no bills today, or not seen in 2+ days
    stale = False
    if last_seen:
        try:
            stale = (datetime.now(timezone.utc) - datetime.fromisoformat(last_seen)).total_seconds() > 2 * 86400
        except Exception:
            stale = False
    return {
        "id": s["id"], "shop_key": s["shop_key"], "name": s["name"] or s["shop_key"],
        "phone": s["phone"], "plan": s["plan"], "monthly_fee": fee, "status": s["status"],
        "online": online, "last_seen": last_seen, "today_sales": today_sales,
        "today_bills": today_bills, "stock_count": stock, "alerts": alerts, "app_version": ver,
        "paid_this_month": paid, "amount_due": 0 if paid else fee,
        "due": due, "overdue": overdue, "at_risk": stale,
    }


@app.route("/api/owner/overview")
@owner_only
def overview():
    with conn() as c:
        shops = [_shop_view(c, s) for s in c.execute("SELECT * FROM shops").fetchall()]
        collected = c.execute("SELECT COALESCE(SUM(amount),0) a FROM payments WHERE period_ym=?",
                              (this_period(),)).fetchone()["a"]
        pending_signups = c.execute("SELECT COUNT(*) n FROM signups WHERE status='pending'").fetchone()["n"]
    mrr = sum(s["monthly_fee"] for s in shops if s["status"] == "active")
    return jsonify({
        "shops_total": len(shops),
        "online_now": sum(1 for s in shops if s["online"]),
        "mrr": mrr,
        "collected_this_month": collected,
        "due_count": sum(1 for s in shops if s["due"]),
        "overdue_count": sum(1 for s in shops if s["overdue"]),
        "at_risk": sum(1 for s in shops if s["at_risk"]),
        "today_sales_total": sum(s["today_sales"] for s in shops),
        "pending_signups": pending_signups,
        "period": this_period(),
    })


@app.route("/api/owner/shops")
@owner_only
def shops_list():
    with conn() as c:
        shops = [_shop_view(c, s) for s in c.execute("SELECT * FROM shops ORDER BY name").fetchall()]
    return jsonify(shops)


@app.route("/api/owner/shops/<int:sid>/<action>", methods=["POST"])
@owner_only
def shop_action(sid, action):
    if action not in ("suspend", "activate"):
        return jsonify({"status": "error"}), 400
    with conn() as c:
        c.execute("UPDATE shops SET status=? WHERE id=?",
                  ("suspended" if action == "suspend" else "active", sid))
    return jsonify({"status": "success"})


@app.route("/api/owner/shops/<int:sid>", methods=["PUT"])
@owner_only
def shop_update(sid):
    d = request.get_json(silent=True) or {}
    with conn() as c:
        c.execute("UPDATE shops SET name=COALESCE(?,name), phone=COALESCE(?,phone), plan=COALESCE(?,plan), monthly_fee=COALESCE(?,monthly_fee), due_day=COALESCE(?,due_day) WHERE id=?",
                  (d.get("name"), d.get("phone"), d.get("plan"), d.get("monthly_fee"), d.get("due_day"), sid))
    return jsonify({"status": "success"})


@app.route("/api/owner/shops/<int:sid>/pay", methods=["POST"])
@owner_only
def record_payment(sid):
    d = request.get_json(silent=True) or {}
    with conn() as c:
        s = c.execute("SELECT * FROM shops WHERE id=?", (sid,)).fetchone()
        if not s:
            return jsonify({"status": "error"}), 404
        amount = float(d.get("amount", s["monthly_fee"]) or 0)
        c.execute("INSERT INTO payments (shop_key, amount, period_ym, paid_on, method, note) VALUES (?,?,?,?,?,?)",
                  (s["shop_key"], amount, d.get("period", this_period()), now_iso(),
                   d.get("method", "cash"), d.get("note", "")))
    return jsonify({"status": "success"})


@app.route("/api/owner/signups")
@owner_only
def signups_list():
    with conn() as c:
        rows = c.execute("SELECT * FROM signups WHERE status='pending' ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/owner/signups/<int:gid>/<action>", methods=["POST"])
@owner_only
def signup_action(gid, action):
    if action not in ("approve", "reject"):
        return jsonify({"status": "error"}), 400
    with conn() as c:
        g = c.execute("SELECT * FROM signups WHERE id=?", (gid,)).fetchone()
        if not g:
            return jsonify({"status": "error"}), 404
        c.execute("UPDATE signups SET status=? WHERE id=?",
                  ("approved" if action == "approve" else "rejected", gid))
        if action == "approve":
            key = (g["phone"] or g["name"] or ("shop%d" % gid)).strip().replace(" ", "").lower()
            plan = g["plan"] or "billing"
            exists = c.execute("SELECT 1 FROM shops WHERE shop_key=?", (key,)).fetchone()
            if not exists:
                c.execute("""INSERT INTO shops (shop_key, name, phone, plan, monthly_fee, due_day, status, created_at)
                             VALUES (?,?,?,?,?,?, 'active', ?)""",
                          (key, g["name"] or key, g["phone"] or "", plan, PLAN_FEE.get(plan, 0),
                           DEFAULT_DUE_DAY, now_iso()))
    return jsonify({"status": "success"})


# ── auth routes ───────────────────────────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    d = request.get_json(silent=True) or {}
    if d.get("password") == OWNER_PASSWORD:
        session["owner"] = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "wrong password"}), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})


# ── dashboard page ────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "owner-registry"})


DASHBOARD_HTML = r"""<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>MediVision — Owner</title><style>
:root{--bg:#0E1117;--card:#1C2028;--card2:#222a39;--line:#2a3344;--txt:#f3f6fc;--dim:#9CA3AF;--green:#22c55e;--blue:#3B82F6;--amber:#F59E0B;--red:#ef4444}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,Segoe UI,Roboto,system-ui,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:20px}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.brand{display:flex;gap:10px;align-items:center;font-weight:800;font-size:20px}
.logo{width:34px;height:34px;border-radius:10px;background:var(--green);color:#04140b;display:grid;place-items:center;font-weight:900}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi .v{font-size:24px;font-weight:800}.kpi .l{color:var(--dim);font-size:12.5px;margin-top:3px}
.kpi.green .v{color:var(--green)}.kpi.amber .v{color:var(--amber)}.kpi.red .v{color:var(--red)}.kpi.blue .v{color:var(--blue)}
h2{font-size:15px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin:24px 0 10px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
th,td{padding:11px 12px;text-align:left;font-size:14px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.4px}
tr:last-child td{border-bottom:none}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:#444}
.dot.on{background:var(--green);box-shadow:0 0 8px var(--green)}
.pill{font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px}
.pill.due{background:rgba(245,158,11,.16);color:var(--amber)}.pill.over{background:rgba(239,68,68,.16);color:var(--red)}
.pill.paid{background:rgba(34,197,94,.16);color:var(--green)}.pill.susp{background:rgba(239,68,68,.16);color:var(--red)}
.pill.risk{background:rgba(245,158,11,.16);color:var(--amber)}
button{cursor:pointer;border:1px solid var(--line);background:var(--card2);color:var(--txt);border-radius:9px;padding:6px 11px;font-size:13px;font-weight:600}
button.g{background:var(--green);color:#04140b;border:none}button.r{background:transparent;color:var(--red);border-color:var(--red)}
button.b{background:var(--blue);color:#fff;border:none}
.login{max-width:340px;margin:12vh auto;text-align:center}
input{width:100%;padding:12px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--txt);font-size:15px;margin:10px 0}
.muted{color:var(--dim);font-size:12px}.row-actions{display:flex;gap:6px;flex-wrap:wrap}
a{color:var(--green)}
</style></head><body><div class=wrap id=app></div>
<script>
const $=s=>document.querySelector(s);
const money=n=>'₹'+(Number(n)||0).toLocaleString('en-IN',{maximumFractionDigits:0});
async function api(p,o={}){o.headers={'Content-Type':'application/json'};const r=await fetch(p,o);if(r.status===401){renderLogin();throw new Error('auth')}return r.json()}
function renderLogin(msg){document.getElementById('app').innerHTML=`<div class=login><div class=brand style="justify-content:center"><div class=logo>⚕</div>MediVision Owner</div>
<input id=pw type=password placeholder="Owner password" onkeydown="if(event.key==='Enter')doLogin()"><button class=g style="width:100%" onclick=doLogin()>Sign in</button>
<div class=muted style="margin-top:10px;color:var(--red)">${msg||''}</div></div>`}
async function doLogin(){const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#pw').value})});if(r.ok){load()}else{renderLogin('Wrong password')}}
async function load(){
 let o,shops,signups;
 try{o=await api('/api/owner/overview');}catch(e){return}
 shops=await api('/api/owner/shops');signups=await api('/api/owner/signups');
 const k=(c,v,l)=>`<div class="kpi ${c}"><div class=v>${v}</div><div class=l>${l}</div></div>`;
 let h=`<div class=top><div class=brand><div class=logo>⚕</div>MediVision — Fleet</div><div><span class=muted>${o.period} · auto-refresh 30s</span> <button onclick=logout()>Sign out</button></div></div>`;
 h+=`<div class=kpis>${k('blue',o.shops_total,'Shops')}${k('green',o.online_now,'Online now')}${k('green',money(o.mrr),'MRR')}${k('',money(o.collected_this_month),'Collected '+o.period)}${k('amber',o.due_count,'Due')}${k('red',o.overdue_count,'Overdue')}${k('amber',o.at_risk,'At risk')}${k('blue',money(o.today_sales_total),'Sales today (fleet)')}</div>`;
 if(signups.length){h+=`<h2>Pending signups (${signups.length})</h2><table><tr><th>Name</th><th>Phone</th><th>Plan</th><th></th></tr>`;
  signups.forEach(g=>{h+=`<tr><td>${g.name||'-'}</td><td>${g.phone||'-'}</td><td>${g.plan}</td><td class=row-actions><button class=g onclick="sg(${g.id},'approve')">Approve</button><button class=r onclick="sg(${g.id},'reject')">Reject</button></td></tr>`});h+=`</table>`}
 h+=`<h2>Shops</h2><table><tr><th>Shop</th><th>Status</th><th>Today</th><th>Plan / Fee</th><th>Billing</th><th>Actions</th></tr>`;
 if(!shops.length)h+=`<tr><td colspan=6 class=muted style="text-align:center;padding:30px">No shops yet — they appear here on first heartbeat.</td></tr>`;
 shops.forEach(s=>{
  const bill = s.paid_this_month?`<span class="pill paid">Paid</span>`:(s.overdue?`<span class="pill over">Overdue ${money(s.amount_due)}</span>`:(s.due?`<span class="pill due">Due ${money(s.amount_due)}</span>`:`<span class=muted>—</span>`));
  const st = s.status==='suspended'?`<span class="pill susp">Suspended</span>`:`<span class=dot${s.online?' on':''}></span>${s.online?'Online':'Offline'}`;
  const risk = s.at_risk?` <span class="pill risk">At risk</span>`:'';
  h+=`<tr><td><b>${s.name}</b><div class=muted>${s.phone||s.shop_key}${s.last_seen?' · seen '+timeago(s.last_seen):''}</div></td>
   <td>${st}${risk}</td>
   <td>${money(s.today_sales)}<div class=muted>${s.today_bills} bills · ${s.stock_count} items</div></td>
   <td>${s.plan}<div class=muted>${money(s.monthly_fee)}/mo</div></td>
   <td>${bill}</td>
   <td class=row-actions>${!s.paid_this_month&&s.monthly_fee>0?`<button class=g onclick="pay(${s.id})">Mark paid</button>`:''}
     ${s.status==='active'?`<button class=r onclick="act(${s.id},'suspend')">Suspend</button>`:`<button class=b onclick="act(${s.id},'activate')">Activate</button>`}
     ${s.phone?`<a href="https://wa.me/91${s.phone.replace(/\D/g,'').slice(-10)}?text=${encodeURIComponent('MediVision: monthly fee '+money(s.amount_due)+' is due. Please pay to keep service active. Thank you!')}" target=_blank><button>Remind</button></a>`:''}</td></tr>`});
 h+=`</table><p class=muted style="margin-top:14px">Suspending a shop blocks its app on next check. Heartbeats every ~2 min keep "online" current.</p>`;
 document.getElementById('app').innerHTML=h;
}
function timeago(iso){const s=(Date.now()-new Date(iso))/1000;if(s<120)return'just now';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
async function act(id,a){await api('/api/owner/shops/'+id+'/'+a,{method:'POST'});load()}
async function sg(id,a){await api('/api/owner/signups/'+id+'/'+a,{method:'POST'});load()}
async function pay(id){const amt=prompt('Amount received (₹):');if(amt===null)return;await api('/api/owner/shops/'+id+'/pay',{method:'POST',body:JSON.stringify({amount:parseFloat(amt)||0})});load()}
async function logout(){await fetch('/logout',{method:'POST'});renderLogin()}
load();setInterval(()=>{if(!document.querySelector('.login'))load()},30000);
</script></body></html>"""


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5002))
    print(f"[MediVision Owner] Dashboard on http://0.0.0.0:{port}  (password: {OWNER_PASSWORD})")
    app.run(host="0.0.0.0", port=port, debug=False)
