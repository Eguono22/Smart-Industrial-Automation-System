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

  const wrapper = document.getElementById('alarm-log-wrapper');
  if (!alarmLog.length) {
    wrapper.innerHTML = '<p class="text-secondary small">No alarms recorded</p>';
    return;
  }
  let html = `<table class="table table-sm table-dark table-hover mb-0">
    <thead><tr><th>Time</th><th>ID</th><th>Message</th><th>Priority</th><th>Status</th></tr></thead><tbody>`;
  for (const a of alarmLog) {
    const sc = a.priority_label === 'critical' ? 'danger' : a.priority_label === 'warning' ? 'warning' : 'info';
    const state = a.active ? '<span class="badge bg-danger">ACTIVE</span>' : '<span class="badge bg-secondary">RESOLVED</span>';
    html += `<tr>
      <td class="text-secondary small">${a.timestamp.slice(0,19).replace('T',' ')}</td>
      <td>${a.id}</td>
      <td>${a.message}</td>
      <td><span class="badge bg-${sc}">${(a.priority_label||'info').toUpperCase()}</span></td>
      <td>${state}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  wrapper.innerHTML = html;
}

// ---- Machine controls ----------------------------------------------------

async function machineCmd(cmd) {
  await siasFetch(`/api/plc/${cmd}`, { method: 'POST' });
}

// ---- Socket.IO handler ---------------------------------------------------

socket.on('data_update', (payload) => {
  const { plc } = payload;
  renderContacts(plc.contacts);
  renderCoils(plc.coils);
  renderLadder(plc);
  renderAlarmLog(plc.alarm_log, plc.active_alarms);

  document.getElementById('plc-tick').textContent = plc.tick;
  const mr = plc.coils.motor_run;
  const el = document.getElementById('motor-run-state');
  if (mr) {
    el.className = `badge ${mr.state ? 'bg-success' : 'bg-secondary'}`;
    el.textContent = mr.state ? 'ON' : 'OFF';
  }
  document.getElementById('plc-ts').textContent = new Date().toLocaleTimeString();
});
