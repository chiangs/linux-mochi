---
name: mochi
description: Change, customize or update Mochi, the little pixel goo app on this Mac that talks to Claude Code. Use when the user asks to change how Mochi looks or behaves (color, outfits, moods, animations, size, sounds), add something to Mochi's to-do list, update Mochi, or fix something about Mochi.
---

# Mochi

Mochi is a small macOS app: a pixel goo that floats at the bottom of the screen, sends the user's messages to Claude Code in Terminal, and shows Claude's replies, questions, progress and a to-do list.

## Where things are

- **Her code:** `{{REPO}}/Sources/Mochi.swift` (one Swift file, AppKit). The goo character is the `Goo` class (shape, eyes, moods, outfits by time of day); the floating bar is the main app delegate.
- **The installer / rebuilder:** `{{REPO}}/install.sh`
- **Her settings:** `{{DATA}}/config.json`, for example `{"color": "#33c7ff", "social": ["ig", "th"]}`. `social` takes any of `ig`, `th`, `li`, `x`.
- **What Claude Code tells her:** the hooks in `~/.claude/settings.json` run `{{DATA}}/hooks/notify.py`, which writes `last.json`, `working.json`, `doing.json`, `progress.json` and `question.json` into `{{DATA}}`. She polls those files.
- **Her log:** `~/Library/Logs/Mochi.log`

## Changing Mochi

1. Edit `{{REPO}}/Sources/Mochi.swift`. Keep her pixel-art style (chunky 2 px cells, about 12 frames a second).
2. Rebuild and relaunch her with:

   ```bash
   cd "{{REPO}}" && ./install.sh --rebuild
   ```

   This keeps the user's answers, builds, signs her with the local "Mochi Local Signing" certificate (so macOS keeps her permissions), installs her to `~/Applications/Mochi.app` and relaunches her. If the build fails, read the error, fix the Swift and run it again.
3. **Never** run `tccutil reset` and never sign her ad-hoc on purpose: that makes macOS forget her Terminal and Accessibility permissions.

Small things don't need code: to change her color, edit `color` in `config.json` (or the user can right-click her → *Change Mochi's Color…*), then rebuild.

## Her to-do list

When the user needs to do something themselves (flip a setting, upload a file, approve a permission), add it to Mochi's list so she reminds them:

```bash
python3 "{{DATA}}/hooks/todo.py" add "Turn on Accessibility for Mochi"
python3 "{{DATA}}/hooks/todo.py" list
python3 "{{DATA}}/hooks/todo.py" done 1
```

## Updating to the newest Mochi

```bash
cd "{{REPO}}" && ./install.sh --update
```

This pulls the newest version from GitHub and rebuilds, keeping the user's settings. If the user has changed `Mochi.swift` themselves, git may refuse to pull: tell them, and offer to keep their changes (commit or stash them first).

## If something's wrong

- She doesn't paste into Terminal: check System Settings → Privacy & Security → Accessibility and Automation for Mochi.
- No social badges: the sites have to be open in Chrome tabs (pinned tabs are best), and `social` has to list them in `config.json`.
- Check `~/Library/Logs/Mochi.log`.
