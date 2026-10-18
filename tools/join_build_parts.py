#!/usr/bin/env python3
"""
Reassemble a large build that arrived in several uploaded chunks.

Chat uploads are capped (~25 MB), so a 90 MB single-file build has to be split
before it can be sent. Split it into ordered chunks and send them in batches:

    split -n 4 -d --additional-suffix=.html 26.3-wasm.html 26.3-wasmp

then, once every chunk is uploaded:

    python3 tools/join_build_parts.py ~/incoming/26.3-wasmp*.html \
        --size 90804846 \
        --sha256 cc6996731471299161f492321d4b1d2db61df3a96fcd0803090e22a07a44a62b \
        --out /tmp/26.3-wasm.html

Chunks are sorted by the trailing number in the file name (p1, p2, p3, p4),
never alphabetically -- "p10" must not sort before "p2".

If the checksum fails the script tries the usual splitter artefacts before
giving up: a trailing newline on each chunk, and CRLF line endings.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys


def part_key(path: str):
    """Sort 26.3-wasmp2.html before 26.3-wasmp10.html."""
    name = os.path.basename(path)
    nums = re.findall(r"(\d+)", name)
    return ([int(n) for n in nums] or [0], name)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assemble(parts, out: str, strip: str | None = None) -> int:
    total = 0
    with open(out, "wb") as dst:
        for i, p in enumerate(parts):
            data = open(p, "rb").read()
            if strip == "newline":
                data = data.rstrip(b"\r\n")
            elif strip == "crlf":
                data = data.replace(b"\r\n", b"\n")
            dst.write(data)
            total += len(data)
            print("  + %-28s %12d bytes" % (os.path.basename(p), len(data)))
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", nargs="+", help="chunk files, any order")
    ap.add_argument("--out", required=True, help="where to write the joined file")
    ap.add_argument("--size", type=int, help="expected size in bytes")
    ap.add_argument("--sha256", help="expected SHA-256")
    ap.add_argument("--strip", choices=["newline", "crlf"],
                    help="force a repair strategy instead of auto-detecting")
    args = ap.parse_args()

    parts = sorted(args.parts, key=part_key)
    print("joining %d chunks in this order:" % len(parts))
    for p in parts:
        print("   ", os.path.basename(p))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)

    strategies = [args.strip] if args.strip else [None, "newline", "crlf"]
    for strat in strategies:
        if strat:
            print("\nretrying with strip=%s ..." % strat)
        total = assemble(parts, args.out, strat)
        print("  total: %d bytes" % total)

        size_ok = args.size is None or total == args.size
        if args.size is not None and not size_ok:
            print("  size mismatch: expected %d, got %d (%+d)"
                  % (args.size, total, total - args.size))
            continue

        if args.sha256:
            got = sha256(args.out)
            if got.lower() != args.sha256.lower():
                print("  sha256 mismatch:\n    expected %s\n    got      %s"
                      % (args.sha256, got))
                continue
            print("  sha256 OK  %s" % got)

        print("\nassembled -> %s (%d bytes)" % (args.out, total))
        return 0

    print("\ncould not reproduce the expected checksum.")
    print("Check that every chunk uploaded intact and that none are missing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
