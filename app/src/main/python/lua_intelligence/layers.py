from __future__ import annotations
from pathlib import Path
import shutil, gzip, zipfile, hashlib

class LayerStore:
    def __init__(self, root: Path, max_artifact_bytes=256*1024*1024):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.max_artifact_bytes=max_artifact_bytes

    def copy(self, src: Path, name: str) -> Path:
        if src.stat().st_size > self.max_artifact_bytes:
            raise ValueError("artifact exceeds configured size budget")
        dst=self.root/name
        with src.open("rb") as a, dst.open("wb") as b:
            shutil.copyfileobj(a,b,1024*1024)
        return dst

    def safe_zip_extract(self, src: Path, name: str) -> list[Path]:
        dst=self.root/name; dst.mkdir(parents=True,exist_ok=True)
        out=[]
        with zipfile.ZipFile(src) as z:
            for info in z.infolist():
                n=info.filename.replace("\\","/")
                if n.startswith("/") or ".." in Path(n).parts: raise ValueError("unsafe archive path")
                target=(dst/Path(n)).resolve()
                if dst.resolve() not in target.parents and target != dst.resolve(): raise ValueError("archive traversal")
                if info.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as a, target.open("wb") as b: shutil.copyfileobj(a,b,1024*1024)
                if target.stat().st_size > self.max_artifact_bytes: raise ValueError("extracted artifact exceeds budget")
                out.append(target)
        return out

    def safe_gzip(self, src: Path, name: str) -> Path:
        dst=self.root/name
        with gzip.open(src,"rb") as a, dst.open("wb") as b: shutil.copyfileobj(a,b,1024*1024)
        if dst.stat().st_size > self.max_artifact_bytes: dst.unlink(missing_ok=True); raise ValueError("decompressed artifact exceeds budget")
        return dst
