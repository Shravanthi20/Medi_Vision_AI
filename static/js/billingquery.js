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
        const val = parseInt(e.target.value);
        if (e.target.value && (isNaN(val) || val < 1 || val > 12)) {
            feedbackText.style.color = '#ef4444';
            feedbackText.textContent = 'Invalid choice. Please enter 1-12.';
        } else {
            feedbackText.style.color = '#60a5fa';
            feedbackText.textContent = 'Enter the valid choice';
        }
    });

    choiceInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const val = parseInt(choiceInput.value);
            if (!isNaN(val) && val >= 1 && val <= 12) {
                handleAction('Billing Option ' + val);
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
        alert("Running Query: " + action);
    }
}
