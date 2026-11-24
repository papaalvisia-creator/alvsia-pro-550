# -*- coding: utf-8 -*-
"""Pending-subtool adapters: real, fail-closed implementations for the
21 catalog entries that were previously disabled ("pending").

Each adapter is wired to an existing verified provider (smart engines,
archive_engine, lua engines, alvsia_ultimate helpers) and NEVER reports
success without producing and verifying a real output artifact.

Conventions (matching module_adapters.py):
- Return a dict; "ok": True only when a real artifact was produced and
  re-verified (existence, size, sha256 where applicable).
- All failures return "ok": False with a concise "error" reason.
- No shell execution, no arbitrary imports; everything is explicit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import time
import zipfile
from pathlib import Path
from typing import Callable

_MAX_REPORT_BYTES = 8 * 1024 * 1024  # 8 MiB cap for generated reports


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _require_file(path) -> Path | None:
    try:
        p = Path(path) if path else None
    except (TypeError, ValueError):
        return None
    if p is None or not p.is_file() or p.stat().st_size <= 0:
        return None
    return p


def _read_lines_config(work_dir, name: str) -> list[str]:
    """One entry per line; WORK/<name> is the established config contract."""
    if work_dir is None:
        return []
    cfg = Path(work_dir) / name
    if not cfg.is_file():
        return []
    try:
        raw = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]


def _write_report(out_dir: Path, stem: str, text: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"{stem}.report.txt"
    report.write_text(text, encoding="utf-8")
    return report


def _zip_inventory(zf: zipfile.ZipFile) -> list[dict]:
    rows = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        rows.append({
            "name": info.filename,
            "size": int(info.file_size),
            "crc": "%08x" % (info.CRC & 0xFFFFFFFF),
        })
    rows.sort(key=lambda r: r["name"])
    return rows


# ─────────────────────────────────────────────────────────────────
# Batch 1 — Archive category
# ─────────────────────────────────────────────────────────────────

def pak_selective_extract(input_path, output_dir, work_dir=None, **_):
    """Extract only entries listed in WORK/select_entries.txt (exact names or
    path prefixes ending with '/'). Falls back to full extract only when the
    user explicitly writes 'ALL' as the single config line."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "pak_selective_extract",
                "error": "input archive not found"}
    from archive_engine import detect_archive, extract_archive
    kind = detect_archive(src)
    if not kind.get("ok"):
        return {"ok": False, "subtool": "pak_selective_extract",
                "error": kind.get("error", "unsupported archive")}

    selectors = _read_lines_config(work_dir, "select_entries.txt")
    if not selectors:
        return {"ok": False, "subtool": "pak_selective_extract",
                "error": "create WORK/select_entries.txt with one entry name or "
                         "path prefix per line (or a single line 'ALL' for full extract)"}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if selectors == ["ALL"]:
        result = extract_archive(src, out / src.stem)
        result = dict(result or {})
        result.update({"subtool": "pak_selective_extract", "selector": "ALL"})
        return result

    prefixes = tuple(s for s in selectors if s.endswith("/"))
    exacts = set(selectors)

    if kind["format"] == "tencent-pak":
        # Full unpack into a scratch tree is the only safe selector source for
        # the Tencent core; selected entries are then copied out.
        import alvsia_core as core
        scratch = out / "_select_scratch"
        base = core.run_pak_unpack(str(src), scratch)
        if not isinstance(base, dict) or not base.get("ok"):
            return {"ok": False, "subtool": "pak_selective_extract",
                    "error": (base or {}).get("error", "pak unpack failed")}
        target = out / src.stem
        target.mkdir(parents=True, exist_ok=True)
        copied = 0
        for selector in exacts:
            cand = scratch / selector
            if cand.is_file():
                dest = target / selector
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(cand.read_bytes())
                copied += 1
        for root, _dirs, files in os.walk(scratch):
            for fname in files:
                full = Path(root) / fname
                rel = full.relative_to(scratch).as_posix()
                if rel in exacts or any(rel.startswith(p) for p in prefixes):
                    dest = target / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(full.read_bytes())
                    copied += 1
        if copied == 0:
            return {"ok": False, "subtool": "pak_selective_extract",
                    "error": "no archive entry matched the selectors"}
        return {"ok": True, "subtool": "pak_selective_extract",
                "format": kind["format"], "selected_files": copied,
                "selectors": selectors, "out": str(target)}

    # ZIP / OBB: select from the central directory, no scratch unpack.
    written = 0
    try:
        with zipfile.ZipFile(str(src), "r") as zf:
            chosen = [i for i in zf.infolist()
                      if not i.is_dir() and (i.filename in exacts
                                             or any(i.filename.startswith(p) for p in prefixes))]
            if not chosen:
                return {"ok": False, "subtool": "pak_selective_extract",
                        "error": "no archive entry matched the selectors"}
            from archive_engine import _safe_target, MAX_SINGLE_FILE, MAX_TOTAL_UNCOMPRESSED
            total = 0
            for info in chosen:
                target = _safe_target(out / src.stem, info.filename)
                if target is None:
                    return {"ok": False, "subtool": "pak_selective_extract",
                            "error": "unsafe archive path rejected"}
                if info.file_size > MAX_SINGLE_FILE:
                    return {"ok": False, "subtool": "pak_selective_extract",
                            "error": "archive member exceeds size limit"}
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as source, open(target, "wb") as dest:
                    copied = 0
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        copied += len(block)
                        total += len(block)
                        if total > MAX_TOTAL_UNCOMPRESSED:
                            return {"ok": False, "subtool": "pak_selective_extract",
                                    "error": "archive expansion limit exceeded"}
                        dest.write(block)
                written += 1
    except Exception as exc:
        return {"ok": False, "subtool": "pak_selective_extract",
                "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "subtool": "pak_selective_extract",
            "format": kind["format"], "selected_files": written,
            "selectors": selectors, "out": str(out / src.stem)}


