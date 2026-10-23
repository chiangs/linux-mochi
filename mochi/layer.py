# floating windows on Wayland: wlr-layer-shell overlay surfaces anchored to the bottom of one output,
# placed by their margins. That's what lets Mochi float over everything, on every workspace, without stealing focus.
# Without layer-shell (GNOME, X11) they fall back to plain undecorated windows, which the compositor places itself.
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk  # noqa: E402

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LS  # noqa: E402
except (ValueError, ImportError):
    LS = None

NAMESPACE = "mochi"     # for compositor rules, e.g. blur (see packaging/hyprland.lua)


def supported():
    return LS is not None and LS.is_supported()


class Floating(Gtk.Window):
    """A borderless floating window at (left, bottom) margins on one monitor. size is set with resize()."""

    def __init__(self, app, monitor=None, keyboard=False):
        super().__init__(application=app, decorated=False, resizable=False)
        self.add_css_class("mochi")
        self.left = self.bottom = 0
        self.w = self.h = 1
        self.layered = supported()
        if self.layered:
            LS.init_for_window(self)
            LS.set_namespace(self, NAMESPACE)
            LS.set_layer(self, LS.Layer.OVERLAY)
            LS.set_anchor(self, LS.Edge.BOTTOM, True)
            LS.set_anchor(self, LS.Edge.LEFT, True)
            LS.set_exclusive_zone(self, 0)
            LS.set_keyboard_mode(self, LS.KeyboardMode.ON_DEMAND if keyboard else LS.KeyboardMode.NONE)
            if monitor is not None: LS.set_monitor(self, monitor)

    def keyboard(self, mode):
        """'none', 'on_demand' or 'exclusive'"""
        if self.layered:
            LS.set_keyboard_mode(self, {"none": LS.KeyboardMode.NONE, "on_demand": LS.KeyboardMode.ON_DEMAND,
                                        "exclusive": LS.KeyboardMode.EXCLUSIVE}[mode])

    def set_monitor(self, monitor):
        if self.layered and monitor is not None: LS.set_monitor(self, monitor)

    def place(self, left, bottom):
        self.left, self.bottom = int(round(left)), int(round(bottom))
        if self.layered:
            LS.set_margin(self, LS.Edge.LEFT, self.left)
            LS.set_margin(self, LS.Edge.BOTTOM, self.bottom)

    def resize(self, w, h):
        self.w, self.h = int(round(w)), int(round(h))
        child = self.get_child()
        if child is not None: child.set_size_request(self.w, self.h)
        self.set_default_size(self.w, self.h)

    @property
    def top(self):
        return self.bottom + self.h


def monitors():
    d = Gdk.Display.get_default()
    ms = d.get_monitors()
    return [ms.get_item(i) for i in range(ms.get_n_items())]


def monitor_named(name):
    ms = monitors()
    return next((m for m in ms if name and m.get_connector() == name), ms[0] if ms else None)
