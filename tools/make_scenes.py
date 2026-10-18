#!/usr/bin/env python3
"""
Generate the inline artwork for the launcher.

Eleven group scenes, all drawn from one vocabulary -- isometric solids with
three lit faces, liquid-glass panels, radial glows, layered atmosphere -- so
the set reads as one piece of design rather than eleven drawings.

Everything is pure SVG: no bitmaps, no external files, and the group name is
always real text so it stays crisp at any size.

    python3 tools/make_scenes.py            # rewrite index.html
    python3 tools/make_scenes.py --svg DIR  # also dump each symbol for preview
"""

import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")

FONT = "Inter,system-ui,-apple-system,'Segoe UI',sans-serif"

# ------------------------------------------------------------------ shared ---

SHARED = """<linearGradient id="g-scrim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#000" stop-opacity="0"/>
      <stop offset=".38" stop-color="#000" stop-opacity=".10"/>
      <stop offset=".72" stop-color="#000" stop-opacity=".42"/>
      <stop offset="1" stop-color="#000" stop-opacity=".76"/>
    </linearGradient>
    <radialGradient id="g-vig" cx=".5" cy=".46" r=".8">
      <stop offset=".5" stop-color="#000" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity=".58"/>
    </radialGradient>
    <linearGradient id="g-glass" x1="0" y1="0" x2=".2" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity=".36"/>
      <stop offset=".38" stop-color="#fff" stop-opacity=".10"/>
      <stop offset=".62" stop-color="#fff" stop-opacity=".06"/>
      <stop offset="1" stop-color="#fff" stop-opacity=".22"/>
    </linearGradient>
    <linearGradient id="g-rim" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity=".95"/>
      <stop offset=".42" stop-color="#fff" stop-opacity=".22"/>
      <stop offset=".72" stop-color="#fff" stop-opacity=".12"/>
      <stop offset="1" stop-color="#fff" stop-opacity=".72"/>
    </linearGradient>
    <linearGradient id="g-title" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#d5e4f6"/>
    </linearGradient>
    <filter id="f-soft" x="-45%" y="-45%" width="190%" height="190%">
      <feGaussianBlur stdDeviation="6"/>
    </filter>
    <filter id="f-glow" x="-70%" y="-70%" width="240%" height="240%">
      <feGaussianBlur stdDeviation="12"/>
    </filter>
    <filter id="f-tiny" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="2.2"/>
    </filter>"""


# ------------------------------------------------------------------- scene ---

