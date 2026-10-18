// marked + DOMPurify wrapper. Sanitizes before insertion — LLM output is untrusted.
(function () {
  marked.setOptions({ breaks: true, gfm: true });

  function render(md) {
    return DOMPurify.sanitize(marked.parse(md || ''), {
      USE_PROFILES: { html: true },
    });
  }

  window.RollCallMarkdown = { render };
})();
