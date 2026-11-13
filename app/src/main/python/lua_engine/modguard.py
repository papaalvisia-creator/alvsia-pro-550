# -*- coding: utf-8 -*-
"""Mod-guard: structural sanitizer for protected mod-tool Lua 5.3 chunks.

Protected mod producers (GOKU-style "anti-decompile fortress" writers) append
to every prototype two dead JMP instructions after the real RETURN, and append
a plain-text banner comment after the main chunk:

    [... real code ..., RETURN(38), JMP(30, sBx=-10), JMP(30, sBx=+50)]

The dead pair is never executed (it sits after an unconditional RETURN) but it
breaks every standard Lua 5.3 loader and decompiler, which require a function
to end with RETURN. The banner bytes after the main chunk break strict
"chunk must end exactly at EOF" validation.

This module:
  1. detects that exact structural signature (bounded scan, no execution),
  2. rewrites each dead JMP pair's final instruction into a RETURN(A=0, B=1)
     so the chunk ends with a real RETURN while keeping every instruction
     offset, jump target and section size identical (no reflow, no target
     invalidation),
  3. splits the appended banner into a separate report field.

Fail-closed: anything that does not match the signature byte-for-byte is left
untouched and reported as not-applicable. The transform never executes the
input and never weakens validation of the remaining chunk structure.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Dict, Optional, Tuple

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_DEPTH = 200
MAX_PROTOS = 100_000

_LUA53_SIG = b"\x1bLua\x53"
_JMP_OP = 30
_RETURN_OP = 38
# Dead-tail signature: [RETURN(38), JMP30(sBx=-10), JMP30(sBx=+50)]
_TAIL_BACK = -10
_TAIL_FWD = 50
_RETURN_NOP = _RETURN_OP | (1 << 22)  # RETURN A=0 B=1 -> 'return'


class _Reader:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 33  # standard 33-byte Lua 5.3 header (LUAC_NUM double)

    def read(self, n: int) -> bytes:
        if n < 0 or self.p + n > len(self.d):
            raise ValueError("truncated chunk at offset %d" % self.p)
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def u8(self) -> int:
        return self.read(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.read(8))[0]

    def string(self) -> Optional[bytes]:
        size = self.u8()
        if size == 0xFF:
            size = self.u32()
        if size == 0:
            return None
        if size > len(self.d) - self.p + 1:
            raise ValueError("string length exceeds input at offset %d" % self.p)
        return self.read(size - 1)


def _sbx(word: int) -> int:
    return ((word >> 14) & 0x3FFFF) - 131071


def detect_mod_guard(data: bytes) -> Optional[Dict]:
    """Return a detection report when the protected-mod signature is present."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 64:
        return None
    data = bytes(data)
    if len(data) > MAX_INPUT_BYTES:
        return None
    if not data.startswith(_LUA53_SIG) or data[5] != 0:
        return None
    if data[6:12] != b"\x19\x93\x0d\x0a\x1a\x0a":
        return None
    if data[12:17] != b"\x04\x04\x04\x08\x08":
        return None
    if data[17:25] != b"\x78\x56\x00\x00\x00\x00\x00\x00":
        return None
    if struct.unpack("<d", data[25:33])[0] != 370.5:
        return None
    r = _Reader(data)
    tail_protos = 0
    total_protos = 0
    chunk_end = None
    try:
        r.u8()  # main closure upvalue count
        chunk_end = _walk_for_tail(r, 0, [0])
        total_protos = [0]
        _count_protos(data, total_protos)
        tail_protos = _count_tails(data)
    except Exception:
        return None
    if chunk_end is None:
        return None
    trailing = len(data) - chunk_end
    if trailing <= 0 and tail_protos == 0:
        return None
    banner = data[chunk_end:] if trailing > 0 else b""
    return {
        "detected": True,
        "chunk_end": chunk_end,
        "trailing_bytes": trailing,
        "banner_bytes": trailing,
        "banner_sha256": hashlib.sha256(banner).hexdigest() if banner else "",
        "banner_preview": banner[:120] if banner else b"",
        "dead_tail_protos": tail_protos,
        "total_protos": total_protos[0] if isinstance(total_protos, list) else 0,
    }


def _count_protos(data: bytes, out: list) -> None:
    r = _Reader(data)
    r.u8()
    _walk(r, 0, out)


def _count_tails(data: bytes) -> int:
    """Count protos whose final two instructions are the dead JMP pair."""
    import io
    count = 0
    # Reuse the walker but only count; bounded by MAX_PROTOS.
    state = {"tails": 0}
    r = _Reader(data)
    r.u8()
    _walk_tails(r, 0, state)
    return state["tails"]


