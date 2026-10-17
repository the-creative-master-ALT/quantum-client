# 🟩 Quantum Launcher

**137 self-contained Eaglercraft builds. One HTML file.**

This repo started as a pile of loose `.html` game files. It is now a launcher
that indexes every build, groups them by era, and boots any of them — no
install, no Java, no build step, no server-side anything.

Live at **<https://the-creative-masteralt.github.io/quantum-client/>**

---

## One file, that's it

`index.html` is the entire launcher. Not "the entry point" — the whole thing:

| | |
|---|---|
| **Markup** | inline |
| **CSS** | inline `<style>` |
| **JavaScript** | inline `<script>` |
| **Build catalogue** (137 entries) | inline `<script type="application/json">` |
| **Artwork** (11 scenes) | inline `<svg>` symbols |
| **Favicon** | inline `data:image/svg+xml` URI |

There is **no** CSS file, no JS file, no JSON fetch, and not a single image
file. That is deliberate:

- **It works from `file://`.** Double-click it. No server, no CORS, no `fetch`
  failing on local files.
- **It works offline.** Nothing to download.
- **You can move it, email it, or drop it on a USB stick** and it still runs —
  as long as the game `.html` files sit next to it.

Total weight: **~82 KB**, of which ~33 KB is the build catalogue.

| | |
|---|---|
| **137 builds** | `rd-131655` (May 2009) → `26.3`, plus 20 clients and a few bonus games |
| **10 groups** | Pre-Classic, Classic, Devs, Alpha, Beta, Early / Middle / Modern Releases, Clients, Extras |
| **2.68 GB** | 84 JavaScript · 46 WebAssembly-GC · 7 WebAssembly |
| **Zero dependencies** | No framework, no CDN, no npm, no build step |

---

## Layout

The same layout at **every** screen size — a smaller window scales the whole
thing down rather than reflowing it into something unrecognisable. The sidebar
stays a sidebar and the dock stays a dock.

```
┌──────────────┬──────────────────────────────────────┐
│              │                                      │
│  SIDEBAR     │         ONE GIANT ARTWORK            │
│              │                                      │
│  All builds  │   ┌────────────────────────────────┐ │
│  Pre-Classic │   │                                │ │
│  Classic     │   │   inline SVG scene, 16:9,      │ │
│  Devs        │   │   unique per group, with the   │ │
│  Alpha       │   │   group name baked in as text   │ │
│  Beta        │   │                                │ │
│  Early ▸     │   └────────────────────────────────┘ │
│  Middle ▸    │                                      │
│  Modern ▸    │   ┌────────────────────────────────┐ │
│  Clients     │   │ build name · size · runtime    │ │
│  Extras      │   │ chip          [★]   [▶ Play]   │ │
│              │   └────────────────────────────────┘ │
│  ─────────   │                                      │
│  ★ Starred   │                                      │
│  ↺ Recent    │                                      │
│  ─────────   │                                      │
│  ⬇ Downloads                                   137  │
├──────────────┴──────────────────────────────────────┤
│  [ build ▾ ]  [◀][▶]  2 / 32                [◐]     │
└─────────────────────────────────────────────────────┘
```

- **Sidebar** — the ten groups, each with a live count. Pick one and the
  artwork, the dropdown and the build card all follow.
- **Giant artwork** — a unique inline SVG scene per group, with the group name
  and its version range drawn right into the art.
- **Downloads** — pinned at the bottom of the sidebar. Opens a panel listing
  **all 137 builds**, searchable, each with a direct download button. Grab any
  build, or narrow it to the current group first.
- **Bottom bar** — the dropdown lists the builds in whichever group you picked
  ("All builds" lists every one), plus step arrows and the theme toggle.

Keyboard: <kbd>↑</kbd><kbd>↓</kbd> or <kbd>←</kbd><kbd>→</kbd> to step through
builds, <kbd>Enter</kbd> to play, <kbd>/</kbd> to open Downloads,
<kbd>Esc</kbd> to close.

### How the scaling works

There are deliberately **no layout breakpoints**. Instead `--s` is computed as

```
--s = clamp(0.4, min(1, width / 1400, height / 860), 1)
```

and the shell is drawn `1 / --s` times too big, then `transform: scale(--s)`ed
back down from the top-left corner — so it lands exactly on the viewport with
the identical layout, just smaller. 1400×860 is the size the design is drawn
for; anything larger renders 1:1.

| Viewport | Scale | Sidebar |
|---|---:|---:|
| 1920×1080 | 1.00 | 264 px |
| 1366×768 | 0.89 | 235 px |
| 1280×720 | 0.84 | 221 px |
| 1024×768 | 0.73 | 193 px |

---

## The artwork

Every group has its own hand-coded SVG scene — no photography, no generated
imagery, no binary assets at all:

| Group | Scene |
|---|---|
| All builds | night panorama, silhouetted ranges, stars |
| Pre-Classic | cold dawn over raw, untextured cubes |
| Classic | bright blue sky, blocky clouds, flat green plains |
| Devs | torch-lit cave with an InDev house and a floating island |
| Alpha | purple-and-orange sunset over water |
| Beta | low golden sun, rolling hills, a lake |
| Early Releases | village houses beside a glowing Nether portal |
| Middle Releases | End-city spires under a violet sky |
| Modern Releases | snow-capped peaks, aurora, glowing deep-dark crystals |
| Clients | neon grid horizon and a cyber skyline |
| Extras | scattered blocks, a star, a gear |

