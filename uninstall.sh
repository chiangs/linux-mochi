#!/bin/bash
# removes Mochi, her data and her Claude Code hooks
pkill -x Mochi 2>/dev/null || true
rm -rf "$HOME/Applications/Mochi.app" "$HOME/Library/Application Support/Mochi" "$HOME/Library/Logs/Mochi.log"
python3 - <<'PY'
import json, os
path = os.path.expanduser("~/.claude/settings.json")
if os.path.exists(path):
    s = json.load(open(path))
    for ev, arr in list(s.get("hooks", {}).items()):
        for m in arr: m["hooks"] = [h for h in m.get("hooks", []) if "Mochi/hooks/notify.py" not in h.get("command", "")]
        s["hooks"][ev] = [m for m in arr if m.get("hooks")]
        if not s["hooks"][ev]: del s["hooks"][ev]
    json.dump(s, open(path, "w"), indent=2)
PY
echo "  Mochi has floated away. 🫧 Bye!"
