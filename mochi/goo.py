# a little goo blob drawn in chunky pixels. It breathes, blinks and follows the cursor; hops, throws, thinks,
# sleeps, gets petted; and dresses for the time of day (coffee in the morning, sunglasses on Friday afternoon, a nightcap late)
#
# Coordinates are y-up pixel cells, like the original AppKit view: cell(0, 0) is bottom-left.
# draw() expects a cairo context that is already flipped to y-up (see Pill.draw).
import math
import os
import random
import time

from .colors import rgb, white, alpha, goo_colors

INK = rgb(0.03, 0.12, 0.24)
WHITE = white(1)


def rnd(x):
    # Swift's .rounded(): halves go away from zero (Python's round() goes to even)
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


class Goo:
    cols, rows, px = 16, 14, 2
    width, height = cols * px, rows * px     # 32 × 28

    def __init__(self, colors=None):
        self.t = 0.0
        self.colors = colors or goo_colors(rgb(0.20, 0.78, 1.00))
        self.thinking = False
        self.asking = False                  # Claude asked a question: a little "?" over its head
        self.fed = 0                         # messages sent today: a little rounder with each
        self.hopT, self.hops = -10.0, 1
        self.sparkT = self.worryT = self.throwT = self.heartT = -10.0
        self.lean = self.leanV = 0.0         # springy sway, for wiggles and flings
        self.nextBlink, self.blinkT = 2.5, -10.0
        self.look = self.lookTo = 0.0
        self.lookY, self.nextLook, self.greetUntil = 0, 4.0, -10.0
        self.lastActive, self.sleepSince = 0.0, None
        self.hoverSince = None
        # for testing the outfits and moods: PB_HOUR=8, PB_WEEKDAY=6 (Friday), PB_MOOD=sleepy|pet|proud|worried
        self.env = os.environ

    # things that happen to it
    def hop(self, n=1): self.hopT = self.t; self.hops = n; self.wake()
    def proud(self): self.hop(2); self.sparkT = self.t
    def worry(self): self.worryT = self.t; self.leanV += 1.2; self.wake()
    def throw_it(self): self.throwT = self.t; self.wake()
    def fling(self, vx): self.leanV += max(-2.2, min(2.2, -vx / 500)); self.wake()
    def greet(self): self.hop(); self.lookTo = 1; self.greetUntil = self.t + 2.5

    def wake(self):
        self.lastActive = self.t
        if self.sleepSince is not None:
            self.sleepSince = None; self.hopT = self.t; self.hops = 1

    @property
    def hour(self):
        try: return int(self.env.get("PB_HOUR", ""))
        except ValueError: return time.localtime().tm_hour

    @property
    def weekday(self):
        # 1 = Sunday … 6 = Friday, like Apple's Calendar
        try: return int(self.env.get("PB_WEEKDAY", ""))
        except ValueError: return (time.localtime().tm_wday + 1) % 7 + 1

    @property
    def night(self): return self.hour >= 22 or self.hour < 5

    @property
    def sleeping(self): return self.sleepSince is not None

    @property
    def petting(self):
        if self.env.get("PB_MOOD") == "pet": return True
        return self.hoverSince is not None and self.t - self.hoverSince > 0.6

    def step(self, pointer=None):
        """Advance one frame (12 a second). pointer is (dx, dy) from the goo's face to the cursor, y up, or None if unknown."""
        t = self.t = self.t + 1 / 12
        if t > self.nextBlink: self.blinkT = t; self.nextBlink = t + 2.5 + random.uniform(0, 3)

        # eyes follow the cursor when it's near, otherwise glance around now and then
        near = over = False
        if pointer is not None:
            dx, dy = pointer
            near = dx * dx + dy * dy < 260 * 260
            if near and t > self.greetUntil:
                self.lookTo = max(-1, min(1, dx / 70)); self.lookY = 1 if dy > 40 else -1 if dy < -40 else 0
            over = abs(dx) < 15 and abs(dy) < 14
        if not near and t > self.greetUntil:
            self.lookY = 0
            if t > self.nextLook: self.lookTo = random.choice([-1, 0, 0, 1]); self.nextLook = t + 2 + random.uniform(0, 3)
        self.look += (self.lookTo - self.look) * 0.35

        # hovering: a happy wiggle, then petting, then a heart
        if over:
            if self.hoverSince is None: self.hoverSince = t; self.leanV += 0.8
            self.wake()
            if t - self.hoverSince > 2.2 and t - self.heartT > 2.6: self.heartT = t
        else:
            self.hoverSince = None

        # springy sway
        self.leanV += -self.lean * 0.3; self.leanV *= 0.78; self.lean = max(-2.5, min(2.5, self.lean + self.leanV))

        # melts into a sleepy puddle after a quiet spell (sooner late at night)
        if self.thinking: self.lastActive = t
        if self.sleepSince is None and t - self.lastActive > (60 if self.night else 300): self.sleepSince = t
        mood = self.env.get("PB_MOOD")
        if mood == "sleepy" and self.sleepSince is None: self.sleepSince = t - 2
        elif mood == "pet" and t - self.heartT > 2.6: self.heartT = t
        elif mood == "proud" and t - self.sparkT > 1.6: self.proud()
        elif mood == "worried" and t - self.worryT > 1.5: self.worry()

    def draw(self, cr, ox=0.0, oy=0.0):
        cols, rows, px, t, colors = self.cols, self.rows, self.px, self.t, self.colors

        def cell(x, y, c):
            if 0 <= x < cols and 0 <= y < rows:
                cr.set_source_rgba(*c); cr.rectangle(ox + x * px, oy + y * px, px, px); cr.fill()

        # ---- shape: breathing, hops, the throw, sleep and snacks ----
        breathe = math.sin(t * (1.4 if self.sleeping else 2.6))
        lift = squash = splat = 0.0
        hp, hopLen = t - self.hopT, 0.7
        if hp < hopLen * self.hops:
            k = math.fmod(hp, hopLen) / hopLen
            if k < 0.15: squash = 0.22 * (k / 0.15)
            elif k < 0.85: a = (k - 0.15) / 0.7; lift = 3 * math.sin(a * math.pi); squash = -0.18 * math.sin(a * math.pi)
            else: squash = 0.18 * (1 - (k - 0.85) / 0.15)
        tp = t - self.throwT
        if tp < 0.95:
            # crouch, spring up tall (the plane leaves here), drop, splat
            if tp < 0.18: squash = 0.32 * tp / 0.18
            elif tp < 0.5: a = (tp - 0.18) / 0.32; lift = 4 * math.sin(a * math.pi / 2); squash = -0.28
            elif tp < 0.72: a = (tp - 0.5) / 0.22; lift = 4 * (1 - a * a); squash = -0.1
            else: a = (tp - 0.72) / 0.23; squash = 0.34 * (1 - a); splat = 2 * (1 - a)
        melt = min(1, (t - self.sleepSince) / 1.5) if self.sleepSince is not None else 0.0
        worried = t - self.worryT < 1.4
        shiver = math.sin(t * 40) * 0.5 if worried else 0

        plump = 1 + min(self.fed, 15) * 0.012
        hgt = 7.4 * (1 + 0.05 * breathe - squash) * (1 - 0.42 * melt)
        wid = 4.8 * (1 - 0.04 * breathe + squash * 0.8) * (1 + 0.22 * melt) * plump
        sway = self.lean + shiver
        cx = 7.0
        base = rnd(lift)

        on = [[False] * cols for _ in range(rows)]
        for y in range(rows):
            yy = y - base
            if yy < 0: continue
            tilt = sway * yy / max(hgt, 1)
            for x in range(cols):
                dx, dy = (x - cx - tilt) / wid, yy / hgt
                if dx * dx + dy * dy <= 1: on[y][x] = True
        if base == 0:
            # the puddle: the bottom row spreads wider and ripples; wider still on a splat
            for x in range(cols):
                if abs(x - cx) <= wid + 1 + splat + 0.6 * math.sin(t * 3 + x): on[0][x] = True
        top = max((y for y in range(rows) if any(on[y])), default=0)

        for y in range(rows):
            for x in range(cols):
                if not on[y][x]: continue
                rim = x == 0 or x == cols - 1 or y == rows - 1 or not on[y][x - 1] or not on[y][x + 1] or (y + 1 < rows and not on[y + 1][x])
                cell(x, y, colors.edge if rim else colors.body)
        sx = rnd(cx - wid * 0.45)
        if top - 1 >= 0 and sx >= 0 and on[top - 1][sx]: cell(sx, top - 1, colors.shine)
        if top - 2 >= 0 and sx >= 0 and on[top - 2][sx]: cell(sx, top - 2, alpha(colors.shine, 0.6))

        # ---- face ----
        mid = rnd(cx + sway * 0.4)
        ex = mid + rnd(self.look)
        ey = base + rnd(hgt * 0.42)
        ey += 1 if self.thinking else self.lookY
        ey = max(base + 1, min(top - 1, ey))
        petting, sleeping = self.petting, self.sleeping
        happy = hp < hopLen * self.hops or tp < 0.95 or petting
        blinking = t - self.blinkT < 0.15
        shades = self.weekday == 6 and 12 <= self.hour < 18 and not sleeping

        def on_body(x, y): return 0 <= x < cols and 0 <= y < rows and on[y][x]
        def dot(x, y, c):
            if on_body(x, y): cell(x, y, c)

        if shades:
            # two lenses and a bridge, a glint on each
            gy = ey - (1 if self.thinking else 0)
            for x in (ex - 3, ex - 2, ex - 1, ex + 1, ex + 2, ex + 3): dot(x, gy, INK); dot(x, gy + 1, INK)
            dot(ex, gy + 1, INK)
            dot(ex - 3, gy + 1, white(0.85)); dot(ex + 1, gy + 1, white(0.85))
        else:
            for e in (ex - 2, ex + 2):
                out = -1 if e < ex else 1
                if sleeping or blinking: dot(e, ey, INK); dot(e + out, ey, INK)                        # closed
                elif petting: dot(e - 1, ey, INK); dot(e, ey + 1, INK); dot(e + 1, ey, INK)          # ^ ^
                elif worried:
                    dot(e, ey, INK); dot(e, ey + 1, INK); dot(e + out, ey, INK); dot(e + out, ey + 1, INK); dot(e, ey + 1, WHITE)
                else: dot(e, ey, INK); dot(e, ey + 1, INK)
        if petting: dot(ex - 4, ey - 1, rgb(1, 0.5, 0.65)); dot(ex + 4, ey - 1, rgb(1, 0.5, 0.65))   # blush
        if worried: dot(ex, ey - 2, INK)
        elif happy and not sleeping: dot(ex - 1, ey - 1, INK); dot(ex, ey - 2, INK); dot(ex + 1, ey - 1, INK)

        # ---- outfits ----
        hour = self.hour
        if 6 <= hour < 11:
            # morning coffee, steaming
            mug, coffee = rgb(0.96, 0.95, 0.92), rgb(0.45, 0.28, 0.18)
            for (x, y) in ((13, 0), (14, 0), (13, 1), (14, 1), (15, 1)): cell(x, y, mug)
            cell(13, 2, coffee); cell(14, 2, coffee)
            s = int(t * 3) % 2
            cell(13 + s, 3 + int(t * 2) % 2, white(0.45))
            cell(14 - s, 5 - int(t * 2) % 2, white(0.3))
        if self.night:
            # a striped nightcap with a pom, flopped to one side
            cap, stripe = rgb(0.32, 0.40, 0.92), rgb(0.85, 0.88, 1)
            y0 = top
            for x in range(mid - 3, mid + 3): cell(x, y0, cap if x % 2 == 0 else stripe)
            for x in range(mid - 2, mid + 2): cell(x, y0 + 1, cap)
            cell(mid, y0 + 2, cap); cell(mid + 1, y0 + 2, cap); cell(mid + 2, y0 + 2, cap)
            cell(mid + 3, y0 + 1, WHITE)

        # ---- little extras above its head ----
        if self.thinking and not sleeping:
            n = int(t * 2.5) % 4
            for i in range(min(n, 3)): cell(mid + 3 + i * 2, min(rows - 1, top + 1 + i), colors.shine)
        if self.asking and not sleeping and int(t * 2) % 3 != 0:
            for dx, dy in ((0, 4), (1, 4), (2, 4), (2, 3), (1, 2), (1, 0)): cell(mid + 3 + dx, min(rows - 1, top + 1 + dy), WHITE)
        if sleeping and melt >= 1:
            # a "z" drifting up
            f = int(math.fmod(t * 1.2, 4)); zx, zy = mid + 3, top + 1 + f
            for dx, dy in ((0, 2), (1, 2), (2, 2), (1, 1), (0, 0), (1, 0), (2, 0)): cell(zx + dx, zy + dy, white(0.75))
        if t - self.heartT < 1.6:
            hy, hx, pink = top + 1 + int((t - self.heartT) * 2), mid + 2, rgb(1, 0.42, 0.62)
            for dx, dy in ((0, 3), (1, 3), (3, 3), (4, 3), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (1, 1), (2, 1), (3, 1), (2, 0)):
                cell(hx + dx, hy + dy, pink)
        if t - self.sparkT < 1.4:
            pts = [(1, top), (13, top - 2), (14, 2)] if int(t * 6) % 2 == 0 else [(1, top - 3), (12, top + 1), (15, 5)]
            for x, y in pts:
                cell(x, y, WHITE)
                for (a, b) in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)): cell(a, b, colors.shine)
