"""Lets the suite run headless: if pynput can't import (no display), install a stub."""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import pynput.keyboard  # noqa: F401
except Exception:
    class _Key:
        left, right, up, down, shift = (object() for _ in range(5))
        f5, f6, f7, f8, f9, f10 = (object() for _ in range(6))

    kb = types.ModuleType("pynput.keyboard")
    kb.Key = _Key
    kb.Controller = lambda: None
    kb.Listener = lambda **kw: types.SimpleNamespace(start=lambda: None, stop=lambda: None)
    pn = types.ModuleType("pynput")
    pn.keyboard = kb
    sys.modules.update({"pynput": pn, "pynput.keyboard": kb})
