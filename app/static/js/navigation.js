document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('mobile-menu-toggle');
  const nav = document.getElementById('nav');
  const overlay = document.getElementById('nav-overlay');
  if (!toggle || !nav || !overlay) return;

  const close = () => {
    document.body.classList.remove('nav-open');
    toggle.setAttribute('aria-expanded', 'false');
    overlay.hidden = true;
  };

  const open = () => {
    document.body.classList.add('nav-open');
    toggle.setAttribute('aria-expanded', 'true');
    overlay.hidden = false;
  };

  toggle.addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) close();
    else open();
  });

  overlay.addEventListener('click', close);
  nav.addEventListener('click', (event) => {
    const link = event.target.closest('a');
    if (link && link.getAttribute('href') !== '#') close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') close();
  });
});
