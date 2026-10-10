/** Contract checks for the plain project-information page. */
export async function testSiteInteractions({ page, context, check, go, shot, axe, assert, base }) {
  const scrollTo = async selector => page.locator(selector).evaluate(el => window.scrollTo({ top: el.getBoundingClientRect().top + scrollY - 20, behavior: 'instant' }));
  await check('Plain informational content contract', async () => {
    await page.setViewportSize({ width: 1440, height: 1050 });
    await go();
    assert.equal((await page.locator('h1').innerText()).trim(), 'OpenRacket');
    const body = await page.locator('body').innerText();
    assert.doesNotMatch(body, /Fresh perspective|Familiar ground|Come look under|Small ideas\. Open possibilities|Good work takes proof|A calmer, more modern home|Explore the source/i);
    assert.equal(await page.locator('.editor,.hero,.theme-controls,.closing-section,button,input,textarea,svg,img,canvas').count(), 0, 'Plain informational page must not retain the former decorative interface or widgets');
    assert.equal(await page.locator('script[src]').count(), 0, 'Production page should have no JavaScript dependency');
    assert.ok(await page.locator('main h2').count() >= 4);
    return 'Project name, factual sections and ordinary links; no slogans, decorative artwork, mock app or JavaScript controls';
  });
  await check('Readable typography and focused content width', async () => {
    const values = await page.evaluate(() => ({ h1: parseFloat(getComputedStyle(document.querySelector('h1')).fontSize), body: parseFloat(getComputedStyle(document.body).fontSize), paragraphs: [...document.querySelectorAll('main p')].map(el => ({ size: parseFloat(getComputedStyle(el).fontSize), width: el.getBoundingClientRect().width })) }));
    assert.ok(values.h1 <= 40 && values.h1 >= 24, JSON.stringify(values));
    assert.ok(values.body >= 15);
    assert.ok(values.paragraphs.length >= 5);
    assert.ok(values.paragraphs.every(p => p.size >= 15 && p.width <= 960), JSON.stringify(values));
    return 'Main text is at least 15px, title is compact, and reading columns stay below 960px';
  });
  await check('System dark preference and accessibility', async () => {
    const light = await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor);
    await page.emulateMedia({ colorScheme: 'dark' });
    assert.notEqual(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), light);
    await shot('desktop-dark');
    const result = await axe('desktop-dark');
    await page.emulateMedia({ colorScheme: 'light' });
    return result;
  });
  await check('Skip link and visible keyboard focus', async () => {
    await go();
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('.skip-link').evaluate(el => el === document.activeElement), true);
    const focus = await page.locator('.skip-link').evaluate(el => ({ outline: getComputedStyle(el).outlineStyle, width: parseFloat(getComputedStyle(el).outlineWidth), top: el.getBoundingClientRect().top }));
    assert.ok(focus.width >= 2 && focus.outline !== 'none' && focus.top >= 0, JSON.stringify(focus));
    await page.keyboard.press('Enter');
    assert.equal(new URL(page.url()).hash, '#main');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => !!document.activeElement.closest('main')), true);
    for (let i = 0; i < 6; i++) {
      const focused = await page.evaluate(() => ({ tag: document.activeElement.tagName, outline: getComputedStyle(document.activeElement).outlineStyle, width: parseFloat(getComputedStyle(document.activeElement).outlineWidth) }));
      assert.equal(focused.tag, 'A'); assert.ok(focused.width >= 2 && focused.outline !== 'none');
      await page.keyboard.press('Tab');
    }
    return 'Skip link enters main; six subsequent documentation links are keyboard reachable with visible focus';
  });
  await check('Section navigation and browser history', async () => {
    await go();
    const links = page.locator('nav a[href^="#"]');
    assert.ok(await links.count() >= 3);
    const first = await links.first().getAttribute('href');
    await links.first().click(); assert.equal(new URL(page.url()).hash, first);
    await page.goBack(); assert.equal(new URL(page.url()).hash, '');
    await page.goForward(); assert.equal(new URL(page.url()).hash, first);
    for (let i = 0; i < await links.count(); i++) {
      const href = await links.nth(i).getAttribute('href');
      await links.nth(i).click(); assert.equal(new URL(page.url()).hash, href);
    }
    return `${await links.count()} section links and Back/Forward preserve fragment navigation`;
  });
  await check('Mobile documentation readability', async () => {
    await page.setViewportSize({ width: 390, height: 950 });
    await go();
    await shot('mobile');
    const dimensions = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, text: [...document.querySelectorAll('main p,main li')].map(el => ({ size: parseFloat(getComputedStyle(el).fontSize), left: el.getBoundingClientRect().left, right: el.getBoundingClientRect().right })) }));
    assert.ok(dimensions.scroll <= dimensions.width + 1);
    assert.ok(dimensions.text.every(x => x.size >= 15 && x.left >= 0 && x.right <= dimensions.width + 1));
    const sections = page.locator('main section[id]');
    assert.ok(await sections.count() >= 4);
    const id = await sections.nth(Math.max(0, (await sections.count()) - 2)).getAttribute('id');
    await scrollTo('#' + id); await shot('mobile-lower');
    return '390px viewport has readable full-width text, natural wrapping and no clipped paragraphs';
  });
  await check('Mobile accessibility', () => axe('mobile'));
  await check('Reduced motion and forced-colors usability', async () => {
    await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
    const media = await page.evaluate(() => ({ reduced: matchMedia('(prefers-reduced-motion: reduce)').matches, forced: matchMedia('(forced-colors: active)').matches, scroll: getComputedStyle(document.documentElement).scrollBehavior, moving: [...document.querySelectorAll('*')].filter(el => { const s = getComputedStyle(el); return s.transitionDuration.split(',').some(d => parseFloat(d) > 0) || s.animationDuration.split(',').some(d => parseFloat(d) > 0); }).map(el => el.tagName) }));
    assert.equal(media.reduced, true); assert.equal(media.forced, true); assert.equal(media.scroll, 'auto'); assert.deepEqual(media.moving, []);
    assert.equal(await page.locator('h1').isVisible(), true);
    assert.equal(await page.locator('nav a').first().isVisible(), true);
    await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'none' });
    return 'Text and ordinary navigation remain available in forced colors; no motion or smooth scrolling';
  });
  await check('Subdirectory serving and lower-page render', async () => {
    await page.setViewportSize({ width: 1440, height: 1050 });
    await go('/website/');
    const sections = page.locator('main section[id]');
    const id = await sections.nth(Math.max(0, (await sections.count()) - 3)).getAttribute('id');
    await scrollTo('#' + id); await shot('desktop-lower');
    assert.ok((await page.locator('h1').innerText()).includes('OpenRacket'));
    const width = await page.locator('main').evaluate(el => el.getBoundingClientRect().width);
    assert.ok(width <= 960, `Stylesheet not applied under subdirectory: ${width}px`);
    return 'Relative stylesheet works under /website/; lower documentation sections render without clipping';
  });
  await check('No-JavaScript documentation', async () => {
    await go(); const expected = await page.locator('main').innerText();
    const nojs = await context.browser().newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 950 } });
    try {
      await nojs.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort('blockedbyclient'));
      const p = await nojs.newPage(); await p.goto(base + '/', { waitUntil: 'networkidle' });
      assert.equal(await p.locator('main').innerText(), expected);
      const link = p.locator('nav a[href^="#"]').first(); const href = await link.getAttribute('href');
      await link.click(); assert.equal(new URL(p.url()).hash, href);
    } finally { await nojs.close(); }
    return 'All information and section navigation remain identical with JavaScript disabled';
  });
}
