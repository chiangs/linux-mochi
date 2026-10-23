import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_home(tmp_path, monkeypatch):
    """a throwaway $XDG_DATA_HOME, with mochi.paths pointed at it"""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    from mochi import paths
    d = tmp_path / "mochi"
    for name, f in (("DATA", ""), ("TODOS", "todos.json"), ("CONFIG", "config.json"), ("STATE", "state.json")):
        monkeypatch.setattr(paths, name, d / f if f else d)
    return d


def have_gi():
    try:
        import gi
        gi.require_version("Pango", "1.0")
        from gi.repository import Pango  # noqa: F401
        return True
    except (ImportError, ValueError):
        return False


needs_gi = pytest.mark.skipif(not have_gi(), reason="needs PyGObject with Pango")
os.environ.setdefault("PB_HOUR", "15")
