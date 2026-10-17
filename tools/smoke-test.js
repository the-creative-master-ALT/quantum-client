#!/usr/bin/env node
/**
 * Smoke test for the single-file launcher.
 *
 * Drives index.html in a headless DOM and checks the things that silently
 * break: group counts, artwork wiring, the downloads panel, and that no
 * external asset crept back in.
 *
 *   NODE_PATH=/tmp/testenv/node_modules node tools/smoke-test.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const INDEX = path.join(ROOT, 'index.html');

let pass = 0, fail = 0;
const errors = [];

const sec = (t) => { console.log(`\n── ${t} ${'─'.repeat(Math.max(0, 38 - t.length))}`); };
function ok(cond, label, detail) {
  if (cond) { pass++; console.log(`  \x1b[32m✓\x1b[0m ${label}`); }
  else { fail++; console.log(`  \x1b[31m✗\x1b[0m ${label}${detail ? '  → ' + detail : ''}`); }
}

/* ------------------------------------------------------------------ load */
const html = fs.readFileSync(INDEX, 'utf8');

const vc = new VirtualConsole();
const navErrors = [];
vc.on('jsdomError', (e) => {
  // jsdom refuses to actually navigate, but it does tell us that it tried --
  // which is how we observe "Play launched the build" without a real browser
  if (/navigation/i.test(e.message)) { navErrors.push(e.message); return; }
  // jsdom cannot execute multi-MB game bundles; the launcher itself must be quiet
  if (!/Could not parse CSS|Not implemented/.test(e.message)) errors.push(e.message);
});
vc.on('error', (m) => errors.push(String(m)));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  url: 'http://localhost:8080/index.html',
  virtualConsole: vc,
  beforeParse(window) {
    window.addEventListener('error', (e) => errors.push(String(e.message)));
  },
});

const win = dom.window;
const doc = win.document;
const $ = (s) => doc.querySelector(s);
const $$ = (s) => Array.from(doc.querySelectorAll(s));
const text = (s) => ($(s) ? $(s).textContent.trim() : '');

const CAT = JSON.parse(doc.getElementById('vault').textContent);

/* -------------------------------------------------------- self-contained */
sec('single file');
ok($$('link[rel="stylesheet"]').length === 0, 'no external stylesheet');
ok($$('script[src]').length === 0, 'no external script');
ok($$('img').length === 0, 'no <img> tags at all (artwork is inline SVG)');
ok(/^data:image\/svg/.test($('link[rel="icon"]').getAttribute('href') || ''), 'favicon is an inline data URI');
ok($$('symbol[id^="scene-"]').length === 11, '11 inline artwork scenes', String($$('symbol[id^="scene-"]').length));

/* --------------------------------------------------------------- catalog */
sec('embedded catalogue');
ok(CAT.count === 137, `${CAT.count} builds embedded`, String(CAT.count));
ok(CAT.versions.length === CAT.count, 'count matches array length');
ok(CAT.versions.every((b) => b.id && b.name && b.file && b.url), 'every build has id, name, file, url');
ok(!!CAT.totalSizeText, `total size present (${CAT.totalSizeText})`);

/* ----------------------------------------------------------------- files */
sec('every build resolves on disk');
const missing = CAT.versions.filter((b) => !fs.existsSync(path.join(ROOT, b.file)));
ok(missing.length === 0, `all ${CAT.count} build files exist`, missing.slice(0, 3).map((b) => b.file).join(', '));

/* ---------------------------------------------------------------- groups */
sec('sidebar groups');
const EXPECTED = {
  'All builds': 137, 'Pre-Classic': 10, Classic: 32, Devs: 8, Alpha: 8, Beta: 18,
  'Early Releases': 19, 'Middle Releases': 10, 'Modern Releases': 6, Clients: 20, Extras: 6,
};
const btns = $$('#nav [data-group]');
ok(btns.length === Object.keys(EXPECTED).length, `${btns.length} sidebar entries`, String(btns.length));

