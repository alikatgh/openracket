'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'script.js'), 'utf8');

function fixture({ preview = true, controls = true, count = 2, announcement = true, hint = true } = {}) {
  const editor = preview ? { dataset: { previewTheme: 'light' } } : null;
  const group = controls ? { hidden: true } : null;
  const status = announcement ? { textContent: '' } : null;
  const themeHint = hint ? { hidden: true } : null;
  const buttons = ['light', 'dark'].slice(0, count).map(theme => ({
    dataset: { themeChoice: theme },
    attributes: { 'aria-pressed': String(theme === 'light') },
    listeners: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(type, callback) { this.listeners[type] = callback; },
    click() { this.listeners.click?.(); },
  }));
  const document = {
    querySelector(selector) {
      return ({ '[data-preview-theme]': editor, '.theme-controls': group, '.theme-hint': themeHint })[selector] ?? null;
    },
    querySelectorAll() { return buttons; },
    getElementById() { return status; },
  };
  vm.runInNewContext(source, { document });
  return { editor, group, status, themeHint, buttons };
}

const site = fixture();
assert.equal(site.group.hidden, false);
assert.equal(site.themeHint.hidden, false);
assert.equal(site.editor.dataset.previewTheme, 'light');
for (let i = 0; i < 20; i++) {
  site.buttons[1].click();
  assert.equal(site.editor.dataset.previewTheme, 'dark');
  assert.equal(site.buttons[0].attributes['aria-pressed'], 'false');
  assert.equal(site.buttons[1].attributes['aria-pressed'], 'true');
  assert.equal(site.status.textContent, 'Dark interface design preview selected.');
}
site.buttons[0].click();
assert.equal(site.editor.dataset.previewTheme, 'light');
assert.equal(site.buttons[0].attributes['aria-pressed'], 'true');
assert.equal(site.buttons[1].attributes['aria-pressed'], 'false');
assert.equal(site.status.textContent, 'Light interface design preview selected.');
site.buttons[1].dataset.themeChoice = 'invalid';
site.buttons[1].click();
assert.equal(site.editor.dataset.previewTheme, 'light');
assert.equal(fixture().editor.dataset.previewTheme, 'light');
for (const options of [{ preview: false }, { controls: false }, { count: 1 }, { announcement: false }, { hint: false }]) {
  assert.doesNotThrow(() => fixture(options));
}
const withoutOptional = fixture({ announcement: false, hint: false });
withoutOptional.buttons[1].click();
assert.equal(withoutOptional.editor.dataset.previewTheme, 'dark');
console.log('PASS: theme initialization, repeated clicks, reversal, aria state, announcement, invalid input, fresh load, missing optional/required elements.');
