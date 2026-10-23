import os
import shutil
import subprocess
import sys
import time

import pytest

from mochi import terminals


def test_is_claude():
    assert terminals.is_claude(["claude"])
    assert terminals.is_claude(["/home/me/.local/bin/claude", "--continue"])
    assert terminals.is_claude(["node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"])
    assert terminals.is_claude(["python3", "/tmp/bin/claude"])
    assert not terminals.is_claude(["vim", "claude.md"])
    assert not terminals.is_claude(["claude", "bg-spare"])


def test_tty_name():
    assert terminals.tty_name((136 << 8) | 3) == "/dev/pts/3"
    assert terminals.tty_name((137 << 8) | 1) == "/dev/pts/257"
    assert terminals.tty_name((4 << 8) | 1) == ""


def test_wtype_combo():
    assert terminals.wtype_combo("ctrl+shift+v") == ["-M", "ctrl", "-M", "shift", "v", "-m", "shift", "-m", "ctrl"]
    assert terminals.wtype_combo("super+Return") == ["-M", "logo", "-k", "return", "-m", "logo"]


def test_wake_command(monkeypatch):
    have = {"alacritty", "tmux", "kitty", "claude"}
    monkeypatch.setattr(shutil, "which", lambda n, path=None: f"/usr/bin/{n}" if n in have else None)
    monkeypatch.delenv("TERMINAL", raising=False)
    monkeypatch.setattr(terminals, "has_conversation", lambda d: True)
    cmd = terminals.wake_command({"terminal": "auto", "wake_in_tmux": True, "wake_dir": "/w"})
    assert cmd[:4] == ["alacritty", "--working-directory", "/w", "-e"] and cmd[4] == "tmux" and "--continue" in cmd[-1]
    cmd = terminals.wake_command({"terminal": "kitty", "wake_in_tmux": False, "wake_dir": "/w"})
    assert cmd == ["kitty", "--directory", "/w", "/usr/bin/claude", "--continue"]
    assert terminals.wake_command({"wake_command": "foot -e claude"}) == ["foot", "-e", "claude"]


@pytest.mark.skipif(not shutil.which("tmux"), reason="needs tmux")
def test_tmux_route(tmp_path):
    """a stand-in claude in a tmux pane gets the message, then the answer to a question"""
    fake = tmp_path / "claude"
    log = tmp_path / "got.log"
    fake.write_text(f"#!{sys.executable}\nimport sys\nfor line in sys.stdin:\n    open({str(log)!r}, 'a').write(line)\n")
    fake.chmod(0o755)
    sock = str(tmp_path / "tmux.sock")
    subprocess.run(["tmux", "-S", sock, "new-session", "-d", "-s", "t", str(fake)], check=True)
    try:
        for _ in range(50):
            s = next((s for s in terminals.sessions() if s.env.get("TMUX", "").startswith(sock)), None)
            if s: break
            time.sleep(0.1)
        assert s and s.route == "tmux"
        queue = []
        sender = terminals.Sender(None, {"send": "auto"}, lambda ms, fn: queue.append(fn))
        errs = []
        sender.send(s, "hello mochi", errs.append)
        while queue: queue.pop(0)()
        sender.answer(s, 3, "my own answer", errs.append)
        while queue: queue.pop(0)()
        time.sleep(0.5)
        assert errs == [None, None]
        assert log.read_text().splitlines() == ["hello mochi", "3my own answer"]
    finally:
        subprocess.run(["tmux", "-S", sock, "kill-server"], capture_output=True)
        if os.path.exists(sock): os.unlink(sock)


def test_asking_trust():
    assert terminals.asking_trust("Quick safety check: …\n❯ No, exit\n  Yes, I trust this folder")
    assert terminals.asking_trust("Do you trust the files in this folder?")
    assert not terminals.asking_trust("> make Mochi purple")
    assert not terminals.asking_trust(None)


def test_wake_dir_follows_last_session(data_home, monkeypatch, tmp_path):
    import json
    import time as t
    from mochi import paths
    monkeypatch.setattr(paths, "WORKING", data_home / "working.json")
    monkeypatch.setattr(paths, "LAST", data_home / "last.json")
    data_home.mkdir(parents=True, exist_ok=True)
    proj = tmp_path / "proj"; proj.mkdir()
    (data_home / "last.json").write_text(json.dumps({"cwd": str(proj), "time": t.time()}))
    (data_home / "working.json").write_text(json.dumps({"cwd": "/no/such/dir", "time": t.time() + 5}))
    assert terminals.wake_dir({"wake_dir": "last"}) == str(proj)       # newest folder that still exists
    assert terminals.wake_dir({"wake_dir": "~/code"}).endswith("/code")


def test_has_conversation(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    proj = tmp_path / ".claude" / "projects" / "-home-me-my-proj"
    proj.mkdir(parents=True)
    assert not terminals.has_conversation("/home/me/my.proj")
    (proj / "abc.jsonl").write_text("{}")
    assert terminals.has_conversation("/home/me/my.proj")
    assert not terminals.has_conversation("/home/me")


def test_wake_without_conversation_starts_fresh(monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(shutil, "which", lambda n, path=None: f"/usr/bin/{n}" if n in {"alacritty", "claude"} else None)
    monkeypatch.delenv("TERMINAL", raising=False)
    cmd = terminals.wake_command({"wake_dir": str(tmp_path), "wake_in_tmux": False})
    assert cmd[-1] == "/usr/bin/claude"          # no --continue: there's nothing to continue here
