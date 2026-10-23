# where Mochi keeps things, following the XDG base directories
#   data (config, hook output, to-dos, hooks):  $XDG_DATA_HOME/mochi   (~/.local/share/mochi)
#   log:                                        $XDG_STATE_HOME/mochi/mochi.log
import os
from pathlib import Path


def _xdg(var, fallback):
    return Path(os.environ.get(var) or Path.home() / fallback)


DATA = _xdg("XDG_DATA_HOME", ".local/share") / "mochi"
STATE_DIR = _xdg("XDG_STATE_HOME", ".local/state") / "mochi"
CONFIG_HOME = _xdg("XDG_CONFIG_HOME", ".config")

CONFIG = DATA / "config.json"
STATE = DATA / "state.json"          # what the Mac version kept in UserDefaults (fed, nudgeDay, …)
TODOS = DATA / "todos.json"
LAST = DATA / "last.json"            # the finished reply (Stop hook)
WORKING = DATA / "working.json"      # a prompt went in (UserPromptSubmit hook)
PROGRESS = DATA / "progress.json"    # what Claude has said so far, and tokens (PostToolUse hook)
DOING = DATA / "doing.json"          # the step Claude is on (PreToolUse hook)
QUESTION = DATA / "question.json"    # AskUserQuestion (PreToolUse hook)
LOG = STATE_DIR / "mochi.log"
AUTOSTART = CONFIG_HOME / "autostart" / "mochi.desktop"


def mtime(p):
    try:
        return p.stat().st_mtime
    except OSError:
        return None


def log(line):
    import time
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line.rstrip() + "\n")
    except OSError:
        pass
