import json

from mochi import setup


def test_hooks_roundtrip(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    monkeypatch.setattr(setup, "SETTINGS", settings)
    settings.write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}],
                                                           "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command",
                                                           "command": 'python3 "/Users/me/Library/Application Support/Mochi/hooks/notify.py" --doing'}]}]}}))
    assert setup.register_hooks(tmp_path / "mochi" / "hooks" / "notify.py")
    s = json.loads(settings.read_text())
    cmds = [h["command"] for arr in s["hooks"].values() for m in arr for h in m["hooks"]]
    assert "echo mine" in cmds and not any("Application Support" in c for c in cmds)   # the macOS hook is replaced
    assert sum("notify.py" in c for c in cmds) == 6
    assert not setup.register_hooks(tmp_path / "mochi" / "hooks" / "notify.py")        # already there: nothing to change
    assert len(list(tmp_path.glob("settings.json.before-mochi-*"))) == 1
    assert setup.unregister_hooks()
    s = json.loads(settings.read_text())
    assert s == {"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}
