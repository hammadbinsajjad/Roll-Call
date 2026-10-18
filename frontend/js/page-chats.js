window.RollCallAuth.requireAuth();
window.RollCallUI.renderNav('chats.html');

(function () {
  const rows = document.getElementById('rows');

  async function load() {
    try {
      const chats = await window.RollCallAPI.get('/chats');
      if (!chats.length) {
        rows.innerHTML = window.RollCallUI.emptyState(
          'No chats yet',
          'Start one and ask anything about your team.'
        );
        return;
      }
      rows.innerHTML = chats.map((c) => `
        <a class="chat-row" href="chat.html?id=${encodeURIComponent(c.chat_id)}">
          <span class="chat-title">${window.RollCallUI.escapeHtml(c.title)}</span>
          <span class="chat-time">${window.RollCallUI.relTime(c.updated_at || c.created_at)}</span>
        </a>`).join('');
    } catch (err) {
      window.RollCallUI.toast(err.message, true);
    }
  }

  load();
})();
