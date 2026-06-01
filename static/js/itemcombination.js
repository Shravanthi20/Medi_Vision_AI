/* ── CLOCK & DATE ── */
(function () {
  var days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

  function pad(n) { return String(n).padStart(2, '0'); }

  function tick() {
    var now = new Date();
    var h = pad(now.getHours()), m = pad(now.getMinutes()), s = pad(now.getSeconds());
    document.getElementById('clock').textContent = h + ':' + m + ':' + s;
    var dd = pad(now.getDate()), mm = pad(now.getMonth()+1), yy = now.getFullYear();
    document.getElementById('date-val').textContent = dd + '/' + mm + '/' + yy;
    document.getElementById('day-val').textContent  = days[now.getDay()];
  }

  tick();
  setInterval(tick, 1000);
}());

/* ── ITEM COMBINATION TABLE ── */
(function () {
  'use strict';

  var mainPanel = document.getElementById('mainPanel');

  function updateTotals() {
    var total = 0;
    document.querySelectorAll('#prrTableBody tr').forEach(function (row) {
      var mrpInput = row.querySelector('td.prr-col-mrp input');
      if (mrpInput) total += parseFloat(mrpInput.value) || 0;
    });
    var totalEl = document.getElementById('totalValue');
    if (totalEl) totalEl.textContent = total.toFixed(2);
  }

  function deleteRow(row) {
    row.remove();
    updateTotals();
  }

  function addEmptyRow() {
    var tbody    = document.getElementById('prrTableBody');
    var blank    = { item:'', name:'', mfr:'', pkg:'', stock:0, offer:'', purrate:0, mrp:0, loc:'', remark:'' };
    var row      = buildRow(blank);
    tbody.appendChild(row);
    row.querySelector('input').focus();
  }

  function buildRow(item) {
    var row = document.createElement('tr');

    var cols = [
      ['txt', item.item    || '', 'text',   'prr-col-item'],
      ['txt', item.name    || '', 'text',   'prr-col-name'],
      ['txt', item.mfr     || '', 'text',   'prr-col-mfr'],
      ['txt', item.pkg     || '', 'text',   'prr-col-pkg'],
      ['num', parseFloat(item.stock   || 0).toFixed(2), 'number', 'prr-col-stock'],
      ['txt', item.offer   || '', 'text',   'prr-col-offer'],
      ['num', parseFloat(item.purrate || 0).toFixed(2), 'number', 'prr-col-purrate'],
      ['num', parseFloat(item.mrp     || 0).toFixed(2), 'number', 'prr-col-mrp'],
      ['txt', item.loc     || '', 'text',   'prr-col-loc'],
      ['txt', item.remark  || '', 'text',   'prr-col-remark'],
    ];

    cols.forEach(function (col, ci) {
      var td            = document.createElement('td');
      td.className      = col[0] + ' ' + col[3];
      td.style.position = 'relative';

      var inp  = document.createElement('input');
      inp.type  = col[2];
      inp.value = col[1];
      if (col[2] === 'number') inp.step = '0.01';

      inp.addEventListener('change', updateTotals);

      inp.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        var all   = Array.from(document.querySelectorAll('#prrTableBody tr td input'));
        var myIdx = all.indexOf(inp);
        if (myIdx === all.length - 1) { addEmptyRow(); }
        else { var next = all[myIdx + 1]; if (next) next.focus(); }
      });

      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Delete' && e.shiftKey) deleteRow(row);
      });

      td.appendChild(inp);

      if (ci === cols.length - 1) {
        var btn         = document.createElement('button');
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

  function renderTable() {
    var tbody = document.getElementById('prrTableBody');
    tbody.innerHTML = '';
    for (var r = 0; r < 12; r++) {
      var blank = { item:'', name:'', mfr:'', pkg:'', stock:0, offer:'', purrate:0, mrp:0, loc:'', remark:'' };
      tbody.appendChild(buildRow(blank));
    }
    updateTotals();
  }

  renderTable();

  /* Info inputs — blue panel border on focus */
  document.querySelectorAll('.prr-input').forEach(function (input) {
    input.addEventListener('focus', function () { mainPanel.classList.add('panel-active'); });
    input.addEventListener('blur',  function () { mainPanel.classList.remove('panel-active'); });
  });

  function handleAction(name) {

  if (name === 'Add') {

    const data = {
      itemcode: document.getElementById('prr-itemcode').value,
      mfr: document.getElementById('prr-mfr').value,
      locn: document.getElementById('prr-locn').value,
      combcode: document.getElementById('prr-combcode').value
    };

    // Step 1: send to backend
    fetch('/add_item_combination', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(() => {
      // Step 2: refresh table
      loadTable();
    })
    .catch(err => console.error(err));
  }

  if (name === 'Exit') {
    if (confirm('Exit?')) window.close();
  }

}

}());