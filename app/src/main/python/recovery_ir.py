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
    "build_cfg", "lift_to_ir", "score_candidate", "rank_candidates",
]