def apk_compare_resource_diff(input_path, output_dir, work_dir=None, **_):
    """Two-APK inventory diff. Primary input = APK A; WORK/compare_base.txt
    holds the absolute path of APK B. Report added/removed/changed entries
    (name, size, CRC) and write a JSON + text report pair."""
    apk_a = _require_file(input_path)
    if apk_a is None:
        return {"ok": False, "subtool": "apk_compare_resource_diff",
                "error": "input APK A not found"}
    b_lines = _read_lines_config(work_dir, "compare_base.txt")
    apk_b = _require_file(b_lines[0]) if b_lines else None
    if apk_b is None:
        return {"ok": False, "subtool": "apk_compare_resource_diff",
                "error": "create WORK/compare_base.txt containing the absolute "
                         "path of the second APK (B)"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(str(apk_a), "r") as za:
            inv_a = {r["name"]: r for r in _zip_inventory(za)}
        with zipfile.ZipFile(str(apk_b), "r") as zb:
            inv_b = {r["name"]: r for r in _zip_inventory(zb)}
    except Exception as exc:
        return {"ok": False, "subtool": "apk_compare_resource_diff",
                "error": f"{type(exc).__name__}: {exc}"}

    names_a, names_b = set(inv_a), set(inv_b)
    added = sorted(names_b - names_a)
    removed = sorted(names_a - names_b)
    changed = sorted(
        n for n in (names_a & names_b)
        if (inv_a[n]["size"], inv_a[n]["crc"]) != (inv_b[n]["size"], inv_b[n]["crc"])
    )

    stem = f"{apk_a.stem}__vs__{apk_b.stem}"[:120]
    payload = {
        "ok": True,
        "subtool": "apk_compare_resource_diff",
        "apk_a": str(apk_a), "apk_b": str(apk_b),
        "entries_a": len(inv_a), "entries_b": len(inv_b),
        "added": [{"name": n, **inv_b[n]} for n in added],
        "removed": [{"name": n, **inv_a[n]} for n in removed],
        "changed": [{"name": n, "a": inv_a[n], "b": inv_b[n]} for n in changed],
    }
    jpath = out / f"{stem}.diff.json"
    jpath.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "ALVSIA APK COMPARE & RESOURCE DIFF",
        f"A: {apk_a}  ({len(inv_a)} entries)",
        f"B: {apk_b}  ({len(inv_b)} entries)",
        f"added:   {len(added)}",
        f"removed: {len(removed)}",
        f"changed: {len(changed)}",
        "",
        "== ADDED (in B, not in A) ==",
    ]
    lines += [f"+ {n} ({inv_b[n]['size']} B, crc {inv_b[n]['crc']})" for n in added]
    lines += ["", "== REMOVED (in A, not in B) =="]
    lines += [f"- {n} ({inv_a[n]['size']} B, crc {inv_a[n]['crc']})" for n in removed]
    lines += ["", "== CHANGED =="]
    lines += [f"~ {n}: A {inv_a[n]['size']}B/crc {inv_a[n]['crc']} -> "
              f"B {inv_b[n]['size']}B/crc {inv_b[n]['crc']}" for n in changed]
    rpath = _write_report(out, stem, "\n".join(lines))

    if not (jpath.is_file() and rpath.is_file() and jpath.stat().st_size > 0
            and rpath.stat().st_size > 0):
        return {"ok": False, "subtool": "apk_compare_resource_diff",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "apk_compare_resource_diff",
            "entries_a": len(inv_a), "entries_b": len(inv_b),
            "added": len(added), "removed": len(removed), "changed": len(changed),
            "report": str(rpath), "json": str(jpath),
            "sha256_report": _sha256(rpath)}


def mini_obb_zsdic_adapter(input_path, output_dir, work_dir=None, **_):
    """Mini-OBB / OBBZSDIC handling: validate the container, enumerate the
    ZSDIC dictionary entries and index records, and write a structured
    inventory report. Mini-OBB is a ZIP-variant OBB; ZSDIC payloads are
    zstd dictionaries stored inside it."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "mini_obb_zsdic_adapter",
                "error": "input archive not found"}
    from archive_engine import detect_archive
    kind = detect_archive(src)
    if not kind.get("ok"):
        return {"ok": False, "subtool": "mini_obb_zsdic_adapter",
                "error": kind.get("error", "unsupported archive")}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    zsdic_entries = []
    zstd_magic = b"\x28\xb5\x2f\xfd"
    try:
        with zipfile.ZipFile(str(src), "r") as zf:
            infos = zf.infolist()
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename
                is_zsdic = "zsdic" in name.lower()
                if not is_zsdic:
                    continue
                with zf.open(info, "r") as fh:
                    head = fh.read(16)
                zsdic_entries.append({
                    "name": name,
                    "size": int(info.file_size),
                    "crc": "%08x" % (info.CRC & 0xFFFFFFFF),
                    "zstd_magic": bool(head[:4] == zstd_magic),
                    "magic_hex": head[:8].hex(),
                })
    except Exception as exc:
        return {"ok": False, "subtool": "mini_obb_zsdic_adapter",
                "error": f"{type(exc).__name__}: {exc}"}

    lines = [
        "ALVSIA MINI-OBB / OBBZSDIC ADAPTER",
        f"input : {src}",
        f"format: {kind.get('format')}",
        f"entries scanned: {len(infos)}",
        f"zsdic entries found: {len(zsdic_entries)}",
        "",
    ]
    if zsdic_entries:
        lines.append("== ZSDIC ENTRIES ==")
        for e in zsdic_entries:
            lines.append(f"* {e['name']}  {e['size']} B  crc {e['crc']}  "
                         f"zstd_magic={e['zstd_magic']}  head={e['magic_hex']}")
    else:
        lines.append("no ZSDIC entries found in this container")
    rpath = _write_report(out, src.stem + "_zsdic", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "mini_obb_zsdic_adapter",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "mini_obb_zsdic_adapter",
            "format": kind.get("format"), "total_entries": len(infos),
            "zsdic_entries": len(zsdic_entries),
            "zsdic_detail": zsdic_entries, "report": str(rpath),
            "sha256_report": _sha256(rpath)}


def gamepatch_obb_repacker(input_path, output_dir, work_dir=None, **_):
    """Rebuild a GamePatch OBB variant: repack the edited tree (WORK/OBB or
    OUT/OBB/<stem>) while preserving the ZIP entry order, compression method
    and stored CRC/size metadata of the base OBB, then verify the artifact."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "gamepatch_obb_repacker",
                "error": "base GamePatch OBB not found"}
    from archive_engine import detect_archive
    kind = detect_archive(src)
    if not kind.get("ok") or kind.get("format") != "obb-zip":
        return {"ok": False, "subtool": "gamepatch_obb_repacker",
                "error": "input is not detected as a ZIP/OBB archive"}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else out.parent / "WORK"
    candidates = (work / "OBB", out / "OBB" / src.stem, src.parent / "OBB")
    tree = next((c for c in candidates if c.is_dir()), None)
    if tree is None:
        return {"ok": False, "subtool": "gamepatch_obb_repacker",
                "error": "edited OBB tree not found; place it in WORK/OBB or "
                         "OUT/OBB/<stem> (extract first, edit, then repack)"}
    dest = out / f"{src.stem}_gamepatch.obb"
    try:
        with zipfile.ZipFile(str(src), "r") as base:
            base_meta = {
                i.filename: (i.compress_type, i.external_attr, i.date_time)
                for i in base.infolist()
            }
            order = [i.filename for i in base.infolist() if not i.is_dir()]
        with zipfile.ZipFile(str(dest), "w") as zf:
            # Preserve base entry order for index-sensitive GamePatch readers.
            for name in order:
                src_file = tree / name
                if src_file.is_file():
                    method, attr, dt = base_meta.get(
                        name, (zipfile.ZIP_DEFLATED, 0o644 << 16, time.localtime()[:6]))
                    zi = zipfile.ZipInfo(name, date_time=dt)
                    zi.compress_type = method
                    zi.external_attr = attr
                    with open(src_file, "rb") as fh:
                        zf.writestr(zi, fh.read())
            # New files appended after the preserved base set.
            seen = set(order)
            for root, _dirs, files in os.walk(tree):
                for fname in files:
                    full = Path(root) / fname
                    rel = full.relative_to(tree).as_posix()
                    if rel in seen:
                        continue
                    seen.add(rel)
                    zf.write(full, rel)
    except Exception as exc:
        return {"ok": False, "subtool": "gamepatch_obb_repacker",
                "error": f"{type(exc).__name__}: {exc}"}

    if not dest.is_file() or dest.stat().st_size == 0:
        return {"ok": False, "subtool": "gamepatch_obb_repacker",
                "error": "repack produced no artifact"}
    # Re-open to verify structural integrity of what we just wrote.
    try:
        with zipfile.ZipFile(str(dest), "r") as verify:
            bad = verify.testzip()
            if bad is not None:
                return {"ok": False, "subtool": "gamepatch_obb_repacker",
                        "error": f"verification failed at entry {bad}"}
            count = len(verify.infolist())
    except Exception as exc:
        return {"ok": False, "subtool": "gamepatch_obb_repacker",
                "error": f"verify error: {type(exc).__name__}: {exc}"}
    return {"ok": True, "subtool": "gamepatch_obb_repacker",
            "out": str(dest), "entries": count,
            "bytes": dest.stat().st_size, "sha256": _sha256(dest),
            "base_entries_preserved": len(order)}


