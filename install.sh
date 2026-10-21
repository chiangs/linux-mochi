#!/bin/bash
# Mochi installer: asks what colour she should be, builds her, puts her in ~/Applications,
# and connects her to Claude Code (adds a few hooks to ~/.claude/settings.json, backing it up first).
set -e
cd "$(dirname "$0")"
APP="$HOME/Applications/Mochi.app"
DATA="$HOME/Library/Application Support/Mochi"
c() { printf "\033[38;2;%d;%d;%dm██\033[0m" "$1" "$2" "$3"; }

echo ""
echo "  🫧  Hi! Let's set up Mochi."
echo ""

# --- 1. her colour ---
echo "  What color do you want Mochi to be?"
echo ""
echo "    1) $(c 51 199 255) Sky        5) $(c 186 160 255) Lavender"
echo "    2) $(c 255 143 194) Bubblegum  6) $(c 255 176 122) Peach"
echo "    3) $(c 120 230 170) Mint       7) $(c 255 92 92) Cherry"
echo "    4) $(c 255 220 90) Lemon      8) or type any hex, like #ff66cc"
echo ""
read -r -p "  Pick one [1]: " pick
case "${pick:-1}" in
  1) HEX="#33c7ff";; 2) HEX="#ff8fc2";; 3) HEX="#78e6aa";; 4) HEX="#ffdc5a";;
  5) HEX="#baa0ff";; 6) HEX="#ffb07a";; 7) HEX="#ff5c5c";;
  \#*) HEX="$pick";;
  *) if [[ "$pick" =~ ^[0-9a-fA-F]{6}$ ]]; then HEX="#$pick"; else HEX="#33c7ff"; fi;;
esac
mkdir -p "$DATA"
R=$((16#${HEX:1:2})); G=$((16#${HEX:3:2})); B=$((16#${HEX:5:2}))
echo ""
echo "  $(c $R $G $B)$(c $R $G $B)  Mochi will be $HEX. (You can change it later from her menu.)"
echo ""

# --- 2. social notifications (optional) ---
echo "  Want Mochi to tell you when you get new notifications on social media?"
echo "  She reads the unread count from tabs you already have open in Google Chrome,"
echo "  like \"(3) Instagram\". No logins, nothing leaves your Mac."
echo ""
read -r -p "  Hook up social media? [y/N]: " yn
SOCIAL=""
if [[ "$yn" =~ ^[Yy] ]]; then
  echo ""
  echo "  Which ones? Type the numbers, like 1 3:"
  echo "    1) Instagram   2) Threads   3) LinkedIn   4) X"
  read -r -p "  [1 2 3 4]: " picks
  for n in ${picks:-1 2 3 4}; do
    case "$n" in 1) SOCIAL="$SOCIAL\"ig\","; NAMES="$NAMES, Instagram";; 2) SOCIAL="$SOCIAL\"th\","; NAMES="$NAMES, Threads";;
                 3) SOCIAL="$SOCIAL\"li\","; NAMES="$NAMES, LinkedIn";; 4) SOCIAL="$SOCIAL\"x\","; NAMES="$NAMES, X";; esac
  done
  SOCIAL="${SOCIAL%,}"
  NAMES="${NAMES#, }"; [[ "$NAMES" == *", "* ]] && NAMES="${NAMES%, *} and ${NAMES##*, }"   # "Instagram, Threads and X"
  echo "  ✓ Got it. Important: Mochi can only see sites that are open in a Chrome tab."
  echo "    Tip: pin them (right-click the tab → Pin) so they're always open. She'll show little badges; click one to jump to it."
  echo "    macOS will ask to let Mochi read Chrome the first time: say OK."
else
  echo "  No problem. You can turn it on later by running ./install.sh again."
fi
printf '{"color": "%s", "social": [%s]}\n' "$HEX" "$SOCIAL" > "$DATA/config.json"
echo ""

# --- 3. build her ---
if ! command -v swiftc >/dev/null; then
  echo "  Mochi needs Apple's command line tools to build. Installing them now (a window will pop up)…"
  xcode-select --install || true
  echo "  When that finishes, run ./install.sh again."; exit 1
