(() => {
  'use strict';
  const industries = JSON.parse(document.getElementById('registry-industries').textContent);
  const singular = {customers: 'customer', sites: 'site', assets: 'asset'};
  const forms = [...document.querySelectorAll('.registry-form')];
  const message = document.getElementById('registry-message');
  const retry = document.getElementById('registry-retry');
  const search = document.getElementById('registry-search');
  const customerFilter = document.getElementById('filter-customer');
  const statusFilter = document.getElementById('filter-status');
  let data = {customers: [], sites: [], assets: []};
  let busy = false;

  function notify(text, error = false) {
    message.textContent = text;
    message.className = `alert ${error ? 'alert-danger' : 'alert-secondary'}`;
  }
  async function api(path, options = {}) {
    const response = await siasFetch(path, options);
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('Server returned an unexpected response.'); }
    if (!response.ok || !result.ok) throw new Error(result.error || 'Request failed.');
    return result;
  }
  function options(select, records, placeholder, label) {
    const previous = select.value;
    select.replaceChildren(new Option(placeholder, ''));
    records.forEach(record => select.add(new Option(label(record), String(record.id))));
    if (records.some(record => String(record.id) === previous)) select.value = previous;
  }
  function customerName(id) { return data.customers.find(record => record.id === id)?.name || 'Unknown customer'; }
  function siteLabel(site) { return `${customerName(site.customer_id)} / ${site.name}`; }
  function enableForms() {
    forms.forEach(form => {
      const blocked = form.dataset.kind === 'sites' ? !data.customers.length : form.dataset.kind === 'assets' ? !data.sites.length : false;
      form.querySelector('fieldset').disabled = busy || blocked || !(['admin', 'manager'].includes(SIAS_ROLE)) || (form.dataset.kind === 'customers' && SIAS_ROLE !== 'admin');
    });
  }
  async function load() {
    const result = await api('/api/registry');
    data = result;
    options(document.getElementById('site-customer'), data.customers, 'Choose customer', record => record.name);
    options(document.getElementById('asset-site'), data.sites, 'Choose site', siteLabel);
    options(customerFilter, data.customers, 'All customers', record => record.name);
    retry.hidden = true;
    render();
  }
  function reset(form) {
    form.reset();
    form.elements.namedItem('id').value = '';
    form.querySelector('[type=submit]').textContent = `Add ${singular[form.dataset.kind]}`;
    form.querySelector('.cancel-edit').hidden = true;
  }
  function edit(kind, record) {
    const form = document.getElementById(`form-${kind}`);
    for (const [field, value] of Object.entries(record)) {
      const input = form.elements.namedItem(field);
      if (input) input.value = value;
    }
    form.querySelector('[type=submit]').textContent = `Save ${singular[kind]}`;
    form.querySelector('.cancel-edit').hidden = false;
    form.scrollIntoView({behavior: 'smooth', block: 'center'});
    form.elements.namedItem('name').focus({preventScroll: true});
  }
  function render() {
    const query = search.value.trim().toLowerCase();
    const selectedCustomer = Number(customerFilter.value);
    for (const kind of Object.keys(singular)) {
      document.getElementById(`count-${kind}`).textContent = data[kind].length;
      const tbody = document.getElementById(`rows-${kind}`);
      tbody.replaceChildren();
      for (const record of data[kind]) {
        const site = kind === 'assets' ? data.sites.find(item => item.id === record.site_id) : null;
        const customerId = kind === 'customers' ? record.id : kind === 'sites' ? record.customer_id : site?.customer_id;
        if (selectedCustomer && customerId !== selectedCustomer) continue;
        if (kind === 'assets' && statusFilter.value && record.status !== statusFilter.value) continue;
        const industry = industries.find(item => item.id === record.industry)?.name || record.industry;
        const values = kind === 'customers' ? [record.name, industry] : kind === 'sites' ? [record.name, customerName(record.customer_id), record.location] : [record.name, site ? siteLabel(site) : 'Unknown site', record.asset_type, record.serial_number, record.criticality, record.status];
        if (query && !values.join(' ').toLowerCase().includes(query)) continue;
        const tr = document.createElement('tr');
        values.forEach(value => { const td = document.createElement('td'); td.textContent = value || '—'; tr.append(td); });
        const actions = document.createElement('td');
        for (const action of (['admin', 'manager'].includes(SIAS_ROLE) && (kind !== 'customers' || SIAS_ROLE === 'admin') ? ['Edit', 'Delete'] : [])) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = `btn btn-sm ${action === 'Edit' ? 'btn-outline-info' : 'btn-outline-danger'} me-1`;
          button.textContent = action;
          button.setAttribute('aria-label', `${action} ${singular[kind]} ${record.name}`);
          button.disabled = busy;
          button.addEventListener('click', () => action === 'Edit' ? edit(kind, record) : remove(kind, record));
          actions.append(button);
        }
        tr.append(actions); tbody.append(tr);
      }
      if (!tbody.children.length) {
        const td = document.createElement('td');
        td.colSpan = kind === 'assets' ? 7 : kind === 'sites' ? 4 : 3;
        td.textContent = data[kind].length ? 'No matching records.' : `No ${kind} yet. Add your first ${singular[kind]} above.`;
        const tr = document.createElement('tr'); tr.append(td); tbody.append(tr);
      }
    }
  }
  async function mutate(path, options, success, onSuccess) {
    if (busy) return;
    busy = true; enableForms(); render();
    let saved = false;
    try {
      await api(path, options);
      saved = true;
      onSuccess?.();
      await load();
      notify(success);
    } catch (error) {
      notify(saved ? `${success} Refresh failed: ${error.message} Retry loading to see the latest records.` : error.message, true);
      if (saved) retry.hidden = false;
    } finally { busy = false; enableForms(); render(); }
  }
  async function remove(kind, record) {
    if (busy || !window.confirm(`Delete ${singular[kind]} “${record.name}”? This cannot be undone. Records with dependent sites or assets cannot be deleted.`)) return;
    await mutate(`/api/registry/${kind}/${record.id}`, {method: 'DELETE'}, 'Record deleted.', () => {
      const form = document.getElementById(`form-${kind}`);
      if (form.elements.namedItem('id').value === String(record.id)) reset(form);
    });
  }
  forms.forEach(form => {
    form.querySelector('.cancel-edit').addEventListener('click', () => reset(form));
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(form));
      const id = values.id;
      delete values.id;
      ['customer_id', 'site_id'].forEach(field => { if (field in values) values[field] = Number(values[field]); });
      await mutate(`/api/registry/${form.dataset.kind}${id ? `/${id}` : ''}`, {method: id ? 'PATCH' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values)}, `${singular[form.dataset.kind]} saved.`, () => reset(form));
    });
  });
  [search, customerFilter, statusFilter].forEach(input => input.addEventListener('input', render));
  async function refresh() {
    if (busy) return;
    busy = true; enableForms();
    try { await load(); notify('Registry ready. Add customers, then sites, then equipment.'); }
    catch (error) { notify(error.message, true); retry.hidden = false; }
    finally { busy = false; enableForms(); render(); }
  }
  retry.addEventListener('click', refresh);
  refresh();
})();
