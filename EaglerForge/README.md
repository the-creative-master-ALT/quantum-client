# EaglerForge (vendored build)

Unmodified (except the page title) EaglerForge v1.3.2 web build, fetched from
<https://github.com/eaglerforge/EaglerForge-builds> (`web/v1.3.2`).

EaglerForge is EaglercraftX 1.8 with Eaglercraft's **ModAPI** wired in, plus an
in-game mod manager (`ModLoader.js`, `ModGUI.js`, `ModAPI.js`).

It cannot be a single HTML file: the game loads `assets.epk`, `lang/*.lang`,
and 31 MB of compiled classes alongside the page, so it ships as a directory.
The launcher catalogue points at `EaglerForge/index.html`.

To use launcher mods: download a mod from the launcher's Mods panel, open
EaglerForge, then load it through the in-game Mods menu.

Upstream license: MIT (see the EaglerForge repositories).
