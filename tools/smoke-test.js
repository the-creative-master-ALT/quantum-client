/* ==========================================================================
   EaglerVault smoke test — drives the real launcher in a headless DOM.

     python3 -m http.server 8080 &        # from the repository root
     npm install jsdom                    # one-time, dev only
     node tools/smoke-test.js

   Set BASE_URL to point at a different origin (e.g. the GitHub Pages site).
   The game .html files are never fetched, so this runs in ~5 s and needs no
   bandwidth — the point is to exercise the launcher, not the builds.
   ========================================================================== */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole, requestInterceptor } = require('jsdom');

// Block the game builds themselves: jsdom must never try to execute a
// 40 MB Eaglercraft bundle inside the test iframe.
const blockGames = requestInterceptor((request, { element }) => {
  const p = request.url.replace(/^https?:\/\/[^/]+\//, '').split('?')[0];
  if (element && element.localName === 'iframe') {
    return new Response('<!-- blocked in tests -->', { headers: { 'Content-Type': 'text/html' } });
  }
  if (/\.html$/.test(p) && p !== '' && p !== 'index.html' && p !== '404.html') {
    return new Response('<!-- blocked in tests -->', { headers: { 'Content-Type': 'text/html' } });
  }
});

const ROOT = path.resolve(__dirname, '..');                       // repo root
const BASE = process.env.BASE_URL || 'http://localhost:8080/';    // static server

let pass = 0, fail = 0;
const ok = (cond, msg, extra) => {
  if (cond) { pass++; console.log('  ✓ ' + msg); }
  else { fail++; console.log('  ✗ ' + msg + (extra ? '  → ' + extra : '')); }
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const vc = new VirtualConsole();
  const logs = [];
  vc.on('jsdomError', (e) => {
    const d = e.detail || e;
    if (/Not implemented/.test(String(d && d.message))) return;   // jsdom gaps, not app bugs
    logs.push('jsdomError: ' + (d && d.stack ? d.stack.split('\n').slice(0,4).join(' | ') : d));
  });
  vc.on('error', (...a) => logs.push('error: ' + a.join(' ')));
  vc.on('warn', (...a) => logs.push('warn: ' + a.join(' ')));

  const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

  const dom = new JSDOM(html, {
    url: BASE,
    runScripts: 'dangerously',
    resources: { interceptors: [blockGames] },
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(window) {
      window.fetch = async (url) => {
        const p = String(url).replace(/^https?:\/\/[^/]+\//, '');
        const file = path.join(ROOT, decodeURIComponent(p));
        const body = fs.readFileSync(file);
        return {
          ok: true, status: 200,
          json: async () => JSON.parse(body.toString('utf8')),
          text: async () => body.toString('utf8'),
          clone() { return this; },
        };
      };
      if (!window.structuredClone) window.structuredClone = (o) => JSON.parse(JSON.stringify(o));
      if (!window.CSS) window.CSS = { escape: (s) => String(s).replace(/[^\w-]/g, (c) => '\\' + c) };
      window.HTMLElement.prototype.scrollIntoView = () => {};
      window.HTMLElement.prototype.requestFullscreen = () => Promise.resolve();
      window.addEventListener('error', (ev) => {
        if (ev.error && ev.error.stack) console.log('\n>>> ORIGINAL ERROR:\n' + ev.error.stack + '\n');
      });
      window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {} }));
    },
  });

  const { window } = dom;
  const doc = window.document;
  const $ = (s) => doc.querySelector(s);
  const $$ = (s) => Array.from(doc.querySelectorAll(s));

  await sleep(900);   // let the app boot + fetch the catalogue

  console.log('\n── boot ───────────────────────────────');
  ok($('#boot').classList.contains('is-done'), 'boot splash dismissed');
  ok(logs.length === 0, 'no console errors during boot', logs.join(' | '));

  const CATVERSIONS = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'versions.json'), 'utf8')).versions;
  const cards = $$('.card');
  ok(cards.length === 140, 'renders all 140 build cards', 'got ' + cards.length);
  ok(/140 builds/.test($('#resultCount').textContent) || /140/.test($('#resultCount').textContent),
    'result count shows 140', $('#resultCount').textContent.trim());
  ok($('#heroSub').textContent.includes('140'), 'hero copy mentions the build count');
  ok($('#search').placeholder.includes('140'), 'search placeholder is dynamic');

  console.log('\n── sidebar ────────────────────────────');
  const cats = $$('#catList .cat-item');
  ok(cats.length === 10, '9 eras + “All eras”', 'got ' + cats.length);
  ok($$('#typeList .chip').length === 4, '4 build-type chips');
  ok($$('#runtimeList .chip').length === 3, '3 runtime chips');
  ok($$('#vaultStats dt').length === 7, 'vault stats populated');
  ok($$('.accent-dot').length === 4, 'accent picker rendered');

  console.log('\n── search ─────────────────────────────');
  const s = $('#search');
  s.value = 'beta 1.8';
  s.dispatchEvent(new window.Event('input'));
  await sleep(200);
  const n1 = $$('.card').length;
  ok(n1 > 0 && n1 < 140, `search “beta 1.8” narrows to ${n1}`);
  ok(!$('#activeFilters').hidden, 'active filter chip shown');

  s.value = 'zzzznotathing';
  s.dispatchEvent(new window.Event('input'));
  await sleep(200);
  ok($$('.card').length === 0 && !$('#empty').hidden, 'empty state appears');
  ok(/zzzznotathing/.test($('#emptyMsg').textContent), 'empty message quotes the query');

  $('#btnEmptyReset').click();
  await sleep(120);
  ok($$('.card').length === 140, 'reset restores every build');
  ok(s.value === '', 'reset clears the search box');

  console.log('\n── filters ────────────────────────────');
  const classicBtn = $$('#catList .cat-item').find((b) => b.querySelector('.cat-name').textContent === 'Classic');
  classicBtn.click();
  await sleep(80);
  ok($$('.card').length === 32, 'Classic era filter → 32 builds', 'got ' + $$('.card').length);
  const wasmChip = $$('#runtimeList .chip').find((c) => /WebAssembly GC/.test(c.textContent));
  wasmChip.click();
  await sleep(80);
  const n2 = $$('.card').length;
  ok(n2 === 15, 'Classic + WASM-GC → 15 builds (Classic 0.30 WASM is plain wasm)', 'got ' + n2);
  $('#btnReset').click();
  await sleep(80);
  ok($$('.card').length === 140, 'reset clears era + runtime filters');

  const dupe = $('#optDupes');
  dupe.checked = true;
  dupe.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok($$('.card').length === 136, 'hide-duplicates drops 4 builds', 'got ' + $$('.card').length);
  dupe.checked = false;
  dupe.dispatchEvent(new window.Event('change'));
  await sleep(80);

  console.log('\n── sorting ────────────────────────────');
  const sort = $('#sortBy');
  // global orderings only apply ungrouped; grouped views cluster by era first
  const gsel = $('#groupBy');
  gsel.value = 'none'; gsel.dispatchEvent(new window.Event('change'));
  await sleep(60);
  sort.value = 'size-desc';
  sort.dispatchEvent(new window.Event('change'));
  await sleep(80);
  const titles = $$('.card .card-title').map((t) => t.textContent);
  ok(titles[0].includes('Myven'), 'largest build first (Myven Client 80 MB)', titles[0]);
  sort.value = 'name';
  sort.dispatchEvent(new window.Event('change'));
  await sleep(80);
  const names = $$('.card .card-title').map((t) => t.textContent);
  ok(names[0] < names[1] && names[0] > '', 'A–Z sort', names.slice(0, 2).join(' / '));
  sort.value = 'order';
  sort.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok($$('.card .card-title')[0].textContent.includes('rd-131655'), 'version order starts at rd-131655',
    $$('.card .card-title')[0].textContent);
  ok($$('.card .card-title')[139].textContent.length > 0, 'last card rendered');

  console.log('\n── per-build art + grouping ───────────');
  // the sorting block above switched grouping off; put it back
  $('#groupBy').value = 'era';
  $('#groupBy').dispatchEvent(new window.Event('change'));
  await sleep(80);
  const withArt = CATVERSIONS.filter((v) => v.cover);
  ok(withArt.length === $$('.card .card-cover-img').length,
    `every build with art renders an <img> (${withArt.length})`,
    String($$('.card .card-cover-img').length));
  ok($$('.card .card-cover-img').every((i) => i.getAttribute('loading') === 'lazy'),
    'cover art is lazy-loaded');
  ok(CATVERSIONS.every((v) => v.cover),
    `all ${CATVERSIONS.length} builds advertise a cover`, String(CATVERSIONS.filter((v) => !v.cover).length) + ' missing');
  ok($$('.card .card-cover-img').length === 140,
    'every card renders art (nothing blank)', String($$('.card .card-cover-img').length));
  ok($$('.card .card-cover').every((c) => /^url\(/.test(c.style.getPropertyValue('--cover'))),
    'every cover keeps an era fallback behind the art');
  ok($$('.group-heading').length === 9, 'one sticky heading per era', String($$('.group-heading').length));
  ok(/Pre-Classic/.test($$('.group-heading')[0].textContent), 'first heading is Pre-Classic',
    $$('.group-heading')[0].textContent.trim().slice(0, 40));

  const gb = $('#groupBy');
  gb.value = 'runtime'; gb.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok($$('.group-heading').length === 3, 'grouping by runtime → 3 headings', String($$('.group-heading').length));
  ok($$('.card').length === 140, 'still 140 cards after regrouping');
  gb.value = 'none'; gb.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok($$('.group-heading').length === 0, 'grouping “none” removes headings');
  gb.value = 'era'; gb.dispatchEvent(new window.Event('change'));
  await sleep(80);

  // collapse the first group
  $$('.group-heading')[0].click();
  await sleep(80);
  ok($$('.card').length === 130, 'collapsing Pre-Classic hides its 10 cards', String($$('.card').length));
  ok($$('.group-heading')[0].getAttribute('aria-expanded') === 'false', 'collapsed heading is aria-expanded=false');
  $$('.group-heading')[0].click();
  await sleep(80);
  ok($$('.card').length === 140, 'expanding restores the cards');

  console.log('\n── sort overhaul ──────────────────────');
  const titlesFor = () => $$('.card .card-title').map((t) => t.textContent);
  const so = $('#sortBy');

  // grouped: a descending timeline should flip the era order too
  so.value = 'order-desc'; so.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok(/Extras/.test($$('.group-heading')[0].textContent),
    'descending timeline flips the era order (Extras first)',
    $$('.group-heading')[0].textContent.trim().slice(0, 30));
  const order = $$('.group-heading').map((h) => h.querySelector('.group-title').textContent);
  ok(order[0] === 'Extras' && order[1] === 'Clients' && order[2] === 'Full Release'
     && order[order.length - 1] === 'Pre-Classic',
    'era headings run newest → oldest', order.join(' > '));

  // global (ungrouped) sorts
  gb.value = 'none'; gb.dispatchEvent(new window.Event('change'));
  await sleep(60);
  so.value = 'order-desc'; so.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok(/26\.2|Minicraft|Scratch|Injector|Client/.test(titlesFor()[0]),
    'newest-first puts the modern builds on top', titlesFor()[0]);
  so.value = 'name-desc'; so.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok(titlesFor()[0] > titlesFor()[1], 'Z–A sort works', titlesFor().slice(0, 2).join(' | '));
  so.value = 'size-asc'; so.dispatchEvent(new window.Event('change'));
  await sleep(80);
  ok(/Minecraft 4k/.test(titlesFor()[0]), 'smallest-first starts with Minecraft 4k', titlesFor()[0]);
  so.value = 'order'; so.dispatchEvent(new window.Event('change'));
  gb.value = 'era'; gb.dispatchEvent(new window.Event('change'));
  await sleep(80);

  console.log('\n── card markup ────────────────────────');
  const c0 = $('.card');
  ok(!!c0.querySelector('.card-cover .card-badge'), 'runtime badge lives on the cover');
  ok(!!c0.querySelector('.card-cover .card-cover-label'), 'version label lives on the cover');
  ok(c0.querySelector('.card-actions .card-fav'), 'favourite button is in the actions overlay');
  ok(c0.querySelector('.card-actions .card-play'), 'play button is in the actions overlay');
  ok(c0.children.length === 3 && c0.lastElementChild.classList.contains('card-actions'),
    'card is cover + body + actions', String(c0.children.length));
  ok(/^url\(/.test(c0.querySelector('.card-cover').style.getPropertyValue('--cover')),
    'cover art wired through a custom property');

  console.log('\n── view toggle ────────────────────────');
  $('#btnList').click();
  await sleep(60);
  ok($('#grid').getAttribute('data-view') === 'list', 'list view applied');
  ok($('#btnList').getAttribute('aria-pressed') === 'true', 'list button pressed');
  $('#btnGrid').click();
  await sleep(60);
  ok($('#grid').getAttribute('data-view') === 'grid', 'grid view restored');

  console.log('\n── favourites ─────────────────────────');
  const first = $('.card');
  const firstName = first.querySelector('.card-title').textContent;
  first.querySelector('.card-fav').click();
  await sleep(60);
  ok($('#favCount').textContent === '1', 'favourite counter = 1');
  ok($('.card').classList.contains('is-fav'), 'card marked as favourite');
  ok(JSON.parse(window.localStorage.getItem('eaglervault.v1')).favs &&
     Object.keys(JSON.parse(window.localStorage.getItem('eaglervault.v1')).favs).length === 1,
    'favourite persisted to localStorage');

  $('#btnFavs').click();
  await sleep(80);
  ok($$('.card').length === 1, 'favourites-only filter → 1 build');
  $('#btnFavs').click();
  await sleep(80);
  ok($$('.card').length === 140, 'favourites filter toggled off');

  console.log('\n── detail drawer ──────────────────────');
  $('.card').click();
  await sleep(120);
  ok(!$('#drawer').hidden, 'drawer opens');
  ok($('#drawerTitle').textContent.length > 0, 'drawer shows a title', $('#drawerTitle').textContent);
  ok(/^rd-131655-JS\.html$/.test($$('#drawerSpecs dd').slice(-1)[0].textContent),
    'drawer lists the raw file name', $$('#drawerSpecs dd').slice(-1)[0].textContent);
  ok(window.location.hash === '#/build/' + $('.card').dataset.id, 'deep link written to the URL',
    window.location.hash);
  ok(doc.body.classList.contains('is-locked'), 'page scroll locked while open');

  console.log('\n── launch ─────────────────────────────');
  $('#drawerPlay').click();
  await sleep(200);
  ok(!$('#player').hidden, 'player overlay opens');
  const iframe = $('#playerStage iframe');
  ok(!!iframe, 'iframe created');
  ok(iframe.getAttribute('src') === './rd-131655-JS.html', 'iframe points at the build',
    iframe && iframe.getAttribute('src'));
  ok(iframe.hasAttribute('allowfullscreen'), 'iframe allows fullscreen');
  ok(/fullscreen/.test(iframe.getAttribute('allow') || ''), 'fullscreen in allow list');
  ok(window.location.hash.startsWith('#/play/'), 'play deep link set', window.location.hash);
  ok(!$('#recentsWrap').hidden, '“continue playing” strip appears after a launch');

  $('#playerQuit').click();
  await sleep(150);
  ok($('#player').hidden, 'player closes');
  ok($('#playerStage iframe') === null, 'iframe removed from the DOM');
  ok(!$('#drawer').hidden, 'returns to the detail view after quitting');

  console.log('\n── routing ────────────────────────────');
  window.location.hash = '#/build/does-not-exist';
  window.dispatchEvent(new window.HashChangeEvent('hashchange'));
  await sleep(80);
  ok(!!$('.toast'), 'unknown deep link shows a warning toast');

  window.location.hash = '#/';
  window.dispatchEvent(new window.HashChangeEvent('hashchange'));
  await sleep(80);
  ok($('#drawer').hidden, 'empty route closes the drawer');

  console.log('\n── theme ──────────────────────────────');
  $('#btnTheme').click();
  await sleep(60);
  ok(doc.documentElement.getAttribute('data-theme') === 'light', 'theme toggles to light');
  ok(JSON.parse(window.localStorage.getItem('eaglervault.v1')).settings.theme === 'light',
    'theme persisted');
  $('#btnTheme').click();
  await sleep(60);
  ok(doc.documentElement.getAttribute('data-theme') === 'dark', 'theme toggles back to dark');

  console.log('\n── keyboard ───────────────────────────');
  doc.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: '/', bubbles: true }));
  await sleep(40);
  ok(doc.activeElement === $('#search'), '“/” focuses search');
  $('#search').blur();
  $('#btnHelp').click();
  await sleep(60);
  ok(!$('#helpModal').hidden, 'help modal opens');
  doc.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await sleep(60);
  ok($('#helpModal').hidden, 'Escape closes help modal');

  console.log('\n── surprise me ────────────────────────');
  $('#btnRandom').click();
  await sleep(150);
  ok(!$('#player').hidden, 'random build launches');
  ok($('#playerStage iframe').getAttribute('src').endsWith('.html'), 'random src is an html file',
    $('#playerStage iframe').getAttribute('src'));
  $('#playerBack').click();
  await sleep(100);

  console.log('\n── hidden elements really hide ────────');
  const disp = (sel) => window.getComputedStyle($(sel)).display;
  ok(disp('#player') === 'none', 'closed player overlay has display:none', disp('#player'));
  ok(disp('#drawer') === 'none', 'closed drawer has display:none', disp('#drawer'));
  ok(disp('#helpModal') === 'none', 'closed help modal has display:none', disp('#helpModal'));
  ok(disp('#searchClear') === 'none', 'search clear button hidden when empty', disp('#searchClear'));
  ok(disp('#grid') !== 'none', 'grid is visible when it has results', disp('#grid'));

  console.log('\n── final ──────────────────────────────');
  ok(logs.length === 0, 'no runtime errors overall', logs.join(' | '));

  console.log(`\n${pass} passed, ${fail} failed\n`);
  window.close();
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('HARNESS CRASH', e); process.exit(2); });
