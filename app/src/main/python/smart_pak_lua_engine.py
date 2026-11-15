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
MAX_LUA_PROBE_BYTES = 1024 * 1024
MAX_LUA_DECOMPILE_BYTES = 256 * 1024 * 1024
LUA_SUFFIXES = {".lua", ".luac", ".luajit", ".ljbc", ".luau"}
LUA_BINARY_SUFFIXES = {".bytes", ".bin", ".dat"}
LUA_MAGIC = (b"\x1bLua", b"\x1bLJ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe_lua(path: Path) -> dict[str, Any]:
    """Classify without executing the payload.

    Protected/hybrid game payloads can prepend a small wrapper before the Lua
    bytecode header, so the probe scans a bounded prefix rather than requiring
    the magic at offset zero. Plain text is accepted only for Lua-like syntax;
    arbitrary UTF-8 assets are not promoted to decompile candidates.
    """
    suffix = path.suffix.lower()
    try:
        size = path.stat().st_size
        if size > MAX_LUA_DECOMPILE_BYTES:
            return {"candidate": False, "reason": "candidate exceeds decompile size limit"}
        with path.open("rb") as handle:
            probe = handle.read(MAX_LUA_PROBE_BYTES)
    except OSError as exc:
        return {"candidate": False, "reason": _safe_error(exc)}

    for magic in LUA_MAGIC:
        pos = probe.find(magic)
        if pos >= 0:
            return {
                "candidate": True,
                "confidence": "high",
                "kind": "bytecode",
                "magic_offset": pos,
                "suffix": suffix,
            }

    if suffix in LUA_SUFFIXES:
        return {"candidate": True, "confidence": "high", "kind": "lua-extension", "suffix": suffix}

    if suffix in LUA_BINARY_SUFFIXES:
        return {"candidate": False, "reason": "binary suffix without Lua magic", "suffix": suffix}

    if suffix not in (".txt", ".cfg", ".json", ".xml", ".ini", ".lua"):
        return {"candidate": False, "reason": "non-Lua extension"}

    try:
        text = probe.decode("utf-8")
    except UnicodeDecodeError:
        return {"candidate": False, "reason": "not UTF-8 source"}

    lua_markers = (
        "function ", "local ", "return ", "require(", "require ",
        "end", "--", "---@", "setmetatable(", "coroutine.", "string.",
    )
    score = sum(1 for marker in lua_markers if marker in text)
    return {
        "candidate": score >= 2,
        "confidence": "medium" if score >= 2 else "low",
        "kind": "source-probe",
        "marker_score": score,
        "suffix": suffix,
    }


def _looks_like_lua(path: Path) -> bool:
    return bool(_probe_lua(path).get("candidate"))

def _make_lua_view(path: Path, probe: dict[str, Any], work_dir: Path) -> Path:
    """Create a bounded parser view for wrapped Lua payloads.

    The original file is never modified. If a Lua magic is found after a
    wrapper, Smart Lua first receives the embedded chunk as a temporary view.
    This is a recovery route only; encrypted/obfuscated payloads still require
    their dedicated adapter.
    """
    offset = int(probe.get("magic_offset") or 0)
    if offset <= 0:
        return path
    size = path.stat().st_size
    if offset >= size:
        return path
    work_dir.mkdir(parents=True, exist_ok=True)
    view = work_dir / ("lua_view_" + hashlib.sha256(
        f"{path}:{size}:{offset}".encode("utf-8")
    ).hexdigest()[:20] + ".bin")
    with path.open("rb") as src, view.open("wb") as dst:
        src.seek(offset)
        remaining = size - offset
        while remaining:
            block = src.read(min(1024 * 1024, remaining))
            if not block:
                break
            dst.write(block)
            remaining -= len(block)
    return view




def _safe_error(exc: BaseException) -> str:
    return (f"{type(exc).__name__}: {exc}")[:500]


def execute(input_path, output_dir, work_dir=None, archive_kind="pak") -> dict[str, Any]:
    """Run PAK extraction and Lua recovery through the shared, proof-aware pipeline.

    A PAK with some authorization-blocked entries must still process the files
    that were safely extracted. The shared archive engine classifies each Lua
    result as SUCCESS, ROUNDTRIP_VERIFIED, STRUCTURALLY_VALID, PARTIAL_RECOVERY
    or FAILED; a created output file alone is never promoted to SUCCESS.
    """
    source = Path(input_path)
    out = Path(output_dir)
    work = Path(work_dir) if work_dir else out.parent / "WORK"
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    if not source.is_file():
        return {"ok": False, "engine": "SMART PAK/LUA",
                "error": "PAK input file not found", "final_status": "FAILED"}
    size = source.stat().st_size
    if size > MAX_IMPORT_BYTES:
        return {"ok": False, "engine": "SMART PAK/LUA",
                "error": "input exceeds 5 GiB per-file/import limit",
                "final_status": "FAILED"}

    try:
        from smart_archive_lua_engine import execute as execute_archive
        report = dict(execute_archive(
            source, out, work_dir=work, archive_kind="pak", deep_lua=True
        ) or {})
        report["engine"] = "SMART PAK/LUA"
        report["operation"] = "extract-analyze-decompile"
        report["archive_out"] = report.get("out")
        report["out"] = str(out / "SMART_LUA")
        recovery = report.get("recovery") or {}
        report["decompile"] = dict(recovery)
        if report.get("ok"):
            extraction_complete = bool(report.get("extraction_complete"))
            partial = int(recovery.get("partial", 0) or 0)
            failed = int(recovery.get("failed", 0) or 0)
            report["final_status"] = (
                "SUCCESS" if extraction_complete and partial == 0 and failed == 0
                else "PARTIAL"
            )
        else:
            report.setdefault("final_status", "FAILED")
        report_path = out / "smart_pak_lua_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        report["report"] = str(report_path)
        return report
    except Exception as exc:
        return {"ok": False, "engine": "SMART PAK/LUA",
                "stage": "pipeline", "error": _safe_error(exc),
                "final_status": "FAILED"}
