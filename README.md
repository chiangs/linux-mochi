<p align="center"><img src="assets/icon.png" width="160" alt="Mochi"></p>

<h1 align="center">Mochi</h1>
<p align="center"><b>A tiny pixel goo who lives at the bottom of your screen and talks to Claude Code for you.</b></p>

---

Mochi floats over everything on your Mac. Click her, type, and your message goes straight to **Claude Code** running in Terminal. When Claude answers, she pops the reply up in a little bubble. She shows what Claude is doing while it works, answers its multiple-choice questions for you, and keeps a tiny to-do list of things Claude needs *you* to do.

She also breathes, blinks, follows your cursor, hops when you send something, gets sleepy when it's quiet, and dresses for the time of day.

## What she does

- 💬 **Message Claude from anywhere.** No need to find the Terminal window.
- 🫧 **Reply bubbles.** A short summary of Claude's answer pops up above her; long replies page with the arrow keys.
- 👀 **Live progress.** A one-line "doing…" status and a little time/token meter while Claude works.
- ❓ **Answers questions.** When Claude asks you to pick an option, pick it right from Mochi.
- ✅ **To-do list.** Claude can add things you need to do yourself; Mochi reminds you.
- 🎨 **Any color you like.** Pick one when you install, or right-click her → *Change Mochi's Color…*

## Install

You need a Mac (macOS 13 or newer) and [Claude Code](https://docs.claude.com/en/docs/claude-code) installed.

Open **Terminal** and run:

```bash
git clone https://github.com/jessawolfe/mochi.git
cd mochi
./install.sh
```

No git? Click the green **Code** button above → **Download ZIP**, unzip it, then in Terminal `cd` into the folder and run `./install.sh`.

The installer will:

1. Ask **what color you want Mochi to be** 🎨
2. Build her (takes about 30 seconds) and put her in `~/Applications`
3. Connect her to Claude Code by adding a few hooks to `~/.claude/settings.json` (your old settings are backed up first)

### Permissions

The first time Mochi sends a message, macOS will ask to let her control **Terminal**: say OK. She also needs **Accessibility** to type into Terminal: *System Settings → Privacy & Security → Accessibility → turn on Mochi*.

## Using her

| | |
|---|---|
| **Click** | Open her message bar, type, press Return |
| **Drag** | Move her anywhere along the bottom of the screen |
| **Right-click** | Her menu: change color, open at login, quit |
| **Hover** | She'll wiggle. Keep hovering and she gets petted 💗 |

If no Terminal tab is running Claude, she opens one with `claude --continue` and sends your message there.

## Make her yours

Mochi is one Swift file, `Sources/Mochi.swift`, so she's easy to remix: her outfits, moods, colors and animations are all in there. Change anything, then run `./install.sh` again to rebuild.

The hook script, `hooks/notify.py`, is what tells Mochi what Claude is doing. It writes small JSON files into `~/Library/Application Support/Mochi/`, which she watches.

Add to-dos from the command line (or let Claude do it):

```bash
python3 ~/Library/Application\ Support/Mochi/hooks/todo.py add "Upload the new images"
```

## Uninstall

```bash
./uninstall.sh
```

This removes the app, her data and her Claude Code hooks.

---

<p align="center">Made with 🫧 by <a href="https://jessa.art">Jessa Wolfe</a>.</p>
