(() => {
  'use strict';
  const el = id => document.getElementById(id), select = el('telemetry-asset');
  let snapshot = null, chart = null, requestId = 0, credentialBusy = false;
  async function api(path, options = {}) {
    const response = await siasFetch(path, options);
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || 'Request failed.');
    return result;
  }
  function hideToken() {
    if (el('telemetry-token')) el('telemetry-token').value = '';
    if (el('telemetry-secret')) el('telemetry-secret').hidden = true;
  }
  function resetDetail() {
    ++requestId; snapshot = null;
    el('telemetry-detail').hidden = true;
    hideToken();
    if (chart) { chart.destroy(); chart = null; }
  }
  async function loadAssets() {
    const result = await api('/api/registry');
    const previous = select.value;
    select.replaceChildren(new Option('Choose equipment', ''));
    result.assets.forEach(asset => {
      const site = result.sites.find(item => item.id === asset.site_id);
      const customer = result.customers.find(item => item.id === site?.customer_id);
      select.add(new Option(`${customer?.name} / ${site?.name} / ${asset.name} (#${asset.id})`, String(asset.id)));
    });
    select.disabled = false;
    if ([...select.options].some(option => option.value === previous)) select.value = previous;
    el('telemetry-message').textContent = result.assets.length ? 'Choose an asset to monitor its readings.' : 'No registered equipment yet. Add an asset in the registry first.';
  }
  function drawChart() {
    if (chart) { chart.destroy(); chart = null; }
    if (!snapshot || !el('telemetry-channel').value) return;
    const [channel, unit] = JSON.parse(el('telemetry-channel').value);
    const history = [...snapshot.history].reverse();
    chart = new Chart(el('telemetry-chart'), {type: 'line', data: {
      labels: history.map(batch => new Date(batch.timestamp).toLocaleString()),
      datasets: [{label: `${channel} (${unit})`, data: history.map(batch => batch.readings[channel]?.unit === unit ? batch.readings[channel].value : null), borderColor: '#0dcaf0', tension: 0.1, spanGaps: false}]
    }, options: {responsive: true, maintainAspectRatio: false, animation: false, scales: {y: {title: {display: true, text: unit}}}}});
  }
  function render() {
    el('telemetry-detail').hidden = false;
    const labels = {never_seen: 'Never received data', stale: 'Stale data', connected: 'Receiving recent data'};
    el('telemetry-status').textContent = labels[snapshot.connection_status];
    el('telemetry-status').className = snapshot.connection_status === 'connected' ? 'text-success' : 'text-warning';
    el('telemetry-times').textContent = snapshot.latest ? `Latest measured: ${new Date(snapshot.latest.timestamp).toLocaleString()} · Last received: ${new Date(snapshot.last_received_at).toLocaleString()}` : 'Waiting for the gateway to send its first readings.';
    const readings = el('telemetry-readings'); readings.replaceChildren();
    Object.entries(snapshot.latest?.readings || {}).forEach(([name, reading]) => {
      const col = document.createElement('div'); col.className = 'col-sm-6 col-lg-3';
      const card = document.createElement('div'); card.className = 'card bg-dark border-secondary p-3';
      const label = document.createElement('span'); label.textContent = name;
      const value = document.createElement('strong'); value.className = 'fs-4'; value.textContent = `${reading.value} ${reading.unit}`;
      card.append(label, value); col.append(card); readings.append(col);
    });
    const rows = el('telemetry-history'); rows.replaceChildren();
    snapshot.history.forEach(batch => {
      const tr = document.createElement('tr');
      [new Date(batch.timestamp).toLocaleString(), new Date(batch.received_at).toLocaleString(), Object.entries(batch.readings).map(([name, reading]) => `${name}: ${reading.value} ${reading.unit}`).join(' · ')].forEach(value => { const td = document.createElement('td'); td.textContent = value; tr.append(td); }); rows.append(tr);
    });
    if (!snapshot.history.length) { const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 3; td.textContent = 'No readings received.'; tr.append(td); rows.append(tr); }
    const channels = el('telemetry-channel'), previous = channels.value, combinations = new Map();
    snapshot.history.forEach(batch => Object.entries(batch.readings).forEach(([name, reading]) => combinations.set(JSON.stringify([name, reading.unit]), `${name} (${reading.unit})`)));
    channels.replaceChildren(); combinations.forEach((label, key) => channels.add(new Option(label, key)));
    if (combinations.has(previous)) channels.value = previous;
    el('telemetry-trend').hidden = !combinations.size;
    drawChart();
    if (el('telemetry-credential-status')) {
      el('telemetry-credential-status').textContent = snapshot.credential_configured ? `Credential configured · rotated ${new Date(snapshot.credential_rotated_at).toLocaleString()}` : 'No active gateway credential.';
      el('telemetry-revoke').disabled = credentialBusy || !snapshot.credential_configured;
      el('telemetry-endpoint').textContent = `/api/telemetry/${select.value}/readings`;
    }
  }
  async function refresh() {
    if (!select.value) return;
    const id = select.value, request = ++requestId;
    try {
      const result = await api(`/api/telemetry/${id}`);
      if (request !== requestId || select.value !== id) return;
      snapshot = result; render(); el('telemetry-message').textContent = `Updated ${new Date().toLocaleTimeString()}`;
    } catch(error) {
      if (request !== requestId) return;
      el('telemetry-message').textContent = `Unable to refresh: ${error.message}`;
      el('telemetry-status').textContent = 'Connection status unavailable — refresh failed';
      el('telemetry-status').className = 'text-warning';
    }
  }
  async function credential(revoke) {
    if (!select.value || credentialBusy) return;
    if (!window.confirm(revoke ? 'Revoke this asset’s gateway credential? Submissions using it will stop.' : 'Generate a new gateway credential? The previous credential will stop working.')) return;
    credentialBusy = true;
    const id = select.value;
    el('telemetry-rotate').disabled = true; el('telemetry-revoke').disabled = true; select.disabled = true;
    hideToken();
    try {
      const result = await api(`/api/telemetry/${id}/credential`, {method: revoke ? 'DELETE' : 'POST'});
      if (select.value !== id) return;
      if (result.token) { el('telemetry-token').value = result.token; el('telemetry-secret').hidden = false; }
      await refresh();
      el('telemetry-message').textContent = revoke ? 'Gateway credential revoked.' : 'Credential created. Copy it now; it cannot be retrieved later.';
    } catch(error) { el('telemetry-message').textContent = error.message; }
    finally { credentialBusy = false; el('telemetry-rotate').disabled = false; select.disabled = false; el('telemetry-revoke').disabled = !snapshot?.credential_configured; }
  }
  select.addEventListener('change', () => { resetDetail(); if (select.value) refresh(); });
  el('telemetry-channel').addEventListener('change', drawChart);
  el('telemetry-refresh').addEventListener('click', async () => {
    if (select.value) await refresh();
    else { try { await loadAssets(); } catch(error) { el('telemetry-message').textContent = error.message; } }
  });
  el('telemetry-rotate')?.addEventListener('click', () => credential(false));
  el('telemetry-revoke')?.addEventListener('click', () => credential(true));
  el('telemetry-hide-token')?.addEventListener('click', hideToken);
  window.addEventListener('pagehide', hideToken);
  loadAssets().catch(error => { el('telemetry-message').textContent = error.message; });
  setInterval(() => { if (!document.hidden && !credentialBusy) refresh(); }, 10000);
})();
