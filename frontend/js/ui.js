// Nav render, toasts, escapeHtml, date formatting, empty states, confirm modal.
(function () {
  const PAGES = [
    { href: 'summaries.html', label: 'Summaries' },
    { href: 'config.html', label: 'Config' },
    { href: 'chats.html', label: 'Chats' },
  ];

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  function renderNav(active) {
    const user = window.RollCallAuth.currentUsername();
    const el = document.createElement('header');
    el.className = 'nav';
    el.innerHTML = `
      <div class="nav-inner">
        <button class="nav-toggle" id="nav-toggle" aria-label="Menu">☰</button>
        <a class="wordmark" href="summaries.html">Roll<span class="tick">-</span>Call</a>
        <nav class="nav-links" id="nav-links">
          ${PAGES.map((p) => `<a href="${p.href}" class="${p.href === active ? 'active' : ''}">${p.label}</a>`).join('')}
        </nav>
        <div class="nav-right">
          <span class="nav-user">${escapeHtml(user)}</span>
          <button class="btn btn-ghost btn-sm" id="logout-btn">Log out</button>
        </div>
      </div>`;
    document.body.prepend(el);
    el.querySelector('#logout-btn').addEventListener('click', window.RollCallAuth.logout);
    el.querySelector('#nav-toggle').addEventListener('click', (e) => {
      e.stopPropagation();
      el.querySelector('#nav-links').classList.toggle('open');
    });
    // Tap/click anywhere outside the nav closes the mobile menu.
    document.addEventListener('click', (e) => {
      if (!el.contains(e.target)) el.querySelector('#nav-links').classList.remove('open');
    });
  }

  function toast(message, isError) {
    let holder = document.querySelector('.toasts');
    if (!holder) {
      holder = document.createElement('div');
      holder.className = 'toasts';
      document.body.appendChild(holder);
    }
    const t = document.createElement('div');
    t.className = 'toast' + (isError ? ' error' : '');
    t.textContent = message;
    holder.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  // UTC date helpers — dates are UTC end-to-end (plan §9.6).
  function todayUTC() { return new Date().toISOString().slice(0, 10); }

  function relTime(iso) {
    const then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    const s = Math.max(0, (Date.now() - then) / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    return Math.floor(s / 86400) + 'd ago';
  }

  function emptyState(title, sub) {
    return `<div class="empty">
      <div class="empty-title">${escapeHtml(title)}</div>
      <div>${escapeHtml(sub || '')}</div>
    </div>`;
  }

  // Confirm modal: returns a Promise<boolean>.
  function confirm(message) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML = `
        <div class="modal" role="dialog" aria-modal="true">
          <h3>Are you sure?</h3>
          <p>${escapeHtml(message)}</p>
          <div class="modal-actions">
            <button class="btn btn-ghost" data-no>Cancel</button>
            <button class="btn btn-danger" data-yes>Remove</button>
          </div>
        </div>`;
      const done = (v) => { overlay.remove(); resolve(v); };
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) done(false);
        if (e.target.closest('[data-yes]')) done(true);
        if (e.target.closest('[data-no]')) done(false);
      });
      document.body.appendChild(overlay);
    });
  }

  window.RollCallUI = { escapeHtml, renderNav, toast, todayUTC, relTime, emptyState, confirm };
})();
