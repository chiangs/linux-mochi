# Changelog

## 1.1.0

- **Keyboard shortcut commands:** `mochi --message`, `--toggle`, `--todo`, `--hide`, `--quit` go to the running Mochi, for compositor keybindings. Opened that way she keeps the keyboard until you send, press Esc, or 20 seconds pass.
- **Claude's folder-trust question:** Mochi waits for you to answer it instead of typing into it (which picked "No, exit"), and opens a terminal for a tmux session that has no window.
- **Starting Claude:** `--continue` only where there's a conversation to continue; new sessions start in the folder of your most recent session (`wake_dir: "last"`).
- **Terminals Mochi opens** close again once your message is in; Claude keeps running in tmux (`close_opened_window`).
- **Settings moved** to `~/.config/mochi/config.json` (moved over automatically) and are documented in the README.

## 1.0.0

- Linux / Wayland port of [Mochi](https://github.com/jessawolfe-ux/mochi): GTK4 + gtk4-layer-shell, Hyprland and Sway support, tmux / kitty / WezTerm / paste routes to Claude Code, tray icon, installer for Arch-based systems.