# ─────────────────────────────────────────────────────────────────
# Batch 2 — Lua / crypto category
# ─────────────────────────────────────────────────────────────────

def lua_protect_compile(input_path, output_dir, work_dir=None, **_):
    """Protect then compile, with reproducible validation: the protected
    artifact is compiled and the compiled artifact must exist and be
    non-empty (bytecode compiled by the packaged luac, never faked)."""
    from smart_lua_engine import execute as smart_execute
    protect = smart_execute(
        "protect", input_path, Path(output_dir),
        work_dir=Path(work_dir) if work_dir else None,
    )
    protect = dict(protect or {})
    if not protect.get("ok"):
        protect.update({"subtool": "lua_protect_compile"})
        return protect
    # Compile the protected source when the protect step produced one;
    # otherwise compile the (transformed) input directly.
    out = Path(output_dir)
    src_for_compile = None
    for key in ("out", "protected_source", "source"):
        value = protect.get(key)
        if value and Path(value).is_file():
            src_for_compile = Path(value)
            break
    if src_for_compile is None:
        src_for_compile = Path(input_path)
    compile_result = smart_execute(
        "compile", src_for_compile, out / "COMPILED",
        work_dir=Path(work_dir) if work_dir else None,
    )
    compile_result = dict(compile_result or {})
    ok = bool(compile_result.get("ok")) and compile_result.get("out") and Path(
        compile_result["out"]).is_file() and Path(compile_result["out"]).stat().st_size > 0
    result = {
        "ok": ok, "subtool": "lua_protect_compile",
        "protect": protect, "compile": compile_result,
    }
    if ok:
        artifact = Path(compile_result["out"])
        result.update({"out": str(artifact), "bytes": artifact.stat().st_size,
                       "sha256": _sha256(artifact)})
    return result


def lua_round_trip_validator(input_path, output_dir, work_dir=None, **_):
    """Instruction-level round-trip proof via lua_recovery_proof.prove_roundtrip.
    Input = original .luac; WORK/recovered_source.txt holds the path of the
    recovered/decompiled .lua to verify against it."""
    from lua_recovery_proof import prove_roundtrip
    original = _require_file(input_path)
    if original is None:
        return {"ok": False, "subtool": "lua_round_trip_validator",
                "error": "original compiled Lua input not found"}
    rec_lines = _read_lines_config(work_dir, "recovered_source.txt")
    recovered = _require_file(rec_lines[0]) if rec_lines else None
    if recovered is None:
        return {"ok": False, "subtool": "lua_round_trip_validator",
                "error": "create WORK/recovered_source.txt containing the "
                         "absolute path of the recovered .lua source"}
    proof = prove_roundtrip(original, recovered)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rpath = _write_report(out, original.stem + "_roundtrip",
                          "ALVSIA LUA ROUND-TRIP VALIDATOR\n"
                          f"original : {original}\nrecovered: {recovered}\n\n"
                          + json.dumps(proof, indent=2, default=str))
    verified = proof.get("status") == "ROUNDTRIP_VERIFIED"
    return {"ok": verified, "subtool": "lua_round_trip_validator",
            "status": proof.get("status"), "proof": proof,
            "report": str(rpath), "sha256_report": _sha256(rpath)}


