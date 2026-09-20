/**
 * Chart.js configurations for SEO Automation Dashboard.
 */

// Color palette
const COLORS = {
  primary: '#4F46E5',
  primaryLight: '#818CF8',
  primaryDark: '#3730A3',
  purple: '#7C3AED',
  pink: '#EC4899',
  cyan: '#06B6D4',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  info: '#3B82F6',
  gray: '#94A3B8',
  gridLine: '#F1F5F9',
  text: '#475569',
  textLight: '#94A3B8',
};

// Global chart defaults
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = COLORS.text;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.plugins.tooltip.backgroundColor = '#0F172A';
Chart.defaults.plugins.tooltip.titleFont = { weight: '600', size: 13 };
Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.padding = 12;

/**
 * Create weekly sessions line chart.
 */
function createSessionsChart(canvasId, labels, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  // Find migration point (roughly week 7 — mid-April)
  const migrationIndex = labels.findIndex(l => l >= '2026-04-13');

  // Create gradient
  const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, 'rgba(79, 70, 229, 0.15)');
  gradient.addColorStop(1, 'rgba(79, 70, 229, 0.01)');

  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels.map(l => {
        const d = new Date(l);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }),
      datasets: [{
        label: 'Organic Sessions',
        data: data,
        borderColor: COLORS.primary,
        backgroundColor: gradient,
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: COLORS.primary,
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        borderWidth: 2.5,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        annotation: migrationIndex >= 0 ? {
          annotations: {
            migrationLine: {
              type: 'line',
              xMin: migrationIndex,
              xMax: migrationIndex,
              borderColor: COLORS.danger,
              borderWidth: 2,
              borderDash: [6, 4],
              label: {
                display: true,
                content: 'Migration',
                position: 'start',
                backgroundColor: COLORS.danger,
                font: { size: 11, weight: '600' },
                padding: 4,
              }
            }
          }
        } : {}
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { maxRotation: 45, font: { size: 11 } },
        },
        y: {
          grid: { color: COLORS.gridLine },
          ticks: {
            callback: v => (v / 1000).toFixed(0) + 'K',
            font: { size: 11 },
          },
          beginAtZero: false,
        }
      }
    }
  });
}

/**
 * Create traffic comparison bar chart.
 */
function createTrafficChart(canvasId, labels, previousData, currentData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels.map(l => l.length > 25 ? l.substring(0, 25) + '…' : l),
      datasets: [
        {
          label: 'Mar 2026',
          data: previousData,
          backgroundColor: 'rgba(79, 70, 229, 0.7)',
          borderRadius: 4,
          borderSkipped: false,
        },
        {
          label: 'Aug 2026',
          data: currentData,
          backgroundColor: 'rgba(124, 58, 237, 0.7)',
          borderRadius: 4,
          borderSkipped: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top' },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 10 }, maxRotation: 60 },
        },
        y: {
          grid: { color: COLORS.gridLine },
          ticks: {
            callback: v => (v / 1000).toFixed(0) + 'K',
            font: { size: 11 },
          },
        }
      }
    }
  });
}

/**
 * Create severity distribution doughnut chart.
 */
function createSeverityChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const chartColors = [COLORS.danger, '#F87171', COLORS.warning, COLORS.info];
  const chartLabels = ['Critical', 'High', 'Medium', 'Low'];
  const chartData = [
    data.Critical || 0,
    data.High || 0,
    data.Medium || 0,
    data.Low || 0,
  ];

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: chartLabels,
      datasets: [{
        data: chartData,
        backgroundColor: chartColors,
        borderWidth: 0,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 16, font: { size: 12 } },
        }
      }
    }
  });
}

/**
 * Create issue types horizontal bar chart.
 */
function createIssueTypesChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const labels = sorted.map(([k]) => k);
  const values = sorted.map(([, v]) => v);

  const barColors = values.map((_, i) => {
    const colors = [COLORS.primary, COLORS.purple, COLORS.pink, COLORS.cyan,
                    COLORS.info, COLORS.warning, COLORS.success, COLORS.danger,
                    COLORS.primaryLight, COLORS.gray, '#8B5CF6', '#F472B6'];
    return colors[i % colors.length];
  });

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: barColors,
        borderRadius: 6,
        borderSkipped: false,
        barThickness: 24,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { color: COLORS.gridLine },
          ticks: { font: { size: 11 }, stepSize: 1 },
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 12, weight: '500' } },
        }
      }
    }
  });
}

/**
 * Create GSC alert level distribution chart.
 */
function createAlertChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const alertColors = {
    'HIGH': COLORS.danger,
    'MEDIUM': COLORS.warning,
    'WATCH': '#FBBF24',
    'IMPROVED': COLORS.success,
    'STABLE': COLORS.gray,
  };

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(data),
      datasets: [{
        data: Object.values(data),
        backgroundColor: Object.keys(data).map(k => alertColors[k] || COLORS.gray),
        borderWidth: 0,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 16, font: { size: 12 } },
        }
      }
    }
  });
}

/**
 * Create GSC clicks comparison scatter/bubble chart.
 */
function createClicksComparisonChart(canvasId, anomalies) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  const alertColorMap = {
    'HIGH': COLORS.danger,
    'MEDIUM': COLORS.warning,
    'WATCH': '#FBBF24',
    'IMPROVED': COLORS.success,
    'STABLE': COLORS.gray,
  };

  const datasets = {};
  anomalies.forEach(a => {
    if (!datasets[a.alert_level]) {
      datasets[a.alert_level] = {
        label: a.alert_level,
        data: [],
        backgroundColor: alertColorMap[a.alert_level] + '99',
        borderColor: alertColorMap[a.alert_level],
        borderWidth: 1.5,
        pointRadius: 6,
        pointHoverRadius: 9,
      };
    }
    datasets[a.alert_level].data.push({
      x: a.clicks_previous,
      y: a.clicks_current,
      query: a.query,
    });
  });

  // Add reference line (y=x)
  const maxVal = Math.max(
    ...anomalies.map(a => Math.max(a.clicks_previous, a.clicks_current)),
    1
  );

  new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: Object.values(datasets),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: (context) => {
              const d = context.raw;
              return `${d.query}: ${d.x} → ${d.y} clicks`;
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Previous Clicks', font: { size: 12, weight: '600' } },
          grid: { color: COLORS.gridLine },
        },
        y: {
          title: { display: true, text: 'Current Clicks', font: { size: 12, weight: '600' } },
          grid: { color: COLORS.gridLine },
        }
      }
    }
  });
}

/**
 * Create redirect pass/fail pie chart.
 */
function createRedirectChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Pass', 'Critical', 'Warning'],
      datasets: [{
        data: [data.PASS || 0, data.CRITICAL || 0, data.WARNING || 0],
        backgroundColor: [COLORS.success, COLORS.danger, COLORS.warning],
        borderWidth: 0,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 16, font: { size: 12 } },
        }
      }
    }
  });
}
