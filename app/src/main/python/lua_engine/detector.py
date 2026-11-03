from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import re
from .container import unwrap_lua_container

LUA_VERSIONS = {0x51: "5.1", 0x52: "5.2", 0x53: "5.3", 0x54: "5.4"}

@dataclass(frozen=True)
class LuaInfo:
    kind: str
    version: str | None
    format: str
    size: int
    magic: str
    confidence: float
    notes: tuple[str, ...] = ()
    wrapped: bool = False
    container: str = "none"
    container_chunks: int = 0

    def to_dict(self):
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


def _find_comment_prefixed_magic(data: bytes):
    """Return (offset, format, version) only for comment/shebang-only prefixes."""
    candidates = []
    for marker, fmt in ((b"\x1bLua", "luac"), (b"\x1bLJ", "luajit")):
        offset = data.find(marker, 1, min(len(data), 65536))
        if offset > 0:
            candidates.append((offset, fmt))
    for offset, fmt in sorted(candidates):
        try:
            prefix = data[:offset].decode("utf-8")
        except UnicodeDecodeError:
            continue
        lines = prefix.splitlines()
        if not lines or not all(
            not line.strip() or line.lstrip().startswith(("--", "#!"))
            for line in lines
        ):
            continue
        if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in prefix):
            continue
        version = data[offset + 4] if fmt == "luac" and len(data) > offset + 4 else None
        return offset, fmt, version
    return None


def detect_bytes(data: bytes) -> LuaInfo:
    size = len(data)
    magic = data[:8].hex()
    if data.startswith(b"\x1bLJ"):
        ver = "LuaJIT 2.0/2.1"
        if len(data) >= 3 and data[2] == 2:
            ver = "LuaJIT 2.1"
        return LuaInfo("bytecode", ver, "luajit", size, magic, 0.99)
    if data.startswith(b"\x1bLua"):
        vb = data[4] if len(data) > 4 else 0
        version = LUA_VERSIONS.get(vb)
        if version:
            return LuaInfo("bytecode", f"Lua {version}", "luac", size, magic, 0.99)
        return LuaInfo("bytecode", None, "luac-unknown", size, magic, 0.90,
                       ("Lua magic present but version byte is unknown",))
    embedded = _find_comment_prefixed_magic(data)
    if embedded:
        offset, fmt, version_byte = embedded
        if fmt == "luajit":
            return LuaInfo("bytecode", "LuaJIT 2.0/2.1", "luajit", size, magic, 0.94,
                           (f"comment_prefix_offset={offset}", "embedded LuaJIT bytecode"))
        version = LUA_VERSIONS.get(version_byte)
        if version:
            return LuaInfo("bytecode", f"Lua {version}", "luac", size, magic, 0.94,
                           (f"comment_prefix_offset={offset}", "embedded Lua bytecode"))
        return LuaInfo("bytecode", None, "luac-unknown", size, magic, 0.85,
                       (f"comment_prefix_offset={offset}", "embedded Lua magic with unknown version"))
    head = data[:8192].decode("utf-8", "ignore")
    stripped = head.lstrip("\ufeff \t\r\n")
    if re.search(r"^(?:#!.*\n\s*)?(?:local|return|function|if|for|while|repeat|do)\b", stripped):
        return LuaInfo("source", None, "lua-source", size, magic, 0.85)
    # Short scripts commonly begin with a call or assignment rather than
    # a block keyword. Require a printable prefix to avoid binary false hits.
    printable = all(b in (9, 10, 13) or 32 <= b < 127 for b in data[:4096])
    if printable and re.search(
        r"^(?:#!.*\\n\\s*)?(?:[A-Za-z_][A-Za-z0-9_.]*\\s*\\(|"
        r"[A-Za-z_][A-Za-z0-9_]*\\s*=|--)",
        stripped,
    ):
        return LuaInfo("source", None, "lua-source", size, magic, 0.78)
    if b"function" in data[:4096] and all((b in (9,10,13) or 32 <= b < 127) for b in data[:4096]):
        return LuaInfo("source", None, "lua-source", size, magic, 0.70)
    return LuaInfo("unknown", None, "unknown", size, magic, 0.0)


def detect_lua(path) -> LuaInfo:
    p = Path(path)
    data = p.read_bytes()
    info = detect_bytes(data)
    # Accept any valid zlib header: CMF=0x78 with FLG such that (CMF*256+FLG)%31==0
    # (78 01, 78 5E, 78 9C, 78 DA are the common ones at various compression levels).
    def _is_zlib_header(d: bytes) -> bool:
        return len(d) >= 2 and d[0] == 0x78 and (d[0] * 256 + d[1]) % 31 == 0

    if info.kind != "unknown" or not _is_zlib_header(data):
        return info
    try:
        payload, ci = unwrap_lua_container(data)
        inner = detect_bytes(payload)
        return LuaInfo(inner.kind, inner.version, inner.format, len(data), data[:8].hex(),
                       min(0.98, inner.confidence),
                       tuple(ci.notes) + tuple(inner.notes), True, ci.format, ci.chunks)
    except Exception as exc:
        return LuaInfo("unknown", None, "container-unknown", len(data), data[:8].hex(), 0.10,
                       (f"container detection failed: {exc}",), True, "unknown", 0)
