#!/bin/bash
# Mochi installer for Arch Linux (CachyOS, EndeavourOS, …) on Wayland: asks what colour she should be and how she should
# reach Claude Code, installs what she needs, puts her in ~/.local, and connects her to Claude Code
# (adds a few hooks to ~/.claude/settings.json, backing it up first).
#
#   ./install.sh            set up from scratch (asks the questions)
#   ./install.sh --rebuild  reinstall and restart after changing her code, keeping your answers (what Claude uses)
#   ./install.sh --update   get the newest Mochi from GitHub, then rebuild
#   ./install.sh --yes      no questions: default answers, installs missing packages
set -e
cd "$(dirname "$0")"
REPO="$PWD"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/mochi"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}/mochi"
APPDIR="$DATA/app"
BIN="$HOME/.local/bin"
MODE=""; YES=""
for a in "$@"; do case "$a" in --rebuild|--update) MODE="$a";; --yes|-y) YES=1;; esac; done
c() { printf "\033[38;2;%d;%d;%dm██\033[0m" "$1" "$2" "$3"; }
ask() { if [ -n "$YES" ]; then REPLY="$2"; else read -r -p "$1" REPLY; REPLY="${REPLY:-$2}"; fi; }

if [ "$MODE" = "--update" ]; then
  echo "  Getting the newest Mochi…"; git pull --ff-only; MODE="--rebuild"
fi
# settings moved from ~/.local/share/mochi to ~/.config/mochi
if [ -f "$DATA/config.json" ] && [ ! -f "$CONF/config.json" ]; then mkdir -p "$CONF" && mv "$DATA/config.json" "$CONF/config.json"; fi
if [ "$MODE" = "--rebuild" ] && [ ! -f "$CONF/config.json" ]; then MODE=""; fi   # never set up yet: ask the questions

# --- what she needs ---
PKGS="python python-gobject python-cairo gtk4 gtk4-layer-shell wl-clipboard wtype tmux"
if [ "$MODE" != "--rebuild" ]; then
  if [ -f /etc/arch-release ] || grep -qiE '^(ID|ID_LIKE)=.*arch' /etc/os-release 2>/dev/null; then
    missing=$(pacman -T $PKGS 2>/dev/null || true)
    if [ -n "$missing" ]; then
      echo ""
      echo "  Mochi needs a few packages: $(echo $missing)"
      ask "  Install them with pacman now? [Y/n]: " y
      if [[ "$REPLY" =~ ^[Yy] ]]; then sudo pacman -S --needed --noconfirm $missing
      else echo "  OK. Install them yourself with: sudo pacman -S --needed $(echo $missing)"; fi
    fi
  else
    echo "  This installer is written for Arch-based systems. Make sure you have the equivalents of: $PKGS"
  fi
  command -v claude >/dev/null || echo "  Heads up: Claude Code isn't on your PATH yet (https://docs.claude.com/en/docs/claude-code). Mochi will look for it when you message her."
  [ -n "$WAYLAND_DISPLAY" ] || echo "  Heads up: you don't seem to be in a Wayland session. Mochi is made for Wayland compositors (Hyprland, Sway, KDE, niri…)."
  [ "$XDG_CURRENT_DESKTOP" = "GNOME" ] && echo "  Heads up: GNOME doesn't support the layer-shell protocol, so Mochi will be an ordinary window there."
fi

if [ "$MODE" != "--rebuild" ]; then
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
ask "  Pick one [1]: " 1; pick="$REPLY"
case "$pick" in
  1) HEX="#33c7ff";; 2) HEX="#ff8fc2";; 3) HEX="#78e6aa";; 4) HEX="#ffdc5a";;
  5) HEX="#baa0ff";; 6) HEX="#ffb07a";; 7) HEX="#ff5c5c";;
  \#*) HEX="$pick";;
  *) if [[ "$pick" =~ ^[0-9a-fA-F]{6}$ ]]; then HEX="#$pick"; else HEX="#33c7ff"; fi;;
