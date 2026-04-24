function initSidebar() {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    const navItems = document.querySelectorAll('.nav-item');
    const timeline = document.getElementById('timeline');

    // Handle Navigation
    navItems.forEach(item => {
        item.addEventListener('click', function (e) {
            navItems.forEach(i => i.classList.remove('active'));
            this.classList.add('active');

            // Re-render icons
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        });
    });

    // Handle Timeline Selection
    if (timeline) {
        timeline.addEventListener('change', (e) => {
            console.log("Selected Timeline:", e.target.value);
            // logic to filter dashboard data
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // If sidebar elements already exist on load
    if (document.querySelector('.nav-item')) {
        initSidebar();
    }
});

// Wait for header.js to load the sidebar component
document.addEventListener("sidebarLoaded", () => {
    initSidebar();
});