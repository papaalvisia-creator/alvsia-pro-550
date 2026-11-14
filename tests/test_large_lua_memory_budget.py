#!/usr/bin/env python3
"""Regression tests for bounded-memory handling of large Lua 5.3 bytecode.

A real-world protected chunk (~22.7 MB) declared >900k instructions and drove
the pure-Python in-memory decompiler past several GB of RAM, OOM-killing the
host. These tests lock in the fix:

* ``estimate_chunk_work`` walks a chunk without materialising instruction
  lists (O(1) extra memory) and reports the declared work.
* ``run_lua_smart`` routes a chunk whose declared instruction count exceeds
  the safe budget to the bounded streaming path and returns an honest
  PARTIAL status instead of attempting an unbounded in-memory decompile.
* A small, normal chunk still takes the in-memory path (no regression).
"""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.decompiler53 import estimate_chunk_work, load_chunk
import alvsia_features as features


def _luac_header() -> bytes:
    return (
        b"\x1bLua"
        + bytes([0x53, 0x00])          # version 5.3, format 0
        + b"\x19\x93\x0d\x0a\x1a\x0a"  # LUAC_DATA
        + bytes([4, 4, 4, 8, 8])       # int, size_t, Instruction, Integer, Number
        + struct.pack("<q", 0x5678)    # LUAC_INT
        + struct.pack("<d", 370.5)     # LUAC_NUM
        + bytes([1])                   # main upvalue count
    )


def _single_proto_chunk(instruction_count: int) -> bytes:
    """Build a syntactically valid Lua 5.3 chunk with one flat prototype."""
    out = bytearray(_luac_header())
    out += bytes([0])                          # source = NULL
    out += struct.pack("<ii", 0, 0)            # linedefined, lastlinedefined
    out += bytes([0, 0, 2])                    # numparams, is_vararg, maxstacksize
    out += struct.pack("<i", instruction_count)
    out += b"\x00\x00\x00\x00" * instruction_count  # NOP instructions
    out += struct.pack("<i", 0)                # constants
    out += struct.pack("<i", 0)                # upvalues
    out += struct.pack("<i", 0)                # nested protos
    out += struct.pack("<i", 0)                # lineinfo
    out += struct.pack("<i", 0)                # locvars
    out += struct.pack("<i", 0)                # upvalue names
    return bytes(out)


def test_estimator_reports_declared_work_without_allocating():
    chunk = _single_proto_chunk(450_000)
    est = estimate_chunk_work(chunk)
    assert est["completed"] is True, est
    assert est["instructions"] == 450_000, est
    assert est["protos"] == 1, est
    # The estimator must not need a per-instruction list: bytes consumed equals
    # the whole chunk, and the input itself is the only large object.
    assert est["bytes_consumed"] == len(chunk), est


def test_estimator_matches_real_parser_on_small_chunk():
    chunk = _single_proto_chunk(12)
    est = estimate_chunk_work(chunk)
    proto = load_chunk(chunk)
    assert est["completed"] is True, est
    assert est["instructions"] == len(proto.code) == 12, est
    assert est["constants"] == len(proto.constants), est


def test_estimator_never_raises_on_truncated_input():
    chunk = _single_proto_chunk(50)[:-8]
    est = estimate_chunk_work(chunk)
    assert est["completed"] is False, est
    assert est["error"], est


def test_large_declared_work_routes_to_bounded_streaming_path():
    chunk = _single_proto_chunk(450_000)  # > 400k instruction budget, > 256 KB
    with tempfile.TemporaryDirectory(prefix="alvsia-budget-") as td:
        root = Path(td)
        src = root / "big.luac"
        src.write_bytes(chunk)
        # Pre-flight gate must flag this as over budget.
        assert features._lua_work_exceeds_budget(src, src.stat().st_size) is True

        out = root / "out"
        result = features.run_lua_smart(src, out)
        assert result.get("mode") == "smart_streaming_large_input", result
        assert result.get("final_status") == "PARTIAL", result
        assert result.get("ok") is False, result


def test_small_chunk_stays_on_in_memory_path():
    # A tiny valid chunk must not be diverted by the work-budget gate.
    with tempfile.TemporaryDirectory(prefix="alvsia-small-") as td:
        root = Path(td)
        src = root / "small.luac"
        src.write_bytes(_single_proto_chunk(8))
        assert features._lua_work_exceeds_budget(src, src.stat().st_size) is False


def test_partial_recovery_is_classified_as_partial_not_failed():
    # A bounded streaming recovery returns ok=False but final_status=PARTIAL
    # with diagnostic artifacts. It must count as PARTIAL, never FAILED.
    from smart_archive_lua_engine import _fallback_recovery_status
    assert _fallback_recovery_status(
        {"ok": False, "final_status": "PARTIAL", "streaming_recovery": {"ok": True}}
    ) == "PARTIAL"
    assert _fallback_recovery_status({"ok": False, "partial_recovery": {"x": 1}}) == "PARTIAL"
    assert _fallback_recovery_status({"ok": False, "final_status": "FAILED"}) == "FAILED"
    assert _fallback_recovery_status({"ok": False, "error": "boom"}) == "FAILED"
    assert _fallback_recovery_status(None) == "FAILED"


if __name__ == "__main__":
    test_estimator_reports_declared_work_without_allocating()
    test_estimator_matches_real_parser_on_small_chunk()
    test_estimator_never_raises_on_truncated_input()
    test_large_declared_work_routes_to_bounded_streaming_path()
    test_small_chunk_stays_on_in_memory_path()
    test_partial_recovery_is_classified_as_partial_not_failed()
    print("LARGE LUA MEMORY BUDGET: PASS")
