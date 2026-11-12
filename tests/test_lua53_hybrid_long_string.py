#!/usr/bin/env python3
"""Regression: Lua 5.3 protected chunks with a 32-bit long-string length."""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.decompiler53 import decompile_bytes


def _header():
    return (
        b"\x1bLuaS\x00\x19\x93\x0d\x0a\x1a\x0a"
        + bytes((4, 8, 4, 8, 8))
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
    )


def _chunk(hybrid: bool) -> bytes:
    out = bytearray(_header())
    out.append(1)  # sizeupvalues
    source = b"@hybrid.lua"
    if hybrid:
        out.append(0xFF)
        out += struct.pack("<I", len(source) + 1)
        out += source
    else:
        out.append(len(source) + 1)
        out += source

    out += struct.pack("<iiBBB", 0, 0, 0, 0, 2)
    # RETURN 0 1 0
    instruction = 38 | (1 << 23)
    out += struct.pack("<I", 1)
    out += struct.pack("<I", instruction)
    out += struct.pack("<I", 0)          # constants
    out += struct.pack("<I", 1) + bytes((1, 0))  # one upvalue
    out += struct.pack("<I", 0)          # nested protos
    out += struct.pack("<I", 1) + struct.pack("<i", 1)  # lineinfo
    out += struct.pack("<I", 0)          # locvars
    name = b"_ENV"
    out += struct.pack("<I", 1) + bytes((len(name) + 1,)) + name
    return bytes(out)


def main():
    standard = decompile_bytes(_chunk(False))
    assert "return" in standard.lower(), standard

    hybrid = decompile_bytes(_chunk(True), hybrid_long_string_size=True)
    assert "return" in hybrid.lower(), hybrid

    print("LUA53 HYBRID LONG-STRING: PASS")


if __name__ == "__main__":
    main()
