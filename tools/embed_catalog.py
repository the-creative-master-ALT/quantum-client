#!/usr/bin/env python3
"""
Embed the build catalogue directly into index.html.

The launcher is one self-contained file, so it cannot fetch data/versions.json
-- and it would not work from file:// if it tried. Instead the catalogue lives
in an inline <script type="application/json"> block, and this script rewrites
that block in place. Run it after adding or renaming a build:

    python3 tools/embed_catalog.py              # reuse data/versions.json if present
    python3 tools/embed_catalog.py --regen      # rescan the *.html files first

Only the fields the UI actually renders are kept, which is roughly a third of
the raw catalogue.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
CATALOG = os.path.join(ROOT, "data", "versions.json")
GENERATOR = os.path.join(ROOT, "tools", "generate_catalog.py")

BLOCK = re.compile(
    r'(<script id="vault" type="application/json">)(.*?)(</script>)',
    re.S,
)

KEEP = ("id", "name", "file", "url", "category", "type", "runtime",
        "version", "size", "sizeText", "tags")


def load(regen: bool) -> dict:
    if regen or not os.path.exists(CATALOG):
        print("scanning builds ...")
        subprocess.run([sys.executable, GENERATOR], check=True, cwd=ROOT)
    with open(CATALOG, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regen", action="store_true",
                    help="rescan the *.html files instead of reusing the existing catalogue")
    ap.add_argument("--keep-catalog", action="store_true",
                    help="leave data/versions.json in place (it is redundant once embedded)")
    args = ap.parse_args()

    raw = load(args.regen)

    slim = {
        "count": raw["count"],
        "totalSizeText": raw["totalSizeText"],
        "versions": [{k: v.get(k) for k in KEEP} for v in raw["versions"]],
    }
    blob = json.dumps(slim, separators=(",", ":"), ensure_ascii=False)

    with open(INDEX, encoding="utf-8") as fh:
        html = fh.read()
    if not BLOCK.search(html):
        print('!! could not find <script id="vault" type="application/json"> in index.html')
        return 1
    html = BLOCK.sub(lambda m: m.group(1) + "\n" + blob + "\n" + m.group(3), html, count=1)
    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write(html)

    if not args.keep_catalog and os.path.exists(CATALOG):
        os.remove(CATALOG)
        d = os.path.dirname(CATALOG)
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)

    print("embedded %d builds into index.html" % slim["count"])
    print("  payload     : %.1f KB of JSON" % (len(blob.encode()) / 1024))
    print("  index.html  : %.1f KB total" % (os.path.getsize(INDEX) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
