// The only place that knows URLs and HTTP details.
(function () {
  const BASE = window.ROLLCALL.API_BASE;

  async function request(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    const token = window.RollCallAuth ? window.RollCallAuth.getToken() : null;
    if (token) headers['Authorization'] = 'Bearer ' + token;

    let res;
    try {
      res = await fetch(BASE + path, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new Error('Cannot reach the server. Is the mock API running?');
    }

    if (res.status === 401 && window.RollCallAuth) {
      window.RollCallAuth.clearAndRedirect();
      throw new Error('Session expired. Please log in again.');
    }

    let data = null;
    try { data = await res.json(); } catch (e) { /* non-JSON response */ }

    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || 'Request failed (' + res.status + ')';
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  window.RollCallAPI = {
    get: (path) => request('GET', path),
    post: (path, body) => request('POST', path, body),
    del: (path, body) => request('DELETE', path, body),
  };
})();
