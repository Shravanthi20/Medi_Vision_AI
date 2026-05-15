/* ══════════════════════════════
   HEADER — Clock & Date
══════════════════════════════ */
const DAYS   = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function pad(n) {
  return String(n).padStart(2, '0');
}

function updateHeader() {
  const n = new Date();

  const clock = document.getElementById('clock');
  if (clock) clock.textContent = pad(n.getHours()) + ':' + pad(n.getMinutes()) + ':' + pad(n.getSeconds());

  const dateVal = document.getElementById('date-val');
  if (dateVal) dateVal.textContent = n.getDate() + ' ' + MONTHS[n.getMonth()] + ' ' + n.getFullYear();

  const dayVal = document.getElementById('day-val');
  if (dayVal) dayVal.textContent = DAYS[n.getDay()];
}

setInterval(updateHeader, 1000);
updateHeader();

/* ══════════════════════════════
   SIDEBAR — Active Nav Highlight
══════════════════════════════ */
const navOptions = document.querySelectorAll('.opt');

navOptions.forEach(function(opt) {
  opt.addEventListener('click', function() {
    navOptions.forEach(function(o) {
      o.classList.remove('active');
    });
    opt.classList.add('active');
  });
});

/* ══════════════════════════════
   SIDEBAR — Timeline Dropdown
══════════════════════════════ */
const timelineDropdown = document.querySelector('.side-bar-dropdown');

if (timelineDropdown) {
  timelineDropdown.addEventListener('change', function() {
    console.log('Timeline changed to:', this.value);
  });
}