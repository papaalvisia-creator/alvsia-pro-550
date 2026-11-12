#!/usr/bin/env python3
"""End-to-end Smart OBB facade fixture tests."""
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))
from smart_archive_engine import execute

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    source = root / "sample.obb"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("assets/config.txt", "version=1\n")

    out = root / "OUT" / "OBB"
    work = root / "WORK"
    inspected = execute("inspect", source, out, work_dir=work, archive_kind="obb")
    assert inspected.get("ok"), inspected

    extracted = execute("extract", source, out, work_dir=work, archive_kind="obb")
    assert extracted.get("ok"), extracted
    tree = out / source.stem
    config = tree / "assets" / "config.txt"
    assert config.read_text(encoding="utf-8") == "version=1\n"
    config.write_text("version=2\n", encoding="utf-8")

    rebuilt = execute("rebuild", source, out, work_dir=work, archive_kind="obb")
    assert rebuilt.get("ok"), rebuilt
    rebuilt_path = Path(rebuilt["out"])
    assert rebuilt_path.is_file() and rebuilt_path.stat().st_size > 0

    integrity = execute("integrity", rebuilt_path, out, work_dir=work, archive_kind="obb")
    assert integrity.get("ok"), integrity
    assert integrity.get("integrity_ok"), integrity
    with zipfile.ZipFile(rebuilt_path, "r") as archive:
        assert archive.read("assets/config.txt") == b"version=2\n"

print("SMART OBB ENGINE: PASS (inspect, safe extract, rebuild, integrity)")
