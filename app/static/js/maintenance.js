/* ============================================================
   Maintenance Page
   ============================================================ */

Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = '#2e3240';

let maintHealthChart  = null;
let maintAnomalyChart = null;

const healthBuf  = { labels: [], data: [] };
const anomalyBuf = { labels: [], data: [] };
const MAX_POINTS = 60;

function pushPoint(buf, lbl, val) {
  buf.labels.push(lbl);
  buf.data.push(val);
  if (buf.labels.length > MAX_POINTS) { buf.labels.shift(); buf.data.shift(); }
}

// ---- Charts ---------------------------------------------------------------

function buildCharts() {
  const ctxH = document.getElementById('maintHealthChart').getContext('2d');
  maintHealthChart = new Chart(ctxH, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{ label: 'Health %', data: [], borderColor: '#28d17c', backgroundColor: '#28d17c22', borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true }],
    },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false } },
      scales: { x: { display: false }, y: { min: 0, max: 100, grid: { color: '#2e3240' } } } },
  });

  const ctxA = document.getElementById('maintAnomalyChart').getContext('2d');
  maintAnomalyChart = new Chart(ctxA, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{ label: 'Anomaly', data: [], borderColor: '#ffc107', backgroundColor: '#ffc10722', borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true }],
    },
    options: { responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false } },
      scales: { x: { display: false }, y: { min: 0, max: 1, grid: { color: '#2e3240' } } } },
  });
}

// ---- DOM helpers ----------------------------------------------------------

function updateKPIs(prediction) {
  const health = prediction.health_score;
  const el = document.getElementById('maint-health');
  el.textContent = health.toFixed(0);
  el.className = `display-3 fw-bold text-${health >= 70 ? 'success' : health >= 40 ? 'warning' : 'danger'}`;

  const bar = document.getElementById('health-bar');
  bar.style.width = health + '%';
  bar.className = `progress-bar ${health >= 70 ? 'bg-success' : health >= 40 ? 'bg-warning' : 'bg-danger'}`;

  document.getElementById('maint-rul').textContent = prediction.rul_label;

  const recs = document.getElementById('maint-recs');
  recs.innerHTML = prediction.recommendations.map(r => `<li class="mb-1">${r}</li>`).join('');

  const ab = document.getElementById('maint-anomaly-badge');
  ab.className = `badge ${prediction.is_anomaly ? 'bg-danger' : 'bg-success'}`;
  ab.textContent = prediction.is_anomaly ? 'ANOMALY' : 'Normal';
}

function updateSensorSummary(sensors) {
  const tbody = document.getElementById('sensor-summary-tbody');
  tbody.innerHTML = '';
  for (const [key, info] of Object.entries(sensors)) {
    const sc = info.status === 'critical' ? 'danger' : info.status === 'warning' ? 'warning' : 'success';
    const lim = info.limits;
    tbody.innerHTML += `<tr>
      <td>${key.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</td>
      <td class="fw-bold text-${sc}">${info.value}</td>
      <td class="text-secondary">${info.unit}</td>
      <td><span class="badge bg-${sc}">${info.status.toUpperCase()}</span></td>
      <td class="text-secondary small">${lim.normal_min} – ${lim.normal_max}</td>
      <td class="text-secondary small">${lim.normal_max} – ${lim.warning_max}</td>
    </tr>`;
  }
}

function updateAlarmHistory(alarmLog) {
  const wrapper = document.getElementById('alarm-history-wrapper');
  if (!alarmLog.length) {
    wrapper.innerHTML = '<p class="text-secondary small">No alarm history yet</p>';
    return;
  }
  let html = `<table class="table table-sm table-dark table-hover mb-0">
    <thead><tr><th>Time</th><th>ID</th><th>Message</th><th>Priority</th><th>Status</th></tr></thead><tbody>`;
  for (const a of alarmLog) {
    const sc = a.priority_label === 'critical' ? 'danger' : a.priority_label === 'warning' ? 'warning' : 'info';
    html += `<tr>
      <td class="text-secondary small">${a.timestamp.slice(0,19).replace('T',' ')}</td>
      <td>${a.id}</td>
      <td>${a.message}</td>
      <td><span class="badge bg-${sc}">${(a.priority_label||'info').toUpperCase()}</span></td>
      <td>${a.active ? '<span class="badge bg-danger">ACTIVE</span>' : '<span class="badge bg-secondary">RESOLVED</span>'}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  wrapper.innerHTML = html;
}

// ---- Socket.IO -----------------------------------------------------------

socket.on('data_update', (payload) => {
  const { sensors, plc, prediction } = payload;
  const ts = new Date().toLocaleTimeString();

  updateKPIs(prediction);
  updateSensorSummary(sensors);
  updateAlarmHistory(plc.alarm_log);

  pushPoint(healthBuf,  ts, prediction.health_score);
  pushPoint(anomalyBuf, ts, prediction.anomaly_score);

  if (maintHealthChart) {
    maintHealthChart.data.labels = [...healthBuf.labels];
    maintHealthChart.data.datasets[0].data = [...healthBuf.data];
    maintHealthChart.update('none');
  }
  if (maintAnomalyChart) {
    maintAnomalyChart.data.labels = [...anomalyBuf.labels];
    maintAnomalyChart.data.datasets[0].data = [...anomalyBuf.data];
    maintAnomalyChart.update('none');
  }
});

// ---- Init ----------------------------------------------------------------

buildCharts();
