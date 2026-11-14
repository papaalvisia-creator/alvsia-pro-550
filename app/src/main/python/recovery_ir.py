"""Evidence-driven recovery IR helpers.

This module is deliberately format-neutral: it does not execute recovered code
and never invents source. It provides the shared intermediate representation
needed by Lua/PAK/OBB/APK recovery adapters and deterministic candidate ranking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class IRInstruction:
    pc: int
    opcode: str
    operands: tuple[Any, ...] = ()
    source_ref: str | None = None


@dataclass
class IRBlock:
    block_id: int
    start_pc: int
    instructions: list[IRInstruction] = field(default_factory=list)
    successors: list[int] = field(default_factory=list)


@dataclass
class RecoveryIR:
    domain: str
    instructions: list[IRInstruction]
    blocks: list[IRBlock]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "instruction_count": len(self.instructions),
            "block_count": len(self.blocks),
            "instructions": [
                {"pc": i.pc, "opcode": i.opcode, "operands": list(i.operands),
                 **({"source_ref": i.source_ref} if i.source_ref else {})}
                for i in self.instructions
            ],
            "blocks": [
                {"block_id": b.block_id, "start_pc": b.start_pc,
                 "instruction_count": len(b.instructions),
                 "successors": list(b.successors)}
                for b in self.blocks
            ],
            "metadata": dict(self.metadata),
        }


def normalize_instructions(records: Iterable[Mapping[str, Any]]) -> list[IRInstruction]:
    """Normalize parser output while rejecting malformed PCs/opcodes."""
    out: list[IRInstruction] = []
    for record in records:
        try:
            pc = int(record["pc"])
            opcode = str(record["opcode"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if pc < 0 or not opcode:
            continue
        operands = record.get("operands", ())
        if isinstance(operands, (str, bytes)):
            operands = (operands,)
        elif not isinstance(operands, Sequence):
            operands = (operands,)
        out.append(IRInstruction(pc, opcode, tuple(operands),
                                 str(record["source_ref"]) if record.get("source_ref") else None))
    return sorted(out, key=lambda item: item.pc)


def build_cfg(instructions: Sequence[IRInstruction],
              branch_targets: Mapping[int, Sequence[int]] | None = None) -> list[IRBlock]:
    """Build conservative basic blocks from instruction PCs and known targets.

    Unknown control flow is left as fall-through; no guessed target is created.
    """
    if not instructions:
        return []
    by_pc = {i.pc: i for i in instructions}
    pcs = [i.pc for i in instructions]
    starts = {pcs[0]}
    targets = branch_targets or {}
    for src, dsts in targets.items():
        if src in by_pc:
            starts.update(dst for dst in dsts if dst in by_pc)
            nxt = next((p for p in pcs if p > src), None)
            if nxt is not None:
                starts.add(nxt)
    ordered_starts = sorted(starts)
    blocks: list[IRBlock] = []
    for idx, start in enumerate(ordered_starts):
        end = ordered_starts[idx + 1] if idx + 1 < len(ordered_starts) else None
        members = [i for i in instructions if i.pc >= start and (end is None or i.pc < end)]
        if members:
            blocks.append(IRBlock(idx, start, members))
    index = {b.start_pc: b.block_id for b in blocks}
    for block in blocks:
        last = block.instructions[-1]
        explicit = [index[t] for t in targets.get(last.pc, ()) if t in index]
        if explicit:
            block.successors = sorted(set(explicit))
        else:
            next_block = block.block_id + 1
            if next_block < len(blocks):
                block.successors = [next_block]
    return blocks


def lift_to_ir(records: Iterable[Mapping[str, Any]], *,
               domain: str = "generic",
               branch_targets: Mapping[int, Sequence[int]] | None = None,
               metadata: Mapping[str, Any] | None = None) -> RecoveryIR:
    instructions = normalize_instructions(records)
    blocks = build_cfg(instructions, branch_targets)
    return RecoveryIR(domain=str(domain), instructions=instructions, blocks=blocks,
                      metadata=dict(metadata or {}))


def score_candidate(candidate: Mapping[str, Any]) -> float:
    """Score only supplied evidence; missing evidence never receives a bonus."""
    score = 0.0
    weights = {
        "source_valid": 0.30,
        "roundtrip_valid": 0.25,
        "cfg_valid": 0.15,
        "instruction_coverage": 0.15,
        "constant_coverage": 0.10,
        "independent_agreement": 0.05,
    }
    for key, weight in weights.items():
        value = candidate.get(key)
        if isinstance(value, bool):
            score += weight if value else 0.0
        elif isinstance(value, (int, float)):
            score += weight * max(0.0, min(1.0, float(value)))
    return round(score, 6)


def rank_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for idx, candidate in enumerate(candidates):
        item = dict(candidate)
        item["score"] = score_candidate(item)
        item["_input_order"] = idx
        ranked.append(item)
    ranked.sort(key=lambda item: (-item["score"], item["_input_order"]))
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
        item.pop("_input_order", None)
    return ranked


__all__ = [
    "IRInstruction", "IRBlock", "RecoveryIR", "normalize_instructions",
    "build_cfg", "lift_to_ir", "build_ssa", "score_candidate", "rank_candidates",
]



def build_ssa(instructions: Sequence[IRInstruction]) -> list[dict[str, Any]]:
    """Build conservative register-version data flow from recovered instructions.

    This is intentionally not a full language-semantic SSA solver. It versions
    register writes and records reads as they appear in the verified instruction
    stream; unknown aliases and control-flow merges are left explicit.
    """
    versions: dict[int, int] = {}
    out: list[dict[str, Any]] = []
    writes = {
        "MOVE", "LOADK", "LOADKX", "LOADBOOL", "LOADNIL", "GETUPVAL",
        "GETTABUP", "GETTABLE", "NEWTABLE", "SELF", "ADD", "SUB", "MUL",
        "MOD", "POW", "DIV", "IDIV", "BAND", "BOR", "BXOR", "SHL", "SHR",
        "UNM", "BNOT", "NOT", "LEN", "CONCAT", "CALL", "TAILCALL",
        "TFORCALL", "CLOSURE", "VARARG",
    }
    for ins in instructions:
        operands = list(ins.operands)
        a = int(operands[0]) if operands and isinstance(operands[0], int) else None
        reads = []
        if ins.opcode in {"MOVE", "GETTABLE", "SETTABLE", "ADD", "SUB", "MUL", "MOD", "POW", "DIV", "IDIV", "BAND", "BOR", "BXOR", "SHL", "SHR", "EQ", "LT", "LE", "TEST", "TESTSET"}:
            for value in operands[1:3]:
                if isinstance(value, int) and 0 <= value < 256:
                    reads.append({"register": value, "version": versions.get(value, 0)})
        write = None
        if a is not None and ins.opcode in writes:
            versions[a] = versions.get(a, 0) + 1
            write = {"register": a, "version": versions[a]}
        out.append({"pc": ins.pc, "opcode": ins.opcode, "reads": reads, "write": write})
    return out

def analyze_lua_bytecode(path: str, *, deadline_seconds: float = 8.0) -> dict:
    """Lift a standard Lua 5.3 chunk into shared IR without executing it."""
    import time
    from pathlib import Path
    try:
        from lua_engine.decompiler53 import load_chunk, decode, OP
        raw = Path(path).read_bytes()
        proto = load_chunk(raw, deadline=time.monotonic() + float(deadline_seconds))
        records = []
        def visit(p, prefix="main"):
            for pc, ins in enumerate(p.code):
                op, a, b, c, bx, sbx = decode(ins)
                operands = (a, b, c, bx, sbx)
                records.append({"pc": pc, "opcode": OP[op] if 0 <= op < len(OP) else f"OP_{op}",
                                "operands": operands, "source_ref": prefix})
            for idx, child in enumerate(p.protos):
                visit(child, f"{prefix}.proto{idx}")
        visit(proto)
        # Conservative branch targets: only direct sBx jumps/loops are lifted.
        targets = {}
        for row in records:
            op = row["opcode"]
            if op in {"JMP", "FORLOOP", "FORPREP", "TFORLOOP"}:
                sbx = int(row["operands"][-1])
                targets.setdefault(int(row["pc"]), []).append(int(row["pc"]) + 1 + sbx)
        ir = lift_to_ir(records, domain="lua", branch_targets=targets,
                        metadata={"format": "Lua 5.3", "prototype_count": 1 + len(proto.protos)})
        return {"ok": True, "format": "Lua 5.3", "ir": ir.to_dict(),
                "instruction_count": len(ir.instructions), "block_count": len(ir.blocks)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