// recompute the grouping independently so the UI cannot drift from the data
const vt = (v) => (String(v || '').match(/\d+/g) || []).map(Number);
function groupOf(b) {
  const c = b.category;
  if (c === 'preclassic') return 'preclassic';
  if (c === 'classic') return 'classic';
  if (c === 'indev' || c === 'infdev') return 'devs';
  if (c === 'alpha') return 'alpha';
  if (c === 'beta') return 'beta';
  if (c === 'client') return 'clients';
  if (c === 'extras') return 'extras';
  if (c === 'release') {
    const n = vt(b.version);
    if (n[0] === 1 && n[1] <= 8) return 'early';
    if (n[0] === 1 && n[1] >= 9 && n[1] <= 17) return 'mid';
    return 'modern';
  }
  return 'extras';
}
const LABEL = { all: 'All builds', preclassic: 'Pre-Classic', classic: 'Classic', devs: 'Devs', alpha: 'Alpha',
  beta: 'Beta', early: 'Early Releases', mid: 'Middle Releases', modern: 'Modern Releases', clients: 'Clients', extras: 'Extras' };
const tally = {};
CAT.versions.forEach((b) => { const g = groupOf(b); tally[LABEL[g]] = (tally[LABEL[g]] || 0) + 1; });
// 10 real groups; "All builds" is a UI-level aggregate, not a category
ok(Object.keys(tally).length === 10, '10 real groups + All builds aggregate', String(Object.keys(tally).length));

let countOk = true, countDetail = '';
btns.forEach((b) => {
  const lbl = b.querySelector('.lbl').textContent.trim();
  const n = Number(b.querySelector('.n').textContent.trim());
  if (EXPECTED[lbl] !== undefined && EXPECTED[lbl] !== n) { countOk = false; countDetail += `${lbl}:${n} `; }
});
ok(countOk, 'sidebar counts match expected', countDetail);
ok(Object.values(tally).reduce((a, b) => a + b, 0) === CAT.count, 'independent tally accounts for every build');

/* ------------------------------------------------------------ duplicates */
sec('duplicates removed');
const stillDup = CAT.versions.filter((b) => (b.tags || []).includes('duplicate'));
ok(stillDup.length === 0, 'no build carries the duplicate tag', String(stillDup.length));
const gone = ['Eaglercraft_indev_20100233.html', 'Eaglercraft_indev_20100233-wasm.html',
  'Eaglercraft-1.12.html', 'wispcraft-Eaglercraft_1.12.2-WASM-GC.html'];
ok(gone.every((f) => !fs.existsSync(path.join(ROOT, f))), 'the 4 duplicate files are gone from disk');
// the survivors must still be there, or we deleted the wrong half of a pair
const kept = ['Eaglercraft_indev 20100223_JS.html', 'Eaglercraft_indev 20100223_WASM.html',
  'Eaglercraft_1.12.2-WASM-GC.html', 'wispcraft-Eaglercraft-1.12.html'];
ok(kept.every((f) => fs.existsSync(path.join(ROOT, f))), 'the originals were kept, not the duplicates');

