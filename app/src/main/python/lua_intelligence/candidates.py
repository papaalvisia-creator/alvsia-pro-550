from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import math, re

_CHUNK = 256 * 1024
_LUA_TOKEN_RE = re.compile(rb"\b(?:local|function|end|if|then|for|while|return|do|repeat|until|break|else|elseif|nil|true|false)\b")
_CONTROL_RE = re.compile(rb"\b(?:function|if|for|while|repeat)\b")
_STRING_RE = re.compile(rb"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""")

@dataclass
class CandidateEvidence:
    kind: str
    score: float
    detail: str

@dataclass
class RecoveryCandidate:
    path: str
    engine: str
    dialect: str
    status: str = "PARTIAL"
    evidence: list[CandidateEvidence] = field(default_factory=list)
    score: float = 0.0

    def rank(self):
        self.score = max(0.0, min(1.0, sum(e.score for e in self.evidence)))
        return self.score

def _scan(path: Path):
    """Bounded-memory lexical scan. Never loads the whole recovered file."""
    size = path.stat().st_size
    total = tokens = controls = strings = nul = printable = 0
    paren = brace = bracket = 0
    tail = b""
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            nul += chunk.count(b"\x00")
            printable += sum(1 for b in chunk if b in (9,10,13) or 32 <= b <= 126)
            data = tail + chunk
            tokens += len(_LUA_TOKEN_RE.findall(data))
            controls += len(_CONTROL_RE.findall(data))
            strings += len(_STRING_RE.findall(data))
            paren += data.count(b"(") - data.count(b")")
            brace += data.count(b"{") - data.count(b"}")
            bracket += data.count(b"[") - data.count(b"]")
            tail = data[-128:]
    return {
        "size": size, "tokens": tokens, "controls": controls, "strings": strings,
        "nul": nul, "printable_ratio": printable / max(1, total),
        "balanced": paren == 0 and brace == 0 and bracket == 0,
        "depth_delta": (paren, brace, bracket),
    }

def score_source_candidate(path: Path, dialect="unknown", engine="unknown") -> RecoveryCandidate:
    path = Path(path)
    c = RecoveryCandidate(str(path), engine, dialect)
    try:
        s = _scan(path)
    except (OSError, ValueError) as exc:
        c.evidence.append(CandidateEvidence("io-error", 0.0, f"{type(exc).__name__}: {exc}"))
        c.status = "FAILED"
        return c

    if s["size"] == 0:
        c.evidence.append(CandidateEvidence("empty-output", 0.0, "empty candidate"))
        c.status = "FAILED"
        return c
    if s["nul"] == 0 and s["printable_ratio"] >= 0.85:
        c.evidence.append(CandidateEvidence("text-integrity", 0.12, "mostly printable text"))
    if s["tokens"]:
        c.evidence.append(CandidateEvidence("lua-grammar-tokens", min(.20, s["tokens"]/500), f"{s['tokens']} Lua-family tokens"))
    if s["balanced"]:
        c.evidence.append(CandidateEvidence("delimiter-balance", .18, "basic delimiters balanced"))
    if s["controls"]:
        c.evidence.append(CandidateEvidence("control-structure", .15, f"{s['controls']} control/function constructs"))
    if s["strings"]:
        c.evidence.append(CandidateEvidence("string-literals", min(.08, s["strings"]/250), "string literals detected"))
    if s["size"] >= 32 and s["size"] <= 256 * 1024 * 1024:
        c.evidence.append(CandidateEvidence("size-sanity", .05, "candidate is within bounded recovery size"))
    c.metadata = {"bytes": s["size"], "printable_ratio": round(s["printable_ratio"], 4),
                  "tokens": s["tokens"], "controls": s["controls"], "strings": s["strings"],
                  "balanced": s["balanced"], "depth_delta": s["depth_delta"]}
    c.rank()
    return c

def rank_candidates(candidates):
    ranked = []
    for c in candidates:
        ranked.append((c.rank(), c))
    ranked.sort(key=lambda x: (-x[0], x[1].engine, x[1].path))
    return [c for _, c in ranked]

def candidates_json(candidates):
    return [asdict(c) for c in rank_candidates(candidates)]
