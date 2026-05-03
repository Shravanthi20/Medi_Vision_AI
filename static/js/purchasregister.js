/**
 * purchaseregister.js
 *
 * Page-specific logic for the Purchase Registers screen.
 *
 * Depends on:
 *   /static/js/sidebar.js  — renders #sidebar-container
 *   /static/js/header.js   — renders #header-container and owns
 *                            the clock / date / FY update loop
 *
 * This file must be loaded AFTER sidebar.js and header.js
 * (script order in purchaseregister.html guarantees this).
 *
 * CHANGES FROM ORIGINAL:
 * ──────────────────────
 * 1. Added: var mainPanel = document.getElementById('mainPanel')
 * 2. Added: mainPanel.classList.add('panel-active') inside selectById()
 *    → This applies the blue border to .main whenever any option is selected.
 *    → The border is additive and stays once set (intentional, per requirements).
 */
(function () {
  'use strict';

  /* ──────────────────────────────────────────────
     Element references
  ────────────────────────────────────────────── */
  var menuBtns   = document.querySelectorAll('.menu-btn');
  var choiceBtns = document.querySelectorAll('.choice-btn');
  var mainPanel  = document.getElementById('mainPanel'); // ADDED

  var activeId = null;

  /* ──────────────────────────────────────────────
     Selection logic
     Keeps menu-btn list and choice-btn row in sync.
     Also activates the blue panel border on first selection.
  ────────────────────────────────────────────── */

  /**
   * Highlight the menu row and the matching choice button
   * that correspond to the given numeric id.
   * Also adds 'panel-active' to #mainPanel for the blue border.
   *
   * @param {string|number} id
   */
  function selectById(id) {
    activeId = id;

    menuBtns.forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-id') === String(id));
    });

    choiceBtns.forEach(function (btn) {
      btn.classList.toggle('selected', btn.getAttribute('data-choice') === String(id));
    });

    // ADDED: activate blue border on the main panel
    if (mainPanel) {
      mainPanel.classList.add('panel-active');
    }
  }

  /* Click on any menu row → select that row */
  menuBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      selectById(btn.getAttribute('data-id'));
    });
  });

  /* Click on a choice button → select matching menu row */
  choiceBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      selectById(btn.getAttribute('data-choice'));
    });
  });

  /* ──────────────────────────────────────────────
     Footer action handler
     (Footer has been removed from the layout per
     UI refinement requirements, but the handler is
     retained here in case it is re-introduced.)
  ────────────────────────────────────────────── */
  function handleAction(name) {
    if (name === 'Exit') {
      if (confirm('Exit?')) { window.close(); }
      return;
    }
    console.log('Action:', name);
  }

  /* Expose handleAction globally in case external
     components (e.g., header or sidebar) need it. */
  window.handleAction = handleAction;

}());