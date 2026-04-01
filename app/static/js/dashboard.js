/* ============================================================
   Dashboard Page – Real-time sensor charts and controls
   ============================================================ */

// Chart.js global defaults
Chart.defaults.color = '#8892a4';
Chart.defaults.borderColor = '#2e3240';

const SENSOR_COLORS = {
  temperature: '#e05252',
  pressure:    '#4f8ef7',
  vibration:   '#ffc107',
  current:     '#a78bfa',
  rpm:         '#28d17c',
  oil_level:   '#38bdf8',
};

const SENSOR_UNITS = {
  temperature: '°C',
  pressure:    'bar',
  vibration:   'mm/s',
  current:     'A',
  rpm:         'RPM',
  oil_level:   '%',
};

let sensorChart = null;
let healthChart = null;
let anomalyChart = null;
let selectedSensor = 'vibration';

const MAX_POINTS = 60;

// Rolling buffer keyed by sensor name
const sensorBuf = {};
const healthBuf  = { labels: [], data: [] };
const anomalyBuf = { labels: [], data: [] };

// ---- Chart builders -------------------------------------------------------

function buildSensorChart() {
  const ctx = document.getElementById('sensorChart').getContext('2d');
  sensorChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: selectedSensor,
        data: [],
        borderColor: SENSOR_COLORS[selectedSensor],
        backgroundColor: SENSOR_COLORS[selectedSensor] + '22',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { grid: { color: '#2e3240' } },
      },
    },
  });
}

function buildHealthChart() {
  const ctx = document.getElementById('healthChart').getContext('2d');
  healthChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Health %',
        data: [],
        borderColor: '#28d17c',
        backgroundColor: '#28d17c22',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { min: 0, max: 100, grid: { color: '#2e3240' } },
      },
    },
  });
}

function buildAnomalyChart() {
  const ctx = document.getElementById('anomalyChart').getContext('2d');
  anomalyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Anomaly',
        data: [],
        borderColor: '#ffc107',
        backgroundColor: '#ffc10722',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { min: 0, max: 1, grid: { color: '#2e3240' } },
      },
    },
  });
}

// ---- Data update helpers --------------------------------------------------

function pushPoint(buf, label, value) {
  buf.labels.push(label);
  buf.data.push(value);
  if (buf.labels.length > MAX_POINTS) { buf.labels.shift(); buf.data.shift(); }
}

function updateSensorChart(ts, sensorData) {
  if (!sensorChart) return;
  const s = sensorData[selectedSensor];
  if (!s) return;
  if (!sensorBuf[selectedSensor]) sensorBuf[selectedSensor] = { labels: [], data: [] };
  const b = sensorBuf[selectedSensor];
  pushPoint(b, ts, s.value);
  sensorChart.data.labels = [...b.labels];
  sensorChart.data.datasets[0].data = [...b.data];
  sensorChart.data.datasets[0].label = selectedSensor;
  sensorChart.data.datasets[0].borderColor = SENSOR_COLORS[selectedSensor];
  sensorChart.data.datasets[0].backgroundColor = SENSOR_COLORS[selectedSensor] + '22';
  sensorChart.update('none');
}

function updateHealthChart(ts, health) {
  if (!healthChart) return;
  pushPoint(healthBuf, ts, health);
  healthChart.data.labels = [...healthBuf.labels];
  healthChart.data.datasets[0].data = [...healthBuf.data];
  healthChart.update('none');
}

function updateAnomalyChart(ts, score) {
  if (!anomalyChart) return;
  pushPoint(anomalyBuf, ts, score);
  anomalyChart.data.labels = [...anomalyBuf.labels];
  anomalyChart.data.datasets[0].data = [...anomalyBuf.data];
  anomalyChart.update('none');
}

// ---- DOM update helpers ---------------------------------------------------

function statusClass(status) {
  if (status === 'critical') return 'danger';
  if (status === 'warning')  return 'warning';
  return 'success';
}

function updateSensorCards(sensorData) {
  for (const [key, info] of Object.entries(sensorData)) {
    const valEl   = document.getElementById(`val-${key}`);
    const badgeEl = document.getElementById(`badge-${key}`);
    const cardEl  = document.getElementById(`card-${key}`);
    if (!valEl) continue;
    valEl.textContent = info.value;
    const sc = statusClass(info.status);
    badgeEl.className = `badge mt-1 w-100 bg-${sc}`;
    badgeEl.textContent = info.status.toUpperCase();
    cardEl.className = `card bg-dark border-secondary h-100 p-3 text-center sensor-card status-${info.status}`;
    // colour value text
    valEl.className = `fs-3 fw-bold text-${sc}`;
  }
}

