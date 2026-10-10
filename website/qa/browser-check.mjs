/** Real-browser checks run only on the explicitly authorized public GitHub runner. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { createRequire } from 'node:module';
import { testSiteInteractions } from './site-interactions.mjs';
const require = createRequire(import.meta.url);
assert.equal(process.env.GITHUB_ACTIONS, 'true', 'This harness must never launch a local browser');
assert.equal(process.env.GITHUB_REPOSITORY, 'alikatgh/openracket');
assert.equal(process.env.GITHUB_REF, 'refs/heads/website/openracket');
assert.equal(process.env.RUNNER_OS, 'Linux');
assert.match(process.env.GITHUB_SHA ?? '', /^[0-9a-f]{40}$/);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(process.env.RUNNER_TEMP, 'openracket-website-evidence');
await fs.mkdir(evidence, { recursive: true });
const rows = [], errors = [], failures = [], requests = [], externalRequests = [];
const start = Date.now();
async function summary() {
  const lines = ['# OpenRacket website browser validation', '', `Commit: ${process.env.GITHUB_SHA}`, `Browser: ${browser?.version?.() || 'not started'}`, '', '| Check | Actual result | Detail |', '|---|---|---|', ...rows.map(r => `| ${r.name} | ${r.ok ? 'PASS' : 'FAIL'} | ${r.detail.replaceAll('|', ';').replaceAll('\n', ' ')} |`), '', 'This is real Chromium desktop/mobile-emulation QA plus automated accessibility checks. It is not a full assistive-technology audit, a real mobile-device test, or native OpenRacket application validation. PNGs are real browser captures requiring human pixel inspection. No deployment, cache or artifact upload occurs.', '', `Elapsed: ${((Date.now() - start) / 1000).toFixed(1)} seconds.`, ''];
  await fs.writeFile(path.join(evidence, 'summary.md'), lines.join('\n'));
  await fs.writeFile(path.join(evidence, 'results.json'), JSON.stringify({ commit: process.env.GITHUB_SHA, browser: browser?.version?.(), rows, errors, failures, externalRequests }, null, 2));
}
async function check(name, fn) {
  try { const detail = await fn(); rows.push({ name, ok: true, detail: String(detail ?? '') }); }
  catch (error) { rows.push({ name, ok: false, detail: String(error.stack || error).slice(0, 5000) }); }
  const row = rows.at(-1);
  console.log(`OPENRACKET_WEBSITE_RESULT ${row.name}: ${row.ok ? 'PASS' : 'FAIL'} ${row.detail}`);
  await summary();
}
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.json': 'application/json' };
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://127.0.0.1');
    let rel = decodeURIComponent(url.pathname);
    // Exercise the source from a project subdirectory, as well as the root.
    if (rel.startsWith('/website/')) rel = rel.slice('/website'.length);
    if (rel.endsWith('/')) rel += 'index.html';
    const file = path.resolve(root, '.' + rel);
    if (!file.startsWith(root + path.sep) || file.includes(path.sep + 'qa' + path.sep)) { res.writeHead(403).end(); return; }
    const bytes = await fs.readFile(file);
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' }).end(bytes);
  } catch { res.writeHead(404).end('Not found'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1, colorScheme: 'light', reducedMotion: 'no-preference' });
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { externalRequests.push(url.origin + url.pathname); return route.abort('blockedbyclient'); }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', request => failures.push({ url: request.url(), error: request.failure()?.errorText }));
  page.on('response', response => { if (response.status() >= 400) requests.push({ url: response.url(), status: response.status() }); });
  async function go(url = '/') { const response = await page.goto(base + url, { waitUntil: 'networkidle' }); assert.equal(response.status(), 200); await page.evaluate(() => document.fonts.ready); }
  async function shot(label) { await page.screenshot({ path: path.join(evidence, label + '.png'), animations: 'disabled', fullPage: false }); return `${label}.png`; }
  async function axe(label) {
    await page.addScriptTag({ path: require.resolve('axe-core/axe.min.js') });
    const result = await page.evaluate(async () => await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } }));
    const problems = result.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map(n => ({ target: n.target, failureSummary: n.failureSummary })) }));
    await fs.writeFile(path.join(evidence, `axe-${label}.json`), JSON.stringify(problems, null, 2));
    assert.deepEqual(problems, [], JSON.stringify(problems));
    return `${result.passes.length} axe rules passed; zero selected WCAG violations`;
  }
  await check('Initial real-browser render', async () => {
    await go(); assert.match(await page.title(), /OpenRacket/i); assert.equal(await page.locator('h1').count(), 1); assert.equal(await page.locator('main').count(), 1); assert.ok((await page.locator('body').innerText()).length > 1000); return await shot('desktop');
  });
  await check('Local assets and anchor link integrity', async () => {
    const anchors = await page.locator('a').evaluateAll(elements => elements.map(a => ({ href: a.getAttribute('href'), text: a.textContent.trim(), target: a.target, rel: a.rel, brand: a.classList.contains('brand') })));
    assert.ok(anchors.length >= 5);
    for (const a of anchors) {
      assert.ok(a.href, `Empty link: ${a.text}`);
      if (a.href === '#') { assert.ok(a.brand, `Undisclosed placeholder link: ${a.text}`); continue; }
      if (a.href.startsWith('#')) assert.equal(await page.locator(`[id=${JSON.stringify(decodeURIComponent(a.href.slice(1)))}]`).count(), 1, `Missing anchor ${a.href}`);
      else if (/^https?:/.test(a.href)) { const url = new URL(a.href); assert.equal(url.protocol, 'https:'); assert.ok(['github.com', 'docs.racket-lang.org', 'racket-lang.org', 'www.racket-lang.org', 'download.racket-lang.org'].includes(url.hostname), `Unexpected external destination ${a.href}`); if (a.target === '_blank') assert.ok(/noopener|noreferrer/.test(a.rel)); }
      else { const response = await page.request.get(new URL(a.href, page.url()).href); assert.equal(response.status(), 200, `Broken relative link ${a.href}`); }
    }
    const broken = await page.locator('img').evaluateAll(imgs => imgs.filter(img => !img.complete || img.naturalWidth === 0).map(img => img.src));
    assert.deepEqual(broken, []); assert.deepEqual(requests, []); return `${anchors.length} links and all image/local asset requests valid; external destination syntax checked only`;
  });
  await check('Desktop accessibility', () => axe('desktop'));
  await check('Responsive horizontal overflow', async () => {
    const widths = [1440, 1280, 1024, 768, 390, 360, 320];
    for (const width of widths) {
      await page.setViewportSize({ width, height: 950 });
      await page.waitForTimeout(100);
      const result = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll('body *')].filter(el => { const r = el.getBoundingClientRect(); return r.width && (r.left < -1 || r.right > innerWidth + 1) && getComputedStyle(el).position !== 'fixed'; }).slice(0, 8).map(el => ({ tag: el.tagName, cls: el.className, width: el.getBoundingClientRect().width })) }));
      assert.ok(result.scroll <= width + 1, `Horizontal overflow: ${JSON.stringify(result)}`);
    }
    return `${widths.join(', ')} px: no document horizontal overflow`;
  });
  await testSiteInteractions({ page, context, check, go, shot, axe, evidence, base, assert, fs });
  await check('No runtime errors or third-party requests', async () => { assert.deepEqual(errors, []); assert.deepEqual(failures, []); assert.deepEqual(externalRequests, []); assert.deepEqual(requests, []); return 'No page/console errors, failed resources, or external network dependencies'; });
  await context.close();
} catch (error) {
  rows.push({ name: 'Browser harness execution', ok: false, detail: String(error.stack || error) });
  console.error(error);
} finally {
  await summary();
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
console.log('OPENRACKET_WEBSITE_RESULTS_JSON ' + JSON.stringify({ commit: process.env.GITHUB_SHA, rows }));
if (rows.some(row => !row.ok)) process.exitCode = 1;
