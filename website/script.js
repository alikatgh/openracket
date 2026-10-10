/* Progressive enhancement only. The site remains useful without JavaScript. */
(function () {
  'use strict';

  const preview = document.querySelector('[data-preview-theme]');
  const controls = document.querySelector('.theme-controls');
  const buttons = Array.from(document.querySelectorAll('[data-theme-choice]'));
  const announcement = document.getElementById('preview-announcement');

  if (!preview || !controls || buttons.length !== 2) return;

  function selectTheme(theme) {
    if (theme !== 'light' && theme !== 'dark') return;
    preview.dataset.previewTheme = theme;
    buttons.forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === theme));
    });
    if (announcement) {
      announcement.textContent = (theme === 'dark' ? 'Dark' : 'Light') + ' interface design preview selected.';
    }
  }

  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      selectTheme(button.dataset.themeChoice);
    });
  });

  controls.hidden = false;
  const hint = document.querySelector('.theme-hint');
  if (hint) hint.hidden = false;
})();
