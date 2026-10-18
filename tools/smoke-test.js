#!/usr/bin/env node
/**
 * Headless smoke tests for the self-contained launcher.
 *
 * This deliberately checks build references against Git's index, not the
 * contents of the large game files, so it remains useful in sparse checkouts.
 *
 *   NODE_PATH=/tmp/quantum-test/node_modules node tools/smoke-test.js
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const INDEX = path.join(ROOT, 'index.html');
let pass = 0, fail = 0;
const errors = [];
const navErrors = [];

const sec = (title) => console.log(`\n── ${title} ${'─'.repeat(Math.max(0, 42 - title.length))}`);
function ok(condition, label, detail) {
  if (condition) { pass++; console.log(`  \x1b[32m✓\x1b[0m ${label}`); }
  else { fail++; console.log(`  \x1b[31m✗\x1b[0m ${label}${detail ? `  → ${detail}` : ''}`); }
}
function gitFiles() {
  return execFileSync('git', ['ls-files', '-z'], { cwd: ROOT })
    .toString('utf8').split('\0').filter(Boolean);
}
function isSparse() {
  try {
    return execFileSync('git', ['config', '--bool', 'core.sparseCheckout'], { cwd: ROOT, encoding: 'utf8' }).trim() === 'true';
  } catch (_) { return false; }
}

const html = fs.readFileSync(INDEX, 'utf8');
const vc = new VirtualConsole();
vc.on('jsdomError', (error) => {
  if (/navigation/i.test(error.message)) { navErrors.push(error.message); return; }
  if (!/Could not parse CSS|Not implemented/.test(error.message)) errors.push(error.message);
});
vc.on('error', (message) => errors.push(String(message)));
const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  url: 'http://localhost:8080/index.html',
  virtualConsole: vc,
  beforeParse(window) { window.addEventListener('error', (event) => errors.push(String(event.message))); },
});
const win = dom.window;
const doc = win.document;
const $ = (selector) => doc.querySelector(selector);
const $$ = (selector) => Array.from(doc.querySelectorAll(selector));
const text = (selector) => $(selector) ? $(selector).textContent.trim() : '';
const CAT = JSON.parse(doc.getElementById('vault').textContent);
const tracked = new Set(gitFiles().filter((name) => !name.includes('/')));
const trackedBuilds = new Set(Array.from(tracked).filter((name) => name.toLowerCase().endsWith('.html') && !['index.html', '404.html'].includes(name)));
const indexedBuilds = new Set(CAT.versions.map((build) => build.file));
const timeline = CAT.versions.filter((build) => build.category !== 'client' && build.category !== 'extras');
const clients = CAT.versions.filter((build) => build.category === 'client');
const bonus = CAT.versions.filter((build) => build.category === 'extras');

sec('single-file launcher');
ok($$('link[rel="stylesheet"]').length === 0, 'no external stylesheet');
ok($$('script[src]').length === 0, 'no external JavaScript');
ok($$('img').length === 0, 'artwork uses inline SVG, not image files');
ok(/^data:image\/svg/.test($('link[rel="icon"]')?.getAttribute('href') || ''), 'favicon is an inline SVG data URI');
ok($$('symbol[id^="scene-"]').length === 11, 'all 11 SVG scenes are embedded', String($$('symbol[id^="scene-"]').length));
ok(!/@import\s|url\(\s*https?:/i.test($('style').textContent), 'CSS has no remote imports or URLs');

sec('catalogue and chronology');
ok(CAT.count === CAT.versions.length, `${CAT.count} embedded entries match the count`);
ok(CAT.versions.every((build) => build.id && build.name && build.file && build.url && Number.isFinite(build.order)), 'every entry has an id, path, and sort key');
ok(new Set(CAT.versions.map((build) => build.id)).size === CAT.count, 'build ids are unique');
ok(new Set(CAT.versions.map((build) => build.file)).size === CAT.count, 'build filenames are unique');
ok(timeline.length === 111, `${timeline.length} mainline builds in the timeline`);
ok(clients.length === 21, `${clients.length} clients in their own wheel`);
ok(bonus.length === 2 && new Set(bonus.map((build) => build.name)).size === 2, 'exactly two bonus games remain');
ok(new Set(bonus.map((build) => build.name)).has('Minecraft 4K') && new Set(bonus.map((build) => build.name)).has('Minicraft'), 'bonus games are Minecraft 4K and Minicraft');
ok(timeline[0]?.version === 'rd-131655', `timeline starts at ${timeline[0]?.version}`);
ok(timeline[timeline.length - 1]?.version === '26.3', `timeline ends at ${timeline[timeline.length - 1]?.version}`);
ok(timeline.every((build, i) => i === 0 || timeline[i - 1].order <= build.order), 'timeline sort keys never move backwards');
ok(!!CAT.totalSizeText, `archive size is present (${CAT.totalSizeText})`);

sec('build references without payload reads');
const missingFromIndex = Array.from(indexedBuilds).filter((file) => !trackedBuilds.has(file));
const unlisted = Array.from(trackedBuilds).filter((file) => !indexedBuilds.has(file));
ok(missingFromIndex.length === 0, 'every catalogue filename exists in Git', missingFromIndex.slice(0, 4).join(', '));
ok(unlisted.length === 0, 'every tracked game HTML is catalogued', unlisted.slice(0, 4).join(', '));
const diskMissing = CAT.versions.filter((build) => !fs.existsSync(path.join(ROOT, build.file)));
const sizeMismatch = CAT.versions.filter((build) => {
  const file = path.join(ROOT, build.file);
  return fs.existsSync(file) && fs.statSync(file).size !== build.size;
});
ok(sizeMismatch.length === 0, 'materialized payload sizes match catalogue metadata', sizeMismatch.slice(0, 3).map((b) => b.file).join(', '));
ok(isSparse() || diskMissing.length === 0, isSparse() ? `${diskMissing.length} unmaterialized files are allowed by sparse checkout` : 'all payloads are materialized in the full checkout');

sec('iPhone-style picker wheels');
ok(!!$('#timelineWheel') && !!$('#clientWheel'), 'timeline and clients have separate wheel pickers');
ok($('#timelineWheel').getAttribute('role') === 'listbox' && $('#clientWheel').getAttribute('role') === 'listbox', 'both wheels expose accessible listbox controls');
ok($$('.wheel-center').length === 2 && $$('.wheel-fade').length === 2, 'each wheel has a fixed center slot and fading edges');
ok(/scroll-snap-type:\s*y\s+mandatory/i.test($('style').textContent), 'wheel scrolling snaps each option into the center');
ok(/perspective:\s*720px/i.test($('style').textContent) && /rotateX\(var\(--wheel-angle/i.test($('style').textContent), 'options bend and fade along a picker-wheel curve');
ok(!$('#nav [data-group]'), 'category sidebar navigation has been removed');
ok($$('#timelineWheel [role="option"]').length === timeline.length, 'timeline wheel renders every chronological option');
ok($$('#clientWheel [role="option"]').length === clients.length, 'client wheel renders every client option');
ok($$('#bonusActions .bonus-link').length === 2, 'two quick-launch buttons sit in the library footer');
ok($('#bonusActions').closest('.rail-footer') === $('.rail-footer'), 'bonus buttons are inside the bottom rail footer');

sec('full-stage artwork and selection');
ok(/\.art-wrap\s*\{[^}]*position:\s*absolute[^}]*inset:\s*0/s.test($('style').textContent), 'artwork layer fills the stage');
ok(/\.art\s*\{[^}]*width:\s*100%[^}]*height:\s*100%/s.test($('style').textContent), 'SVG scales to the full artwork layer');
ok($('#artUse').getAttribute('href') === '#scene-modern', 'starts on the newest build artwork');
ok(text('#bName') === 'Eaglercraft 26.3', '26.3 is selected on launch', text('#bName'));

const firstTimelineRow = $('#timelineWheel .wheel-item');
firstTimelineRow.dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#artUse').getAttribute('href') === '#scene-preclassic', 'selecting an RD build swaps the artwork');
ok(text('#bName') === timeline[0].name, 'timeline click selects the matching build');
ok($('#timelineWheel .wheel-item[aria-selected="true"]')?.getAttribute('data-build-id') === timeline[0].id, 'the centered option is marked as selected');
ok($('#timelineWheel').getAttribute('aria-activedescendant') === $('#timelineWheel .wheel-item[aria-selected="true"]')?.id, 'picker announces its active option');
const wheelDown = new win.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true });
$('#timelineWheel').dispatchEvent(wheelDown);
ok(wheelDown.defaultPrevented && text('#bName') === timeline[1].name, 'focused wheel advances one option with the down arrow');
$('#timelineWheel').dispatchEvent(new win.KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true }));
ok(text('#bName') === timeline[0].name, 'up arrow returns the wheel to the prior option');
$('#next').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(text('#pos') === '2 / 111', 'next advances through the current wheel', text('#pos'));
$('#prev').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(text('#pos') === '1 / 111', 'previous returns to the prior build', text('#pos'));

$('#clientWheel .wheel-item').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#artUse').getAttribute('href') === '#scene-clients', 'client selection uses client artwork');
ok(text('#bName') === clients[0].name, 'client wheel selects its own build');
ok(text('#pos') === '1 / 21', 'client position is counted within the client wheel');

const search = $('#wheelSearch');
search.value = '26.3';
search.dispatchEvent(new win.Event('input', { bubbles: true }));
ok($$('#timelineWheel .wheel-item').length === 1, 'wheel search narrows the timeline');
ok($$('#clientWheel .wheel-item').length === 0, 'wheel search independently filters clients');
$('#timelineWheel .wheel-item').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(text('#bName') === 'Eaglercraft 26.3', 'search result is launch-selectable');
search.value = '';
search.dispatchEvent(new win.Event('input', { bubbles: true }));
ok($$('#timelineWheel .wheel-item').length === timeline.length, 'clearing search restores the timeline');

sec('saved builds and downloads');
$('#fav').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#fav').getAttribute('aria-pressed') === 'true', 'selected build can be saved');
ok(!!win.localStorage.getItem('quantum-launcher-v1'), 'saved builds persist in local storage');
$('#favFilter').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#favFilter').getAttribute('aria-pressed') === 'true' && $$('#timelineWheel .wheel-item').length === 1, 'saved-only filter keeps the wheel usable');
$('#favFilter').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));

$('#dlOpen').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(!$('#dlScrim').hasAttribute('hidden'), 'build library opens');
ok($$('#dlList .dl-row').length === CAT.count, `all ${CAT.count} catalogue entries are listed`);
const links = $$('#dlList a.dl-btn');
ok(links.length === CAT.count && links.every((link) => link.hasAttribute('download')), 'every archive row has a download link');
ok(links.every((link) => (link.getAttribute('href') || '').startsWith('./')), 'download links remain local');
const dlSearch = $('#dlSearch');
dlSearch.value = 'beta 1.8';
dlSearch.dispatchEvent(new win.Event('input', { bubbles: true }));
ok($$('#dlList .dl-row').length > 0 && $$('#dlList .dl-row').length < CAT.count, 'archive search filters results');
dlSearch.value = 'no-such-build';
dlSearch.dispatchEvent(new win.Event('input', { bubbles: true }));
ok(/No builds match/.test(text('#dlList')), 'archive search has an empty state');
dlSearch.value = '';
dlSearch.dispatchEvent(new win.Event('input', { bubbles: true }));
$('#dlSaved').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($$('#dlList .dl-row').length === 1, 'saved-only archive filter works');
$('#dlSaved').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
$('#dlClose').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok($('#dlScrim').hasAttribute('hidden'), 'build library closes');

sec('play actions');
navErrors.length = 0;
$('#play').dispatchEvent(new win.MouseEvent('click', { bubbles: true }));
ok(navErrors.length === 1, 'Play navigates to the selected build');
const selected = CAT.versions.find((build) => build.name === text('#bName') && build.version === '26.3');
ok(!!selected && trackedBuilds.has(selected.file), 'launch target is the tracked 26.3 HTML file');

sec('runtime');
ok(errors.length === 0, 'no launcher runtime errors', errors.slice(0, 3).join(' | '));
console.log(`\n${fail === 0 ? '\x1b[32m' : '\x1b[31m'}${pass} passed, ${fail} failed\x1b[0m\n`);
process.exit(fail === 0 ? 0 : 1);
