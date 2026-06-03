/* ═══════════════════════════════════════════════════════════
   supplier-mfr.js
═══════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var menuBtns   = document.querySelectorAll('.menu-btn');
  var choiceBtns = document.querySelectorAll('.choice-btn');
  var mainPanel  = document.getElementById('mainPanel');

  function selectById(id) {
    var str = String(id);

    menuBtns.forEach(function(btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-id') === str);
    });

    choiceBtns.forEach(function(btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-choice') === str);
    });

    if (mainPanel) {
      mainPanel.classList.add('panel-active');
      setTimeout(function() {
        mainPanel.classList.remove('panel-active');
      }, 1000);
    }
  }

  menuBtns.forEach(function(btn) {
    btn.addEventListener('click', function() {
      selectById(btn.getAttribute('data-id'));
    });
  });

  choiceBtns.forEach(function(btn) {
    btn.addEventListener('click', function() {
      selectById(btn.getAttribute('data-choice'));
    });
  });

  /* Keyboard: press 1 or 2 to select */
  document.addEventListener('keydown', function(e) {
    if (e.key === '1') selectById(1);
    if (e.key === '2') selectById(2);
  });

  function handleAction(name) {
    if (name === 'Exit') {
      if (confirm('Exit?')) window.history.back();
    }
  }

  window.handleAction = handleAction;

}());