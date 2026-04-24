// Function to fetch backend data
async function fetchDashboardStats() {
    try {
        //placeholder data
        // const response = await fetch('/api/dashboard-stats');
        // const data = await response.json();

        // Placeholder data
        const data = {
            sales: "Rs 18,750",
            bills: "52",
            lowStock: "15",
            expiring: "5"
        };

        const valSales = document.getElementById('val-sales');
        const valBills = document.getElementById('val-bills');
        const valLowStock = document.getElementById('val-lowstock');
        const valExpiring = document.getElementById('val-expiring');

        if (valSales) valSales.textContent = data.sales;
        if (valBills) valBills.textContent = data.bills;
        if (valLowStock) valLowStock.textContent = data.lowStock;
        if (valExpiring) valExpiring.textContent = data.expiring;
    } catch (error) {
        console.error("Error fetching stats:", error);
    }
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    fetchDashboardStats();
});