"""Unified Smart PAK -> Lua corpus pipeline.

This is an internal execution path: one PAK operation can extract, classify Lua
payloads, route them through Smart Lua, and produce a deterministic report.
Existing PAK and Lua engines remain the providers; no user-facing legacy
operation is removed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MAX_IMPORT_BYTES = 5 * 1024 * 1024 * 1024
MAX_CANDIDATES = 50000
LUA_SUFFIXES = {".lua", ".luac", ".luajit", ".ljbc", ".luau", ".bytes", ".bin", ".dat"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _looks_like_lua(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in LUA_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
        return head.startswith(b"\x1bLua") or head.startswith(b"\x1bLJ")
    except OSError:
        return False


def _safe_error(exc: BaseException) -> str:
    return (f"{type(exc).__name__}: {exc}")[:500]


def execute(input_path, output_dir, work_dir=None, archive_kind="pak") -> dict[str, Any]:
    source = Path(input_path)
    out = Path(output_dir)
    work = Path(work_dir) if work_dir else out.parent / "WORK"
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    if not source.is_file():
        return {"ok": False, "engine": "SMART PAK/LUA", "error": "PAK input file not found"}
    size = source.stat().st_size
    if size > MAX_IMPORT_BYTES:
        return {"ok": False, "engine": "SMART PAK/LUA",
                "error": "input exceeds 5 GiB per-file/import limit"}

    try:
        from archive_engine import detect_archive, extract_archive
        detected = detect_archive(source)
        if not detected.get("ok") or detected.get("format") != "tencent-pak":
            return {"ok": False, "engine": "SMART PAK/LUA",
                    "error": "input is not a detected Tencent PAK", "detect": detected}

        pak_out = out / "PAK"
        extracted = extract_archive(source, pak_out)
        if not extracted.get("ok"):
            return {"ok": False, "engine": "SMART PAK/LUA",
                    "stage": "extract", "error": extracted.get("error", "PAK extraction failed"),
                    "extract": extracted}

        files = sorted(
            p for p in pak_out.rglob("*")
            if p.is_file()
        )
        if len(files) > MAX_CANDIDATES:
            return {"ok": False, "engine": "SMART PAK/LUA",
                    "stage": "scan", "error": "extracted file count exceeds safety limit",
                    "files": len(files)}

        candidates = [p for p in files if _looks_like_lua(p)]
        lua_out = out / "SMART_LUA"
        lua_out.mkdir(parents=True, exist_ok=True)

        from smart_lua_engine import detect, decompile

        successes = []
        failures = []
        for src in candidates:
            rel = src.relative_to(pak_out)
            # Keep every result in a deterministic, collision-free directory.
            digest = hashlib.sha256(rel.as_posix().encode("utf-8")).hexdigest()[:16]
            dest_dir = lua_out / digest
            dest_dir.mkdir(parents=True, exist_ok=True)
            detection = detect(src)
            record = {
                "path": rel.as_posix(),
                "bytes": src.stat().st_size,
                "sha256": _sha256(src),
                "detection": detection,
            }
            try:
                result = decompile(src, dest_dir)
            except Exception as exc:
                result = {"ok": False, "error": _safe_error(exc)}
            record["decompile"] = result
            if result.get("ok") and result.get("out"):
                artifact = Path(str(result["out"]))
                if artifact.is_file() and artifact.stat().st_size > 0:
                    record["status"] = "SUCCESS"
                    successes.append(record)
                    continue
            record["status"] = "FAILED"
            failures.append(record)

        report = {
            "ok": True,
            "engine": "SMART PAK/LUA",
            "operation": "extract-analyze-decompile",
            "input": {
                "name": source.name,
                "bytes": size,
                "sha256": _sha256(source),
            },
            "extract": extracted,
            "scan": {
                "files": len(files),
                "lua_candidates": len(candidates),
            },
            "decompile": {
                "attempted": len(candidates),
                "success": len(successes),
                "failed": len(failures),
            },
            "successes": successes,
            "failures": failures,
            "out": str(lua_out),
        }
        report_path = out / "smart_pak_lua_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        report["report"] = str(report_path)
        return report
    except Exception as exc:
        return {"ok": False, "engine": "SMART PAK/LUA",
                "stage": "pipeline", "error": _safe_error(exc)}
