/* ═══════════════════════════════════════════════════════════
   doctor.js
═══════════════════════════════════════════════════════════ */

const footerDescriptions = {
  'Add':     'Add New Doctor',
  'Modify':  'Modify Doctor',
  'Delete':  'Delete Doctor',
  'View':    'View Doctor',
  'Go To':   'Go To Doctor',
  'Next':    'Next Doctor',
  'Prior':   'Previous Doctor',
  'Options': 'Doctor Setup',
  'Exit':    'Exit screen?'
};

const DEFAULT_HELPER = 'Doctor Setup';

const fieldIds = [
  'doctorCode',
  'doctorName',
  'clinicName',
  'address',
  'mobileNo',
  'visitingHours'
];

const fieldElements = {};

/* ── FOOTER MODE TOGGLE ── */

function setFooterMode(mode) {
  var normal  = document.getElementById('footerNormal');
  var confirm = document.getElementById('footerConfirm');
  if (mode === 'confirm') {
    normal.style.display  = 'none';
    confirm.style.display = 'flex';
  } else {
    normal.style.display  = 'flex';
    confirm.style.display = 'none';
  }
}

/* ── CONFIRMATION HANDLER ── */

function handleConfirm(action) {
  switch (action) {
    case 'Save':
      // collect and save
      var data = {};
      fieldIds.forEach(function(id) {
        data[id] = fieldElements[id] ? fieldElements[id].value : '';
      });
      console.log('Doctor saved:', data);
      clearForm();
      focusFirst();
      setFooterMode('normal');
      break;

    case 'Re-enter':
      clearForm();
      focusFirst();
      setFooterMode('normal');
      break;

    case 'Cancel':
      setFooterMode('normal');
      break;
  }
}

/* ── NORMAL FOOTER ACTION HANDLER ── */

function handleAction(name) {
  switch (name) {
    case 'Add':
      clearForm();
      focusFirst();
      break;

    case 'Modify': {
      const code = fieldElements['doctorCode'] && fieldElements['doctorCode'].value;
      if (!code) { alert('Please enter Doctor Code to modify'); focusFirst(); }
      break;
    }

    case 'Delete': {
      const code = fieldElements['doctorCode'] && fieldElements['doctorCode'].value;
      if (!code) { alert('Please enter Doctor Code to delete'); focusFirst(); return; }
      if (confirm('Delete this doctor?')) { clearForm(); focusFirst(); }
      break;
    }

    case 'View': {
      const code = fieldElements['doctorCode'] && fieldElements['doctorCode'].value;
      if (!code) { alert('Please enter Doctor Code to view'); focusFirst(); }
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

  document.querySelectorAll('#footerNormal .action-btn').forEach(function(btn) {
    const label = btn.textContent.trim();
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

  document.querySelectorAll('.doc-input').forEach(function(inp) {
    inp.addEventListener('focus', function() {
      mainPanel.classList.add('panel-active');
      if (panelTimer) clearTimeout(panelTimer);
      panelTimer = setTimeout(function() {
        mainPanel.classList.remove('panel-active');
      }, 1000);
    });
  });
}

/* ── ALL FIELDS FILLED CHECK ── */

function allFieldsFilled() {
  return fieldIds.every(function(id) {
    return fieldElements[id] && fieldElements[id].value.trim() !== '';
  });
}

/* ── FORM HELPERS ── */

function focusFirst() {
  const el = fieldElements['doctorCode'];
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
    const el = document.getElementById(id);
    if (!el) return;
    fieldElements[id] = el;

    el.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();

        // Last field — check and switch to confirm mode
        if (id === 'visitingHours') {
          if (allFieldsFilled()) {
            setFooterMode('confirm');
          }
          return;
        }

        // Move to next field
        const next = fieldElements[fieldIds[idx + 1]];
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