class Scene:
    def __init__(self, key, uid):
        self.key = key
        self.uid = uid
        self.defs = []
        self.body = []
        self.n = 0

    # -- gradient helpers ---------------------------------------------------
    def _stops(self, stops):
        return "".join(
            '<stop offset="%s" stop-color="%s" stop-opacity="%s"/>' % (o, c, a)
            for o, c, a in stops
        )

    def lg(self, stops, x1=0, y1=0, x2=0, y2=1):
        self.n += 1
        i = "%s-l%d" % (self.key, self.n)
        self.defs.append(
            '<linearGradient id="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
            % (i, x1, y1, x2, y2, self._stops(stops))
        )
        return "url(#%s)" % i

    def rg(self, stops, cx=0.5, cy=0.5, r=0.6, fx=None, fy=None):
        self.n += 1
        i = "%s-r%d" % (self.key, self.n)
        f = "" if fx is None else ' fx="%s" fy="%s"' % (fx, fy)
        self.defs.append(
            '<radialGradient id="%s" cx="%s" cy="%s" r="%s"%s>%s</radialGradient>'
            % (i, cx, cy, r, f, self._stops(stops))
        )
        return "url(#%s)" % i

    def add(self, *chunks):
        for c in chunks:
            if c:
                self.body.append(c)

    # -- primitives ---------------------------------------------------------
    def sky(self, a, b, c, mid=0.55):
        g = self.lg([(0, a, 1), (mid, b, 1), (1, c, 1)])
        self.add('<rect width="480" height="270" fill="%s"/>' % g)
        return g

    def glow(self, x, y, r, color, op=0.5):
        g = self.rg([(0, color, op), (0.55, color, op * 0.42), (1, color, 0)])
        self.add('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (x, y, r, g))

    def stars(self, n, seed, x0=0, y0=0, x1=480, y1=160, maxr=1.3):
        rnd = random.Random(seed)
        dots = []
        for _ in range(n):
            x = round(rnd.uniform(x0, x1), 1)
            y = round(rnd.uniform(y0, y1), 1)
            r = round(rnd.uniform(0.5, maxr), 2)
            o = round(rnd.uniform(0.25, 0.95), 2)
            dots.append('<circle cx="%s" cy="%s" r="%s" fill="#fff" fill-opacity="%s"/>' % (x, y, r, o))
        self.add('<g fill="#fff">%s</g>' % "".join(dots))

    def cube(self, x, y, w, d, top, left, right, op=1.0, edge=None, eo=0.35, round_=2.5):
        """Isometric block. (x, y) is the top vertex of the top face."""
        h = w * 0.5
        t = "M%s %s L%s %s L%s %s L%s %s Z" % (x, y, x + w, y + h, x, y + w, x - w, y + h)
        lf = "M%s %s L%s %s L%s %s L%s %s Z" % (
            x - w, y + h, x, y + w, x, y + w + d, x - w, y + h + d)
        rt = "M%s %s L%s %s L%s %s L%s %s Z" % (
            x + w, y + h, x, y + w, x, y + w + d, x + w, y + h + d)
        s = 'stroke-linejoin="round" stroke-width="%s"' % (round_ * 2)
        self.add(
            '<path d="%s" fill="%s" fill-opacity="%s" stroke="%s" stroke-opacity="%s" %s/>'
            % (lf, left, op, left, op, s),
            '<path d="%s" fill="%s" fill-opacity="%s" stroke="%s" stroke-opacity="%s" %s/>'
            % (rt, right, op, right, op, s),
            '<path d="%s" fill="%s" fill-opacity="%s" stroke="%s" stroke-opacity="%s" %s/>'
            % (t, top, op, top, op, s),
        )
        if edge:
            self.add(
                '<path d="M%s %s L%s %s L%s %s" fill="none" stroke="%s" stroke-opacity="%s" '
                'stroke-width="1.1" stroke-linejoin="round"/>'
                % (x - w, y + h, x, y + w, x + w, y + h, edge, eo)
            )

    def glass_cube(self, x, y, w, d, tint, op=0.42, rim=0.8):
        """A cube drawn as liquid glass: translucent faces plus bright edges."""
        self.cube(x, y, w, d, tint, tint, tint, op=op)
        h = w * 0.5
        self.add(
            '<path d="M%s %s L%s %s L%s %s L%s %s Z" fill="none" stroke="#fff" '
            'stroke-opacity="%s" stroke-width="1.2" stroke-linejoin="round"/>'
            % (x, y, x + w, y + h, x, y + w, x - w, y + h, rim),
            '<path d="M%s %s L%s %s L%s %s" fill="none" stroke="#fff" stroke-opacity="%s" '
            'stroke-width="1" stroke-linejoin="round"/>'
            % (x - w, y + h, x - w, y + h + d, x, y + w + d, rim * 0.55),
            '<path d="M%s %s L%s %s L%s %s" fill="none" stroke="#fff" stroke-opacity="%s" '
            'stroke-width="1" stroke-linejoin="round"/>'
            % (x + w, y + h, x + w, y + h + d, x, y + w + d, rim * 0.55),
        )

    def panel(self, x, y, w, h, r=11, tint="#ffffff", sheen=True, glow=None):
        self.add(
            '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="url(#g-glass)" '
            'stroke="url(#g-rim)" stroke-width="1"/>' % (x, y, w, h, r)
        )
        if sheen:
            self.add(
                '<path d="M%s %s H%s" stroke="#fff" stroke-opacity=".6" stroke-width="1.5" '
                'stroke-linecap="round"/>' % (x + r, y + 1.6, x + w - r),
                '<path d="M%s %s H%s" stroke="%s" stroke-opacity=".28" stroke-width="1.2" '
                'stroke-linecap="round"/>' % (x + r, y + h - 1.4, x + w - r, tint),
            )
        if glow:
            g = self.rg([(0, glow, 0.5), (1, glow, 0)])
            self.add('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s"/>'
                     % (x + w / 2, y + h * 0.55, w * 0.66, h * 0.7, g))

    def hill(self, y, amp, color, op=1.0, phase=0, w=480):
        d = ("M0 %s C%s %s %s %s %s %s C%s %s %s %s %s %s C%s %s %s %s %s %s "
             "L%s 270 L0 270 Z") % (
            y,
            w * 0.12 + phase, y - amp, w * 0.24 + phase, y + amp * 0.5, w * 0.34 + phase, y - amp * 0.2,
            w * 0.5 + phase, y - amp * 1.2, w * 0.62 + phase, y + amp * 0.6, w * 0.74 + phase, y - amp * 0.4,
            w * 0.86 + phase, y - amp * 0.9, w * 0.94 + phase, y + amp * 0.2, w + 40 + phase, y - amp * 0.3,
            w,
        )
        self.add('<path d="%s" fill="%s" fill-opacity="%s"/>' % (d, color, op))

    def island(self, cx, cy, w, top_c, lit_c, rock_a, rock_b, depth=52, rim="#ffffff"):
        """Floating 2.5D landmass: lit grass top over a tapered rock skirt."""
        h = w * 0.5
        rock = self.lg([(0, rock_b, 1), (0.55, rock_a, 1), (1, rock_b, 0.95)])
        top = self.lg([(0, lit_c, 1), (1, top_c, 1)])
        # skirt
        self.add(
            '<path d="M%s %s L%s %s L%s %s L%s %s L%s %s L%s %s Z" fill="%s"/>'
            % (cx - w, cy, cx, cy + h, cx + w, cy,
               cx + w * 0.58, cy + depth * 0.72, cx, cy + depth,
               cx - w * 0.58, cy + depth * 0.72, rock)
        )
        # rock strata
        for k, o in ((0.30, 0.18), (0.52, 0.14), (0.72, 0.12)):
            yy = cy + depth * k
            self.add('<path d="M%s %s Q%s %s %s %s" fill="none" stroke="#000" '
                     'stroke-opacity="%s" stroke-width="1.4"/>'
                     % (cx - w * 0.86, yy, cx, yy + w * 0.22, cx + w * 0.86, yy, o))
        # grass top, rounded via a wide stroke of the same colour
        d = "M%s %s L%s %s L%s %s L%s %s Z" % (cx, cy - h, cx + w, cy, cx, cy + h, cx - w, cy)
        self.add('<path d="%s" fill="%s" stroke="%s" stroke-width="7" stroke-linejoin="round"/>'
                 % (d, top, top))
        # lit front lip
        self.add('<path d="M%s %s L%s %s L%s %s" fill="none" stroke="%s" stroke-opacity=".55" '
                 'stroke-width="2" stroke-linejoin="round"/>'
                 % (cx - w, cy, cx, cy + h, cx + w, cy, rim))

    # -- chrome -------------------------------------------------------------
    def label(self, title, sub, accent, chip=None, size=29):
        """Scene labels live in the HTML overlay so the background stays clean."""
        # Keep the call sites descriptive, but let the full-stage illustration
        # remain free of baked-in headings and counts. The selected build is
        # rendered above the artwork by the launcher itself.
        return

    def finish(self):
        self.add(
            '<rect width="480" height="270" fill="url(#g-vig)"/>',
            '<rect y="150" width="480" height="120" fill="url(#g-scrim)"/>',
        )

    # -- new primitives -----------------------------------------------------
    def aurora(self, y, amp, c1, c2, op=0.5, thick=46, seed=0):
        """A soft ribbon of light: smooth top edge, tapering bottom edge."""
        rnd = random.Random(seed)
        top, bot = [], []
        for i in range(7):
            x = -40 + i * 94
            top.append((x, y + rnd.uniform(-amp, amp)))
            bot.append((x, y + thick + rnd.uniform(-amp * .5, amp * .5)))
        def curve(pts):
            d = "M%s %s" % pts[0]
            for i in range(1, len(pts)):
                x0, y0 = pts[i - 1]; x1, y1 = pts[i]
                d += " C%s %s %s %s %s %s" % (x0 + 47, y0, x1 - 47, y1, x1, y1)
            return d
        g = self.lg([(0, c1, 0), (.22, c1, op), (.7, c2, op * .82), (1, c2, 0)], 0, 0, 0, 1)
        pts = top + list(reversed(bot))
        d = "M%s %s" % pts[0]
        for x1, y1 in pts[1:]:
            d += " L%s %s" % (x1, y1)
        d += " Z"
        self.add('<path d="%s" fill="%s" filter="url(#f-soft)"/>' % (d, g))
        # bright filament along the crest
        self.add('<path d="%s" fill="none" stroke="%s" stroke-opacity="%s" stroke-width="2.2" '
                 'filter="url(#f-tiny)"/>' % (curve(top), c1, min(1, op + .25)))

    def snowcap(self, cx, base, w, hgt, color="#eef8ff"):
        """Snow sitting on a triangle peak, with a soft sagging lower edge."""
        i = "snow-%s-%s" % (self.key, self.n)
        self.n += 1
        tri = "M%s %s L%s %s L%s %s Z" % (cx - w, base, cx, base - hgt, cx + w, base)
        lip = base - hgt * .46
        self.defs.append('<clipPath id="%s"><path d="%s"/></clipPath>' % (i, tri))
        cap = "M%s %s L%s %s L%s %s Q%s %s %s %s Q%s %s %s %s Z" % (
            cx - w, base, cx, base - hgt, cx + w, base,
            cx + w * .34, lip + hgt * .10, cx + w * .10, lip,
            cx - w * .18, lip - hgt * .07, cx - w * .46, lip + hgt * .04)
        self.add('<path d="%s" fill="%s" fill-opacity=".96" clip-path="url(#%s)"/>' % (cap, color, i))

    def torch(self, x, y, scale=1.0):
        """A small torch: stick, flame, and two glow falloffs."""
        self.glow(x, y - 6 * scale, 34 * scale, "#ff9a3c", .30)
        self.glow(x, y - 4 * scale, 12 * scale, "#ffd08a", .55)
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="1.4" fill="#4a3220"/>'
                 % (x - 1.8 * scale, y - 2 * scale, 3.6 * scale, 16 * scale))
        self.add('<path d="M%s %s q%s %s 0 %s q%s %s 0 %s Z" fill="#ffd08a" fill-opacity=".95"/>'
                 % (x, y - 12 * scale, 4 * scale, -4 * scale, -3 * scale,
                    -4 * scale, 5 * scale, 6 * scale))
        self.add('<path d="M%s %s q%s %s 0 %s Z" fill="#fff6d8"/>'
                 % (x, y - 7 * scale, 1.8 * scale, -2.5 * scale, -4 * scale))

    def beam(self, x, top, bottom, w0=1.5, w1=26, color="#c9b0ff", op=.55):
        g = self.lg([(0, color, 0), (.18, color, op * .5), (.55, color, op), (1, color, .05)],
                    0, 0, 0, 1)
        self.add('<path d="M%s %s L%s %s L%s %s L%s %s Z" fill="%s"/>'
                 % (x - w0, top, x + w0, top, x + w1, bottom, x - w1, bottom, g))
        self.add('<path d="M%s %s L%s %s L%s %s L%s %s Z" fill="%s" fill-opacity=".5" '
                 'filter="url(#f-tiny)"/>'
                 % (x - w0 * .6, top, x + w0 * .6, top, x + w1 * .34, bottom, x - w1 * .34, bottom,
                    "#ffffff"))

    def floor_glass(self, y, color="#ffffff", op=.10):
        """A glossy plane at the bottom for reflections."""
        g = self.lg([(0, color, op * 1.6), (.5, color, op * .5), (1, color, 0)])
        self.add('<rect y="%s" width="480" height="%s" fill="%s"/>' % (y, 270 - y, g))

    def render(self):
        return (
            '<symbol id="scene-%s" viewBox="0 0 480 270">\n    %s\n  </symbol>'
            % (self.key, "\n    ".join(self.defs + self.body))
        )


