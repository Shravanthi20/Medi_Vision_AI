/* prr.js — Purchase Return Register
   Load AFTER sidebar-header.js
*/

(function () {
  'use strict';

  /* ── Inject 12 empty rows ── */
  const tbody = document.getElementById('prrTableBody');

  const colClasses = [
    'prr-col-code',
    'prr-col-name',
    'prr-col-batch',
    'prr-col-expiry',
    'prr-col-type',
    'prr-col-qty',
    'prr-col-price',
    'prr-col-taxcd',
    'prr-col-value',
  ];

  for (var r = 0; r < 12; r++) {
    var tr = document.createElement('tr');
    colClasses.forEach(function (cls) {
      var td = document.createElement('td');
      td.className = cls;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }

  /* ── Info inputs — focus triggers blue panel border ── */
  var mainPanel = document.getElementById('mainPanel');

  document.querySelectorAll('.prr-input').forEach(function (input) {
    input.addEventListener('focus', function () {
      mainPanel.classList.add('panel-active');
    });
    input.addEventListener('blur', function () {
      mainPanel.classList.remove('panel-active');
    });
  });

}());