esac
R=$((16#${HEX:1:2})); G=$((16#${HEX:3:2})); B=$((16#${HEX:5:2}))
echo ""
echo "  $(c $R $G $B)$(c $R $G $B)  Mochi will be $HEX. (You can change it later from her menu.)"
echo ""

# --- 2. how she reaches Claude ---
TERM_GUESS=""
for t in "$TERMINAL" alacritty kitty wezterm foot ghostty; do [ -n "$t" ] && command -v "$t" >/dev/null && { TERM_GUESS="$t"; break; }; done
echo "  How should Mochi reach Claude Code?"
echo ""
echo "    1) Through tmux (recommended). Run Claude inside tmux and Mochi types into it directly:"
echo "       your focus never moves and your clipboard is never touched."
echo "    2) Straight into your terminal window. Mochi focuses it, pastes, presses Return and puts you back."
echo "       Works with any terminal; kitty (remote control) and WezTerm are reached directly."
echo ""
ask "  Pick one [1]: " 1
if [ "$REPLY" = "2" ]; then TMUX_WAKE=false; else TMUX_WAKE=true; fi
echo ""
echo "  When no Claude is running, Mochi opens one in: ${TERM_GUESS:-(no terminal found)}"
ask "  Use that terminal? Or type another (like kitty) [${TERM_GUESS:-alacritty}]: " "${TERM_GUESS:-alacritty}"; TERM_PICK="$REPLY"
echo ""

mkdir -p "$DATA" "$CONF"
python3 - "$CONF/config.json" "$HEX" "$TERM_PICK" "$TMUX_WAKE" <<'PY'
import json, sys
path, color, term, tmux = sys.argv[1:]
try: c = json.load(open(path))
except (OSError, ValueError): c = {}
c.update({"color": color, "terminal": term, "wake_in_tmux": tmux == "true"})
c.setdefault("social", [])
json.dump(c, open(path, "w"), indent=2)
PY
fi   # end of the questions

# --- 3. put her in ~/.local ---
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Gtk4LayerShell', '1.0')" 2>/dev/null \
  || echo "  Heads up: GTK4 or gtk4-layer-shell isn't importable from Python yet (see the packages above)."
rm -rf "$APPDIR" && mkdir -p "$APPDIR" "$BIN"
cp -R mochi "$APPDIR/mochi"; cp -R hooks claude-skill "$APPDIR/"
find "$APPDIR" -name __pycache__ -prune -exec rm -rf {} +
cat > "$BIN/mochi" <<SH
#!/bin/sh
# Mochi, installed from $REPO
export MOCHI_REPO="$REPO"
exec env PYTHONPATH="$APPDIR\${PYTHONPATH:+:\$PYTHONPATH}" python3 -m mochi "\$@"
SH
chmod +x "$BIN/mochi"
mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
sed "s#^Exec=mochi#Exec=$BIN/mochi#" packaging/mochi.desktop > "$HOME/.local/share/applications/mochi.desktop"
python3 - <<'PY' 2>/dev/null || cp assets/icon.png "$HOME/.local/share/icons/hicolor/256x256/apps/mochi.png"
import cairo, os
src = cairo.ImageSurface.create_from_png("assets/icon.png")
dst = cairo.ImageSurface(cairo.FORMAT_ARGB32, 256, 256); cr = cairo.Context(dst)
cr.scale(256 / src.get_width(), 256 / src.get_height()); cr.set_source_surface(src); cr.paint()
dst.write_to_png(os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/mochi.png"))
PY
echo "  ✓ Mochi is in ~/.local (run her with: mochi)"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "  Heads up: ~/.local/bin isn't on your PATH. Add it, or run $BIN/mochi";; esac

# --- 4. connect her to Claude Code ---
MOCHI_REPO="$REPO" PYTHONPATH="$APPDIR" python3 -m mochi setup
[ "$MODE" = "--rebuild" ] || echo "  ✓ Claude Code knows how to change Mochi now: just ask it (\"make Mochi wear a party hat\")"

# --- 5. (re)start her ---
pkill -f "python3 -m mochi( --|$)" 2>/dev/null || true
sleep 0.3
if [ -n "$WAYLAND_DISPLAY" ]; then
  setsid -f "$BIN/mochi" >/dev/null 2>&1 < /dev/null
fi
if [ "$MODE" = "--rebuild" ]; then echo "  🫧  Mochi's rebuilt and back."; exit 0; fi

echo ""
echo "  🫧  Mochi's here! Look for her at the bottom of your screen."
echo ""
echo "  • Click her and type to talk to Claude Code."
if [ "$TMUX_WAKE" = "true" ]; then
echo "  • Start Claude inside tmux so Mochi can reach it:  tmux new -A -s claude claude"
echo "    (or just message her with no Claude running and she opens one for you)"
fi
echo "  • Right-click her for her menu (color, open at login, quit). Settings: ~/.config/mochi/config.json"
echo "  • Give her a keyboard shortcut: bind a key to  mochi --message  (see the README)."
if [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] || command -v Hyprland >/dev/null; then
  echo "  • On Hyprland, to start her with Hyprland and blur behind her glass, add the snippet from"
  if [ -f "$HOME/.config/hypr/hyprland.lua" ]; then echo "      $REPO/packaging/hyprland.lua"; else echo "      $REPO/packaging/hyprland.conf"; fi
  echo "    to your Hyprland config."
fi
echo ""