# ---------------------------------------------------------------- palettes ---

INK = "#05070e"


# ------------------------------------------------------------------ scenes ---

def scene_all():
    s = Scene("all", "all")
    s.sky("#060a15", "#101d33", "#05080f", mid=0.6)
    s.stars(46, 7, y1=210, maxr=1.2)
    s.glow(240, 138, 150, "#39e0c0", 0.32)
    s.glow(240, 138, 70, "#8ff8e2", 0.35)

    # orbit ring behind the hero
    s.add('<ellipse cx="240" cy="150" rx="152" ry="46" fill="none" stroke="#7ff0d8" '
          'stroke-opacity=".20" stroke-width="1" stroke-dasharray="2 7"/>')
    s.add('<ellipse cx="240" cy="150" rx="118" ry="34" fill="none" stroke="#7ff0d8" '
          'stroke-opacity=".12" stroke-width="1"/>')

    # hero glass vault
    s.glass_cube(240, 74, 60, 56, "#63f0cf", 0.16, 0.9)
    core = s.rg([(0, "#c9fff4", 1), (0.42, "#4fe8c8", 0.85), (1, "#0b6a5e", 0)], 0.38, 0.32, 0.72)
    s.add('<circle cx="240" cy="146" r="33" fill="%s"/>' % core)
    s.add('<ellipse cx="228" cy="132" rx="9" ry="6" fill="#fff" fill-opacity=".85" '
          'filter="url(#f-tiny)"/>')
    s.glass_cube(240, 74, 60, 56, "#63f0cf", 0.05, 0.55)

    # satellites
    s.cube(112, 96, 17, 15, "#8ef7e2", "#2fa391", "#49c3ad", op=0.95, edge="#d9fff8", eo=0.6)
    s.cube(372, 88, 13, 12, "#b9a6ff", "#5b48b8", "#7c68d8", op=0.95, edge="#e8e1ff", eo=0.6)
    s.cube(394, 168, 10, 9, "#ffd39b", "#b07430", "#d79a55", op=0.9, edge="#fff0d6", eo=0.5)
    s.cube(86, 178, 9, 8, "#9fe8ff", "#2f7f9e", "#4ba3c2", op=0.9, edge="#e2f9ff", eo=0.5)

    s.finish()
    s.label("ALL BUILDS", "138 RELEASES · ONE LAUNCHER", "#7ff0d8", "2010 → 2026")
    return s


