# python3 -m mochi  — start Mochi (running it again while she's up brings her to you and says hi)
import ctypes
import os
import sys


def preload_layer_shell():
    # gtk4-layer-shell has to be loaded before libwayland-client (which GTK pulls in), or its surfaces silently don't work
    for name in ("libgtk4-layer-shell.so.0", "libgtk4-layer-shell.so"):
        try:
            ctypes.CDLL(name)
            return True
        except OSError:
            continue
    return False


def main():
    if "--version" in sys.argv:
        from . import __version__
        print(__version__); return 0
    if sys.argv[1:2] == ["setup"]:
        from .setup import main as setup
        return setup(sys.argv[2:])
    have_ls = preload_layer_shell()
    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("GDK_BACKEND", "wayland")

    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gio, GLib

    from . import layer, paths

    if not have_ls or not layer.supported():
        msg = ("gtk4-layer-shell isn't installed" if not have_ls else
               "this compositor doesn't support wlr-layer-shell (GNOME doesn't), so Mochi can't float over your windows")
        print(f"mochi: {msg}; running as a normal window instead.", file=sys.stderr)
        paths.log("no layer-shell: " + msg)

    app = Gtk.Application(application_id="io.github.chiangs.Mochi", flags=getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE))
    state = {}

    def activate(a):
        if "bar" in state:
            state["bar"].find_mochi(); return
        from .bar import Bar
        bar = Bar(a)
        bar.install_actions()
        state["bar"] = bar
        a.hold()     # stay alive while hidden

    app.connect("activate", activate)
    GLib.set_application_name("Mochi")
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
