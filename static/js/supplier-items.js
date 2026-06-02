/* ═══════════════════════════════════════════════════════════
   supplier-items.js
═══════════════════════════════════════════════════════════ */

const footerDescriptions = {
  'Add':     'Add New Supplier & Items',
  'Modify':  'Modify Supplier & Items',
  'Delete':  'Delete Supplier & Items',
  'View':    'View Supplier & Items',
  'Go To':   'Go To Supplier & Items',
  'Next':    'Next Supplier & Items',
  'Prior':   'Previous Supplier & Items',
  'Options': 'Supplier & Items Setup',
  'Exit':    'Exit screen?'
};

const DEFAULT_HELPER = 'Supplier & Items Setup';

const fieldIds = [
  'serialNo', 'supplierCode',
  'ourItem',  'ourMfr',  'ourPack',
  'supplierItem', 'supplierMfr', 'supplierPack'
];

const fieldElements = {};

/* ── FOOTER ACTION HANDLER ── */

function handleAction(name) {
  switch (name) {
    case 'Add':
      clearForm(); focusFirst(); break;

    case 'Modify': {
      const code = fieldElements['supplierCode'] && fieldElements['supplierCode'].value;
      if (!code) { alert('Please enter Supplier Code to modify'); focusFirst(); }
      break;
    }
    case 'Delete': {
      const code = fieldElements['supplierCode'] && fieldElements['supplierCode'].value;
      if (!code) { alert('Please enter Supplier Code to delete'); focusFirst(); return; }
      if (confirm('Delete this entry?')) { clearForm(); focusFirst(); }
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

/* ── PANEL GLOW — 1 second flash ── */

function initPanelGlow() {
  var mainPanel = document.getElementById('mainPanel');
  if (!mainPanel) return;
  var panelTimer = null;
  document.querySelectorAll('.si-input').forEach(function(inp) {
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
  var el = fieldElements['serialNo'];
  if (el) el.focus();
}

function clearForm() {
  fieldIds.forEach(function(id) {
    if (fieldElements[id]) fieldElements[id].value = '';
  });
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
  });

  initPanelGlow();
  focusFirst();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}