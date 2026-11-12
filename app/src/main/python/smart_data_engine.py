"""Unified Smart Data transform and recovery engine."""
from __future__ import annotations

import hashlib
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def execute(operation: str, input_path, output_dir, work_dir=None) -> dict:
    op = str(operation).strip().lower()
    source = Path(input_path) if input_path else None
    out = Path(output_dir)
    work = Path(work_dir) if work_dir else out.parent / "WORK"
    out.mkdir(parents=True, exist_ok=True)
    if source is None or not source.exists():
        return {"ok": False, "engine": "SMART DATA", "error": "input file or folder not found"}

    if op == "recover":
        if not source.is_file():
            return {"ok": False, "engine": "SMART DATA", "error": "recovery input must be a file"}
        import alvsia_ultimate as ultimate
        result = ultimate.decrypt_auto(str(source), out, str(work))
        return dict(result or {}, engine="SMART DATA", operation=op)

    if op == "xor":
        if not source.is_file():
            return {"ok": False, "engine": "SMART DATA", "error": "XOR input must be a file"}
        import alvsia_ultimate as ultimate
        result = ultimate.xor_single_byte_scan(str(source), out)
        return dict(result or {}, engine="SMART DATA", operation=op)

    if op == "sm4":
        from alvsia_features import SM4AllKeyFinder
        folder = source if source.is_dir() else source.parent
        finder = SM4AllKeyFinder(str(folder))
        hits = finder.find_all_keys()
        report_path = out / "sm4_all_keys.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        counts = {}
        for family in ("SM4_SECRET_NEW", "SM4_SECRET_4", "SM4_SECRET_2"):
            values = hits.get(family, [])
            counts[family] = len(values)
            lines.extend("%s 0x%08X %s" % (family, offset, key) for offset, key in values)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return {
            "ok": True, "engine": "SMART DATA", "operation": op,
            "counts": counts, "total_candidates": sum(counts.values()),
            "out": str(report_path), "bytes": report_path.stat().st_size,
            "sha256": _sha256(report_path),
        }

    if op == "metadata":
        if not source.is_file():
            return {"ok": False, "engine": "SMART DATA", "error": "metadata input must be a file"}
        from alvsia_metadata import decode_metadata_v39_file
        digest = _sha256(source)[:12]
        target = out / (source.stem + "_decoded_" + digest + ".dat")
        target.parent.mkdir(parents=True, exist_ok=True)
        report = decode_metadata_v39_file(source, target)
        report_path = target.with_suffix(target.suffix + ".json")
        import json
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        valid = target.is_file() and target.stat().st_size > 0 and bool(report.get("ok"))
        return {
            "ok": valid, "engine": "SMART DATA", "operation": op,
            "out": str(target) if valid else None, "report": str(report_path),
            "details": report,
            "error": None if valid else "metadata decode or section validation failed",
        }

    return {"ok": False, "engine": "SMART DATA", "error": "unsupported Smart Data operation"}
