(() => {
  const form = document.getElementById('users-form'), message = document.getElementById('users-message');
  const field = name => form.elements.namedItem(name);
  let busy = false;
  async function api(path, options = {}) {
    const response = await siasFetch(path, options), result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed.');
    return result;
  }
  function role() { field('customer_id').disabled = field('role').value === 'admin'; field('customer_id').required = field('role').value !== 'admin'; }
  function reset() { form.reset(); field('id').value = ''; field('password').required = true; role(); }
  async function load() {
    const [accounts, registry] = await Promise.all([api('/api/auth/users'), api('/api/registry')]);
    const previous = field('customer_id').value;
    field('customer_id').replaceChildren(new Option('Choose customer', ''));
    registry.customers.forEach(customer => field('customer_id').add(new Option(customer.name, customer.id)));
    field('customer_id').value = previous;
    const rows = document.getElementById('users-rows'); rows.replaceChildren();
    accounts.users.forEach(user => {
      const tr = document.createElement('tr');
      [user.username, user.name, user.role, registry.customers.find(c => c.id === user.customer_id)?.name || 'All customers', user.active ? 'Active' : 'Disabled'].forEach(value => { const td = document.createElement('td'); td.textContent = value; tr.append(td); });
      const td = document.createElement('td'), edit = document.createElement('button'); edit.className = 'btn btn-sm btn-outline-info'; edit.textContent = 'Edit';
      edit.addEventListener('click', () => {
        if (busy) return;
        for (const [key, value] of Object.entries(user)) { if (field(key)) { if (key === 'active') field(key).checked = Boolean(value); else field(key).value = value ?? ''; } }
        field('password').value = ''; field('password').required = false; role(); form.scrollIntoView({behavior:'smooth'});
      }); td.append(edit); tr.append(td); rows.append(tr);
    });
    message.textContent = 'Accounts ready.';
  }
  async function refresh() {
    if (busy) return; busy = true; form.querySelector('fieldset').disabled = true;
    try { await load(); } catch (error) { message.textContent = error.message; }
    finally { busy = false; form.querySelector('fieldset').disabled = false; role(); }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    const values = Object.fromEntries(new FormData(form)), id = values.id; delete values.id;
    values.active = field('active').checked; values.customer_id = values.role === 'admin' ? null : Number(values.customer_id);
    if (id && !values.password) delete values.password;
    busy = true; form.querySelector('fieldset').disabled = true;
    try {
      await api(`/api/auth/users${id ? `/${id}` : ''}`, {method: id ? 'PATCH' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(values)});
      const me = await api('/api/auth/me');
      if (!me.user) { window.location.assign('/login'); return; }
      reset(); await load(); message.textContent = 'Account saved.';
    } catch(error) { message.textContent = error.message; }
    finally { busy = false; form.querySelector('fieldset').disabled = false; role(); }
  });
  document.getElementById('users-retry').addEventListener('click', refresh);
  document.getElementById('user-reset').addEventListener('click', reset);
  field('role').addEventListener('change', role);
  reset(); refresh();
})();
