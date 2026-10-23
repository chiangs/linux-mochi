# finding Claude Code sessions and getting text into them.
#
# Each running `claude` is a Session. How Mochi reaches it (its "route") is picked per session from its environment:
#   tmux     TMUX_PANE is set         tmux paste-buffer + Enter. Focus never moves, the clipboard is never touched.
#   kitty    KITTY_LISTEN_ON is set   kitten @ send-text (needs allow_remote_control + listen_on in kitty.conf)
#   wezterm  WEZTERM_PANE is set      wezterm cli send-text
#   paste    anything else            the compositor focuses the terminal window, wtype presses the paste shortcut
#                                     and Return, then you're put back where you were (like the Mac version)
# "send" in config.json can force one ("tmux", "kitty", "wezterm", "paste"); "auto" picks as above.
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from . import paths

TERMINALS = ("alacritty", "kitty", "wezterm-gui", "wezterm", "foot", "footclient", "ghostty", "konsole", "gnome-terminal-",
             "xfce4-terminal", "tilix", "terminator", "st", "urxvt", "xterm", "rio", "contour", "blackbox")
ENV_KEYS = ("TMUX", "TMUX_PANE", "KITTY_LISTEN_ON", "KITTY_WINDOW_ID", "WEZTERM_PANE", "WEZTERM_UNIX_SOCKET")


def is_claude(cmd):
    # the claude process: "claude", "/path/to/claude --continue", or node running Claude Code's cli.js
    first = os.path.basename(cmd[0]) if cmd else ""
    return (first == "claude" or any(a.endswith("/claude") or "claude-code/cli" in a for a in cmd[:2])) and "bg-spare" not in " ".join(cmd)


def _read(path, binary=False):
    try:
        with open(path, "rb") as f:
            b = f.read()
        return b if binary else b.decode("utf-8", "ignore")
    except OSError:
        return None


def _stat(pid):
    s = _read(f"/proc/{pid}/stat")
    if not s: return None
    comm = s[s.index("(") + 1:s.rindex(")")]
    f = s.rsplit(")", 1)[1].split()
    return {"comm": comm, "ppid": int(f[1]), "tty_nr": int(f[4]), "start": int(f[19])}


def tty_name(tty_nr):
    major, minor = (tty_nr >> 8) & 0xFFF, (tty_nr & 0xFF) | ((tty_nr >> 12) & 0xFFF00)
    return f"/dev/pts/{minor + (major - 136) * 256}" if 136 <= major <= 143 else ""


def ancestors(pid, limit=30):
    out = []
    while pid > 1 and len(out) < limit:
        st = _stat(pid)
        if not st: break
        out.append((pid, st["comm"]))
        pid = st["ppid"]
    return out


class Session:
    def __init__(self, pid, tty, env, start, chain):
        self.pid, self.tty, self.env, self.start, self.chain = pid, tty, env, start, chain   # chain: [(pid, comm)] up to init

    @property
    def route(self):
        if self.env.get("TMUX_PANE") and shutil.which("tmux"): return "tmux"
        if self.env.get("KITTY_LISTEN_ON") and self.env.get("KITTY_WINDOW_ID") and shutil.which("kitten"): return "kitty"
        if self.env.get("WEZTERM_PANE") and shutil.which("wezterm"): return "wezterm"
        return "paste"

    def alive(self):
        return os.path.exists(f"/proc/{self.pid}")

    def terminal_pids(self):
        """pids that may own this session's terminal window: its ancestors, or for tmux the attached clients' ancestors"""
        pids = [p for p, _ in self.chain]
        if self.route == "tmux":
            for cpid in tmux_clients(self):
                pids += [p for p, _ in ancestors(cpid)]
        return pids

    def __repr__(self):
        return f"Session(pid={self.pid}, tty={self.tty}, route={self.route})"


