"""Regression: genuine Lua 5.3 bytecode must parse and decompile.

Root cause fixed here: `decompiler53.load_proto` previously used the Lua 5.4
debug layout (1-byte line deltas + an `abslineinfo` table). Authoritative Lua
5.3 `lundump.c` stores `lineinfo` as an array of `int` (4 bytes each) and has
NO `abslineinfo` table. That mismatch made every genuine Lua 5.3 chunk fail
with "invalid absolute line count ..." so nothing standard could decompile.

These tests compile a real Lua 5.3 chunk with the system `luac5.3` and assert
that the decompiler now parses it and emits syntactically valid Lua.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.decompiler53 import decompile_file, load_chunk  # noqa: E402

LUAC = shutil.which("luac5.3") or shutil.which("luac")

pytestmark = pytest.mark.skipif(LUAC is None, reason="luac5.3 not available")

SOURCE = """
local function add(a, b)
  return a + b
end
local function greet(name)
  return "Hello, " .. name
end
local t = {1, 2, 3, x = 10}
local sum = 0
for i = 1, #t do
  sum = sum + t[i]
end
return add(2, 3), greet("World"), sum, t.x
"""


def _compile(tmp: Path) -> Path:
    src = tmp / "chunk.lua"
    out = tmp / "chunk.luac"
    src.write_text(SOURCE, encoding="utf-8")
    subprocess.run([LUAC, "-o", str(out), str(src)], check=True)
    return out


def test_standard_lua53_chunk_parses():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        luac = _compile(tmp)
        proto = load_chunk(luac.read_bytes())
        assert proto is not None
        # main chunk of the fixture has 2 nested function prototypes
        assert len(proto.protos) >= 2
        assert proto.code, "main proto must contain instructions"


def test_standard_lua53_decompile_is_syntactically_valid():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        luac = _compile(tmp)
        out = tmp / "out.lua"
        res = decompile_file(luac, out)
        assert res.get("ok") is True, res
        assert out.exists() and out.stat().st_size > 0
        # The emitted source must recompile with the same Lua 5.3 compiler.
        check = subprocess.run([LUAC, "-p", str(out)], capture_output=True, text=True)
        assert check.returncode == 0, check.stderr


def test_compile_decompile_recompile_round_trip():
    """Full round-trip: source -> compile -> decompile -> recompile."""
    from lua_engine.engine import compile_lua

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = tmp / "rt.lua"
        src.write_text(SOURCE, encoding="utf-8")
        c1 = compile_lua(src, tmp / "c1", expected_version="Lua 5.3")
        assert c1.get("ok") is True, c1
        dec = tmp / "rt.dec.lua"
        d = decompile_file(Path(c1["out"]), dec)
        assert d.get("ok") is True, d
        c2 = compile_lua(dec, tmp / "c2", expected_version="Lua 5.3")
        assert c2.get("ok") is True, c2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
