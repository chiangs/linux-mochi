#!/usr/bin/env python3
"""Mochi's to-do list from the command line, so Claude can add things you need to do yourself.
Mochi watches the file and pops up "added to your to-do list" when something new lands.

  todo.py add "Rename the project folder"
  todo.py list
  todo.py done 2            (or part of the text)
"""
import json, os, sys, time, uuid

FILE = os.path.expanduser("~/Library/Application Support/Mochi/todos.json")


def load():
    try:
        return json.load(open(FILE))
    except (OSError, ValueError):
        return []


def save(items):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE + ".tmp", "w") as f:
        json.dump(items, f)
    os.replace(FILE + ".tmp", FILE)


cmd, rest = (sys.argv[1] if len(sys.argv) > 1 else "list"), " ".join(sys.argv[2:]).strip()
items = load()
open_items = [t for t in items if not t.get("done")]

if cmd == "add" and rest:
    items.append({"id": str(uuid.uuid4()).upper(), "text": rest[:200], "added": time.time()})
    save(items)
    print("added:", rest)
elif cmd == "done" and rest:
    hit = open_items[int(rest) - 1] if rest.isdigit() and 0 < int(rest) <= len(open_items) else \
        next((t for t in open_items if rest.lower() in t["text"].lower()), None)
    if not hit:
        sys.exit("not on the list: " + rest)
    hit["done"] = time.time()
    save(items)
    print("done:", hit["text"])
else:
    for i, t in enumerate(open_items, 1):
        print(f"{i}. {t['text']}")
    if not open_items:
        print("(nothing on the list)")
