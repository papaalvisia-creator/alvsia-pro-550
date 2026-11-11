from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import hashlib, json, time

STATUS = ("LOSSLESS","SEMANTIC","PARTIAL","DISASSEMBLY","STRINGS_ONLY","UNSUPPORTED","FAILED")

@dataclass
class AnalysisEvidence:
    kind: str
    value: Any
    confidence: float
    source: str = ""
    detail: str = ""

@dataclass
class LayerArtifact:
    artifact_id: str
    path: str
    sha256: str
    size: int
    parent_id: str | None
    dialect: str = "unknown"
    format: str = "unknown"
    transformation: str = "original"
    confidence: float = 0.0
    status: str = "PARTIAL"
    depth: int = 0
    evidence: list[AnalysisEvidence] = field(default_factory=list)
    children: list[str] = field(default_factory=list)

@dataclass
class AnalysisResult:
    ok: bool
    status: str
    root_id: str
    artifacts: list[LayerArtifact]
    report_path: str | None = None
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "ok": self.ok, "status": self.status, "root_id": self.root_id,
            "artifacts": [asdict(a) for a in self.artifacts],
            "report_path": self.report_path, "errors": self.errors,
            "metrics": self.metrics,
        }

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    h = hashlib.sha256(); size = 0
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b: break
            h.update(b); size += len(b)
    return h.hexdigest(), size

def write_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
