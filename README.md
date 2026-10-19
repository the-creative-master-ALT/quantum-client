# Quantum Launcher

A self-contained browser launcher for the Eaglercraft archive. The launcher is
one file: **`index.html` contains its markup, styles, JavaScript, embedded build
catalogue, inline SVG artwork, favicon, boot intro, and mod sources.** It has no
external scripts, stylesheets, fonts, image requests, package install, or build
step.

The page is designed for GitHub Pages and also opens directly from `file://`.
The individual game builds remain separate HTML files and are loaded only when
launched.

## The launcher flow

1. **Boot intro** — three animated atoms, the letters of EAGLERCRAFT appearing
   one by one, then a QUANTUM LAUNCHER wordmark and progress bar. It lasts about
   three seconds and can be skipped, replayed from Settings → Advanced, or
   disabled with Settings → Behavior → Boot animation.
2. **Home** — the wordmark, a PLAY button, Settings, GitHub, Mods, and a shortcut
   to the build library, all over an animated artwork backdrop.
3. **Play chooser** — PLAY asks for **Vanilla**, **Clients**, **Extras**, or
   **Custom HTML**. Vanilla and Clients open the stage with that wheel selected
   in the sidebar. Extras opens a two-button menu for Minecraft 4K and Minicraft.
   Custom HTML accepts your own single-file builds (file picker or drag and
   drop), stores them in this browser with IndexedDB, and launches them in the
   embedded player.

## Mods

Ten mods ship inline, all written for **EaglerForge**. The launcher does not
inject mod code into game pages: it hands you the `.js` file and EaglerForge
loads it itself.

- **Coal-Xray** — `X` hides everything but ores, chests, and furnaces.
- **Fullbright** — `PageUp` pushes gamma to 1000 for a lit-up world.
- **AutoRespawn** — respawns you the instant you die.
- **Autoclicker** — clicks twice per second.
- **Duck Entity** — a modelled duck with AI, textures, and quacks.
- **Grapple Hook** — hook a block and get pulled toward it; crouch to cancel.
- **Music Player** — a draggable player; name tracks and paste audio URLs.
- **Screenshot** — press `F2` to save a PNG of the game canvas.
- **Keystrokes HUD** and **Custom Crosshair** — overlay widgets for the game window.

To use one: open **Mods**, press **Download .js**, then launch **Clients →
EaglerForge** (or **Play EaglerForge** in the Mods panel) and add the file
through its in-game mod manager (`ModGUI.js`). Nothing is installed
automatically, and the other archive builds do not get mods — they launch as
shipped. EaglerForge is a multi-file web build (`EaglerForge/index.html` +
`classes.js`, `assets.epk`, `lang/`), so it must be served over HTTP; opening it
from `file://` is blocked by its own loader.

The archive also contains **Eaglet** (Eaglercraft packed into 2.7 MB) and
**Resent Client 1.8.8**.

## Archive

- **137 builds · 2.65 GB** of game payloads
- **111 chronological builds**, from `rd-131655` through `26.3`
- **24 clients** in their own scroll wheel
- **2 bonus games**, reachable only through **Extras**: Minecraft 4K and Minicraft

Both selectors are iPhone-style vertical picker wheels that live in the library
rail: options curve and fade above and below a fixed center slot, and scrolling
snaps a build into that slot. A Vanilla / Clients switch at the top of the rail
(and the Play chooser) decides which wheel is shown. The full-stage artwork
follows the centered selection. Minecraft 4K and Minicraft are never listed
outside the Extras menu.

Keyboard shortcuts: **↑ / ↓** or **← / →** browse the active wheel, **Enter**
launches the selected build, **F** saves it, **/** opens the download library,
**,** opens settings, and **Esc** closes a dialog or returns home.

## Chunked uploads

Big builds arrive as chat-size chunks. The chunks are **not** in a reliable
order and exact byte splits share no repeated text, so join them from content,
not from the file names:

```bash
python3 tools/assemble_parts.py "incoming/chunk-*.html" \
    --name "My Client" --add
```

`assemble_parts.py` finds the chunk that opens the document and the one that
ends in `</html>`, orders the rest between them, then refuses to import anything
that does not start with `<!DOCTYPE` and end with `</html>`. Partial joins are
deleted so a half build can never be launched. `incoming/` is git-ignored.

The mod-capable build here is **EaglerForge** (tagged `modapi` in the
catalogue). Download a mod from the Mods panel and load it inside EaglerForge;
the launcher itself never injects scripts into a game page.

## Work in a sparse checkout

The game files are large, so a launcher-only checkout is the recommended way
to make UI changes. Git's blob filter avoids fetching game payloads, and sparse
checkout keeps them out of the working tree:

```bash
git clone --filter=blob:none --sparse https://github.com/the-creative-masterALT/quantum-client.git
cd quantum-client
git sparse-checkout set --no-cone '/*' '!/*.html' '/index.html'
```

This is enough to edit and test `index.html`, but the omitted game files cannot
be launched locally. The published site still serves the complete archive.

`tools/verify_catalog.py` checks the embedded catalogue against Git's index and
checks file sizes for any builds already materialized; it does not read or
fetch the game payloads. The catalog generator and build importer deliberately
refuse to run from an incomplete sparse checkout, rather than replacing the
catalogue with a partial one.

## Local preview and tests

Open `index.html` directly, or serve it over HTTP:

```bash
python3 -m http.server 8080 --bind 0.0.0.0
```

Install the smoke-test dependency outside the repository, then run the UI
suite and catalogue audit:

```bash
npm install --prefix /tmp/quantum-test jsdom
NODE_PATH=/tmp/quantum-test/node_modules node tools/smoke-test.js
python3 tools/verify_catalog.py
```

The smoke suite runs the real inline launcher in jsdom and works with either a
full or sparse checkout. In a sparse checkout, catalogue links are checked
against Git's tracked files rather than requiring the game blobs on disk.

## Importing a build

A new single-file game can be imported with:

```bash
python3 tools/add_build.py /path/to/build.html --name "Eaglercraft 26.4"
```

The importer validates the input and refreshes the embedded catalogue. It
requires the archive files to be materialized; do not run the generator against
a sparse directory listing. For chunked uploads, `tools/join_build_parts.py`
reassembles the pieces only after the expected size and SHA-256 match.

## Project files

```text
index.html                   complete launcher, including catalogue and SVG scenes
tools/generate_catalog.py    catalogue builder with sparse-checkout safety checks
tools/embed_catalog.py       embeds the generated catalogue in index.html
tools/add_build.py           validated build import
tools/join_build_parts.py    verified chunk reassembly (needs a known hash)
tools/assemble_parts.py      content-ordered chunk join + validated import
tools/verify_catalog.py      low-I/O catalogue / Git-index audit
tools/smoke-test.js          jsdom interaction and self-containment tests
tools/make_scenes.py         inline SVG scene generator
```

The game ports remain independent single-file HTML builds created by their
authors; the launcher indexes these local files without bundling them into
`index.html`.