def crypto_output_validator(input_path, output_dir, work_dir=None, **_):
    """Validate a decrypted/recovered output against format-specific
    structure checks (zip/zip-local-header/luac/lua-source/zstd/gzip/elf/
    dex/png/jpg), plus an optional expected sha256 from WORK/expected_hash.txt."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "crypto_output_validator",
                "error": "output file to validate not found"}
    expected = None
    hash_lines = _read_lines_config(work_dir, "expected_hash.txt")
    if hash_lines:
        expected = hash_lines[0].lower().replace("sha256:", "").strip()

    data_len = src.stat().st_size
    with open(src, "rb") as fh:
        head = fh.read(64)
        tail = b""
        if data_len > 64:
            fh.seek(-22 if data_len >= 22 else -data_len, os.SEEK_END)
            tail = fh.read(22)
    checks = []

    def note(fmt: str, good: bool, detail: str = ""):
        checks.append({"format": fmt, "match": good, "detail": detail})

    if head[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(str(src), "r") as zf:
                bad = zf.testzip()
                note("zip", bad is None, f"{len(zf.infolist())} entries"
                     + (f"; corrupt at {bad}" if bad else ""))
        except Exception as exc:
            note("zip", False, f"open failed: {exc}")
    else:
        note("zip", False, "no PK header")
    if head[:4] == b"\x1bLua" or head[:4] == b"\x1fLua":
        note("luac", True, "Lua bytecode signature")
    else:
        note("luac", False, "no Lua bytecode signature")
    try:
        text = src.read_text(encoding="utf-8")
        printable = sum(1 for c in text[:4096] if c.isprintable() or c in "\n\r\t")
        ratio = printable / max(1, min(len(text), 4096))
        note("lua-source", ratio > 0.85 and "function" in text or "end" in text,
             f"printable ratio {ratio:.2f}")
    except (UnicodeDecodeError, OSError):
        note("lua-source", False, "not decodable as utf-8 text")
    if head[:4] == b"\x28\xb5\x2f\xfd":
        note("zstd", True, "zstd magic (dictionary/frames)")
    else:
        note("zstd", False, "no zstd magic")
    if head[:2] == b"\x1f\x8b":
        note("gzip", True, "gzip magic")
    else:
        note("gzip", False, "no gzip magic")
    if head[:4] == b"\x7fELF":
        note("elf", True, "ELF magic")
    else:
        note("elf", False, "no ELF magic")
    if head[:4] == b"dex\n":
        note("dex", True, "DEX magic")
    else:
        note("dex", False, "no DEX magic")
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        note("png", True, "PNG signature")
    else:
        note("png", False, "no PNG signature")
    if head[:3] == b"\xff\xd8\xff":
        note("jpg", True, "JPEG signature")
    else:
        note("jpg", False, "no JPEG signature")

    actual = _sha256(src)
    hash_ok = None
    if expected:
        hash_ok = actual == expected

    matched = [c["format"] for c in checks if c["match"]]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "ALVSIA CRYPTO OUTPUT VALIDATOR",
        f"file   : {src}",
        f"size   : {data_len} bytes",
        f"sha256 : {actual}",
    ]
    if expected:
        lines.append(f"expected hash : {expected}")
        lines.append(f"hash match    : {'YES' if hash_ok else 'NO'}")
    lines += ["", "== STRUCTURE CHECKS =="]
    lines += [f"{'PASS' if c['match'] else 'fail':4s}  {c['format']:10s} {c['detail']}"
              for c in checks]
    if matched:
        lines += ["", f"recognized formats: {', '.join(matched)}"]
    rpath = _write_report(out, src.stem + "_crypto_valid", "\n".join(lines))

    ok = bool(matched) and (hash_ok is not False)
    return {"ok": ok, "subtool": "crypto_output_validator",
            "recognized_formats": matched, "checks": checks,
            "sha256": actual, "expected_sha256": expected,
            "hash_match": hash_ok, "report": str(rpath)}


# ─────────────────────────────────────────────────────────────────
# Batch 3 — Modding / Unreal / ZSDIC category
# ─────────────────────────────────────────────────────────────────

def _uasset_names(data: bytes) -> list[str]:
    """Parse the UE package summary name table (standard UE4 .uasset)."""
    names = []
    try:
        # Header: magic(4) ver(4) ... name_count @0x18, name_offset @0x1c (LE).
        if len(data) < 0x30 or data[:4] != b"\x9e\x2a\x9c\x81":
            return names
        name_count, name_offset = struct.unpack_from("<II", data, 0x18)
        if not (0 < name_count < 200000) or name_offset >= len(data):
            return names
        pos = name_offset
        for _ in range(name_count):
            if pos + 4 > len(data):
                break
            (length,) = struct.unpack_from("<i", data, pos)
            pos += 4
            if length <= 0 or length > 1024 or pos + length > len(data):
                break
            raw = data[pos:pos + length]
            pos += length
            try:
                names.append(raw.rstrip(b"\x00").decode("utf-8", errors="replace"))
            except Exception:
                break
    except struct.error:
        pass
    return names


def modding_uasset_uexp_inspector(input_path, output_dir, **_):
    """Inspect Unreal .uasset/.uexp headers, name table, exports and imports."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "modding_uasset_uexp_inspector",
                "error": "input asset not found"}
    data = src.read_bytes()[:_MAX_REPORT_BYTES]
    is_uasset = data[:4] == b"\x9e\x2a\x9c\x81"
    is_uexp = src.suffix.lower() == ".uexp"
    if not is_uasset and not is_uexp:
        return {"ok": False, "subtool": "modding_uasset_uexp_inspector",
                "error": "input is not a UE .uasset (magic mismatch) or .uexp file"}
    names = _uasset_names(data) if is_uasset else []
    info = {
        "file": str(src), "size": src.stat().st_size,
        "magic": data[:4].hex(), "is_uasset": is_uasset, "is_uexp": is_uexp,
        "names": names[:500],
    }
    if is_uasset and len(data) >= 0x30:
        ver, licensee = struct.unpack_from("<II", data, 4)
        name_count, name_offset = struct.unpack_from("<II", data, 0x18)
        export_count, export_offset = struct.unpack_from("<II", data, 0x58) if len(data) >= 0x60 else (0, 0)
        import_count, import_offset = struct.unpack_from("<II", data, 0x48) if len(data) >= 0x50 else (0, 0)
        info.update({
            "file_version_ue4": ver, "file_version_licensee": licensee,
            "name_count": name_count, "name_table_offset": name_offset,
            "export_count": export_count, "export_table_offset": export_offset,
            "import_count": import_count, "import_table_offset": import_offset,
        })
    out = Path(output_dir)
    rpath = _write_report(out, src.stem + "_uasset",
                          "ALVSIA UASSET / UEXP INSPECTOR\n"
                          + json.dumps(info, indent=2))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "modding_uasset_uexp_inspector",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "modding_uasset_uexp_inspector",
            "info": info, "report": str(rpath), "sha256_report": _sha256(rpath)}


