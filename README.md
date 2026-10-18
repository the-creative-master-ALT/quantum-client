# Quantum Launcher

A self-contained browser launcher for the Eaglercraft archive. The launcher is
one file: **`index.html` contains its markup, styles, JavaScript, embedded build
catalogue, inline SVG artwork, and favicon.** It has no external scripts,
stylesheets, fonts, image requests, package install, or build step.

The page is designed for GitHub Pages and also opens directly from `file://`.
The individual game builds remain separate HTML files and are loaded only when
launched.

## Archive

- **134 builds · 2.58 GB** of game payloads
- **111 chronological builds**, from `rd-131655` through `26.3`
- **21 clients** in their own scroll wheel
- **2 bonus-game launch buttons**: Minecraft 4K and Minicraft

Both selectors are iPhone-style vertical picker wheels: options curve and fade
above and below a fixed center slot, and scrolling snaps a build into that slot.
The timeline runs from the earliest RD build through 26.3; the client picker is
independent. The full-stage artwork follows the centered selection. Minecraft
4K and Minicraft stay pinned at the bottom of the library rail.

Keyboard shortcuts: **↑ / ↓** or **← / →** browse the active wheel, **Enter**
launches the selected build, **F** saves it, **/** opens the download library,
and **Esc** closes the library.

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
tools/join_build_parts.py    verified chunk reassembly
tools/verify_catalog.py      low-I/O catalogue / Git-index audit
tools/smoke-test.js          jsdom interaction and self-containment tests
tools/make_scenes.py         inline SVG scene generator
```

The game ports remain independent single-file HTML builds created by their
authors; the launcher indexes these local files without bundling them into
`index.html`.
