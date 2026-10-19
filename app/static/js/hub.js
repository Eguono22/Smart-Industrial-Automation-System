/* Industry discovery and browser-local solution planning. */
(() => {
  'use strict';
  const catalog = JSON.parse(document.getElementById('hub-catalog').textContent);
  const industry = document.getElementById('plan-industry');
  const customer = document.getElementById('plan-customer');
  const notes = document.getElementById('plan-notes');
  const checks = [...document.querySelectorAll('.capability-check')];
  const message = document.getElementById('plan-message');
  const storageKey = `sias-hub-plan-v1-${SIAS_USER_ID || 'guest'}`;
  const profile = () => catalog.industries.find(item => item.id === industry.value);
  const selected = () => catalog.capabilities.filter(item => checks.some(check => check.value === item.id && check.checked));

  function update() {
    const current = profile();
    document.getElementById('plan-context').textContent = `Potential customers: ${current.customers}. Typical assets: ${current.assets}. Target KPIs: ${current.kpis}.`;
    const capabilities = selected();
    const available = capabilities.filter(item => item.status === 'Available').length;
    document.getElementById('plan-summary').textContent = `${capabilities.length} selected · ${available} available · ${capabilities.length - available} planned`;
    document.getElementById('plan-export').disabled = capabilities.length === 0;
  }
  function save() {
    update();
    try {
      localStorage.setItem(storageKey, JSON.stringify({industry: industry.value, customer: customer.value, notes: notes.value, capabilities: selected().map(item => item.id)}));
      message.textContent = 'Plan saved in this browser.';
    } catch (_) {
      message.textContent = 'Browser storage unavailable. Export your plan to keep a copy.';
    }
  }
  function suggest() {
    checks.forEach(check => { check.checked = profile().capabilities.includes(check.value); });
    save();
  }
  let restored = false;
  try {
    const plan = JSON.parse(localStorage.getItem(storageKey));
    if (plan && catalog.industries.some(item => item.id === plan.industry) && Array.isArray(plan.capabilities)) {
      industry.value = plan.industry;
      customer.value = typeof plan.customer === 'string' ? plan.customer.slice(0, 160) : '';
      notes.value = typeof plan.notes === 'string' ? plan.notes.slice(0, 4000) : '';
      checks.forEach(check => { check.checked = plan.capabilities.includes(check.value); });
      restored = true;
    }
  } catch (_) { /* Invalid or unavailable storage falls back to suggestions. */ }
  if (restored) update(); else suggest();
  industry.addEventListener('change', suggest);
  checks.forEach(check => check.addEventListener('change', save));
  [customer, notes].forEach(input => input.addEventListener('input', save));
  document.getElementById('plan-reset').addEventListener('click', suggest);
  document.querySelectorAll('.select-industry').forEach(button => button.addEventListener('click', () => {
    industry.value = button.dataset.industry;
    suggest();
    document.getElementById('planner').scrollIntoView({behavior: 'smooth'});
    industry.focus({preventScroll: true});
  }));
  const cards = [...document.querySelectorAll('.industry-item')];
  document.getElementById('industry-search').addEventListener('input', event => {
    const terms = event.target.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    cards.forEach(card => { card.hidden = !terms.every(term => card.dataset.search.includes(term)); });
    count();
  });
  function count() {
    const visible = cards.filter(card => !card.hidden).length;
    document.getElementById('industry-count').textContent = `${visible} of ${cards.length} industries`;
    document.getElementById('industry-empty').hidden = visible !== 0;
  }
  count();
  document.getElementById('capability-status').addEventListener('change', event => {
    document.querySelectorAll('.capability-item').forEach(item => {
      item.hidden = event.target.value !== 'all' && item.dataset.status !== event.target.value;
    });
  });
  document.getElementById('plan-export').addEventListener('click', () => {
    const plan = {schema_version: 1, created_at: new Date().toISOString(), customer: customer.value.trim(), industry: profile(), capabilities: selected(), notes: notes.value.trim(), scope: 'Discovery plan. Available capabilities cover the single-machine SIAS demo and persistent asset-linked work orders. Planned capabilities require implementation; no deployment or certification is implied.'};
    const url = URL.createObjectURL(new Blob([JSON.stringify(plan, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = `sias-solution-${industry.value}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    message.textContent = 'Solution plan exported.';
  });
})();