def scene_preclassic():
    s = Scene("preclassic", "pre")
    s.sky("#1b2c40", "#3d5a75", "#0d1720", mid=0.42)
    s.glow(356, 96, 120, "#ffd9a0", 0.34)
    s.glow(356, 96, 42, "#ffe9c8", 0.5)
    s.add('<circle cx="356" cy="96" r="16" fill="#fff4de"/>')

    # layered ridges receding into cold blue
    s.hill(150, 22, "#2b4157", 0.85, phase=-50)
    s.hill(168, 16, "#203244", 0.95, phase=40)
    s.hill(186, 12, "#141f2b", 1.0, phase=-10)

    # the first world, larger in frame
    s.island(238, 112, 104, "#5b8a45", "#96cc6d", "#6a5747", "#1e1811", depth=76)

    # crude tree -- chunky, obviously early
    s.cube(238, 52, 10, 22, "#6b4a2f", "#382513", "#4a3019")
    s.cube(238, 30, 26, 17, "#57a04c", "#26562b", "#356e35")
    s.cube(238, 12, 16, 14, "#63ae52", "#2c6130", "#3b7a3b")
    s.cube(214, 44, 12, 10, "#4d9646", "#224d27", "#2f642f")
    s.cube(262, 46, 11, 9, "#4a9143", "#214a25", "#2d5f2d")

    # loose blocks tumbling off the edge
    for cx, cy, w, o in ((176, 128, 13, .95), (306, 132, 11, .9), (330, 104, 9, .85),
                         (196, 160, 10, .8), (288, 166, 8, .7)):
        s.cube(cx, cy, w, w * .85, "#88bb62", "#4a7638", "#628f47", op=o)

    # ground mist, but only the bottom sliver
    mist = s.lg([(0, "#7f9db5", 0), (.55, "#7f9db5", .22), (1, "#7f9db5", .05)])
    s.add('<rect y="188" width="480" height="60" fill="%s"/>' % mist)
    s.finish()
    s.label("PRE-CLASSIC", "rd-131655 \u00b7 2009 \u00b7 THE FIRST WORLD",
            "#d6f5a8", "10 BUILDS", size=26)
    return s

def scene_classic():
    s = Scene("classic", "cla")
    s.sky("#3f9fdc", "#a8ddf5", "#e8f7ff", mid=0.5)
    s.glow(96, 40, 110, "#fff4c0", 0.6)
    s.add('<circle cx="96" cy="40" r="23" fill="#fffbe8"/>')

    # soft clouds with shading
    for cx, cy, sc, op in ((352, 46, 1.0, 0.95), (188, 34, 0.7, 0.8), (424, 96, 0.55, 0.7)):
        s.add('<g opacity="%s"><ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#ffffff"/>'
              '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#dcefff" fill-opacity=".75"/>'
              '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#ffffff"/></g>'
              % (op, cx, cy + 8 * sc, 34 * sc, 11 * sc,
                 cx, cy + 4 * sc, 26 * sc, 9 * sc,
                 cx - 14 * sc, cy - 4 * sc, 20 * sc, 12 * sc))

    s.hill(198, 16, "#63a86c", 0.9, phase=-20)
    s.hill(214, 10, "#4c8c56", 1.0, phase=40)

    # creative build: three floating tiers, glass + grass
    s.island(234, 132, 78, "#6aa85a", "#8ec974", "#7a5a3a", "#3d2c1c", depth=44)
    s.cube(206, 96, 15, 22, "#8fd46f", "#57923f", "#6dad4e")
    s.cube(236, 96, 15, 22, "#8fd46f", "#57923f", "#6dad4e")
    s.cube(221, 78, 15, 18, "#9ee07c", "#5f9c45", "#74b854")

    s.glass_cube(150, 108, 26, 20, "#bfefff", 0.30, 0.85)
    s.glass_cube(330, 118, 20, 16, "#ffe6b8", 0.28, 0.8)

    # a floating glass slab with a sheen
    s.panel(300, 74, 76, 34, 8, tint="#cfefff")
    s.add('<text x="312" y="95" font-family="%s" font-size="9" font-weight="700" fill="#0d2a3a" '
          'fill-opacity=".75" letter-spacing="1.4">CREATIVE</text>' % FONT)

    s.finish()
    s.label("CLASSIC", "0.0.11a → 0.30 · CREATIVE &amp; SURVIVAL",
            "#d8f7c8", "32 BUILDS", size=28)
    return s


