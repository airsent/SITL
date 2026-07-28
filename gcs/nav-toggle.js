/* nav-toggle.js — click-to-open for the topbar logo navigation menu.
   The menu was hover/:focus-within only (styles.css "UNIVERSAL LOGO DROPDOWN FIX"),
   so clicking the logo button did nothing. Adds click-toggle, click-outside close,
   and Escape close. Hover behaviour is unchanged.
   Class-name pairs cover both variants used across the console pages. */
(function () {
  var PAIRS = [
    ['.logo-dropdown', '.logo-dropdown-btn', '.logo-dropdown-menu'],
    ['.logo-wrap',     '.logo-btn',          '.logo-menu']
  ];

  /* Beats the stylesheet's `display:none !important` on specificity (0,3,0 vs 0,1,0). */
  var style = document.createElement('style');
  style.textContent =
    '.logo-dropdown.nav-open .logo-dropdown-menu,' +
    '.logo-wrap.nav-open .logo-menu{display:block !important;}';
  document.head.appendChild(style);

  function closeAll() {
    document.querySelectorAll('.nav-open').forEach(function (w) {
      w.classList.remove('nav-open');
      var b = w.querySelector('button');
      if (b) b.setAttribute('aria-expanded', 'false');
    });
  }

  PAIRS.forEach(function (p) {
    document.querySelectorAll(p[0]).forEach(function (wrap) {
      var btn = wrap.querySelector(p[1]);
      if (!btn) return;
      btn.setAttribute('aria-expanded', 'false');
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();   /* keeps the document handler from closing it instantly */
        var open = wrap.classList.toggle('nav-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    });
  });

  document.addEventListener('click', closeAll);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });
})();
