document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();

    const navItems = document.querySelectorAll('.nav-item');
    const timeline = document.getElementById('timeline');

    // Handle Navigation
    navItems.forEach(item => {
        item.addEventListener('click', function (e) {
            navItems.forEach(i => i.classList.remove('active'));
            this.classList.add('active');

            // Re-render icons
            lucide.createIcons();
        });
    });

    // Handle Timeline Selection
    timeline.addEventListener('change', (e) => {
        console.log("Selected Timeline:", e.target.value);
        // logic to filter dashboard data
    });
});