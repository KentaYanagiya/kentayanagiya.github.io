const body = document.body;
const langButtons = document.querySelectorAll('.lang-button');
const menuToggle = document.querySelector('.menu-toggle');
const navLinks = document.querySelector('.nav-links');
const year = document.getElementById('year');

function setLanguage(lang) {
  const normalized = lang === 'ja' ? 'ja' : 'en';
  body.classList.toggle('lang-ja-mode', normalized === 'ja');
  body.classList.toggle('lang-en-mode', normalized === 'en');
  document.documentElement.lang = normalized === 'ja' ? 'ja' : 'en';
  langButtons.forEach((button) => {
    button.classList.toggle('active', button.dataset.lang === normalized);
  });
  localStorage.setItem('siteLanguage', normalized);
}

langButtons.forEach((button) => {
  button.addEventListener('click', () => setLanguage(button.dataset.lang));
});

if (menuToggle && navLinks) {
  menuToggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(isOpen));
  });

  navLinks.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      menuToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const savedLanguage = localStorage.getItem('siteLanguage');
const browserLanguage = navigator.language && navigator.language.startsWith('ja') ? 'ja' : 'en';
setLanguage(savedLanguage || browserLanguage);

if (year) {
  year.textContent = new Date().getFullYear();
}
