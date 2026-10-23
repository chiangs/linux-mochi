# what Mochi needs from the compositor, beyond what Wayland lets an app do on its own:
#   cursor()            where the pointer is anywhere on screen (so her eyes can follow it), or None
#   windows()           top-level windows with their pid, for finding the terminal Claude runs in
#   active()            the focused window's id
#   focus(id)           bring a window forward (switching workspace if need be)
#   focused_monitor()   the connector name of the focused output, to start there
#   reserved(name)      space taken by bars on that output: (left, top, right, bottom)
# Hyprland and Sway are supported; anything else gets the Generic adapter (no focusing, no global cursor),
# so the tmux / kitty / wezterm routes still work there but the paste route doesn't.
import json
import os
import shutil
import socket
import subprocess


class Window:
    def __init__(self, id, pid, title="", app="", recent=0):
        self.id, self.pid, self.title, self.app, self.recent = id, pid, title, app, recent   # recent: lower = focused more recently

    def __repr__(self):
        return f"Window({self.id!r}, pid={self.pid}, app={self.app!r})"


class Generic:
    name = "generic"
    def cursor(self): return None
    def windows(self): return []
    def active(self): return None
    def focus(self, wid): return False
    def focused_monitor(self): return None
    def reserved(self, name): return (0, 0, 0, 0)


class Hyprland(Generic):
    name = "hyprland"

    def __init__(self, sig):
        rt = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        self.sock = next((p for p in (f"{rt}/hypr/{sig}/.socket.sock", f"/tmp/hypr/{sig}/.socket.sock") if os.path.exists(p)), None)
        self.lua = None           # Hyprland 0.55+ dispatches in Lua; older ones take "focuswindow address:…"

    def request(self, cmd, timeout=0.3):
        if not self.sock: return ""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(timeout); s.connect(self.sock); s.sendall(cmd.encode())
                out = b""
                while True:
                    b = s.recv(65536)
                    if not b: break
                    out += b
            return out.decode("utf-8", "ignore")
        except OSError:
            return ""

    def json(self, cmd):
        try:
            return json.loads(self.request("j/" + cmd))
        except ValueError:
            return None

    def cursor(self):
        j = self.json("cursorpos")
        return (j["x"], j["y"]) if isinstance(j, dict) and "x" in j else None

    def windows(self):
        return [Window(c.get("address"), c.get("pid", 0), c.get("title", ""), c.get("class", ""), c.get("focusHistoryID", 99))
                for c in self.json("clients") or [] if isinstance(c, dict)]

    def active(self):
        j = self.json("activewindow")
        return j.get("address") if isinstance(j, dict) else None

    def focus(self, wid):
        if not wid: return False
        forms = {True: f'dispatch hl.dsp.focus({{ window = "address:{wid}" }})', False: f"dispatch focuswindow address:{wid}"}
        for lua in ([self.lua] if self.lua is not None else [True, False]):
            if self.request(forms[lua]).strip().startswith("ok"):
                self.lua = lua
                return True
        return False

    def focused_monitor(self):
        return next((m.get("name") for m in self.json("monitors") or [] if m.get("focused")), None)

    def reserved(self, name):
        for m in self.json("monitors") or []:
            if m.get("name") == name and isinstance(m.get("reserved"), list) and len(m["reserved"]) == 4:
                return tuple(m["reserved"])
        return (0, 0, 0, 0)


class Sway(Generic):
    name = "sway"

    def msg(self, *args):
        try:
            return subprocess.run(["swaymsg", "-r", *args], capture_output=True, text=True, timeout=1).stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""

    def _nodes(self):
        try:
            tree = json.loads(self.msg("-t", "get_tree"))
        except ValueError:
            return []
        out, stack = [], [tree]
        while stack:
            n = stack.pop()
            if n.get("pid"): out.append(n)
            stack += n.get("nodes", []) + n.get("floating_nodes", [])
        return out

    def windows(self):
        return [Window(str(n["id"]), n["pid"], n.get("name") or "", n.get("app_id") or "", 0 if n.get("focused") else 1) for n in self._nodes()]

    def active(self):
        return next((str(n["id"]) for n in self._nodes() if n.get("focused")), None)

    def focus(self, wid):
        if not wid: return False
        try:
            return json.loads(self.msg(f"[con_id={wid}]", "focus"))[0].get("success", False)
        except (ValueError, IndexError, AttributeError):
            return False

    def focused_monitor(self):
        try:
            return next((o["name"] for o in json.loads(self.msg("-t", "get_outputs")) if o.get("focused")), None)
        except ValueError:
            return None


def detect():
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        h = Hyprland(os.environ["HYPRLAND_INSTANCE_SIGNATURE"])
        if h.sock: return h
    if os.environ.get("SWAYSOCK") and shutil.which("swaymsg"):
        return Sway()
    return Generic()