def sessions():
    """every Claude Code running on this machine (for this user), newest first"""
    found = {}
    me = os.getuid()
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            if os.stat(f"/proc/{d}").st_uid != me: continue
        except OSError:
            continue
        raw = _read(f"/proc/{d}/cmdline", binary=True)
        if not raw: continue
        cmd = raw.decode("utf-8", "ignore").rstrip("\0").split("\0")
        if not is_claude(cmd): continue
        st = _stat(int(d))
        if not st or not st["tty_nr"]: continue
        chain = ancestors(int(d))
        # a wrapper script and the node process it runs are one session: keep the outermost
        tty = tty_name(st["tty_nr"])
        envb = _read(f"/proc/{d}/environ", binary=True) or b""
        env = {}
        for kv in envb.split(b"\0"):
            k, _, v = kv.decode("utf-8", "ignore").partition("=")
            if k in ENV_KEYS: env[k] = v
        s = Session(int(d), tty, env, st["start"], chain)
        if tty not in found or s.start < found[tty].start: found[tty] = s
    return sorted(found.values(), key=lambda s: -s.start)


def session_for(pid=0, tty=""):
    ss = sessions()
    return next((s for s in ss if pid and s.pid == pid), None) or next((s for s in ss if tty and s.tty == tty), None)


# ---- tmux ----

def _tmux(s, *args, input=None):
    sock = (s.env.get("TMUX") or "").split(",")[0]
    cmd = ["tmux"] + (["-S", sock] if sock else []) + list(args)
    r = subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=2)
    if r.returncode != 0: raise RuntimeError("tmux: " + (r.stderr.strip() or "failed"))
    return r.stdout


def tmux_clients(s):
    try:
        sess = _tmux(s, "display-message", "-p", "-t", s.env["TMUX_PANE"], "#{session_id}").strip()
        out = _tmux(s, "list-clients", "-F", "#{client_pid} #{session_id}")
    except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError):
        return []
    return [int(p) for p, sid in (ln.split() for ln in out.splitlines() if ln.count(" ") == 1) if sid == sess]


# ---- what's on Claude's screen ----

# Claude Code asks whether to trust a folder the first time it starts there. Anything typed then lands on that
# question (and Return picks the highlighted "No, exit"), so Mochi waits for you to answer it instead.
TRUST_MARKERS = ("trust this folder", "trust the files in this folder")


def screen(s):
    """the visible text of a session's terminal, where the route can read it (tmux, kitty, wezterm), else None"""
    try:
        if s.route == "tmux":
            return _tmux(s, "capture-pane", "-p", "-t", s.env["TMUX_PANE"])
        if s.route == "kitty":
            r = subprocess.run(["kitten", "@", "--to", s.env["KITTY_LISTEN_ON"], "get-text", "--match", "id:" + s.env["KITTY_WINDOW_ID"]],
                               capture_output=True, text=True, timeout=2)
            return r.stdout if r.returncode == 0 else None
        if s.route == "wezterm":
            env = dict(os.environ)
            if s.env.get("WEZTERM_UNIX_SOCKET"): env["WEZTERM_UNIX_SOCKET"] = s.env["WEZTERM_UNIX_SOCKET"]
            r = subprocess.run(["wezterm", "cli", "get-text", "--pane-id", s.env["WEZTERM_PANE"]], capture_output=True, text=True, timeout=2, env=env)
            return r.stdout if r.returncode == 0 else None
    except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError):
        return None
    return None


def asking_trust(text):
    t = (text or "").lower()
    return any(m in t for m in TRUST_MARKERS)


def last_dir():
    """the folder of the most recent Claude session the hooks told Mochi about (likely one you already trust)"""
    best = (0, None)
    for f in (paths.WORKING, paths.LAST):
        try:
            j = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(j, dict) and j.get("cwd") and os.path.isdir(j["cwd"]) and j.get("time", 0) > best[0]:
            best = (j["time"], j["cwd"])
    return best[1]


