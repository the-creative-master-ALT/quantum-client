#!/usr/bin/env python3
"""Audit the embedded catalogue without opening or fetching game payloads."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
def git_files() -> set[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return {
        os.fsdecode(path) for path in raw.split(bytes([0]))
        if path and b"/" not in path
    }


def sparse_checkout() -> bool:
    try:
        value = subprocess.check_output(
            ["git", "config", "--bool", "core.sparseCheckout"],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True,
        ).strip().lower()
        return value == "true"
    except subprocess.CalledProcessError:
        return False


def main() -> int:
    try:
        html = INDEX.read_text(encoding="utf-8")
        match = re.search(
            r'<script id="vault" type="application/json">(.*?)</script>',
            html, re.S,
        )
        if not match:
            raise ValueError("embedded catalogue block is missing")
        catalog = json.loads(match.group(1))
        versions = catalog["versions"]
        tracked = git_files()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("catalogue audit failed: %s" % error, file=sys.stderr)
        return 1

    problems: list[str] = []
    files = [entry.get("file", "") for entry in versions]
    ids = [entry.get("id", "") for entry in versions]
    catalog_files = set(files)
    tracked_html = {
        name for name in tracked
        if name.lower().endswith(".html") and name not in {"index.html", "404.html"}
    }

    if catalog.get("count") != len(versions):
        problems.append("embedded count does not match the versions array")
    if len(catalog_files) != len(files):
        problems.append("catalogue contains duplicate file entries")
    if len(set(ids)) != len(ids):
        problems.append("catalogue contains duplicate build ids")

    missing_from_git = sorted(catalog_files - tracked_html)
    unlisted_in_catalog = sorted(tracked_html - catalog_files)
    if missing_from_git:
        problems.append("catalogue file(s) missing from Git index: " + ", ".join(missing_from_git[:5]))
    if unlisted_in_catalog:
        problems.append("tracked game HTML not catalogued: " + ", ".join(unlisted_in_catalog[:5]))
    timeline = [entry for entry in versions if entry.get("category") not in {"client", "extras"}]
    clients = [entry for entry in versions if entry.get("category") == "client"]
    bonus = [entry for entry in versions if entry.get("category") == "extras"]
    if not timeline or not str(timeline[0].get("version", "")).startswith("rd-"):
        problems.append("timeline does not begin with an RD build")
    release_versions = [str(entry.get("version") or "") for entry in timeline if entry.get("category") == "release"]
    if "26.3" not in release_versions:
        problems.append("timeline is missing the 26.3 build")
    orders = [entry.get("order") for entry in timeline]
    if any(not isinstance(order, (int, float)) for order in orders):
        problems.append("timeline is missing numeric chronology keys")
    elif any(a > b for a, b in zip(orders, orders[1:])):
        problems.append("timeline entries are not in chronological order")
    if len(bonus) != 2 or {entry.get("name") for entry in bonus} != {"Minecraft 4K", "Minicraft"}:
        problems.append("bonus section must contain only Minecraft 4K and Minicraft")
    if any(entry.get("type") == "tool" for entry in versions):
        problems.append("non-game tool is present in the launcher catalogue")

    materialized = 0
    missing_on_disk: list[str] = []
    size_mismatches: list[str] = []
    for entry in versions:
        path = ROOT / entry["file"]
        if not path.is_file():
            missing_on_disk.append(entry["file"])
            continue
        materialized += 1
        expected_size = entry.get("size")
        if expected_size is not None and path.stat().st_size != expected_size:
            size_mismatches.append(entry["file"])
    if size_mismatches:
        problems.append("materialized build size mismatch: " + ", ".join(size_mismatches[:5]))
    if missing_on_disk and not sparse_checkout():
        problems.append("build file(s) absent from a full checkout: " + ", ".join(missing_on_disk[:5]))

    if problems:
        for problem in problems:
            print("FAIL: " + problem, file=sys.stderr)
        return 1

    sparse_note = " · sparse checkout: %d payloads omitted" % len(missing_on_disk) if missing_on_disk else ""
    print("OK: %d builds · %d timeline · %d clients · %d bonus · %d payloads materialized%s" % (
        len(versions), len(timeline), len(clients), len(bonus), materialized, sparse_note,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
