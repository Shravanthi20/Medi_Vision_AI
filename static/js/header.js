function loadComponent(id, url) {
    fetch(url)
        .then(response => response.text())
        .then(data => {
            document.getElementById(id).innerHTML = data;
            lucide.createIcons(); // Initialize icons after loading
        });
}

function updateDateAndDay() {
    const dateElement = document.getElementById('current-date');
    const dayElement = document.getElementById('current-day');
    const now = new Date();

    // Format Date: DD/MM/YYYY
    const day = String(now.getDate()).padStart(2, '0');
    const month = String(now.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const year = now.getFullYear();

    // Format Day
    const options = { weekday: 'long' };
    const dayName = new Intl.DateTimeFormat('en-US', options).format(now);

    // Update HTML
    dateElement.textContent = `${day}/${month}/${year}`;
    dayElement.textContent = dayName;
}

function updateFinancialYear() {
    const fyElement = document.getElementById('dynamic-fy');
    const now = new Date();
    const currentYear = now.getFullYear();
    const nextYear = currentYear + 1;

    // Updates the text to: FY: 2026-2027
    fyElement.textContent = `FY: ${currentYear}-${nextYear}`;
}

// Run function when page loads
document.addEventListener('DOMContentLoaded', () => {
    updateFinancialYear();
    updateDateAndDay();

});

// Usage on index.html, sales.html, etc.
loadComponent('sidebar-placeholder', 'sidebar.html');
loadComponent('header-placeholder', 'header.html');