def _walk_tails(r: _Reader, depth: int, state: dict) -> None:
    if depth > MAX_DEPTH:
        raise ValueError("proto nesting exceeds limit")
    r.string()
    r.i32(); r.i32()
    r.u8(); r.u8(); r.u8()
    n = r.u32()
    if n == 0 or n > len(r.d):
        raise ValueError("bad code count")
    code_pos = r.p
    code = r.read(n * 4)
    if n >= 3:
        w3 = struct.unpack_from("<I", code, (n - 3) * 4)[0]
        w2 = struct.unpack_from("<I", code, (n - 2) * 4)[0]
        w1 = struct.unpack_from("<I", code, (n - 1) * 4)[0]
        if ((w3 & 0x3F) == _RETURN_OP and (w2 & 0x3F) == _JMP_OP
                and _sbx(w2) == _TAIL_BACK and (w1 & 0x3F) == _JMP_OP
                and _sbx(w1) == _TAIL_FWD):
            state["tails"] += 1
    nc = r.u32()
    if nc > len(r.d) - r.p:
        raise ValueError("bad constant count")
    for _ in range(nc):
        t = r.u8()
        if t == 0:
            continue
        elif t == 1:
            r.u8()
        elif t == 3:
            r.f64()
        elif t == 19:
            r.i64()
        elif t in (4, 20):
            r.string()
        else:
            raise ValueError("unknown constant tag %d" % t)
    nu = r.u32()
    if nu > (len(r.d) - r.p) // 2:
        raise ValueError("bad upvalue count")
    for _ in range(nu):
        r.u8(); r.u8()
    npt = r.u32()
    if npt > MAX_PROTOS:
        raise ValueError("proto count exceeds limit")
    for _ in range(npt):
        _walk_tails(r, depth + 1, state)
    nl = r.u32()
    if nl > len(r.d) - r.p:
        raise ValueError("bad lineinfo count")
    r.read(nl)
    na = r.u32()
    if na > (len(r.d) - r.p) // 8:
        raise ValueError("bad abslineinfo count")
    r.read(na * 8)
    nloc = r.u32()
    if nloc > (len(r.d) - r.p) // 9:
        raise ValueError("bad local count")
    for _ in range(nloc):
        r.string(); r.i32(); r.i32()
    nun = r.u32()
    if nun > len(r.d) - r.p:
        raise ValueError("bad upvalue-name count")
    for _ in range(nun):
        r.string()


def _walk(r: _Reader, depth: int, out: list) -> int:
    """Walk protos; return the main chunk end offset (after top-level proto)."""
    if depth > MAX_DEPTH:
        raise ValueError("proto nesting exceeds limit")
    r.string()
    r.i32(); r.i32()
    r.u8(); r.u8(); r.u8()
    n = r.u32()
    if n == 0 or n > len(r.d):
        raise ValueError("bad code count")
    r.read(n * 4)
    nc = r.u32()
    if nc > len(r.d) - r.p:
        raise ValueError("bad constant count")
    for _ in range(nc):
        t = r.u8()
        if t == 0:
            continue
        elif t == 1:
            r.u8()
        elif t == 3:
            r.f64()
        elif t == 19:
            r.i64()
        elif t in (4, 20):
            r.string()
        else:
            raise ValueError("unknown constant tag %d" % t)
    nu = r.u32()
    if nu > (len(r.d) - r.p) // 2:
        raise ValueError("bad upvalue count")
    for _ in range(nu):
        r.u8(); r.u8()
    npt = r.u32()
    if npt > MAX_PROTOS:
        raise ValueError("proto count exceeds limit")
    for _ in range(npt):
        _walk(r, depth + 1, out)
    nl = r.u32()
    if nl > len(r.d) - r.p:
        raise ValueError("bad lineinfo count")
    r.read(nl)
    na = r.u32()
    if na > (len(r.d) - r.p) // 8:
        raise ValueError("bad abslineinfo count")
    r.read(na * 8)
    nloc = r.u32()
    if nloc > (len(r.d) - r.p) // 9:
        raise ValueError("bad local count")
    for _ in range(nloc):
        r.string(); r.i32(); r.i32()
    nun = r.u32()
    if nun > len(r.d) - r.p:
        raise ValueError("bad upvalue-name count")
    for _ in range(nun):
        r.string()
    return r.p