def scene_devs():
    s = Scene("devs", "dev")
    s.sky("#0b0918", "#221a3e", "#060510", mid=0.6)
    s.stars(28, 21, y1=120, maxr=1.0)
    s.glow(240, 150, 140, "#7a5cff", 0.26)

    # a stepped, unfinished plateau -- clearly work in progress
    steps = [(146, 176, 30, 26), (200, 168, 34, 30), (256, 160, 38, 34), (314, 170, 30, 26)]
    for cx, y, w, d in steps:
        s.cube(cx, y, w, d, "#8b7ad4", "#40326f", "#574791")
        s.cube(cx, y - d, w, 6, "#9c8ce0", "#4a3b7d", "#6252a0")

    # developer console floating above
    s.panel(148, 46, 184, 66, 13, tint="#b7a4ff", glow="#6b4fd8")
    s.add('<path d="M148 58 H332" stroke="#fff" stroke-opacity=".2" stroke-width="1"/>')
    for i, c in enumerate(("#8f7bff", "#68e8c8", "#ff8fb8")):
        s.add('<circle cx="160" cy="52" r="2.8" fill="%s" fill-opacity=".95"/>' % c)
    mono = "ui-monospace,SFMono-Regular,Menlo,monospace"
    s.add('<text x="160" y="76" font-family="%s" font-size="9" fill="#ded4ff">&gt; indev 20100223</text>' % mono)
    s.add('<text x="160" y="89" font-family="%s" font-size="9" fill="#8fe8d0">&gt; infdev 20100618</text>' % mono)
    s.add('<text x="160" y="102" font-family="%s" font-size="9" fill="#ffb0c8" '
          'fill-opacity=".85">&gt; building terrain_</text>' % mono)
    s.add('<rect x="268" y="95" width="5" height="9" fill="#ffb0c8" fill-opacity=".85"/>')

    # torches lighting the unfinished edges
    s.torch(126, 168, 1.0)
    s.torch(354, 174, 0.95)

    s.finish()
    s.label("DEV BUILDS", "INDEV &amp; INFDEV \u00b7 2010 \u00b7 UNFINISHED WORLDS",
            "#c3b2ff", "8 BUILDS", size=27)
    return s

def scene_alpha():
    s = Scene("alpha", "alp")
    s.sky("#22143c", "#7b3f68", "#f0a563", mid=0.58)
    s.glow(240, 176, 160, "#ffb877", 0.55)
    s.stars(26, 33, y1=96, maxr=1.0)

    # sun on the horizon
    sun = s.rg([(0, "#fff6d0", 1), (0.6, "#ffcf8a", 0.9), (1, "#ff9d5c", 0)])
    s.add('<circle cx="240" cy="178" r="46" fill="%s"/>' % sun)
    s.add('<circle cx="240" cy="176" r="18" fill="#fff9e2"/>')

    s.hill(186, 14, "#43265a", 0.9, phase=-40)
    s.hill(198, 12, "#2c1740", 1.0, phase=30)

    # hero island with a big tree
    s.island(244, 130, 92, "#4f8a4a", "#6fae5e", "#4b3a2e", "#241a13", depth=56)
    # trunk
    s.cube(244, 84, 8, 30, "#7a5334", "#4a3120", "#5d3f28")
    s.cube(244, 76, 8, 10, "#8a5f3c", "#543821", "#68462c")
    # canopy
    s.cube(244, 44, 30, 24, "#3f8f52", "#1f5c34", "#2c7442", edge="#6fc47a", eo=0.3)
    s.cube(220, 56, 18, 16, "#3c8a4e", "#1d5731", "#2a6f3f")
    s.cube(268, 58, 17, 15, "#3a854b", "#1c5230", "#286c3d")
    s.cube(244, 28, 19, 15, "#4d9e5c", "#256a3a", "#337c48")

    # reflections
    s.add('<ellipse cx="244" cy="200" rx="96" ry="10" fill="#ffb877" fill-opacity=".16" '
          'filter="url(#f-soft)"/>')

    s.finish()
    s.label("ALPHA", "1.0.x · THE WORLD GROWS", "#ffd0a0", "8 BUILDS", size=30)
    return s


