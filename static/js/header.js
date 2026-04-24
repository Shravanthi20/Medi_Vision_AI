async function loadComponent(id, url) {
    const element = document.getElementById(id);
    if (!element) return false;
    
    try {
        const response = await fetch(url);
        const data = await response.text();
        element.innerHTML = data;
        if (typeof lucide !== 'undefined') {
            lucide.createIcons(); // Initialize icons after loading
        }
        return true;
    } catch (error) {
        console.error(`Error loading ${url} into ${id}:`, error);
        return false;
    }
}

function updateDateAndDay() {
    const dateElement = document.getElementById('current-date');
    const dayElement = document.getElementById('current-day');
    
    if (!dateElement || !dayElement) return;

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
    if (!fyElement) return;
    
    const now = new Date();
    const currentYear = now.getFullYear();
    const nextYear = currentYear + 1;

    // Updates the text to: FY: 2026-2027
    fyElement.textContent = `FY: ${currentYear}-${nextYear}`;
}

// Run function when page loads
document.addEventListener('DOMContentLoaded', async () => {
    // Check which IDs are used in the current page
    const sidebarId = document.getElementById('sidebar-target') ? 'sidebar-target' : 'sidebar-placeholder';
    const headerId = document.getElementById('header-target') ? 'header-target' : 'header-placeholder';

    const sidebarLoaded = await loadComponent(sidebarId, 'sidebar.html');
    const headerLoaded = await loadComponent(headerId, 'header.html');
    
    if (headerLoaded) {
        updateFinancialYear();
        updateDateAndDay();
    }
    
    if (sidebarLoaded) {
        // Dispatch an event so sidebar.js knows it can bind its events
        document.dispatchEvent(new CustomEvent('sidebarLoaded'));
    }
});