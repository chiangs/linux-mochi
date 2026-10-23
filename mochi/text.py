# text with Pango: measuring, and drawing into the y-up pixel views
import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

FAMILY = {"sans": "sans-serif", "mono": "monospace"}
_WEIGHTS = {"regular": Pango.Weight.NORMAL, "medium": Pango.Weight.MEDIUM, "semibold": Pango.Weight.SEMIBOLD, "bold": Pango.Weight.BOLD}
_scratch = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))


def set_families(sans, mono):
    FAMILY["sans"], FAMILY["mono"] = sans, mono


def font(size, weight="regular", mono=False):
    d = Pango.FontDescription()
    d.set_family(FAMILY["mono" if mono else "sans"])
    d.set_weight(_WEIGHTS[weight])
    d.set_absolute_size(size * Pango.SCALE)
    return d


def layout(s, fd, cr=None, width=None):
    lay = PangoCairo.create_layout(cr or _scratch)
    lay.set_font_description(fd)
    if width is not None:
        lay.set_width(int(width * Pango.SCALE)); lay.set_wrap(Pango.WrapMode.WORD_CHAR)
    lay.set_text(s, -1)
    return lay


def size(s, fd, width=None):
    w, h = layout(s, fd, width=width).get_pixel_size()
    return w, h


def draw(cr, s, x, y, fd, color):
    """Draw text with its bottom-left at (x, y) in a y-up context (like NSString.draw(at:))."""
    lay = layout(s, fd, cr)
    _, h = lay.get_pixel_size()
    cr.save()
    cr.translate(x, y + h); cr.scale(1, -1)
    cr.set_source_rgba(*color)
    PangoCairo.show_layout(cr, lay)
    cr.restore()
