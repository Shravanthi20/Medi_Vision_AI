/* credit-note.js
   STATE FLOW: Hover → Orange (CSS) | Click → Green | Panel → Blue
   CHANGED: buildRow, deleteRow, addEmptyRow, updateTotals, Enter nav, del-btn */

const mainPanel = document.getElementById('mainPanel');

/* ── Seed data ── */
const items = [
  { id: 1, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 2, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 3, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 4, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 5, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 6, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
];

/* ══════════════════════════════════════════
   CHANGED: buildRow — every td is an input
══════════════════════════════════════════ */
function buildRow(item, idx) {
  const row = document.createElement('tr');

  const cols = [
    ['txt', item.code,                           'text'],
    ['txt', item.itemName,                       'text'],
    ['txt', item.batch,                          'text'],
    ['txt', item.expDate,                        'text'],
    ['txt', item.term,                           'text'],
    ['num', parseFloat(item.qty).toFixed(0),     'number'],
    ['num', parseFloat(item.mrp).toFixed(2),     'number'],
    ['num', parseFloat(item.disc).toFixed(2),    'number'],
    ['num', parseFloat(item.value).toFixed(2),   'number'],
  ];

  cols.forEach(function(col, ci) {
    const td = document.createElement('td');
    td.className      = col[0];
    td.style.position = 'relative';

    const inp = document.createElement('input');
    inp.type  = col[2];
    inp.value = col[1];
    if (col[2] === 'number') inp.step = '0.01';

    inp.addEventListener('change', updateTotals);

    /* Enter key — move to next input, or add new row if last */
    inp.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const all    = Array.from(document.querySelectorAll('#tableBody tr td input'));
      const myIdx  = all.indexOf(inp);
      const isLast = myIdx === all.length - 1;
      if (isLast) { addEmptyRow(); }
      else        { const next = all[myIdx + 1]; if (next) next.focus(); }
    });

    /* Shift+Delete — remove this row */
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Delete' && e.shiftKey) deleteRow(row);
    });

    td.appendChild(inp);

    /* del-btn on last cell only */
    if (ci === cols.length - 1) {
      const btn       = document.createElement('button');
      btn.className   = 'del-btn';
      btn.textContent = '×';
      btn.title       = 'Delete row';
      btn.addEventListener('click', function() { deleteRow(row); });
      td.appendChild(btn);
    }

    row.appendChild(td);
  });

  return row;
}

/* CHANGED: delete row + recalc */
function deleteRow(row) {
  row.remove();
  updateTotals();
}

/* CHANGED: add blank row, focus first cell */
function addEmptyRow() {
  const tbody = document.getElementById('tableBody');
  const blank = { code: '', itemName: '', batch: '', expDate: '', term: '', qty: 0, mrp: 0, disc: 0, value: 0 };
  const row   = buildRow(blank, tbody.rows.length);
  tbody.appendChild(row);
  row.querySelector('input').focus();
}

/* CHANGED: renderTable uses buildRow */
function renderTable() {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';

  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="item-empty-state">No items added yet.</td></tr>`;
    updateTotals();
    return;
  }

  items.forEach(function(item, i) {
    tbody.appendChild(buildRow(item, i));
  });

  updateTotals();
}

/* CHANGED: reads live from value inputs */
function updateTotals() {
  let total = 0;
  document.querySelectorAll('#tableBody tr').forEach(function(row) {
    const valInput = row.querySelector('td.num:last-child input');
    if (valInput) total += parseFloat(valInput.value) || 0;
  });
  const fmt = total.toFixed(2);
  const sub = document.getElementById('totalValue');
  if (sub) sub.textContent = fmt;
}

/* Init */
renderTable();

/* ══════════════════════════════════════════
   ACTION BUTTONS — click = green, panel = blue
══════════════════════════════════════════ */
document.querySelectorAll('.action-btn.active').forEach(function(btn) {
  btn.addEventListener('click', function() {
    const isSelected = btn.classList.contains('selected');
    document.querySelectorAll('.action-btn').forEach(function(b) { b.classList.remove('selected'); });
    if (!isSelected) {
      btn.classList.add('selected');
      mainPanel.classList.add('panel-active');
    } else {
      mainPanel.classList.remove('panel-active');
    }
  });
});

/* ══════════════════════════════════════════
   FORM INPUTS — focus triggers blue panel border
══════════════════════════════════════════ */
document.querySelectorAll('.cn-input').forEach(function(input) {
  input.addEventListener('focus', function() {
    mainPanel.classList.add('panel-active');
  });
  input.addEventListener('blur', function() {
    if (!document.querySelector('.action-btn.selected')) {
      mainPanel.classList.remove('panel-active');
    }
  });
});