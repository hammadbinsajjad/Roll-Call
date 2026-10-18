// Applies THEME (js/config.js) as CSS custom properties. Loaded synchronously in <head>
// so the page never flashes unstyled.
(function () {
  var theme = window.ROLLCALL.THEME;
  for (var k in theme) {
    document.documentElement.style.setProperty(k, theme[k]);
  }
  document.documentElement.classList.add('theme-ready');
})();
