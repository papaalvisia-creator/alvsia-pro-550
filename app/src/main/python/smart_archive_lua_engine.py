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
    return f"{type(exc).__name__}: {exc}"


def _fallback_recovery_status(result) -> str:
    """Classify a non-success recovery result as PARTIAL or FAILED.

    A bounded streaming recovery that produced diagnostic artifacts (strings,
    container unwrap, etc.) reports ``final_status == "PARTIAL"`` with
    ``ok == False``. That is an honest partial recovery, not a failure, and
    must be counted as such so the archive summary never under-reports work
    that actually succeeded within its memory budget.
    """
    if isinstance(result, dict):
        if result.get("partial_recovery"):
            return "PARTIAL"
        if str(result.get("final_status") or "") in (
            "PARTIAL", "PARTIAL_RECOVERY", "STRUCTURALLY_VALID"
        ):
            return "PARTIAL"
    return "FAILED"


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
    # Normalise the caller-facing short kind ("pak"/"obb") to the canonical
    # detected format names ("tencent-pak"/"obb-zip") before comparing.
    _kind_map = {"pak": "tencent-pak", "obb": "obb-zip"}
    normalized_kind = _kind_map.get(archive_kind, archive_kind)
    if normalized_kind not in ("auto", fmt):
        expected = "tencent-pak" if normalized_kind == "tencent-pak" else "obb-zip"
        return {"ok": False, "engine": "SMART " + archive_kind.upper(),
                "stage": "detect", "error": f"expected {expected}, detected {fmt}"}

    extracted_root = out / ("PAK" if fmt == "tencent-pak" else "OBB")
    extracted = extract_archive(source, extracted_root)
    extract_stats = extracted.get("stats") or {}
    try:
        _on_disk = int(extract_stats.get("on_disk") or 0)
    except (TypeError, ValueError):
        _on_disk = 0
    # A partially-extracted archive (e.g. some entries are SM4-blocked with no
    # authorized key material) must NOT abort the whole pipeline: the entries
    # that *were* written can still be scanned and recovered. We only abort
    # when nothing at all was written to disk. The blocked/failed entries stay
    # visible in ``extract`` and the report is marked partial.
    if not extracted.get("ok") and _on_disk <= 0:
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
                proof_status = proof.get("status")
                passthrough = result.get("selected_engine") == "source_passthrough"
                # Honesty rule: a created file is NOT proof of success. Only an
                # already-valid source passthrough or a VM roundtrip match may be
                # reported as SUCCESS/ROUNDTRIP_VERIFIED. A decompiled bytecode
                # artifact that parses but diverges from the original VM listing
                # is STRUCTURALLY_VALID (parseable, not semantically proven), and
                # an unproven artifact is PARTIAL_RECOVERY -- never SUCCESS.
                if passthrough:
                    record["status"] = "SUCCESS"
                elif proof_status == "ROUNDTRIP_VERIFIED":
                    record["status"] = "ROUNDTRIP_VERIFIED"
                elif proof_status == "DIVERGED":
                    record["status"] = "STRUCTURALLY_VALID"
                else:
                    record["status"] = "PARTIAL_RECOVERY"
                if record["status"] in ("SUCCESS", "ROUNDTRIP_VERIFIED",
                                        "EXACT_SOURCE_RECOVERY"):
                    successes.append(record)
                else:
                    partials.append(record)
                continue
        partials_info = result.get("partial_recovery") if isinstance(result, dict) else None
        if partials_info or _fallback_recovery_status(result) == "PARTIAL":
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
        "extraction_complete": bool(extracted.get("ok")),
        "blocked_entries": list(extract_stats.get("blocked_entries") or []),
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




def execute_batch(input_paths, output_dir, work_dir=None, archive_kind="auto",
                  deep_lua=True) -> dict[str, Any]:
    """Run the universal Smart Archive->Lua pipeline over many archives.

    Each archive is processed independently into its own sub-directory so one
    failure never aborts the batch. Returns per-archive summaries plus totals.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else out / "WORK"
    work.mkdir(parents=True, exist_ok=True)

    paths = [Path(p) for p in (input_paths or [])]
    if not paths:
        return {"ok": False, "engine": "SMART ARCHIVE/LUA", "operation": "batch",
                "error": "no input archives supplied", "results": []}

    results = []
    for index, source in enumerate(paths):
        sub_out = out / f"archive_{index:03d}_{source.stem}"
        sub_work = work / f"archive_{index:03d}"
        if not source.is_file():
            results.append({"path": str(source), "ok": False,
                            "error": "input archive not found"})
            continue
        try:
            report = execute(source, sub_out, work_dir=sub_work,
                             archive_kind=archive_kind, deep_lua=deep_lua)
        except Exception as exc:  # one bad archive must not abort the batch
            report = {"ok": False, "engine": "SMART ARCHIVE/LUA",
                      "stage": "pipeline", "error": _safe_error(exc)}
        results.append({
            "path": str(source),
            "ok": bool(report.get("ok")),
            "format": report.get("format"),
            "scan": report.get("scan"),
            "recovery": report.get("recovery"),
            "out": report.get("out"),
            "report": report.get("report"),
            "error": report.get("error"),
        })

    processed = [r for r in results if r.get("ok")]
    total_candidates = sum((r.get("scan") or {}).get("lua_candidates", 0) for r in results)
    total_recovered = sum((r.get("recovery") or {}).get("success", 0) for r in results)
    summary = {
        "ok": bool(processed),
        "engine": "SMART ARCHIVE/LUA",
        "operation": "batch",
        "archive_kind": archive_kind,
        "archives": {"total": len(results), "processed": len(processed),
                     "failed": len(results) - len(processed)},
        "totals": {"lua_candidates": total_candidates,
                   "recovered": total_recovered},
        "results": results,
        "out": str(out),
    }
    report_path = out / "smart_archive_lua_batch_report.json"
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False),
                           encoding="utf-8")
    summary["report"] = str(report_path)
    return summary


__all__ = ["execute", "execute_batch"]
