(function () {
  if (window.RollCallAuth.getToken()) window.location.replace('summaries.html');

  const form = document.getElementById('register-form');
  const error = document.getElementById('error');
  const btn = document.getElementById('submit');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = form.username.value.trim();
    const password = form.password.value;
    const confirm = form.confirm.value;

    error.textContent = '';
    if (!username || !password) {
      error.textContent = 'Please fill in both fields.';
      return;
    }
    if (password !== confirm) {
      error.textContent = 'Passwords do not match.';
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Creating account…';
    try {
      await window.RollCallAuth.register(username, password);
      window.location.replace('summaries.html');
    } catch (err) {
      error.textContent = err.message;
      btn.disabled = false;
      btn.textContent = 'Create account';
    }
  });
})();
