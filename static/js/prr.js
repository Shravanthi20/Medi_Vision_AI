/* prr.js — Purchase Return Register
   Load AFTER sidebar-header.js
*/

(function () {
  'use strict';

  var mainPanel = document.getElementById('mainPanel');

  /* ══════════════════════════════════════════
     TOTAL RECALCULATION
     Reads live from the last .num input in each row
  ══════════════════════════════════════════ */
  function updateTotals() {
    var total = 0;
    document.querySelectorAll('#prrTableBody tr').forEach(function (row) {
      var valInput = row.querySelector('td.num:last-of-type input');
      if (valInput) total += parseFloat(valInput.value) || 0;
    });
    var totalEl = document.getElementById('totalValue');
    if (totalEl) totalEl.textContent = total.toFixed(2);
  }

  /* ══════════════════════════════════════════
     DELETE ROW
  ══════════════════════════════════════════ */
  function deleteRow(row) {
    row.remove();
    updateTotals();
  }

  /* ══════════════════════════════════════════
     ADD EMPTY ROW
  ══════════════════════════════════════════ */
  function addEmptyRow() {
    var tbody    = document.getElementById('prrTableBody');
    var rowCount = tbody.rows.length;
    var blank    = { code: '', name: '', batch: '', expiry: '', type: '', qty: 0, price: 0, taxcd: '', value: 0 };
    var row      = buildRow(blank, rowCount);
    tbody.appendChild(row);
    row.querySelector('input').focus();
  }

  /* ══════════════════════════════════════════
     BUILD ROW — every cell is an editable input
     Columns: Code | Item Name | Batch | Expiry | Type | Qty | Price | Taxcd | Value
  ══════════════════════════════════════════ */
  function buildRow(item, idx) {
    var row = document.createElement('tr');

    var cols = [
      ['txt', idx > 0 ? (idx + ' ' + item.code) : item.code, 'text',   'prr-col-code'],
      ['txt', item.name,                                       'text',   'prr-col-name'],
      ['txt', item.batch,                                      'text',   'prr-col-batch'],
      ['txt', item.expiry,                                     'text',   'prr-col-expiry'],
      ['txt', item.type,                                       'text',   'prr-col-type'],
      ['num', item.qty,                                        'number', 'prr-col-qty'],
      ['num', parseFloat(item.price || 0).toFixed(2),          'number', 'prr-col-price'],
      ['txt', item.taxcd,                                      'text',   'prr-col-taxcd'],
      ['num', parseFloat(item.value || 0).toFixed(2),          'number', 'prr-col-value'],
    ];

    cols.forEach(function (col, ci) {
      var td = document.createElement('td');
      td.className      = col[0] + ' ' + col[3];
      td.style.position = 'relative';

      var inp   = document.createElement('input');
      inp.type  = col[2];
      inp.value = col[1];
      if (col[2] === 'number') inp.step = '0.01';

      inp.addEventListener('change', updateTotals);

      /* Enter key — move to next input or add new row */
      inp.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        var all    = Array.from(document.querySelectorAll('#prrTableBody tr td input'));
        var myIdx  = all.indexOf(inp);
        var isLast = myIdx === all.length - 1;
        if (isLast) { addEmptyRow(); }
        else        { var next = all[myIdx + 1]; if (next) next.focus(); }
      });

      /* Shift+Delete — remove row */
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Delete' && e.shiftKey) deleteRow(row);
      });

      td.appendChild(inp);

      /* Delete button — last cell only */
      if (ci === cols.length - 1) {
        var btn       = document.createElement('button');
        btn.className   = 'del-btn';
        btn.textContent = '×';
        btn.title       = 'Delete row';
        btn.addEventListener('click', function () { deleteRow(row); });
        td.appendChild(btn);
      }

      row.appendChild(td);
    });

    return row;
  }

  /* ══════════════════════════════════════════
     RENDER TABLE — 12 empty rows on load
  ══════════════════════════════════════════ */
  function renderTable() {
    var tbody = document.getElementById('prrTableBody');
    tbody.innerHTML = '';
    for (var r = 0; r < 12; r++) {
      var blank = { code: '', name: '', batch: '', expiry: '', type: '', qty: 0, price: 0, taxcd: '', value: 0 };
      tbody.appendChild(buildRow(blank, r + 1));
    }
    updateTotals();
  }

  renderTable();

  /* ══════════════════════════════════════════
     INFO INPUTS — focus triggers blue panel border
  ══════════════════════════════════════════ */
  document.querySelectorAll('.prr-input').forEach(function (input) {
    input.addEventListener('focus', function () {
      mainPanel.classList.add('panel-active');
    });
    input.addEventListener('blur', function () {
      mainPanel.classList.remove('panel-active');
    });
  });

}());