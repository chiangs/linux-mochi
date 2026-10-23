import pytest

from mochi import todos


@pytest.mark.parametrize("msg,want", [
    ("todo: buy matcha", ("add", "buy matcha")),
    ("To-do - call mum", ("add", "call mum")),
    ("mochi add buy matcha to my to-do list", ("add", "buy matcha")),
    ("hey, please add water the plants to my todo list!", ("add", "water the plants")),
    ("put renew passport on the todo list", ("add", "renew passport")),
    ("what's on my list?", ("show", None)),
    ("todo list", ("show", None)),
    ("my todos?", None),
    ("show me my to-do list", ("show", None)),
    ("done matcha", ("done", "matcha")),
    ("check off 2", ("done", "2")),
    ("fix the failing test in bar.py", None),
    ("what's the weather", None),
])
def test_parse(msg, want):
    assert todos.parse(msg) == want


def test_find_open():
    items = [todos.new("a one"), todos.new("b two"), todos.new("c three")]
    items[0]["done"] = 1.0
    assert todos.find_open(items, "1") == 1           # numbers count open items only
    assert todos.find_open(items, "THREE") == 2
    assert todos.find_open(items, "one") is None      # already done
    assert todos.find_open(items, "9") is None


def test_save_load_and_fading(data_home):
    import time
    items = [todos.new("keep"), todos.new("old done"), todos.new("done today")]
    items[1]["done"] = time.time() - 3 * 86400
    items[2]["done"] = time.time()
    todos.save(items)
    assert [t["text"] for t in todos.load()] == ["keep", "done today"]   # checked-off things fade away the next day


def test_ago():
    import time
    assert todos.ago(time.time()) == "now"
    assert todos.ago(time.time() - 7200) == "2h"
