import { media } from './media.js';

const toggle = document.querySelector('.menu-toggle');
const nav = document.querySelector('#navegacion');
const mobile = window.matchMedia('(max-width: 800px)');

function setMenu(open) {
  toggle.setAttribute('aria-expanded', String(open));
  nav.hidden = mobile.matches && !open;
}

function syncNavigation() {
  if (toggle.contains(document.activeElement) && !mobile.matches) {
    nav.hidden = false;
    nav.querySelector('a').focus();
  } else if (nav.contains(document.activeElement) && mobile.matches) {
    toggle.hidden = false;
    toggle.focus();
  }
  toggle.hidden = !mobile.matches;
  setMenu(false);
}

toggle.addEventListener('click', () => setMenu(nav.hidden));
nav.addEventListener('click', (event) => {
  if (mobile.matches && event.target.closest('a')) {
    const section = document.querySelector(event.target.closest('a').hash);
    section.setAttribute('tabindex', '-1');
    section.focus({ preventScroll: true });
    setMenu(false);
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
    setMenu(false);
    toggle.focus();
  }
});
mobile.addEventListener('change', syncNavigation);
syncNavigation();

if (media.videoUrl) {
  document.querySelector('[data-demo-link]').href = media.videoUrl;
  document.querySelector('#demostracion').hidden = false;
}

if (media.downloadUrl) {
  const download = document.querySelector('[data-download-link]');
  download.href = media.downloadUrl;
  download.hidden = false;
  document.querySelector('[data-download-status]').hidden = true;
}
