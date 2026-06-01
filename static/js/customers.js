/* ═══════════════════════════════════════════════════════════
   customers.js
═══════════════════════════════════════════════════════════ */

const footerDescriptions = {
  'Add':     'Add New Customer',
  'Modify':  'Modify Customer',
  'Delete':  'Delete Customer',
  'View':    'View Customer',
  'Go To':   'Go To Customer',
  'Next':    'Next Customer',
  'Prior':   'Previous Customer',
  'Options': 'Customer Setup',
  'Exit':    'Exit screen?'
};

const DEFAULT_HELPER = 'Customer Setup';

const fieldIds = [
  'customerCode',
  'customerName',
  'address',
  'openingBal',
  'mobileNo',
  'allowBills',
  'gstinNo',
  'balanceAmount',
  'discount'
];

const fieldElements = {};

/* ── FOOTER ACTION HANDLER ── */

function handleAction(name) {
  switch (name) {
    case 'Add':
      clearForm();
      focusFirst();
      break;

    case 'Modify': {
      const code = fieldElements['customerCode'] && fieldElements['customerCode'].value;
      if (!code) { alert('Please enter Customer Code to modify'); focusFirst(); }
      break;
    }

    case 'Delete': {
      const code = fieldElements['customerCode'] && fieldElements['customerCode'].value;
      if (!code) { alert('Please enter Customer Code to delete'); focusFirst(); return; }
      if (confirm('Delete this customer?')) { clearForm(); focusFirst(); }
      break;
    }

    case 'View': {
      const code = fieldElements['customerCode'] && fieldElements['customerCode'].value;
      if (!code) { alert('Please enter Customer Code to view'); focusFirst(); }
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
  const helperEl = document.getElementById('footerHelperText');
  if (!helperEl) return;

  document.querySelectorAll('.action-btn').forEach(function(btn) {
    const label = btn.textContent.trim();
    btn.addEventListener('mouseenter', function() {
      helperEl.textContent = footerDescriptions[label] || DEFAULT_HELPER;
    });
    btn.addEventListener('mouseleave', function() {
      helperEl.textContent = DEFAULT_HELPER;
    });
  });
}

/* ── MAIN PANEL BLUE OUTLINE — 1 second flash on focus ── */

function initPanelGlow() {
  var mainPanel = document.getElementById('mainPanel');
  if (!mainPanel) return;

  var panelTimer = null;

  document.querySelectorAll('.cust-input').forEach(function(inp) {
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
  const el = fieldElements['customerCode'];
  if (el) el.focus();
}

function clearForm() {
  fieldIds.forEach(function(id) {
    if (fieldElements[id]) fieldElements[id].value = '';
  });
}

/* ── INIT ── */

function init() {
  fieldIds.forEach(function(id) {
    const el = document.getElementById(id);
    if (!el) return;
    fieldElements[id] = el;
    el.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const next = fieldElements[fieldIds[fieldIds.indexOf(id) + 1]];
        if (next) next.focus();
      }
    });
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