def _walk_for_tail(r: _Reader, depth: int, out: list) -> Optional[int]:
    out[0] += 1
    if out[0] > MAX_PROTOS:
        raise ValueError("proto count exceeds limit")
    r.string()
    r.i32(); r.i32()
    r.u8(); r.u8(); r.u8()
    n = r.u32()
    if n == 0 or n > len(r.d):
        raise ValueError("bad code count")
    r.read(n * 4)
    nc = r.u32()
    if nc > len(r.d) - r.p:
        raise ValueError("bad constant count")
    for _ in range(nc):
        t = r.u8()
        if t == 0:
            continue
        elif t == 1:
            r.u8()
        elif t == 3:
            r.f64()
        elif t == 19:
            r.i64()
        elif t in (4, 20):
            r.string()
        else:
            raise ValueError("unknown constant tag %d" % t)
    nu = r.u32()
    if nu > (len(r.d) - r.p) // 2:
        raise ValueError("bad upvalue count")
    for _ in range(nu):
        r.u8(); r.u8()
    npt = r.u32()
    if npt > MAX_PROTOS:
        raise ValueError("proto count exceeds limit")
    for _ in range(npt):
        _walk_for_tail(r, depth + 1, out)
    nl = r.u32()
    if nl > len(r.d) - r.p:
        raise ValueError("bad lineinfo count")
    r.read(nl)
    na = r.u32()
    if na > (len(r.d) - r.p) // 8:
        raise ValueError("bad abslineinfo count")
    r.read(na * 8)
    nloc = r.u32()
    if nloc > (len(r.d) - r.p) // 9:
        raise ValueError("bad local count")
    for _ in range(nloc):
        r.string(); r.i32(); r.i32()
    nun = r.u32()
    if nun > len(r.d) - r.p:
        raise ValueError("bad upvalue-name count")
    for _ in range(nun):
        r.string()
    return r.p


def sanitize_mod_guard(data: bytes) -> Tuple[bytes, Dict]:
    """Patch the dead JMP tails and split the banner.

    Returns (clean_bytes, report). The clean chunk keeps every instruction
    offset and section size identical except the final dead JMP word of each
    tail, which becomes RETURN(A=0, B=1).
    """
    report = detect_mod_guard(data)
    if not report or not report.get("detected"):
        return bytes(data), {"applied": False, "reason": "signature not present"}
    clean = bytearray(data[:report["chunk_end"]])
    r = _Reader(bytes(clean))
    r.u8()
    patched = {"tails": 0}
    _patch_tails(r, 0, clean, patched)
    out = bytes(clean)
    report2 = {
        "applied": True,
        "patched_protos": patched["tails"],
        "chunk_bytes": len(out),
        "banner_bytes": report["trailing_bytes"],
        "banner_sha256": report["banner_sha256"],
        "banner_preview": report["banner_preview"],
    }
    return out, report2


def _patch_tails(r: _Reader, depth: int, buf: bytearray, state: dict) -> None:
    if depth > MAX_DEPTH:
        raise ValueError("proto nesting exceeds limit")
    r.string()
    r.i32(); r.i32()
    r.u8(); r.u8(); r.u8()
    n = r.u32()
    if n == 0 or n > len(buf):
        raise ValueError("bad code count")
    code_pos = r.p
    code = r.read(n * 4)
    if n >= 3:
        w3 = struct.unpack_from("<I", code, (n - 3) * 4)[0]
        w2 = struct.unpack_from("<I", code, (n - 2) * 4)[0]
        w1 = struct.unpack_from("<I", code, (n - 1) * 4)[0]
        if ((w3 & 0x3F) == _RETURN_OP and (w2 & 0x3F) == _JMP_OP
                and _sbx(w2) == _TAIL_BACK and (w1 & 0x3F) == _JMP_OP
                and _sbx(w1) == _TAIL_FWD):
            struct.pack_into("<I", buf, code_pos + (n - 1) * 4, _RETURN_NOP)
            state["tails"] += 1
    nc = r.u32()
    if nc > len(buf) - r.p:
        raise ValueError("bad constant count")
    for _ in range(nc):
        t = r.u8()
        if t == 0:
            continue
        elif t == 1:
            r.u8()
        elif t == 3:
            r.f64()
        elif t == 19:
            r.i64()
        elif t in (4, 20):
            r.string()
        else:
            raise ValueError("unknown constant tag %d" % t)
    nu = r.u32()
    if nu > (len(buf) - r.p) // 2:
        raise ValueError("bad upvalue count")
    for _ in range(nu):
        r.u8(); r.u8()
    npt = r.u32()
    if npt > MAX_PROTOS:
        raise ValueError("proto count exceeds limit")
    for _ in range(npt):
        _patch_tails(r, depth + 1, buf, state)
    nl = r.u32()
    if nl > len(buf) - r.p:
        raise ValueError("bad lineinfo count")
    r.read(nl)
    na = r.u32()
    if na > (len(buf) - r.p) // 8:
        raise ValueError("bad abslineinfo count")
    r.read(na * 8)
    nloc = r.u32()
    if nloc > (len(buf) - r.p) // 9:
        raise ValueError("bad local count")
    for _ in range(nloc):
        r.string(); r.i32(); r.i32()
    nun = r.u32()
    if nun > len(buf) - r.p:
        raise ValueError("bad upvalue-name count")
    for _ in range(nun):
        r.string()
