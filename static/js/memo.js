/**
 * memo.js
 * Page-specific logic for the Memo screen.
 * Load AFTER sidebar-header.js
 */
(function () {
  'use strict';

  /* ── Calendar button — opens native date picker ── */
  var calendarBtns = document.querySelectorAll('.calendar-btn');

  calendarBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = btn.closest('.input-wrap').querySelector('.form-input');
      if (!input) return;

      /* Switch to date type temporarily to trigger native picker */
      input.type = 'date';
      input.focus();
      input.showPicker && input.showPicker();

      input.addEventListener('change', function () {
        input.type = 'text';
      }, { once: true });
    });
  });

  /* ── Action items ── */
  var actionItems = document.querySelectorAll('.action-item.active');

  actionItems.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var label = btn.textContent.trim();

      if (label === 'Exit') {
        if (confirm('Exit?')) { window.history.back(); }
        return;
      }

      if (label === 'Add') {
        /* Clear all inputs */
        document.querySelectorAll('.form-input').forEach(function (inp) {
          inp.value = '';
        });
        document.getElementById('memoDate') &&
          document.getElementById('memoDate').focus();
        return;
      }

      console.log('Action:', label);
    });
  });

  /* Expose globally if needed */
  window.handleAction = function (name) {
    console.log('Action:', name);
  };

}());