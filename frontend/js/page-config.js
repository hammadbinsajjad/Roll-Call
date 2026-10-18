window.RollCallAuth.requireAuth();
window.RollCallUI.renderNav('config.html');

(function () {
  const UI = window.RollCallUI, API = window.RollCallAPI;
  const REPO_RE = /^[^/\s]+\/[^/\s]+$/;

  function renderRepos(repos) {
    const el = document.getElementById('repo-rows');
    if (!repos.length) {
      el.innerHTML = UI.emptyState('No repositories yet', 'Add owner/repo above to start watching.');
      return;
    }
    el.innerHTML = repos.map((r) => `
      <div class="config-row">
        <div class="row-main"><span class="row-title">${UI.escapeHtml(r)}</span></div>
        <button class="btn btn-danger btn-sm" data-remove-repo="${UI.escapeHtml(r)}">Remove</button>
      </div>`).join('');
  }

  function renderMembers(members) {
    const el = document.getElementById('member-rows');
    if (!members.length) {
      el.innerHTML = UI.emptyState('No team members yet', 'Add teammates so standups can be summarized.');
      return;
    }
    el.innerHTML = members.map((m) => `
      <div class="config-row">
        <div class="row-main">
          <div class="row-title">${UI.escapeHtml(m.member_name || m.github_username)}</div>
          <div class="row-sub">@${UI.escapeHtml(m.github_username)} · ${UI.escapeHtml(m.linear_email)}</div>
        </div>
        <button class="btn btn-danger btn-sm" data-remove-member="${UI.escapeHtml(m.github_username)}">Remove</button>
      </div>`).join('');
  }

  async function load() {
    try {
      const cfg = await API.get('/config');
      renderRepos(cfg.repos || []);
      renderMembers(cfg.team_members || []);
    } catch (err) {
      UI.toast(err.message, true);
    }
  }

  document.getElementById('repo-add').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('repo-input');
    const errEl = document.getElementById('repo-error');
    const name = input.value.trim();
    errEl.textContent = '';
    if (!REPO_RE.test(name)) {
      errEl.textContent = 'Use the format owner/repo, e.g. acme/roll-call.';
      return;
    }
    try {
      const cfg = await API.post('/config/repos', { name });
      renderRepos(cfg.repos);
      input.value = '';
      UI.toast('Added ' + name);
    } catch (err) {
      errEl.textContent = err.message;
    }
  });

  document.getElementById('member-add').addEventListener('submit', async (e) => {
    e.preventDefault();
    const github = document.getElementById('member-github').value.trim();
    const email = document.getElementById('member-email').value.trim();
    const name = document.getElementById('member-name').value.trim();
    const errEl = document.getElementById('member-error');
    errEl.textContent = '';
    if (!github || !email || !name) {
      errEl.textContent = 'All three fields are required.';
      return;
    }
    try {
      const cfg = await API.post('/config/members', {
        github_username: github, linear_email: email, member_name: name,
      });
      renderMembers(cfg.team_members);
      document.getElementById('member-add').reset();
      UI.toast('Added ' + name);
    } catch (err) {
      errEl.textContent = err.message;
    }
  });

  document.getElementById('repo-rows').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-remove-repo]');
    if (!btn) return;
    const name = btn.dataset.removeRepo;
    if (!(await UI.confirm('Remove repository ' + name + '?'))) return;
    try {
      const cfg = await API.del('/config/repos', { name });
      renderRepos(cfg.repos);
      UI.toast('Removed ' + name);
    } catch (err) {
      UI.toast(err.message, true);
    }
  });

  document.getElementById('member-rows').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-remove-member]');
    if (!btn) return;
    const github = btn.dataset.removeMember;
    if (!(await UI.confirm('Remove @' + github + ' from the team?'))) return;
    try {
      const cfg = await API.del('/config/members', { github_username: github });
      renderMembers(cfg.team_members);
      UI.toast('Removed @' + github);
    } catch (err) {
      UI.toast(err.message, true);
    }
  });

  load();
})();
