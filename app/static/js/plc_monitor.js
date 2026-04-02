/* ============================================================
   PLC Monitor Page
   ============================================================ */

// ---- Ladder logic rung definitions  (mirrors plc.py logic) ---------------
const RUNGS = [
  {
    id: 'rung1',
    label: 'Rung 1 – Motor Run',
    contacts: ['start_pb', 'stop_pb', 'estop_pb', 'temp_sw', 'pres_sw', 'oil_level_sw', 'motor_overload'],
    coil: 'motor_run',
  },
  {
    id: 'rung2',
    label: 'Rung 2 – Coolant Pump',
    contacts: ['motor_run'],
    coil: 'pump_run',
  },
  {
    id: 'rung3',
    label: 'Rung 3 – Lube Pump',
    contacts: ['motor_run'],
    coil: 'lube_pump',
  },
  {
    id: 'rung4',
    label: 'Rung 4 – Pressure Relief (NC)',
    contacts: ['pres_sw'],
    coil: 'pressure_relief',
    ncCoil: true,
  },
  {
    id: 'rung5',
    label: 'Rung 5 – Alarm Horn',
    contacts: [],
    coil: 'alarm_horn',
    note: '(any unacknowledged alarm)',
  },
];

let currentAlarmFilter = 'all';
let latestAlarmLog = [];
let latestActiveAlarms = [];
let ackAllInFlight = false;

// ---- Render ladder diagram -----------------------------------------------

function renderLadder(plcData) {
  const contacts = plcData.contacts;
  const coils    = plcData.coils;
  const div = document.getElementById('ladder-diagram');
  div.innerHTML = '';

  for (const rung of RUNGS) {
    const row = document.createElement('div');
    row.className = 'rung';

    // Label
    const lbl = document.createElement('span');
    lbl.className = 'rung-label';
    lbl.textContent = rung.label;
    row.appendChild(lbl);

    // Power rail
    row.appendChild(railSpan('|'));

    // Contacts
    for (const cName of rung.contacts) {
      const cData = contacts[cName] || coils[cName];
      const closed = cData ? cData.state : false;
      const sym = closed
        ? `<span class="contact-closed" title="${cName}">─[ ]─</span>`
        : `<span class="contact-open"   title="${cName}">─[/]─</span>`;
      const el = document.createElement('span');
      el.innerHTML = sym + `<span class="text-secondary" style="font-size:0.65rem">${cData ? cData.address : cName}</span>`;
      el.style.marginRight = '4px';
      row.appendChild(el);
    }

    // Wire to coil
    row.appendChild(railSpan('──────'));

    // Coil
    const coilData = coils[rung.coil];
    const on = coilData ? coilData.state : false;
    const coilEl = document.createElement('span');
    coilEl.className = on ? 'coil-on fw-bold' : 'coil-off';
    coilEl.innerHTML = on
      ? `<span title="${rung.coil}">─( ✔ )─</span>`
      : `<span title="${rung.coil}">─(   )─</span>`;
    row.appendChild(coilEl);

    // Coil label
    const coilLbl = document.createElement('span');
    coilLbl.className = 'text-secondary';
    coilLbl.style.fontSize = '0.72rem';
    coilLbl.textContent = coilData ? `${coilData.address} ${coilData.label}` : rung.coil;
    row.appendChild(coilLbl);

    if (rung.note) {
      const n = document.createElement('span');
      n.className = 'text-secondary ms-2';
      n.style.fontSize = '0.7rem';
      n.textContent = rung.note;
      row.appendChild(n);
    }

    // Right rail
    row.appendChild(railSpan('|'));
    div.appendChild(row);
  }
}

function railSpan(text) {
  const s = document.createElement('span');
  s.className = 'rung-arrow';
  s.textContent = text;
  return s;
}

// ---- Contacts & coils tables ---------------------------------------------

