/* ═══════════════════════════════════════════════════════════
   wanted-manual.js
   ⚠️  Clock, date, panel-active border → sidebar-header.js
       This file handles ONLY wanted-manual page logic.
═══════════════════════════════════════════════════════════ */


/* ── FOOTER handleAction ──────────────────────────────────
   Routes each footer button.
   Extend cases as backend pages become ready.
─────────────────────────────────────────────────────────── */
function handleAction(name) {
  switch (name) {

    case 'Add':
      clearForm();
      focusFirst();
      break;

    case 'View':
      console.log('Action: View');
      break;

    case 'Go To':
      focusFirst();
      break;

    case 'Next':
      /* Extend: load next record */
      console.log('Action: Next');
      break;

    case 'Prior':
      /* Extend: load previous record */
      console.log('Action: Prior');
      break;

    case 'Exit':
      if (confirm('Exit this page?')) window.history.back();
      break;

    default:
      console.log('Action:', name);
  }
}


/* ── HELPERS ──────────────────────────────────────────── */
function focusFirst() {
  var el = document.getElementById('serialNumber');
  if (el) el.focus();
}

function clearForm() {
  ['serialNumber', 'wantedDate', 'itemCode',
   'quantity', 'supplier', 'wantedTF'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.value = '';
  });
}


/* ── KEYBOARD NAV  (Enter / Tab moves to next field) ─── */
(function () {
  var fields = ['serialNumber', 'wantedDate', 'itemCode',
                'quantity', 'supplier', 'wantedTF'];

  fields.forEach(function (id, i) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var next = document.getElementById(fields[i + 1]);
        if (next) next.focus();
      }
    });
  });
}());


/* ── WANTED DATE  — attach date picker here ──────────── */
(function () {
  var dateField = document.getElementById('wantedDate');
  if (!dateField) return;

  /* Uncomment when Flatpickr is available:
  flatpickr(dateField, { dateFormat: 'd/m/Y', allowInput: true });
  */
}());

function handleAction(name) {
  if (name === 'Add')    { clearForm(); focusFirst(); return; }
  if (name === 'Go To')  { focusFirst(); return; }
  if (name === 'Exit')   { if (confirm('Exit?')) window.close(); return; }
  /* View / Next / Prior / Modify / Delete → extend when backend ready */
  console.log('Action:', name);
}
 
 
/* ── HELPERS ──────────────────────────────────────────── */
function focusFirst() {
  var el = document.getElementById('serialNumber');
  if (el) el.focus();
}
 
function clearForm() {
  ['serialNumber', 'wantedDate', 'itemCode',
   'quantity', 'supplier', 'wantedTF'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.value = '';
  });
}
 
 
/* ── KEYBOARD NAV  (Enter moves to next field) ─────────── */
(function () {
  var fields = ['serialNumber', 'wantedDate', 'itemCode',
                'quantity', 'supplier', 'wantedTF'];
 
  fields.forEach(function (id, i) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var next = document.getElementById(fields[i + 1]);
        if (next) next.focus();
      }
    });
  });
}());
 
 
/* ── WANTED DATE  — attach date picker here ──────────── */
(function () {
  var dateField = document.getElementById('wantedDate');
  if (!dateField) return;
 
  /* Uncomment when Flatpickr is available:
  flatpickr(dateField, { dateFormat: 'd/m/Y', allowInput: true });
  */
}());