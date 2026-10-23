---
name: mochi
description: Change, customize or update Mochi, the little pixel goo at the bottom of this Linux (Wayland) desktop that talks to Claude Code. Use when the user asks to change how Mochi looks or behaves (color, outfits, moods, animations, size, sounds), add something to Mochi's to-do list, update Mochi, or fix something about Mochi.
---

# Mochi

Mochi is a small Python/GTK4 app: a pixel goo that floats at the bottom of the screen (a wlr-layer-shell overlay), sends the user's messages to Claude Code in their terminal, and shows Claude's replies, questions, progress and a to-do list.

## Where things are

- **Her code:** `{{REPO}}/mochi/` (Python, GTK4 + gtk4-layer-shell, drawn with Cairo)
  - `goo.py`: the goo itself: shape, eyes, moods, outfits by time of day (`draw()` is y-up pixel cells, 2 px each)
  - `parts.py`: the paper plane, the bobbing name, badges
  - `bar.py`: the pill, reply bubble, question panel, to-do list, menus and sending
  - `terminals.py`: finding Claude sessions and typing into them (tmux, kitty, wezterm, or focus + paste with wtype)
  - `compositor.py`: Hyprland / Sway specifics (cursor position, focusing windows)
  - `config.py`: every setting and its default
- **The installer / rebuilder:** `{{REPO}}/install.sh`
- **Her settings:** `{{CONFIG}}`, e.g. `{"color": "#33c7ff", "terminal": "alacritty", "wake_in_tmux": true}`. All keys and defaults are in `mochi/config.py`, and described in the README's "Settings" section.
- **What Claude Code tells her:** the hooks in `~/.claude/settings.json` run `{{HOOKS}}/notify.py`, which writes `last.json`, `working.json`, `doing.json`, `progress.json` and `question.json` into `{{DATA}}`. She checks those files every 0.7 s.
- **Her log:** `{{LOG}}`
- **The macOS original** is kept for reference in `{{REPO}}/macos/`.

## Changing Mochi

1. Edit the files in `{{REPO}}/mochi/`. Keep her pixel-art style (chunky 2 px cells, about 12 frames a second).
2. Check it still imports: `cd "{{REPO}}" && python3 -c "import mochi.bar"`, and run the tests if pytest is there: `python3 -m pytest -q`.
3. Reinstall and restart her:

   ```bash
   cd "{{REPO}}" && ./install.sh --rebuild
   ```

   If she doesn't come back, run `mochi` in a terminal to see the error, fix it, and rebuild again.

To try a look without waiting for the right moment: `PB_HOUR=8 mochi` (morning coffee), `PB_WEEKDAY=6 PB_HOUR=14 mochi` (Friday sunglasses), `PB_MOOD=sleepy|pet|proud|worried mochi`, `PB_DEMO=send mochi` (the send animation, nothing sent), `PB_DEMO=social mochi` (sample badges). Quit the running Mochi first: `mochi --quit`.

The running Mochi takes commands too (the user may have bound them to keys): `mochi --message`, `--toggle`, `--todo`, `--hide`, `--quit`.

Small things don't need code: to change her color, edit `color` in `{{CONFIG}}` (or right-click her → color), then restart her (`mochi --quit; mochi`).

## Her to-do list

When the user needs to do something themselves (flip a setting, upload a file, approve something), add it to Mochi's list so she reminds them:

```bash
python3 "{{HOOKS}}/todo.py" add "Turn on blur for Mochi in Hyprland"
python3 "{{HOOKS}}/todo.py" list
python3 "{{HOOKS}}/todo.py" done 1
```

## Updating to the newest Mochi

```bash
cd "{{REPO}}" && ./install.sh --update
```

This pulls the newest version from GitHub and rebuilds, keeping the user's settings. If the user has changed Mochi's code themselves, git may refuse to pull: tell them, and offer to keep their changes (commit or stash them first).

## If something's wrong

- Messages don't arrive: check `{{LOG}}`. With tmux, Claude must be running inside tmux. Without tmux, `wtype` and `wl-clipboard` must be installed, and the compositor must be Hyprland or Sway (Mochi focuses the terminal window through it). kitty needs `allow_remote_control yes` and `listen_on unix:@kitty` in kitty.conf to be reached directly.
- She isn't floating over windows: the compositor needs wlr-layer-shell (Hyprland, Sway, KDE, niri, river…; not GNOME) and the `gtk4-layer-shell` package.
