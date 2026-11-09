from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import math, re

@dataclass
class Fingerprint:
    kind: str
    dialect: str
    format: str
    confidence: float
    features: dict
    notes: list[str]

def _entropy_sample(path: Path, limit: int = 1024 * 1024):
    freq = [0] * 256; total = 0
    with path.open("rb") as f:
        while total < limit:
            b = f.read(min(1024 * 1024, limit-total))
            if not b: break
            for x in b: freq[x] += 1
            total += len(b)
    if not total: return 0.0
    return -sum((n/total)*math.log2(n/total) for n in freq if n)

def _head(path: Path, n=256):
    with path.open("rb") as f: return f.read(n)

def fingerprint(path: Path) -> Fingerprint:
    head = _head(path)
    printable = sum(32 <= x < 127 or x in (9,10,13) for x in head) / max(1,len(head))
    entropy = _entropy_sample(path)
    notes=[]; features={"entropy":round(entropy,4),"printable_head_ratio":round(printable,4)}
    if head.startswith(b"\x1bLua"):
        version = head[4]
        if version == 0x51: dialect="lua-5.1"
        elif version == 0x52: dialect="lua-5.2"
        elif version == 0x53: dialect="lua-5.3"
        elif version == 0x54: dialect="lua-5.4"
        elif version == 0x55: dialect="lua-5.5"
        else: dialect="lua-unknown"
        return Fingerprint("bytecode", dialect, "PUC-Lua", .99, features, notes)
    if head.startswith(b"\x1bLJ"):
        return Fingerprint("bytecode", "luajit", "LuaJIT", .99, features, notes)
    if head.startswith(b"Luau"):
        return Fingerprint("bytecode", "luau", "Luau", .98, features, notes)
    if head.startswith(b"\x1f\x8b"):
        return Fingerprint("container", "unknown", "GZIP", .98, features, notes)
    if head.lstrip().startswith((b"--",b"local ",b"return ",b"function ",b"do ",b"if ",b"for ",b"while ",b"repeat ")):
        return Fingerprint("source", "lua-family", "Lua source", .82, features, notes)
    if b"Lua" in head[:128]:
        notes.append("Lua marker found without canonical header")
    if entropy >= 7.4 and printable < .25:
        notes.append("high-entropy binary region")
    if b"PK\x03\x04" in head:
        return Fingerprint("container","unknown","ZIP",.98,features,notes)
    return Fingerprint("unknown","unknown","unknown",.15,features,notes)

def fingerprint_dict(fp: Fingerprint):
    return asdict(fp)
