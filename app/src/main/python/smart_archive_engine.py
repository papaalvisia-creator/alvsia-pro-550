"""Unified Smart PAK/OBB execution facade over the retained archive providers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def execute(operation: str, input_path, output_dir, work_dir=None,
            archive_kind: str = "auto") -> dict:
    from archive_engine import (
        detect_archive, inspect_archive, extract_archive, repack_obb, repack_pak,
    )

    op = str(operation).strip().lower()
    source = Path(input_path) if input_path else None
    out = Path(output_dir)
    work = Path(work_dir) if work_dir else out.parent / "WORK"
    out.mkdir(parents=True, exist_ok=True)
    if op not in {"inspect", "extract", "rebuild", "integrity", "smart-recover"}:
        return {"ok": False, "engine": "SMART ARCHIVE", "error": "unsupported archive operation"}

    if op == "smart-recover":
        from smart_archive_lua_engine import execute as smart_recover
        return smart_recover(
            source, out, work_dir=work,
            archive_kind=archive_kind, deep_lua=True,
        )

    if op == "rebuild":
        kind = str(archive_kind).lower()
        if kind == "obb":
            candidates = (out / source.stem if source else None, work / "OBB")
            tree = next((p for p in candidates if p is not None and p.is_dir()), None)
            if tree is None:
                return {"ok": False, "engine": "SMART OBB",
                        "error": "edited OBB tree not found; extract first or place it in WORK/OBB"}
            dest = out / ((source.stem if source else "rebuilt") + "_rezip.obb")
            result = repack_obb(tree, dest)
        else:
            if source is None or not source.is_file():
                return {"ok": False, "engine": "SMART PAK", "error": "base PAK input not found"}
            candidates = (work / "MOD", out / source.stem, source.parent / "Modified_files")
            mod_dir = next((p for p in candidates if p.is_dir()), None)
            if mod_dir is None:
                return {"ok": False, "engine": "SMART PAK",
                        "error": "edited files not found; use WORK/MOD or OUT/PAK/<base-name>"}
            dest = out / (source.stem + "_repack.pak")
            result = repack_pak(source, mod_dir, dest, smart=True)
        result = dict(result or {})
        artifact = Path(str(result.get("out") or dest)) if result.get("ok") else None
        if artifact is None or not artifact.is_file() or artifact.stat().st_size <= 0:
            return {"ok": False, "engine": "SMART ARCHIVE",
                    "error": result.get("error", "rebuild did not produce a valid archive"),
                    "provider": result}
        result.update({"ok": True, "out": str(artifact), "bytes": artifact.stat().st_size,
                       "sha256": _sha256(artifact), "engine": "SMART ARCHIVE"})
        return result

    if source is None or not source.is_file():
        return {"ok": False, "engine": "SMART ARCHIVE", "error": "archive input file not found"}
    detected = detect_archive(source)
    if not detected.get("ok"):
        return {"ok": False, "engine": "SMART ARCHIVE", "error": detected.get("error", "unsupported archive")}
    fmt = detected.get("format", "")
    if archive_kind == "pak" and fmt != "tencent-pak":
        return {"ok": False, "engine": "SMART PAK", "error": "input is not detected as a Tencent PAK"}
    if archive_kind == "obb" and fmt != "obb-zip":
        return {"ok": False, "engine": "SMART OBB", "error": "input is not detected as a ZIP/OBB archive"}

    if op == "inspect":
        report_path = out / (source.name + ".info.txt")
        result = dict(inspect_archive(source, report_path) or {})
        if result.get("ok"):
            result.update({"engine": "SMART ARCHIVE", "format": fmt,
                           "out": result.get("out") or str(report_path)})
        return result

    if op == "extract":
        target = out / source.stem
        result = dict(extract_archive(source, target) or {})
        if result.get("ok"):
            result.update({"engine": "SMART ARCHIVE", "format": fmt, "out": str(target)})
        return result

    report_path = out / (source.name + ".integrity.json")
    try:
        if fmt == "tencent-pak":
            import alvsia_core as core
            report = core.run_pak_integrity_audit(source, report_path)
        else:
            from alvsia_reference_tools import audit_archive_file
            report = audit_archive_file(source)
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        if not isinstance(report, dict):
            return {"ok": False, "engine": "SMART ARCHIVE", "error": "integrity provider returned invalid report"}
        return {"ok": True, "engine": "SMART ARCHIVE", "format": fmt,
                "integrity_ok": bool(report.get("ok")), "report": report,
                "out": str(report_path) if report_path.is_file() else None}
    except Exception as exc:
        return {"ok": False, "engine": "SMART ARCHIVE",
                "error": type(exc).__name__ + ": " + str(exc)[:300]}
