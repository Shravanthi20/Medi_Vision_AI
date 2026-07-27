/* ===================================================================
   MediVision Mobile — Device License Lock (Stage: mobile anti-piracy)
   Self-contained; loads BEFORE app.js and gates app.js's boot().

   Model (mirrors app.py's desktop license, adapted for a 30-day cycle):
   - Each phone gets a persistent DEVICE CODE (random UUID, stored once).
   - Vendor runs `python mobile_activate.py <DEVICE-CODE> [--days 30]`
     (repo root) to issue an UNLOCK CODE good until an expiry date.

   TWO code formats are understood, checked in this order:

   1. SIGNED (current, recommended) — "<YYYYMMDD>.<base64url ECDSA sig>".
      The vendor tool signs `${deviceCode}|${YYYYMMDD}` with a private
      ECDSA P-256 key that NEVER ships anywhere near the app. Only the
      matching PUBLIC key is embedded below, used solely to verify.
      A decompiled APK reveals the public key, which is useless for
      forging new codes — this is real asymmetric crypto, not a shared
      secret. Codes are long (~95 chars) and meant to be copy-pasted
      from WhatsApp/SMS, not hand-typed.

   2. LEGACY (kept only so already-issued codes don't break) —
      "<YYYYMMDD>-<HASH4>-<HASH4>", HASH = SHA-256(deviceCode|YYYYMMDD|
      OWNER_SECRET)[:8]. This used a shared secret baked into the JS
      bundle, which a determined attacker COULD extract from the APK
      and use to self-issue codes forever. `mobile_activate.py` no
      longer issues this format — it only still verifies here for
      phones activated before the signed scheme existed.

   On every boot the app re-verifies the stored code against whichever
   scheme it matches; a failed or past-due code re-locks the app and
   shows the device code again for renewal.
   =================================================================== */
