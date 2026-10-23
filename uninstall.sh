#!/bin/bash
# removes Mochi, her data and her Claude Code hooks
cd "$(dirname "$0")"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/mochi"
pkill -f "python3 -m mochi( --|$)" 2>/dev/null || true
PYTHONPATH="$DATA/app:$PWD" python3 -m mochi setup --remove 2>/dev/null || true
rm -rf "$DATA" "${XDG_CONFIG_HOME:-$HOME/.config}/mochi" "${XDG_STATE_HOME:-$HOME/.local/state}/mochi" "$HOME/.local/bin/mochi" \
       "$HOME/.local/share/applications/mochi.desktop" "$HOME/.local/share/icons/hicolor/256x256/apps/mochi.png" \
       "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/mochi.desktop" "$HOME/.claude/skills/mochi"
echo "  Mochi has floated away. 🫧 Bye!"
echo "  (If you added her lines to your Hyprland config, take those out too.)"
