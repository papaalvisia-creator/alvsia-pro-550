"""Universal Smart Archive -> Lua recovery pipeline.

Smart PAK and Smart OBB share one bounded pipeline:
detect -> extract -> enumerate -> identify Lua -> recover/decompile -> validate -> report.
Existing archive and Lua providers remain adapters; no provider is deleted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MAX_ARCHIVE_FILES = 50_000
MAX_LUA_CANDIDATES = 20_000


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]


def _candidate_probe(path: Path) -> dict[str, Any]:
    from smart_pak_lua_engine import _probe_lua
    return _probe_lua(path)


def execute(input_path, output_dir, work_dir=None, archive_kind="auto",
            deep_lua=True) -> dict[str, Any]:
    source = Path(input_path)
    out = Path(output_dir)
    work = Path(work_dir) if work_dir else out.parent / "WORK"
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    if not source.is_file():
        return {"ok": False, "engine": "SMART ARCHIVE/LUA", "error": "input archive not found"}

    from archive_engine import detect_archive, extract_archive
    detected = detect_archive(source)
    if not detected.get("ok"):
        return {"ok": False, "engine": "SMART ARCHIVE/LUA", "stage": "detect",
                "error": detected.get("error", "unsupported archive"), "detect": detected}

    fmt = detected.get("format")
    if archive_kind not in ("auto", fmt):
        expected = "tencent-pak" if archive_kind == "pak" else "obb-zip"
        return {"ok": False, "engine": "SMART " + archive_kind.upper(),
                "stage": "detect", "error": f"expected {expected}, detected {fmt}"}

    extracted_root = out / ("PAK" if fmt == "tencent-pak" else "OBB")
    extracted = extract_archive(source, extracted_root)
    if not extracted.get("ok"):
        return {"ok": False, "engine": "SMART ARCHIVE/LUA", "stage": "extract",
                "error": extracted.get("error", "archive extraction failed"),
                "detect": detected, "extract": extracted}

    files = sorted(p for p in extracted_root.rglob("*") if p.is_file())
    if len(files) > MAX_ARCHIVE_FILES:
        return {"ok": False, "engine": "SMART ARCHIVE/LUA", "stage": "scan",
                "error": "archive file count exceeds safety limit", "files": len(files)}

    probes = {str(p): _candidate_probe(p) for p in files}
    candidates = [p for p in files if probes[str(p)].get("candidate")]
    if len(candidates) > MAX_LUA_CANDIDATES:
        return {"ok": False, "engine": "SMART ARCHIVE/LUA", "stage": "scan",
                "error": "Lua candidate count exceeds safety limit",
                "candidates": len(candidates)}

    lua_root = out / "SMART_LUA"
    lua_root.mkdir(parents=True, exist_ok=True)
    successes = []
    partials = []
    failures = []

    from smart_lua_engine import decompile, deep_recover
    for src in candidates:
        rel = src.relative_to(extracted_root).as_posix()
        key = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16]
        dest = lua_root / key
        dest.mkdir(parents=True, exist_ok=True)
        record = {
            "path": rel,
            "bytes": src.stat().st_size,
            "sha256": _sha256(src),
            "probe": probes[str(src)],
        }
        try:
            result = deep_recover(src, dest) if deep_lua else decompile(src, dest)
        except Exception as exc:
            result = {"ok": False, "error": _safe_error(exc)}
        record["recovery"] = result
        if result.get("ok") and result.get("out"):
            artifact = Path(str(result["out"]))
            if artifact.is_file() and artifact.stat().st_size > 0:
                # Strongest available proof: compile the recovered source and
                # compare normalized VM listings with the original chunk.
                # This never executes recovered Lua.
                try:
                    from lua_recovery_proof import prove_roundtrip
                    proof = prove_roundtrip(src, artifact)
                except Exception as exc:
                    proof = {"status": "UNPROVEN", "reason": f"{type(exc).__name__}: {exc}"}
                record["recovery_proof"] = proof
                if proof.get("status") == "ROUNDTRIP_VERIFIED":
                    record["status"] = "ROUNDTRIP_VERIFIED"
                else:
                    record["status"] = result.get("final_status", "SUCCESS")
                if record["status"] in ("SUCCESS", "ROUNDTRIP_VERIFIED"):
                    successes.append(record)
                else:
                    partials.append(record)
                continue
        partials_info = result.get("partial_recovery") if isinstance(result, dict) else None
        if partials_info:
            record["status"] = "PARTIAL"
            partials.append(record)
        else:
            record["status"] = "FAILED"
            failures.append(record)

    report = {
        "ok": bool(successes or partials),
        "engine": "SMART ARCHIVE/LUA",
        "format": fmt,
        "operation": "extract-scan-recover",
        "input": {"name": source.name, "bytes": source.stat().st_size,
                  "sha256": _sha256(source)},
        "extract": extracted,
        "scan": {"files": len(files), "lua_candidates": len(candidates)},
        "recovery": {"attempted": len(candidates), "success": len(successes),
                     "partial": len(partials), "failed": len(failures)},
        "successes": successes,
        "partials": partials,
        "failures": failures,
        "out": str(out),
    }
    report_path = out / "smart_archive_lua_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
                           encoding="utf-8")
    report["report"] = str(report_path)
    return report


__all__ = ["execute"]