Each carries its name and version range as real SVG text, so it scales cleanly
and stays sharp on high-DPI screens.

---

## Adding a build

1. Drop the single-file `.html` into the **repository root** — that is where
   the launcher looks for builds.
2. Re-embed the catalogue:

   ```bash
   python3 tools/embed_catalog.py --regen
   ```

   That rescans the root, rebuilds the catalogue, rewrites the JSON block
   inside `index.html`, and cleans up the intermediate file. Then just commit
   `index.html`.

### Adding a big build (the 90 MB case)

Chat uploads cap around 25 MB, so a large build has to arrive in pieces. Split
it, send the chunks, reassemble, verify, and import in one go:

```bash
split -n 4 -d --additional-suffix=.html 26.3-wasm.html 26.3-wasmp

# once every chunk is uploaded:
python3 tools/join_build_parts.py ~/incoming/26.3-wasmp*.html \
    --size 90804846 \
    --sha256 cc6996731471299161f492321d4b1d2db61df3a96fcd0803090e22a07a44a62b \
    --out /tmp/26.3-wasm.html

python3 tools/add_build.py /tmp/26.3-wasm.html --name "Eaglercraft 26.3-WASM" --move
```

`join_build_parts.py` sorts by the trailing number (so `p10` never precedes
`p2`) and will not hand you a file unless the checksum matches. Never skip
that check — a build that is off by one byte just silently fails to boot.

`add_build.py` detects HTML hiding under any extension, renames it to
`.html`, refuses anything over 100 MB (GitHub's hard limit), rejects
byte-identical duplicates, and re-embeds the catalogue for you.

> **Do not use Git LFS for the game builds.** Pages serves the LFS *pointer*
> file, so the build would silently stop working. GitHub's large-file warning
> on push is expected and safe to ignore.

### Fixing a mis-detected build

Filenames and `<title>` tags are unreliable across these builds — roughly
fifteen of them claim to be "EaglercraftX 1.8", and two say
"My Drive - Google Drive". When the auto-detection gets one wrong, add an
entry to the `OVERRIDES` table in `tools/generate_catalog.py` and re-run
`embed_catalog.py --regen`.

---

## Running locally

```bash
python3 -m http.server 8080
# → http://localhost:8080
```

Or just open `index.html` directly — it is designed to work from `file://`.

Heads-up: launching a build downloads that whole `.html`, so expect 10–90 MB
per game on the first hit.

### Recovering after a sandbox recycle

A recycle hands you back a clean clone at the base commit: `index.html` and the
90 MB `26.3` build are gone, the remote-tracking ref is gone, and `jsdom` is
gone from `/tmp`. One command puts it back:

```bash
./tools/resume.sh            # repair, then serve
./tools/resume.sh --test     # ...then run the smoke suite
./tools/resume.sh --check    # verify only, change nothing
./tools/resume.sh --force    # allow a reset despite uncommitted edits
```

Every step is idempotent, so it is safe to run on a healthy checkout. It ends
by checking that every build in the catalogue still serves, and that the
served page actually contains the embedded catalogue — a page returning 200
with no data would otherwise look fine.

> The script lives inside the branch, so a recycle deletes it too. Keep the
> manual path handy:
> ```bash
> git fetch origin <branch> && git reset --hard FETCH_HEAD
> git branch --set-upstream-to=origin/<branch>
> mkdir -p /tmp/testenv && cd /tmp/testenv && npm install jsdom
> python3 -m http.server 8080 --bind 0.0.0.0
> ```

---

## Project layout

```
index.html                     the entire launcher (markup + CSS + JS + data + SVG art)
Eaglercraft 26.3-WASM.html     ← 137 game builds live in the root, alongside it
rd-131655-JS.html
...

tools/
  generate_catalog.py          scans the root *.html, writes the catalogue
  embed_catalog.py             folds that catalogue into index.html
  add_build.py                 one-command import for a new build
  join_build_parts.py          reassembles chunked uploads, verifies SHA-256
  smoke-test.js                54 assertions against the real page (jsdom)
  resume.sh                    recovery after a sandbox recycle
```

Run the tests with:

```bash
mkdir -p /tmp/testenv && cd /tmp/testenv && npm install jsdom
NODE_PATH=/tmp/testenv/node_modules node tools/smoke-test.js
```

---

## Notes and caveats

- **4 byte-identical duplicates were removed** (90.7 MB reclaimed). Each was
  bit-for-bit identical to a file we kept, verified by MD5, and the survivor
  has the better name — the two `20100233` files carried a typo'd date; the
  real one is `20100223`. They are listed in `EXCLUDE` in
  `tools/generate_catalog.py` so they cannot come back.
- **The archive is 2.68 GB**, over GitHub Pages' 1 GB guidance. It serves fine
  today (legacy branch build, no compilation step).
- **Builds must end in `.html`.** Pages serves a `.docx` with a Word MIME type,
  so the browser would download it instead of running it.
- Two builds reach out to the network at runtime: `Minicraft.html` loads assets
  from `api.webmc.xyz`, and `injector.html` pulls Rollup from `unpkg.com`.
  Both work on Pages; both fail in a sandboxed preview.
- Filenames contain spaces, so links are percent-encoded (`%20`).

## Credits

Every build here was made by other people — the Eaglercraft authors, the
Minecraft client ports, and the client-pack developers. This is only a launcher
that indexes them.
