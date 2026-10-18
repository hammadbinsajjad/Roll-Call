(function () {
  if (window.RollCallAuth.getToken()) window.location.replace('summaries.html');

  const form = document.getElementById('login-form');
  const error = document.getElementById('error');
  const btn = document.getElementById('submit');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = form.username.value.trim();
    const password = form.password.value;

    error.textContent = '';
    if (!username || !password) {
      error.textContent = 'Please fill in both fields.';
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Logging in…';
    try {
      await window.RollCallAuth.login(username, password);
      window.location.replace('summaries.html');
    } catch (err) {
      error.textContent = err.message;
      btn.disabled = false;
      btn.textContent = 'Log in';
    }
  });
})();
