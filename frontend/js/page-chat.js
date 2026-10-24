window.RollCallAuth.requireAuth();

(function () {
  const UI = window.RollCallUI, API = window.RollCallAPI, MD = window.RollCallMarkdown;
  const scroll = document.getElementById('scroll');
  const composer = document.getElementById('composer');
  const input = document.getElementById('message');
  const sendBtn = document.getElementById('send');
  const hint = document.getElementById('hint');


  let busy = false;

  function getChatId() {
    return new URLSearchParams(location.search).get('id');
  }

  // Static nav: highlight chats, wire the burger.
  (function () {
    const nav = document.querySelector('header.nav');
    const t = document.getElementById('nav-toggle');
    t.addEventListener('click', (e) => {
      e.stopPropagation();
      document.getElementById('nav-links').classList.toggle('open');
    });
    // Tap/click anywhere outside the nav closes the mobile menu.
    document.addEventListener('click', (e) => {
      if (!nav.contains(e.target)) document.getElementById('nav-links').classList.remove('open');
    });
  })();

  function bubble(role, content) {
    const el = document.createElement('div');
    el.className = 'chat-msg ' + role;
    if (role === 'assistant') {
      el.innerHTML = '<div class="chat-bubble">' + MD.render(content) + '</div>';
    } else {
      const p = document.createElement('div');
      p.className = 'chat-bubble';
      p.textContent = content;
      el.appendChild(p);
    }
    scroll.appendChild(el);
    scroll.scrollTop = scroll.scrollHeight;
  }

  function setBusy(v) {
    busy = v;
    sendBtn.disabled = v;
    sendBtn.textContent = v ? 'Thinking…' : 'Send';
    hint.textContent = v ? 'Thinking…' : 'Ask about your team…';
  }

  async function send(message) {
    bubble('user', message);
    setBusy(true);
    try {
      let data;
      const id = getChatId();
      if (id) {
        data = await API.post('/chat/' + encodeURIComponent(id), { message });
      } else {
        data = await API.post('/chat', { message });
        // New chat: adopt the server-assigned id so a refresh continues it.
        history.replaceState(null, '', 'chat.html?id=' + encodeURIComponent(data.chat_id));
      }
      bubble('assistant', data.reply);
    } catch (err) {
      UI.toast(err.message, true);
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  composer.addEventListener('submit', (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg || busy) return;
    input.value = '';
    input.style.height = 'auto';
    send(msg);
  });

  // Enter sends, Shift+Enter newline; grow the textarea as the user types.
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      composer.requestSubmit();
    }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  });

  async function load() {
    const id = getChatId();
    if (!id) {
      hint.textContent = 'Ask about your team…';
      return;
    }
    try {
      const chat = await API.get('/chat/' + encodeURIComponent(id));
      (chat.messages || []).forEach((m) => bubble(m.role, m.content));
    } catch (err) {
      UI.toast(err.message, true);
    }
  }

  load();
  input.focus();
})();
