# the little things drawn on the pill next to the goo: the paper plane, the name that bobs,
# the visitor goos, the social badges and the to-do badge. All y-up, 2 px cells, like the originals.
import math
import time

from . import text
from .colors import WHITE, hex_, rgb, white, alpha, blend, BLACK


def fill(cr, x, y, w, h, c):
    cr.set_source_rgba(*c); cr.rectangle(x, y, w, h); cr.fill()


# the paper plane the goo throws when a message is sent: flies across the bar with a sparkly trail and bursts at the end
class Fx:
    px = 2

    def __init__(self):
        self.start = self.end = (0, 0)
        self.t0 = -10.0
        self.trail = []
        self.color = WHITE
        self.shine = WHITE

    def launch(self, a, b, color, shine):
        self.start, self.end, self.color, self.shine, self.trail, self.t0 = a, b, color, shine, [], time.monotonic()

    @property
    def active(self):
        return time.monotonic() - self.t0 < 1.15

    def draw(self, cr):
        e = time.monotonic() - self.t0
        if e >= 1.15:
            self.trail = []
            return
        px = self.px

        def cell(p, c):
            fill(cr, round(p[0] / px) * px, round(p[1] / px) * px, px, px, c)
        fly = 0.7
        k = min(1, e / fly)
        ease = k * k * (3 - 2 * k)
        # up out of the goo, then a long swoop right
        (sx, sy), (ex, ey) = self.start, self.end
        p = (sx + (ex - sx) * ease, sy + (ey - sy) * ease + 6 * math.sin(k * math.pi))
        if k < 1:
            self.trail.append(p)
            if len(self.trail) > 26: self.trail.pop(0)
            # the plane, nose to the right
            for dx, dy, c in ((0, 2, WHITE), (0, 1, WHITE), (1, 1, WHITE), (2, 1, WHITE), (3, 1, WHITE), (4, 1, WHITE),
                              (0, 0, self.shine), (1, 0, self.shine), (2, 0, self.shine)):
                cell((p[0] + dx * px, p[1] + dy * px), c)
        # trail: twinkly pixels that fade out
        n = len(self.trail)
        for i, q in enumerate(self.trail):
            if i % 2 != int(e * 30) % 2: continue
            a = i / max(n, 1)
            cell((q[0] - 2, q[1] + px), alpha(self.color, 0.25 + 0.6 * a * (1 if k < 1 else max(0, 1 - (e - fly) / 0.45))))
        # burst at the end
        if e > fly:
            b = (e - fly) / 0.45
            d, a = 3 + b * 9, max(0, 1 - b)
            for dx, dy in ((1.0, 0.0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)):
                c = WHITE if int(dx * 10) % 2 == 0 else self.color
                cell((ex + 4 + dx * d, ey + 2 + dy * d), alpha(c, a))


# the name on the pill: its letters bob in a gentle wave while the pill is idle
class Wave:
    def __init__(self, s):
        self.string = s
        self.color = white(0.85)
        self.font = text.font(13, "medium")
        self.bobbing = True
        self.t = 0.0

    def size(self):
        w, h = text.size(self.string, self.font)
        return math.ceil(w) + 1, math.ceil(h) + 4     # room to bob

    def draw(self, cr, x0, y0):
        x = x0
        for i, ch in enumerate(self.string):
            dy = 1.6 * math.sin(self.t * 3.2 - i * 0.75) if self.bobbing else 0
            text.draw(cr, ch, x, y0 + 2 + dy, self.font, self.color)
            x += text.size(ch, self.font)[0]