(() => {
  "use strict";

  // Public half of the vendor's ECDSA P-256 signing key. Generated once by
  // mobile_signing_key.pem (private, never committed — see .gitignore).
  // To rotate: regenerate the keypair, update this JWK, reissue all codes.
  const PUBLIC_KEY_JWK = {
    kty: "EC", crv: "P-256",
    x: "e8j_iapL-phYmX0H3AgvWd6LUAL4oSPAxoKeVvATJVk",
    y: "l5BjKpnSC5urHI-8kE_nTzTQF-Ukjxl3Vnt3q10_UE8",
  };
  // Legacy-format verification only — must match OWNER_SECRET in the old
  // mobile_activate.py history. New codes are never issued with this.
  const OWNER_SECRET = "SELVAM-MEDIVISION-MOBILE-2026";
  // First install: allow the app to run this many days before requiring activation.
  const FIRST_RUN_GRACE_DAYS = 3;
  // How long the app may run on a CACHED "active" server status if the VPS
  // can't be reached (Wi-Fi blip, VPS restart). Beyond this, no connection = locked.
  const SERVER_GRACE_MS = 12 * 60 * 1000;
  const SERVER_FETCH_TIMEOUT_MS = 7000;

  const Cap = window.Capacitor || null;
  const P = (Cap && Cap.Plugins) || {};

  const store = {
    async get(k) {
      try { if (P.Preferences) return (await P.Preferences.get({ key: k })).value; } catch (e) {}
      return localStorage.getItem(k);
    },
    async set(k, v) {
      try { if (P.Preferences) return void (await P.Preferences.set({ key: k, value: v })); } catch (e) {}
      localStorage.setItem(k, v);
    }
  };

  async function sha256Hex(str) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
  }

  function todayYYYYMMDD() {
    const d = new Date();
    return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  }

  function groupDeviceCode(hex16) {
    return hex16.toUpperCase().match(/.{1,4}/g).join("-");
  }

  async function getDeviceCode() {
    let uuid = await store.get("mv_device_uuid");
    if (!uuid) {
      uuid = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
      await store.set("mv_device_uuid", uuid);
    }
    const hex = (await sha256Hex(uuid)).slice(0, 16);
    return groupDeviceCode(hex);
  }

  // ── legacy (shared-secret) format — verify only, never issued anymore ──
  async function computeLegacyCode(deviceCode, expiryYYYYMMDD) {
    const raw = `${deviceCode}|${expiryYYYYMMDD}|${OWNER_SECRET}`;
    const hash4 = (await sha256Hex(raw)).slice(0, 8).toUpperCase();
    return `${expiryYYYYMMDD}-${hash4.slice(0, 4)}-${hash4.slice(4, 8)}`;
  }

  function parseLegacyCode(code) {
    const m = String(code || "").trim().toUpperCase().match(/^(\d{8})-([0-9A-F]{4})-([0-9A-F]{4})$/);
    if (!m) return null;
    return { expiry: m[1], hash: m[2] + m[3] };
  }

  // ── signed (ECDSA P-256) format — the real license scheme ──────────────
  function parseSignedCode(code) {
    const m = String(code || "").trim().match(/^(\d{8})\.([A-Za-z0-9_-]{80,90})$/);
    if (!m) return null;
    return { expiry: m[1], sig: m[2] };
  }

  function b64urlToBytes(b64url) {
    const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(b64url.length / 4) * 4, "=");
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  let _pubKeyPromise = null;
  function importPublicKey() {
    if (!_pubKeyPromise) {
      _pubKeyPromise = crypto.subtle.importKey(
        "jwk", PUBLIC_KEY_JWK, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]
      );
    }
    return _pubKeyPromise;
  }

  async function verifySignedCode(deviceCode, expiryYYYYMMDD, sigB64url) {
    try {
      const key = await importPublicKey();
      const sig = b64urlToBytes(sigB64url);
      const msg = new TextEncoder().encode(`${deviceCode}|${expiryYYYYMMDD}`);
      return await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, key, sig, msg);
    } catch (e) {
      return false;
    }
  }

  function expiryToDate(yyyymmdd) {
    return new Date(`${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}T23:59:59`);
  }

  // Returns { valid, reason, deviceCode, expiry, daysLeft }
  async function checkLicense() {
    const deviceCode = await getDeviceCode();
    const savedCode = await store.get("mv_lic_code");

    if (!savedCode) {
      let firstRun = await store.get("mv_first_run_ts");
      if (!firstRun) {
        firstRun = String(Date.now());
        await store.set("mv_first_run_ts", firstRun);
      }
      const elapsedDays = (Date.now() - Number(firstRun)) / 86400000;
      if (elapsedDays < FIRST_RUN_GRACE_DAYS) {
        return { valid: true, reason: "grace", deviceCode, expiry: null, daysLeft: Math.ceil(FIRST_RUN_GRACE_DAYS - elapsedDays) };
      }
      return { valid: false, reason: "not_activated", deviceCode, expiry: null, daysLeft: 0 };
    }

    const signed = parseSignedCode(savedCode);
    if (signed) {
      const ok = await verifySignedCode(deviceCode, signed.expiry, signed.sig);
      if (!ok) return { valid: false, reason: "tampered", deviceCode, expiry: signed.expiry, daysLeft: 0 };
      const daysLeft = Math.ceil((expiryToDate(signed.expiry) - Date.now()) / 86400000);
      if (daysLeft < 0) return { valid: false, reason: "expired", deviceCode, expiry: signed.expiry, daysLeft: 0 };
      return { valid: true, reason: "ok", deviceCode, expiry: signed.expiry, daysLeft };
    }

    const legacy = parseLegacyCode(savedCode);
    if (!legacy) return { valid: false, reason: "invalid_format", deviceCode, expiry: null, daysLeft: 0 };
    const expected = await computeLegacyCode(deviceCode, legacy.expiry);
    if (expected !== savedCode.trim().toUpperCase()) return { valid: false, reason: "tampered", deviceCode, expiry: legacy.expiry, daysLeft: 0 };
    const daysLeft = Math.ceil((expiryToDate(legacy.expiry) - Date.now()) / 86400000);
    if (daysLeft < 0) return { valid: false, reason: "expired", deviceCode, expiry: legacy.expiry, daysLeft: 0 };
    return { valid: true, reason: "ok", deviceCode, expiry: legacy.expiry, daysLeft };
  }

  async function activate(deviceCode, enteredCode) {
    const raw = String(enteredCode || "").trim();

    const signed = parseSignedCode(raw);
    if (signed) {
      const ok = await verifySignedCode(deviceCode, signed.expiry, signed.sig);
      if (!ok) return { ok: false, error: "That code doesn't match this device." };
      if (expiryToDate(signed.expiry) < new Date()) return { ok: false, error: "That code has already expired. Ask for a fresh one." };
      await store.set("mv_lic_code", raw);
      return { ok: true };
    }

    const legacy = parseLegacyCode(raw);
    if (!legacy) return { ok: false, error: "Code format looks wrong. Paste it exactly as sent." };
    const expected = await computeLegacyCode(deviceCode, legacy.expiry);
    if (expected !== raw.toUpperCase()) return { ok: false, error: "That code doesn't match this device." };
    if (expiryToDate(legacy.expiry) < new Date()) return { ok: false, error: "That code has already expired. Ask for a fresh one." };
    await store.set("mv_lic_code", expected);
    return { ok: true };
  }

  function fmtExpiry(yyyymmdd) {
    if (!yyyymmdd) return "";
    return `${yyyymmdd.slice(6, 8)}/${yyyymmdd.slice(4, 6)}/${yyyymmdd.slice(0, 4)}`;
  }

  function renderLock(container, info, errorMsg) {
    const reasonText = {
      not_activated: "This phone is not activated yet.",
      expired: `Your license expired on ${fmtExpiry(info.expiry)}.`,
      tampered: "This unlock code isn't valid for this device.",
      invalid_format: "Enter the unlock code exactly as given to you.",
    }[info.reason] || "Activation required.";

    container.innerHTML = `
      <div class="lock" style="padding-top:8vh">
        <div class="e">🔒</div>
        <h2>Activation required</h2>
        <p>${reasonText} Send the Device Code below to MediVision AI support; you'll receive an unlock code good for the next billing cycle.</p>
        <div class="field" style="text-align:left">
          <label>Step 1 — Send this Device Code</label>
          <div style="display:flex;gap:8px">
            <input id="lic_dc" class="input" value="${info.deviceCode}" readonly style="font-weight:700;letter-spacing:1px">
            <button class="btn" id="lic_copy" style="white-space:nowrap;padding:0 16px;border:1px solid var(--line);border-radius:12px">Copy</button>
          </div>
        </div>
        <div class="field" style="text-align:left">
          <label>Step 2 — Paste the unlock code you receive</label>
          <div style="display:flex;gap:8px">
            <input id="lic_code" class="input" placeholder="Paste code here (WhatsApp/SMS)" autocapitalize="off" autocorrect="off" spellcheck="false" autocomplete="off">
            <button class="btn" id="lic_paste" style="white-space:nowrap;padding:0 16px;border:1px solid var(--line);border-radius:12px">Paste</button>
          </div>
        </div>
        <div id="lic_err" style="color:var(--red);font-size:13.5px;min-height:18px;margin-bottom:8px">${errorMsg || ""}</div>
        <button class="btn primary" id="lic_go" style="width:100%">Activate this phone</button>
      </div>`;

    const $ = (s) => container.querySelector(s);
    $("#lic_copy").onclick = async () => {
      try { await navigator.clipboard.writeText(info.deviceCode); $("#lic_copy").textContent = "Copied"; setTimeout(() => { $("#lic_copy").textContent = "Copy"; }, 1200); } catch (e) {}
    };
    $("#lic_paste").onclick = async () => {
      try { $("#lic_code").value = (await navigator.clipboard.readText()).trim(); } catch (e) { /* clipboard read denied — user can paste manually */ }
    };
    $("#lic_go").onclick = async () => {
      const entered = $("#lic_code").value;
      const res = await activate(info.deviceCode, entered);
      if (!res.ok) { $("#lic_err").textContent = res.error; return; }
      location.reload();
    };
  }

  // ===================================================================
  //  SERVER GATE — owner VPS (owner/owner_server.py) is the monthly
  //  lock/unlock authority. Rules (per product decision):
  //   - VPS reachable + "active"    -> allowed
  //   - VPS reachable + "suspended" -> LOCKED immediately, no grace
  //   - VPS unreachable             -> allowed only within SERVER_GRACE_MS
  //     of the last confirmed "active" check-in; otherwise LOCKED.
  //     (A cached "suspended" also blocks outright while offline —
  //     losing connectivity is never a way to bypass a suspension.)
  //   - OWNER_BASE not configured (dev/local mode) -> gate is a no-op.
  // ===================================================================
  function ownerBase() {
    const cfg = window.MV_CONFIG || {};
    return (cfg.OWNER_BASE || "").replace(/\/$/, "");
  }

  async function fetchWithTimeout(url, opts, ms) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), ms);
    try { return await fetch(url, Object.assign({}, opts, { signal: ctrl.signal })); }
    finally { clearTimeout(t); }
  }

  async function pingServer(deviceCode) {
    const base = ownerBase();
    try {
      const r = await fetchWithTimeout(`${base}/api/license?shop_key=${encodeURIComponent(deviceCode)}`, {}, SERVER_FETCH_TIMEOUT_MS);
      const j = await r.json();
      return { reachable: true, license: (j && j.license) || "active" };
    } catch (e) {
      return { reachable: false, license: null };
    }
  }

  // Records a check-in result (from either the boot-time ping or app.js's
  // running heartbeat) and returns the resulting gate decision.
  async function evaluateServerResult(reachable, license) {
    const deviceCode = await getDeviceCode();
    const base = ownerBase();
    if (!base) return { ok: true, reason: "not_configured", deviceCode };

    if (reachable) {
      license = license || "active";
      await store.set("mv_srv_status", license);
      await store.set("mv_srv_last_check_ts", String(Date.now()));
      if (license === "active") await store.set("mv_srv_last_ok_ts", String(Date.now()));
      if (license === "suspended") return { ok: false, reason: "suspended", deviceCode };
      return { ok: true, reason: "online", deviceCode };
    }

    const lastStatus = await store.get("mv_srv_status");
    if (lastStatus === "suspended") return { ok: false, reason: "suspended", deviceCode };
    const lastOkTs = Number((await store.get("mv_srv_last_ok_ts")) || 0);
    if (lastOkTs && (Date.now() - lastOkTs) < SERVER_GRACE_MS) {
      return { ok: true, reason: "offline_grace", deviceCode, graceMsLeft: SERVER_GRACE_MS - (Date.now() - lastOkTs) };
    }
    return { ok: false, reason: "offline", deviceCode };
  }

  async function checkServerGate(deviceCode) {
    const base = ownerBase();
    if (!base) return { ok: true, reason: "not_configured", deviceCode };
    const res = await pingServer(deviceCode);
    return evaluateServerResult(res.reachable, res.license);
  }

  function renderServerLock(container, srv) {
    const copy = {
      suspended: {
        icon: "⏸️", title: "Subscription paused",
        msg: "Your MediVision subscription is on hold. Contact us to reactivate — the app unlocks automatically the moment you're back online.",
      },
      offline: {
        icon: "📶", title: "No connection",
        msg: "Can't verify your subscription — no connection to the license server. Connect to Wi-Fi or mobile data and try again.",
      },
    }[srv.reason] || { icon: "📶", title: "Can't verify subscription", msg: "Please connect to the internet and try again." };

    container.innerHTML = `
      <div class="lock" style="padding-top:16vh">
        <div class="e">${copy.icon}</div>
        <h2>${copy.title}</h2>
        <p>${copy.msg}</p>
        <div class="dt" style="margin:10px 0 18px;font-size:12px;opacity:.7">Device: ${srv.deviceCode || ""}</div>
        <button class="btn primary" id="srv_retry" style="width:100%">Retry</button>
      </div>`;
    const b = container.querySelector("#srv_retry");
    if (b) b.onclick = () => location.reload();
  }

  // Locks the currently-running app immediately (used by app.js's live
  // heartbeat loop when a suspension/offline-timeout is detected mid-session).
  function lockApp(srv) {
    const appEl = document.getElementById("app");
    const navEl = document.getElementById("nav");
    if (navEl) navEl.classList.add("hide");
    if (appEl) renderServerLock(appEl, srv);
  }

  // Entry point: check local device license + server subscription gate;
  // if both pass, run bootFn(), else render the appropriate lock screen.
  async function guard(bootFn) {
    const appEl = document.getElementById("app");
    const navEl = document.getElementById("nav");
    const info = await checkLicense();
    if (!info.valid) {
      if (navEl) navEl.classList.add("hide");
      if (appEl) renderLock(appEl, info);
      return;
    }
    const srv = await checkServerGate(info.deviceCode);
    if (!srv.ok) {
      if (navEl) navEl.classList.add("hide");
      if (appEl) renderServerLock(appEl, srv);
      return;
    }
    if (info.reason === "grace") {
      setTimeout(() => { try { window.MV && window.MV.toast && window.MV.toast(`Activation needed in ${info.daysLeft}d`, "warn"); } catch (e) {} }, 1500);
    }
    return bootFn();
  }

  window.MVLICENSE = { checkLicense, guard, getDeviceCode, evaluateServerResult, lockApp };
})();