function updateKPIs(sensors, prediction, plc) {
  const health = prediction.health_score;
  const healthEl = document.getElementById('kpi-health');
  healthEl.textContent = health.toFixed(0);
  healthEl.className = `display-5 fw-bold text-${health >= 70 ? 'success' : health >= 40 ? 'warning' : 'danger'}`;

  document.getElementById('kpi-rul').textContent = prediction.rul_label;

  const alarmCount = plc.active_alarms.length;
  const alarmEl = document.getElementById('kpi-alarms');
  alarmEl.textContent = alarmCount;
  alarmEl.className = `display-5 fw-bold text-${alarmCount === 0 ? 'success' : alarmCount < 3 ? 'warning' : 'danger'}`;

  const running = plc.machine_running;
  const statEl = document.getElementById('kpi-status');
  statEl.textContent = running ? 'RUNNING' : 'STOPPED';
  statEl.className = `display-5 fw-bold text-${running ? 'success' : 'secondary'}`;
}

function updateRecommendations(recs) {
  const ul = document.getElementById('recommendations');
  ul.innerHTML = recs.map(r => `<li class="mb-1">${r}</li>`).join('');
}

function updateAnomalyBadge(prediction) {
  const el = document.getElementById('anomaly-label');
  if (prediction.is_anomaly) {
    el.className = 'badge bg-danger';
    el.textContent = 'ANOMALY DETECTED';
  } else {
    el.className = 'badge bg-success';
    el.textContent = 'Normal';
  }
  const modelEl = document.getElementById('model-status');
  modelEl.textContent = prediction.model_trained
    ? `Trained (${prediction.samples_collected} samples)`
    : `Training… (${prediction.samples_collected} / 50)`;
  modelEl.className = prediction.model_trained ? 'text-success' : 'text-warning';
}

function updateAlarmTable(activeAlarms) {
  const wrapper = document.getElementById('alarm-table-wrapper');
  if (!activeAlarms.length) {
    wrapper.innerHTML = '<p class="text-secondary small">No active alarms</p>';
    return;
  }
  let html = `<table class="table table-sm table-dark table-hover mb-0">
    <thead><tr><th>Time</th><th>ID</th><th>Message</th><th>Priority</th><th>Ack</th></tr></thead><tbody>`;
  for (const a of activeAlarms) {
    const pri = a.priority_label;
    const sc  = pri === 'critical' ? 'danger' : pri === 'warning' ? 'warning' : 'info';
    html += `<tr>
      <td class="text-secondary small">${a.timestamp.slice(11,19)}</td>
      <td>${a.id}</td>
      <td>${a.message}</td>
      <td><span class="badge bg-${sc}">${pri.toUpperCase()}</span></td>
      <td>${a.acknowledged
        ? '<span class="badge bg-secondary">ACK</span>'
        : `<button class="btn btn-outline-secondary btn-sm py-0 px-1" onclick="ackAlarm('${a.id}')">ACK</button>`}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  wrapper.innerHTML = html;
}

// ---- Machine controls & fault injection ----------------------------------

async function machineCmd(cmd) {
  const res = await fetch(`/api/plc/${cmd}`, { method: 'POST' });
  const data = await res.json();
  console.log(cmd, data.message);
}

async function ackAlarm(id) {
  await fetch('/api/plc/acknowledge-alarm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alarm_id: id }),
  });
}

async function injectFault() {
  const sensor = document.getElementById('fault-sensor').value;
  await fetch('/api/fault/inject', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sensor, magnitude: 3.0 }),
  });
}

async function clearFault() {
  await fetch('/api/fault/clear', { method: 'POST' });
}

// ---- Socket.IO data handler ----------------------------------------------

socket.on('data_update', (payload) => {
  const { sensors, plc, prediction } = payload;
  const ts = new Date().toLocaleTimeString();

  updateSensorCards(sensors);
  updateKPIs(sensors, prediction, plc);
  updateRecommendations(prediction.recommendations);
  updateAnomalyBadge(prediction);
  updateAlarmTable(plc.active_alarms);

  updateSensorChart(ts, sensors);
  updateHealthChart(ts, prediction.health_score);
  updateAnomalyChart(ts, prediction.anomaly_score);
});

// ---- Sensor chart selector -----------------------------------------------

document.getElementById('chart-sensor-select').addEventListener('change', (e) => {
  selectedSensor = e.target.value;
  if (!sensorBuf[selectedSensor]) sensorBuf[selectedSensor] = { labels: [], data: [] };
  const b = sensorBuf[selectedSensor];
  if (sensorChart) {
    sensorChart.data.labels = [...b.labels];
    sensorChart.data.datasets[0].data = [...b.data];
    sensorChart.data.datasets[0].borderColor = SENSOR_COLORS[selectedSensor];
    sensorChart.data.datasets[0].backgroundColor = SENSOR_COLORS[selectedSensor] + '22';
    sensorChart.update('none');
  }
});

// ---- Init ----------------------------------------------------------------

buildSensorChart();
buildHealthChart();
buildAnomalyChart();
