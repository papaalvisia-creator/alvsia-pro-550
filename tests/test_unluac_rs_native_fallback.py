"""Real native unluac-rs integration test for high-instruction Lua 5.3 chunks.

The test is enabled in Smart Lua CI after building the pinned v1.4.4 host CLI.
It deliberately exceeds the Python instruction budget so the app must route to
the same native CLI registered by Android's PythonBridgeRunner.
"""
import os
import shutil
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

import alvsia_features as features
from lua_engine.decompiler53 import estimate_chunk_work


def _large_valid_lua53_chunk(instruction_count: int) -> bytes:
    header = (
        b"\x1bLua"
        + bytes([0x53, 0x00])
        + b"\x19\x93\x0d\x0a\x1a\x0a"
        + bytes([4, 4, 4, 8, 8])
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
        + bytes([1])
    )
    out = bytearray(header)
    out += b"\x00"                 # source = NULL
    out += struct.pack("<ii", 0, 0)
    out += bytes([0, 0, 2])         # params, vararg, maxstack
    out += struct.pack("<i", instruction_count)
    out += b"\x00\x00\x00\x00" * (instruction_count - 1)  # MOVE R0,R0
    out += struct.pack("<I", 38 | (1 << 23))                # RETURN R0, zero values
    out += struct.pack("<i", 0)  # constants
    out += struct.pack("<i", 0)  # upvalues
    out += struct.pack("<i", 0)  # nested protos
    out += struct.pack("<i", 0)  # lineinfo
    out += struct.pack("<i", 0)  # local variables
    out += struct.pack("<i", 0)  # upvalue names
    return bytes(out)


def test_native_unluac_rs_decompiles_high_instruction_lua53_chunk(tmp_path):
    binary = os.environ.get("ALVSIA_UNLUAC_RS_BIN", "").strip()
    if not binary or not Path(binary).is_file():
        pytest.skip("pinned unluac-rs host CLI was not built in this environment")
    luac = shutil.which("luac5.3")
    if not luac:
        pytest.skip("luac5.3 is required for the final syntax check")

    source = tmp_path / "high-work.luac"
    output_dir = tmp_path / "out"
    source.write_bytes(_large_valid_lua53_chunk(450_001))

    estimate = estimate_chunk_work(memoryview(source.read_bytes()))
    assert estimate["completed"] is True, estimate
    assert estimate["instructions"] > 400_000, estimate

    result = features.run_lua_smart(source, output_dir)
    assert result.get("ok") is True, result
    assert result.get("mode") == "smart_native_large_input", result
    assert result.get("selected_engine") == "unluac_rs_v1_4_4", result
    assert result.get("final_status") == "STRUCTURALLY_VALID", result
    assert result.get("validation_level") == "syntax_only", result
    assert result.get("roundtrip_proof") == "NOT_RUN", result

    recovered = Path(result["out"])
    assert recovered.is_file() and recovered.stat().st_size > 0
    check = __import__("subprocess").run(
        [luac, "-p", str(recovered)], capture_output=True, text=True, check=False
    )
    assert check.returncode == 0, check.stderr
