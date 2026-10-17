#!/usr/bin/env python3
"""
Render a unique, era-flavoured voxel cover for every build that does not have
hand-generated art yet.

    python3 tools/make_procedural_covers.py            # fill the gaps
    python3 tools/make_procedural_covers.py --all      # redraw everything

Each cover is a seeded procedural scene -- layered hills, block terrain,
water, trees, clouds and era-specific colour grading -- so every build gets
its own artwork and no card is ever blank.  Images already produced by the
image generator (assets/img/builds/<id>.jpg) are left alone unless --all.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "img", "builds")
CATALOG = os.path.join(ROOT, "data", "versions.json")

W, H = 960, 600          # 16:10, matches the card aspect ratio
BLOCK = 20              # pixels per voxel


# --------------------------------------------------------------- helpers ---
class Rng:
    """Tiny deterministic xorshift PRNG seeded from the build id."""

    def __init__(self, seed: str):
        self.s = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) or 1

    def next(self) -> int:
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x & 0xFFFFFFFF
        return self.s

    def rand(self) -> float:
        return self.next() / 0xFFFFFFFF

    def rint(self, a: int, b: int) -> int:
        return a + int(self.rand() * (b - a + 1))

    def chance(self, p: float) -> bool:
        return self.rand() < p


def hexc(c: str):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(c, f: float):
    return tuple(max(0, min(255, int(v * f))) for v in c)


# --------------------------------------------------------------- palettes ---
PALETTES = {
    "preclassic": dict(
        sky=("#8a94a6", "#c3c0b4"), fog="#b9b6a8", sun="#e8e2cf",
        grass="#6f8f4a", dirt="#7a5c3a", stone="#8b8375", sand="#a89a72",
        water="#4d6b7a", trunk="#5b4630", leaf="#4e6b39", cloud="#d8d5c8",
        grade="#c9b79a", grade_amt=0.16, night=0.0),
    "classic": dict(
        sky=("#4facf7", "#a8e2ff"), fog="#bfe6ff", sun="#fff6c8",
        grass="#5fbf3f", dirt="#8b6640", stone="#9a9a9a", sand="#e0d6a0",
        water="#3f7bd6", trunk="#6b4f2a", leaf="#3f8f34", cloud="#ffffff",
        grade="#ffffff", grade_amt=0.0, night=0.0),
    "indev": dict(
        sky=("#5b6b7d", "#9fb0bd"), fog="#a8b6c0", sun="#e6ddc0",
        grass="#5c8a4a", dirt="#6f5537", stone="#7f7d74", sand="#9c9374",
        water="#3d5f70", trunk="#54402c", leaf="#42613a", cloud="#cfd6da",
        grade="#8fa2ad", grade_amt=0.20, night=0.0),
    "infdev": dict(
        sky=("#6a7f96", "#a9bcc9"), fog="#aebcc6", sun="#efe4c4",
        grass="#5f9050", dirt="#71573a", stone="#83817a", sand="#a79c7a",
        water="#42657a", trunk="#57432e", leaf="#456a3c", cloud="#d5dbe0",
        grade="#93a7b3", grade_amt=0.18, night=0.0),
    "alpha": dict(
        sky=("#1b2a44", "#4a5f7a"), fog="#3d4c63", sun="#cfd8e8",
        grass="#4a7a3c", dirt="#5f4a30", stone="#6f6d68", sand="#8d8468",
        water="#2b4a63", trunk="#46351f", leaf="#33542f", cloud="#5a6a80",
        grade="#2b3a55", grade_amt=0.30, night=0.55),
    "beta": dict(
        sky=("#f0a35e", "#ffd9a0"), fog="#e8c9a2", sun="#fff2c0",
        grass="#6ea84a", dirt="#8a6a41", stone="#94918a", sand="#e3d3a2",
        water="#3f7fae", trunk="#6d5130", leaf="#437f38", cloud="#ffe9c8",
        grade="#ffb066", grade_amt=0.16, night=0.0),
    "release": dict(
        sky=("#2f7fd6", "#b6e3ff"), fog="#cfeaff", sun="#fffbe0",
        grass="#63b13f", dirt="#8b6b45", stone="#9c9c9c", sand="#e6d9a8",
        water="#2f6fc4", trunk="#6f5231", leaf="#3f9a3c", cloud="#ffffff",
        grade="#ffffff", grade_amt=0.0, night=0.0),
    "client": dict(
        sky=("#2a0b52", "#7a1f8f"), fog="#5a1f7a", sun="#ff6ae0",
        grass="#3d3670", dirt="#453480", stone="#5f51a8", sand="#7a4fb0",
        water="#2a2a7a", trunk="#4a3a80", leaf="#3df0d0", cloud="#9a5fd0",
        grade="#a24bff", grade_amt=0.20, night=0.34),
    "extras": dict(
        sky=("#101a3a", "#2b3f7a"), fog="#243a66", sun="#41e0ff",
        grass="#2f6f6a", dirt="#3a4a6a", stone="#5a6a8a", sand="#4a5a7a",
        water="#123a6a", trunk="#3a4a6a", leaf="#41e0ff", cloud="#3a5a9a",
        grade="#22d3ee", grade_amt=0.28, night=0.5),
}


# ----------------------------------------------------------------- scene ---
def draw_block(d, x, y, size, top, side, rng):
    d.rectangle([x, y, x + size - 1, y + size - 1], fill=side)
    d.rectangle([x, y, x + size - 1, y + max(1, size // 4)], fill=top)
    d.rectangle([x, y + size - max(1, size // 6), x + size - 1, y + size - 1],
                fill=shade(side, 0.72))
    d.rectangle([x + size - max(1, size // 9), y, x + size - 1, y + size - 1],
                fill=shade(side, 0.84))
    # a little per-block speckle so large flats do not look plastic
    for _ in range(3):
        px = x + rng.rint(1, size - 2)
        py = y + rng.rint(1, size - 2)
        f = 0.86 + rng.rand() * 0.22
        d.point((px, py), fill=shade(side, f))


def heights_for(rng, cols, base, amp, rough):
    p1 = rng.rand() * math.pi * 2
    p2 = rng.rand() * math.pi * 2
    p3 = rng.rand() * math.pi * 2
    out = []
    for i in range(cols):
        h = base
        h += amp * math.sin(i / 7.0 + p1)
        h += (amp * 0.55) * math.sin(i / 3.1 + p2)
        h += (amp * 0.3) * math.sin(i / 1.7 + p3)
        h += rng.rint(-rough, rough)
        out.append(int(h))
    # smooth once so columns do not jump by more than 2
    for i in range(1, cols - 1):
        out[i] = (out[i - 1] + out[i] * 2 + out[i + 1]) // 4
    return out


def render(build, path):
    rng = Rng(build["id"])
    pal_src = PALETTES.get(build["category"], PALETTES["release"])
    def conv(v):
        if isinstance(v, str) and v.startswith("#"):
            return hexc(v)
        if isinstance(v, (tuple, list)):
            return tuple(conv(x) for x in v)
        return v

    pal = {k: conv(v) for k, v in pal_src.items()}

    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)

    # ---- sky ------------------------------------------------------------
    top_c, bot_c = pal["sky"]
    for y in range(H):
        d.line([(0, y), (W, y)], fill=mix(top_c, bot_c, y / H))

    # sun / moon
    sun_x = rng.rint(int(W * 0.12), int(W * 0.86))
    sun_y = rng.rint(int(H * 0.10), int(H * 0.30))
    sun_r = rng.rint(26, 44)
    glow = Image.new("RGB", (W, H), top_c)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([sun_x - sun_r * 3, sun_y - sun_r * 3,
                sun_x + sun_r * 3, sun_y + sun_r * 3],
               fill=mix(top_c, pal["sun"], 0.35))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img = Image.blend(img, glow, 0.55)
    d = ImageDraw.Draw(img)
    d.ellipse([sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r],
              fill=pal["sun"])

    # ---- clouds ---------------------------------------------------------
    for _ in range(rng.rint(3, 6)):
        cx = rng.rint(-60, W)
        cy = rng.rint(int(H * 0.05), int(H * 0.42))
        cw = rng.rint(90, 210)
        ch = rng.rint(18, 34)
        col = mix(pal["cloud"], pal["fog"], rng.rand() * 0.4)
        for bx in range(0, cw, BLOCK):
            bump = ch // 2 if rng.chance(0.35) else 0
            d.rectangle([cx + bx, cy - bump, cx + bx + BLOCK - 2, cy + ch],
                        fill=col)

    # ---- far hills ------------------------------------------------------
    cols = W // BLOCK + 1
    for layer, (alpha, y_off, amp) in enumerate(
            [(0.45, 0.30, 3.2), (0.72, 0.44, 2.4)]):
        hh = heights_for(rng, cols, int(H * 0.62 / BLOCK) // 2 + 1, amp, 1)
        pts = []
        for i, h in enumerate(hh):
            pts.append((i * BLOCK, H - (h + y_off * H / BLOCK) * BLOCK - H * y_off / 2))
        pts += [(W, H), (0, H)]
        hill_col = mix(pal["fog"], pal["grass"], 0.25 + layer * 0.15)
        sil = Image.new("RGB", (W, H), (0, 0, 0))
        sd = ImageDraw.Draw(sil)
        base_y = H * (0.52 + layer * 0.07)
        poly = [(i * BLOCK, base_y - h * (10 + layer * 6)) for i, h in enumerate(hh)]
        poly += [(W, H), (0, H)]
        sd.polygon(poly, fill=hill_col)
        img = Image.blend(img, sil, alpha * 0.55)
        d = ImageDraw.Draw(img)

    # ---- main block terrain ---------------------------------------------
    base = rng.rint(6, 9)
    hs = heights_for(rng, cols, base, rng.rint(2, 4), 1)
    water_level = rng.rint(2, 4) if rng.chance(0.55) else -99
    snow = H // BLOCK - max(hs) < 6 or rng.chance(0.18)

    ground_rows = H // BLOCK + 1
    for i, h in enumerate(hs):
        x = i * BLOCK
        for level in range(0, min(h, ground_rows) + 1):
            y = H - (level + 1) * BLOCK
            depth = h - level
            if depth == 0:
                top_col, side_col = pal["grass"], pal["dirt"]
                if h <= water_level + 1:
                    top_col, side_col = pal["sand"], pal["sand"]
                elif snow and h >= max(hs) - 1:
                    top_col, side_col = mix(pal["grass"], (245, 250, 255), 0.85), pal["stone"]
                elif h >= max(hs) - 1 and rng.chance(0.25):
                    top_col, side_col = pal["stone"], pal["stone"]
            elif depth < 3:
                top_col = side_col = pal["dirt"]
            else:
                top_col = side_col = mix(pal["stone"], pal["dirt"], 0.25)
            draw_block(d, x, y, BLOCK, top_col, side_col, rng)

        # water on top of low columns
        if h < water_level:
            for level in range(h + 1, water_level + 1):
                y = H - (level + 1) * BLOCK
                wcol = mix(pal["water"], pal["sky"][1], 0.12)
                draw_block(d, x, y, BLOCK, mix(wcol, (255, 255, 255), 0.18), wcol, rng)

        # trees
        if h > water_level and rng.chance(0.10):
            th = rng.rint(2, 4)
            tx = x
            ty = H - (h + 1) * BLOCK
            for k in range(th):
                draw_block(d, tx, ty - (k + 1) * BLOCK, BLOCK,
                           mix(pal["trunk"], (255, 255, 255), 0.15), pal["trunk"], rng)
            lx, ly = tx, ty - (th + 1) * BLOCK
            leaf = mix(pal["leaf"], pal["grass"], rng.rand() * 0.3)
            for dx in range(-2, 3):
                for dy in range(-2, 2):
                    if abs(dx) + abs(dy) > 2:
                        continue
                    draw_block(d, lx + dx * BLOCK, ly + dy * BLOCK, BLOCK,
                               mix(leaf, (255, 255, 255), 0.12), leaf, rng)

    # ---- neon accents (clients only) -----------------------------------
    if build["category"] == "client":
        neon = [(45, 240, 200), (255, 110, 220), (130, 190, 255), (255, 220, 110)].copy()
        for _ in range(rng.rint(14, 22)):
            gx = rng.rint(0, cols - 1)
            gy = H - (min(hs[gx], ground_rows - 1) + 1) * BLOCK - rng.rint(1, 7) * BLOCK
            if gy < -BLOCK:
                continue
            col = neon[rng.rint(0, len(neon) - 1)]
            draw_block(d, gx * BLOCK, gy, BLOCK,
                       mix(col, (255, 255, 255), 0.5), col, rng)
        # glowing horizon band
        hy = int(H * 0.62)
        band = Image.new("RGB", (W, H), (0, 0, 0))
        bd = ImageDraw.Draw(band)
        bd.rectangle([0, hy - 4, W, hy + 4], fill=(255, 120, 230))
        band = band.filter(ImageFilter.GaussianBlur(14))
        img = Image.blend(img, band, 0.5)
        d = ImageDraw.Draw(img)

    # ---- foreground framing --------------------------------------------
    fg = shade(mix(pal["stone"], pal["dirt"], 0.4), 0.55)
    for i in range(cols):
        h = rng.rint(1, 2)
        for level in range(h):
            y = H - (level + 1) * BLOCK
            draw_block(d, i * BLOCK, y, BLOCK, shade(fg, 1.25), fg, rng)

    # ---- grade + vignette ----------------------------------------------
    if pal.get("grade_amt"):
        tint = Image.new("RGB", (W, H), pal["grade"])
        img = Image.blend(img, tint, float(pal["grade_amt"]))
    if pal.get("night"):
        night = Image.new("RGB", (W, H), (12, 18, 40))
        img = Image.blend(img, night, float(pal["night"]))

    vg = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vg).ellipse(
        [-W * 0.35, -H * 0.45, W * 1.35, H * 1.45], fill=255)
    vg = vg.filter(ImageFilter.GaussianBlur(150))
    img = Image.composite(img, Image.new("RGB", (W, H), shade(pal["fog"], 0.25)), vg)

    img.save(path, "JPEG", quality=82, optimize=True, progressive=True)


def main() -> int:
    redraw_all = "--all" in sys.argv
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
    os.makedirs(OUT_DIR, exist_ok=True)
    cat = json.load(open(CATALOG, encoding="utf-8"))

    made, skipped = 0, []
    for v in cat["versions"]:
        if only and v["category"] != only:
            continue
        out = os.path.join(OUT_DIR, "%s.jpg" % v["id"])
        if os.path.exists(out) and not redraw_all and not only:
            continue
        render(v, out)
        made += 1
        if not v.get("cover"):
            skipped.append(v["name"])

    print("rendered %d procedural covers -> assets/img/builds/" % made)
    total = len([f for f in os.listdir(OUT_DIR) if f.endswith(".jpg")])
    print("total cover files: %d / %d builds" % (total, cat["count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
