import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"


def run(flag, payload, data):
    env = dict(os.environ, XDG_DATA_HOME=str(data))
    args = [sys.executable, str(HOOKS / "notify.py")] + ([flag] if flag else [])
    subprocess.run(args, input=json.dumps(payload), text=True, env=env, check=True)


def test_turn(tmp_path):
    d = tmp_path / "mochi"
    tr = tmp_path / "t.jsonl"
    lines = [
        {"type": "user", "message": {"content": "hi"}},
        {"type": "assistant", "message": {"id": "m1", "usage": {"output_tokens": 40}, "content": [{"type": "text", "text": "Working on **it**."}]}},
        {"type": "assistant", "message": {"id": "m2", "usage": {"output_tokens": 2}, "content": [{"type": "tool_use", "name": "Read"}]}},
    ]
    tr.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    base = {"cwd": "/home/me/proj", "transcript_path": str(tr)}
    run("--working", base, tmp_path)
    assert json.loads((d / "working.json").read_text())["project"] == "proj"
    run("--doing", dict(base, tool_name="Edit", tool_input={"file_path": "/x/bar.py"}), tmp_path)
    assert json.loads((d / "doing.json").read_text())["text"] == "Editing bar.py"
    run("--progress", base, tmp_path)
    p = json.loads((d / "progress.json").read_text())
    assert p["tokens"] == 42 and p["text"] == "Working on it."
    run("--question", dict(base, tool_input={"questions": [{"question": "Pick?", "options": [{"label": "A"}]}]}, tool_use_id="t1"), tmp_path)
    q = json.loads((d / "question.json").read_text())
    assert q["id"] == "t1" and "pid" in q and "tty" in q
    run("--answered", base, tmp_path)
    assert not (d / "question.json").exists()
    run(None, dict(base, last_assistant_message="## Done\n\nI fixed the **bug** in `bar.py`. It works now.\n\n```py\nx = 1\n```"), tmp_path)
    last = json.loads((d / "last.json").read_text())
    assert last["text"] == "Done I fixed the bug in bar.py. It works now."
    assert "[code]" in last["full"] and not (d / "progress.json").exists()


def test_todo_cli(tmp_path):
    env = dict(os.environ, XDG_DATA_HOME=str(tmp_path))
    todo = [sys.executable, str(HOOKS / "todo.py")]
    subprocess.run(todo + ["add", "Upload the images"], env=env, check=True, capture_output=True)
    subprocess.run(todo + ["add", "Rename the folder"], env=env, check=True, capture_output=True)
    out = subprocess.run(todo + ["done", "rename"], env=env, check=True, capture_output=True, text=True).stdout
    assert "Rename the folder" in out
    out = subprocess.run(todo + ["list"], env=env, check=True, capture_output=True, text=True).stdout
    assert out.strip() == "1. Upload the images"
