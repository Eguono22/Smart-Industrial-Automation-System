(() => {
  const form = document.getElementById('login-form');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button'); button.disabled = true;
    try {
      const response = await siasFetch('/api/auth/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(Object.fromEntries(new FormData(form)))});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Login failed.');
      window.location.assign('/assets');
    } catch (error) { document.getElementById('login-message').textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
