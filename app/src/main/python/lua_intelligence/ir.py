from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable
import json, re

@dataclass
class IRInstruction:
    opcode: str
    operands: tuple[Any,...] = ()
    offset: int | None = None
    source_line: int | None = None
    confidence: float = 1.0
    evidence: tuple[str,...] = ()

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
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(self.to_dict(),ensure_ascii=False,indent=2),encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str,Any]):
        funcs=[]
        for f in data.get("functions",[]):
            funcs.append(IRFunction(
                function_id=str(f.get("function_id","")),
                name_hint=f.get("name_hint"),
                params=f.get("params"),
                vararg=f.get("vararg"),
                instructions=[IRInstruction(
                    opcode=str(i.get("opcode","unknown")),
                    operands=tuple(i.get("operands",[])),
                    offset=i.get("offset"), source_line=i.get("source_line"),
                    confidence=float(i.get("confidence",1.0)),
                    evidence=tuple(i.get("evidence",[])))
                    for i in f.get("instructions",[])],
                constants=list(f.get("constants",[])),
                upvalues=list(f.get("upvalues",[])),
                children=list(f.get("children",[]))))
        return cls(schema=str(data.get("schema","alvsia-program-ir-v1")),
                   dialect=str(data.get("dialect","unknown")),
                   source_artifact=str(data.get("source_artifact","")),
                   functions=funcs, globals=list(data.get("globals",[])),
                   metadata=dict(data.get("metadata",{})))

@dataclass(frozen=True)
class IRValidation:
    valid: bool
    score: float
    errors: tuple[str,...] = ()
    warnings: tuple[str,...] = ()

def validate_ir(program: ProgramIR) -> IRValidation:
    errors=[]; warnings=[]
    if program.schema != "alvsia-program-ir-v1": errors.append("unsupported IR schema")
    ids=[f.function_id for f in program.functions]
    if len(ids)!=len(set(ids)): errors.append("duplicate function ids")
    known=set(ids)
    for f in program.functions:
        for child in f.children:
            if child not in known: warnings.append(f"unresolved child: {child}")
        for ins in f.instructions:
            if not ins.opcode: errors.append(f"empty opcode in {f.function_id}")
            if not 0 <= ins.confidence <= 1: errors.append(f"invalid instruction confidence: {f.function_id}")
    score=1.0
    score-=min(.8,.25*len(errors))
    score-=min(.4,.05*len(warnings))
    return IRValidation(not errors,max(0.0,score),tuple(errors),tuple(warnings))

def ir_from_source(path: Path, dialect="lua-family", artifact_id="") -> ProgramIR:
    """Conservative source adapter. It records structural facts, never invents bytecode."""
    path=Path(path); data=path.read_bytes()
    text=data.decode("utf-8","replace")
    p=ProgramIR(dialect=dialect,source_artifact=artifact_id,
                metadata={"adapter":"source-structural-v1","bytes":len(data)})
    function_re=re.compile(r"\bfunction\s+([A-Za-z_][\w.]*)\s*\(([^)]*)\)")
    for n,(name,args) in enumerate(function_re.findall(text)):
        params=[x.strip() for x in args.split(",") if x.strip()]
        p.functions.append(IRFunction(function_id=f"fn-{n}",name_hint=name,params=len(params),
                                       vararg="..." in params,
                                       instructions=[IRInstruction("SOURCE_FUNCTION", (name,), evidence=("source-function",))]))
    return p

def ir_from_bytecode_header(path: Path, dialect: str, artifact_id="") -> ProgramIR:
    """Header-level adapter; bytecode instructions are intentionally unknown until a dialect decoder proves them."""
    path=Path(path)
    size=path.stat().st_size
    p=ProgramIR(dialect=dialect,source_artifact=artifact_id,
                metadata={"adapter":"bytecode-header-v1","bytes":size,"instruction_decode":"not-attempted"})
    p.functions.append(IRFunction("root",instructions=[IRInstruction("BYTECODE_MODULE",(dialect,),confidence=.55,evidence=("canonical-header",))]))
    return p
