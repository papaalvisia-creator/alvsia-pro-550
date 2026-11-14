"""Real native unluac-rs integration test for high-instruction Lua 5.3 chunks.

The test is enabled in Smart Lua CI after building the pinned v1.4.4 host CLI.
It compiles a real source file with luac5.3, exceeds the Python instruction
budget, then verifies that the registered native CLI returns syntax-valid Lua.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

import alvsia_features as features
from lua_engine.decompiler53 import estimate_chunk_work


def test_native_unluac_rs_decompiles_high_instruction_lua53_chunk(tmp_path):
    binary = os.environ.get("ALVSIA_UNLUAC_RS_BIN", "").strip()
    if not binary or not Path(binary).is_file():
        pytest.skip("pinned unluac-rs host CLI was not built in this environment")
    luac = shutil.which("luac5.3")
    if not luac:
        pytest.skip("luac5.3 is required for the final syntax check")

    source = tmp_path / "high-work.lua"
    chunk = tmp_path / "high-work.luac"
    output_dir = tmp_path / "out"

    # Two independent local arithmetic statements per line produce a large,
    # straight-line function without long-jump edge cases or external globals.
    body = "\n".join(["x=x+1; y=y+2"] * 220_000)
    source.write_text("local x,y=0,0\n" + body + "\nreturn x+y\n", encoding="utf-8")
    subprocess.run(
        [luac, "-o", str(chunk), str(source)],
        capture_output=True, text=True, check=True, timeout=90,
    )

    estimate = estimate_chunk_work(memoryview(chunk.read_bytes()))
    assert estimate["completed"] is True, estimate
    assert estimate["instructions"] > 400_000, estimate

    result = features.run_lua_smart(chunk, output_dir)
    assert result.get("ok") is True, result
    assert result.get("mode") == "smart_native_large_input", result
    assert result.get("selected_engine") == "unluac_rs_v1_4_4", result
    assert result.get("final_status") == "STRUCTURALLY_VALID", result
    assert result.get("validation_level") == "syntax_only", result
    assert result.get("roundtrip_proof") == "NOT_RUN", result

    recovered = Path(result["out"])
    assert recovered.is_file() and recovered.stat().st_size > 0
    check = subprocess.run(
        [luac, "-p", str(recovered)],
        capture_output=True, text=True, check=False, timeout=90,
    )
    assert check.returncode == 0, check.stderr
