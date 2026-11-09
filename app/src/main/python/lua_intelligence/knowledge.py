from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json

@dataclass(frozen=True)
class KnowledgeEntry:
    key: str
    category: str
    detector: str
    dialects: tuple[str,...] = ()
    evidence: tuple[str,...] = ()
    version: str = "1"

class KnowledgeRegistry:
    """Versioned local registry. Entries are descriptive; no third-party code is copied."""
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.entries: dict[str, KnowledgeEntry] = {}
        self._seed()

    def _seed(self):
        seeds = [
            ("puc-lua","dialect","canonical Lua bytecode headers",("lua-5.1","lua-5.2","lua-5.3","lua-5.4","lua-5.5")),
            ("luajit","dialect","LuaJIT bytecode marker",("luajit",)),
            ("luau","dialect","Luau bytecode marker",("luau",)),
            ("high-entropy","fingerprint","entropy requires corroborating structural evidence",()),
            ("layer-hash-cycle","safety","SHA-256 cycle detection",()),
            ("semantic-unknown","policy","never invent stripped identifiers or semantics",()),
        ]
        for key,cat,det,dial in seeds:
            self.entries[key]=KnowledgeEntry(key,cat,det,dial)

    def add(self, entry: KnowledgeEntry):
        self.entries[entry.key]=entry

    def export(self):
        return {"schema":"alvsia-knowledge-v1","entries":[asdict(x) for x in self.entries.values()]}

    def save(self, path: Path | None = None):
        p=Path(path or self.path) if (path or self.path) else None
        if not p: raise ValueError("registry path required")
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(self.export(),ensure_ascii=False,indent=2),encoding="utf-8")
