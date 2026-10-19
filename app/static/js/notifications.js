(() => {
  const message = document.getElementById('notice-message'), rows = document.getElementById('notice-rows'), filter = document.getElementById('notice-status');
  let notices = [], busy = false;
  function render() {
    rows.replaceChildren();
    const visible = notices.filter(notice => !filter.value || notice.status === filter.value);
    visible.forEach(notice => {
      const tr = document.createElement('tr');
      [notice.subject, `${notice.recipient_name}${(notice.sent_to || notice.recipient_email) ? ` (${notice.sent_to || notice.recipient_email})` : ' (email missing)'}`, `${notice.status} · ${notice.attempts} attempts${notice.last_error ? ` — ${notice.last_error}` : ''}`, new Date(notice.created_at).toLocaleString()].forEach(value => { const td = document.createElement('td'); td.textContent = value; tr.append(td); });
      const td = document.createElement('td');
      if (SIAS_ROLE === 'admin' && ['failed', 'skipped'].includes(notice.status)) {
        const retry = document.createElement('button'); retry.textContent = 'Retry'; retry.className = 'btn btn-sm btn-outline-info'; retry.disabled = busy;
        retry.addEventListener('click', () => retryNotice(notice.id)); td.append(retry);
      }
      tr.append(td); rows.append(tr);
    });
    if (!visible.length) { const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 5; td.textContent = 'No matching notifications.'; tr.append(td); rows.append(tr); }
    message.textContent = `${visible.length} of ${notices.length} notifications`;
  }
  async function load() {
    const response = await siasFetch('/api/notifications'), result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Unable to load notifications.');
    notices = result.notifications;
  }
  async function retryNotice(id) {
    if (busy) return; busy = true; render();
    try {
      const response = await siasFetch(`/api/notifications/${id}/retry`, {method: 'POST'}), result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Retry failed.');
      await load();
    } catch(error) { message.textContent = error.message; }
    finally { busy = false; const error = message.textContent; render(); if (!/^\d+ of/.test(error)) message.textContent = error; }
  }
  async function refresh() {
    if (busy) return; busy = true; document.getElementById('notice-refresh').disabled = true;
    try { await load(); render(); } catch(error) { message.textContent = error.message; }
    finally { busy = false; document.getElementById('notice-refresh').disabled = false; renderButtons(); }
  }
  function renderButtons() { rows.querySelectorAll('button').forEach(button => { button.disabled = busy; }); }
  filter.addEventListener('change', render);
  document.getElementById('notice-refresh').addEventListener('click', refresh);
  refresh();
})();