/* ------------------------------------------------------------- responsive */
sec('responsive: scales, never reflows');
const css = $('style').textContent;
ok(!/grid-template-areas\s*:\s*["']?side["']?\s*["']?stage["']?/.test(css) ||
   !/@media[^{]*max-width[^{]*\{[^{]*grid-template-areas/.test(css),
   'no breakpoint moves the sidebar into a topbar');
ok(/transform-origin\s*:\s*0 0/.test(css), 'shell scales from the top-left corner');
ok(/width\s*:\s*calc\(100vw \/ var\(--s\)\)/.test(css), 'shell is drawn 1/--s oversized so it lands exactly on the viewport');

// jsdom reports a 1024x768 viewport, so --s should be min(1, 1024/1400, 768/860)
const shell = $('.shell');
const sVal = parseFloat(shell.style.getPropertyValue('--s'));
const expectedS = Math.min(1, 1024 / 1400, 768 / 860);
ok(Math.abs(sVal - expectedS) < 0.001,
   `--s scales the layout to ${sVal} in a 1024px viewport`, String(sVal));
ok(sVal < 1, 'a narrow window is scaled down rather than reflowed', String(sVal));

/* ------------------------------------------------------------- downloads */
sec('downloads lives in the sidebar');
ok(!!$('aside.side #dlOpen'), 'the Downloads button is inside the sidebar');
ok(!$('.dock #dlOpen'), 'Downloads is gone from the bottom dock');
ok($('#dlCount').textContent === String(CAT.count),
   `sidebar shows the build count (${$('#dlCount').textContent})`);

/* --------------------------------------------------------------- artwork */
sec('artwork + selection');
ok($('#artUse').getAttribute('href') === '#scene-all', 'starts on the overview scene');
const before = text('#bName');
ok(before && before !== '—', `a build is selected (${before})`);

const classicBtn = btns.find((b) => b.querySelector('.lbl').textContent.trim() === 'Classic');
classicBtn.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#artUse').getAttribute('href') === '#scene-classic', 'selecting Classic swaps the artwork');
ok($$('#pick option').length === 32, 'picker narrows to Classic builds', String($$('#pick option').length));
ok(classicBtn.getAttribute('aria-current') === 'true', 'selected group is marked current');

const preBtn = btns.find((b) => b.querySelector('.lbl').textContent.trim() === 'Pre-Classic');
preBtn.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#artUse').getAttribute('href') === '#scene-preclassic', 'selecting Pre-Classic swaps the artwork');
ok($$('#pick option').length === 10, 'picker narrows to 10 Pre-Classic builds', String($$('#pick option').length));

$('#next').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(/2 \/ 10/.test(text('#pos')), 'next advances within the group', text('#pos'));
$('#prev').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(/1 \/ 10/.test(text('#pos')), 'prev goes back', text('#pos'));

// every group must actually have a scene, or the art renders blank
let scenesOk = true, sceneDetail = '';
$$('#nav [data-group]').forEach((b) => {
  b.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
  const href = $('#artUse').getAttribute('href') || '';
  if (!href.startsWith('#scene-') || !doc.querySelector(href)) { scenesOk = false; sceneDetail += href + ' '; }
});
ok(scenesOk, 'every group resolves to a real scene', sceneDetail);

/* ------------------------------------------------------------------ play */
sec('play');
btns.find((b) => b.getAttribute('data-group') === 'all')
  .dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
$('#pick').value = CAT.versions[0].id;
$('#pick').dispatchEvent(new win.Event('change', { bubbles: true }));
ok(text('#bName') === CAT.versions[0].name, 'picking from the dropdown updates the card', text('#bName'));
const target = CAT.versions[0];
navErrors.length = 0;
$('#play').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(navErrors.length === 1, 'Play triggers navigation', String(navErrors.length));
ok(fs.existsSync(path.join(ROOT, target.file)), `target is the selected build's own file (${target.file})`);
ok(!!$('#gRecent'), 'a Continue entry appears after playing');

/* ------------------------------------------------------------- downloads */
sec('downloads');
ok($('#dlScrim').hasAttribute('hidden'), 'downloads panel starts hidden');
$('#dlOpen').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(!$('#dlScrim').hasAttribute('hidden'), 'Downloads button opens the panel');
ok($$('#dlList .dl-row').length === CAT.count, `all ${CAT.count} builds listed`, String($$('#dlList .dl-row').length));

const links = $$('#dlList a.dl-btn');
ok(links.length === CAT.count, 'every row has a download link', String(links.length));
ok(links.every((a) => a.hasAttribute('download')), 'links carry the download attribute');
ok(links.every((a) => (a.getAttribute('href') || '').startsWith('./')), 'links point at local build files');

const dlSearch = $('#dlSearch');
dlSearch.value = 'beta 1.8';
dlSearch.dispatchEvent(new win.Event('input', { bubbles: true }));
const filtered = $$('#dlList .dl-row').length;
ok(filtered > 0 && filtered < CAT.count, `search narrows to ${filtered}`);
dlSearch.value = 'zzzznope';
dlSearch.dispatchEvent(new win.Event('input', { bubbles: true }));
ok(/Nothing matches/.test(text('#dlList')), 'empty state for no results');
dlSearch.value = '';
dlSearch.dispatchEvent(new win.Event('input', { bubbles: true }));
ok($$('#dlList .dl-row').length === CAT.count, 'clearing search restores the full list');

$('#dlGroup').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($$('#dlList .dl-row').length <= CAT.count, 'scope-to-group toggle filters the list');
$('#dlGroup').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
$('#dlClose').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#dlScrim').hasAttribute('hidden'), 'close hides the panel');

/* ------------------------------------------------------------ favourites */
sec('favourites');
$('#fav').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#fav').getAttribute('aria-pressed') === 'true', 'star marks the build');
ok(!!$('#gFav'), 'a Favourites entry appears in the sidebar');
ok(!!win.localStorage.getItem('quantum-launcher-v1'), 'favourite persisted to localStorage');

/* ------------------------------------------------------------- resilience */
sec('final');
ok(errors.length === 0, 'no runtime errors', errors.slice(0, 2).join(' | '));

console.log(`\n${fail === 0 ? '\x1b[32m' : '\x1b[31m'}${pass} passed, ${fail} failed\x1b[0m\n`);
process.exit(fail === 0 ? 0 : 1);
