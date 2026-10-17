#!/usr/bin/env python3
"""
Drop a new single-file build into the vault.

    python3 tools/add_build.py ~/Downloads/26.3-wasm.docx
    python3 tools/add_build.py ~/Downloads/weird-name.bin --name "Eaglercraft 26.3"
    python3 tools/add_build.py ~/Downloads/thing.html --move

It handles the annoying parts of adding a 90 MB single-file build:

* detects HTML even when the file is misnamed (`.docx`, `.bin`, no extension)
* refuses things that are not actually the single-file HTML build
* warns before you hit GitHub's 100 MB hard file limit
* refuses Git LFS (GitHub Pages serves the pointer file, not the game)
* skips byte-identical duplicates already in the vault
* renames to a clean `<name>.html` and regenerates data/versions.json

Then just commit and push -- `.github/workflows/update-catalog.yml` rebuilds
the catalogue again on the remote as a safety net.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "data", "versions.json")

GITHUB_WARN = 50 * 1024 * 1024      # GitHub starts warning here
GITHUB_HARD = 100 * 1024 * 1024     # ...and refuses pushes above this
PAGES_SOFT = 1 * 1024 * 1024 * 1024  # published Pages site guidance


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f GB" % n


def md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_html(path: str) -> tuple[bool, str]:
    """Single-file builds always start with a doctype or <html near the top."""
    with open(path, "rb") as fh:
        head = fh.read(8192).decode("utf-8", "replace").lower()
    if "<!doctype html" in head or "<html" in head:
        return True, "starts with a doctype / <html> tag"
    if "<head" in head or "<script" in head:
        return True, "contains <head> / <script>"
    return False, "no HTML doctype in the first 8 KB"


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._+ -]+", "", name).strip()
    s = re.sub(r"\s+", " ", s)
    return s or "build"


def load_embedded() -> dict:
    """Read the catalogue back out of index.html (it no longer lives in data/)."""
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as fh:
        m = re.search(r'<script id="vault" type="application/json">(.*?)</script>',
                      fh.read(), re.S)
    if not m:
        raise SystemExit("could not find the embedded catalogue in index.html")
    return json.loads(m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="the single-file build to add")
    ap.add_argument("--name", help="name to store it under (defaults to the file name)")
    ap.add_argument("--move", action="store_true", help="move instead of copying")
    ap.add_argument("--force", action="store_true", help="add even if it looks wrong")
    args = ap.parse_args()

    src = os.path.abspath(os.path.expanduser(args.file))
    if not os.path.isfile(src):
        print("error: no such file: %s" % src)
        return 1

    size = os.path.getsize(src)
    print("source : %s" % src)
    print("size   : %s (%d bytes)" % (human(size), size))

    # ---- sanity checks --------------------------------------------------
    ok, why = looks_like_html(src)
    if not ok and not args.force:
        print("\nerror: this does not look like a single-file HTML build (%s)." % why)
        print("Eaglercraft builds are self-contained .html files even when they")
        print("are misnamed .docx / .bin. Re-export it, or pass --force.")
        return 1

    if size == 0:
        print("error: file is empty")
        return 1

    if size > GITHUB_HARD:
        print("\nerror: %s is over GitHub's 100 MB hard file limit." % human(size))
        print("Split it, or host it elsewhere and link to it.")
        return 1
    if size > GITHUB_WARN:
        print("\nnote  : over %s -- GitHub will warn on push but accept it."
              % human(GITHUB_WARN))
        print("        Git LFS is NOT an option here: GitHub Pages serves the")
        print("        LFS pointer file, so the build would not run.")

    # ---- duplicate check ------------------------------------------------
    digest = md5(src)
    cat = {}
    if os.path.exists(CATALOG):
        cat = json.load(open(CATALOG, encoding="utf-8"))
    for v in cat.get("versions", []):
        if v.get("sha1_12") and digest.startswith(v["sha1_12"]):
            print("\nerror: byte-identical to '%s' already in the vault." % v["file"])
            return 1

    # ---- destination ----------------------------------------------------
    base = args.name or os.path.splitext(os.path.basename(src))[0]
    dest_name = slug(base)
    if not dest_name.lower().endswith(".html"):
        dest_name += ".html"
    dest = os.path.join(ROOT, dest_name)

    if os.path.exists(dest):
        print("\nerror: '%s' already exists in the vault." % dest_name)
        print("Use --name to pick a different name.")
        return 1

    print("adding : %s" % dest_name)
    if args.move:
        shutil.move(src, dest)
    else:
        shutil.copyfile(src, dest)
        try:
            shutil.copystat(src, dest)
        except OSError:
            pass

    # ---- regenerate -----------------------------------------------------
    print()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "generate_catalog.py")],
                       cwd=ROOT)
    if r.returncode != 0:
        return r.returncode

    # the launcher is a single file, so the catalogue is baked into index.html
    # rather than sitting in data/versions.json
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "embed_catalog.py")],
                       cwd=ROOT)
    if r.returncode != 0:
        return r.returncode

    cat = load_embedded()
    entry = next((v for v in cat["versions"] if v["file"] == dest_name), None)
    print()
    if entry:
        print("indexed as: %s  [%s / %s / %s]"
              % (entry["name"], entry["category"], entry["runtime"], entry["sizeText"]))
    # the embedded catalogue keeps only the pre-formatted size string
    total_bytes = sum(v.get("size", 0) for v in cat["versions"])
    print("\narchive: %s across %s builds"
          % (cat.get("totalSizeText", "?"), cat.get("count", "?")))
    if total_bytes > PAGES_SOFT:
        print("note  : over GitHub Pages' 1 GB guidance.")

    print("\nnext:")
    print("  git add %r index.html" % dest_name)
    print("  git commit -m 'Add %s'" % (entry["name"] if entry else dest_name))
    print("  git push")
    print("\nIf the metadata looks wrong, add an entry to the OVERRIDES table")
    print("in tools/generate_catalog.py and re-run it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
