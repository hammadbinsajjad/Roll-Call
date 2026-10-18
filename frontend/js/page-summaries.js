window.RollCallAuth.requireAuth();
window.RollCallUI.renderNav('summaries.html');

(function () {
  const grid = document.getElementById('grid');
  const dateInput = document.getElementById('date');
  const DATE_KEY = 'rollcall_summary_date';
  const today = window.RollCallUI.todayUTC();
  dateInput.max = today;

  // Restore the persisted date; a future date (e.g. after midnight UTC) falls back to today.
  const stored = localStorage.getItem(DATE_KEY);
  dateInput.value = stored && stored <= today ? stored : today;

  function skeletons(n) {
    grid.innerHTML = Array.from({ length: n }, () => `
      <div class="card member-card">
        <div class="skeleton skeleton-line w60" style="height:16px"></div>
        <div class="skeleton skeleton-line w80"></div>
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line w60"></div>
      </div>`).join('');
  }

  async function load() {
    const date = dateInput.value || today;
    skeletons(3);
    try {
      const members = await window.RollCallAPI.get('/member-summary?date=' + date);
      if (!members.length) {
        grid.innerHTML = window.RollCallUI.emptyState(
          'No summaries for ' + date,
          'Pick another date, or check back after the next ingestion run.'
        );
        return;
      }
      grid.innerHTML = members.map((m) => `
        <article class="card member-card">
          <div class="member-head">
            <div class="member-name">${window.RollCallUI.escapeHtml(m.member_name)}</div>
            <div class="member-meta">@${window.RollCallUI.escapeHtml(m.github_username)} · ${window.RollCallUI.escapeHtml(m.linear_email)}</div>
          </div>
          <div class="summary-body">${window.RollCallMarkdown.render(m.summary)}</div>
        </article>`).join('');
    } catch (err) {
      grid.innerHTML = '';
      window.RollCallUI.toast(err.message, true);
    }
  }

  dateInput.addEventListener('change', () => {
    if (dateInput.value) localStorage.setItem(DATE_KEY, dateInput.value);
    load();
  });

  document.getElementById('today-btn').addEventListener('click', () => {
    localStorage.removeItem(DATE_KEY);
    dateInput.value = today;
    load();
  });

  load();
})();