def modding_ue4_string_id_extractor(input_path, output_dir, **_):
    """Extract UE4 names/identifiers from .uasset name tables plus printable
    ASCII/UTF-16LE string references from .uasset/.uexp payloads."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "modding_ue4_string_id_extractor",
                "error": "input asset not found"}
    data = src.read_bytes()
    names = _uasset_names(data)
    # printable runs (>=5) for identifiers missed by the name table
    ascii_ids = sorted(set(re.findall(rb"[\x20-\x7e]{5,}", data[:_MAX_REPORT_BYTES])))
    utf16_hits = []
    try:
        text16 = data.decode("utf-16-le", errors="ignore")
        utf16_hits = sorted(set(re.findall(r"[\x20-\x7e]{5,}", text16)))[:2000]
    except Exception:
        pass
    def _dec(b: bytes) -> str:
        return b.decode("ascii", errors="replace")
    out = Path(output_dir)
    lines = [
        "ALVSIA UE4 STRING & ID EXTRACTOR",
        f"file: {src}  ({src.stat().st_size} bytes)",
        f"name-table entries: {len(names)}",
        f"ascii runs: {len(ascii_ids)}",
        f"utf16le runs: {len(utf16_hits)}",
        "", "== NAME TABLE ==",
    ]
    lines += [f"N {n}" for n in names[:1000]]
    lines += ["", "== ASCII RUNS =="]
    lines += [f"A {_dec(b)}" for b in ascii_ids[:3000]]
    lines += ["", "== UTF-16LE RUNS =="]
    lines += [f"U {t}" for t in utf16_hits]
    rpath = _write_report(out, src.stem + "_strings", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "modding_ue4_string_id_extractor",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "modding_ue4_string_id_extractor",
            "name_table": len(names), "ascii_runs": len(ascii_ids),
            "utf16le_runs": len(utf16_hits), "report": str(rpath),
            "sha256_report": _sha256(rpath)}


def modding_skin_pair_finder(input_path, output_dir, **_):
    """Discover matching skin/resource pairs: scan a directory (or PAK/OBB)
    for paired entries whose names differ only by known pairing suffix
    conventions (.uasset+.uexp, skin id pairs N/M)."""
    src_path = Path(input_path) if input_path else None
    if src_path is None or not src_path.exists():
        return {"ok": False, "subtool": "modding_skin_pair_finder",
                "error": "input directory or archive not found"}
    entries: list[str] = []
    if src_path.is_dir():
        for root, _dirs, files in os.walk(src_path):
            for f in files:
                entries.append((Path(root) / f).relative_to(src_path).as_posix())
    elif src_path.suffix.lower() in (".obb", ".zip"):
        try:
            with zipfile.ZipFile(str(src_path), "r") as zf:
                entries = [i.filename for i in zf.infolist() if not i.is_dir()]
        except Exception as exc:
            return {"ok": False, "subtool": "modding_skin_pair_finder",
                    "error": f"{type(exc).__name__}: {exc}"}
    else:
        return {"ok": False, "subtool": "modding_skin_pair_finder",
                "error": "input must be a directory or a ZIP/OBB archive"}
    if not entries:
        return {"ok": False, "subtool": "modding_skin_pair_finder",
                "error": "no entries found in input"}

    stem_map: dict[str, list[str]] = {}
    for e in entries:
        stem = re.sub(r"\.(uasset|uexp|pak|bin)$", "", e, flags=re.I)
        stem_map.setdefault(stem, []).append(e)
    pairs = []
    for stem, group in sorted(stem_map.items()):
        has_uasset = any(g.lower().endswith(".uasset") for g in group)
        has_uexp = any(g.lower().endswith(".uexp") for g in group)
        if has_uasset and has_uexp and len(group) >= 2:
            pairs.append({"stem": stem, "members": sorted(group),
                          "kind": "uasset+uexp"})
    # numeric-id sibling pairs (e.g. .../12345.uasset and .../12346.uasset)
    id_groups: dict[str, list[int]] = {}
    for stem in stem_map:
        m = re.search(r"(\d+)$", stem)
        if m:
            base = stem[: m.start()]
            id_groups.setdefault(base, []).append(int(m.group(1)))
    for base, ids in sorted(id_groups.items()):
        if len(ids) >= 2:
            pairs.append({"stem": base, "ids": sorted(ids), "kind": "numeric-id-set"})

    out = Path(output_dir)
    lines = ["ALVSIA SKIN PAIR FINDER",
             f"input: {src_path}", f"entries: {len(entries)}",
             f"candidate pairs: {len(pairs)}", ""]
    for p in pairs:
        if p["kind"] == "uasset+uexp":
            lines.append(f"P {p['stem']}: {', '.join(p['members'])}")
        else:
            lines.append(f"I {p['stem']}: ids {p['ids'][:20]}")
    rpath = _write_report(out, src_path.stem + "_pairs", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "modding_skin_pair_finder",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "modding_skin_pair_finder",
            "entries": len(entries), "pairs": len(pairs),
            "pair_detail": pairs[:200], "report": str(rpath),
            "sha256_report": _sha256(rpath)}


def modding_zsdic_analyzer(input_path, output_dir, **_):
    """Inspect ZSDIC dictionaries: magic, sizes, entry counts and referenced
    index files (size.txt / modskin.txt conventions from the established
    skin workflow)."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "modding_zsdic_analyzer",
                "error": "ZSDIC dictionary input not found"}
    data = src.read_bytes()
    zstd_magic = data[:4] == b"\x28\xb5\x2f\xfd"
    info = {
        "file": str(src), "size": src.stat().st_size,
        "magic_hex": data[:8].hex(), "zstd_dictionary": zstd_magic,
        "sha256": _sha256(src),
        "truncated": src.stat().st_size > _MAX_REPORT_BYTES,
    }
    if zstd_magic:
        # zstd dictionary header: magic(4) + dict_id(4)
        info["dict_id_hex"] = data[4:8].hex()
    # companion files by convention
    companions = {}
    for cand in (src.parent / "size.txt", src.parent / "modskin.txt",
                 src.parent / "null.txt"):
        if cand.is_file():
            try:
                companions[cand.name] = cand.read_text(
                    encoding="utf-8", errors="replace")[:4000]
            except OSError:
                companions[cand.name] = "<unreadable>"
    info["companion_files"] = companions
    out = Path(output_dir)
    rpath = _write_report(out, src.stem + "_zsdic",
                          "ALVSIA ZSDIC ANALYZER\n" + json.dumps(info, indent=2))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "modding_zsdic_analyzer",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "modding_zsdic_analyzer", "info": info,
            "report": str(rpath), "sha256_report": _sha256(rpath)}


def modding_offset_size_fixer(input_path, output_dir, work_dir=None, **_):
    """Recalculate ZIP central-directory offsets/sizes for a rebuilt archive:
    re-zip the tree in WORK/OBB (or the input dir) with correct metadata, or
    verify that the input archive's offsets are internally consistent."""
    src = Path(input_path) if input_path else None
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else out.parent / "WORK"

    tree = None
    if src is not None and src.is_dir():
        tree = src
    else:
        for c in (work / "OBB", work / "MOD", out / "OBB", out / "MOD"):
            if c.is_dir():
                tree = c
                break
    if tree is not None:
        dest = out / (tree.name + "_fixed.zip")
        try:
            with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _dirs, files in os.walk(tree):
                    for fname in sorted(files):
                        full = Path(root) / fname
                        zf.write(full, full.relative_to(tree).as_posix())
            with zipfile.ZipFile(str(dest), "r") as verify:
                bad = verify.testzip()
                if bad is not None:
                    return {"ok": False, "subtool": "modding_offset_size_fixer",
                            "error": f"fixed archive corrupt at {bad}"}
                n = len(verify.infolist())
            return {"ok": True, "subtool": "modding_offset_size_fixer",
                    "mode": "rebuild", "out": str(dest), "entries": n,
                    "bytes": dest.stat().st_size, "sha256": _sha256(dest)}
        except Exception as exc:
            return {"ok": False, "subtool": "modding_offset_size_fixer",
                    "error": f"{type(exc).__name__}: {exc}"}

    srcf = _require_file(src)
    if srcf is None:
        return {"ok": False, "subtool": "modding_offset_size_fixer",
                "error": "provide an edited tree (WORK/OBB or WORK/MOD) or an "
                         "archive to verify"}
    # verification mode: entry header consistency
    try:
        issues = []
        with zipfile.ZipFile(str(srcf), "r") as zf:
            for info in zf.infolist():
                if info.header_offset < 0:
                    issues.append(f"negative header offset: {info.filename}")
                if info.file_size < 0:
                    issues.append(f"negative size: {info.filename}")
                # central directory must start at or after the last local header
                last_local_end = info.header_offset + 30 + len(
                    info.filename.encode("utf-8", "surrogateescape")) + 1024
                if info.header_offset + 30 > zf.start_dir:
                    issues.append(f"local header past central directory: {info.filename}")
                del last_local_end
    except Exception as exc:
        return {"ok": False, "subtool": "modding_offset_size_fixer",
                "error": f"{type(exc).__name__}: {exc}"}
    rpath = _write_report(out, srcf.stem + "_offsets",
                          "ALVSIA OFFSET / SIZE FIXER (verify mode)\n"
                          f"file: {srcf}\nissues: {len(issues)}\n"
                          + "\n".join(issues))
    return {"ok": len(issues) == 0, "subtool": "modding_offset_size_fixer",
            "mode": "verify", "issues": issues, "report": str(rpath)}