def scene_beta():
    s = Scene("beta", "bet")
    s.sky("#141a38", "#6a4470", "#f4a45e", mid=0.56)
    s.glow(132, 168, 170, "#ffbe80", 0.55)
    sun = s.rg([(0, "#fff3cf", 1), (0.55, "#ffc07a", 0.85), (1, "#ff9350", 0)])
    s.add('<circle cx="132" cy="170" r="52" fill="%s"/>' % sun)
    s.add('<circle cx="132" cy="168" r="20" fill="#fffaea"/>')

    # layered ridges
    s.hill(174, 16, "#5c3a68", 0.95, phase=-60)
    s.hill(192, 14, "#3c2550", 1.0, phase=10)
    s.hill(214, 12, "#241634", 1.0, phase=70)

    # beta house on the near hill
    s.island(330, 156, 62, "#4f8a4a", "#6fae5e", "#453427", "#221a12", depth=38)
    s.cube(330, 116, 24, 24, "#b08050", "#6b4a2b", "#8a6239")   # walls
    s.add('<path d="M306 116 L330 100 L354 116 Z" fill="#8d3f38"/>')  # roof
    s.add('<path d="M330 100 L354 116 L354 124 L330 108 Z" fill="#6e2f2a"/>')
    s.add('<rect x="324" y="126" width="9" height="10" fill="#ffd68a"/>')
    s.glow(328, 131, 16, "#ffcf85", 0.7)

    # birds
    s.add('<path d="M84 74 q6 -5 12 0 q6 -5 12 0" fill="none" stroke="#2b1b33" '
          'stroke-opacity=".6" stroke-width="1.6" stroke-linecap="round"/>')
    s.add('<path d="M110 88 q4 -3 8 0 q4 -3 8 0" fill="none" stroke="#2b1b33" '
          'stroke-opacity=".45" stroke-width="1.3" stroke-linecap="round"/>')

    s.finish()
    s.label("BETA", "1.0 → 1.8.1 · SUNSET HILLS", "#ffd2a4", "18 BUILDS", size=30)
    return s


def scene_early():
    s = Scene("early", "ear")
    s.sky("#07141c", "#0e3540", "#030b10", mid=0.6)
    s.stars(38, 55, y1=150, maxr=1.1)
    s.glow(240, 150, 140, "#3fd0c0", 0.2)

    # one keep: a wide base slab with three towers rising from it
    s.cube(240, 150, 86, 20, "#8a9ca6", "#3f535d", "#59707a")
    s.cube(240, 146, 78, 6, "#9fb0b8", "#4c616b", "#68808a")

    for cx, top, hgt, w in ((196, 96, 52, 22), (240, 78, 70, 26), (284, 104, 44, 20)):
        s.cube(cx, top, w, hgt, "#93a5ae", "#455861", "#5d7480")
        for k in (-w * .58, 0, w * .58):
            s.cube(cx + k, top - 6, 5, 7, "#a3b4bd", "#4f636d", "#6b828d")
        # arrow slit
        s.add('<rect x="%s" y="%s" width="3" height="9" rx="1.5" fill="#0a1218" '
              'fill-opacity=".8"/>' % (cx - 1.5, top + hgt * .42))

    # glowing portal in the gate
    portal = s.rg([(0, "#efd9ff", 1), (.42, "#a061ff", .95), (1, "#3a1370", .25)])
    s.add('<rect x="224" y="112" width="32" height="58" rx="16" fill="%s"/>' % portal)
    s.add('<rect x="224" y="112" width="32" height="58" rx="16" fill="none" stroke="#dcbcff" '
          'stroke-opacity=".85" stroke-width="1.3"/>')
    s.add('<ellipse cx="240" cy="142" rx="10" ry="20" fill="#f2e4ff" fill-opacity=".38" '
          'filter="url(#f-soft)"/>')
    s.glow(240, 174, 54, "#a061ff", 0.4)

    # rubble
    for cx, cy, w in ((138, 190, 13), (342, 194, 11), (166, 200, 9)):
        s.cube(cx, cy, w, w * .85, "#5f7a86", "#2f424b", "#435962", op=.92)

    s.finish()
    s.label("EARLY RELEASES", "1.0 \u2192 1.8.8 \u00b7 THE GOLDEN AGE",
            "#9ff0e2", "19 BUILDS", size=25)
    return s

def scene_mid():
    s = Scene("mid", "mid")
    s.sky("#150c28", "#3a1f5c", "#0b0516", mid=0.55)
    s.stars(46, 71, y1=170, maxr=1.2)
    s.glow(240, 150, 130, "#b06cff", 0.22)

    # beacon: narrow at the source, blooming upward
    s.beam(240, 30, 186, w0=2.4, w1=30, color="#c9b0ff", op=.5)

    # the end island
    s.island(240, 158, 76, "#3e2a5c", "#5d4283", "#2a1c3e", "#140c20", depth=44,
             rim="#c9a6ff")

    # chorus crystals -- tall, faceted, catching the light
    for cx, cy, w, hgt, o in ((210, 138, 8, 38, .95), (230, 132, 7, 52, 1),
                              (258, 140, 9, 34, .95), (274, 144, 6, 24, .85)):
        g = s.lg([(0, "#f0e2ff", .98), (.5, "#a86ef5", .9), (1, "#5a2f9e", .78)])
        s.add('<path d="M%s %s L%s %s L%s %s L%s %s Z" fill="%s" stroke="#f4e9ff" '
              'stroke-opacity=".55" stroke-width=".8"/>'
              % (cx, cy - hgt, cx + w, cy - hgt * .52, cx + w * .55, cy, cx - w * .55, cy, g))
        s.add('<path d="M%s %s L%s %s L%s %s" fill="none" stroke="#fff" stroke-opacity=".5" '
              'stroke-width="1.1"/>' % (cx, cy - hgt + 2, cx + w * .2, cy - hgt * .35, cx, cy - 3))
        s.glow(cx, cy - hgt * .7, w * 3.4, "#c9a6ff", .3 * o)

    # end crystals drifting around the island
    for cx, cy, r, o in ((120, 92, 5, .9), (364, 78, 4, .8), (400, 134, 3, .7),
                         (86, 140, 3, .6)):
        s.glow(cx, cy, r * 5.5, "#c9a6ff", .38 * o)
        s.add('<path d="M%s %s L%s %s L%s %s L%s %s Z" fill="#eadcff" fill-opacity="%s"/>'
              % (cx, cy - r, cx + r * .8, cy, cx, cy + r, cx - r * .8, cy, o))

    # end-stone pillars
    for cx, y in ((150, 172), (330, 176)):
        s.cube(cx, y, 11, 22, "#7f6aa0", "#3d2f5c", "#523f76")

    s.finish()
    s.label("MIDDLE RELEASES", "1.9 \u2192 1.17 \u00b7 THE END &amp; BEYOND",
            "#d9b8ff", "10 BUILDS", size=24)
    return s

