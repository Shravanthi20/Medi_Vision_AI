/* ===================================================================
   MediVision Mobile — app engine (Phase 0)
   Vanilla JS SPA. Wraps the existing Flask backend.
   Priority: simple, fast, big touch targets, calm UX.
   =================================================================== */
(() => {
  "use strict";

  const Cap = window.Capacitor || null;
  const P = (Cap && Cap.Plugins) || {};
  const cfg = window.MV_CONFIG;

  // ---------- tiny helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const app = $("#app");
  const navEl = $("#nav");
  navEl.addEventListener("click", e => { const b = e.target.closest("[data-tab]"); if (b) go(b.dataset.tab); });
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const money = (n) => "₹" + (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

  // ---------- persistent store (Preferences plugin or localStorage) ----------
  const store = {
    async get(k) {
      try { if (P.Preferences) return (await P.Preferences.get({ key: k })).value; } catch (e) {}
      return localStorage.getItem(k);
    },
    async set(k, v) {
      try { if (P.Preferences) return void (await P.Preferences.set({ key: k, value: v })); } catch (e) {}
      localStorage.setItem(k, v);
    },
    async del(k) {
      try { if (P.Preferences) return void (await P.Preferences.remove({ key: k })); } catch (e) {}
      localStorage.removeItem(k);
    }
  };

  // ---------- haptics ----------
  const buzz = (style = "Light") => { try { P.Haptics && P.Haptics.impact({ style }); } catch (e) {} };

  // ---------- state ----------
  const S = {
    apiBase: cfg.API_BASE,
    me: null,            // { name, type }
    planKey: "max",       // subscription is now enforced server-side (owner VPS), not per-feature — always full feature set
    medicines: [],
    recent: [],          // freshly onboarded this session
    cart: [],
    cust: { name: "", phone: "" },
    pay: "cash",
    disc: 0,
    held: [],
    customers: [],
    enquiries: [],
    loc: {},            // medicine id -> rack location
    upiQr: "",          // base64 UPI QR image
    cashOpen: { date: "", amount: 0 },
    role: "Manager",
    staffName: "Owner",
    staff: [],           // cached staff list for billing chip strip
    tab: "home",
    kpis: null,
    theme: "dark",
    setup: {},
  };
  const plan = () => cfg.PLANS[S.planKey] || cfg.PLANS.billing;
  const can = (feat) => plan().features.includes(feat);
  const roleCan = (sec) => window.MVROLES ? window.MVROLES.can(S.role, sec) : true;
  function roleBlock(name) {
    navEl.classList.remove("hide");
    app.innerHTML = `<div class="lock"><div class="e">🔒</div><h2>${esc(name)} is restricted</h2><p>Your role (${esc(S.role)}) can't open this. Ask the owner.</p><button class="btn primary" onclick="MV.go('home')">Back</button></div>`;
  }

  // ---------- theme ----------
  function applyTheme() {
    document.body.classList.toggle("theme-light", S.theme === "light");
    const m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", S.theme === "light" ? "#f4f6fb" : "#0E1117");
  }
  async function toggleTheme() {
    S.theme = S.theme === "light" ? "dark" : "light";
    applyTheme(); await store.set("mv_theme", S.theme); buzz();
  }

  // ---------- toast ----------
  let toastT;
  function toast(msg, kind = "") {
    const t = $("#toast");
    t.className = ""; t.textContent = msg;
    requestAnimationFrame(() => t.className = "show " + kind);
    clearTimeout(toastT);
    toastT = setTimeout(() => t.className = "", 2600);
  }

  // ---------- API ----------
  async function api(path, opts = {}) {
    if (cfg.STANDALONE && window.MVLOCAL) return window.MVLOCAL.localApi(path, opts);
    const url = S.apiBase.replace(/\/$/, "") + path;
    const o = Object.assign({ credentials: "include", headers: {} }, opts);
    if (o.body && typeof o.body !== "string") { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(o.body); }
    const r = await fetch(url, o);
    const txt = await r.text();
    let data; try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = txt; }
    if (!r.ok) throw Object.assign(new Error((data && data.message) || ("HTTP " + r.status)), { status: r.status, data });
    return data;
  }

  // ---------- native camera bridges ----------
  async function scanBarcode() {
    const B = P.BarcodeScanning;
    if (!B) { // dev / browser fallback
      const v = prompt("Barcode (dev fallback — real camera works in the installed app):");
      return v ? v.trim() : null;
    }
    try {
      const perm = await B.requestPermissions();
      if (perm.camera !== "granted" && perm.camera !== "limited") { toast("Camera permission needed", "err"); return null; }
      const { barcodes } = await B.scan();
      return barcodes && barcodes.length ? barcodes[0].rawValue : null;
    } catch (e) { if (!/cancel/i.test(e.message || "")) toast("Scan failed", "err"); return null; }
  }

  // OCR for medicine-name scan: capture a photo via @capacitor/camera, then run
  // Google ML Kit text recognition. Returns the raw recognized text, or null if
  // the plugins aren't present (UI then falls back to manual typing).
  async function ocrCapture() {
    const cam = P.Camera, ocr = P.CapacitorPluginMlKitTextRecognition;
    if (!cam || !ocr) return null;
    try {
      const photo = await cam.getPhoto({ quality: 65, resultType: "base64", source: "CAMERA", allowEditing: false, correctOrientation: true });
      const b64 = photo && photo.base64String;
      if (!b64) return "";
      const res = await ocr.detectText({ base64Image: b64 });
      return (res && res.text) ? res.text : "";
    } catch (e) { if (!/cancel/i.test(e.message || "")) toast("Scan failed", "err"); return ""; }
  }

  // ---------- screen router ----------
  function go(tab) {
    S.tab = tab; buzz();
    [...navEl.querySelectorAll("button")].forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
    ({ home: viewHome, stock: viewStock, scan: viewScan, bill: viewBill, reports: viewReports, ret: viewReturns, wholesale: () => (roleCan("wholesale") && window.MVWHOLE ? window.MVWHOLE.open() : roleBlock("Wholesale")), admin: () => (roleCan("admin") && window.MVADMIN ? window.MVADMIN.open() : roleBlock("Admin")), attendance: () => (roleCan("admin") && window.MVATTEND ? window.MVATTEND.open() : roleBlock("Attendance")), setup: () => (window.MVSETUP ? window.MVSETUP.open() : toast("Setup not loaded", "err")), more: viewMore }[tab] || viewHome)();
    app.scrollTop = 0;
  }

  // =================================================================
  //  LOGIN
  // =================================================================
  function viewLogin() {
    navEl.classList.add("hide");
    app.innerHTML = `
      <div class="login">
        <div class="logo">⚕</div>
        <h1>${esc(cfg.APP_NAME)}</h1>
        <p class="tag">Pharmacy billing & stock, in your pocket</p>
        <div class="field"><label>Shop username</label>
          <input id="u" class="input" autocapitalize="none" autocomplete="username" placeholder="e.g. sel"></div>
        <div class="field"><label>Password</label>
          <input id="p" class="input" type="password" autocomplete="current-password" placeholder="••••••••"></div>
        <button class="btn primary lg" id="go"><span class="ico">→</span> Sign in</button>
        <button class="btn ghost" id="srv" style="margin-top:12px;color:var(--txt-dim)">⚙️ Server settings</button>
      </div>`;
    $("#go").onclick = doLogin;
    $("#p").addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
    $("#srv").onclick = serverSheet;
  }

  async function doLogin() {
    const username = $("#u").value.trim(), password = $("#p").value.trim();
    if (!username || !password) return toast("Enter username & password", "err");
    const btn = $("#go"); btn.disabled = true; btn.innerHTML = '<span class="ico">⏳</span> Signing in…';
    try {
      const res = await api("/api/portal/login", { method: "POST", body: { username, password } });
      S.me = { name: res.name, type: res.type };
      await store.set("mv_user", username);
      buzz("Medium"); toast("Welcome, " + res.name, "ok");
      await boot();
    } catch (e) {
      btn.disabled = false; btn.innerHTML = '<span class="ico">→</span> Sign in';
      toast(e.status === 401 ? "Wrong username or password" : "Can't reach server — check Server settings", "err");
    }
  }

  function serverSheet() {
    openSheet(`
      <h3>Server settings</h3>
      <p class="hint">Address of your MediVision backend.</p>
      <div class="field"><label>Backend URL</label>
        <input id="sv" class="input" value="${esc(S.apiBase)}" autocapitalize="none" placeholder="https://your-server"></div>
      <button class="btn primary" id="svok">Save</button>`,
      () => { $("#svok").onclick = async () => { S.apiBase = $("#sv").value.trim() || cfg.API_BASE; await store.set("mv_api", S.apiBase); closeSheet(); toast("Saved", "ok"); }; });
  }

  // =================================================================
  //  HOME
  // =================================================================
  async function viewHome() {
    navEl.classList.remove("hide");
    const shopN = (S.setup && S.setup.shopName) ? S.setup.shopName : (S.me ? S.me.name : "Shop");
    app.innerHTML = `
      <div class="topbar">
        <div class="brandmark"><div class="logo">⚕</div>
          <div><h1>${esc(shopN)}</h1><div class="sub">${esc(S.staffName || "")} · ${esc(S.role)}</div></div>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <button id="theme" class="btn" style="width:42px;height:42px;min-height:42px;padding:0;font-size:18px">${S.theme === "light" ? "🌙" : "☀️"}</button>
          <span class="plan-badge">${esc(plan().label)}</span>
        </div>
      </div>
      <div class="kpis" id="kpis">${kpiSkeleton()}</div>
      <div class="quick">
        <button class="btn primary" onclick="MV.go('scan')"><span class="ico">📷</span>Scan stock in</button>
        <button class="btn blue" id="qbill"><span class="ico">🧾</span>New bill</button>
      </div>
      <div class="sectitle">Shortcuts</div>
      ${roleCan("reports") ? '<button class="btn" onclick="MV.go(\'reports\')" style="justify-content:flex-start;gap:12px"><span class="ico">📊</span>Reports &amp; insights</button><div style="height:10px"></div>' : ''}
      <button class="btn" onclick="MV.go('stock')" style="justify-content:flex-start;gap:12px"><span class="ico">📦</span>View &amp; search stock</button>
      <div style="height:10px"></div>
      <button class="btn" onclick="MV.go('more')" style="justify-content:flex-start;gap:12px"><span class="ico">⚙️</span>Settings &amp; plan</button>`;
    $("#qbill").onclick = () => go("bill");
    $("#theme").onclick = async () => { await toggleTheme(); viewHome(); };
    loadKpis();
  }
  const kpiSkeleton = () => ["", "", "", ""].map(() => `<div class="kpi"><div class="v">—</div><div class="l">loading…</div></div>`).join("");

  // Skeleton rows for stock / list loading states
  const SKEL_W = [[65,38],[78,42],[55,35],[70,40],[60,44],[75,37]];
  function skelRows(n = 5) {
    return Array.from({length: n}, (_, i) => {
      const [w1, w2] = SKEL_W[i % SKEL_W.length];
      return `<div class="skel-row">
        <div class="meta">
          <div class="skel" style="height:16px;width:${w1}%;margin-bottom:9px"></div>
          <div class="skel" style="height:11px;width:${w2}%;margin-bottom:8px"></div>
          <div style="display:flex;gap:7px">
            <div class="skel" style="height:22px;width:58px;border-radius:999px"></div>
            <div class="skel" style="height:22px;width:46px;border-radius:999px"></div>
          </div>
        </div>
        <div class="rt"><div class="skel" style="height:18px;width:50px"></div></div>
      </div>`;
    }).join('');
  }

  async function loadKpis() {
    try {
      const k = await api("/api/kpis").catch(() => null);
      const meds = S.medicines.length ? S.medicines : await loadMeds();
      const low = meds.filter(m => Number(m.s) <= Number(m.reorder || 0) && Number(m.reorder || 0) > 0).length;
      const exp = meds.filter(m => isExpiringSoon(m.expiry)).length;
      const sales = (k && (k.today_sales ?? k.sales_today ?? k.todaySales)) || 0;
      const el = $("#kpis"); if (!el) return;
      el.innerHTML = `
        ${kpi("green", money(sales), "Today's sales")}
        ${kpi("blue", meds.length, "Total items")}
        ${kpi("red", low, "Low stock")}
        ${kpi("amber", exp, "Expiring ≤90d")}`;
    } catch (e) { const el = $("#kpis"); if (el) el.innerHTML = kpi("", "—", "Could not load KPIs"); }
  }
  const kpi = (c, v, l) => `<div class="kpi ${c}"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`;

  // =================================================================
  //  STOCK
  // =================================================================
  let stockSort = "name";
  const marginPct = m => { const p = Number(m.p) || 0, pr = Number(m.p_rate) || 0; return (p > 0 && pr > 0) ? Math.round((p - pr) / p * 100) : null; };
  function expKey(e) { const m = String(e || "").match(/(\d{1,2})[\/\-](\d{2,4})/); if (!m) return 9e15; let mo = +m[1], yr = +m[2]; if (yr < 100) yr += 2000; return new Date(yr, mo, 0).getTime(); }
  function sortMeds(list) {
    const a = list.slice();
    if (stockSort === "margin") a.sort((x, y) => (marginPct(y) ?? -1) - (marginPct(x) ?? -1));
    else if (stockSort === "stock") a.sort((x, y) => (Number(x.s) || 0) - (Number(y.s) || 0));
    else if (stockSort === "expiry") a.sort((x, y) => expKey(x.expiry) - expKey(y.expiry));
    else a.sort((x, y) => (x.n || "").localeCompare(y.n || ""));
    return a;
  }
  async function viewStock() {
    navEl.classList.remove("hide");
    app.innerHTML = `
      <div class="topbar"><h1>Stock</h1>
        <button class="btn" style="width:auto;padding:0 16px;min-height:42px" onclick="MV.go('scan')">＋ Add</button></div>
      <div class="search"><span class="si">🔍</span><input id="q" class="input" placeholder="Search medicine or generic…" autocapitalize="none"></div>
      <div class="seg" id="ssort">${[["name", "A–Z"], ["margin", "Margin"], ["stock", "Low stock"], ["expiry", "Expiry"]].map(([k, l]) => `<button data-s="${k}" class="${stockSort === k ? "on" : ""}">${l}</button>`).join("")}</div>
      <div id="list">${skelRows(6)}</div>`;
    if (!S.medicines.length) await loadMeds();
    stockRefresh();
    $("#q").addEventListener("input", stockRefresh);
    app.querySelectorAll("#ssort button").forEach(b => b.onclick = () => { stockSort = b.dataset.s; app.querySelectorAll("#ssort button").forEach(x => x.classList.toggle("on", x.dataset.s === stockSort)); stockRefresh(); });
  }
  function stockRefresh() {
    const inp = $("#q"); const raw = inp ? inp.value.trim() : ""; const q = raw.toLowerCase();
    const filtered = !q ? S.medicines : S.medicines.filter(m => (m.n || "").toLowerCase().includes(q) || (m.g || "").toLowerCase().includes(q));
    if (q && !filtered.length) {
      $("#list").innerHTML = emptyBox("🔍", "Not in stock", "Log it as a customer enquiry.") + `<button class="btn primary" id="enqbtn">＋ Log "${esc(raw)}" as enquiry</button>`;
      const eb = $("#enqbtn"); if (eb) eb.onclick = () => { addEnquiry(raw); if (inp) inp.value = ""; stockRefresh(); };
      return;
    }
    renderStock(sortMeds(filtered));
  }
  function renderStock(meds) {
    const el = $("#list"); if (!el) return;
    if (!meds.length) { el.innerHTML = emptyBox("📦", "No medicines yet", "Tap “Add” to scan your first product."); return; }
    el.innerHTML = meds.slice(0, 300).map(m => {
      const low = Number(m.s) <= Number(m.reorder || 0) && Number(m.reorder || 0) > 0;
      const exp = isExpiringSoon(m.expiry);
      const loc = S.loc[m.id]; const mg = marginPct(m);
      return `<div class="row" data-mid="${esc(m.id)}">
        <div class="meta"><div class="nm">${esc(m.n)}</div>
          <div class="dt">${esc(m.g || "—")} ${m.batch ? "· " + esc(m.batch) : ""}</div>
          <div style="margin-top:6px">${low ? '<span class="pill low">Low: ' + esc(m.s) + "</span> " : '<span class="pill ok">Qty ' + esc(m.s) + "</span> "}${exp ? '<span class="pill exp">Exp ' + esc(m.expiry) + "</span> " : ""}${mg !== null ? '<span class="pill ' + (mg >= 20 ? "ok" : "low") + '">' + mg + '% margin</span> ' : ""}${loc ? '<span class="pill ok">📍 ' + esc(loc) + "</span>" : ""}</div></div>
        <div class="rt"><div class="price">${money(m.p)}</div></div></div>`;
    }).join("") + (meds.length > 300 ? `<div class="empty">Showing first 300 of ${meds.length}. Use search.</div>` : "");
    el.querySelectorAll("[data-mid]").forEach(r => r.onclick = () => { const m = S.medicines.find(x => String(x.id) === r.dataset.mid); if (m) locSheet(m); });
  }

  // =================================================================
  //  SCAN — camera onboarding (the star)
  // =================================================================
  let scanMode = "barcode";
  function viewScan() {
    navEl.classList.remove("hide");
    if (!can("scan")) return lockedView("Stock scanning", "scan");
    app.innerHTML = `
      <div class="topbar"><h1>Add stock</h1>
        <span class="plan-badge">${S.recent.length} added</span></div>
      <div class="seg">
        <button data-m="barcode" class="${scanMode === "barcode" ? "on" : ""}">📷 Barcode</button>
        <button data-m="name" class="${scanMode === "name" ? "on" : ""}">🔤 Name scan</button>
      </div>
      <div class="scan-hero">
        <div class="ring">${scanMode === "barcode" ? "🏷️" : "🔤"}</div>
        <h2>${scanMode === "barcode" ? "Scan the barcode" : "Scan the medicine name"}</h2>
        <p>${scanMode === "barcode" ? "Point at the strip’s barcode — instant match." : "Point at the printed name, then confirm the details."}</p>
        <button class="btn primary lg" id="cam"><span class="ico">📷</span> Open camera</button>
      </div>
      <button class="btn ghost" id="manual" style="color:var(--txt-dim)">✏️ Add manually instead</button>
      <div class="sectitle">Added in this session</div>
      <div id="recent"></div>`;
    navEl.querySelectorAll(".seg button");
    app.querySelectorAll(".seg button").forEach(b => b.onclick = () => { scanMode = b.dataset.m; viewScan(); });
    $("#cam").onclick = scanMode === "barcode" ? doBarcodeFlow : doNameFlow;
    $("#manual").onclick = () => confirmSheet({});
    renderRecent();
  }
  function renderRecent() {
    const el = $("#recent"); if (!el) return;
    if (!S.recent.length) { el.innerHTML = emptyBox("✨", "Nothing yet", "Scanned items appear here."); return; }
    el.innerHTML = S.recent.map(m => `<div class="row"><div class="meta"><div class="nm">${esc(m.n)}</div>
      <div class="dt">Qty ${esc(m.s)} · ${esc(m.batch || "no batch")}</div></div>
      <div class="rt"><div class="price">${money(m.p)}</div></div></div>`).join("");
  }

  async function doBarcodeFlow() {
    buzz();
    const code = await scanBarcode();
    if (!code) return;
    buzz("Medium");
    const existing = S.medicines.find(m => String(m.id) === String(code));
    confirmSheet(existing ? { ...existing } : { id: code, n: "" }, code);
  }
  async function doNameFlow() {
    buzz();
    const text = await ocrCapture();
    if (text === null) { // plugins not in this build yet
      toast("Name-scan activates after the update — type for now", "");
      return confirmSheet({});
    }
    buzz("Medium");
    const lines = String(text).split(/\n/).map(s => s.trim()).filter(s => s.length >= 3);
    if (!lines.length) return confirmSheet({});
    const matches = matchMeds(lines);
    if (matches.length) pickMatchSheet(lines, matches);
    else confirmSheet({ n: lines[0] || "" });
  }
  function matchMeds(lines) {
    const meds = S.medicines, out = [], seen = new Set();
    for (const ln of lines) {
      const t = ln.toLowerCase().replace(/[^a-z0-9 ]/g, "").trim();
      if (t.length < 3) continue;
      const first = t.split(" ")[0];
      for (const m of meds) {
        const n = (m.n || "").toLowerCase(); if (!n) continue;
        if (n.includes(t) || (first.length >= 4 && n.includes(first))) {
          if (!seen.has(m.id)) { seen.add(m.id); out.push(m); }
        }
      }
      if (out.length >= 8) break;
    }
    return out.slice(0, 8);
  }
  function pickMatchSheet(lines, matches) {
    openSheet(`<h3>Scanned text</h3><p class="hint">Pick the matching medicine, or add it as new.</p>
      <div class="dt" style="margin-bottom:10px">Read: ${esc(lines.slice(0, 3).join(" / "))}</div>
      ${matches.map(m => `<div class="row" data-id="${esc(m.id)}"><div class="meta"><div class="nm">${esc(m.n)}</div><div class="dt">${esc(m.g || "")} · Qty ${esc(m.s)}</div></div><div class="rt"><div class="price">${money(m.p)}</div></div></div>`).join("")}
      <button class="btn" id="asnew" style="margin-top:8px">＋ Add as new (${esc(lines[0] || "")})</button>`,
      () => {
        $("#modal-root").querySelectorAll("[data-id]").forEach(r => r.onclick = () => { const m = S.medicines.find(x => String(x.id) === r.dataset.id); closeSheet(); confirmSheet({ ...m }); });
        $("#asnew").onclick = () => { closeSheet(); confirmSheet({ n: lines[0] || "" }); };
      });
  }

  function confirmSheet(m, barcode) {
    const id = m.id || barcode || ("MV" + Date.now().toString(36).toUpperCase());
    openSheet(`
      <h3>Confirm product</h3>
      <p class="hint">${barcode ? "Barcode: " + esc(barcode) : "Check the details, then save."}</p>
      <div class="field"><label>Medicine name *</label>
        <input id="f_n" class="input" value="${esc(m.n || "")}" placeholder="e.g. Dolo 650"></div>
      <div class="two">
        <div class="field"><label>MRP (₹) *</label><input id="f_p" class="input" inputmode="decimal" value="${esc(m.p || "")}" placeholder="0.00"></div>
        <div class="field"><label>Quantity *</label><input id="f_s" class="input" inputmode="numeric" value="${esc(m.s || "")}" placeholder="0"></div>
      </div>
      <div class="two">
        <div class="field"><label>Batch</label><input id="f_b" class="input" value="${esc(m.batch || "")}" placeholder="optional"></div>
        <div class="field"><label>Expiry</label><input id="f_e" class="input" value="${esc(m.expiry || "")}" placeholder="MM/YY"></div>
      </div>
      <div class="field"><label>Generic / company</label><input id="f_g" class="input" value="${esc(m.g || "")}" placeholder="optional"></div>
      <button class="btn primary lg" id="save"><span class="ico">✓</span> Save product</button>
      <button class="btn ghost" id="saveNext" style="margin-top:10px;color:var(--green)">Save &amp; scan next</button>`,
      () => {
        $("#f_n").focus();
        const doSave = async (again) => {
          const payload = {
            id, n: $("#f_n").value.trim(), p: parseFloat($("#f_p").value) || 0, s: parseInt($("#f_s").value) || 0,
            batch: $("#f_b").value.trim(), expiry: $("#f_e").value.trim(), g: $("#f_g").value.trim()
          };
          if (!payload.n) return toast("Name is required", "err");
          if (!payload.p) return toast("MRP is required", "err");
          try {
            await api("/api/medicines", { method: "POST", body: payload });
            S.recent.unshift(payload);
            const i = S.medicines.findIndex(x => String(x.id) === String(id));
            if (i >= 0) S.medicines[i] = payload; else S.medicines.unshift(payload);
            buzz("Heavy"); toast("Saved: " + payload.n, "ok"); closeSheet();
            if (again) (scanMode === "barcode" ? doBarcodeFlow : doNameFlow)();
            else if (S.tab === "scan") renderRecent();
          } catch (e) { toast("Save failed: " + (e.message || "error"), "err"); }
        };
        $("#save").onclick = () => doSave(false);
        $("#saveNext").onclick = () => doSave(true);
      });
  }

  // =================================================================
  //  BILL
  // =================================================================
  function viewBill() {
    navEl.classList.remove("hide");
    if (!can("bill")) return lockedView("Billing", "billing");
    // Staff quick-select chips
    const staffChips = S.staff && S.staff.length
      ? S.staff.map((s, i) => `<button class="stchip${S.staffName === s.name ? ' on' : ''}" data-si="${i}" style="min-height:36px;padding:0 13px;border-radius:10px;font-size:13px;font-weight:700;background:${S.staffName === s.name ? 'var(--green)' : 'var(--card-2)'};color:${S.staffName === s.name ? '#04140b' : 'var(--txt-dim)'};border:1px solid var(--line-2)">${esc(s.name)}</button>`).join("")
      : `<span style="color:var(--txt-mut);font-size:13px">No staff set — add in Admin</span>`;
    app.innerHTML = `
      <div class="topbar"><h1>New bill</h1>
        <button class="btn" id="held" style="width:auto;padding:0 14px;min-height:42px">⏸ Held ${S.held.length}</button></div>
      <div class="card" style="padding:12px 14px">
        <div style="font-size:12px;color:var(--txt-dim);font-weight:700;margin-bottom:8px">BILLING STAFF</div>
        <div id="staffchips" style="display:flex;flex-wrap:wrap;gap:8px">${staffChips}</div>
      </div>
      <div class="card" style="margin-top:10px">
        <div class="two">
          <div class="field" style="margin:0"><label>Customer</label><input id="cn" class="input" value="${esc(S.cust.name)}" placeholder="Walk-in" autocomplete="off"></div>
          <div class="field" style="margin:0"><label>Phone</label><input id="cp" class="input" inputmode="tel" value="${esc(S.cust.phone)}" placeholder="optional"></div>
        </div>
        <div id="csug"></div>
        <div id="cinfo"></div>
      </div>
      <div class="search" style="margin-top:14px"><span class="si">🔍</span><input id="bq" class="input" placeholder="Add medicine to bill…" autocapitalize="none"></div>
      <div class="seg" id="bsort">${[["name", "A–Z"], ["margin", "Margin"], ["stock", "Low stock"], ["expiry", "Expiry"]].map(([k, l]) => `<button data-s="${k}" class="${stockSort === k ? "on" : ""}">${l}</button>`).join("")}</div>
      <div id="bres"></div>
      <div class="sectitle">Cart</div>
      <div id="cart"></div>
      <div class="card" id="total" style="margin-top:14px"></div>`;
    const cn = $("#cn"), cp = $("#cp");
    cn.oninput = () => { S.cust.name = cn.value; custSuggest(cn.value); };
    cp.oninput = () => { S.cust.phone = cp.value; };
    // Staff chip clicks
    app.querySelectorAll(".stchip").forEach(b => b.onclick = () => {
      const s = S.staff && S.staff[+b.dataset.si];
      if (!s) return;
      S.staffName = s.name; S.role = s.role || S.role; buzz();
      app.querySelectorAll(".stchip").forEach(x => { x.classList.toggle("on", x.dataset.si === b.dataset.si); x.style.background = x.dataset.si === b.dataset.si ? "var(--green)" : "var(--card-2)"; x.style.color = x.dataset.si === b.dataset.si ? "#04140b" : "var(--txt-dim)"; });
      toast(s.name + " billing", "ok");
    });
    $("#held").onclick = heldSheet;
    const q = $("#bq");
    app.querySelectorAll("#bsort button").forEach(b => b.onclick = () => { stockSort = b.dataset.s; app.querySelectorAll("#bsort button").forEach(x => x.classList.toggle("on", x.dataset.s === stockSort)); q.dispatchEvent(new Event("input")); });
    q.addEventListener("input", () => {
      const raw = q.value.trim(); const t = raw.toLowerCase();
      const res = !t ? [] : sortMeds(S.medicines.filter(m => (m.n || "").toLowerCase().includes(t))).slice(0, 6);
      if (t && !res.length) {
        $("#bres").innerHTML = `<button class="btn" id="enqbtn2">＋ Log "${esc(raw)}" as enquiry</button>`;
        $("#enqbtn2").onclick = () => { addEnquiry(raw); q.value = ""; $("#bres").innerHTML = ""; };
        return;
      }
      $("#bres").innerHTML = res.map(m => `<div class="row" data-add="${esc(m.id)}">
        <div class="meta"><div class="nm">${esc(m.n)}</div><div class="dt">Qty ${esc(m.s)}${S.loc[m.id] ? " · 📍" + esc(S.loc[m.id]) : ""}</div></div>
        <div class="rt"><div class="price">${money(m.p)}</div><div class="dt">tap to add</div></div></div>`).join("");
      $("#bres").querySelectorAll("[data-add]").forEach(r => r.onclick = () => { addToCart(r.dataset.add); q.value = ""; $("#bres").innerHTML = ""; });
    });
    loadCustomers(); custInfo(); renderCart();
  }
  async function loadCustomers() { if (S.customers.length) return; try { S.customers = await api("/api/customers") || []; } catch (e) {} }
  function custSuggest(t) {
    t = (t || "").toLowerCase().trim(); const el = $("#csug"); if (!el) return;
    if (t.length < 2) { el.innerHTML = ""; return; }
    const res = S.customers.filter(c => (c.name || "").toLowerCase().includes(t) || (c.phone || "").includes(t)).slice(0, 4);
    el.innerHTML = res.map(c => `<div class="row" data-cu='${esc(JSON.stringify({ n: c.name, p: c.phone }))}' style="margin-top:8px">
      <div class="meta"><div class="nm">${esc(c.name || "—")}</div><div class="dt">${esc(c.phone || "")} · ${c.visits || 0} visits</div></div>
      <div class="rt"><div class="price">${money(c.total || 0)}</div></div></div>`).join("");
    el.querySelectorAll("[data-cu]").forEach(r => r.onclick = () => { const c = JSON.parse(r.dataset.cu); S.cust = { name: c.n || "", phone: c.p || "" }; $("#cn").value = S.cust.name; $("#cp").value = S.cust.phone; el.innerHTML = ""; custInfo(); });
  }
  function custInfo() {
    const el = $("#cinfo"); if (!el) return;
    const c = S.customers.find(x => (S.cust.phone && x.phone === S.cust.phone) || (S.cust.name && x.name === S.cust.name));
    el.innerHTML = c ? `<div class="dt" style="margin-top:10px;color:var(--green)">Returning customer · ${c.visits || 0} visits · spent ${money(c.total || 0)}</div>` : "";
  }
  function addToCart(id) {
    const m = S.medicines.find(x => String(x.id) === String(id)); if (!m) return;
    const ex = S.cart.find(c => String(c.id) === String(id));
    if (ex) { ex.qty++; buzz(); renderCart(); return; }
    // New item — show dosage picker sheet first
    dosePicker(m, (dose) => {
      S.cart.push({ id: m.id, n: m.n, p: Number(m.p) || 0, qty: 1, dose });
      buzz(); renderCart();
    });
  }

  // Dosage picker sheet — picks morning/afternoon/night/days then calls back
  function dosePicker(m, cb) {
    const presets = [
      { label: "1-0-1",   m: 1, a: 0, n: 1, days: 5 },
      { label: "1-1-1",   m: 1, a: 1, n: 1, days: 5 },
      { label: "0-0-1",   m: 0, a: 0, n: 1, days: 5 },
      { label: "1-0-0",   m: 1, a: 0, n: 0, days: 5 },
      { label: "½-0-½",  m: 0.5, a: 0, n: 0.5, days: 5 },
      { label: "SOS",     m: 0, a: 0, n: 0, days: 1 },
    ];
    const fmtDose = d => d.m + "-" + d.a + "-" + d.n + (d.days > 1 ? " × " + d.days + " days" : "");
    openSheet(`
      <h3>${esc(m.n)}</h3>
      <p class="hint">Set dosage for the bill. Tap a preset or type custom.</p>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:14px" id="dpresets">
        ${presets.map((p, i) => `<button data-pi="${i}" style="min-height:48px;border-radius:12px;font-size:13px;font-weight:700;background:var(--card-2);color:var(--txt);border:1px solid var(--line-2)">${p.label}<br><span style="font-size:11px;font-weight:400;color:var(--txt-dim)">${p.days}d</span></button>`).join("")}
      </div>
      <div class="two" style="gap:8px;margin-bottom:10px">
        <div class="field" style="margin:0"><label>Morning</label><input id="dm" class="input" inputmode="decimal" value="1" style="text-align:center"></div>
        <div class="field" style="margin:0"><label>Afternoon</label><input id="da" class="input" inputmode="decimal" value="0" style="text-align:center"></div>
      </div>
      <div class="two" style="gap:8px;margin-bottom:14px">
        <div class="field" style="margin:0"><label>Night</label><input id="dn" class="input" inputmode="decimal" value="1" style="text-align:center"></div>
        <div class="field" style="margin:0"><label>Days</label><input id="dd" class="input" inputmode="numeric" value="5" style="text-align:center"></div>
      </div>
      <div id="dpreview" style="text-align:center;font-size:15px;font-weight:700;color:var(--green);margin-bottom:14px">1-0-1 × 5 days</div>
      <button class="btn primary" id="dadd">Add to bill</button>
      <button class="btn" id="dskip" style="margin-top:8px;color:var(--txt-mut)">Skip dosage</button>`,
      () => {
        const gv = id => parseFloat(($("#" + id) || {}).value) || 0;
        const updatePreview = () => {
          const d = { m: gv("dm"), a: gv("da"), n: gv("dn"), days: gv("dd") || 1 };
          const pr = $("#dpreview"); if (pr) pr.textContent = fmtDose(d);
        };
        ["dm","da","dn","dd"].forEach(id => { const el = $("#" + id); if (el) el.oninput = updatePreview; });
        $("#dpresets").querySelectorAll("[data-pi]").forEach(b => b.onclick = () => {
          const p = presets[+b.dataset.pi];
          ($("#dm")||{}).value = p.m; ($("#da")||{}).value = p.a;
          ($("#dn")||{}).value = p.n; ($("#dd")||{}).value = p.days;
          updatePreview(); buzz();
        });
        $("#dadd").onclick = () => {
          const dose = fmtDose({ m: gv("dm"), a: gv("da"), n: gv("dn"), days: gv("dd") || 1 });
          closeSheet(); cb(dose);
        };
        $("#dskip").onclick = () => { closeSheet(); cb(""); };
      });
  }
  function billTotals() {
    const sub = S.cart.reduce((s, c) => s + c.p * c.qty, 0);
    const disc = Math.min(S.disc || 0, sub);
    return { sub, disc, total: Math.max(0, sub - disc) };
  }
  function refreshTotals() {
    const { disc, total } = billTotals();
    const sd = $("#sumDisc"), st = $("#sumTotal"); if (sd) sd.textContent = "− " + money(disc); if (st) st.textContent = money(total);
  }
  function renderCart() {
    const el = $("#cart"); if (!el) return;
    if (!S.cart.length) { el.innerHTML = emptyBox("🧾", "Cart empty", "Search above to add items."); if ($("#total")) $("#total").innerHTML = ""; return; }
    el.innerHTML = S.cart.map(c => `<div class="row" style="flex-wrap:wrap">
      <div class="meta" style="flex-basis:100%;margin-bottom:${c.dose ? 4 : 0}px">
        <div class="nm">${esc(c.n)}</div>
        <div class="dt">${money(c.p)} each${c.dose ? ` · <span style="color:var(--green);font-weight:700">${esc(c.dose)}</span>` : ""}</div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;margin-left:auto">
        <button class="btn" style="width:38px;height:38px;min-height:38px;padding:0" data-dec="${esc(c.id)}">−</button>
        <b style="min-width:24px;text-align:center">${c.qty}</b>
        <button class="btn" style="width:38px;height:38px;min-height:38px;padding:0" data-inc="${esc(c.id)}">＋</button>
        <button class="btn" style="width:38px;height:38px;min-height:38px;padding:0;font-size:14px" data-dose="${esc(c.id)}" title="Edit dosage">💊</button>
      </div></div>`).join("");
    el.querySelectorAll("[data-inc]").forEach(b => b.onclick = () => { S.cart.find(c => String(c.id) === b.dataset.inc).qty++; buzz(); renderCart(); });
    el.querySelectorAll("[data-dec]").forEach(b => b.onclick = () => { const c = S.cart.find(c => String(c.id) === b.dataset.dec); c.qty--; if (c.qty <= 0) S.cart = S.cart.filter(x => x !== c); buzz(); renderCart(); });
    el.querySelectorAll("[data-dose]").forEach(b => b.onclick = () => { const c = S.cart.find(c => String(c.id) === b.dataset.dose); if (!c) return; const m = S.medicines.find(x => String(x.id) === String(c.id)) || { n: c.n }; dosePicker(m, dose => { c.dose = dose; renderCart(); }); });
    const { sub, disc, total } = billTotals();
    const pays = [["cash", "Cash"], ["upi", "UPI"], ["card", "Card"], ["credit", "Credit"]];
    $("#total").innerHTML = `
      <div class="field" style="margin-bottom:12px"><label>Discount (₹)</label><input id="disc" class="input" inputmode="decimal" value="${S.disc || ""}" placeholder="0"></div>
      <label style="display:block;font-size:13px;color:var(--txt-dim);margin-bottom:7px;font-weight:600">Payment</label>
      <div class="seg" id="pay">${pays.map(([k, l]) => `<button data-p="${k}" class="${S.pay === k ? "on" : ""}">${l}</button>`).join("")}</div>
      <div style="display:flex;justify-content:space-between;color:var(--txt-dim);font-size:14px;margin:4px 0"><span>Subtotal</span><span>${money(sub)}</span></div>
      <div style="display:flex;justify-content:space-between;color:var(--txt-dim);font-size:14px;margin:4px 0"><span>Discount</span><span id="sumDisc">− ${money(disc)}</span></div>
      <div style="display:flex;justify-content:space-between;font-size:21px;font-weight:800;margin:8px 0 14px"><span>Total</span><span id="sumTotal" style="color:var(--green)">${money(total)}</span></div>
      ${S.pay === "credit" ? '<div class="dt" style="color:var(--amber);margin:-6px 0 12px">⚠️ Credit (khata) — added to customer\'s due</div>' : ''}
      ${S.pay === "upi" ? '<button class="btn" id="upiqr" style="margin-bottom:10px">📷 Show UPI QR to customer</button>' : ''}
      <button class="btn primary lg" id="save">${can("print") ? "💾 Save & Print" : "💾 Save bill"}</button>
      <button class="btn" id="hold" style="margin-top:10px">⏸ Hold this bill</button>`;
    { const uq = $("#upiqr"); if (uq) uq.onclick = () => showUpiQr(total); }
    $("#disc").oninput = e => { S.disc = parseFloat(e.target.value) || 0; refreshTotals(); };
    app.querySelectorAll("#pay button").forEach(b => b.onclick = () => { S.pay = b.dataset.p; buzz(); renderCart(); });
    $("#save").onclick = saveBill;
    $("#hold").onclick = holdBill;
  }
  function holdBill() {
    if (!S.cart.length) return toast("Cart is empty", "err");
    S.held.push({ cart: S.cart, cust: S.cust, disc: S.disc, pay: S.pay, at: Date.now() });
    store.set("mv_held", JSON.stringify(S.held));
    S.cart = []; S.cust = { name: "", phone: "" }; S.disc = 0; S.pay = "cash";
    buzz("Medium"); toast("Bill held", "ok"); viewBill();
  }
  function heldSheet() {
    if (!S.held.length) return toast("No held bills", "");
    openSheet(`<h3>Held bills</h3><p class="hint">Tap to resume, ✕ to discard.</p>` + S.held.map((h, i) => {
      const sub = h.cart.reduce((a, c) => a + c.p * c.qty, 0);
      return `<div class="row" data-h="${i}"><div class="meta"><div class="nm">${esc(h.cust.name || "Walk-in")}</div><div class="dt">${h.cart.length} items · ${new Date(h.at).toLocaleTimeString()}</div></div>
        <div class="rt" style="display:flex;align-items:center;gap:10px"><div class="price">${money(sub)}</div><button class="btn" style="width:34px;height:34px;min-height:34px;padding:0;color:var(--red)" data-del="${i}">✕</button></div></div>`;
    }).join(""), () => {
      $("#modal-root").querySelectorAll("[data-del]").forEach(b => b.onclick = (ev) => { ev.stopPropagation(); S.held.splice(+b.dataset.del, 1); store.set("mv_held", JSON.stringify(S.held)); closeSheet(); heldSheet(); });
      $("#modal-root").querySelectorAll("[data-h]").forEach(r => r.onclick = () => { const i = +r.dataset.h; const h = S.held[i]; S.cart = h.cart; S.cust = h.cust; S.disc = h.disc; S.pay = h.pay; S.held.splice(i, 1); store.set("mv_held", JSON.stringify(S.held)); closeSheet(); viewBill(); });
    });
  }
  function receiptText(b) {
    const su = (S.setup && S.setup.shopName) ? S.setup : null;
    const shop = (su && su.shopName) || (S.me && S.me.name) || "MediVision";
    const L = [shop];
    if (su && su.address) L.push(su.address);
    if (su && su.phone) L.push("Ph: " + su.phone);
    if (su && su.gst) L.push("GST: " + su.gst);
    if (su && su.drugLicense) L.push("DL: " + su.drugLicense);
    if (su && su.billHeader) L.push(su.billHeader);
    L.push(b.date + "  " + new Date(b.ts).toLocaleTimeString(), "Bill: " + b.id);
    if (b.staff_name) L.push("Staff: " + b.staff_name);
    if (b.cust && b.cust !== "Walk-in") L.push("Cust: " + b.cust + (b.phone ? " (" + b.phone + ")" : ""));
    L.push("--------------------------------");
    b.items.forEach(it => {
      L.push(it.n);
      const doseLine = it.dose ? ("  Dose: " + it.dose) : "";
      L.push("  " + it.qty + " x " + money(it.price) + "   " + money(it.qty * it.price) + (doseLine ? "\n" + doseLine : ""));
    });
    L.push("--------------------------------");
    L.push("Subtotal: " + money(b.sub));
    if (b.disc) L.push("Discount: -" + money(b.disc));
    L.push("TOTAL: " + money(b.total));
    L.push("Pay: " + String(b.pay).toUpperCase());
    L.push("");
    L.push((su && su.billFooter) || "Thank you! Visit again.");
    return L.join("\n");
  }
  function printReceipt(b) {
    const hasPhone = b.phone && b.phone.replace(/\D/g, "").length >= 10;
    openSheet(`<h3>Receipt</h3><p class="hint">Send free on WhatsApp (1 tap), or screenshot. A paired Bluetooth printer prints automatically.</p>
      <pre style="white-space:pre-wrap;background:var(--bg-2);border:1px solid var(--line);border-radius:12px;padding:14px;font-size:13px;line-height:1.5;font-family:monospace;color:var(--txt)">${esc(receiptText(b))}</pre>
      ${hasPhone ? '<button class="btn primary" id="wabill">📲 Send bill on WhatsApp</button>' : ''}
      ${hasPhone && b.pay === "credit" ? '<button class="btn" id="wacredit" style="margin-top:10px;color:var(--amber)">⏰ Send credit reminder</button>' : ''}
      <button class="btn" id="rok" style="margin-top:10px">Done</button>`,
      () => {
        $("#rok").onclick = closeSheet;
        const wb = $("#wabill"); if (wb) wb.onclick = () => waSend(b.phone, receiptText(b));
        const wc = $("#wacredit"); if (wc) wc.onclick = () => waSend(b.phone, `Dear ${b.cust || "customer"}, a friendly reminder from ${(S.me && S.me.name) || "our pharmacy"}: your credit (khata) of ${money(b.total)} for bill ${b.id} is pending. Kindly pay at your convenience. Thank you!`);
      });
  }
  // ---------- thermal printer (capacitor-thermal-printer) ----------
  const rs = n => "Rs " + (Number(n) || 0).toFixed(2);
  async function doPrint(b) {
    const t = P.CapacitorThermalPrinter; const addr = await store.get("mv_printer");
    if (t && addr) return btPrintReceipt(b, t, addr);
    printReceipt(b);
  }
  async function btPrintReceipt(b, t, addr) {
    try {
      toast("Connecting to printer…");
      const dev = await t.connect({ address: addr });
      if (!dev) { toast("Printer not reachable — showing preview", "err"); return printReceipt(b); }
      const su = (S.setup && S.setup.shopName) ? S.setup : null;
      const shop = (su && su.shopName) || (S.me && S.me.name) || "MediVision";
      await t.begin();
      await t.align({ alignment: "center" });
      await t.bold({ enabled: true }); await t.doubleHeight({ enabled: true });
      await t.text({ text: shop + "\n" });
      await t.clearFormatting();
      if (su && su.address) await t.text({ text: su.address + "\n" });
      if (su && su.phone) await t.text({ text: "Ph: " + su.phone + "\n" });
      if (su && su.gst) await t.text({ text: "GST: " + su.gst + "\n" });
      if (su && su.billHeader) await t.text({ text: su.billHeader + "\n" });
      await t.text({ text: b.date + "  " + new Date(b.ts).toLocaleTimeString() + "\n" });
      await t.text({ text: "Bill: " + b.id + "\n" });
      if (b.staff_name) await t.text({ text: "Staff: " + b.staff_name + "\n" });
      if (b.cust && b.cust !== "Walk-in") await t.text({ text: b.cust + (b.phone ? " " + b.phone : "") + "\n" });
      await t.align({ alignment: "left" });
      await t.text({ text: "--------------------------------\n" });
      for (const it of b.items) {
        await t.text({ text: it.n + "\n" });
        await t.text({ text: "  " + it.qty + " x " + rs(it.price) + "   " + rs(it.qty * it.price) + "\n" });
      }
      await t.text({ text: "--------------------------------\n" });
      await t.text({ text: "Subtotal: " + rs(b.sub) + "\n" });
      if (b.disc) await t.text({ text: "Discount: -" + rs(b.disc) + "\n" });
      await t.bold({ enabled: true }); await t.text({ text: "TOTAL: " + rs(b.total) + "\n" }); await t.clearFormatting();
      await t.text({ text: "Pay: " + String(b.pay).toUpperCase() + "\n" });
      await t.align({ alignment: "center" });
      await t.text({ text: "\nThank you! Visit again.\n\n" });
      await t.cutPaper({ half: false });
      await t.write();
      buzz("Heavy"); toast("Printed ✓", "ok");
    } catch (e) { toast("Print error — showing preview", "err"); printReceipt(b); }
  }
  function printerSheet() {
    const t = P.CapacitorThermalPrinter;
    if (!t) return toast("Printer activates after the update + rebuild", "");
    openSheet(`<h3>Bluetooth printer</h3><p class="hint">Turn the printer on, then Scan. Tap a device to pair.</p>
      <button class="btn primary" id="scan">🔍 Scan for printers</button>
      <div id="devs" style="margin-top:12px"></div>`,
      () => {
        const render = (list) => {
          const el = $("#devs"); if (!el) return;
          el.innerHTML = (list && list.length) ? list.map(d => `<div class="row" data-a="${esc(d.address)}"><div class="meta"><div class="nm">${esc(d.name || "Printer")}</div><div class="dt">${esc(d.address)}</div></div><div class="rt"><span class="pill ok">Pair</span></div></div>`).join("") : '<div class="empty">No devices yet — make sure the printer is on.</div>';
          el.querySelectorAll("[data-a]").forEach(r => r.onclick = async () => { const a = r.dataset.a; try { const dev = await t.connect({ address: a }); if (dev) { await store.set("mv_printer", a); buzz("Heavy"); toast("Printer paired ✓", "ok"); closeSheet(); } else toast("Connect failed", "err"); } catch (e) { toast("Connect failed", "err"); } });
        };
        try { t.addListener && t.addListener("discoverDevices", (ev) => render((ev && ev.devices) || ev || [])); } catch (e) {}
        $("#scan").onclick = async () => { try { await t.startScan(); toast("Scanning…"); } catch (e) { toast("Scan failed — check Bluetooth", "err"); } };
      });
  }
  async function saveBill() {
    if (!S.cart.length) return toast("Cart is empty", "err");
    const { sub, disc, total } = billTotals();
    const now = new Date();
    const payload = {
      id: "B" + now.getTime().toString(36).toUpperCase(),
      ts: now.toISOString(), date: now.toISOString().slice(0, 10),
      cust: (S.cust.name || "Walk-in").trim() || "Walk-in", phone: (S.cust.phone || "").trim() || "-",
      pay: S.pay, sub: +sub.toFixed(2), disc: +disc.toFixed(2), tax: 0, total: +total.toFixed(2),
      items: S.cart.map(c => ({ id: c.id, n: c.n, qty: c.qty, price: c.p, dose: c.dose || "" })),
      staff_name: S.staffName || (S.me && S.me.name) || "",
    };
    const btn = $("#save"); if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
    try {
      await api("/api/bills", { method: "POST", body: payload });
      buzz("Heavy"); toast("Bill saved " + money(total), "ok");
      payload.items.forEach(it => { const m = S.medicines.find(x => String(x.id) === String(it.id)); if (m) m.s = Math.max(0, (+m.s || 0) - it.qty); });
      S.customers = []; // refresh customer cache next open
      const printed = can("print"); const last = payload;
      S.cart = []; S.disc = 0; S.pay = "cash"; S.cust = { name: "", phone: "" };
      viewBill();
      if (window.MVBACKUP && cfg.STANDALONE) window.MVBACKUP.saveToPhone().catch(() => {});
      if (printed) doPrint(last);
    } catch (e) { if (btn) btn.disabled = false; toast("Save failed: " + (e.message || "error"), "err"); }
  }

  // =================================================================
  //  MORE
  // =================================================================
  function viewMore() {
    navEl.classList.remove("hide");
    const pk = S.planKey;
    app.innerHTML = `
      <div class="topbar"><h1>Settings</h1></div>
      <div class="card"><div style="display:flex;justify-content:space-between;align-items:center">
        <div><div style="font-weight:700">${esc(S.me ? S.me.name : "")}</div><div class="sub" style="color:var(--txt-dim)">Signed in</div></div>
        <span class="plan-badge">${esc(plan().label)}</span></div></div>

      <div class="sectitle">Your plan</div>
      <div class="row"><div class="meta"><div class="nm">${esc(plan().label)}</div><div class="dt">${plan().features.length} features</div></div><div class="rt"><div class="price">₹${plan().price}/mo</div><div class="dt" style="color:var(--green)">active</div></div></div>
      <div class="dt" style="margin:8px 2px 0">Contact MediVision to upgrade your plan.</div>

      <div class="sectitle">Shop tools</div>
      <button class="btn" id="setupbtn" style="justify-content:flex-start;gap:12px"><span class="ico">🏪</span>Shop Setup (name, GST, licence)</button>
      <div style="height:10px"></div>
      <button class="btn" id="enq" style="justify-content:flex-start;gap:12px"><span class="ico">📝</span>Enquiries (${S.enquiries.length})</button>
      <div style="height:10px"></div>
      <button class="btn" id="paycfg" style="justify-content:flex-start;gap:12px"><span class="ico">💳</span>Payment &amp; cash setup</button>
      <div style="height:10px"></div>
      <button class="btn" id="cash" style="justify-content:flex-start;gap:12px"><span class="ico">💵</span>Cash drawer (today)</button>
      <div style="height:10px"></div>
      ${roleCan("returns") ? '<button class="btn" id="retbtn" style="justify-content:flex-start;gap:12px"><span class="ico">↩️</span>Return / refund</button><div style="height:10px"></div>' : ''}
      <button class="btn" id="bkbtn" style="justify-content:flex-start;gap:12px"><span class="ico">🛟</span>Backup &amp; restore</button>
      <div style="height:10px"></div>
      <button class="btn" id="stfbtn" style="justify-content:flex-start;gap:12px"><span class="ico">👥</span>Switch staff</button>
      ${roleCan("wholesale") ? '<div style="height:10px"></div><button class="btn" id="whbtn" style="justify-content:flex-start;gap:12px"><span class="ico">🏭</span>Wholesale platform</button>' : ''}
      ${roleCan("admin") ? '<div style="height:10px"></div><button class="btn" id="adbtn" style="justify-content:flex-start;gap:12px"><span class="ico">🔐</span>Admin / Members</button>' : ''}

      <div class="sectitle">App</div>
      <button class="btn" id="thm" style="justify-content:flex-start;gap:12px"><span class="ico">${S.theme === "light" ? "🌙" : "☀️"}</span>Appearance: ${S.theme === "light" ? "Light" : "Dark"}</button>
      <div style="height:10px"></div>
      ${can("print") ? '<button class="btn" id="prn" style="justify-content:flex-start;gap:12px"><span class="ico">🖨</span>Printer setup</button><div style="height:10px"></div>' : ''}
      ${cfg.STANDALONE ? '' : '<button class="btn" id="srv" style="justify-content:flex-start;gap:12px"><span class="ico">🌐</span>Server settings</button><div style="height:10px"></div>'}
      <button class="btn" id="out" style="justify-content:flex-start;gap:12px;color:var(--red)"><span class="ico">↩</span>Sign out</button>

      <div class="sectitle" style="margin-top:20px">🚀 Coming soon</div>
      <button class="btn cs" data-cs="Demand forecast &amp; reorder alerts (Smart ₹700)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🔮</span>Demand forecast + reorder alerts</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Customer loyalty, groups &amp; monthly order notes (Smart ₹700)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">👥</span>Customer loyalty &amp; groups</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Swipe-to-order on stock list (Smart ₹700)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">👆</span>Swipe-to-order</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Twilio automated call reminders for credit (Smart ₹700)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">📞</span>Twilio call reminders</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Tally / accounting sync (Pro ₹1000)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🔄</span>Tally sync</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Multi-counter — run two billing windows at once (Pro ₹1000)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🖥</span>Multi-counter</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Face attendance + customer face registration (Pro ₹1000)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🧑</span>Face attendance &amp; customer register</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Hindi ↔ Tamil local language UI (Pro ₹1000)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🌐</span>Local language / Hindi↔Tamil</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Multi-branch stock push &amp; fleet dashboard (Max ₹1599)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🏬</span>Multi-branch stock push</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Dedicated WhatsApp number + n8n auto order-to-bill (Max ₹1599)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">📱</span>WhatsApp auto order → bill</button>
      <div style="height:8px"></div>
      <button class="btn cs" data-cs="Wholesaler full workflow: pack / checker / photo / delivery (Max ₹1599)" style="justify-content:flex-start;gap:12px;opacity:.75"><span class="ico">🏭</span>Wholesaler full workflow</button>
      <p style="text-align:center;color:var(--txt-mut);font-size:12px;margin-top:24px">MediVision Mobile · Phase 0 · v0.1</p>`;
    // plan is owner-controlled — read-only here (no self-switching)
    $("#thm").onclick = async () => { await toggleTheme(); viewMore(); };
    $("#setupbtn").onclick = () => go("setup");
    $("#enq").onclick = enquirySheet;
    $("#paycfg").onclick = paymentSetupSheet;
    $("#cash").onclick = cashDrawerSheet;
    { const _r = $("#retbtn"); if (_r) _r.onclick = () => go("ret"); }
    $("#bkbtn").onclick = backupSheet;
    $("#stfbtn").onclick = staffSheet;
    { const _w = $("#whbtn"); if (_w) _w.onclick = () => go("wholesale"); }
    { const _a = $("#adbtn"); if (_a) _a.onclick = () => go("admin"); }
    { const _pb = $("#prn"); if (_pb) _pb.onclick = printerSheet; }
    app.querySelectorAll(".cs").forEach(b => b.onclick = () => toast("Coming soon: " + b.dataset.cs, ""));
    { const _sv = $("#srv"); if (_sv) _sv.onclick = serverSheet; }
    $("#out").onclick = logout;
  }
  async function logout() {
    try { await api("/api/portal/logout", { method: "POST" }); } catch (e) {}
    S.me = null; S.medicines = []; S.cart = []; S.recent = [];
    await store.del("mv_user"); viewLogin();
  }

  // =================================================================
  //  shared UI bits
  // =================================================================
  function lockedView(name, neededPlan) {
    const need = cfg.PLANS[neededPlan];
    app.innerHTML = `<div class="lock"><div class="e">🔒</div><h2>${esc(name)} is locked</h2>
      <p>Upgrade to <b>${esc(need.label)}</b> (₹${need.price}/mo) to unlock this.</p>
      <button class="btn primary" onclick="MV.go('more')">See plans</button></div>`;
  }
  const emptyBox = (e, t, s) => `<div class="empty"><div class="e">${e}</div><div style="font-weight:700;color:var(--txt-dim)">${esc(t)}</div><div style="font-size:13px;margin-top:4px">${esc(s)}</div></div>`;

  function openSheet(html, after) {
    const root = $("#modal-root");
    root.innerHTML = `<div class="sheet-bg"><div class="sheet"><div class="grab"></div>${html}</div></div>`;
    root.querySelector(".sheet-bg").onclick = e => { if (e.target.classList.contains("sheet-bg")) closeSheet(); };
    after && after();
  }
  function closeSheet() { $("#modal-root").innerHTML = ""; }

  // ---------- data ----------
  async function loadMeds() {
    try { S.medicines = await api("/api/medicines") || []; } catch (e) { S.medicines = []; }
    return S.medicines;
  }
  function isExpiringSoon(expiry) {
    if (!expiry) return false;
    const m = String(expiry).match(/(\d{1,2})[\/\-](\d{2,4})/);
    if (!m) return false;
    let mo = +m[1], yr = +m[2]; if (yr < 100) yr += 2000;
    const d = new Date(yr, mo, 0); const days = (d - Date.now()) / 864e5;
    return days >= 0 && days <= 90;
  }

  // =================================================================
  //  RETURNS / REFUND
  // =================================================================
  let retCart = [];
  function viewReturns() {
    navEl.classList.remove("hide");
    if (!roleCan("returns")) return roleBlock("Returns");
    if (!can("bill")) return lockedView("Returns", "billing");
    app.innerHTML = `
      <div class="topbar"><h1>Return / refund</h1><span class="plan-badge">${retCart.length} items</span></div>
      <div class="search"><span class="si">🔍</span><input id="rq" class="input" placeholder="Search returned medicine…" autocapitalize="none"></div>
      <div id="rres"></div>
      <div class="sectitle">Returning</div>
      <div id="rcart"></div>
      <div class="card" id="rtotal" style="margin-top:14px"></div>`;
    const q = $("#rq");
    q.addEventListener("input", () => {
      const t = q.value.toLowerCase().trim();
      const res = !t ? [] : sortMeds(S.medicines.filter(m => (m.n || "").toLowerCase().includes(t))).slice(0, 6);
      $("#rres").innerHTML = res.map(m => `<div class="row" data-radd="${esc(m.id)}"><div class="meta"><div class="nm">${esc(m.n)}</div><div class="dt">Qty ${esc(m.s)}</div></div><div class="rt"><div class="price">${money(m.p)}</div><div class="dt">tap to add</div></div></div>`).join("");
      $("#rres").querySelectorAll("[data-radd]").forEach(r => r.onclick = () => { retAdd(r.dataset.radd); q.value = ""; $("#rres").innerHTML = ""; });
    });
    renderRet();
  }
  function retAdd(id) {
    const m = S.medicines.find(x => String(x.id) === String(id)); if (!m) return;
    const ex = retCart.find(c => String(c.id) === String(id));
    if (ex) ex.qty++; else retCart.push({ id: m.id, n: m.n, p: Number(m.p) || 0, qty: 1 });
    buzz(); renderRet();
  }
  function renderRet() {
    const el = $("#rcart"); if (!el) return;
    if (!retCart.length) { el.innerHTML = emptyBox("↩️", "Nothing to return", "Search above to add items."); if ($("#rtotal")) $("#rtotal").innerHTML = ""; return; }
    el.innerHTML = retCart.map(c => `<div class="row"><div class="meta"><div class="nm">${esc(c.n)}</div><div class="dt">${money(c.p)} each</div></div>
      <div class="rt" style="display:flex;align-items:center;gap:10px"><button class="btn" style="width:38px;height:38px;min-height:38px;padding:0" data-rdec="${esc(c.id)}">−</button><b style="min-width:20px;text-align:center">${c.qty}</b><button class="btn" style="width:38px;height:38px;min-height:38px;padding:0" data-rinc="${esc(c.id)}">＋</button></div></div>`).join("");
    el.querySelectorAll("[data-rinc]").forEach(b => b.onclick = () => { retCart.find(c => String(c.id) === b.dataset.rinc).qty++; buzz(); renderRet(); });
    el.querySelectorAll("[data-rdec]").forEach(b => b.onclick = () => { const c = retCart.find(c => String(c.id) === b.dataset.rdec); c.qty--; if (c.qty <= 0) retCart = retCart.filter(x => x !== c); buzz(); renderRet(); });
    const total = retCart.reduce((s, c) => s + c.p * c.qty, 0);
    $("#rtotal").innerHTML = `<div class="field"><label>Reason</label><input id="rreason" class="input" placeholder="e.g. expired, damaged, wrong item"></div>
      <div style="display:flex;justify-content:space-between;font-size:21px;font-weight:800;margin:8px 0 14px"><span>Refund</span><span style="color:var(--amber)">${money(total)}</span></div>
      <button class="btn primary lg" id="rsave">↩ Process return (restock)</button>`;
    $("#rsave").onclick = saveReturn;
  }
  async function saveReturn() {
    if (!retCart.length) return;
    const total = retCart.reduce((s, c) => s + c.p * c.qty, 0);
    const body = { items: retCart.map(c => ({ id: c.id, n: c.n, qty: c.qty, price: c.p })), total, reason: ($("#rreason") ? $("#rreason").value.trim() : "") || "Return" };
    const btn = $("#rsave"); if (btn) { btn.disabled = true; btn.textContent = "Processing…"; }
    try {
      await api("/api/returns", { method: "POST", body });
      body.items.forEach(it => { const m = S.medicines.find(x => String(x.id) === String(it.id)); if (m) m.s = (Number(m.s) || 0) + it.qty; });
      buzz("Heavy"); toast("Return processed " + money(total), "ok");
      retCart = []; viewReturns();
    } catch (e) { if (btn) btn.disabled = false; toast("Return failed: " + (e.message || "error"), "err"); }
  }

  // =================================================================
  //  QUICK WINS — WhatsApp, enquiries, location, UPI QR, cash drawer
  // =================================================================
  function waSend(phone, text) {
    const num = String(phone || "").replace(/\D/g, "").slice(-10);
    const url = "https://wa.me/" + (num ? "91" + num : "") + "?text=" + encodeURIComponent(text);
    try { window.open(url, "_system"); } catch (e) { try { window.open(url, "_blank"); } catch (e2) { toast("Couldn't open WhatsApp", "err"); } }
  }
  // --- enquiry log (local demand list) ---
  async function addEnquiry(q) {
    q = (q || "").trim(); if (!q) return;
    S.enquiries.unshift({ q, at: Date.now() });
    await store.set("mv_enq", JSON.stringify(S.enquiries.slice(0, 500)));
    buzz("Medium"); toast("Enquiry logged: " + q, "ok");
  }
  function enquirySheet() {
    const list = S.enquiries;
    openSheet(`<h3>Enquiries (${list.length})</h3><p class="hint">Items customers asked for — your reorder demand list.</p>
      ${list.length ? list.slice(0, 40).map((e, i) => `<div class="row"><div class="meta"><div class="nm">${esc(e.q)}</div><div class="dt">${new Date(e.at).toLocaleString()}</div></div><div class="rt"><button class="btn" style="width:34px;height:34px;min-height:34px;padding:0;color:var(--red)" data-x="${i}">✕</button></div></div>`).join("") : emptyBox("📝", "No enquiries yet", "Searches that find nothing get logged here.")}
      ${list.length ? '<button class="btn" id="enqexp" style="margin-top:8px">⬇ Export list</button><button class="btn" id="enqclr" style="margin-top:10px;color:var(--red)">Clear all</button>' : ""}`,
      () => {
        $("#modal-root").querySelectorAll("[data-x]").forEach(b => b.onclick = async () => { S.enquiries.splice(+b.dataset.x, 1); await store.set("mv_enq", JSON.stringify(S.enquiries)); closeSheet(); enquirySheet(); });
        const ex = $("#enqexp"); if (ex) ex.onclick = () => shareFile("MediVision-enquiries.csv", "item,date\n" + S.enquiries.map(e => csvEscape(e.q) + "," + new Date(e.at).toLocaleString()).join("\n"));
        const cl = $("#enqclr"); if (cl) cl.onclick = async () => { S.enquiries = []; await store.set("mv_enq", "[]"); closeSheet(); toast("Cleared", "ok"); };
      });
  }
  // --- item rack location (local) ---
  function locSheet(m) {
    const low = Number(m.s) <= Number(m.reorder || 0) && Number(m.reorder || 0) > 0;
    const exp = isExpiringSoon(m.expiry);
    const mg = marginPct(m);
    openSheet(`<h3>${esc(m.n)}</h3>
      <div class="dt" style="margin-bottom:6px">${esc(m.g || "—")}${m.batch ? " · " + esc(m.batch) : ""}${m.expiry ? " · Exp " + esc(m.expiry) : ""}</div>
      <div style="margin-bottom:10px">${low ? '<span class="pill low">⚠ Low: ' + esc(m.s) + ' units</span> ' : '<span class="pill ok">Stock: ' + esc(m.s) + '</span> '}${exp ? '<span class="pill exp">Expiring soon</span> ' : ''}${mg !== null ? '<span class="pill ' + (mg >= 20 ? 'ok' : 'low') + '">' + mg + '% margin</span>' : ''}</div>
      <div class="dt" style="margin-bottom:14px">MRP ${money(m.p)}${m.p_rate ? " · Purchase ₹" + esc(m.p_rate) : ""}${m.reorder ? " · Reorder at " + esc(m.reorder) : ""}</div>
      <div class="field"><label>Rack location (e.g. R3-B2)</label><input id="loc" class="input" value="${esc(S.loc[m.id] || "")}" placeholder="leave blank to clear"></div>
      <button class="btn primary" id="locok">Save location</button>
      <div style="height:10px"></div>
      <button class="btn" id="alts" style="justify-content:flex-start;gap:10px"><span class="ico">🔄</span>Substitutes / alternatives</button>
      <div style="height:8px"></div>
      <button class="btn" id="fcbtn" style="justify-content:flex-start;gap:10px"><span class="ico">📈</span>Demand forecast for this item</button>`,
      () => {
        $("#loc").focus();
        $("#locok").onclick = async () => { const v = $("#loc").value.trim(); if (v) S.loc[m.id] = v; else delete S.loc[m.id]; await store.set("mv_loc", JSON.stringify(S.loc)); closeSheet(); toast("Saved", "ok"); if (S.tab === "stock") viewStock(); };
        $("#alts").onclick = () => toast("Substitutes / alternatives — coming in Smart plan 🚀", "");
        $("#fcbtn").onclick = () => toast("Demand forecast — coming in Smart plan 🚀", "");
      });
  }
  // --- payment & cash setup ---
  function paymentSetupSheet() {
    openSheet(`<h3>Payment &amp; cash</h3><p class="hint">Your UPI QR shows to customers at UPI payment.</p>
      <button class="btn" id="pickqr">${S.upiQr ? "Replace UPI QR image" : "📷 Add UPI QR image"}</button>
      ${S.upiQr ? `<img src="${S.upiQr}" style="width:140px;height:140px;object-fit:contain;display:block;margin:12px auto;border-radius:12px;background:#fff;padding:6px">` : ""}
      <div class="field" style="margin-top:14px"><label>Cash drawer — opening balance today (₹)</label><input id="copen" class="input" inputmode="decimal" value="${S.cashOpen && S.cashOpen.date === new Date().toISOString().slice(0,10) ? (S.cashOpen.amount || "") : ""}" placeholder="0"></div>
      <button class="btn primary" id="psave">Save</button>`,
      () => {
        $("#pickqr").onclick = async () => {
          const cam = P.Camera; if (!cam) return toast("Photo picker needs the update", "");
          try { const ph = await cam.getPhoto({ source: "PHOTOS", resultType: "base64", quality: 80, allowEditing: true }); if (ph && ph.base64String) { S.upiQr = "data:image/jpeg;base64," + ph.base64String; await store.set("mv_upi_qr", S.upiQr); closeSheet(); paymentSetupSheet(); toast("UPI QR saved", "ok"); } } catch (e) {}
        };
        $("#psave").onclick = async () => { S.cashOpen = { date: new Date().toISOString().slice(0, 10), amount: parseFloat($("#copen").value) || 0 }; await store.set("mv_cash_open", JSON.stringify(S.cashOpen)); closeSheet(); toast("Saved", "ok"); };
      });
  }
  function showUpiQr(amount) {
    if (!S.upiQr) return paymentSetupSheet();
    openSheet(`<h3 style="text-align:center">Scan to pay ${money(amount)}</h3><p class="hint" style="text-align:center">Customer scans this with any UPI app.</p>
      <img src="${S.upiQr}" style="width:min(86vw,380px);height:auto;aspect-ratio:1;object-fit:contain;display:block;margin:10px auto 18px;border-radius:16px;background:#fff;padding:12px">
      <button class="btn primary lg" id="qrok">Done</button>`, () => { $("#qrok").onclick = closeSheet; });
  }
  async function cashDrawerSheet() {
    let bills = []; try { const r = await api("/api/bills"); bills = Array.isArray(r) ? r : (r.bills || []); } catch (e) {}
    const today = new Date().toISOString().slice(0, 10);
    const cashToday = bills.filter(b => (b.date || (b.ts || "").slice(0, 10)) === today && String(b.pay).toLowerCase() === "cash").reduce((s, b) => s + (Number(b.total) || 0), 0);
    const opening = (S.cashOpen && S.cashOpen.date === today) ? (S.cashOpen.amount || 0) : 0;
    openSheet(`<h3>Cash drawer — today</h3>
      <div style="display:flex;justify-content:space-between;margin:8px 0;color:var(--txt-dim)"><span>Opening</span><span>${money(opening)}</span></div>
      <div style="display:flex;justify-content:space-between;margin:8px 0;color:var(--txt-dim)"><span>Cash sales</span><span>+ ${money(cashToday)}</span></div>
      <div style="display:flex;justify-content:space-between;font-size:21px;font-weight:800;margin:10px 0 16px"><span>In drawer</span><span style="color:var(--green)">${money(opening + cashToday)}</span></div>
      <button class="btn" id="setopen">Set opening balance</button><button class="btn primary" id="cdok" style="margin-top:10px">Done</button>`,
      () => { $("#cdok").onclick = closeSheet; $("#setopen").onclick = () => { closeSheet(); paymentSetupSheet(); }; });
  }

  async function backupSheet() {
    const B = window.MVBACKUP; if (!B) return toast("Backup needs the update", "");
    openSheet(`<h3>Backup &amp; restore</h3><p class="hint">Keep your data safe — save it off the phone, or restore after a reinstall.</p>
      <div class="field"><label>PIN (optional — encrypts the backup)</label><input id="bkpin" class="input" inputmode="numeric" placeholder="leave blank for none"></div>
      <button class="btn primary" id="bkshare">📤 Backup &amp; share (Drive/WhatsApp)</button>
      <button class="btn" id="bksave" style="margin-top:10px">💾 Save to phone (Documents)</button>
      <button class="btn" id="bkrestore" style="margin-top:10px">♻ Restore from phone</button>
      <p class="dt" style="margin-top:12px">Auto-saved to the phone's Documents after each bill — that copy survives an app uninstall.</p>`,
      () => {
        const pin = () => ($("#bkpin").value || "").trim();
        $("#bkshare").onclick = async () => {
          try {
            const str = await B.makeBackupString(pin());
            const FS = P.Filesystem, SH = P.Share;
            if (FS && SH) { const w = await FS.writeFile({ path: "medivision-backup.json", data: str, directory: "CACHE", encoding: "utf8" }); await SH.share({ title: "MediVision backup", url: w.uri }); }
            else { try { navigator.clipboard.writeText(str); toast("Backup copied", "ok"); } catch (e) { toast("Backup ready (no share)", ""); } }
          } catch (e) { toast("Backup failed", "err"); }
        };
        $("#bksave").onclick = async () => { const ok = await B.saveToPhone(pin()); toast(ok ? "Saved to phone ✓" : "Save needs the update", ok ? "ok" : ""); };
        $("#bkrestore").onclick = async () => {
          const str = await B.readFromPhone();
          if (!str) return toast("No phone backup found", "err");
          try { const ok = await B.loadBackupString(str, pin()); if (ok) { buzz("Heavy"); toast("Restored ✓ — reloading", "ok"); setTimeout(() => location.reload(), 700); } else toast("Nothing to restore", ""); }
          catch (e) { toast(e.code === "PIN" ? "Enter the backup PIN" : "Restore failed", "err"); }
        };
      });
  }

  async function staffSheet() {
    const staff = await api("/api/staff");
    openSheet(`<h3>Who's using the till?</h3><p class="hint">Pick a staff member — their role controls what they can open.</p>
      ${staff.map(s => `<div class="row" data-st="${esc(s.id)}"><div class="meta"><div class="nm">${esc(s.name)}</div><div class="dt">${esc(s.role)}</div></div><div class="rt">${s.name === S.staffName ? '<span class="pill ok">active</span>' : '<span class="dt">tap</span>'}</div></div>`).join("")}
      <p class="dt" style="margin-top:10px">Add or remove staff in Admin (owner PIN).</p>`,
      () => {
        $("#modal-root").querySelectorAll("[data-st]").forEach(r => r.onclick = async () => { const as = await api("/api/active-staff", { method: "POST", body: { id: r.dataset.st } }); S.role = as.role || "Manager"; S.staffName = as.name || ""; try { await api("/api/attendance/clockin", { method: "POST", body: { staff_id: as.id || r.dataset.st, staff_name: as.name || S.staffName } }); } catch (e) {} closeSheet(); buzz("Medium"); toast("Now: " + S.staffName + " (" + S.role + ")", "ok"); go("home"); });
      });
  }

  // =================================================================
  //  REPORTS & INSIGHTS
  // =================================================================
  let repPeriod = 30;
  async function viewReports() {
    navEl.classList.remove("hide");
    if (!roleCan("reports")) return roleBlock("Reports");
    if (!can("bill")) return lockedView("Reports", "billing");
    app.innerHTML = `
      <div class="topbar"><h1>Reports</h1>
        <button class="btn" id="exp" style="width:auto;padding:0 14px;min-height:42px">⬇ Export</button></div>
      <div class="seg" id="per">
        ${[[7, "7 days"], [30, "30 days"], [0, "All"]].map(([d, l]) => `<button data-d="${d}" class="${repPeriod === d ? "on" : ""}">${l}</button>`).join("")}
      </div>
      <div id="rep">${skelRows(4)}</div>
      <div id="rep-cs"></div>`;
    app.querySelectorAll("#per button").forEach(b => b.onclick = () => { repPeriod = +b.dataset.d; viewReports(); });
    const data = await reportData(repPeriod);
    renderReport(data);
    $("#exp").onclick = () => exportReport(data);
    const rcs = $("#rep-cs");
    if (rcs) rcs.innerHTML = `
      <div class="sectitle" style="margin-top:6px">📈 Coming soon — Smart plan</div>
      <div class="card" style="opacity:.78">
        <div class="nm" style="margin-bottom:4px">Demand forecast &amp; reorder alerts</div>
        <div class="dt">Predict which medicines to reorder and when, based on your actual sales rhythm. Never run out of a fast-mover.</div>
        <div style="height:10px"></div>
        <div class="nm" style="margin-bottom:4px">Customer loyalty dashboard</div>
        <div class="dt">Top-customer leaderboard, monthly spend trends, automatic credit-reminder scheduling via WhatsApp or Twilio call.</div>
        <button class="btn" onclick="window.MV.toast('Smart plan — contact us to upgrade 🚀','')" style="margin-top:12px;width:auto;padding:0 18px">Learn more</button>
      </div>`;
  }
  async function reportData(days) {
    let bills = []; try { const r = await api("/api/bills"); bills = Array.isArray(r) ? r : (r.bills || []); } catch (e) {}
    const meds = S.medicines.length ? S.medicines : await loadMeds();
    const cutoff = days > 0 ? Date.now() - days * 86400000 : 0;
    const inP = bills.filter(b => (Date.parse(b.ts || b.date || "") || 0) >= cutoff);
    let sales = 0, n = 0; const sold = {};
    inP.forEach(b => {
      sales += Number(b.total) || 0; n++;
      let items = b.items; if (typeof items === "string") { try { items = JSON.parse(items); } catch (e) { items = []; } }
      (items || []).forEach(it => { const id = String(it.id || ""); const q = Number(it.qty) || 0; if (id) sold[id] = (sold[id] || 0) + q; });
    });
    const movers = meds.map(m => ({ m, q: sold[String(m.id)] || 0 })).filter(x => x.q > 0).sort((a, b) => b.q - a.q).slice(0, 10);
    const dead = meds.filter(m => Number(m.s) > 0 && !sold[String(m.id)]);
    const low = meds.filter(m => Number(m.s) <= Number(m.reorder || 0) && Number(m.reorder || 0) > 0);
    const exp = meds.filter(m => isExpiringSoon(m.expiry));
    return { days, sales, n, avg: n ? sales / n : 0, movers, dead, low, exp };
  }
  function renderReport(d) {
    const el = $("#rep"); if (!el) return;
    const kv = (l, v, cls = "") => `<div class="kpi${cls ? " " + cls : ""}"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    el.innerHTML = `
      <div class="kpis">
        ${kv("Sales (" + (d.days || "all") + "d)", money(d.sales), "green")}
        ${kv("Bills", d.n, "")}
        ${kv("Avg bill", money(d.avg), "")}
        ${kv("Low stock", d.low.length, d.low.length ? "red" : "")}
      </div>
      ${d.exp.length ? `<div class="card" style="margin-top:12px;border-color:var(--amber)"><div class="nm" style="color:var(--amber)">⚠ ${d.exp.length} items expiring in 90 days</div></div>` : ""}
      <div class="sectitle">Top movers</div>
      ${d.movers.length
        ? d.movers.map(({ m, q }) => `<div class="row"><div class="meta"><div class="nm">${esc(m.n)}</div><div class="dt">Sold ${q} units</div></div><div class="rt"><div class="price">${money(q * (Number(m.p) || 0))}</div></div></div>`).join("")
        : emptyBox("📊", "No sales yet", "Bills will appear here once you start billing.")}
      ${d.dead.length ? `<div class="sectitle">Dead stock (${d.dead.length} items)</div>${d.dead.slice(0, 5).map(m => `<div class="row"><div class="meta"><div class="nm">${esc(m.n)}</div><div class="dt">Qty ${m.s} · zero sales</div></div></div>`).join("")}` : ""}`;
  }
  function exportReport(d) {
    const lines = ["Name,Qty Sold,Revenue (INR)"];
    d.movers.forEach(({ m, q }) => lines.push('"' + (m.n || "").replace(/"/g, '""') + '",' + q + ',' + (q * (Number(m.p) || 0)).toFixed(2)));
    const csv = lines.join("\n");
    openSheet(`<h3>${d.days ? d.days + "-day" : "All-time"} report</h3>
      <p class="hint">Copy this CSV to paste into Excel / Google Sheets.</p>
      <textarea class="input" style="min-height:180px;font-family:monospace;font-size:11px;line-height:1.4" readonly>${esc(csv)}</textarea>
      <button class="btn primary" id="cpcopy" style="margin-top:12px">Copy CSV</button>
      <button class="btn" id="cpclose" style="margin-top:8px">Close</button>`,
      () => {
        $("#cpcopy").onclick = () => { try { navigator.clipboard.writeText(csv); } catch (e) { const ta = document.querySelector(".sheet textarea"); if (ta) { ta.select(); document.execCommand("copy"); } } toast("Copied ✓", "ok"); };
        $("#cpclose").onclick = closeSheet;
      });
  }

  // =================================================================
  //  HEARTBEAT → owner server
  // =================================================================
  async function sendHeartbeat() {
    const base = cfg.OWNER_BASE; if (!base) return;
    const key = window.MVLICENSE ? await window.MVLICENSE.getDeviceCode() : (cfg.SHOP_KEY || (S.me && S.me.name) || "demo");
    let todayBills = 0, sales = 0;
    try {
      const r = await api("/api/bills");
      const bills = Array.isArray(r) ? r : (r && r.bills ? r.bills : []);
      const today = new Date().toISOString().slice(0, 10);
      const tb = bills.filter(b => (b.date || "").startsWith(today));
      todayBills = tb.length;
      sales = tb.reduce((s, b) => s + (Number(b.total) || 0), 0);
    } catch (e) {}
    const low = S.medicines.filter(m => Number(m.s) <= Number(m.reorder || 0) && Number(m.reorder || 0) > 0).length;
    const exp = S.medicines.filter(m => isExpiringSoon(m.expiry)).length;
    try {
      const r = await fetch(base + "/api/heartbeat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shop_key: key, name: (S.setup && S.setup.shopName) || (S.me && S.me.name) || key, plan: S.planKey, app_version: "0.1", today_bills: todayBills, today_sales: sales, stock_count: S.medicines.length, alerts: low + exp }),
      });
      const j = await r.json().catch(() => ({}));
      if (window.MVSYNC) window.MVSYNC.updateStatus(true, j && j.license);
      if (window.MVLICENSE) {
        const gate = await window.MVLICENSE.evaluateServerResult(true, j && j.license);
        if (!gate.ok) window.MVLICENSE.lockApp(gate);
      }
    } catch (e) {
      if (window.MVSYNC) window.MVSYNC.updateStatus(false, null);
      if (window.MVLICENSE) {
        const gate = await window.MVLICENSE.evaluateServerResult(false, null);
        if (!gate.ok) window.MVLICENSE.lockApp(gate);
      }
    }
  }

  // =================================================================
  //  BOOT
  // =================================================================
  async function boot() {
    // Load shop setup (name, GST, licence etc.) immediately so topbar shows real name
    if (window.MVSETUP) S.setup = window.MVSETUP.load();
    const saved = await store.get("mv_api"); if (saved) S.apiBase = saved;
    // planKey stays "max" — feature tiers are no longer client-enforced, subscription is gated server-side
    const th = await store.get("mv_theme"); if (th) S.theme = th; applyTheme();
    const hd = await store.get("mv_held"); if (hd) { try { S.held = JSON.parse(hd) || []; } catch (e) {} }
    const eq = await store.get("mv_enq"); if (eq) { try { S.enquiries = JSON.parse(eq) || []; } catch (e) {} }
    const lc = await store.get("mv_loc"); if (lc) { try { S.loc = JSON.parse(lc) || {}; } catch (e) {} }
    S.upiQr = (await store.get("mv_upi_qr")) || "";
    const co = await store.get("mv_cash_open"); if (co) { try { S.cashOpen = JSON.parse(co) || S.cashOpen; } catch (e) {} }
    try {
      const me = await api("/api/portal/me");
      S.me = { name: me.name, type: me.type };
      try { const as = await api("/api/active-staff"); if (as) { S.role = as.role || "Manager"; S.staffName = as.name || ""; } } catch (e) {}
      await loadMeds();
      try { S.staff = await api("/api/staff") || []; } catch (e) { S.staff = []; }
      go("home");
      sendHeartbeat();
    } catch (e) {
      viewLogin();
    }
  }
  setInterval(() => { if (S.me) sendHeartbeat(); }, 120000);

  // Apply setup data without full reload (called from setup-ui.js after save)
  function applySetup(data) { S.setup = data || {}; }

  // Android hardware back button
  document.addEventListener("backbutton", () => {
    if (document.querySelector(".sheet-bg")) { closeSheet(); return; }
    if (S.tab !== "home") { go("home"); return; }
  }, false);

  // ---------- global API exposed to other modules ----------
  window.MV = { go, toast, api, nav: navEl, _applySetup: applySetup };

  // ---------- Capacitor device ready ----------
  const bootGated = () => (window.MVLICENSE ? window.MVLICENSE.guard(boot) : boot());
  document.addEventListener("deviceready", bootGated, false);
  // Fallback: browser / dev mode (deviceready never fires outside Capacitor)
  if (!Cap || !Cap.isNativePlatform || !Cap.isNativePlatform()) bootGated();
})();