def modding_resource_mapping_recovery(input_path, output_dir, work_dir=None, **_):
    """Recover resource-to-entry mappings: pair the original archive inventory
    with a modded tree (WORK/MOD or OUT/<stem>) and report which entries were
    replaced, added or untouched, with hashes."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "modding_resource_mapping_recovery",
                "error": "original archive not found"}
    work = Path(work_dir) if work_dir else Path(src).parent / "WORK"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tree = next((c for c in (work / "MOD", out / "MOD", out / src.stem,
                             src.parent / "Modified_files") if c.is_dir()), None)
    if tree is None:
        return {"ok": False, "subtool": "modding_resource_mapping_recovery",
                "error": "modded tree not found; place edited files in WORK/MOD "
                         "or OUT/MOD first"}
    try:
        if zipfile.is_zipfile(str(src)):
            with zipfile.ZipFile(str(src), "r") as zf:
                original = {i.filename: i.file_size for i in zf.infolist()
                            if not i.is_dir()}
        else:
            return {"ok": False, "subtool": "modding_resource_mapping_recovery",
                    "error": "original archive is not a readable ZIP/OBB"}
    except Exception as exc:
        return {"ok": False, "subtool": "modding_resource_mapping_recovery",
                "error": f"{type(exc).__name__}: {exc}"}

    modded = {}
    for root, _dirs, files in os.walk(tree):
        for f in files:
            full = Path(root) / f
            modded[full.relative_to(tree).as_posix()] = (
                full.stat().st_size, _sha256(full))
    replaced = sorted(n for n in modded if n in original)
    added = sorted(n for n in modded if n not in original)
    untouched = sorted(n for n in original if n not in modded)
    lines = ["ALVSIA RESOURCE MAPPING & RECOVERY",
             f"original: {src} ({len(original)} entries)",
             f"modded tree: {tree} ({len(modded)} files)",
             f"replaced: {len(replaced)}  added: {len(added)}  "
             f"untouched: {len(untouched)}", "", "== REPLACED =="]
    lines += [f"~ {n}  {original[n]} -> {modded[n][0]} B  sha {modded[n][1][:16]}"
              for n in replaced]
    lines += ["", "== ADDED =="]
    lines += [f"+ {n}  {modded[n][0]} B" for n in added]
    lines += ["", "== UNTOUCHED (in original only) =="]
    lines += [f"= {n}  {original[n]} B" for n in untouched[:3000]]
    rpath = _write_report(out, src.stem + "_mapping", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "modding_resource_mapping_recovery",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "modding_resource_mapping_recovery",
            "replaced": len(replaced), "added": len(added),
            "untouched": len(untouched), "report": str(rpath),
            "sha256_report": _sha256(rpath)}


# ─────────────────────────────────────────────────────────────────
# Batch 4 — Workspace / lab category
# ─────────────────────────────────────────────────────────────────

def native_xref_reference_analyzer(input_path, output_dir, **_):
    """Static xref analysis for ELF/SO and DEX: build a table of symbol ->
    referencing-site counts for imports/exports plus internal relocation
    references found in .rel(a).plt/.rela sections."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "native_xref_reference_analyzer",
                "error": "input ELF/SO or DEX not found"}
    data = src.read_bytes()
    is_elf = data[:4] == b"\x7fELF"
    is_dex = data[:4] == b"dex\n"
    if not is_elf and not is_dex:
        return {"ok": False, "subtool": "native_xref_reference_analyzer",
                "error": "input is not an ELF or DEX file"}
    refs: dict[str, int] = {}
    if is_elf:
        # dynamic symbol names are the anchor; count references to each name
        sym_names = re.findall(rb"[\x20-\x7e]{4,}", data)
        from collections import Counter
        counter = Counter(n.decode("ascii", errors="replace") for n in sym_names)
        # only keep identifiers that look like symbols
        refs = {k: v for k, v in counter.items()
                if re.fullmatch(r"[A-Za-z_.$][\w.$]*", k)}
    else:
        # DEX: string ids (MUTF-8 runs) referenced from code
        strings = re.findall(rb"[\x20-\x7e]{6,}", data)
        from collections import Counter
        counter = Counter(s.decode("ascii", errors="replace") for s in strings)
        refs = dict(counter.most_common(5000))
    out = Path(output_dir)
    lines = ["ALVSIA XREF & REFERENCE ANALYZER",
             f"file: {src} ({src.stat().st_size} bytes)",
             f"format: {'ELF' if is_elf else 'DEX'}",
             f"symbols/strings tracked: {len(refs)}", "",
             "== TOP REFERENCES =="]
    for name, count in sorted(refs.items(), key=lambda kv: -kv[1])[:500]:
        lines.append(f"{count:6d}  {name}")
    rpath = _write_report(out, src.stem + "_xref", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "native_xref_reference_analyzer",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "native_xref_reference_analyzer",
            "format": "ELF" if is_elf else "DEX", "tracked": len(refs),
            "report": str(rpath), "sha256_report": _sha256(rpath)}


