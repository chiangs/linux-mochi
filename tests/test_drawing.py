import cairo
import pytest

from mochi.colors import goo_colors, hex_, to_hex
from mochi.goo import Goo
from mochi.tray import pixmap
from conftest import needs_gi


def render(env, steps=40):
    g = Goo(goo_colors(hex_("#33c7ff")))
    g.env = env
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 32, 28)
    cr = cairo.Context(surf)
    cr.translate(0, 28); cr.scale(1, -1)
    for _ in range(steps):
        g.step((5.0, 3.0))
        g.draw(cr)
    return g, bytes(surf.get_data())


@pytest.mark.parametrize("env", [{"PB_HOUR": "15"}, {"PB_MOOD": "pet"}, {"PB_MOOD": "sleepy"}, {"PB_MOOD": "proud"},
                                 {"PB_MOOD": "worried"}, {"PB_HOUR": "8"}, {"PB_WEEKDAY": "6", "PB_HOUR": "14"}, {"PB_HOUR": "23"}])
def test_goo_draws_every_mood(env):
    g, px = render(env)
    assert any(px), "nothing drawn"


def test_goo_actions():
    g = Goo()
    for f in (g.hop, g.proud, g.worry, g.throw_it, g.greet, lambda: g.fling(900)):
        f()
        for _ in range(20): g.step(None)
    g.fed = 15; g.thinking = True; g.asking = True
    for _ in range(30): g.step(None)


def test_colors():
    assert to_hex(hex_("#ff8fc2")) == "#ff8fc2"
    c = goo_colors(hex_("#33c7ff"))
    assert c.edge[0] < c.body[0] < c.shine[0]


def test_tray_pixmap():
    (w, h, data), = pixmap(hex_("#33c7ff"))
    assert (w, h, len(data)) == (22, 22, 22 * 22 * 4) and any(data)


@needs_gi
def test_paginate():
    from mochi import text, ui
    fd = text.font(13)
    long = " ".join(f"Sentence number {i} is here." for i in range(60))
    pages = ui.paginate(long, 324, 88, fd)
    assert len(pages) > 1
    assert " ".join(pages).split() == long.split()
    assert all(text.size(p, fd, width=324)[1] <= 88 for p in pages[:-1])


@needs_gi
def test_parts_draw():
    from mochi.parts import Fx, Wave, Social, TodoBadge, Visitors, SOCIAL_SITES
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 40); cr = cairo.Context(surf)
    w = Wave("Mochi"); w.draw(cr, 0, 0); assert w.size()[0] > 20
    s = Social(); s.counts = [(SOCIAL_SITES[0], 3), (SOCIAL_SITES[2], 120)]; s.draw(cr, 0, 0)
    assert s.site_at(1) is SOCIAL_SITES[0] and s.site_at(s.slot(3) + 1) is SOCIAL_SITES[2]
    t = TodoBadge(); t.n = 4; t.draw(cr, 0, 0); assert t.width > 17
    v = Visitors(); v.tints = [hex_("#7ad3a3")] * 6; v.draw(cr, 0, 0); assert v.extra == 2
    f = Fx(); f.launch((0, 0), (200, 10), hex_("#33c7ff"), hex_("#ffffff")); f.draw(cr); assert f.active
