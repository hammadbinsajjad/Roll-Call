// Token storage, login/register/logout, route guard.
(function () {
  const KEY = 'rollcall_token';
  const USER_KEY = 'rollcall_username';

  function getToken() { return localStorage.getItem(KEY); }
  function setSession(token, username) {
    localStorage.setItem(KEY, token);
    localStorage.setItem(USER_KEY, username);
  }
  function clearAndRedirect() {
    localStorage.removeItem(KEY);
    localStorage.removeItem(USER_KEY);
    window.location.replace('login.html');
  }

  async function login(username, password) {
    const data = await window.RollCallAPI.post('/auth/login', { username, password });
    setSession(data.token, data.username || username);
  }

  async function register(username, password) {
    const data = await window.RollCallAPI.post('/auth/register', { username, password });
    setSession(data.token, data.username || username);
  }

  function logout() {
    localStorage.removeItem(KEY);
    localStorage.removeItem(USER_KEY);
    window.location.replace('login.html');
  }

  // Guard: all pages except login/register include this and run it on load.
  function requireAuth() {
    if (!getToken()) window.location.replace('login.html');
  }

  function currentUsername() { return localStorage.getItem(USER_KEY) || ''; }

  window.RollCallAuth = { getToken, setSession, clearAndRedirect, login, register, logout, requireAuth, currentUsername };
})();