def has_conversation(d):
    """whether Claude Code has a saved conversation for folder d (~/.claude/projects/<the path with every non-alphanumeric as ->)"""
    p = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(d))
    return p.is_dir() and any(p.glob("*.jsonl"))


def same_terminal(s):
    """the Claude now running where s was (it may have restarted in the same tmux pane or terminal), or None"""
    for n in sessions():
        if s.env.get("TMUX_PANE") and n.env.get("TMUX_PANE") == s.env["TMUX_PANE"] and n.env.get("TMUX") == s.env.get("TMUX"): return n
        if s.tty and n.tty == s.tty: return n
    return None


def wake_dir(cfg):
    d = cfg.get("wake_dir") or "last"
    if d == "last": return last_dir() or str(Path.home())
    return os.path.expanduser(d)


# ---- the paste route: wl-clipboard + wtype ----

KEYCODES = {"return": "Return", "enter": "Return"}


def wtype_combo(combo):
    """'ctrl+shift+v' -> wtype arguments"""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    mods, key = parts[:-1], parts[-1]
    mods = ["logo" if m in ("super", "meta", "win") else m for m in mods]
    args = []
    for m in mods: args += ["-M", m]
    args += ["-k", key] if len(key) > 1 else [key]
    for m in reversed(mods): args += ["-m", m]
    return args