def scene_modern():
    s = Scene("modern", "mod")
    s.sky("#03081a", "#0a2244", "#04121c", mid=0.46)
    s.stars(56, 91, y1=176, maxr=1.2)

    # moon with soft maria
    s.glow(404, 42, 56, "#cfe6ff", 0.4)
    s.add('<circle cx="404" cy="42" r="15" fill="#f2f8ff"/>')
    s.add('<circle cx="400" cy="38" r="4.2" fill="#cddff2" fill-opacity=".55"/>')
    s.add('<circle cx="409" cy="46" r="2.6" fill="#cddff2" fill-opacity=".45"/>')

    # aurora: three layered ribbons, soft and flowing
    s.aurora(64, 14, "#4dffc3", "#2a8fd8", op=.42, thick=54, seed=3)
    s.aurora(96, 18, "#8f7bff", "#37c8ff", op=.36, thick=64, seed=11)
    s.aurora(46, 10, "#5cffd8", "#4d7bff", op=.26, thick=40, seed=7)

    # peaks with proper snow caps
    s.add('<path d="M0 250 L78 196 L134 214 L206 186 L268 224 L330 200 L392 222 L446 198 '
          'L480 212 L480 270 L0 270 Z" fill="#122c47"/>')
    s.snowcap(118, 246, 86, 110)
    s.add('<path d="M32 246 L118 136 L204 246 Z" fill="#1b3a5b"/>')
    s.add('<path d="M32 246 L118 136 L118 246 Z" fill="#2b5480"/>')
    s.snowcap(118, 246, 86, 110)

    s.add('<path d="M156 252 L272 108 L388 252 Z" fill="#152f4c"/>')
    s.add('<path d="M156 252 L272 108 L272 252 Z" fill="#25507a"/>')
    s.snowcap(272, 252, 116, 144, "#f4fbff")

    s.add('<path d="M336 250 L414 170 L492 250 Z" fill="#193552"/>')
    s.add('<path d="M336 250 L414 170 L414 250 Z" fill="#2a5480"/>')
    s.snowcap(414, 250, 78, 80)

    # frosted ground catching the light
    g = s.lg([(0, "#c9e2f5", .18), (1, "#7fa8c8", .5)])
    s.add('<path d="M0 244 C90 230 160 254 250 242 C340 230 410 254 480 240 L480 270 L0 270 Z" '
          'fill="%s"/>' % g)

    s.finish()
    s.label("MODERN RELEASES", "1.18 \u2192 TODAY \u00b7 MOUNTAINS &amp; AURORA",
            "#a8f0d8", "6 BUILDS", size=23)
    return s

def scene_clients():
    s = Scene("clients", "cli")
    s.sky("#050810", "#0d1624", "#03060b", mid=0.55)
    s.glow(240, 120, 150, "#2f6fff", 0.2)
    s.stars(22, 101, y1=110, maxr=0.9)

    mono = "ui-monospace,SFMono-Regular,Menlo,monospace"

    # performance panel
    s.panel(58, 46, 136, 92, 12, tint="#8fd0ff")
    s.add('<text x="72" y="66" font-family="%s" font-size="7.6" fill="#9fc8ff" '
          'fill-opacity=".9" letter-spacing="1.6">PERFORMANCE</text>' % mono)
    s.add('<text x="72" y="92" font-family="%s" font-size="23" font-weight="700" fill="#fff">'
          '244</text>' % mono)
    s.add('<text x="118" y="92" font-family="%s" font-size="7.6" fill="#8fd0ff" '
          'fill-opacity=".85">FPS</text>' % mono)
    for i in range(11):
        hh = 4 + (i * 9 % 20)
        s.add('<rect x="%s" y="%s" width="7" height="%s" rx="1.5" fill="#5fb0ff" '
              'fill-opacity="%s"/>' % (72 + i * 10, 126 - hh, hh, .35 + (i % 4) * .15))

    # modules panel
    s.panel(292, 40, 130, 108, 12, tint="#a0ffd8", glow="#1fbf8f")
    s.add('<text x="306" y="60" font-family="%s" font-size="7.6" fill="#9ff0d0" '
          'fill-opacity=".9" letter-spacing="1.6">MODULES</text>' % mono)
    for i, (label, on) in enumerate((("AIM ASSIST", 1), ("SPRINT", 1), ("FULLBRIGHT", 0),
                                     ("FPS BOOST", 1), ("PACKET LOG", 0))):
        yy = 76 + i * 13.5
        s.add('<text x="306" y="%s" font-family="%s" font-size="7" fill="#dff8ee" '
              'fill-opacity=".88" letter-spacing=".9">%s</text>' % (yy, mono, label))
        s.add('<rect x="392" y="%s" width="16" height="7.5" rx="3.75" fill="%s" '
              'fill-opacity="%s"/>' % (yy - 6, "#3fe0a8" if on else "#ffffff", .85 if on else .18))
        s.add('<circle cx="%s" cy="%s" r="2.6" fill="#fff" fill-opacity="%s"/>'
              % (400 if on else 395, yy - 2.2, .92 if on else .45))

    # crosshair with bloom
    s.glow(240, 122, 26, "#5fffbf", .3)
    s.add('<circle cx="240" cy="122" r="13" fill="none" stroke="#fff" stroke-opacity=".6" '
          'stroke-width="1.2"/>')
    s.add('<circle cx="240" cy="122" r="1.7" fill="#5fffbf"/>')
    s.add('<path d="M240 102 V113 M240 131 V142 M220 122 H231 M249 122 H260" stroke="#fff" '
          'stroke-opacity=".85" stroke-width="1.6" stroke-linecap="round"/>')

    # health + armour, kept clear of the title band
    s.add('<rect x="164" y="166" width="152" height="6" rx="3" fill="#000" fill-opacity=".5"/>')
    hp = s.lg([(0, "#ff5f7a", 1), (1, "#ff9f6a", 1)], 0, 0, 1, 0)
    s.add('<rect x="164" y="166" width="112" height="6" rx="3" fill="%s"/>' % hp)
    s.add('<rect x="164" y="176" width="152" height="5" rx="2.5" fill="#000" fill-opacity=".5"/>')
    ar = s.lg([(0, "#7fd0ff", 1), (1, "#b9a6ff", 1)], 0, 0, 1, 0)
    s.add('<rect x="164" y="176" width="78" height="5" rx="2.5" fill="%s"/>' % ar)

    s.finish()
    s.label("CLIENTS", "PVP \u00b7 UTILITY \u00b7 HUDS", "#9ff0d0", "21 BUILDS", size=27)
    return s

