#!/usr/bin/env python3
"""Smart Data facade smoke test for the authoritative SM4 registry."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "app/src/main/python"
sys.path.insert(0, str(PYTHON_ROOT))

from smart_data_engine import execute

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    sample = root / "libfixture.bin"
    synthetic_key = "aA0bB1cC2dD3eE4fF5gG"
    sample.write_bytes(b"\x00" * 41 + synthetic_key.encode("ascii") + b"\x00" * 32)
    result = execute("sm4", sample, root / "OUT", work_dir=root / "WORK")
    assert result.get("ok"), result
    assert result.get("counts", {}).get("SM4_SECRET_NEW") == 1, result
    output = Path(result["out"])
    assert synthetic_key in output.read_text(encoding="utf-8")

print("SMART DATA ENGINE: PASS (SM4 registry routed through .bin scanner)")
