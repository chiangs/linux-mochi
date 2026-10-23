# the look of Mochi's pop-ups (smoked glass, like the pill) and small widget helpers
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib  # noqa: E402

from . import text  # noqa: E402

CSS = """
window.mochi, window.mochi.background { background: transparent; box-shadow: none; }
.glass { background-color: rgba(16, 16, 18, %(alpha)s); border: 1px solid rgba(0, 0, 0, 0.45);
         box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.28); border-radius: 15px; color: rgba(255, 255, 255, 0.92); }
.glass.step { border-radius: 12px; }
.glass label { color: rgba(255, 255, 255, 0.92); }
.glass label.mono { font-family: %(mono)s; }
.glass label.cyan, .glass button.link label { color: rgba(128, 230, 255, 0.9); }
.glass label.dim { color: rgba(255, 255, 255, 0.62); }
.glass label.faint { color: rgba(255, 255, 255, 0.45); }
.glass label.done { color: rgba(255, 255, 255, 0.45); text-decoration: line-through; }
.glass button { background: none; border: none; box-shadow: none; padding: 0; min-height: 0; min-width: 0; outline: none; }
.glass button:hover { background: none; }
.glass button.arrow label { font-size: 24px; color: rgba(255, 255, 255, 0.8); }
.glass button.x label { color: rgba(255, 255, 255, 0.55); font-size: 16px; }
.glass button.del label { color: rgba(255, 255, 255, 0.35); font-size: 14px; }
.glass button.option { background-color: rgba(255, 255, 255, 0.09); border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 10px; padding: 8px 10px; }
.glass button.option:hover { background-color: rgba(255, 255, 255, 0.15); }
.glass box.option.off { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.14); border-radius: 10px; padding: 8px 10px; }
.glass button.check { border: 1.5px solid rgba(255, 255, 255, 0.7); border-radius: 50%%; min-width: 14px; min-height: 14px; margin: 2px; }
.glass button.check.on { background-color: #7ad3a3; border-color: #7ad3a3; }
.glass button.check.on label { color: #0b2a1b; font-size: 10px; font-weight: bold; }
.glass.menu { padding: 6px 4px; }
.glass button.item { padding: 4px 8px; border-radius: 7px; }
.glass button.item:hover { background-color: rgba(255, 255, 255, 0.12); }
.glass separator.sep { background-color: rgba(255, 255, 255, 0.14); margin: 4px 8px; min-height: 1px; }
.glass button.swatch { min-width: 18px; min-height: 18px; border-radius: 50%%; border: 2px solid rgba(0, 0, 0, 0.35); }
.glass button.swatch.on { border-color: white; }
entry.mochi-field, entry.mochi-field text { background: none; border: none; box-shadow: none; outline: none; color: white; caret-color: white;
                     font-family: %(sans)s; font-size: 14px; padding: 0; min-height: 0; }
entry.mochi-field text placeholder { color: rgba(255, 255, 255, 0.62); }
"""


def install_css(glass_alpha, sans, mono):
    p = Gtk.CssProvider()
    css = CSS % {"alpha": glass_alpha, "mono": mono, "sans": sans}
    try:
        p.load_from_string(css)            # GTK ≥ 4.12
    except AttributeError:
        p.load_from_data(css, -1)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)


def label(s, size=13, weight="regular", classes=(), mono=False, wrap=None, xalign=0.0):
    lbl = Gtk.Label(label=s, xalign=xalign)
    attrs_font = text.font(size, weight, mono)
    from gi.repository import Pango
    al = Pango.AttrList(); al.insert(Pango.attr_font_desc_new(attrs_font)); lbl.set_attributes(al)
    for c in classes: lbl.add_css_class(c)
    if mono: lbl.add_css_class("mono")
    if wrap:
        lbl.set_wrap(True); lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR); lbl.set_size_request(int(wrap), -1)
        lbl.set_max_width_chars(1); lbl.set_hexpand(False)
    return lbl


def button(child_or_text, cb, classes=(), size=13, tooltip=None):
    b = Gtk.Button()
    b.set_child(label(child_or_text, size=size, xalign=0.5) if isinstance(child_or_text, str) else child_or_text)
    for c in classes: b.add_css_class(c)
    b.set_focusable(False); b.set_can_focus(False)
    b.connect("clicked", lambda *_: cb())
    if tooltip: b.set_tooltip_text(tooltip)
    return b


def natural(widget, width):
    """height of a widget laid out at a given width (ignoring the size it was last given)"""
    widget.set_size_request(-1, -1)
    _min, nat, _b1, _b2 = widget.measure(Gtk.Orientation.VERTICAL, int(width))
    return nat


def fade(win, to, secs=0.2, done=None):
    """fade a window's opacity (Mochi's NSAnimationContext alpha animations)"""
    start, frm = GLib.get_monotonic_time(), win.get_opacity()
    token = object()
    win._fade = token

    def tick():
        if getattr(win, "_fade", None) is not token: return False
        k = min(1.0, (GLib.get_monotonic_time() - start) / 1e6 / secs)
        win.set_opacity(frm + (to - frm) * k)
        if k >= 1:
            if done: done()
            return False
        return True
    GLib.timeout_add(16, tick)


def paginate(s, width, max_h, fd):
    """split a long reply into pages that fit, breaking after a sentence where one ends late enough on the page"""
    def h(t): return text.size(t, fd, width=width)[1]
    toks = []
    for i, line in enumerate(s.split("\n")):
        if i > 0: toks.append("\n")
        toks += line.split()

    def join(ts):
        out = ""
        for t in ts:
            if t == "\n": out += "\n"
            else: out += ("" if (not out or out.endswith("\n")) else " ") + t
        return out.strip()
    out, i = [], 0
    while i < len(toks):
        j = i
        while j < len(toks) and (j == i or h(join(toks[i:j + 1])) <= max_h): j += 1
        end = j
        if j < len(toks):
            for k in range(j - 1, i - 1, -1):
                t = toks[k]
                if (t == "\n" or t.endswith((".", "!", "?", ":"))) and k - i >= (j - i) // 2:
                    end = k + 1; break
        p = join(toks[i:end])
        if p: out.append(p)
        i = end
    return out or [s]