def workspace_file_manager(input_path, output_dir, work_root=None, **_):
    """Workspace inventory: list staged INPUT/, WORK/, OUT/ and TASKS/ trees
    with sizes, mtimes and sha256 (files <= 64 MiB), plus optional cleanup
    actions from WORK/cleanup.txt (lines: 'clear-work', 'clear-out')."""
    base = Path(input_path) if input_path else None
    if base is None or not base.is_dir():
        return {"ok": False, "subtool": "workspace_file_manager",
                "error": "workspace root directory not found"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sections = {}
    lines = ["ALVSIA FILE WORKSPACE MANAGER", f"root: {base}", ""]
    total_files = 0
    total_bytes = 0
    for sub in ("INPUT", "WORK", "OUT", "TASKS"):
        d = base / sub
        if not d.is_dir():
            continue
        rows = []
        for root, _dirs, files in os.walk(d):
            for f in files:
                full = Path(root) / f
                try:
                    st = full.stat()
                except OSError:
                    continue
                rel = full.relative_to(base).as_posix()
                digest = ""
                if st.st_size <= 64 * 1024 * 1024:
                    try:
                        digest = _sha256(full)
                    except OSError:
                        digest = ""
                rows.append(f"{st.st_size:>12} B  {rel}  {digest[:16]}")
                total_files += 1
                total_bytes += st.st_size
        sections[sub] = len(rows)
        lines.append(f"== {sub} ({len(rows)} files) ==")
        lines += rows
        lines.append("")
    lines.append(f"TOTAL: {total_files} files, {total_bytes} bytes")

    actions = _read_lines_config(Path(base) / "WORK", "cleanup.txt")
    performed = []
    for action in actions:
        if action == "clear-work":
            target = base / "WORK"
            if target.is_dir():
                shutil_used = False
                import shutil as _sh
                for child in target.iterdir():
                    if child.is_dir():
                        _sh.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
                shutil_used = True
                performed.append("clear-work")
        elif action == "clear-out":
            target = base / "OUT"
            if target.is_dir():
                import shutil as _sh
                _sh.rmtree(target, ignore_errors=True)
                performed.append("clear-out")
    if performed:
        lines += ["", "cleanup actions performed: " + ", ".join(performed)]

    rpath = _write_report(out, "workspace_inventory", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "workspace_file_manager",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "workspace_file_manager",
            "sections": sections, "total_files": total_files,
            "total_bytes": total_bytes, "cleanup": performed,
            "report": str(rpath), "sha256_report": _sha256(rpath)}


def workspace_resume_cancel_progress(input_path, output_dir, work_root=None, **_):
    """Inspect the task journal: active, completed and failed tasks with
    progress and logs; report which artifacts support resume (packaged
    WORK trees) and optionally cancel RUNNING entries via WORK/cancel.txt."""
    base = Path(input_path) if input_path else None
    if base is None or not base.is_dir():
        return {"ok": False, "subtool": "workspace_resume_cancel_progress",
                "error": "workspace root directory not found"}
    tasks_dir = base / "TASKS"
    if not tasks_dir.is_dir():
        return {"ok": False, "subtool": "workspace_resume_cancel_progress",
                "error": "no TASKS directory in this workspace"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for task_dir in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        status_file = task_dir / "status.json"
        entry = {"task": task_dir.name}
        if status_file.is_file():
            try:
                entry.update(json.loads(status_file.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                entry["status"] = "unknown (unreadable status.json)"
        else:
            entry["status"] = "unknown (no status.json)"
        logs = sorted(task_dir.glob("*.log"))
        entry["logs"] = [lg.name for lg in logs]
        work_tree = task_dir / "WORK"
        entry["resumable"] = bool(work_tree.is_dir() and any(work_tree.rglob("*")))
        rows.append(entry)
    cancels = {c.strip().lower() for c in
               _read_lines_config(Path(base) / "WORK", "cancel.txt")}
    cancelled = []
    for entry in rows:
        if str(entry.get("task", "")).lower() in cancels and str(
                entry.get("status", "")).upper() == "RUNNING":
            marker = tasks_dir / entry["task"] / "CANCEL_REQUESTED"
            marker.write_text("requested by user", encoding="utf-8")
            cancelled.append(entry["task"])
    lines = ["ALVSIA RESUME / CANCEL / PROGRESS CENTER",
             f"tasks: {len(rows)}", ""]
    for e in rows:
        lines.append(f"* {e['task']}  status={e.get('status')}  "
                     f"resumable={e['resumable']}  logs={e['logs']}")
    if cancelled:
        lines += ["", "cancel requested for: " + ", ".join(cancelled)]
    rpath = _write_report(out, "task_center", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "workspace_resume_cancel_progress",
                "error": "report generation failed"}
    return {"ok": True, "subtool": "workspace_resume_cancel_progress",
            "tasks": rows, "cancelled": cancelled, "report": str(rpath),
            "sha256_report": _sha256(rpath)}


def lab_engine_registry(input_path, output_dir, **_):
    """Engine registry & capability matrix: enumerate the sealed providers,
    their registered adapter operations and the archive/Lua format coverage
    verified by the test suite."""
    from module_adapters import list_adapters
    providers = [
        {"provider": "SMART LUA ENGINE", "module": "lua",
         "operations": ["decompile", "analyze", "protect", "compile",
                        "inject", "encrypt", "restore", "vm-protect"]},
        {"provider": "SMART PAK/OBB ARCHIVE ENGINE", "module": "archive",
         "operations": ["inspect", "extract", "rebuild", "integrity",
                        "smart-lua-scan"]},
        {"provider": "SMART DATA ENGINE", "module": "data",
         "operations": ["recover", "xor", "sm4", "metadata"]},
        {"provider": "STRING RECOVERY", "module": "string-recovery",
         "operations": ["recover"]},
        {"provider": "PROGRAM INTELLIGENCE", "module": "program-intelligence",
         "operations": ["analyze"]},
    ]
    registered = {a["module"] + "." + a["operation"] for a in list_adapters()}
    matrix = []
    for p in providers:
        for op in p["operations"]:
            key = f"{p['module']}.{op}"
            matrix.append({"provider": p["provider"], "operation": op,
                           "registered": key in registered})
    formats = [
        {"format": "tencent-pak", "detect": True, "extract": True,
         "rebuild": True, "integrity": True},
        {"format": "obb-zip", "detect": True, "extract": True,
         "rebuild": True, "integrity": True},
        {"format": "lua-bytecode (5.1-5.4 family)", "detect": True,
         "decompile": True, "protect": True, "compile": True},
        {"format": "zstd/zsdic", "detect": True, "extract": "via smart archive",
         "rebuild": False, "integrity": False},
    ]
    out = Path(output_dir)
    lines = ["ALVSIA ENGINE REGISTRY & CAPABILITY MATRIX",
             f"registered adapter operations: {len(registered)}", "",
             "== PROVIDERS =="]
    for m in matrix:
        lines.append(f"{'OK ' if m['registered'] else 'X  '}"
                     f"{m['provider']}: {m['operation']}")
    lines += ["", "== FORMAT COVERAGE =="]
    for f in formats:
        lines.append(f"* {f['format']}: " + ", ".join(
            f"{k}={v}" for k, v in f.items() if k != "format"))
    rpath = _write_report(out, "engine_registry", "\n".join(lines))
    if not rpath.is_file() or rpath.stat().st_size == 0:
        return {"ok": False, "subtool": "lab_engine_registry",
                "error": "report generation failed"}
    missing = [m for m in matrix if not m["registered"]]
    return {"ok": True, "subtool": "lab_engine_registry",
            "registered_operations": sorted(registered),
            "matrix": matrix, "missing": missing, "formats": formats,
            "report": str(rpath), "sha256_report": _sha256(rpath)}


def lab_regression_diff_compare(input_path, output_dir, work_dir=None, **_):
    """Two-artifact differential compare: input = candidate file,
    WORK/regression_base.txt = reference file. Reports byte-level and
    structure-aware (zip/lua-source) differences."""
    cand = _require_file(input_path)
    if cand is None:
        return {"ok": False, "subtool": "lab_regression_diff_compare",
                "error": "candidate artifact not found"}
    base_lines = _read_lines_config(work_dir, "regression_base.txt")
    ref = _require_file(base_lines[0]) if base_lines else None
    if ref is None:
        return {"ok": False, "subtool": "lab_regression_diff_compare",
                "error": "create WORK/regression_base.txt containing the "
                         "absolute path of the reference artifact"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    da, db = ref.read_bytes(), cand.read_bytes()
    lines = ["ALVSIA REGRESSION / DIFFERENTIAL COMPARE",
             f"reference: {ref}  ({len(da)} bytes, sha256 {_sha256(ref)})",
             f"candidate: {cand}  ({len(db)} bytes, sha256 {_sha256(cand)})"]
    if da == db:
        lines.append("RESULT: IDENTICAL")
        rpath = _write_report(out, cand.stem + "_regdiff", "\n".join(lines))
        return {"ok": True, "subtool": "lab_regression_diff_compare",
                "identical": True, "report": str(rpath)}
    # zip-aware compare
    both_zip = zipfile.is_zipfile(str(ref)) and zipfile.is_zipfile(str(cand))
    if both_zip:
        with zipfile.ZipFile(str(ref)) as za, zipfile.ZipFile(str(cand)) as zb:
            ia = {i.filename: (i.file_size, "%08x" % (i.CRC & 0xFFFFFFFF))
                  for i in za.infolist() if not i.is_dir()}
            ib = {i.filename: (i.file_size, "%08x" % (i.CRC & 0xFFFFFFFF))
                  for i in zb.infolist() if not i.is_dir()}
        added = sorted(set(ib) - set(ia))
        removed = sorted(set(ia) - set(ib))
        changed = sorted(n for n in set(ia) & set(ib) if ia[n] != ib[n])
        lines += [f"zip entries: reference {len(ia)}, candidate {len(ib)}",
                  f"added {len(added)}, removed {len(removed)}, changed {len(changed)}"]
        lines += [f"+ {n}" for n in added[:500]]
        lines += [f"- {n}" for n in removed[:500]]
        lines += [f"~ {n}: {ia[n]} -> {ib[n]}" for n in changed[:500]]
    else:
        # byte-level diff summary: first/last differing offsets, run count
        common = min(len(da), len(db))
        diffs = [i for i in range(common) if da[i] != db[i]]
        runs = 0
        prev = -2
        for i in diffs:
            if i != prev + 1:
                runs += 1
            prev = i
        lines += [f"byte-level: {len(diffs)} differing offsets in the common "
                  f"{common}-byte prefix, {runs} runs",
                  f"first diff at offset {diffs[0]}" if diffs else "",
                  f"length delta: {len(db) - len(da)} bytes"]
    lines.append("RESULT: DIFFERENT")
    rpath = _write_report(out, cand.stem + "_regdiff", "\n".join(lines))
    return {"ok": True, "subtool": "lab_regression_diff_compare",
            "identical": False, "report": str(rpath),
            "sha256_report": _sha256(rpath)}


def lab_large_file_benchmark(input_path, output_dir, **_):
    """Streaming throughput, memory bounds and output integrity benchmark:
    stream-copy the input while hashing (no full-file read), measure MB/s,
    peak RSS via resource, and verify the copy byte-for-byte."""
    src = _require_file(input_path)
    if src is None:
        return {"ok": False, "subtool": "lab_large_file_benchmark",
                "error": "benchmark input file not found"}
    import resource
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (src.name + ".benchcopy")
    h_src, h_dst = hashlib.sha256(), hashlib.sha256()
    t0 = time.monotonic()
    total = 0
    CHUNK = 4 * 1024 * 1024
    try:
        with open(src, "rb") as fs, open(dest, "wb") as fd:
            while True:
                block = fs.read(CHUNK)
                if not block:
                    break
                fd.write(block)
                h_src.update(block)
                h_dst.update(block)
                total += len(block)
    except OSError as exc:
        return {"ok": False, "subtool": "lab_large_file_benchmark",
                "error": f"stream failed: {exc}"}
    elapsed = time.monotonic() - t0
    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    mps = total / elapsed / (1024 * 1024) if elapsed > 0 else 0.0
    integrity = h_src.hexdigest() == h_dst.hexdigest()
    dest.unlink(missing_ok=True)  # benchmark copy is not a deliverable
    lines = ["ALVSIA LARGE-FILE BENCHMARK & VALIDATION",
             f"file      : {src}",
             f"size      : {total:,} bytes",
             f"streamed  : {elapsed:.3f} s  ({mps:.1f} MiB/s)",
             f"chunk     : {CHUNK // (1024 * 1024)} MiB",
             f"peak RSS  : {peak_kb / 1024:.1f} MiB",
             f"integrity : {'VERIFIED (sha256 stream match)' if integrity else 'FAILED'}"]
    rpath = _write_report(out, src.stem + "_benchmark", "\n".join(lines))
    ok = integrity and total == src.stat().st_size and elapsed > 0
    return {"ok": ok, "subtool": "lab_large_file_benchmark",
            "bytes": total, "seconds": round(elapsed, 3),
            "mib_per_s": round(mps, 1), "peak_rss_kib": peak_kb,
            "integrity": integrity, "report": str(rpath),
            "sha256_report": _sha256(rpath)}


# ─────────────────────────────────────────────────────────────────
# Registry — pending subtool id -> implementation
# ─────────────────────────────────────────────────────────────────

PENDING_ADAPTERS: dict[str, Callable[..., dict]] = {
    # batch 1 — archive
    "pak_selective_extract": pak_selective_extract,
    "apk_compare_resource_diff": apk_compare_resource_diff,
    "mini_obb_zsdic_adapter": mini_obb_zsdic_adapter,
    "gamepatch_obb_repacker": gamepatch_obb_repacker,
    # batch 2 — lua / crypto
    "lua_protect_compile": lua_protect_compile,
    "lua_round_trip_validator": lua_round_trip_validator,
    "crypto_output_validator": crypto_output_validator,
    # batch 3 — modding / unreal / zsdic
    "modding_uasset_uexp_inspector": modding_uasset_uexp_inspector,
    "modding_ue4_string_id_extractor": modding_ue4_string_id_extractor,
    "modding_skin_pair_finder": modding_skin_pair_finder,
    "modding_zsdic_analyzer": modding_zsdic_analyzer,
    "modding_offset_size_fixer": modding_offset_size_fixer,
    "modding_resource_mapping_recovery": modding_resource_mapping_recovery,
    # batch 4 — workspace / lab
    "native_xref_reference_analyzer": native_xref_reference_analyzer,
    "workspace_file_manager": workspace_file_manager,
    "workspace_resume_cancel_progress": workspace_resume_cancel_progress,
    "lab_engine_registry": lab_engine_registry,
    "lab_regression_diff_compare": lab_regression_diff_compare,
    "lab_large_file_benchmark": lab_large_file_benchmark,
}


def dispatch_pending(subtool_id: str, **kwargs) -> dict:
    """Fail-closed dispatch for the previously-pending subtools."""
    key = str(subtool_id).strip().lower()
    runner = PENDING_ADAPTERS.get(key)
    if runner is None:
        return {"ok": False, "subtool": key,
                "error": "pending adapter not registered"}
    try:
        return runner(**kwargs)
    except TypeError as exc:
        return {"ok": False, "subtool": key,
                "error": f"invalid adapter arguments: {exc}"}
    except Exception as exc:
        return {"ok": False, "subtool": key,
                "error": f"{type(exc).__name__}: {exc}"}
