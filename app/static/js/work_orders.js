(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const form = el('work-form');
  const field = name => form.elements.namedItem(name);
  let orders = [], assets = [], busy = false, ready = false, detailRequest = 0, technicians = [], originalAssignee = null;
  const statusName = value => value.replaceAll('_', ' ');
  function notify(text, error = false) {
    el('work-message').textContent = text;
    el('work-message').className = `alert ${error ? 'alert-danger' : 'alert-secondary'}`;
  }
  async function api(path, options = {}) {
    const response = await siasFetch(path, options);
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('Unexpected server response.'); }
    if (!response.ok || !result.ok) throw new Error(result.error || 'Request failed.');
    return result;
  }
  function lock() {
    form.querySelector('fieldset').disabled = busy || !ready || !assets.length || !(SIAS_ROLE === 'admin' || SIAS_ROLE === 'manager' || (SIAS_ROLE === 'technician' && field('id').value));
    field('asset_id').disabled = Boolean(field('id').value);
    ['title', 'description', 'priority', 'assignee_id', 'due_date'].forEach(name => { field(name).disabled = SIAS_ROLE === 'technician'; });
    el('work-retry').disabled = busy;
  }
  function reset() {
    form.reset(); field('id').value = ''; originalAssignee = null; assignmentOptions();
    el('work-form-heading').textContent = 'Create work order';
    form.querySelector('[type=submit]').textContent = 'Create work order';
    el('work-cancel-edit').hidden = true;
    field('completion_notes').required = false;
    lock();
  }
  function fillOptions(select, placeholder) {
    const previous = select.value;
    select.replaceChildren(new Option(placeholder, ''));
    assets.forEach(asset => select.add(new Option(asset.label, String(asset.id))));
    if (assets.some(asset => String(asset.id) === previous)) select.value = previous;
  }
  async function load() {
    const [registry, result, people] = await Promise.all([api('/api/registry'), api('/api/work-orders'), api('/api/auth/technicians')]);
    technicians = people.technicians;
    assets = registry.assets.map(asset => {
      const site = registry.sites.find(item => item.id === asset.site_id);
      const customer = registry.customers.find(item => item.id === site?.customer_id);
      return {...asset, customer_id: site?.customer_id, label: `${customer?.name || ''} / ${site?.name || ''} / ${asset.name} (#${asset.id})`};
    });
    orders = result.work_orders;
    fillOptions(field('asset_id'), 'Choose asset');
    fillOptions(el('work-filter-asset'), 'All assets');
    assignmentOptions();
    ready = true;
    el('work-retry').hidden = true;
  }
  function assignmentOptions(order = null) {
    const select = field('assignee_id'), previous = order ? String(order.assignee_id || '') : select.value;
    const asset = assets.find(item => String(item.id) === field('asset_id').value);
    select.replaceChildren(new Option('Unassigned', ''));
    technicians.filter(item => item.customer_id === asset?.customer_id).forEach(item => select.add(new Option(item.name, String(item.id))));
    if (order?.assignee_id && !technicians.some(item => item.id === order.assignee_id)) select.add(new Option(`${order.assignee} (previous assignment)`, String(order.assignee_id)));
    if ([...select.options].some(option => option.value === previous)) select.value = previous;
  }
  function render() {
    el('work-summary').textContent = `${orders.length} work orders · ${orders.filter(item => item.status === 'open' || item.status === 'in_progress').length} active · ${orders.filter(item => item.overdue).length} overdue`;
    const query = el('work-search').value.trim().toLowerCase();
    const filtered = orders.filter(order =>
      (!el('work-filter-asset').value || String(order.asset_id) === el('work-filter-asset').value) &&
      (!el('work-filter-status').value || order.status === el('work-filter-status').value) &&
      (!el('work-overdue').checked || order.overdue) &&
      (!query || [order.id, order.title, order.description, order.assignee, order.asset_name, order.site_name, order.customer_name, order.completion_notes].join(' ').toLowerCase().includes(query)));
    const rows = el('work-rows'); rows.replaceChildren();
    filtered.forEach(order => {
      const tr = document.createElement('tr');
      const values = [`#${order.id} ${order.title}\n${order.customer_name} / ${order.site_name} / ${order.asset_name}`, `${order.priority}\n${order.assignee || 'Unassigned'}`, `${order.due_date}\n${statusName(order.status)}${order.overdue ? ' · OVERDUE' : ''}`];
      values.forEach(value => { const td = document.createElement('td'); td.textContent = value; td.style.whiteSpace = 'pre-line'; tr.append(td); });
      const actions = document.createElement('td');
      const canEdit = ['admin', 'manager'].includes(SIAS_ROLE) || (SIAS_ROLE === 'technician' && order.assignee_id === SIAS_USER_ID);
      for (const action of (canEdit ? ['Edit', 'History'] : ['History'])) {
        const button = document.createElement('button'); button.type = 'button';
        button.textContent = action; button.className = 'btn btn-sm btn-outline-info me-1 mb-1';
        button.disabled = busy; button.setAttribute('aria-label', `${action} work order ${order.id}`);
        button.addEventListener('click', () => action === 'Edit' ? edit(order) : history(order));
        actions.append(button);
      }
      tr.append(actions); rows.append(tr);
    });
    if (!filtered.length) {
      const tr = document.createElement('tr'), td = document.createElement('td');
      td.colSpan = 4; td.textContent = orders.length ? 'No work orders match these filters.' : 'No work orders yet. Create your first task for a registered asset.';
      tr.append(td); rows.append(tr);
    }
    el('work-count').textContent = `${filtered.length} of ${orders.length} work orders`;
  }
  function edit(order) {
    Object.keys(order).forEach(name => { const input = field(name); if (input) input.value = order[name] ?? ''; });
    originalAssignee = order.assignee_id; assignmentOptions(order);
    el('work-form-heading').textContent = `Edit work order #${order.id}`;
    form.querySelector('[type=submit]').textContent = 'Save work order';
    el('work-cancel-edit').hidden = false;
    field('completion_notes').required = field('status').value === 'completed';
    lock(); form.scrollIntoView({behavior: 'smooth', block: 'start'}); field('title').focus({preventScroll: true});
  }
  async function history(order) {
    const request = ++detailRequest;
    el('work-detail').hidden = false;
    el('work-detail-heading').textContent = `Work order #${order.id}: ${order.title}`;
    el('work-history').textContent = 'Loading history…';
    try {
      const result = await api(`/api/work-orders/${order.id}`);
      if (request !== detailRequest) return;
      el('work-history').replaceChildren();
      result.record.history.forEach(event => {
        const item = document.createElement('div'); item.className = 'border-bottom border-secondary py-2';
        const snapshot = event.snapshot;
        item.textContent = `${new Date(event.changed_at).toLocaleString()} · ${event.actor_name || 'Legacy record (actor unknown)'} — ${statusName(snapshot.status)}\n${snapshot.title}\n${snapshot.description || 'No description'}\nPriority: ${snapshot.priority}; assigned to: ${snapshot.assignee || 'Unassigned'}; due: ${snapshot.due_date}\nCompletion notes: ${snapshot.completion_notes || 'None'}`;
        item.style.whiteSpace = 'pre-wrap'; el('work-history').append(item);
      });
    } catch (error) { if (request === detailRequest) el('work-history').textContent = error.message; }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !ready) return;
    let values = Object.fromEntries(new FormData(form));
    const id = values.id; delete values.id;
    if (SIAS_ROLE === 'technician') values = {status: values.status, completion_notes: values.completion_notes};
    else {
      values.assignee_id = values.assignee_id ? Number(values.assignee_id) : null;
      if (id && values.assignee_id === originalAssignee) delete values.assignee_id;
    }
    // Existing asset links are immutable and disabled selects are omitted by FormData.
    if (!id) values.asset_id = Number(values.asset_id);
    busy = true; lock(); render();
    let saved = false;
    try {
      await api(`/api/work-orders${id ? `/${id}` : ''}`, {method: id ? 'PATCH' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values)});
      saved = true; reset(); ++detailRequest; el('work-detail').hidden = true;
      await load(); notify('Work order saved.');
    } catch (error) {
      notify(saved ? `Work order saved, but refreshing failed: ${error.message}` : error.message, true);
      if (saved) { ready = false; el('work-retry').hidden = false; }
    } finally { busy = false; lock(); render(); }
  });
  field('asset_id').addEventListener('change', () => assignmentOptions());
  field('status').addEventListener('change', () => { field('completion_notes').required = field('status').value === 'completed'; });
  el('work-cancel-edit').addEventListener('click', reset);
  ['work-search', 'work-filter-asset', 'work-filter-status', 'work-overdue'].forEach(id => el(id).addEventListener('input', render));
  async function refresh() {
    if (busy) return;
    busy = true; lock(); render();
    try { await load(); notify(assets.length ? 'Ready to plan maintenance.' : 'Add equipment in the asset registry to create work orders.'); }
    catch (error) { ready = false; notify(error.message, true); el('work-retry').hidden = false; }
    finally { busy = false; lock(); render(); }
  }
  el('work-retry').addEventListener('click', refresh);
  refresh();
})();
