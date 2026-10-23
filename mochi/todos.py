# the to-do list, kept in $XDG_DATA_HOME/mochi/todos.json (Claude can add to it too, with hooks/todo.py)
import json
import re
import time
import uuid

from . import paths


def load():
    try:
        items = json.loads(paths.TODOS.read_text())
    except (OSError, ValueError):
        return []
    lt = time.localtime()
    today = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return [t for t in items if isinstance(t, dict) and (t.get("done") is None or t["done"] >= today)]   # checked-off things fade away the next day


def save(items):
    paths.DATA.mkdir(parents=True, exist_ok=True)
    tmp = paths.TODOS.with_suffix(".tmp")
    tmp.write_text(json.dumps(items))
    tmp.replace(paths.TODOS)


def new(text_):
    return {"id": str(uuid.uuid4()).upper(), "text": text_[:200], "added": time.time(), "done": None}


def ago(t):
    s = time.time() - t
    return "now" if s < 60 else f"{int(s / 60)}m" if s < 3600 else f"{int(s / 3600)}h" if s < 86400 else f"{int(s / 86400)}d"


T = r"(?:to-?\s?do|todo)"
_STRIP = " \t\n\"“”'.!"


def parse(raw):
    """What a typed message means for the to-do list:
         ("add", text)   "todo: buy matcha", "mochi add buy matcha to my to-do list", "put x on my todo list"
         ("show", None)  "what's on my list", "todo list", "my todos?"
         ("done", what)  "done matcha", "done 2", "check off matcha"
         None            a message for Claude"""
    s = raw.strip()
    s = re.sub(r"^(?i:hey|hi|ok|okay)[,!]?\s+", "", s)
    s = re.sub(r"^(?i:mochi)[,!:]?\s+", "", s)

    def grab(pat):
        m = re.search(pat, s, re.I)
        if not m: return None
        v = m.group(1).strip(_STRIP)
        return v or None

    def matches(pat): return re.search(pat, s, re.I) is not None

    item = (grab("^" + T + r"\s*[:\-–]\s*(.+)$")
            or grab(r"^(?:please\s+|can you\s+)*add\s+(.+?)\s+to\s+(?:my\s+|the\s+)?" + T + r"(?:\s+list)?[.!?]*$")
            or grab(r"^(?:put|stick|write)\s+(.+?)\s+on\s+(?:my\s+|the\s+)?" + T + r"(?:\s+list)?[.!?]*$"))
    if item: return ("add", item)
    if (matches(r"^(?:what'?s|whats|show(?: me)?|open|see)\s+(?:on\s+)?(?:my\s+|the\s+)?(?:" + T + r"\s*)?list\??$")
            or matches(r"^what'?s\s+on\s+my\s+" + T + r"(?:\s+list)?\??$") or matches(r"^(?:my\s+)?" + T + r"(?:\s+list)?\??$")):
        return ("show", None)
    what = grab(r"^(?:done|check off|cross off|finished|completed?)\s*[:\-]?\s+(.+)$")
    if what: return ("done", what)
    return None


def find_open(items, what):
    """index into items of the open to-do that `what` names (its number among the open ones, or part of its text)"""
    open_ = [i for i, t in enumerate(items) if t.get("done") is None]
    if what.isdigit() and 1 <= int(what) <= len(open_): return open_[int(what) - 1]
    return next((i for i in open_ if what.lower() in items[i]["text"].lower()), None)
