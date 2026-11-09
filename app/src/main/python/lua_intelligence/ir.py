from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import json

@dataclass
class IRInstruction:
    opcode: str
    operands: tuple[Any,...] = ()
    offset: int | None = None
    source_line: int | None = None

@dataclass
class IRFunction:
    function_id: str
    name_hint: str | None = None
    params: int | None = None
    vararg: bool | None = None
    instructions: list[IRInstruction] = field(default_factory=list)
    constants: list[Any] = field(default_factory=list)
    upvalues: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)

@dataclass
class ProgramIR:
    schema: str = "alvsia-program-ir-v1"
    dialect: str = "unknown"
    source_artifact: str = ""
    functions: list[IRFunction] = field(default_factory=list)
    globals: list[str] = field(default_factory=list)
    metadata: dict[str,Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    def write(self, path):
        path.write_text(json.dumps(self.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")