# tiny goos for a list of people (unused by default: a hook for your own customisations)
class Visitors:
    px, shown = 2, 4

    def __init__(self):
        self.tints = []
        self.t = 0.0

    @property
    def extra(self): return max(0, len(self.tints) - self.shown)

    @property
    def width(self):
        if not self.tints: return 0
        n = min(len(self.tints), self.shown)
        return n * 10 + (n - 1) * 3 + (20 if self.extra > 0 else 0)

    def draw(self, cr, ox, oy):
        px = self.px
        for i, c in enumerate(self.tints[:self.shown]):
            x0 = ox + i * 13
            bob = px if math.sin(self.t * 3 + i * 1.3) > 0.6 else 0
            edge = blend(c, 0.35, BLACK)
            # a 5×4 goo: rounded top, flat bottom, two eye pixels
            for row, line in enumerate((".XXX.", "XXXXX", "XXXXX", "XXXXX")):
                for col, ch in enumerate(line):
                    if ch != "X": continue
                    rim = row == 0 or col == 0 or col == 4
                    fill(cr, x0 + col * px, oy + (3 - row) * px + bob, px, px, edge if rim else c)
            ink = rgb(0.1, 0.15, 0.25)
            fill(cr, x0 + px, oy + 2 * px + bob, px, px, ink); fill(cr, x0 + 3 * px, oy + 2 * px + bob, px, px, ink)
        if self.extra > 0:
            text.draw(cr, f"+{self.extra}", ox + self.shown * 13 + 1, oy - 1, text.font(10, "semibold", mono=True), white(0.7))


# unread counts from social sites, as tiny pixel badges (needs a social source plug-in: see mochi/social.py)
class SocialSite:
    def __init__(self, key, name, hosts, icon, palette):
        self.key, self.name, self.hosts, self.icon, self.palette = key, name, hosts, icon, palette


SOCIAL_SITES = [
    SocialSite("ig", "Instagram", ["instagram.com"],
               [".abbbc.", "a.....c", "a.ddd.c", "a.d.d.c", "a.ddd.c", "a....ec", ".aeeec."],
               {"a": hex_("#ff3e8a"), "b": hex_("#ff5e5b"), "c": hex_("#ff9b3d"), "d": WHITE, "e": hex_("#c13ad6")}),
    SocialSite("th", "Threads", ["threads.net", "threads.com"],
               [".wwwww.", "w.....w", "w.www.w", "w.w.w.w", "w.wwwww", "w......", ".wwwww."], {"w": WHITE}),
    SocialSite("li", "LinkedIn", ["linkedin.com"],
               ["bbbbbbb", "bwbbbbb", "bbbbbbb", "bwbwwwb", "bwbwbwb", "bwbwbwb", "bbbbbbb"], {"b": hex_("#0a66c2"), "w": WHITE}),
    SocialSite("x", "X", ["x.com", "twitter.com"],
               ["w.....w", ".w...w.", "..w.w..", "...w...", "..w.w..", ".w...w.", "w.....w"], {"w": WHITE}),
]


def _icon(cr, icon, palette, x, y, px=2):
    for row, line in enumerate(icon):
        for col, ch in enumerate(line):
            c = palette.get(ch)
            if c: fill(cr, x + col * px, y + (6 - row) * px, px, px, c)


class Social:
    def __init__(self):
        self.counts = []          # [(SocialSite, n)]
        self.font = text.font(10, "semibold", mono=True)

    def label(self, n): return "99+" if n > 99 else str(n)
    def slot(self, n): return 14 + 3 + text.size(self.label(n), self.font)[0] + 7

    @property
    def width(self):
        return 0 if not self.counts else sum(self.slot(n) for _, n in self.counts) - 7

    def site_at(self, x):
        """which site sits under an x offset from the badges' left edge"""
        at = 0
        for s, n in self.counts:
            w = self.slot(n)
            if at <= x < at + w: return s
            at += w
        return None

    def draw(self, cr, ox, oy):
        x = ox
        for s, n in self.counts:
            _icon(cr, s.icon, s.palette, x, oy)
            text.draw(cr, self.label(n), x + 17, oy, self.font, white(0.85))
            x += self.slot(n)


# a pixel checklist and how many things are still open
class TodoBadge:
    ICON = ["wwwwwww", "w.....w", "w...llw", "wg....w", "wwg.llw", "w.g...w", "wwwwwww"]

    def __init__(self):
        self.n = 0
        self.font = text.font(10, "semibold", mono=True)
        self.pal = {"w": white(0.8), "g": hex_("#7ad3a3"), "l": white(0.5)}

    @property
    def width(self):
        return 0 if self.n == 0 else 17 + text.size(str(self.n), self.font)[0]

    def draw(self, cr, ox, oy):
        if self.n <= 0: return
        _icon(cr, self.ICON, self.pal, ox, oy)
        text.draw(cr, str(self.n), ox + 17, oy, self.font, white(0.85))
