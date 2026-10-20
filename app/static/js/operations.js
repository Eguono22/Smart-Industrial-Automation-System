(() => {
  'use strict';
  const input = document.getElementById('module-search');
  const rows = [...document.querySelectorAll('#module-rows tr')];
  input.addEventListener('input', () => {
    const terms = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    rows.forEach(row => { row.hidden = !terms.every(term => row.textContent.toLowerCase().includes(term)); });
    const visible = rows.filter(row => !row.hidden).length;
    document.getElementById('module-count').textContent = `${visible} of ${rows.length} example records`;
    document.getElementById('module-empty').hidden = visible > 0;
  });
})();
