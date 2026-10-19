#!/usr/bin/env python3
"""
generate_catalog.py
===================

Scans every ``*.html`` game file in the repository root and builds
``data/versions.json`` -- the catalogue that powers the EaglerVault launcher.

The launcher is 100% static (GitHub Pages), so the catalogue has to be a
plain JSON file that is committed alongside the site.  Re-run this script
afterever you drop a new game .html into the repo::

    python3 tools/generate_catalog.py

It is deterministic: same files in, same JSON out (modulo file sizes).

Metadata that is derived automatically
--------------------------------------
* file name, file size, <title> (for reference / debugging)
* runtime  -- from the file name first, then by sniffing the payload
* category -- Pre-Classic / Classic / Indev / Infdev / Alpha / Beta /
              Release / Client / Extras
* version  -- normalised version string + numeric sort key
* tags     -- e.g. "mobile", "forge", "multiplayer", "test-build"

Anything the heuristics cannot know (which build is a client, which
"EaglercraftX 1.8" file is *actually* 1.7.10, what a file is called) lives in
the curated ``OVERRIDES`` table at the top of this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FILE = os.path.join(ROOT, "data", "versions.json")

# Files that are part of the website itself, not playable builds.
EXCLUDE = {
    "index.html",
    "404.html",

    # Byte-identical duplicates, removed 2026-10-17. Each is bit-for-bit the
    # same file as one listed below it -- verified by MD5 -- and the file we
    # kept is the one with the correct name:
    #
    #   Eaglercraft_indev_20100233.html        == Eaglercraft_indev 20100223_JS.html
    #   Eaglercraft_indev_20100233-wasm.html   == Eaglercraft_indev 20100223_WASM.html
    #   Eaglercraft-1.12.html                  == Eaglercraft_1.12.2-WASM-GC.html
    #   wispcraft-Eaglercraft_1.12.2-WASM-GC.html == wispcraft-Eaglercraft-1.12.html
    #
    # (the "20100233" files carry a typo'd date -- Indev 20100223 is the real one)
    "Eaglercraft_indev_20100233.html",
    "Eaglercraft_indev_20100233-wasm.html",
    "Eaglercraft-1.12.html",
    "wispcraft-Eaglercraft_1.12.2-WASM-GC.html",

}

# --------------------------------------------------------------------------
# Curated metadata.  Key = exact file name (without extension).
# Only needed where the file name is wrong, missing, or ambiguous.
# --------------------------------------------------------------------------
OVERRIDES = {
    # ---------------- releases with misleading / missing info -------------
    "1.5.2": dict(name="Eaglercraft 1.5.2", category="release", type="vanilla",
                  version="1.5.2", runtime="js"),
    "Eaglercraft-1.5.2": dict(name="Eaglercraft 1.5.2", category="release",
                              type="vanilla", version="1.5.2", runtime="js"),
    "Eaglercraft 1.6.4": dict(name="Eaglercraft 1.6.4", category="release",
                              type="vanilla", version="1.6.4"),
    "Eaglercraft 1.7.10-Javascript": dict(name="Eaglercraft 1.7.10",
                                          category="release", type="vanilla",
                                          version="1.7.10", runtime="js"),
    "Eaglercraft 1.8.8 ": dict(name="EaglercraftX 1.8.8", category="release",
                               type="vanilla", version="1.8.8", runtime="js"),
    "Eaglercraft-1.7-wasm": dict(name="Eaglercraft 1.7", category="release",
                                 type="vanilla", version="1.7", runtime="wasm"),
    "Eaglercraft_1.12_Javascript": dict(name="Eaglercraft 1.12",
                                        category="release", type="vanilla",
                                        version="1.12", runtime="js"),
    "Eaglercraft-1.12": dict(name="EaglercraftX 1.12.2", category="release",
                             type="vanilla", version="1.12.2",
                             runtime="wasm-gc"),
    "Eaglercraft_1.14.4_WASM-GC_U1": dict(name="EaglercraftX 1.14.4 (U1)",
                                          category="release", type="vanilla",
                                          version="1.14.4", runtime="wasm-gc",
                                          note="Update 1 of the 1.14.4 WASM-GC build"),
    "Eaglercraft_1.14.4_WASM-GC": dict(name="EaglercraftX 1.14.4",
                                       category="release", type="vanilla",
                                       version="1.14.4", runtime="wasm-gc"),
    "Eaglercraft_Beta_1.9_pre_5": dict(name="Beta 1.9 Pre-release 5",
                                       category="beta", type="vanilla",
                                       version="1.9", tags=["pre-release"]),
    "Eaglercraft_Beta_1.9_pre_5_WASM": dict(name="Beta 1.9 Pre-release 5",
                                            category="beta", type="vanilla",
                                            version="1.9", runtime="wasm",
                                            tags=["pre-release"]),
    "Eaglercraft beta 1.6-tb3": dict(name="Beta 1.6 Test Build 3",
                                     category="beta", type="vanilla",
                                     version="1.6", runtime="js",
                                     tags=["test-build"]),
    "Eaglercraft beta 1.6-tb3-wasm": dict(name="Beta 1.6 Test Build 3",
                                          category="beta", type="vanilla",
                                          version="1.6", runtime="wasm",
                                          tags=["test-build"]),
    "eaglercraft-beta-1.3": dict(name="Beta 1.3 (local build)",
                                 category="beta", type="vanilla",
                                 version="1.3", runtime="js",
                                 note="Stripped-down local build, only 4 MB"),
    "Eaglercraft_Beta_1.0.2": dict(name="Beta 1.0.2", category="beta",
                                   type="vanilla", version="1.0.2"),
    "Eaglercraft Beta 1.4": dict(name="Beta 1.4", category="beta",
                                 type="vanilla", version="1.4"),
    "Eaglercraft_Beta_1.4_01": dict(name="Beta 1.4_01", category="beta",
                                    type="vanilla", version="1.4_01"),
    "Eaglercraft Beta 1.5_01": dict(name="Beta 1.5_01", category="beta",
                                    type="vanilla", version="1.5_01"),
    "Eaglercraft_Beta-1.2_02": dict(name="Beta 1.2_02", category="beta",
                                    type="vanilla", version="1.2_02"),
    "Eaglercraft Alpha 1.0.6_03": dict(name="Alpha 1.0.6_03", category="alpha",
                                       type="vanilla", version="1.0.6_03"),
    "Eaglercraft_Alpha_1.1.2_01": dict(name="Alpha 1.1.2_01",
                                       category="alpha", type="vanilla",
                                       version="1.1.2_01"),
    "Eaglercraft alpha 1.0.16_02-JS": dict(name="Alpha 1.0.16_02",
                                           category="alpha", type="vanilla",
                                           version="1.0.16_02", runtime="js"),
    "Eaglercraft alpha 1.0.16_02-WASM": dict(name="Alpha 1.0.16_02",
                                             category="alpha", type="vanilla",
                                             version="1.0.16_02",
                                             runtime="wasm"),
    "eaglercraft-alpha-1.2.6": dict(name="Alpha 1.2.6", category="alpha",
                                    type="vanilla", version="1.2.6",
                                    runtime="js"),
    "eaglercraft-alpha-1.2.6-WASM": dict(name="Alpha 1.2.6",
                                         category="alpha", type="vanilla",
                                         version="1.2.6", runtime="wasm"),
    "Eaglercraft_1.4.7-JS": dict(name="Eaglercraft 1.4.7", category="release",
                                 type="vanilla", version="1.4.7", runtime="js"),
    "Eaglercraft_1.4.7-WASM": dict(name="Eaglercraft 1.4.7",
                                   category="release", type="vanilla",
                                   version="1.4.7", runtime="wasm"),
    "Eaglercraft-1-21-11_wasm": dict(name="Eaglercraft 1.21.11",
                                     category="release", type="vanilla",
                                     version="1.21.11", runtime="wasm"),
    "Eaglercraft 1.21.11 WASM": dict(name="EaglercraftX 1.21.11",
                                     category="release", type="vanilla",
                                     version="1.21.11", runtime="wasm"),
    "eaglercraft-26.2": dict(name="Eaglercraft 26.2", category="release",
                             type="vanilla", version="26.2"),
    "26.3-wasm": dict(name="Eaglercraft 26.3", category="release",
                      type="vanilla", version="26.3", runtime="wasm",
                      note="Single-file WASM build, unpacked from 26.3-wasm.docx"),
    "Eaglercraft 26.3-WASM": dict(name="Eaglercraft 26.3", category="release",
                                  type="vanilla", version="26.3", runtime="wasm",
                                  note="Single-file WASM build"),
    "Eaglercraft-26.3": dict(name="Eaglercraft 26.3", category="release",
                             type="vanilla", version="26.3", runtime="wasm"),
    "eaglercraftx-194": dict(name="EaglercraftX 1.9 (b194)",
                             category="release", type="vanilla",
                             version="1.9", note="EaglercraftL 1.9, internal build 194"),
    "Eaglercraft Mobile": dict(name="EaglercraftX 1.8 (Mobile)",
                               category="release", type="vanilla",
                               version="1.8", runtime="js", tags=["mobile"],
                               note="Touch-optimised build, shows a warning on desktop"),
    "Eaglercraft-1.6.4-Forge": dict(name="Eaglercraft 1.6.4 Forge",
                                    category="release", type="vanilla",
                                    version="1.6.4", tags=["forge"]),
    "Eaglercraft-1.6.4-Forge-WASM": dict(name="Eaglercraft 1.6.4 Forge",
                                         category="release", type="vanilla",
                                         version="1.6.4", runtime="wasm",
                                         tags=["forge"]),
    "Eaglercraft_1.2.5_JS": dict(name="Eaglercraft 1.2.5", category="release",
                                 type="vanilla", version="1.2.5", runtime="js"),
    "Eaglercraft_1.2.5_wasm": dict(name="Eaglercraft 1.2.5",
                                   category="release", type="vanilla",
                                   version="1.2.5", runtime="wasm"),
    "Eaglercraft_Beta_1.1_02-JAVS": dict(name="Eaglercraft Beta 1.1_02",
                                         category="beta", type="vanilla",
                                         version="1.1_02", runtime="js"),
    "Eaglercraft_b1.1": dict(name="Eaglercraft Beta 1.1", category="beta",
                             type="vanilla", version="1.1"),
    "classic-0.30_WASM": dict(name="Classic 0.30", category="classic",
                              type="vanilla", version="0.30",
                              runtime="wasm", tags=["multiplayer"],
                              note="Multiplayer-enabled Classic build"),
    "eagler-indev": dict(name="Eaglercraft Indev", category="indev",
                         type="vanilla", version=""),
    "pre-release-160052": dict(name="rd-160052 Pre-release",
                               category="preclassic", type="vanilla",
                               version="rd-160052", runtime="wasm-gc"),

    # -------------------------- clients ----------------------------------
    "Aero Client JS": dict(name="Aero Client", category="client", type="client",
                           version="1.12.2", runtime="js"),
    # EFI (EaglercraftForge): the only build here that ships Eaglercraft's
    # ModAPI, so the launcher's ModAPI mods actually load inside it.
    "EFI": dict(name="EFI", category="client", type="client", version="1.8.8",
                runtime="js", tags=["forge", "modapi"],
                note="EaglercraftForge 1.8.8 - ships ModAPI, so every launcher mod "
                     "loads here (Xray, Fullbright, AutoRespawn, Autoclicker, Duck, "
                     "Grapple Hook)"),
    "Eaglet": dict(name="Eaglet", category="client", type="client", version="",
                   runtime="js", tags=["tiny"],
                   note="Eaglercraft shrunk to 2.7 MB - the whole game in one tiny file"),
    "Resent Client": dict(name="Resent Client", category="client", type="client",
                          version="1.8.8", runtime="js",
                          note="Resent Client 1.8.8 - custom loading screen and HUD"),
    "EB Client Nextgen CU4": dict(name="EB Client Nextgen CU4",
                                  category="client", type="client", version=""),
    "Eclipse Client": dict(name="Eclipse Client", category="client",
                           type="client", version="1.8.8",
                           note="PvP-focused 1.8.8 client"),
    "Huzzium-Client": dict(name="Huzzium Client", category="client",
                           type="client", version="1.8"),
    "Koneclient-1.8.8": dict(name="Kone Client", category="client",
                             type="client", version="1.8.8", runtime="js"),
    "Mega Client-JS": dict(name="Mega Client", category="client",
                           type="client", version="", runtime="js"),
    "Myven-Client-WASM": dict(name="Myven Client", category="client",
                              type="client", version="1.8", runtime="wasm-gc"),
    "N0VA CLIENT": dict(name="N0VA Client", category="client", type="client",
                        version=""),
    "Novix_26.1.2": dict(name="Novix 26.1.2", category="client", type="client",
                         version="26.1.2", runtime="js"),
    "PixelClient 1.8.8 JS": dict(name="PixelClient", category="client",
                                 type="client", version="1.8.8", runtime="js"),
    "Precision": dict(name="Precision Client", category="client",
                      type="client", version="1.5.2",
                      note="Precision Client 1.5.2-beta_0.1.1"),
    "Prism-Client": dict(name="Prism Client", category="client",
                         type="client", version="1.8"),
    "Tuff_Client_WASM": dict(name="Tuff Client", category="client",
                             type="client", version="1.12", runtime="wasm-gc"),
    "Water Client": dict(name="Water Client", category="client",
                         type="client", version=""),
    "WurstX": dict(name="WurstX", category="client", type="client",
                   version="1.8", note="Wurst-style utility client"),
    "Reflex Client": dict(name="Reflex Client", category="client", type="client",
                          version="1.8", runtime="wasm-gc",
                          note="WASM-GC 1.8 client"),
    "EaglercraftZ": dict(name="EaglercraftZ", category="client", type="client",
                         version="1.20"),
    "EaglyMC": dict(name="EaglyMC", category="client", type="client",
                    version="1.8"),
    "wispcraft-Eaglercraft 1.8.8 ": dict(name="Wispcraft Eaglercraft 1.8.8",
                                         category="client", type="client",
                                         version="1.8.8", runtime="js"),
    "wispcraft-Eaglercraft-1.12": dict(name="Wispcraft Eaglercraft 1.12",
                                       category="client", type="client",
                                       version="1.12"),
    "wispcraft-EaglercraftX_1.8_WASM-GC": dict(
        name="Wispcraft EaglercraftX 1.8", category="client", type="client",
        version="1.8", runtime="wasm-gc"),
    "wispcraft-Eaglercraft_1.12.2-WASM-GC": dict(
        name="Wispcraft Eaglercraft 1.12.2", category="client", type="client",
        version="1.12.2", runtime="wasm-gc"),

    # -------------------------- bonus games -----------------------------
    "mc4k": dict(name="Minecraft 4K", category="extras", type="extra",
                 version="", runtime="js",
                 note="Notch's 4-kilobyte Java4K entry, compiled to JS"),
    "Minicraft": dict(name="Minicraft", category="extras", type="extra",
                      version="", runtime="js",
                      note="Notch's original top-down Minicraft, ported to the web"),
}

# Numeric order of the eras, used to build the sort key.
ERA_ORDER = {
    "preclassic": 0,
    "classic": 1,
    "indev": 2,
    "infdev": 3,
    "alpha": 4,
    "beta": 5,
    "release": 6,
    "client": 7,
    "extras": 8,
}

CATEGORY_INFO = {
    "preclassic": dict(label="Pre-Classic", blurb="RubyDung-era prototypes (rd-131655 → rd-161348)"),
    "classic": dict(label="Classic", blurb="Creative-mode Classic, 0.0.11a through 0.30"),
    "indev": dict(label="Indev", blurb="The first survival builds, Feb 2010"),
    "infdev": dict(label="Infdev", blurb="Infinite terrain arrives"),
    "alpha": dict(label="Alpha", blurb="Survival, multiplayer and the Nether"),
    "beta": dict(label="Beta", blurb="1.0 → 1.8.1, the road to full release"),
    "release": dict(label="Full Release", blurb="1.0.0 through 26.3"),
    "client": dict(label="Clients", blurb="PvP clients, utility clients and forks"),
    "extras": dict(label="Bonus Games", blurb="Minecraft 4K and Minicraft"),
}

RUNTIME_INFO = {
    "js": dict(label="JavaScript", short="JS"),
    "wasm": dict(label="WebAssembly", short="WASM"),
    "wasm-gc": dict(label="WebAssembly GC", short="WASM-GC"),
    "unknown": dict(label="Unknown", short="?"),
}

TYPE_INFO = {
    "vanilla": dict(label="Vanilla"),
    "client": dict(label="Client"),
    "extra": dict(label="Bonus"),
    "tool": dict(label="Tool"),
}

# --------------------------------------------------------------------------
# heuristics
# --------------------------------------------------------------------------
RE_RD = re.compile(r"\brd[-\s]?(\d{6})\b", re.I)
RE_CLASSIC = re.compile(r"(?:classic)?\s*0\.(\d+)(?:\.(\d+))?([a-z])?[_ ]?(\d+)?", re.I)
RE_INDEV_DATE = re.compile(r"(20\d{6})")
RE_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?(?:[_.\- ]?((?:pre|beta|rc|tb)\d*|\d+))?", re.I)


def read_head(path: str, limit: int = 400_000) -> bytes:
    with open(path, "rb") as fh:
        return fh.read(limit)


def sniff_runtime(path: str, head: bytes) -> str | None:
    """Detect JS vs WASM by looking at the payload.  Returns None if unsure."""
    has_wasm = b"WebAssembly" in head
    if not has_wasm:
        # some builds only reference wasm further down the file
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as fh:
                chunk = fh.read(min(size, 4_000_000))
            has_wasm = b"WebAssembly" in chunk
        except OSError:
            pass
    if not has_wasm:
        return "js"
    return "wasm"


def runtime_from_name(stem: str) -> str | None:
    low = stem.lower()
    if "wasm-gc" in low or "wasm_gc" in low or "wasm gc" in low:
        return "wasm-gc"
    if "wasm" in low:
        return "wasm"
    if re.search(r"(^|[^a-z])(js|javascript|javs)([^a-z]|$)", low):
        return "js"
    return None


def parse_version(text: str) -> list[int]:
    """Turn '1.8.8', '0.0.11a', '1.6-tb3', '20100219' into a sortable list."""
    text = text.strip().lower()
    if not text:
        return []
    m = RE_VERSION.search(text)
    if not m:
        return []
    parts = [int(m.group(1)), int(m.group(2)) if m.group(2) else 0,
             int(m.group(3)) if m.group(3) else 0]
    extra = 0
    tail = (m.group(4) or "").lower()
    if tail.startswith("pre"):
        extra = -100 + int(tail[3:] or 0)
    elif tail.startswith("tb"):
        extra = int(tail[2:] or 0) - 50
    elif tail.isdigit():
        extra = int(tail)
    parts.append(extra)
    return parts


def sort_key(category: str, version: str, raw: str) -> float:
    era = ERA_ORDER.get(category, 9) * 1e12
    if category == "preclassic":
        m = RE_RD.search(raw)
        if m:
            return era + int(m.group(1))
        return era + 999999
    if category == "classic":
        nums = [int(n) for n in re.findall(r"\d+", version)] or [0]
        if version.startswith("0.0."):          # 0.0.11a … 0.0.23a_01
            minor = 0
            rev = nums[2] if len(nums) > 2 else 0
            extra = nums[3] if len(nums) > 3 else 0
        else:                                    # 0.24_3, 0.25_5, 0.30
            minor = nums[1] if len(nums) > 1 else 0
            rev = nums[2] if len(nums) > 2 else 0
            extra = 0
        return era + minor * 1e6 + rev * 1e3 + extra
    if category == "indev":
        m = RE_INDEV_DATE.search(raw)
        return era + (int(m.group(1)) if m else 999999)
    v = parse_version(version)
    if not v:
        return era + 5e11
    return era + v[0] * 1e9 + v[1] * 1e6 + v[2] * 1e3 + (v[3] + 1000)


def auto_metadata(stem: str, title: str | None) -> dict:
    """Best-effort metadata purely from the file name."""
    raw = stem
    low = stem.lower()
    meta: dict = {}

    # ---------------- Pre-Classic (rd-######) ----------------------------
    m = RE_RD.search(raw)
    if m:
        meta.update(category="preclassic", type="vanilla",
                    name="rd-%s" % m.group(1), version="rd-%s" % m.group(1))
        return meta

    # ---------------- Classic -------------------------------------------
    if "classic" in low or re.match(r"^0\.\d", low):
        m = re.search(r"0\.(?:\d+\.)?\d+[a-z]?(?:[_.]\d+)?", raw, re.I)
        if m:
            ver = m.group(0)
            meta.update(category="classic", type="vanilla",
                        name="Classic %s" % ver, version=ver)
            return meta

    # ---------------- Indev / Infdev ------------------------------------
    if "infdev" in low:
        meta.update(category="infdev", type="vanilla", name="Infdev", version="")
        return meta
    if "indev" in low:
        d = RE_INDEV_DATE.search(raw)
        meta.update(category="indev", type="vanilla",
                    name="Indev %s" % d.group(1) if d else "Indev",
                    version=d.group(1) if d else "")
        return meta

    # ---------------- Alpha / Beta --------------------------------------
    is_alpha = "alpha" in low
    is_beta = "beta" in low or re.search(r"\bb1?\.\d", low)
    if is_alpha or is_beta:
        ver = ""
        m = re.search(r"1\.(\d+)(?:\.(\d+))?(?:[_ ](\d+))?", raw)
        if m:
            ver = "1.%s" % m.group(1)
            if m.group(2):
                ver += ".%s" % m.group(2)
            if m.group(3):
                ver += "_%s" % m.group(3)
        label = "Alpha" if is_alpha else "Beta"
        meta.update(category="alpha" if is_alpha else "beta", type="vanilla",
                    name="%s %s" % (label, ver) if ver else label, version=ver)
        return meta

    # ---------------- plain release numbers -------------------------------
    m = re.search(r"(?<![\d.])(\d{1,2})[.\-_](\d{1,2})(?:[.\-_](\d{1,3}))?(?![\d])", raw)
    if m:
        ver = "%s.%s" % (m.group(1), m.group(2))
        if m.group(3):
            ver += ".%s" % m.group(3)
        meta.update(category="release", type="vanilla",
                    name="Eaglercraft %s" % ver, version=ver)
        return meta

    return meta


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "build"


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.0f %s" % (n, unit) if unit == "B" else \
                   ("%.2f %s" % (n, unit) if n < 10 else "%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f GB" % n


def md5_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_hash_cache() -> dict:
    """Re-use hashes from the previous run so we never re-hash 2.7 GB."""
    cache = {}
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE, encoding="utf-8") as fh:
                for v in json.load(fh).get("versions", []):
                    if v.get("sha1_12") and v.get("size"):
                        cache[(v["file"], v["size"])] = v["sha1_12"]
        except (ValueError, OSError):
            pass
    return cache


def main() -> int:
    files = sorted(
        f for f in os.listdir(ROOT)
        if f.lower().endswith(".html") and f not in EXCLUDE
        and os.path.isfile(os.path.join(ROOT, f))
    )

    # A sparse checkout intentionally omits the multi-gigabyte game payloads.
    # Never mistake that partial directory listing for the complete archive and
    # overwrite the embedded catalogue with a tiny, incomplete one.
    try:
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).split(bytes([0]))
    except (OSError, subprocess.CalledProcessError):
        tracked = []
    tracked_builds = {
        os.fsdecode(path) for path in tracked
        if path and b"/" not in path and os.fsdecode(path).lower().endswith(".html")
        and os.fsdecode(path) not in EXCLUDE
    }
    missing_checkout = sorted(tracked_builds.difference(files))
    if missing_checkout:
        print("error: refusing to regenerate from a partial checkout.")
        print("       %d tracked build file(s) are not materialized; the embedded catalogue was left untouched."
              % len(missing_checkout))
        print("       first missing: %s" % ", ".join(missing_checkout[:5]))
        print("       materialize the game files before running this scanner.")
        return 2

    hash_cache = load_hash_cache()

    entries, problems = [], []
    for fname in files:
        stem = fname[:-5]
        path = os.path.join(ROOT, fname)
        head = read_head(path)
        tm = re.search(rb"<title[^>]*>(.*?)</title>", head, re.I | re.S)
        title = tm.group(1).decode("utf-8", "replace").strip() if tm else None

        meta = auto_metadata(stem, title)
        meta.update(OVERRIDES.get(stem, {}))

        category = meta.get("category")
        if not category:
            problems.append("no category: %s" % fname)
            category = "extras"
        version = meta.get("version", "")
        name = meta.get("name") or stem
        gtype = meta.get("type") or ("client" if category == "client" else "vanilla")

        size = os.path.getsize(path)
        runtime = meta.get("runtime") or runtime_from_name(stem) or "unknown"
        if runtime == "unknown":
            runtime = sniff_runtime(path, head) or "unknown"
        if runtime == "wasm" and title and "wasm-gc" in title.lower():
            runtime = "wasm-gc"          # the file name said 'wasm', the build says GC

        tags = list(meta.get("tags") or [])
        low = stem.lower()
        if "forge" in low:
            tags.append("forge")
        if "mobile" in low:
            tags.append("mobile")
        if re.search(r"\btb\d", low):
            tags.append("test-build")
        if "multiplayer" in low or "mp" == low[-2:]:
            tags.append("multiplayer")
        tags = sorted(set(tags))

        key = (fname, size)
        if key in hash_cache:
            digest = hash_cache[key]
        else:
            digest = md5_file(path)[:12]
            hash_cache[key] = digest

        entry = {
            "id": slugify(name) + "-" + digest[:6],
            "sha1_12": digest,
            "name": name,
            "file": fname,
            "url": "./" + fname.replace(" ", "%20"),
            "category": category,
            "type": gtype,
            "runtime": runtime,
            "version": version or None,
            "size": size,
            "sizeText": human_size(size),
            "tags": tags,
            "note": meta.get("note", ""),
            "title": title,
            "order": sort_key(category, version or "", stem),
        }
        entry["eraCover"] = "./assets/img/cat-%s.jpg" % category
        # per-build art lives in assets/img/builds/<id>.jpg; only advertise it
        # once the file actually exists so the launcher never requests a 404
        cover_rel = "./assets/img/builds/%s.jpg" % entry["id"]
        entry["cover"] = cover_rel if os.path.exists(
            os.path.join(ROOT, cover_rel[2:])) else None
        entries.append(entry)

    entries.sort(key=lambda e: (e["order"], e["name"].lower()))

    # flag byte-identical builds (the repo has a few accidental duplicates)
    by_hash: dict[str, list] = {}
    for e in entries:
        by_hash.setdefault(e["sha1_12"], []).append(e)
    for digest, group in by_hash.items():
        if len(group) < 2:
            continue
        leader = group[0]
        for e in group[1:]:
            e["duplicateOf"] = leader["id"]
            if "duplicate" not in e["tags"]:
                e["tags"] = sorted(e["tags"] + ["duplicate"])

    # de-duplicate ids
    seen, out = {}, []
    for e in entries:
        base, i = e["id"], 2
        while e["id"] in seen:
            e["id"] = "%s-%d" % (base, i)
            i += 1
        seen[e["id"]] = True
        out.append(e)

    total = sum(e["size"] for e in out)
    by_cat, by_rt, by_type = {}, {}, {}
    for e in out:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
        by_rt[e["runtime"]] = by_rt.get(e["runtime"], 0) + 1
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1

    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(out),
        "totalSize": total,
        "totalSizeText": human_size(total),
        "categories": [dict(id=k, **CATEGORY_INFO[k], count=by_cat.get(k, 0))
                       for k in ERA_ORDER if by_cat.get(k)],
        "runtimes": [dict(id=k, **RUNTIME_INFO[k], count=by_rt.get(k, 0))
                     for k in ("js", "wasm", "wasm-gc", "unknown") if by_rt.get(k)],
        "types": [dict(id=k, **TYPE_INFO[k], count=by_type.get(k, 0))
                  for k in ("vanilla", "client", "extra", "tool") if by_type.get(k)],
        "versions": out,
    }

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    print("wrote %s" % os.path.relpath(OUT_FILE, ROOT))
    print("  builds      : %d" % data["count"])
    print("  total size  : %s" % data["totalSizeText"])
    for c in data["categories"]:
        print("    %-14s %3d" % (c["label"], c["count"]))
    for p in problems:
        print("  !! %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
