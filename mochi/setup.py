# connecting Mochi to Claude Code, used by install.sh, uninstall.sh and `mochi setup` (for packaged installs):
#   hooks   add Mochi's hooks to ~/.claude/settings.json (backing it up first), replacing any older Mochi hooks
#   unhooks take them out again
#   skill   teach Claude Code how to change Mochi (~/.claude/skills/mochi/SKILL.md)
import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import paths

SETTINGS = Path.home() / ".claude" / "settings.json"
SKILL_DIR = Path.home() / ".claude" / "skills" / "mochi"
WANT = [("Stop", None, ""), ("UserPromptSubmit", None, "--working"), ("PreToolUse", "AskUserQuestion", "--question"),
        ("PreToolUse", "*", "--doing"), ("PostToolUse", "AskUserQuestion", "--answered"), ("PostToolUse", "*", "--progress")]


def _is_mochi(h, notify=None):
    cmd = h.get("command", "")
    return "mochi/hooks/notify.py" in cmd.lower() or (notify is not None and str(notify) in cmd)   # this port's, and the macOS original's


def _strip(s, notify=None):
    hooks = s.get("hooks", {})
    for ev, arr in list(hooks.items()):
        for m in arr: m["hooks"] = [h for h in m.get("hooks", []) if not _is_mochi(h, notify)]
        arr[:] = [m for m in arr if m.get("hooks")]
        if not arr: del hooks[ev]


def _write(s, before):
    if json.dumps(s, sort_keys=True) == before: return False   # only touch the file (and back it up) when something changed
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS.exists(): shutil.copy(SETTINGS, str(SETTINGS) + ".before-mochi-" + time.strftime("%Y%m%d-%H%M%S"))
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2) + "\n")
    tmp.replace(SETTINGS)
    return True


def _load():
    try:
        return json.loads(SETTINGS.read_text())
    except FileNotFoundError:
        return {}


def register_hooks(notify):
    s = _load()
    before = json.dumps(s, sort_keys=True)
    _strip(s, notify)
    hooks = s.setdefault("hooks", {})
    for ev, matcher, flag in WANT:
        entry = {"hooks": [{"type": "command", "command": f'python3 "{notify}"{" " + flag if flag else ""} 2>/dev/null || true'}]}
        if matcher: entry["matcher"] = matcher
        hooks.setdefault(ev, []).append(entry)
    return _write(s, before)


def unregister_hooks():
    if not SETTINGS.exists(): return False
    s = _load()
    before = json.dumps(s, sort_keys=True)
    _strip(s)
    return _write(s, before)


def install_skill(template, repo, hooks_dir):
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    t = Path(template).read_text()
    t = t.replace("{{REPO}}", str(repo) if repo else "(Mochi was installed from a package: clone https://github.com/chiangs/linux-mochi to change her)")
    t = t.replace("{{DATA}}", str(paths.DATA)).replace("{{CONFIG}}", str(paths.CONFIG)).replace("{{HOOKS}}", str(hooks_dir)).replace("{{LOG}}", str(paths.LOG))
    (SKILL_DIR / "SKILL.md").write_text(t)


def main(argv):
    """mochi setup            connect a packaged Mochi (hooks in /usr/share/mochi) to Claude Code
       mochi setup --remove   disconnect her"""
    here = Path(__file__).resolve().parent
    share = next((p for p in (here.parent / "hooks", Path("/usr/share/mochi/hooks")) if (p / "notify.py").exists()), None)
    if "--remove" in argv:
        unregister_hooks()
        shutil.rmtree(SKILL_DIR, ignore_errors=True)
        print("  Mochi's hooks and skill are gone from Claude Code."); return 0
    if not share:
        print("mochi: can't find hooks/notify.py", file=sys.stderr); return 1
    # the hooks run from the data folder so they keep working however Mochi was installed
    dest = paths.DATA / "hooks"
    dest.mkdir(parents=True, exist_ok=True)
    for f in ("notify.py", "todo.py"): shutil.copy(share / f, dest / f)
    if register_hooks(dest / "notify.py"):
        print("  ✓ Connected to Claude Code (your old settings were backed up next to ~/.claude/settings.json)")
    tpl = next((p for p in (here.parent / "claude-skill" / "SKILL.md", Path("/usr/share/mochi/SKILL.md")) if p.exists()), None)
    repo = os.environ.get("MOCHI_REPO") or (str(here.parent) if (here.parent / ".git").exists() else "")
    if tpl: install_skill(tpl, repo, dest)
    return 0