fi
echo "  Building Mochi… (about 30 seconds)"
rm -rf build && mkdir -p build/Mochi.app/Contents/MacOS build/Mochi.app/Contents/Resources
if ! swiftc -O Sources/Mochi.swift -o build/Mochi.app/Contents/MacOS/Mochi 2> build/errors.txt; then
  # some Command Line Tools versions ship a duplicate Swift module map; build around it if so
  if grep -q "redefinition of module" build/errors.txt; then
    printf '' > build/empty.modulemap
    printf '{ "version": 0, "case-sensitive": "false", "roots": [ { "type": "file", "name": "/Library/Developer/CommandLineTools/usr/include/swift/module.modulemap", "external-contents": "%s/build/empty.modulemap" } ] }' "$PWD" > build/overlay.yaml
    swiftc -O -vfsoverlay build/overlay.yaml Sources/Mochi.swift -o build/Mochi.app/Contents/MacOS/Mochi
  else cat build/errors.txt; exit 1; fi
fi
cp assets/Mochi.icns build/Mochi.app/Contents/Resources/Mochi.icns
cat > build/Mochi.app/Contents/Info.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Mochi</string>
  <key>CFBundleDisplayName</key><string>Mochi</string>
  <key>CFBundleIdentifier</key><string>io.github.jessawolfe.mochi</string>
  <key>CFBundleExecutable</key><string>Mochi</string>
  <key>CFBundleIconFile</key><string>Mochi</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSAppleEventsUsageDescription</key><string>Mochi pastes your message into Terminal, where Claude Code is running, and (if you turned it on) reads unread counts from social tabs open in Chrome.</string>
</dict></plist>
PLIST
codesign --force --sign - build/Mochi.app >/dev/null 2>&1 || true
pkill -x Mochi 2>/dev/null || true
mkdir -p "$HOME/Applications" && rm -rf "$APP" && cp -R build/Mochi.app "$APP"
echo "  ✓ Mochi is in ~/Applications"

# --- 4. connect her to Claude Code ---
mkdir -p "$DATA/hooks" && cp hooks/notify.py hooks/todo.py "$DATA/hooks/"
# a reminder in Mochi's own to-do list, so she tells them how social works
if [ -n "$NAMES" ] && ! grep -q "Chrome tab" "$DATA/todos.json" 2>/dev/null; then
  python3 "$DATA/hooks/todo.py" add "Open $NAMES in Chrome tabs (pin them!) so Mochi can see your notifications" >/dev/null
fi
python3 - "$DATA/hooks/notify.py" <<'PY'
import json, os, shutil, sys, time
notify = sys.argv[1]; path = os.path.expanduser("~/.claude/settings.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
s = json.load(open(path)) if os.path.exists(path) else {}
if os.path.exists(path): shutil.copy(path, path + ".before-mochi-" + time.strftime("%Y%m%d-%H%M%S"))
cmd = lambda flag: f'python3 "{notify}"{(" " + flag) if flag else ""} 2>/dev/null || true'
want = [("Stop", None, ""), ("UserPromptSubmit", None, "--working"), ("PreToolUse", "AskUserQuestion", "--question"),
        ("PreToolUse", "*", "--doing"), ("PostToolUse", "AskUserQuestion", "--answered"), ("PostToolUse", "*", "--progress")]
hooks = s.setdefault("hooks", {})
for ev, arr in hooks.items():   # take out any older Mochi hooks first (re-running the installer replaces them)
    for m in arr: m["hooks"] = [h for h in m.get("hooks", []) if "Mochi/hooks/notify.py" not in h.get("command", "")]
    arr[:] = [m for m in arr if m.get("hooks")]
for ev, matcher, flag in want:
    arr = hooks.setdefault(ev, [])
    entry = {"hooks": [{"type": "command", "command": cmd(flag)}]}
    if matcher: entry["matcher"] = matcher
    arr.append(entry)
json.dump(s, open(path, "w"), indent=2)
print("  ✓ Connected to Claude Code (your old settings were backed up next to ~/.claude/settings.json)")
PY

open "$APP"
echo ""
echo "  🫧  Mochi's here! Look for her at the bottom of your screen."
echo ""
echo "  • Click her and type to talk to Claude Code in Terminal."
echo "  • The first time she sends a message, macOS asks to let Mochi control Terminal: say OK."
echo "    (She also needs Accessibility: System Settings → Privacy & Security → Accessibility → Mochi.)"
echo "  • Right-click her for her menu (color, open at login, quit)."
echo ""
