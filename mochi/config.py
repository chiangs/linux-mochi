# Mochi's settings: ~/.config/mochi/config.json ($XDG_CONFIG_HOME). The installer writes it; anything missing falls back
# to these defaults. Every key is described in the README's "Settings" section.
import json

from . import paths

DEFAULTS = {
    "color": "#33c7ff",
    "social": [],                 # ig, th, li, x (needs a social source plug-in; none ships yet)
    # how messages reach Claude Code: "auto" picks per session (tmux > kitty > wezterm > paste)
    "send": "auto",
    # the terminal Mochi opens when no Claude is running: "auto" tries $TERMINAL, alacritty, kitty, wezterm, foot, ghostty
    "terminal": "auto",
    "wake_in_tmux": True,         # start that new Claude inside tmux (the most reliable way for Mochi to reach it)
    "wake_dir": "last",           # where that new Claude starts: "last" = the folder of your most recent Claude session, or a path
    "wake_command": [],           # or spell out the whole command, e.g. ["alacritty", "-e", "claude", "--continue"]
    "close_opened_window": True,  # a terminal Mochi opened (to start Claude, or to show you its trust question) closes once
                                  # your message is in; Claude keeps running in tmux (tmux only)
    "paste_keys": "ctrl+shift+v",  # the terminal's paste shortcut, for the paste route
    "font": "sans-serif",
    "mono_font": "monospace",
    "glass_alpha": 0.86,          # the pill's darkness; lower it (e.g. 0.7) if your compositor blurs behind Mochi
    "bottom_margin": 18,
    "monitor": "",                # connector name like "DP-1"; empty = the focused monitor at launch
}


def load():
    paths.migrate_config()
    c = dict(DEFAULTS)
    try:
        c.update(json.loads(paths.CONFIG.read_text()))
    except (OSError, ValueError):
        pass
    return c


def save_key(key, value):
    try:
        j = json.loads(paths.CONFIG.read_text())
    except (OSError, ValueError):
        j = {}
    j[key] = value
    paths.CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(j, indent=2) + "\n")
    tmp.replace(paths.CONFIG)


class State:
    """Small persistent key/value store (the Mac version used UserDefaults)."""

    def __init__(self):
        try:
            self.d = json.loads(paths.STATE.read_text())
        except (OSError, ValueError):
            self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v
        try:
            paths.DATA.mkdir(parents=True, exist_ok=True)
            tmp = paths.STATE.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.d))
            tmp.replace(paths.STATE)
        except OSError:
            pass
