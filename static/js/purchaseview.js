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

        // Load the Footer component
        const footerRes = await fetch('/templates/footer.html');
        const footerHtml = await footerRes.text();
        document.getElementById('footer-target').innerHTML = footerHtml;

        // Initialize Lucide icons after injection
        lucide.createIcons();

        // Update the dynamic time/date if those functions exist
        if (window.updateDateAndDay) updateDateAndDay();
        if (window.updateFinancialYear) updateFinancialYear();

    } catch (err) {
        console.error("Component loading failed:", err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadComponents();

    const choiceInput = document.getElementById('choice-input');
    const feedbackText = document.getElementById('feedback-text');

    choiceInput.addEventListener('input', (e) => {
        const val = e.target.value;
        if (val && (val < '1' || val > '7')) {
            feedbackText.style.color = '#ef4444';
            feedbackText.textContent = 'Invalid choice. Please enter 1-7.';
        } else {
            feedbackText.style.color = '#10b981'; // Green for valid
            feedbackText.textContent = 'Choice selected: ' + (val || 'None');
        }
    });

    choiceInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const val = choiceInput.value;
            if (val >= '1' && val <= '7') {
                handleAction('View Option ' + val);
            }
        }
    });

    // Auto focus the input
    choiceInput.focus();
});

function handleAction(action) {
    console.log("Action performed:", action);
    if (action === 'Exit') {
        window.history.back();
    } else {
        alert("Navigating to: " + action);
    }
}
