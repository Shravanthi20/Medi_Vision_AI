async function loadComponents() {
    try {
        // Load the Sidebar component
        const sidebarRes = await fetch('/templates/sidebar.html');
        const sidebarHtml = await sidebarRes.text();
        document.getElementById('sidebar-target').innerHTML = sidebarHtml;

        // Load the Header component
        const headerRes = await fetch('/templates/header.html');
        const headerHtml = await headerRes.text();
        document.getElementById('header-target').innerHTML = headerHtml;

        // Initialize Lucide icons after injection
        lucide.createIcons();

        // Update the dynamic time/date if those functions exist
        if (window.updateDateAndDay) updateDateAndDay();
        if (window.updateFinancialYear) updateFinancialYear();

    } catch (err) {
        console.error("Component loading failed:", err);
    }
}

document.addEventListener('DOMContentLoaded', loadComponents);