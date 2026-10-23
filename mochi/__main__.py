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


USAGE = """usage: mochi [option]

Starts Mochi. When she's already running, the option goes to her (handy for keybindings):
  (none)      bring her to you and say hi
  --message   open her message bar, ready to type
  --toggle    open her message bar, or fold it if it's open
  --todo      show or hide her to-do list
  --hide      hide her (--message or no option brings her back)
  --quit      quit her

  mochi setup [--remove]   connect her to Claude Code (or disconnect)"""


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(USAGE); return 0
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

    # one Mochi at a time: running `mochi` again hands its options to the one that's running
    app = Gtk.Application(application_id="io.github.chiangs.Mochi", flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
    state = {}

    def command_line(a, cmdline):
        args = cmdline.get_arguments()[1:]
        if "bar" not in state:
            if "--quit" in args or "--hide" in args: a.quit(); return 0     # nothing running to quit or hide
            from .bar import Bar
            bar = Bar(a)
            bar.install_actions()
            state["bar"] = bar
            a.hold()     # stay alive while hidden
            if any(x in args for x in ("--message", "--todo", "--toggle")):
                GLib.timeout_add(300, lambda: (bar.command(args), False)[1])
            return 0
        state["bar"].command(args)
        return 0

    app.connect("command-line", command_line)
    GLib.set_application_name("Mochi")
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
