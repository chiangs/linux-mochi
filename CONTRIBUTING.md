# Working on Mochi

## How it fits together

```
Claude Code ──hooks──▶ hooks/notify.py ──writes──▶ ~/.local/share/mochi/*.json ──polled every 0.7 s──▶ Mochi (mochi/bar.py)
                                                                                                         │
Mochi ──terminals.Sender──▶ tmux / kitty / wezterm / (compositor focus + wtype paste) ──▶ Claude Code ◀──┘
```

- **The hook** (`hooks/notify.py`) runs on Claude Code's `UserPromptSubmit`, `PreToolUse`, `PostToolUse` and `Stop` events and writes `working.json`, `doing.json`, `progress.json`, `question.json` and `last.json`. It has no dependencies beyond Python.
- **The app** (`mochi/`) is Python + GTK4. Every window is a wlr-layer-shell overlay (`layer.py`) anchored to the bottom of one output, placed by its margins. The pill is drawn by hand with Cairo (`bar.py: draw_pill`, `goo.py`, `parts.py`), in **y-up** coordinates like the original AppKit views, so the pixel art ports one-to-one. The pop-ups are GTK widgets styled by `ui.py`.
- **Sending** (`terminals.py`) finds every `claude` process through `/proc`, reads its environment to see where it runs, and picks a route per session.
- **The compositor** (`compositor.py`) covers what Wayland doesn't let apps do: the global cursor position, listing and focusing windows. Hyprland and Sway are implemented.

The macOS original is in `macos/`. The Python mirrors its structure and comments, which helps when porting new upstream features.

## Running from the checkout

```bash
python3 -m mochi          # quit the installed one first (right-click → Quit)
python3 -m pytest -q      # tests (some need tmux, PyGObject)
ruff check .
```

Test switches: `PB_HOUR`, `PB_WEEKDAY` (1 = Sunday … 6 = Friday), `PB_MOOD=sleepy|pet|proud|worried`, `PB_DEMO=send|social`, `PB_SCREEN=<monitor index>`.

## Adding a terminal

If the terminal has a way to send text to a pane from outside (like kitty's `kitten @` or `wezterm cli`):

1. Add its environment variable to `ENV_KEYS` in `terminals.py`, so sessions remember it.
2. Teach `Session.route` to pick it.
3. Handle the route in `Sender.send`, `Sender.answer` and `Sender.press_return`.
4. If it needs special arguments to open a new window, add them to `wake_command`.

Terminals without such an interface already work through the paste route. If yours uses a different paste shortcut, set `paste_keys`.

## Adding a compositor

Subclass `Generic` in `compositor.py` and implement `windows()`, `active()`, `focus()` (needed for the paste route), plus `cursor()` (eyes following the pointer everywhere) and `focused_monitor()` / `reserved()` where possible. Then detect it in `detect()`.

## Social badges

The badge drawing and site definitions are in `parts.py` (`SOCIAL_SITES`). No source ships on Linux yet. The macOS version read Chrome tab titles over AppleScript. A Linux source could read Chromium's DevTools endpoint (`--remote-debugging-port`, `/json` lists tab titles) or use a small browser extension. It goes in `Bar.check_social()` / `Bar.open_social()`.
