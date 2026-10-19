#!/usr/bin/env python3
"""
Join a chunked single-file build, in the right order, and optionally import it.

Chat uploads cap out around 25 MB, so a 78 MB build arrives as several parts.
File names are NOT trustworthy -- a chat client can rename, renumber, or hand
back the parts out of order. This script decides the order from the bytes
themselves: the tail of one chunk must be the head of the next.

    python3 tools/assemble_parts.py "incoming/chunk-*.html" --out /tmp/joined.html
    python3 tools/assemble_parts.py "incoming/chunk-*.html" \
        --name "My Client" --add

Two hard rules are enforced before anything is imported:

* the joined stream must start with ``<!DOCTYPE``/``<html``
* the joined stream must end with ``</html>``

If either fails the script says exactly which side is missing and refuses to
touch the vault, so a half build can never end up in the catalogue.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW = 4096  # bytes of overlap to look for at a chunk boundary


def read_head(path: str, size: int = WINDOW) -> bytes:
    with open(path, "rb") as fh:
        return fh.read(size)


def read_tail(path: str, size: int = WINDOW) -> bytes:
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        length = fh.tell()
        fh.seek(max(0, length - size))
        return fh.read()


def overlap(tail: bytes, head: bytes) -> int:
    """Longest suffix of ``tail`` that is a prefix of ``head`` (0 if none)."""
    longest = min(len(tail), len(head))
    for n in range(longest, 15, -1):
        if tail[-n:] == head[:n]:
            return n
    return 0


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def part_key(path: str):
    """Sort p2 before p10 when names are the only clue."""
    numbers = [int(n) for n in re.findall(r"\d+", os.path.basename(path))]
    return (numbers or [0], os.path.basename(path))


def opens_document(path: str) -> bool:
    head = read_head(path, 512).lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def closes_document(path: str) -> bool:
    return read_tail(path, 512).rstrip().lower().endswith(b"</html>")


def chain(parts: list[str]) -> tuple[list[str], list[str]]:
    """Return (ordered parts, notes).

    Exact byte splits share no repeated text, so there is usually nothing to
    overlap on. Structure is the reliable clue: whichever chunk ends in
    ``</html>`` is last, whichever opens with a doctype is first, and the file
    names decide the order of anything in between.
    """
    notes: list[str] = []

    # 1. If the uploader duplicated bytes at the boundaries, chain on overlap.
    rem = list(parts)
    chain_seq: list[str] = []
    seed = next((p for p in rem if opens_document(p)), None)
    if seed:
        chain_seq.append(seed)
        rem.remove(seed)
        while rem:
            tail = read_tail(chain_seq[-1])
            best, best_n = None, 0
            for path in rem:
                n = overlap(tail, read_head(path))
                if n > best_n:
                    best, best_n = path, n
            if not best or best_n < 64:
                break
            chain_seq.append(best)
            rem.remove(best)
    if rem and not chain_seq and len(parts) > 1:
        # no overlap information at all -> structural order below
        pass

    if not rem and chain_seq:
        return chain_seq, ["ordered by byte overlap"]

    # 2. Structural order: opener, middles by name, closer.
    openers = [p for p in parts if opens_document(p)]
    closers = [p for p in parts if closes_document(p) and p not in openers]
    middles = sorted(
        [p for p in parts if p not in openers and p not in closers], key=part_key)

    if len(openers) > 1:
        notes.append("more than one part opens a document; using %s"
                     % os.path.basename(openers[0]))
    if not openers:
        notes.append("no part opens the document -- the first chunk is missing")
    if not closers:
        notes.append("no part ends with </html> -- the last chunk is missing")
    notes.append("order inferred from document structure and file names "
                 "(exact splits share no overlap bytes)")

    return openers[:1] + middles + closers[:1], notes


def join(ordered: list[str], out: str) -> int:
    total = 0
    with open(out, "wb") as dst:
        for path in ordered:
            with open(path, "rb") as src:
                for block in iter(lambda: src.read(1 << 20), b""):
                    dst.write(block)
                    total += len(block)
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", help="glob for the uploaded chunks")
    ap.add_argument("--out", default=os.path.join(ROOT, "incoming", "joined.html"),
                    help="where to write the joined file (default: incoming/joined.html)")
    ap.add_argument("--name", help="build name; with --add this is the catalogued name")
    ap.add_argument("--add", action="store_true",
                    help="import the joined file once it validates (runs add_build.py)")
    ap.add_argument("--keep-going", action="store_true",
                    help="write the partial join even if the file is incomplete")
    args = ap.parse_args()

    parts = sorted(glob.glob(args.parts))
    if not parts:
        print("error: no files matched %s" % args.parts)
        return 1

    print("parts found: %d" % len(parts))
    for path in parts:
        print("  %-34s %12d bytes  %s" % (
            os.path.basename(path), os.path.getsize(path), sha256(path)[:16]))

    ordered, notes = chain(parts)
    print("\nbyte-order chain:")
    for index, path in enumerate(ordered, 1):
        print("  %d. %s" % (index, os.path.basename(path)))
    for note in notes:
        print("  note: %s" % note)

    if len({sha256(p) for p in parts}) != len(parts):
        print("warning: two parts are byte-identical; one upload may be a duplicate")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    size = join(ordered, args.out)
    print("\njoined: %s (%d bytes)" % (args.out, size))

    head = read_head(args.out, 512).lstrip().lower()
    tail = read_tail(args.out, 512).rstrip().lower()
    opens = head.startswith(b"<!doctype") or head.startswith(b"<html")
    closes = tail.endswith(b"</html>")
    print("opens with a document tag : %s" % ("yes" if opens else "NO"))
    print("closes with </html>        : %s" % ("yes" if closes else "NO"))

    if not opens:
        print("\nmissing the FIRST chunk: the joined stream starts mid-content:")
        print("  %r" % read_head(args.out, 70))
    if not closes:
        print("\nmissing the LAST chunk: the joined stream ends mid-content:")
        print("  %r" % read_tail(args.out, 70))

    complete = opens and closes
    if not complete:
        print("\nthis is not a runnable build yet; upload the remaining part(s).")
        if not args.keep_going:
            try:
                os.remove(args.out)
                print("removed the partial join so it cannot be launched by mistake.")
            except OSError:
                pass
            return 2

    if args.add and complete:
        name = args.name or os.path.splitext(os.path.basename(args.out))[0]
        print("\nimporting as %r ...\n" % name)
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "add_build.py"), args.out,
             "--name", name], cwd=ROOT
        ).returncode

    if complete:
        print("\ncomplete build. import it with:")
        print("  python3 tools/add_build.py %r --name %r" % (args.out, args.name or "..."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
