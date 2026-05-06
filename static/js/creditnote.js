/* credit-note.js
   STATE FLOW: Hover → Orange (CSS) | Click → Green | Panel → Blue
   TABLE: New component with editable rows, add/delete, summary sync */

const mainPanel = document.getElementById('mainPanel');

/* ══════════════════════════════════════════
   TABLE COMPONENT — data & logic
   (replaces old static cn-tbody injection)
══════════════════════════════════════════ */

// Seed data — replace or populate from your API/store
const items = [
  { id: 1, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 2, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 3, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 4, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 5, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
  { id: 6, code: "UPAR39", itemName: "Parachute JAS 200 ml", batch: "003", expDate: "12/2027", term: "Expiry", qty: 1, mrp: 135.00, disc: 0, value: 115.58 },
];

let nextId = items.length + 1;

/**
 * Renders all rows into #tableBody.
 * Shows an empty-state row when items array is empty.
 */
function renderTable() {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';

  if (items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" class="item-empty-state">
          No items added yet. Click "Add Item" to get started.
        </td>
      </tr>`;
    updateSummary();
    return;
  }

  items.forEach((item) => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><input type="text"   value="${item.code}"     onchange="updateItem(${item.id}, 'code', this.value)"></td>
      <td><input type="text"   value="${item.itemName}" onchange="updateItem(${item.id}, 'itemName', this.value)"></td>
      <td><input type="text"   value="${item.batch}"    onchange="updateItem(${item.id}, 'batch', this.value)"></td>
      <td><input type="text"   value="${item.expDate}"  onchange="updateItem(${item.id}, 'expDate', this.value)"></td>
      <td><input type="text"   value="${item.term}"     onchange="updateItem(${item.id}, 'term', this.value)"></td>
      <td><input type="number" value="${item.qty}"      onchange="updateItem(${item.id}, 'qty', this.value)"></td>
      <td><input type="number" value="${item.mrp}"      onchange="updateItem(${item.id}, 'mrp', this.value)"></td>
      <td><input type="number" value="${item.disc}"     onchange="updateItem(${item.id}, 'disc', this.value)"></td>
      <td>${item.value.toFixed(2)}</td>

    `;
    tbody.appendChild(row);
  });

  updateSummary();
}

/**
 * Updates a single field on an item and re-renders.
 * @param {number} id   - item id
 * @param {string} key  - field name
 * @param {string} value - new raw value from input
 */
function updateItem(id, key, value) {
  const item = items.find(i => i.id === id);
  if (!item) return;

  if (key === 'qty' || key === 'mrp' || key === 'disc') {
    item[key] = parseFloat(value) || 0;
  } else {
    item[key] = value;
  }

  renderTable();
}

/**
 * Removes an item by id and re-renders.
 * @param {number} id - item id
 */
function deleteItem(id) {
  const idx = items.findIndex(i => i.id === id);
  if (idx !== -1) {
    items.splice(idx, 1);
    renderTable();
  }
}

/**
 * Adds a blank row and re-renders.
 */
function addItem() {
  items.push({
    id: nextId++,
    code: '',
    itemName: '',
    batch: '',
    expDate: '',
    term: '',
    qty: 1,
    mrp: 0,
    disc: 0,
    value: 0,
  });
  renderTable();
}

/**
 * Updates summary counters.
 * DEPENDENCY: requires #totalItems, #totalQty, #totalValue in the DOM.
 * Gracefully no-ops if those elements are absent.
 */
function updateSummary() {
  const totalItemsEl = document.getElementById('totalItems');
  const totalQtyEl   = document.getElementById('totalQty');
  const totalValueEl = document.getElementById('totalValue');

  if (!totalItemsEl || !totalQtyEl || !totalValueEl) return;

  const totalQty   = items.reduce((sum, item) => sum + item.qty,   0);
  const totalValue = items.reduce((sum, item) => sum + item.value, 0);

  totalItemsEl.textContent = items.length;
  totalQtyEl.textContent   = totalQty;
  totalValueEl.textContent = '₹' + totalValue.toFixed(2);
}

// Wire up Add Item button


// Init table
renderTable();

/* ══════════════════════════════════════════
   ACTION BUTTONS — click = green, panel = blue
══════════════════════════════════════════ */
document.querySelectorAll('.action-btn.active').forEach(btn => {
  btn.addEventListener('click', () => {
    const isSelected = btn.classList.contains('selected');
    document.querySelectorAll('.action-btn').forEach(b => b.classList.remove('selected'));
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
document.querySelectorAll('.cn-input').forEach(input => {
  input.addEventListener('focus', () => {
    mainPanel.classList.add('panel-active');
  });
  input.addEventListener('blur', () => {
    if (!document.querySelector('.action-btn.selected')) {
      mainPanel.classList.remove('panel-active');
    }
  });
});