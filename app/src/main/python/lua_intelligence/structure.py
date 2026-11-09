from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class BytecodeStructure:
    dialect: str
    valid_header: bool
    header_size: int
    size: int
    sections: tuple[str,...]
    anomalies: tuple[str,...]
    score: float

def analyze_bytecode_structure(path: Path, dialect="unknown") -> BytecodeStructure:
    path=Path(path); size=path.stat().st_size
    with path.open("rb") as f: head=f.read(64)
    sections=[]; anomalies=[]; valid=False; header_size=0
    if head.startswith(b"\x1bLua"):
        valid=True; header_size=12; sections.append("puc-lua-header")
        if len(head)<12: anomalies.append("truncated-header")
        if len(head)>=6 and head[5] not in (0,1): anomalies.append("unexpected-format-byte")
    elif head.startswith(b"\x1bLJ"):
        valid=True; header_size=3; sections.append("luajit-header")
    elif head.startswith(b"Luau"):
        valid=True; header_size=4; sections.append("luau-header")
    else:
        anomalies.append("canonical-bytecode-header-missing")
    if size < header_size: anomalies.append("file-shorter-than-header")
    score=0.0 if not valid else max(0.0,min(1.0,.95-.08*len(anomalies)))
    return BytecodeStructure(dialect,valid,header_size,size,tuple(sections),tuple(anomalies),score)

def structure_dict(s): return asdict(s)
