// Scope everything inside your feature only
const container = document.querySelector('.menu-card');

if (container) {

  const menuBtns   = container.querySelectorAll('.menu-btn');
  const choiceBtns = container.querySelectorAll('.choice-btn');

  let activeId = null;

  function selectById(id) {
    activeId = id;

    menuBtns.forEach(btn => {
      btn.classList.toggle('selected', btn.dataset.id === String(id));
    });

    choiceBtns.forEach(btn => {
      btn.classList.toggle('selected', btn.dataset.choice === String(id));
    });
  }

  menuBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      selectById(btn.dataset.id);
    });
  });
git