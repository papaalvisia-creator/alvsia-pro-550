from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import json, time, hashlib
from .model import LayerArtifact, AnalysisEvidence, AnalysisResult, sha256_file, write_json
from .fingerprint import fingerprint
from .knowledge import KnowledgeRegistry

@dataclass
class IntelligenceConfig:
    max_depth: int = 12
    max_artifacts: int = 128
    max_file_bytes: int = 256*1024*1024
    max_elapsed_seconds: float = 45.0
    sample_bytes: int = 1024*1024

class IntelligenceEngine:
    """Recursive static program-analysis coordinator.

    It never executes an unknown input. Transform adapters are opt-in and must
    create a new file-backed artifact; every artifact is content-addressed.
    """
    def __init__(self, config: IntelligenceConfig | None=None, registry: KnowledgeRegistry | None=None):
        self.config=config or IntelligenceConfig()
        self.registry=registry or KnowledgeRegistry()

    def analyze(self, input_path: Path, out_dir: Path) -> AnalysisResult:
        started=time.monotonic(); input_path=Path(input_path); out_dir=Path(out_dir)
        out_dir.mkdir(parents=True,exist_ok=True)
        errors=[]; artifacts=[]; seen=set(); queue=[]
        if not input_path.is_file(): return AnalysisResult(False,"FAILED","",[],errors=["input is not a file"])
        if input_path.stat().st_size > self.config.max_file_bytes:
            return AnalysisResult(False,"UNSUPPORTED","",[],errors=["input exceeds configured size budget"])
        sha,size=sha256_file(input_path)
        root_id="a-"+sha[:20]
        queue.append((input_path,None,0,"original"))
        while queue and len(artifacts)<self.config.max_artifacts and time.monotonic()-started < self.config.max_elapsed_seconds:
            path,parent,depth,transform=queue.pop(0)
            fp=fingerprint(path)
            digest,size=sha256_file(path)
            if digest in seen: continue
            seen.add(digest)
            status="PARTIAL" if fp.kind in ("source","bytecode","container") else "UNSUPPORTED"
            conf=fp.confidence
            evidence=[AnalysisEvidence("fingerprint",fp.format,conf,"builtin",",".join(fp.notes))]
            art=LayerArtifact(
                artifact_id="a-"+digest[:20], path=str(path), sha256=digest, size=size,
                parent_id=parent, dialect=fp.dialect, format=fp.format,
                transformation=transform, confidence=conf, status=status, depth=depth,
                evidence=evidence)
            artifacts.append(art)
            if parent:
                for p in artifacts:
                    if p.artifact_id==parent and art.artifact_id not in p.children: p.children.append(art.artifact_id)
            # Conservative recursive recovery adapters. Each transform is file-backed,
            # deterministic, bounded, and immediately re-fingerprinted on the next queue pass.
            if depth < self.config.max_depth and fp.format in ("ZIP", "GZIP"):
                try:
                    from .layers import LayerStore
                    store=LayerStore(out_dir/"layers",self.config.max_file_bytes)
                    if fp.format=="ZIP":
                        children=store.safe_zip_extract(path,"zip-"+digest[:12])
                        for child in children[:32]:
                            if child.is_file() and child.stat().st_size<=self.config.max_file_bytes:
                                queue.append((child,art.artifact_id,depth+1,"zip-extract"))
                    else:
                        child=store.safe_gzip(path,"gzip-"+digest[:12])
                        if child.is_file() and child.stat().st_size<=self.config.max_file_bytes:
                            queue.append((child,art.artifact_id,depth+1,"gzip-decompress"))
                except Exception as exc:
                    errors.append(f"{fp.format.lower()} expansion: {type(exc).__name__}: {exc}")
        elapsed=time.monotonic()-started
        if queue: errors.append("analysis budget reached before queue exhaustion")
        report=out_dir/(input_path.stem+"_intelligence.json")
        result=AnalysisResult(True, "PARTIAL" if artifacts else "FAILED", root_id, artifacts, str(report), errors,
                             {"elapsed_seconds":round(elapsed,3),"artifact_count":len(artifacts),
                              "unique_hashes":len(seen),"budget":{"max_depth":self.config.max_depth,
                              "max_artifacts":self.config.max_artifacts,"max_file_bytes":self.config.max_file_bytes}})
        write_json(report,result.to_dict())
        return result

def analyze_file(input_path, out_dir, config=None):
    return IntelligenceEngine(config).analyze(Path(input_path),Path(out_dir))
