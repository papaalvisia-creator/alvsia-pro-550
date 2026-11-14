"""Pytest bootstrap for ALVSIA engine tests.

The production Python modules live under ``app/src/main/python`` and are
imported by the Android/Chaquopy bridge as top-level modules (e.g.
``import lua_engine``, ``import lua_intelligence``). The test-suite mirrors
that runtime by putting that directory on ``sys.path`` once, here, instead of
relying on every individual test file to do it. This keeps imports consistent
between the packaged app and the test harness.
"""
import sys
from pathlib import Path

_PY_ROOT = Path(__file__).resolve().parent / "app" / "src" / "main" / "python"
if _PY_ROOT.is_dir() and str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))
