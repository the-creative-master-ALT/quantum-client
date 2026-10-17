/* ==========================================================================
   EaglerVault — static launcher front-end
   No frameworks, no build step, no network calls except the catalogue JSON.
   ========================================================================== */
(() => {
  'use strict';

  const CATALOG_URL = './data/versions.json';
  const STORE_KEY = 'eaglervault.v1';
  const LIGHT_LIMIT = 25 * 1024 * 1024;   // "data saver" threshold
  const HEAVY_LIMIT = 45 * 1024 * 1024;   // warn before loading

  /* ------------------------------------------------------------ helpers -- */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function el(tag, attrs = {}, kids = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k === 'html') node.innerHTML = v;
      else if (k === 'style') node.setAttribute('style', v);
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? '' : v);
    }
    (Array.isArray(kids) ? kids : [kids]).forEach((k) => {
      if (k) node.appendChild(typeof k === 'string' ? document.createTextNode(k) : k);
    });
    return node;
  }

  function svgIcon(id, cls) {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('class', 'ico' + (cls ? ' ' + cls : ''));
    s.setAttribute('aria-hidden', 'true');
    const u = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    u.setAttribute('href', '#' + id);
    s.appendChild(u);
    return s;
  }

  const coverFor = (e) => `./assets/img/cat-${e.category}.jpg`;

  const CAT_COLORS = {
    preclassic: '#8b7355', classic: '#5bbf7a', indev: '#7fa8c9', infdev: '#9b8ec4',
    alpha: '#c98b5e', beta: '#d4c05f', release: '#4ade80', client: '#e05fa8', extras: '#22d3ee',
  };

  const RT_LABEL = { js: 'JS', wasm: 'WASM', 'wasm-gc': 'WASM-GC', unknown: '?' };

  function fmtRelative(ts) {
    const d = Date.now() - ts;
    if (d < 60e3) return 'just now';
    if (d < 3600e3) return Math.round(d / 60e3) + ' min ago';
    if (d < 86400e3) return Math.round(d / 3600e3) + ' h ago';
    if (d < 7 * 86400e3) return Math.round(d / 86400e3) + ' d ago';
    return new Date(ts).toLocaleDateString();
  }

  /* ------------------------------------------------------------- storage -- */
  const defaults = {
    favs: {}, plays: {}, recents: [],
    settings: { theme: 'dark', accent: 'emerald', view: 'grid', sort: 'order', hideDupes: false, lightOnly: false },
  };

  const store = {
    data: structuredClone(defaults),
    load() {
      try {
        const raw = localStorage.getItem(STORE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          this.data = {
            favs: parsed.favs || {},
            plays: parsed.plays || {},
            recents: Array.isArray(parsed.recents) ? parsed.recents : [],
            settings: Object.assign({}, defaults.settings, parsed.settings || {}),
          };
        }
      } catch (_) { /* corrupt or blocked storage — run with defaults */ }
      return this.data;
    },
    save() {
      try { localStorage.setItem(STORE_KEY, JSON.stringify(this.data)); }
      catch (_) { /* private mode / quota — non fatal */ }
    },
  };

  /* --------------------------------------------------------------- state -- */
  let CAT = null;                 // parsed catalogue
  let VIEW = [];                  // filtered + sorted entries
  let FOCUS_INDEX = -1;
  let lastFocused = null;
  let playerReturnHash = '';
  let loadTimer = null;
  let loadStart = 0;
  let activeEntry = null;

  const filters = {
    q: '',
    cats: new Set(),
    types: new Set(),
    rts: new Set(),
    favsOnly: false,
    hideDupes: false,
    lightOnly: false,
  };

  /* ----------------------------------------------------------------- dom -- */
  const dom = {
    boot: $('#boot'),
    grid: $('#grid'),
    empty: $('#empty'),
    emptyMsg: $('#emptyMsg'),
    sidebar: $('#sidebar'),
    scrim: $('#scrim'),
    catList: $('#catList'),
    typeList: $('#typeList'),
    runtimeList: $('#runtimeList'),
    vaultStats: $('#vaultStats'),
    heroSub: $('#heroSub'),
    heroStats: $('#heroStats'),
    heroKicker: $('#heroKicker'),
    resultCount: $('#resultCount'),
    activeFilters: $('#activeFilters'),
    search: $('#search'),
    searchClear: $('#searchClear'),
    sortBy: $('#sortBy'),
    favCount: $('#favCount'),
    recentsWrap: $('#recentsWrap'),
    recentRow: $('#recentRow'),
    drawer: $('#drawer'),
    player: $('#player'),
    playerStage: $('#playerStage'),
    playerLoading: $('#playerLoading'),
    playerLoadingText: $('#playerLoadingText'),
    playerHint: $('#playerHint'),
    playerTitle: $('#playerTitle'),
    toasts: $('#toasts'),
    footerMeta: $('#footerMeta'),
    btnPlayTop: $('#btnPlayTop'),
  };

  /* --------------------------------------------------------------- toasts -- */
  function toast(message, icon = 'i-play') {
    const t = el('div', { class: 'toast' }, [svgIcon(icon), el('span', { text: message })]);
    dom.toasts.appendChild(t);
    setTimeout(() => {
      t.classList.add('is-out');
      setTimeout(() => t.remove(), 260);
    }, 2600);
  }

  /* ------------------------------------------------------------- catalog -- */
  async function loadCatalog() {
    const res = await fetch(CATALOG_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    CAT = await res.json();
    if (!CAT || !Array.isArray(CAT.versions)) throw new Error('malformed catalogue');
  }

  const byId = (id) => CAT.versions.find((v) => v.id === id) || null;

  /* -------------------------------------------------------------- filter -- */
  function haystack(e) {
    if (!e._hay) {
      e._hay = [e.name, e.file, e.category, e.type, e.runtime, e.version, e.note,
        (e.tags || []).join(' ')].join(' ').toLowerCase();
    }
    return e._hay;
  }

  function matches(e) {
    if (filters.favsOnly && !store.data.favs[e.id]) return false;
    if (filters.cats.size && !filters.cats.has(e.category)) return false;
    if (filters.types.size && !filters.types.has(e.type)) return false;
    if (filters.rts.size && !filters.rts.has(e.runtime)) return false;
    if (filters.hideDupes && e.duplicateOf) return false;
    if (filters.lightOnly && e.size > LIGHT_LIMIT) return false;
    const q = filters.q.trim().toLowerCase();
    if (!q) return true;
    return q.split(/\s+/).every((tok) => haystack(e).includes(tok));
  }

  function sortEntries(list) {
    const s = store.data.settings.sort;
    const plays = store.data.plays;
    const lastPlayed = (id) => {
      const r = store.data.recents.find((x) => x.id === id);
      return r ? r.ts : 0;
    };
    const cmp = {
      order: (a, b) => (a.order - b.order) || a.name.localeCompare(b.name),
      name: (a, b) => a.name.localeCompare(b.name) || a.size - b.size,
      'size-desc': (a, b) => b.size - a.size,
      'size-asc': (a, b) => a.size - b.size,
      plays: (a, b) => (plays[b.id] || 0) - (plays[a.id] || 0) || a.name.localeCompare(b.name),
      recent: (a, b) => lastPlayed(b.id) - lastPlayed(a.id) || a.name.localeCompare(b.name),
    }[s] || ((a, b) => a.order - b.order);
    return list.slice().sort(cmp);
  }

  function applyFilters() {
    VIEW = sortEntries(CAT.versions.filter(matches));
    renderGrid();
    renderActiveFilters();
    dom.resultCount.innerHTML =
      `<b>${VIEW.length}</b> of <b>${CAT.count}</b> build${CAT.count === 1 ? '' : 's'}` +
      (VIEW.length !== CAT.count ? ' shown' : '');
    dom.empty.hidden = VIEW.length > 0;
    dom.grid.hidden = VIEW.length === 0;
    if (!VIEW.length) {
      dom.emptyMsg.textContent = filters.q
        ? `Nothing matches “${filters.q}”. Try a shorter term or clear your filters.`
        : 'No builds match these filters. Try turning one off.';
    }
  }

  /* --------------------------------------------------------------- cards -- */
  function labelFor(e) {
    if (e.version) return e.version;
    if (e.category === 'client') return 'CLIENT';
    if (e.category === 'extras') return 'EXTRA';
    return (e.name || '').toUpperCase();
  }

  function makeCard(e, index) {
    const fav = !!store.data.favs[e.id];
    const catLabel = (CAT.categories.find((c) => c.id === e.category) || {}).label || e.category;

    const card = el('article', {
      class: 'card' + (fav ? ' is-fav' : ''),
      role: 'listitem',
      tabindex: '0',
      'data-id': e.id,
      'data-index': index,
      'aria-label': `${e.name}, ${catLabel}, ${RT_LABEL[e.runtime] || e.runtime}, ${e.sizeText}. Press Enter for details, Space to launch.`,
    });

    const cover = el('div', {
      class: 'card-cover',
      style: `--cover:url('${coverFor(e)}')`,
    });

    cover.appendChild(el('span', { class: 'card-badge', 'data-rt': e.runtime, text: RT_LABEL[e.runtime] || '?' }));

    const favBtn = el('button', {
      class: 'card-fav',
      type: 'button',
      'aria-pressed': fav ? 'true' : 'false',
      'aria-label': (fav ? 'Remove ' : 'Add ') + e.name + (fav ? ' from' : ' to') + ' favourites',
      onclick: (ev) => { ev.stopPropagation(); toggleFav(e); },
    }, [svgIcon(fav ? 'i-star' : 'i-star-o')]);

    const playBtn = el('button', {
      class: 'card-play', type: 'button', 'aria-label': 'Launch ' + e.name,
      onclick: (ev) => { ev.stopPropagation(); launch(e); },
    }, [svgIcon('i-play')]);

    cover.append(favBtn, el('span', { class: 'card-cover-label', text: labelFor(e) }), playBtn);

    const meta = el('div', { class: 'card-meta' });
    meta.appendChild(el('span', { text: catLabel }));
    meta.appendChild(el('span', { class: 'dot', text: '·' }));
    meta.appendChild(el('span', { text: e.sizeText }));
    (e.tags || []).forEach((t) => {
      meta.appendChild(el('span', { class: 'tag-mini', 'data-tag': t, text: t }));
    });
    if (store.data.plays[e.id]) {
      meta.appendChild(el('span', { class: 'tag-mini', text: store.data.plays[e.id] + '×' }));
    }

    card.append(cover, el('div', { class: 'card-body' }, [
      el('h3', { class: 'card-title', text: e.name }),
      meta,
    ]));

    card.addEventListener('click', () => openDrawer(e));
    card.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); openDrawer(e); }
      else if (ev.key === ' ') { ev.preventDefault(); launch(e); }
      else if (ev.key === 'f' || ev.key === 'F') { ev.preventDefault(); toggleFav(e); }
    });

    return card;
  }

  function renderGrid() {
    dom.grid.setAttribute('data-view', store.data.settings.view);
    dom.grid.textContent = '';
    const frag = document.createDocumentFragment();
    VIEW.forEach((e, i) => frag.appendChild(makeCard(e, i)));
    dom.grid.appendChild(frag);
    FOCUS_INDEX = -1;
  }

  /* ------------------------------------------------------------- sidebar -- */
  function renderSidebar() {
    // eras
    dom.catList.textContent = '';
    const allBtn = el('button', {
      class: 'cat-item', type: 'button', 'aria-current': filters.cats.size ? 'false' : 'true',
      onclick: () => { filters.cats.clear(); applyFilters(); renderSidebar(); },
    }, [
      el('span', { class: 'cat-dot', style: 'background:var(--accent)' }),
      el('span', { class: 'cat-name', text: 'All eras' }),
      el('span', { class: 'cat-count', text: CAT.count }),
    ]);
    dom.catList.appendChild(allBtn);

    CAT.categories.forEach((c) => {
      const on = filters.cats.has(c.id);
      dom.catList.appendChild(el('button', {
        class: 'cat-item', type: 'button', 'aria-current': on ? 'true' : 'false',
        'aria-label': `${c.label}, ${c.count} builds`,
        onclick: () => {
          if (filters.cats.has(c.id)) filters.cats.delete(c.id); else filters.cats.add(c.id);
          applyFilters(); renderSidebar();
        },
      }, [
        el('span', { class: 'cat-dot', style: `background:${CAT_COLORS[c.id] || 'var(--accent)'}` }),
        el('span', { class: 'cat-name', text: c.label }),
        el('span', { class: 'cat-count', text: c.count }),
      ]));
    });

    // type + runtime chips
    const chipRow = (host, items, set) => {
      host.textContent = '';
      items.forEach((it) => {
        host.appendChild(el('button', {
          class: 'chip', type: 'button', 'aria-pressed': set.has(it.id) ? 'true' : 'false',
          onclick: () => {
            if (set.has(it.id)) set.delete(it.id); else set.add(it.id);
            applyFilters(); renderSidebar();
          },
        }, [el('span', { text: it.label }), el('span', { class: 'chip-count', text: it.count })]));
      });
    };
    chipRow(dom.typeList, CAT.types, filters.types);
    chipRow(dom.runtimeList, CAT.runtimes, filters.rts);

    // stats
    const biggest = CAT.versions.reduce((a, b) => (b.size > a.size ? b : a), CAT.versions[0]);
    const stats = [
      ['Builds', CAT.count],
      ['Total size', CAT.totalSizeText],
      ['Vanilla', CAT.versions.filter((v) => v.type === 'vanilla').length],
      ['Clients', CAT.versions.filter((v) => v.type === 'client').length],
      ['JavaScript', CAT.versions.filter((v) => v.runtime === 'js').length],
      ['WebAssembly', CAT.versions.filter((v) => v.runtime !== 'js').length],
      ['Largest build', biggest.sizeText],
    ];
    dom.vaultStats.textContent = '';
    stats.forEach(([k, v]) => {
      dom.vaultStats.append(el('dt', { text: k }), el('dd', { text: String(v) }));
    });
  }

  function renderActiveFilters() {
    dom.activeFilters.textContent = '';
    const chips = [];
    if (filters.favsOnly) chips.push(['Favourites only', () => setFavsOnly(false)]);
    filters.cats.forEach((id) => {
      const c = CAT.categories.find((x) => x.id === id);
      chips.push([c ? c.label : id, () => { filters.cats.delete(id); applyFilters(); renderSidebar(); }]);
    });
    filters.types.forEach((id) => {
      const t = CAT.types.find((x) => x.id === id);
      chips.push([t ? t.label : id, () => { filters.types.delete(id); applyFilters(); renderSidebar(); }]);
    });
    filters.rts.forEach((id) => {
      const r = CAT.runtimes.find((x) => x.id === id);
      chips.push([r ? r.label : id, () => { filters.rts.delete(id); applyFilters(); renderSidebar(); }]);
    });
    if (filters.hideDupes) chips.push(['No duplicates', () => { filters.hideDupes = false; $('#optDupes').checked = false; applyFilters(); }]);
    if (filters.lightOnly) chips.push(['Under 25 MB', () => { filters.lightOnly = false; $('#optLight').checked = false; applyFilters(); }]);
    if (filters.q.trim()) chips.push([`“${filters.q.trim()}”`, () => { dom.search.value = ''; filters.q = ''; dom.searchClear.hidden = true; applyFilters(); }]);

    dom.activeFilters.hidden = chips.length === 0;
    chips.forEach(([label, fn]) => {
      dom.activeFilters.appendChild(el('button', {
        class: 'active-chip', type: 'button', onclick: () => { fn(); },
      }, [el('span', { text: label }), svgIcon('i-close')]));
    });
  }

  /* ---------------------------------------------------------------- hero -- */
  function renderHero() {
    const vanilla = CAT.versions.filter((v) => v.type === 'vanilla').length;
    dom.heroSub.textContent =
      `${CAT.count} playable builds — ${vanilla} vanilla versions from rd-131655 to 26.2, ` +
      `plus ${CAT.versions.filter((v) => v.type === 'client').length} clients. ` +
      `Pick one and it boots straight in your browser.`;
    dom.heroStats.textContent = '';
    [
      ['Builds', CAT.count],
      ['Archive size', CAT.totalSizeText],
      ['Eras', CAT.categories.length],
      ['Clients', CAT.versions.filter((v) => v.type === 'client').length],
    ].forEach(([k, v]) => {
      dom.heroStats.appendChild(el('div', {}, [el('dt', { text: k }), el('dd', { text: String(v) })]));
    });
    dom.footerMeta.textContent =
      `Catalogue generated ${CAT.generated} · ${CAT.count} builds · ${CAT.totalSizeText} total`;
    dom.search.placeholder = `Search ${CAT.count} builds…`;
  }

  function renderRecents() {
    const recents = store.data.recents.slice(0, 10)
      .map((r) => ({ r, e: byId(r.id) }))
      .filter((x) => x.e);
    dom.recentsWrap.hidden = recents.length === 0;
    dom.recentRow.textContent = '';
    recents.forEach(({ r, e }) => {
      dom.recentRow.appendChild(el('button', {
        class: 'recent-card', type: 'button',
        onclick: () => launch(e),
        'aria-label': `Play ${e.name}, last played ${fmtRelative(r.ts)}`,
      }, [
        el('span', { class: 'recent-thumb', style: `background-image:url('${coverFor(e)}')` }),
        el('span', { class: 'recent-meta' }, [
          el('span', { class: 'recent-name', text: e.name }),
          el('span', { class: 'recent-when', text: fmtRelative(r.ts) }),
        ]),
      ]));
    });

    // top hero button
    const next = recents.length ? recents[0].e : null;
    dom.btnPlayTop.innerHTML = '';
    dom.btnPlayTop.append(svgIcon('i-play'),
      document.createTextNode(next ? `Continue ${next.name}` : 'Play something random'));
    dom.btnPlayTop.onclick = () => {
      if (next) launch(next);
      else randomPick();
    };
  }

  /* ------------------------------------------------------------ drawer -- */
  function openDrawer(e) {
    activeEntry = e;
    lastFocused = document.activeElement;
    const cat = CAT.categories.find((c) => c.id === e.category) || { label: e.category };

    const panel = $('.drawer-panel', dom.drawer);
    const cover = $('#drawerCover');
    cover.style.setProperty('--cover', `url('${coverFor(e)}')`);
    $('#drawerCoverLabel').textContent = labelFor(e);
    $('#drawerEyebrow').textContent = cat.label + (e.type !== 'vanilla' ? ' · ' + e.type : '');
    $('#drawerTitle').textContent = e.name;

    const note = $('#drawerNote');
    if (e.note) { note.textContent = e.note; note.hidden = false; } else { note.hidden = true; }

    const specs = $('#drawerSpecs');
    specs.textContent = '';
    const rows = [
      ['Runtime', (CAT.runtimes.find((r) => r.id === e.runtime) || {}).label || e.runtime],
      ['Build type', (CAT.types.find((t) => t.id === e.type) || {}).label || e.type],
      ['Download size', e.sizeText],
      ['Plays', String(store.data.plays[e.id] || 0)],
    ];
    if (e.version) rows.unshift(['Version', e.version]);
    if (e.tags && e.tags.length) rows.push(['Tags', e.tags.join(', ')]);
    rows.push(['File', e.file]);
    rows.forEach(([k, v]) => specs.append(el('dt', { text: k }), el('dd', { text: v })));

    const favBtn = $('#drawerFav');
    const isFav = !!store.data.favs[e.id];
    favBtn.innerHTML = '';
    favBtn.append(svgIcon(isFav ? 'i-star' : 'i-star-o'),
      document.createTextNode(isFav ? ' Favourited' : ' Favourite'));
    favBtn.setAttribute('aria-pressed', isFav ? 'true' : 'false');
    favBtn.classList.toggle('is-active', isFav);
    favBtn.onclick = () => { toggleFav(e); openDrawer(e); };

    $('#drawerPlay').onclick = () => launch(e);
    $('#drawerNewTab').onclick = () => { window.open(e.url, '_blank', 'noopener'); };
    $('#drawerCopy').onclick = () => copyLink(e);

    dom.drawer.hidden = false;
    document.body.classList.add('is-locked');
    panel.scrollTop = 0;
    panel.focus();

    const hash = '#/build/' + e.id;
    if (location.hash !== hash) history.pushState(null, '', hash);
  }

  function closeDrawer() {
    if (dom.drawer.hidden) return;
    dom.drawer.hidden = true;
    if (!dom.player || dom.player.hidden) document.body.classList.remove('is-locked');
    if (lastFocused && lastFocused.focus) { try { lastFocused.focus(); } catch (_) {} }
    lastFocused = null;
    if (/^#\/build\//.test(location.hash)) history.pushState(null, '', '#/');
  }

  /* ------------------------------------------------------------ favourites */
  function toggleFav(e) {
    const on = !store.data.favs[e.id];
    if (on) store.data.favs[e.id] = Date.now();
    else delete store.data.favs[e.id];
    store.save();
    renderFavCount();
    renderRecents();
    // refresh just this card in place
    const card = dom.grid.querySelector(`.card[data-id="${CSS.escape(e.id)}"]`);
    if (card) {
      const idx = Number(card.dataset.index);
      const fresh = makeCard(e, idx);
      card.replaceWith(fresh);
    }
    toast(on ? 'Added to favourites' : 'Removed from favourites', 'i-star');
  }

  function renderFavCount() {
    const n = Object.keys(store.data.favs).length;
    dom.favCount.textContent = n;
    $('#btnFavs').setAttribute('aria-pressed', filters.favsOnly ? 'true' : 'false');
  }

  function setFavsOnly(on) {
    filters.favsOnly = on;
    renderFavCount();
    applyFilters();
    renderActiveFilters();
  }

  /* -------------------------------------------------------------- player -- */
  function recordPlay(e) {
    store.data.plays[e.id] = (store.data.plays[e.id] || 0) + 1;
    store.data.recents = [{ id: e.id, ts: Date.now() }]
      .concat(store.data.recents.filter((r) => r.id !== e.id))
      .slice(0, 24);
    store.save();
    renderRecents();
  }

  function launch(e) {
    if (!e) return;
    playerReturnHash = /^#\/build\//.test(location.hash) ? location.hash
      : (/^#\/play\//.test(location.hash) ? '#/' : location.hash);
    if (location.hash !== '#/play/' + e.id) history.pushState(null, '', '#/play/' + e.id);

    activeEntry = e;
    if (!dom.drawer.hidden) dom.drawer.hidden = true;

    dom.player.hidden = false;
    dom.playerTitle.textContent = e.name;
    document.body.classList.add('is-locked');

    dom.playerLoading.classList.remove('is-hidden');
    loadStart = Date.now();
    dom.playerLoadingText.textContent = `Loading ${e.name} — ${e.sizeText}…`;
    clearInterval(loadTimer);
    loadTimer = setInterval(() => {
      const s = Math.round((Date.now() - loadStart) / 1000);
      dom.playerLoadingText.textContent = `Still loading… ${s}s elapsed (${e.sizeText})`;
    }, 1000);

    dom.playerHint.innerHTML = e.size > HEAVY_LIMIT
      ? `This is a <b>${e.sizeText}</b> build — the first launch can take a minute on a slow connection.<br>` +
        `Once it's cached, later launches are much faster.`
      : `Click inside the game to capture your mouse. Press <b>Esc</b> in the game to release it.`;

    // clean slate
    dom.playerStage.querySelectorAll('iframe').forEach((f) => f.remove());
    const frame = el('iframe', {
      src: e.url,
      title: e.name,
      allow: 'autoplay; fullscreen; gamepad; clipboard-read; clipboard-write; web-share; microphone; display-capture; xr-spatial-tracking',
      allowfullscreen: true,
      referrerpolicy: 'no-referrer',
    });
    frame.addEventListener('load', () => {
      clearInterval(loadTimer);
      dom.playerLoading.classList.add('is-hidden');
    });
    frame.addEventListener('error', () => {
      clearInterval(loadTimer);
      dom.playerLoadingText.textContent = 'This build failed to load. Try reloading or open it in a new tab.';
    });
    dom.playerStage.appendChild(frame);
    $('#playerBack').focus({ preventScroll: true });
    recordPlay(e);
  }

  function closePlayer() {
    if (dom.player.hidden) return;
    dom.player.hidden = true;
    clearInterval(loadTimer);
    // unload the game so it stops using CPU / memory
    dom.playerStage.querySelectorAll('iframe').forEach((f) => { f.src = 'about:blank'; f.remove(); });
    document.body.classList.remove('is-locked');
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});

    if (/^#\/play\//.test(location.hash)) {
      history.pushState(null, '', playerReturnHash || '#/');
      if (/^#\/build\//.test(playerReturnHash) && activeEntry) openDrawer(activeEntry);
      else applyFilters();
    }
  }

  function randomPick() {
    const pool = VIEW.length ? VIEW : CAT.versions;
    const e = pool[Math.floor(Math.random() * pool.length)];
    launch(e);
    toast('Rolled ' + e.name, 'i-dice');
  }

  async function copyLink(e) {
    const url = location.origin + location.pathname + '#/build/' + e.id;
    try {
      await navigator.clipboard.writeText(url);
      toast('Link copied to clipboard', 'i-link');
    } catch (_) {
      prompt('Copy this link:', url);
    }
  }

  /* --------------------------------------------------------------- modal -- */
  const FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

  function openModal(node) {
    lastFocused = document.activeElement;
    node.hidden = false;
    document.body.classList.add('is-locked');
    $('.modal-panel', node).focus();
  }
  function closeModal(node) {
    node.hidden = true;
    if (dom.drawer.hidden && dom.player.hidden) document.body.classList.remove('is-locked');
    if (lastFocused && lastFocused.focus) { try { lastFocused.focus(); } catch (_) {} }
    lastFocused = null;
  }

  /** Keep Tab (and Shift+Tab) inside an open dialog. */
  function trapFocus(container, ev) {
    const items = $$(FOCUSABLE, container).filter((n) => n.offsetParent !== null || n === container);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
  }

  /* ------------------------------------------------------------- routing -- */
  function applyRoute() {
    const h = location.hash.replace(/^#\/?/, '');
    const m = h.match(/^(build|play)\/(.+)$/);
    if (m) {
      const e = byId(decodeURIComponent(m[2]));
      if (e) {
        if (m[1] === 'play') { if (dom.player.hidden || activeEntry?.id !== e.id) launch(e); }
        else { if (dom.drawer.hidden || activeEntry?.id !== e.id) openDrawer(e); }
        return;
      }
      toast('That build is not in the vault', 'i-warn');
    }
    if (dom.player.hidden === false) closePlayer();
    if (dom.drawer.hidden === false) closeDrawer();
  }

  /* ----------------------------------------------------------- keyboard -- */
  function gridKeyNav(ev) {
    const cols = getComputedStyle(dom.grid).gridTemplateColumns.split(' ').length;
    const cards = $$('.card', dom.grid);
    if (!cards.length) return;
    const perRow = store.data.settings.view === 'list' ? 1 : Math.max(1, cols);
    let next = -1;
    if (ev.key === 'ArrowRight') next = Math.min(cards.length - 1, FOCUS_INDEX + 1);
    else if (ev.key === 'ArrowLeft') next = Math.max(0, FOCUS_INDEX - 1);
    else if (ev.key === 'ArrowDown') next = Math.min(cards.length - 1, FOCUS_INDEX + perRow);
    else if (ev.key === 'ArrowUp') next = Math.max(0, FOCUS_INDEX - perRow);
    else if (ev.key === 'Home') next = 0;
    else if (ev.key === 'End') next = cards.length - 1;
    if (next >= 0) {
      ev.preventDefault();
      FOCUS_INDEX = next;
      cards[next].focus();
      cards[next].scrollIntoView({ block: 'nearest' });
    }
  }

  /* --------------------------------------------------------------- theme -- */
  function applyTheme() {
    const s = store.data.settings;
    document.documentElement.setAttribute('data-theme', s.theme);
    document.documentElement.setAttribute('data-accent', s.accent);
    $('#btnTheme').setAttribute('aria-label',
      s.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    $$('.accent-dot').forEach((d) => d.setAttribute('aria-pressed', d.dataset.accent === s.accent ? 'true' : 'false'));
  }

  /* ---------------------------------------------------------------- init -- */
  function buildAccentPicker() {
    const row = el('div', { class: 'accent-row', role: 'group', 'aria-label': 'Accent colour' });
    [['emerald', '#4ade80'], ['cyan', '#22d3ee'], ['amber', '#fbbf24'], ['violet', '#a78bfa']]
      .forEach(([id, color]) => {
        row.appendChild(el('button', {
          class: 'accent-dot', type: 'button', 'data-accent': id,
          style: `background:${color}`, 'aria-label': id + ' accent',
          'aria-pressed': store.data.settings.accent === id ? 'true' : 'false',
          onclick: () => { store.data.settings.accent = id; store.save(); applyTheme(); },
        }));
      });
    $('#optLight').closest('.side-block').appendChild(
      el('div', {}, [el('h3', { class: 'side-title', style: 'margin-top:12px', text: 'Accent' }), row]));
  }

  function wire() {
    // search
    let debounce;
    dom.search.addEventListener('input', () => {
      dom.searchClear.hidden = !dom.search.value;
      clearTimeout(debounce);
      debounce = setTimeout(() => { filters.q = dom.search.value; applyFilters(); }, 110);
    });
    dom.searchClear.addEventListener('click', () => {
      dom.search.value = ''; dom.searchClear.hidden = true; filters.q = ''; applyFilters(); dom.search.focus();
    });

    // topbar
    $('#btnRandom').addEventListener('click', randomPick);
    $('#btnRandomHero').addEventListener('click', randomPick);
    $('#btnFavs').addEventListener('click', () => setFavsOnly(!filters.favsOnly));
    $('#btnHelp').addEventListener('click', () => openModal($('#helpModal')));
    $('#btnTheme').addEventListener('click', () => {
      store.data.settings.theme = store.data.settings.theme === 'dark' ? 'light' : 'dark';
      store.save(); applyTheme();
    });

    // sort + view
    dom.sortBy.value = store.data.settings.sort;
    dom.sortBy.addEventListener('change', () => {
      store.data.settings.sort = dom.sortBy.value; store.save(); applyFilters();
    });
    const setView = (v) => {
      store.data.settings.view = v; store.save();
      dom.grid.setAttribute('data-view', v);
      $('#btnGrid').classList.toggle('is-active', v === 'grid');
      $('#btnList').classList.toggle('is-active', v === 'list');
      $('#btnGrid').setAttribute('aria-pressed', v === 'grid' ? 'true' : 'false');
      $('#btnList').setAttribute('aria-pressed', v === 'list' ? 'true' : 'false');
    };
    $('#btnGrid').addEventListener('click', () => setView('grid'));
    $('#btnList').addEventListener('click', () => setView('list'));
    setView(store.data.settings.view);

    // options
    $('#optDupes').addEventListener('change', (ev) => {
      filters.hideDupes = ev.target.checked;
      store.data.settings.hideDupes = ev.target.checked; store.save(); applyFilters();
    });
    $('#optLight').addEventListener('change', (ev) => {
      filters.lightOnly = ev.target.checked;
      store.data.settings.lightOnly = ev.target.checked; store.save(); applyFilters();
    });
    $('#btnReset').addEventListener('click', resetFilters);
    $('#btnEmptyReset').addEventListener('click', resetFilters);

    // sidebar (mobile)
    const openSidebar = () => {
      dom.sidebar.classList.add('is-open');
      dom.scrim.hidden = false;
      $('#btnMenu').setAttribute('aria-expanded', 'true');
    };
    const closeSidebar = () => {
      dom.sidebar.classList.remove('is-open');
      dom.scrim.hidden = true;
      $('#btnMenu').setAttribute('aria-expanded', 'false');
    };
    $('#btnMenu').addEventListener('click', openSidebar);
    $('#btnCloseSidebar').addEventListener('click', closeSidebar);
    dom.scrim.addEventListener('click', closeSidebar);

    // drawer / modal close affordances
    $$('[data-close]').forEach((n) => n.addEventListener('click', () => {
      const modal = n.closest('.modal');
      if (modal) closeModal(modal); else closeDrawer();
    }));

    // player
    $('#playerBack').addEventListener('click', closePlayer);
    $('#playerQuit').addEventListener('click', closePlayer);
    $('#playerReload').addEventListener('click', () => {
      const iframe = dom.playerStage.querySelector('iframe');
      if (!iframe) return;
      dom.playerLoading.classList.remove('is-hidden');
      loadStart = Date.now();
      dom.playerLoadingText.textContent = 'Reloading…';
      clearInterval(loadTimer);
      loadTimer = setInterval(() => {
        dom.playerLoadingText.textContent = `Still loading… ${Math.round((Date.now() - loadStart) / 1000)}s elapsed`;
      }, 1000);
      iframe.src = iframe.src;
    });
    $('#playerFull').addEventListener('click', toggleFullscreen);
    $('#playerTab').addEventListener('click', () => { if (activeEntry) window.open(activeEntry.url, '_blank', 'noopener'); });

    // global keys
    document.addEventListener('keydown', (ev) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');

      if ((ev.ctrlKey || ev.metaKey) && ev.shiftKey && ev.key.toLowerCase() === 'q') {
        ev.preventDefault(); closePlayer(); return;
      }
      if ((ev.ctrlKey || ev.metaKey) && ev.shiftKey && ev.key.toLowerCase() === 'f') {
        ev.preventDefault(); toggleFullscreen(); return;
      }
      if (ev.key === 'Tab') {
        const openDialog = $('.drawer:not([hidden]) .drawer-panel')
          || $('.modal:not([hidden]) .modal-panel');
        if (openDialog) trapFocus(openDialog, ev);
        return;
      }
      if (ev.key === 'Escape') {
        if (!$('#helpModal').hidden) { closeModal($('#helpModal')); return; }
        if (!dom.drawer.hidden) { closeDrawer(); return; }
        if (dom.sidebar.classList.contains('is-open')) { closeSidebar(); return; }
        if (typing) { document.activeElement.blur(); return; }
        return;
      }
      if (typing) return;

      if (ev.key === '/') { ev.preventDefault(); dom.search.focus(); dom.search.select(); return; }
      if (ev.key === '?' ) { ev.preventDefault(); openModal($('#helpModal')); return; }
      if (ev.key.toLowerCase() === 'r' && !ev.ctrlKey && !ev.metaKey && dom.player.hidden) {
        ev.preventDefault(); randomPick(); return;
      }
      if (document.activeElement?.classList?.contains('card')) gridKeyNav(ev);
    });

    window.addEventListener('hashchange', applyRoute);
    window.addEventListener('popstate', applyRoute);
  }

  function toggleFullscreen() {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else dom.player.requestFullscreen?.().catch(() => {
      toast('Fullscreen was blocked by the browser', 'i-warn');
    });
  }

  function resetFilters() {
    filters.q = ''; dom.search.value = ''; dom.searchClear.hidden = true;
    filters.cats.clear(); filters.types.clear(); filters.rts.clear();
    filters.favsOnly = false; filters.hideDupes = false; filters.lightOnly = false;
    $('#optDupes').checked = false; $('#optLight').checked = false;
    dom.sidebar.classList.remove('is-open'); dom.scrim.hidden = true;
    renderFavCount(); renderSidebar(); applyFilters();
    toast('Filters reset', 'i-filter');
  }

  /* ----------------------------------------------------------- bootstrap -- */
  async function init() {
    store.load();
    applyTheme();
    wire();

    try {
      await loadCatalog();
    } catch (err) {
      dom.boot.querySelector('.boot-text').innerHTML =
        'Could not load <code>data/versions.json</code>.<br><br>' +
        'If you opened this file directly from disk, run a local server instead:' +
        '<br><code>python3 -m http.server</code>';
      console.error(err);
      return;
    }

    renderHero();
    // restore saved toggles
    $('#optDupes').checked = !!store.data.settings.hideDupes;
    $('#optLight').checked = !!store.data.settings.lightOnly;
    filters.hideDupes = !!store.data.settings.hideDupes;
    filters.lightOnly = !!store.data.settings.lightOnly;

    buildAccentPicker();
    renderSidebar();
    renderFavCount();
    renderRecents();
    applyFilters();
    applyTheme();

    dom.boot.classList.add('is-done');
    setTimeout(() => { dom.boot.hidden = true; }, 400);

    applyRoute();

    // register the offline shell (never caches the multi-MB game files)
    if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
      navigator.serviceWorker.register('./sw.js').catch(() => {});
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
