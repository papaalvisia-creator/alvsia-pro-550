"""E2E PAK -> Lua verification harness (test-only).

Runs the real smart_archive_lua_engine pipeline on a real Tencent PAK.
The production authorization gate is asserted to reject a marker-only
session, then bypassed in-process (same pattern as
tests/test_pak_extraction.py) so the extraction/recovery pipeline can be
exercised without a live server-signed grant. This does NOT modify any
production source file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"
sys.path.insert(0, str(PY_ROOT))

import alvsia_core as core  # noqa: E402


def _assert_gate_rejects_marker_only() -> bool:
    os.environ["ALVSIA_APK_SESSION"] = "1"
    os.environ.pop("ALVSIA_SESSION_TOKEN", None)
    core._alvsia_clear_operation_proof()
    try:
        core._alvsia_require_operation(("pak.unpack",))
    except RuntimeError as exc:
        return "Operation authorization failed" in str(exc)
    return False


def main() -> int:
    pak = sys.argv[1] if len(sys.argv) > 1 else "/workspace/corpus/samples/pak/game_patch_4.7.0.21752.pak"
    out = sys.argv[2] if len(sys.argv) > 2 else "/workspace/e2e_out"
    kind = sys.argv[3] if len(sys.argv) > 3 else "pak"

    gate_ok = _assert_gate_rejects_marker_only()
    print(f"[gate] marker-only session rejected: {gate_ok}")

    # Test-only isolation of the pipeline from the production grant gate.
    core._alvsia_require_operation = lambda _allowed: True

    from smart_archive_lua_engine import execute  # noqa: E402

    report = execute(pak, out, archive_kind=kind)
    summary = {
        "ok": report.get("ok"),
        "format": report.get("format"),
        "scan": report.get("scan"),
        "recovery": report.get("recovery"),
        "extract_ok": report.get("extract", {}).get("ok"),
        "report": report.get("report"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
