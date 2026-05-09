/* ═══════════════════════════════════════════════════════════
   mfrchange.js  —  Mfr / Location Change
   Includes: clock/date tick, custom dropdown, handleAction
═══════════════════════════════════════════════════════════ */

/* ── CLOCK & DATE ─────────────────────────────────────── */
(function () {
  var DAYS = ['Sunday','Monday','Tuesday','Wednesday',
              'Thursday','Friday','Saturday'];

  function pad(n) { return String(n).padStart(2, '0'); }

  function tick() {
    var now = new Date();
    var clockEl = document.getElementById('clock');
    var dateEl  = document.getElementById('date-val');
    var dayEl   = document.getElementById('day-val');

    if (clockEl)
      clockEl.textContent =
        pad(now.getHours()) + ':' +
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


/* ── CUSTOM DROPDOWN ──────────────────────────────────── */
var mlcCurrentValue = 'Manufacturer';

function mlcToggleDropdown() {
  var list    = document.getElementById('mlcDropdownList');
  var chevron = document.getElementById('mlcChevron');
  var btn     = document.getElementById('mlcSelectBtn');
  var isOpen  = list.classList.contains('open');

  if (isOpen) {
    list.classList.remove('open');
    chevron.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  } else {
    list.classList.add('open');
    chevron.classList.add('open');
    btn.setAttribute('aria-expanded', 'true');
  }
}

function mlcSelectOption(el) {
  /* Remove active from all items */
  document.querySelectorAll('.mlc-dropdown-item').forEach(function (item) {
    item.classList.remove('active');
  });

  /* Mark this one active */
  el.classList.add('active');
  mlcCurrentValue = el.getAttribute('data-value');

  /* Update button text */
  var textEl = document.getElementById('mlcSelectedText');
  if (textEl) textEl.textContent = mlcCurrentValue;

  /* Close dropdown */
  var list    = document.getElementById('mlcDropdownList');
  var chevron = document.getElementById('mlcChevron');
  var btn     = document.getElementById('mlcSelectBtn');
  list.classList.remove('open');
  chevron.classList.remove('open');
  btn.setAttribute('aria-expanded', 'false');
}

/* Close dropdown when clicking outside */
document.addEventListener('click', function (e) {
  var dropdown = document.getElementById('mlcDropdown');
  if (dropdown && !dropdown.contains(e.target)) {
    var list    = document.getElementById('mlcDropdownList');
    var chevron = document.getElementById('mlcChevron');
    var btn     = document.getElementById('mlcSelectBtn');
    if (list)    list.classList.remove('open');
    if (chevron) chevron.classList.remove('open');
    if (btn)     btn.setAttribute('aria-expanded', 'false');
  }
});


/* ── NEXT BUTTON ACTION ───────────────────────────────── */
function handleMlcNext() {
  /* Route to the correct sub-page based on selection */
  var routes = {
    'Manufacturer': '/mfr_change_detail',
    'Location':     '/loc_change_detail',
    'Supplier':     '/sup_change_detail'
  };

  var route = routes[mlcCurrentValue];
  if (route) {
    /* Uncomment when sub-pages are ready: */
    /* window.location.href = route; */
    console.log('Navigate to:', route, '| Selected:', mlcCurrentValue);
    alert('Proceeding with: ' + mlcCurrentValue + ' Change');
  }
}


/* ── FOOTER handleAction ──────────────────────────────── */
function handleAction(name) {
  if (name === 'Next')   { handleMlcNext(); return; }
  if (name === 'Go To')  { document.getElementById('mlcSelectBtn').focus(); return; }
  if (name === 'Exit')   { if (confirm('Exit?')) window.close(); return; }
  /* Add / View / Prior → extend when backend ready */
  console.log('Action:', name);
}