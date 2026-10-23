# colours are (r, g, b, a) tuples, 0..1, so the drawing code needs nothing but cairo
from collections import namedtuple

GooColors = namedtuple("GooColors", "body edge shine")

PRESETS = [("Sky", "#33c7ff"), ("Bubblegum", "#ff8fc2"), ("Mint", "#78e6aa"), ("Lemon", "#ffdc5a"),
           ("Lavender", "#baa0ff"), ("Peach", "#ffb07a"), ("Cherry", "#ff5c5c")]


def rgb(r, g, b, a=1.0):
    return (r, g, b, a)


def hex_(s):
    try:
        v = int(s.lstrip("#")[:6], 16)
    except ValueError:
        v = 0x33C7FF
    return ((v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255, 1.0)


def to_hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(x * 255)))) for x in c[:3])


def alpha(c, a):
    return (c[0], c[1], c[2], a)


def blend(c, frac, other):
    return tuple(c[i] * (1 - frac) + other[i] * frac for i in range(3)) + (c[3],)


WHITE = (1.0, 1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0, 1.0)
CYAN_TEXT = (0.5, 0.9, 1.0, 0.9)


def white(a):
    return (1.0, 1.0, 1.0, a)


def goo_colors(body):
    # the edge and shine are worked out from the body colour
    return GooColors(body, blend(body, 0.38, BLACK), blend(body, 0.72, WHITE))