def clipboard_get():
    try:
        r = subprocess.run(["wl-paste", "--no-newline", "--type", "text"], capture_output=True, timeout=0.6)
        return r.stdout.decode("utf-8", "ignore") if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def clipboard_set(s):
    subprocess.run(["wl-copy", "--type", "text/plain;charset=utf-8"], input=s.encode(), timeout=2,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wtype(*args):
    # each wtype run is a fresh virtual keyboard, and its very first key can land before the terminal has its keymap: wait a beat
    r = subprocess.run(["wtype", "-s", "60", *args], capture_output=True, text=True, timeout=3)
    if r.returncode != 0: raise RuntimeError("wtype: " + (r.stderr.strip() or "failed"))


class Sender:
    """Gets text and keys into a Session. `later(ms, fn)` schedules on the UI loop; `done(err)` reports back (err is None on success)."""

    def __init__(self, comp, cfg, later):
        self.comp, self.cfg, self.later = comp, cfg, later

    def route(self, s):
        forced = self.cfg.get("send", "auto")
        return s.route if forced in ("", "auto") else forced

    def window_for(self, s):
        pids = set(s.terminal_pids())
        wins = [w for w in self.comp.windows() if w.pid in pids]
        return min(wins, key=lambda w: w.recent) if wins else None

    def missing_tools(self, s):
        if self.route(s) != "paste": return None
        for tool in ("wtype", "wl-copy", "wl-paste"):
            if not shutil.which(tool): return f"install {'wl-clipboard' if tool.startswith('wl-') else tool}"
        if self.comp.name == "generic": return "use tmux"
        return None

    # -- the three things Mochi does to a session --

    def send(self, s, text, done):
        """type a message into Claude and press Return"""
        r = self.route(s)
        try:
            if r == "tmux":
                pane = s.env["TMUX_PANE"]
                _tmux(s, "load-buffer", "-b", "mochi", "-", input=text)
                _tmux(s, "paste-buffer", "-p", "-d", "-b", "mochi", "-t", pane)
                self.later(250, lambda: self._finish(done, lambda: _tmux(s, "send-keys", "-t", pane, "Enter")))
                return
            if r == "kitty":
                self._kitty(s, text, bracketed=True)
                self.later(250, lambda: self._finish(done, lambda: self._kitty(s, "\r")))
                return
            if r == "wezterm":
                self._wez(s, text)
                self.later(250, lambda: self._finish(done, lambda: self._wez(s, "\r", paste=False)))
                return
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError) as e:
            done(str(e)); return
        self._paste_route(s, done, [("paste", text), ("wait", 250), ("key", "Return")])

    def answer(self, s, number, other, done):
        """pick option `number` in Claude's question menu (typing its number), then type `other` and Return if given"""
        r = self.route(s)
        try:
            if r == "tmux":
                pane = s.env["TMUX_PANE"]
                _tmux(s, "send-keys", "-t", pane, "-l", str(number))
                if other is None: done(None); return
                def rest():
                    _tmux(s, "load-buffer", "-b", "mochi", "-", input=other)
                    _tmux(s, "paste-buffer", "-p", "-d", "-b", "mochi", "-t", pane)
                    self.later(250, lambda: self._finish(done, lambda: _tmux(s, "send-keys", "-t", pane, "Enter")))
                self.later(350, lambda: self._finish(None, rest, done))
                return
            if r in ("kitty", "wezterm"):
                put = (lambda t, **k: self._kitty(s, t, **k)) if r == "kitty" else (lambda t, bracketed=False: self._wez(s, t, paste=bracketed))
                put(str(number))
                if other is None: done(None); return
                self.later(350, lambda: self._finish(None, lambda: put(other, bracketed=True), done))
                self.later(600, lambda: self._finish(done, lambda: put("\r")))
                return
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError) as e:
            done(str(e)); return
        steps = [("type", str(number))]
        if other is not None: steps += [("wait", 350), ("paste", other), ("wait", 250), ("key", "Return")]
        self._paste_route(s, done, steps)

    def press_return(self, s, done):
        """the "submit answers" step after several questions"""
        r = self.route(s)
        try:
            if r == "tmux": _tmux(s, "send-keys", "-t", s.env["TMUX_PANE"], "Enter")
            elif r == "kitty": self._kitty(s, "\r")
            elif r == "wezterm": self._wez(s, "\r", paste=False)
            else: self._paste_route(s, done, [("key", "Return")], hand_back=False); return
            done(None)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError) as e:
            done(str(e))

    def focus(self, s):
        """bring the session's terminal (and its tmux pane) to the front. A tmux session nobody is attached to
        (its window was closed, Claude still running) gets a new terminal attached to it."""
        if self.route(s) == "tmux":
            try:
                pane = s.env["TMUX_PANE"]
                _tmux(s, "select-window", "-t", pane); _tmux(s, "select-pane", "-t", pane)
                if not tmux_clients(s):
                    name = _tmux(s, "display-message", "-p", "-t", pane, "#{session_name}").strip()
                    sock = (s.env.get("TMUX") or "").split(",")[0]
                    cmd = terminal_command(self.cfg, ["tmux"] + (["-S", sock] if sock else []) + ["attach-session", "-t", name], str(Path.home()))
                    if cmd:
                        spawn(cmd)
                        return True
            except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError):
                pass
        w = self.window_for(s)
        return bool(w and self.comp.focus(w.id))

    # -- helpers --

    def _finish(self, done, fn, on_err=None):
        try:
            fn()
        except (RuntimeError, OSError, subprocess.TimeoutExpired, KeyError) as e:
            (on_err or done or (lambda _e: None))(str(e)); return
        if done: done(None)

    def _kitty(self, s, text, bracketed=False):
        args = ["kitten", "@", "--to", s.env["KITTY_LISTEN_ON"], "send-text", "--match", "id:" + s.env["KITTY_WINDOW_ID"]]
        if bracketed: args.append("--bracketed-paste=enable")
        r = subprocess.run(args + ["--stdin"], input=text, capture_output=True, text=True, timeout=3)
        if r.returncode != 0: raise RuntimeError("kitty: " + (r.stderr.strip() or "remote control is off"))

    def _wez(self, s, text, paste=True):
        args = ["wezterm", "cli", "send-text", "--pane-id", s.env["WEZTERM_PANE"]] + ([] if paste else ["--no-paste"])
        env = dict(os.environ)
        if s.env.get("WEZTERM_UNIX_SOCKET"): env["WEZTERM_UNIX_SOCKET"] = s.env["WEZTERM_UNIX_SOCKET"]
        r = subprocess.run(args, input=text, capture_output=True, text=True, timeout=3, env=env)
        if r.returncode != 0: raise RuntimeError("wezterm: " + (r.stderr.strip() or "failed"))

    def _paste_route(self, s, done, steps, hand_back=True):
        """focus the terminal window, run the steps (paste / type / key / wait), restore the clipboard, hand focus back"""
        miss = self.missing_tools(s)
        if miss: done(miss); return
        win = self.window_for(s)
        if not win: done("no window"); return
        back = self.comp.active()
        if not self.comp.focus(win.id): done("can't focus"); return
        saved, mine = None, None
        started = time.monotonic()

        def wait_focus():
            if self.comp.active() != win.id and time.monotonic() - started < 1.2:
                self.later(40, wait_focus); return
            self.later(200, lambda: run(0))

        def run(i):
            nonlocal saved, mine
            try:
                while i < len(steps):
                    kind, arg = steps[i]
                    i += 1
                    if kind == "wait": self.later(arg, lambda i=i: run(i)); return
                    if kind == "type": wtype(arg)
                    elif kind == "key": wtype("-k", arg)
                    elif kind == "paste":
                        if mine is None: saved = clipboard_get()
                        clipboard_set(arg); mine = arg
                        wtype(*wtype_combo(self.cfg.get("paste_keys", "ctrl+shift+v")))
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
                done(str(e)); return
            done(None)
            # go back to the window you were in, unless you've moved on yourself since
            if hand_back and back and back != win.id:
                self.later(800, lambda: self.comp.active() == win.id and self.comp.focus(back))
            # put the old clipboard back once the terminal has surely taken the paste, and only if nothing else changed it
            if mine is not None:
                self.later(2500, lambda: saved is not None and clipboard_get() == mine and clipboard_set(saved))
        wait_focus()


