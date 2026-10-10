/** Contract tests for this static design-study website, not a Racket evaluator. */
export async function testSiteInteractions({ page, context, check, go, shot, axe, assert, base }) {
  const preview = page.locator('.editor[data-preview-theme]');
  const light = page.locator('[data-theme-choice="light"]');
  const dark = page.locator('[data-theme-choice="dark"]');
  const scrollTo = async selector => page.locator(selector).evaluate(el => window.scrollTo({ top: el.getBoundingClientRect().top + scrollY - 20, behavior: 'instant' }));
  await check('Skip link and visible keyboard focus', async () => {
    await page.setViewportSize({ width: 1440, height: 1050 });
    await go();
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('.skip-link').evaluate(el => el === document.activeElement), true);
    const focus = await page.locator('.skip-link').evaluate(el => ({ outline: getComputedStyle(el).outlineStyle, width: parseFloat(getComputedStyle(el).outlineWidth), top: el.getBoundingClientRect().top }));
    assert.ok(focus.width >= 2 && focus.outline !== 'none' && focus.top >= 0, JSON.stringify(focus));
    await page.keyboard.press('Enter');
    assert.equal(new URL(page.url()).hash, '#main');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => !!document.activeElement.closest('main')), true, 'Skip navigation did not move keyboard navigation into main');
    const linkFocus = await page.evaluate(() => ({ width: parseFloat(getComputedStyle(document.activeElement).outlineWidth), style: getComputedStyle(document.activeElement).outlineStyle }));
    assert.ok(linkFocus.width >= 2 && linkFocus.style !== 'none');
    return 'Skip link is visible on focus and moves keyboard sequence into main; focused links have visible outline';
  });
  await check('Anchor navigation and browser history', async () => {
    await go();
    await page.locator('.hero-actions a[href="#workspace"]').click();
    assert.equal(new URL(page.url()).hash, '#workspace');
    await page.goBack();
    assert.equal(new URL(page.url()).hash, '');
    await page.goForward();
    assert.equal(new URL(page.url()).hash, '#workspace');
    await page.locator('.site-header a[href="#development"]').click();
    assert.equal(new URL(page.url()).hash, '#development');
    await page.locator('.footer-brand').click();
    assert.equal(new URL(page.url()).hash, '');
    return 'Design/development/home links and Back/Forward maintain expected fragment history';
  });
  await check('Preview theme controls, repeated clicks and announcements', async () => {
    await go();
    assert.equal(await preview.getAttribute('data-preview-theme'), 'light');
    assert.equal(await light.isVisible(), true);
    assert.equal(await light.getAttribute('aria-pressed'), 'true');
    assert.equal(await dark.getAttribute('aria-pressed'), 'false');
    const bodyBackground = await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor);
    const lightBackground = await preview.evaluate(el => getComputedStyle(el).backgroundColor);
    await dark.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(250);
    assert.equal(await preview.getAttribute('data-preview-theme'), 'dark');
    assert.equal(await dark.getAttribute('aria-pressed'), 'true');
    assert.equal(await light.getAttribute('aria-pressed'), 'false');
    assert.match(await page.locator('#preview-announcement').innerText(), /Dark interface design preview selected\./);
    assert.notEqual(await preview.evaluate(el => getComputedStyle(el).backgroundColor), lightBackground);
    assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), bodyBackground, 'Theme should change illustration only');
    for (let i = 0; i < 3; i++) await dark.click();
    assert.equal(await preview.getAttribute('data-preview-theme'), 'dark');
    for (let i = 0; i < 3; i++) await light.click();
    assert.equal(await preview.getAttribute('data-preview-theme'), 'light');
    await dark.click();
    await page.waitForTimeout(250);
    await scrollTo('#workspace');
    await shot('desktop-dark');
    return 'Keyboard, light/dark ARIA state, live announcement and repeated clicks work; page theme is unchanged';
  });
  await check('Desktop dark-preview accessibility', () => axe('desktop-dark'));
  await check('Theme defaults and illustration honesty', async () => {
    await page.reload({ waitUntil: 'networkidle' });
    assert.equal(await preview.getAttribute('data-preview-theme'), 'light');
    assert.equal(await light.getAttribute('aria-pressed'), 'true');
    assert.equal(await preview.locator('button,input,textarea,[contenteditable="true"]').count(), 0);
    assert.match(await page.locator('.preview-caption').innerText(), /illustration, not a running app or screenshot/i);
    assert.match(await page.locator('.editor-toolbar').getAttribute('aria-label'), /not application controls/);
    return 'Reload restores default light preview; illustrated toolbar is noninteractive and clearly disclosed';
  });
  await check('FAQ keyboard and repeated disclosure behavior', async () => {
    const details = page.locator('.project-faq details');
    assert.equal(await details.count(), 3);
    for (let i = 0; i < await details.count(); i++) {
      const item = details.nth(i), summary = item.locator('summary');
      assert.equal(await item.getAttribute('open'), null);
      await summary.focus();
      await page.keyboard.press('Enter');
      assert.notEqual(await item.getAttribute('open'), null);
      assert.equal(await item.locator('div').isVisible(), true);
      await page.keyboard.press('Space');
      assert.equal(await item.getAttribute('open'), null);
      await summary.click(); await summary.click();
      assert.equal(await item.getAttribute('open'), null);
    }
    return 'All three native disclosures open/close using Enter, Space and repeated pointer activation';
  });
  await check('Mobile visible navigation and theme preview', async () => {
    await page.setViewportSize({ width: 390, height: 950 });
    await go();
    assert.equal(await page.locator('.site-header .nav-source').isVisible(), true);
    assert.equal(await page.locator('.site-header a[href="#development"]').isVisible(), true);
    await shot('mobile-light');
    await dark.click();
    assert.equal(await preview.getAttribute('data-preview-theme'), 'dark');
    await light.click();
    assert.equal(await preview.getAttribute('data-preview-theme'), 'light');
    await scrollTo('#workspace');
    await shot('mobile-demo');
    await page.locator('.project-faq details').first().locator('summary').click();
    await scrollTo('.project-faq');
    await shot('mobile-faq');
    assert.equal(await page.locator('.project-faq details').first().locator('div').isVisible(), true);
    return '390px navigation stays available; theme and FAQ work without a mobile-menu dependency';
  });
  await check('Mobile accessibility with open FAQ', () => axe('mobile-light'));
  await check('Reduced-motion preference honored', async () => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reduced = await page.evaluate(() => ({ matches: matchMedia('(prefers-reduced-motion: reduce)').matches, scroll: getComputedStyle(document.documentElement).scrollBehavior, moving: [...document.querySelectorAll('*')].filter(el => { const s = getComputedStyle(el); return s.transitionDuration.split(',').some(d => parseFloat(d) > 0) || s.animationDuration.split(',').some(d => parseFloat(d) > 0); }).map(el => el.className).slice(0, 5) }));
    assert.equal(reduced.matches, true); assert.equal(reduced.scroll, 'auto'); assert.deepEqual(reduced.moving, []);
    await page.locator('.button-primary').hover();
    assert.equal(await page.locator('.button-primary').evaluate(el => getComputedStyle(el).transform), 'none');
    return 'No smooth scrolling, nonzero transitions/animations or hover movement with reduced motion';
  });
  await check('Subdirectory serving and lower-page render', async () => {
    await page.setViewportSize({ width: 1440, height: 1050 });
    await go('/website/');
    assert.equal(await light.isVisible(), true);
    const styled = await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor);
    assert.equal(styled, 'rgb(244, 241, 233)');
    await scrollTo('.architecture-section');
    await shot('desktop-overview');
    return 'Relative CSS/JS/assets work under /website/ and lower-page architecture/development render';
  });
  await check('No-JavaScript content and native FAQs', async () => {
    const nojs = await context.browser().newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 950 } });
    try {
      await nojs.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort('blockedbyclient'));
      const p = await nojs.newPage();
      await p.goto(base + '/', { waitUntil: 'networkidle' });
      assert.equal(await p.locator('h1').count(), 1);
      assert.equal(await p.locator('.theme-controls').isVisible(), false);
      assert.equal(await p.locator('.editor').getAttribute('data-preview-theme'), 'light');
      await p.locator('.project-faq summary').first().click();
      assert.notEqual(await p.locator('.project-faq details').first().getAttribute('open'), null);
      assert.ok((await p.locator('body').innerText()).length > 1000);
    } finally { await nojs.close(); }
    return 'Core content, source links and native disclosures remain usable without JavaScript';
  });
}
