/**
 * purchaseregister.js
 *
 * Interaction logic for the Purchase Register screen.
 * Works for ANY number of menu-btn / choice-btn pairs.
 *
 * Depends on:
 *   /static/js/sidebar-header.js — clock, date, sidebar
 * Load this AFTER sidebar-header.js.
 *
 * STATE FLOW:
 *   Hover  → Orange  (CSS only)
 *   Click  → Green   (.selected class, instant)
 *   Panel  → Blue    (.panel-active on #mainPanel)
 */
(function () {
  'use strict';

  /* ── Element references ── */
  var menuBtns   = document.querySelectorAll('.menu-btn');
  var choiceBtns = document.querySelectorAll('.choice-btn');
  var mainPanel  = document.getElementById('mainPanel');

  /* ── Core selection function ──
     Syncs menu row + choice button, activates panel border */
  function selectById(id) {
    var str = String(id);

    menuBtns.forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-id') === str);
    });

    choiceBtns.forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-choice') === str);
    });

    /* Blue border on main panel — added once, stays */
    if (mainPanel) {
      mainPanel.classList.add('panel-active');
    }
  }

  /* ── Event listeners ── */

  /* Click on menu row → select it */
  menuBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      selectById(btn.getAttribute('data-id'));
    });
  });

  /* Click on choice button → select matching menu row */
  choiceBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      selectById(btn.getAttribute('data-choice'));
    });
  });

  /* ── Footer action handler (retained for compatibility) ── */
  function handleAction(name) {
    if (name === 'Exit') {
      if (confirm('Exit?')) { window.close(); }
      return;
    }
    console.log('Action:', name);
  }

  window.handleAction = handleAction;

}());