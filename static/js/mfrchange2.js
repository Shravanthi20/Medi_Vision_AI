/* ═══════════════════════════════════════════════════════════
   mfr_change_detail.js  —  Mfr / Location Change Detail
   Includes: clock/date tick, label switching, real-time sync,
             Y/N confirm toggle, footer actions
═══════════════════════════════════════════════════════════ */

/* ── CLOCK & DATE ─────────────────────────────────────── */
(function () {
  var DAYS = ['Sunday','Monday','Tuesday','Wednesday',
              'Thursday','Friday','Saturday'];

  function pad(n) { return String(n).padStart(2, '0'); }

  function tick() {
    var now     = new Date();
    var clockEl = document.getElementById('clock');
    var dateEl  = document.getElementById('date-val');
    var dayEl   = document.getElementById('day-val');

    if (clockEl)
      clockEl.textContent =
        pad(now.getHours())   + ':' +
        pad(now.getMinutes()) + ':' +
        pad(now.getSeconds());

    if (dateEl)
      dateEl.textContent =
        pad(now.getDate()) + '/' +
        pad(now.getMonth() + 1) + '/' +
        now.getFullYear();

    if (dayEl)
      dayEl.textContent = DAYS[now.getDay()];
  }

  tick();
  setInterval(tick, 1000);
}());


/* ── LABEL CONFIG ─────────────────────────────────────── */
/*
  When this page is reached via "NEXT" from mfrchange.html the
  selection (Manufacturer / Location / Supplier) should be passed
  via URL param or sessionStorage.  We read it here and adapt ALL
  labels accordingly.
*/

var MCD_TYPE_MAP = {
  'Manufacturer': 'Mfr.',
  'Location':     'Location',
  'Supplier':     'Supplier'
};

/* Read selection from sessionStorage (set by mfrchange.js on NEXT) */
var mcdChangeType  = sessionStorage.getItem('mlcSelectedValue') || 'Manufacturer';
var mcdShortLabel  = MCD_TYPE_MAP[mcdChangeType] || 'Mfr.';
var mcdConfirm     = 'No';   /* default */

function mcdApplyLabels() {
  /* Breadcrumb */
  var bc = document.getElementById('breadcrumbCurrent');
  if (bc) bc.textContent = mcdChangeType + ' Change';

  /* Section 1 static chip */
  var chip = document.getElementById('staticChangeType');
  if (chip) chip.textContent = mcdChangeType;

  /* Section 1 input labels */
  var lFrom = document.getElementById('labelFrom');
  var lTo   = document.getElementById('labelTo');
  if (lFrom) lFrom.textContent = 'Change ' + mcdShortLabel + ' From';
  if (lTo)   lTo.textContent   = 'Change ' + mcdShortLabel + ' To';

  /* Section 2 summary labels */
  var sFrom = document.getElementById('summaryLabelFrom');
  var sTo   = document.getElementById('summaryLabelTo');
  if (sFrom) sFrom.textContent = 'Change ' + mcdShortLabel + ' From';
  if (sTo)   sTo.textContent   = 'Change ' + mcdShortLabel + ' To';
}


/* ── REAL-TIME SYNC ───────────────────────────────────── */
function mcdSyncValues() {
  var fromVal = (document.getElementById('inputFrom').value || '').trim();
  var toVal   = (document.getElementById('inputTo').value   || '').trim();

  var sumFrom = document.getElementById('summaryFrom');
  var sumTo   = document.getElementById('summaryTo');

  if (sumFrom) {
    sumFrom.textContent = fromVal || '—';
    sumFrom.classList.toggle('has-value', fromVal.length > 0);
  }
  if (sumTo) {
    sumTo.textContent = toVal || '—';
    sumTo.classList.toggle('has-value', toVal.length > 0);
  }
}

function mcdBindInputs() {
  var inputFrom = document.getElementById('inputFrom');
  var inputTo   = document.getElementById('inputTo');
  if (inputFrom) inputFrom.addEventListener('input', mcdSyncValues);
  if (inputTo)   inputTo.addEventListener('input',   mcdSyncValues);
}


/* ── YES / NO TOGGLE ──────────────────────────────────── */
function mcdSetConfirm(choice) {
  mcdConfirm = choice;

  var yesBtn = document.getElementById('yesBtn');
  var noBtn  = document.getElementById('noBtn');

  if (!yesBtn || !noBtn) return;

  if (choice === 'Yes') {
    /* YES active */
    yesBtn.classList.remove('mcd-yes-inactive');
    yesBtn.classList.add('mcd-yes-active');
    /* NO inactive */
    noBtn.classList.remove('mcd-no-active');
    noBtn.classList.add('mcd-no-inactive');
  } else {
    /* NO active */
    noBtn.classList.remove('mcd-no-inactive');
    noBtn.classList.add('mcd-no-active');
    /* YES inactive */
    yesBtn.classList.remove('mcd-yes-active');
    yesBtn.classList.add('mcd-yes-inactive');
  }

  console.log('Confirm choice:', mcdConfirm);
}


/* ── FOOTER ACTION ────────────────────────────────────── */
function handleDetailAction(name) {
  if (name === 'Next') {
    var fromVal = (document.getElementById('inputFrom').value || '').trim();
    var toVal   = (document.getElementById('inputTo').value   || '').trim();
    if (!fromVal || !toVal) {
      alert('Please fill in both "From" and "To" fields before proceeding.');
      return;
    }
    if (mcdConfirm !== 'Yes') {
      alert('Please select "Yes" to confirm the change.');
      return;
    }
    console.log('Proceed with', mcdChangeType, 'change:', fromVal, '→', toVal);
    alert('Change confirmed: ' + mcdChangeType + ' | ' + fromVal + ' → ' + toVal);
    return;
  }

  if (name === 'Prior') {
    window.history.back();
    return;
  }

  if (name === 'Go To') {
    document.getElementById('inputFrom').focus();
    return;
  }

  if (name === 'Exit') {
    if (confirm('Exit?')) window.close();
    return;
  }

  console.log('Action:', name);
}


/* ── INIT ─────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  mcdApplyLabels();
  mcdBindInputs();
  /* Set default NO active visual */
  mcdSetConfirm('No');
});