function renderContacts(contacts) {
  const tbody = document.getElementById('contacts-tbody');
  tbody.innerHTML = '';
  for (const [key, c] of Object.entries(contacts)) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-secondary small">${c.address}</td>
      <td>${c.label}</td>
      <td><span class="badge ${c.state ? 'bg-success' : 'bg-secondary'}">${c.state ? 'CLOSED' : 'OPEN'}</span></td>`;
    tbody.appendChild(tr);
  }
}

function renderCoils(coils) {
  const tbody = document.getElementById('coils-tbody');
  tbody.innerHTML = '';
  for (const [key, c] of Object.entries(coils)) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-secondary small">${c.address}</td>
      <td>${c.label}</td>
      <td><span class="badge ${c.state ? 'bg-warning text-dark' : 'bg-secondary'}">${c.state ? 'ON' : 'OFF'}</span></td>`;
    tbody.appendChild(tr);
  }
}

// ---- Alarm log -----------------------------------------------------------

function renderAlarmLog(alarmLog, activeAlarms) {
  const badge = document.getElementById('alarm-count-badge');
  badge.textContent = `${activeAlarms.length} active`;
  badge.className   = `badge ${activeAlarms.length > 0 ? 'bg-danger' : 'bg-secondary'}`;

  const activeById = {};
  for (const alarm of activeAlarms) {
    activeById[alarm.id] = alarm;
  }

  const wrapper = document.getElementById('alarm-log-wrapper');
  if (!alarmLog.length) {
    wrapper.innerHTML = '<p class="text-secondary small">No alarms recorded</p>';
    updateAckAllButtonState(activeAlarms);
    return;
  }
  let html = `<table class="table table-sm table-dark table-hover mb-0">
    <thead><tr><th>Time</th><th>ID</th><th>Message</th><th>Priority</th><th>Status</th><th>Ack</th></tr></thead><tbody>`;
  const shownAckActionFor = new Set();
  const filteredAlarmLog = alarmLog.filter((a) => {
    const isActive = !!activeById[a.id];
    if (currentAlarmFilter === 'active') return isActive;
    if (currentAlarmFilter === 'resolved') return !isActive;
    return true;
  });

  if (!filteredAlarmLog.length) {
    wrapper.innerHTML = '<p class="text-secondary small mb-0">No alarms for selected filter</p>';
    updateAckAllButtonState(activeAlarms);
    return;
  }

  for (const a of filteredAlarmLog) {
    const active = activeById[a.id];
    const acknowledged = active ? active.acknowledged : true;
    const sc = a.priority_label === 'critical' ? 'danger' : a.priority_label === 'warning' ? 'warning' : 'info';
    const state = active
      ? `<span class="badge ${acknowledged ? 'bg-warning text-dark' : 'bg-danger'}">${acknowledged ? 'ACTIVE (ACK)' : 'ACTIVE'}</span>`
      : '<span class="badge bg-secondary">RESOLVED</span>';
    let ackControl = '<span class="text-secondary small">—</span>';
    if (active && !acknowledged && !shownAckActionFor.has(a.id)) {
      shownAckActionFor.add(a.id);
      ackControl = `<button class="btn btn-outline-secondary btn-sm py-0 px-1" onclick="ackAlarm('${a.id}')">ACK</button>`;
    }
    html += `<tr>
      <td class="text-secondary small">${a.timestamp.slice(0,19).replace('T',' ')}</td>
      <td>${a.id}</td>
      <td>${a.message}</td>
      <td><span class="badge bg-${sc}">${(a.priority_label||'info').toUpperCase()}</span></td>
      <td>${state}</td>
      <td>${ackControl}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  wrapper.innerHTML = html;
  updateAckAllButtonState(activeAlarms);
}

// ---- Machine controls ----------------------------------------------------

async function machineCmd(cmd) {
  await siasFetch(`/api/plc/${cmd}`, { method: 'POST' });
}

async function ackAlarm(id) {
  try {
    const res = await siasFetch('/api/plc/acknowledge-alarm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alarm_id: id }),
    });
    if (!res.ok) {
      throw new Error(`Failed with status ${res.status}`);
    }
    const alarm = latestActiveAlarms.find((a) => a.id === id);
    if (alarm) alarm.acknowledged = true;
    renderAlarmLog(latestAlarmLog, latestActiveAlarms);
    showToast(`Alarm ${id} acknowledged`, 'success');
  } catch (err) {
    console.error(err);
    showToast(`Unable to acknowledge ${id}`, 'danger');
  }
}

function setAlarmFilter(filter) {
  currentAlarmFilter = filter;
  updateAlarmFilterButtons();
  renderAlarmLog(latestAlarmLog, latestActiveAlarms);
}

async function ackAllActiveAlarms() {
  if (ackAllInFlight) return;
  const targets = latestActiveAlarms.filter((a) => !a.acknowledged).map((a) => a.id);
  if (!targets.length) {
    showToast('No unacknowledged active alarms', 'info');
    return;
  }

  ackAllInFlight = true;
  updateAckAllButtonState(latestActiveAlarms);
  const results = await Promise.all(
    targets.map(async (id) => {
      try {
        const res = await siasFetch('/api/plc/acknowledge-alarm', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ alarm_id: id }),
        });
        return { id, ok: res.ok };
      } catch (err) {
        console.error(err);
        return { id, ok: false };
      }
    })
  );

  const successIds = results.filter((r) => r.ok).map((r) => r.id);
  const failedCount = results.length - successIds.length;
  for (const id of successIds) {
    const alarm = latestActiveAlarms.find((a) => a.id === id);
    if (alarm) alarm.acknowledged = true;
  }
  renderAlarmLog(latestAlarmLog, latestActiveAlarms);
  ackAllInFlight = false;
  updateAckAllButtonState(latestActiveAlarms);

  if (failedCount === 0) {
    showToast(`Acknowledged ${successIds.length} active alarm(s)`, 'success');
  } else if (successIds.length > 0) {
    showToast(`Acknowledged ${successIds.length}, failed ${failedCount}`, 'warning');
  } else {
    showToast('Failed to acknowledge active alarms', 'danger');
  }
}

function updateAlarmFilterButtons() {
  const ids = ['all', 'active', 'resolved'];
  for (const id of ids) {
    const btn = document.getElementById(`alarm-filter-${id}`);
    if (!btn) continue;
    btn.classList.toggle('active', currentAlarmFilter === id);
  }
}

function updateAckAllButtonState(activeAlarms) {
  const btn = document.getElementById('ack-all-btn');
  if (!btn) return;
  const hasUnack = activeAlarms.some((a) => !a.acknowledged);
  btn.disabled = ackAllInFlight || !hasUnack;
}

function showToast(message, level = 'success') {
  const container = document.getElementById('plc-toast-container');
  if (!container || !window.bootstrap) return;

  const tone = {
    success: 'text-bg-success',
    danger: 'text-bg-danger',
    warning: 'text-bg-warning text-dark',
    info: 'text-bg-info text-dark',
  }[level] || 'text-bg-secondary';
  const closeClass = (level === 'warning' || level === 'info') ? 'btn-close' : 'btn-close btn-close-white';

  const toast = document.createElement('div');
  toast.className = `toast align-items-center border-0 ${tone}`;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'assertive');
  toast.setAttribute('aria-atomic', 'true');
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="${closeClass} me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>
  `;
  container.appendChild(toast);
  const bsToast = new bootstrap.Toast(toast, { delay: 2600 });
  toast.addEventListener('hidden.bs.toast', () => toast.remove());
  bsToast.show();
}

function renderPlcData(plc) {
  latestAlarmLog = plc.alarm_log || [];
  latestActiveAlarms = plc.active_alarms || [];

  renderContacts(plc.contacts);
  renderCoils(plc.coils);
  renderLadder(plc);
  renderAlarmLog(latestAlarmLog, latestActiveAlarms);

  document.getElementById('plc-tick').textContent = plc.tick;
  const mr = plc.coils.motor_run;
  const el = document.getElementById('motor-run-state');
  if (mr) {
    el.className = `badge ${mr.state ? 'bg-success' : 'bg-secondary'}`;
    el.textContent = mr.state ? 'ON' : 'OFF';
  }
  document.getElementById('plc-ts').textContent = new Date().toLocaleTimeString();
}

async function loadInitialPlcStatus() {
  const res = await siasFetch('/api/plc/status');
  const plc = await res.json();
  renderPlcData(plc);
}

// ---- Socket.IO handler ---------------------------------------------------

socket.on('data_update', (payload) => {
  const plc = payload?.plc;
  if (plc) {
    renderPlcData(plc);
  }
});

loadInitialPlcStatus();
updateAlarmFilterButtons();
