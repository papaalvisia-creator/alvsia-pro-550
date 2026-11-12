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

        probes = {str(p): _probe_lua(p) for p in files}
        candidates = [p for p in files if probes[str(p)].get("candidate")]
        lua_out = out / "SMART_LUA"
        lua_out.mkdir(parents=True, exist_ok=True)

        from smart_lua_engine import detect, decompile, deep_recover

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
                "probe": probes[str(src)],
            }
            try:
                result = deep_recover(src, dest_dir)
                # If a wrapper precedes a real Lua chunk, retry against an
                # immutable embedded view. This makes wrapped/hybrid payloads
                # recoverable without altering the original corpus file.
                if (not result.get("ok")) and probes[str(src)].get("magic_offset", 0) > 0:
                    view = _make_lua_view(src, probes[str(src)], work / "LUA_VIEWS")
                    retry_dir = dest_dir / "embedded"
                    retry_dir.mkdir(parents=True, exist_ok=True)
                    retry = deep_recover(view, retry_dir)
                    result = dict(retry)
                    result["recovery"] = "embedded-lua-view"
                    result["embedded_offset"] = probes[str(src)].get("magic_offset")
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
                "non_candidates": len(files) - len(candidates),
                "probe": {
                    "max_probe_bytes": MAX_LUA_PROBE_BYTES,
                    "max_decompile_bytes": MAX_LUA_DECOMPILE_BYTES,
                },
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
