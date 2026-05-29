/* ═══════════════════════════════════════════════════════════
   supplier-manufacturer.js
═══════════════════════════════════════════════════════════ */

const footerDescriptions = {
  'Add':     'Add New Supplier & Manufacturer',
  'Modify':  'Modify Supplier & Manufacturer',
  'Delete':  'Delete Supplier & Manufacturer',
  'View':    'View Supplier & Manufacturer',
  'Go To':   'Go To Supplier & Manufacturer',
  'Next':    'Next Supplier & Manufacturer',
  'Prior':   'Previous Supplier & Manufacturer',
  'Options': 'Supplier & Manufacturer Setup',
  'Exit':    'Exit screen?'
};

const DEFAULT_HELPER = 'Supplier & Manufacturer Setup';

const fieldIds = ['supplierCode', 'mfrCode'];
const fieldElements = {};

/* ── MFR NAME LOOKUP (stub — wire to backend) ── */

var mfrLookup = {
  // example: '001': 'ARAVIND REMEDIES(P) LTD'
};

function lookupMfrName(code) {
  return mfrLookup[code.trim().toUpperCase()] || '';
}

function updateMfrName(val) {
  var nameEl = document.getElementById('mfrName');
  if (!nameEl) return;
  var name = lookupMfrName(val);
  nameEl.textContent = name;
  if (name) {
    nameEl.classList.add('visible');
  } else {
    nameEl.classList.remove('visible');
  }
}

/* ── FOOTER ACTION HANDLER ── */

function handleAction(name) {
  switch (name) {
    case 'Add':
      clearForm();
      focusFirst();
      break;

    case 'Modify': {
      const code = fieldElements['supplierCode'] && fieldElements['supplierCode'].value;
      if (!code) { alert('Please enter Supplier Code to modify'); focusFirst(); }
      break;
    }

    case 'Delete': {
      const code = fieldElements['supplierCode'] && fieldElements['supplierCode'].value;
      if (!code) { alert('Please enter Supplier Code to delete'); focusFirst(); return; }
      if (confirm('Delete this supplier?')) { clearForm(); focusFirst(); }
      break;
    }

    case 'View': {
      const code = fieldElements['supplierCode'] && fieldElements['supplierCode'].value;
      if (!code) { alert('Please enter Supplier Code to view'); focusFirst(); }
      break;
    }

    case 'Go To':   focusFirst(); break;
    case 'Next':    break;
    case 'Prior':   break;
    case 'Options': break;

    case 'Exit':
      if (confirm('Exit this page?')) window.history.back();
      break;
  }
}

/* ── HELPER TEXT ── */

function initHelperText() {
  var helperEl = document.getElementById('footerHelperText');
  if (!helperEl) return;

  document.querySelectorAll('.action-btn').forEach(function(btn) {
    var label = btn.textContent.trim();
    btn.addEventListener('mouseenter', function() {
      helperEl.textContent = footerDescriptions[label] || DEFAULT_HELPER;
    });
    btn.addEventListener('mouseleave', function() {
      helperEl.textContent = DEFAULT_HELPER;
    });
  });
}

/* ── MAIN PANEL BLUE OUTLINE — 1 second flash ── */

function initPanelGlow() {
  var mainPanel = document.getElementById('mainPanel');
  if (!mainPanel) return;
  var panelTimer = null;

  document.querySelectorAll('.sm-input').forEach(function(inp) {
    inp.addEventListener('focus', function() {
      mainPanel.classList.add('panel-active');
      if (panelTimer) clearTimeout(panelTimer);
      panelTimer = setTimeout(function() {
        mainPanel.classList.remove('panel-active');
      }, 1000);
    });
  });
}

/* ── FORM HELPERS ── */

function focusFirst() {
  var el = fieldElements['supplierCode'];
  if (el) el.focus();
}

function clearForm() {
  fieldIds.forEach(function(id) {
    if (fieldElements[id]) fieldElements[id].value = '';
  });
  updateMfrName('');
}

/* ── INIT ── */

function init() {
  fieldIds.forEach(function(id, idx) {
    var el = document.getElementById(id);
    if (!el) return;
    fieldElements[id] = el;

    el.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var next = fieldElements[fieldIds[idx + 1]];
        if (next) next.focus();
      }
    });

    // Live mfr name lookup on mfrCode input
    if (id === 'mfrCode') {
      el.addEventListener('input', function() {
        updateMfrName(el.value);
      });
    }
  });

  initHelperText();
  initPanelGlow();
  focusFirst();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}