def scene_extras():
    s = Scene("extras", "ext")
    s.sky("#05131a", "#0e3540", "#040d10", mid=0.5)
    s.glow(240, 110, 160, "#3fd8b0", 0.2)
    s.stars(30, 131, y1=130, maxr=1.0)

    # two glass plates for the two bonus games
    cards = ((66, 62, 148, 104, "#9ff7dc", -1), (266, 50, 158, 112, "#b8d8ff", 0))
    for x, y, w, h, tint, side in cards:
        s.panel(x, y, w, h, 14, tint=tint)

    # card 1 -- minicraft
    s.cube(106, 92, 13, 11, "#8fd46f", "#4f8a3f", "#65a84e")
    s.cube(128, 98, 10, 9, "#c9b48f", "#8a7657", "#a58f6c")
    s.add('<text x="88" y="142" font-family="%s" font-size="8.6" font-weight="700" fill="#e2fff4" '
          'fill-opacity=".9" letter-spacing="1.1">MINICRAFT</text>' % FONT)

    # card 2 -- Minecraft 4K
    for bx, by, c, o in ((288, 74, "#7fd0ff", .9), (310, 74, "#a8e0ff", .72),
                         (288, 98, "#5fb0e8", .85), (310, 98, "#8fd0ff", .78)):
        s.add('<rect x="%s" y="%s" width="19" height="19" rx="3" fill="%s" fill-opacity="%s"/>'
              % (bx, by, c, o))
    s.add('<text x="284" y="146" font-family="%s" font-size="8.6" font-weight="700" fill="#e6f4ff" '
          'fill-opacity=".9" letter-spacing="1.1">MINECRAFT 4K</text>' % FONT)

    # sparkles
    for cx, cy, r in ((164, 44, 2.2), (292, 32, 1.8), (438, 156, 2), (36, 152, 1.8)):
        s.add('<path d="M%s %s V%s M%s %s H%s" stroke="#bfffe8" stroke-opacity=".75" '
              'stroke-width="1.2" stroke-linecap="round"/>'
              % (cx, cy - r, cy + r, cx - r, cy, cx + r))

    s.finish()
    s.label("BONUS GAMES", "MINECRAFT 4K · MINICRAFT",
            "#a8f0d8", "2 GAMES", size=27)
    return s

SCENES = [scene_all, scene_preclassic, scene_classic, scene_devs, scene_alpha,
          scene_beta, scene_early, scene_mid, scene_modern, scene_clients,
          scene_extras]


def build():
    scenes = [fn() for fn in SCENES]
    defs = []
    for s in scenes:
        defs.extend(s.defs)
    blocks = "\n  ".join(s.render() for s in scenes)
    return (
        '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">\n'
        '  <defs>\n    ' + SHARED + "\n  </defs>\n\n  " + blocks + "\n</svg>"
    )


def main():
    svg = build()
    html = open(INDEX, encoding="utf-8").read()

    start = html.index('<svg width="0" height="0" style="position:absolute" aria-hidden="true"')
    # the art block is the first </svg> after that opening tag
    end = html.index("</svg>", start) + len("</svg>")
    html = html[:start] + svg + html[end:]
    open(INDEX, "w", encoding="utf-8").write(html)

    print("scenes   : %d" % len(SCENES))
    print("art block: %.1f KB" % (len(svg) / 1024))
    print("index    : %.1f KB" % (len(html) / 1024))

    if "--svg" in sys.argv:
        out = sys.argv[sys.argv.index("--svg") + 1]
        os.makedirs(out, exist_ok=True)
        for fn in SCENES:
            s = fn()
            doc = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 270" '
                   'width="960" height="540"><defs>%s%s</defs>%s</svg>'
                   % (SHARED, "\n".join(s.defs), "\n".join(s.body)))
            open(os.path.join(out, "%s.svg" % s.key), "w").write(doc)
        print("dumped   : %s" % out)


if __name__ == "__main__":
    main()
