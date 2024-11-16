// Initialize MSE Chart
function initializeMseChart() {
    const ctx = document.getElementById('mseChart').getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],  // Time labels
            datasets: [{
                label: 'MSE',
                data: [],
                borderColor: 'rgba(75, 192, 192, 1)',
                fill: false,
            }]
        },
        options: {
            scales: {
                x: { title: { display: true, text: 'Time' }},
                y: { title: { display: true, text: 'MSE' }}
            }
        }
    });
}

// Initialize RUL Prediction Chart
function initializeRulChart() {
    const ctx = document.getElementById('rulChart').getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],  // Time labels
            datasets: [{
                label: 'RUL Prediction',
                data: [],
                borderColor: 'rgba(54, 162, 235, 1)',
                fill: false,
            }]
        },
        options: {
            scales: {
                x: { title: { display: true, text: 'Time' }},
                y: { title: { display: true, text: 'RUL (Days)' }}
            }
        }
    });
}

// Initialize Anomaly Detection Chart
function initializeAnomalyChart() {
    const ctx = document.getElementById('anomalyChart').getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],  // Time labels
            datasets: [{
                label: 'Anomaly Score',
                data: [],
                borderColor: 'rgba(255, 99, 132, 1)',
                fill: false,
            }]
        },
        options: {
            scales: {
                x: { title: { display: true, text: 'Time' }},
                y: { title: { display: true, text: 'Anomaly Score' }}
            }
        }
    });
}

// Fetch and update data periodically
function fetchAndUpdateData(mseChart, rulChart, anomalyChart) {
    setInterval(() => {
        fetch("/history?limit=50")  // Adjusted endpoint to retrieve history data
            .then(response => response.json())
            .then(data => {
                const labels = data.map(entry => entry.timestamp);
                const mseData = data.map(entry => entry.mse);
                
                // Generate RUL prediction based on MSE (assume this logic exists in the frontend for demonstration)
                const rulData = mseData.map(mse => {
                    if (mse <= 0.71) return 80; // Placeholder RUL values
                    else if (mse <= 1.12) return 50;
                    else if (mse <= 1.8) return 20;
                    else return 5;  // Critical
                });
                
                // Anomaly scores based on classification logic
                const anomalyData = data.map(entry => entry.classification === 'D (Not Allowed)' ? 1 : 0);

                // Update MSE Chart
                mseChart.data.labels = labels;
                mseChart.data.datasets[0].data = mseData;
                mseChart.update();

                // Update RUL Prediction Chart
                rulChart.data.labels = labels;
                rulChart.data.datasets[0].data = rulData;
                rulChart.update();

                // Update Anomaly Detection Chart
                anomalyChart.data.labels = labels;
                anomalyChart.data.datasets[0].data = anomalyData;
                anomalyChart.update();
            });
    }, 5000);  // Update every 5 seconds
}

// Initialize all charts and start fetching data
document.addEventListener('DOMContentLoaded', () => {
    const mseChart = initializeMseChart();
    const rulChart = initializeRulChart();
    const anomalyChart = initializeAnomalyChart();
    fetchAndUpdateData(mseChart, rulChart, anomalyChart);
});
