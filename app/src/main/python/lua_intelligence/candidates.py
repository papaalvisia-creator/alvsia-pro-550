from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import hashlib, math, re

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
        self.score=max(0.0,min(1.0,sum(e.score for e in self.evidence)))
        return self.score

def score_source_candidate(path: Path, dialect="unknown", engine="unknown") -> RecoveryCandidate:
    data=path.read_bytes()
    text=data.decode("utf-8","replace")
    evidence=[]
    if text.count("\x00")==0:
        evidence.append(CandidateEvidence("text-integrity",0.12,"UTF-8-compatible output"))
    tokens=len(re.findall(r"\b(local|function|end|if|then|for|while|return|do)\b",text))
    if tokens:
        evidence.append(CandidateEvidence("lua-grammar-tokens",min(.20,tokens/500),"Lua-family syntax tokens present"))
    balanced=sum(text.count(x) for x in ("(","{","["))-sum(text.count(x) for x in (")","}","]"))
    if balanced==0:
        evidence.append(CandidateEvidence("delimiter-balance",.18,"basic delimiters balanced"))
    if re.search(r"\b(function|local|return|if|for|while|repeat)\b",text):
        evidence.append(CandidateEvidence("control-structure",.15,"control/function syntax detected"))
    if len(text)>0 and len(data)<max(1,len(text)*4):
        evidence.append(CandidateEvidence("expansion-sanity",.10,"reasonable text expansion"))
    return RecoveryCandidate(str(path),engine,dialect,evidence=evidence)

def rank_candidates(candidates):
    ranked=[]
    for c in candidates: ranked.append((c.rank(),c))
    ranked.sort(key=lambda x:x[0],reverse=True)
    return [c for _,c in ranked]

def candidates_json(candidates):
    return [asdict(c) for c in rank_candidates(candidates)]