# ---- starting a new Claude when none is running ----

def find_claude():
    extra = [str(Path.home() / p) for p in (".local/bin", ".npm-global/bin", ".bun/bin", ".claude/local")] + ["/usr/local/bin", "/usr/bin"]
    return shutil.which("claude", path=os.pathsep.join([os.environ.get("PATH", "")] + extra)) or "claude"


def find_terminal(pref="auto"):
    names = ([pref] if pref and pref != "auto" else []) + [os.environ.get("TERMINAL", "")] + ["alacritty", "kitty", "wezterm", "foot", "ghostty"]
    for n in names:
        if n and shutil.which(n.split()[0]): return n.split()[0]
    return None


def terminal_command(cfg, inner, d):
    """the command that opens the user's terminal in folder d, running `inner`"""
    term = find_terminal(cfg.get("terminal", "auto"))
    if not term: return None
    t = os.path.basename(term)
    if t == "kitty": return [term, "--directory", d, *inner]
    if t == "wezterm": return [term, "start", "--cwd", d, "--", *inner]
    if t in ("foot", "footclient"): return [term, "-D", d, *inner]
    if t == "ghostty": return [term, f"--working-directory={d}", "-e", *inner]
    return [term, "--working-directory", d, "-e", *inner]   # alacritty, and most others take -e


def wake_command(cfg):
    """the command that opens a terminal running `claude --continue` (in tmux, if wanted and installed)"""
    if cfg.get("wake_command"):
        return list(cfg["wake_command"]) if isinstance(cfg["wake_command"], list) else shlex.split(cfg["wake_command"])
    d = wake_dir(cfg)
    # pick up the last conversation there, if there is one (`--continue` with none just errors and quits)
    inner = [find_claude()] + (["--continue"] if has_conversation(d) else [])
    if cfg.get("wake_in_tmux", True) and shutil.which("tmux"):
        inner = ["tmux", "new-session", "-s", f"claude-{int(time.time()) % 100000}", "-c", d, shlex.join(inner)]
    return terminal_command(cfg, inner, d)


def spawn(cmd):
    paths.log("wake: " + shlex.join(cmd))
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, cwd=str(Path.home()))
