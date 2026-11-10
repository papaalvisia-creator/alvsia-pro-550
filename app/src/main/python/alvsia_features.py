# -*- coding: utf-8 -*-
"""ALVSIA PRO 5.5 — features: LUA (unluac jar), helpers."""
from __future__ import annotations
import os
import hashlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from lua_engine import detect_lua, analyze_lua, decompile_lua, validate_lua_source, transform_bgmi_lua, unwrap_lua_container
from lua_engine.engine import clean_lua_source
try:
    from lua_engine.decompiler53 import decompile_file as _decompile53_file
except Exception as _e53:
    _decompile53_file = None
try:
    from lua_output_validator import validate_decompile_text, classify_bytes
except Exception:
    validate_decompile_text = None
    classify_bytes = None


def _find_java():
    for c in ("java", "/data/data/com.termux/files/usr/bin/java"):
        if shutil.which(c) or Path(c).is_file():
            return c if Path(c).is_file() or shutil.which(c) else None
    # Android: try common paths
    for c in (
        "/system/bin/java",
        "/data/data/com.alvsia.pro/files/java/bin/java",
    ):
        if Path(c).is_file():
            return c
    return shutil.which("java")


def _pick_jar(jars_dir, prefer=("unluac_2025_12_23.jar", "unluac_pro.jar", "unluac_patched.jar", "unluac.jar")):
    jars_dir = Path(jars_dir) if jars_dir else None
    if jars_dir and jars_dir.is_dir():
        for name in prefer:
            p = jars_dir / name
            if p.is_file() and p.stat().st_size > 1000:
                return p
        for p in jars_dir.glob("unluac*.jar"):
            if p.stat().st_size > 1000:
                return p
    return None


def _prepare_lua_input(input_path, out_dir):
    input_path = Path(input_path); out_dir = Path(out_dir)
    raw = input_path.read_bytes()
    if not raw.startswith(b"\x78\xda"):
        return input_path, None
    payload, ci = unwrap_lua_container(raw)
    if not payload.startswith((b"\x1bLua", b"\x1bLJ")):
        raise ValueError("compressed input did not contain Lua/LuaJIT bytecode")
    normalized = out_dir / (input_path.stem + "_unwrapped.luac")
    normalized.write_bytes(payload)
    return normalized, ci

def run_unluac(input_path, out_dir, jars_dir=None, mode="decompile"):
    """Decompile Lua bytecode with strict exit/output validation and container unwrapping."""
    input_path = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        normalized, ci = _prepare_lua_input(input_path, out_dir)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    jar = _pick_jar(jars_dir)
    if jar is None:
        return {"ok": False, "error": "unluac jar missing — place unluac.jar in jars dir",
                **({"unwrapped": str(normalized)} if ci else {})}
    java = _find_java()
    if not java:
        dest = out_dir / (input_path.stem + "_NEED_JAVA.txt")
        dest.write_text("Java runtime unavailable.\nJar: %s\nInput: %s\n" % (jar, normalized), encoding="utf-8")
        return {"ok": False, "error": "Java runtime not found on device", "jar": str(jar),
                "hint": str(dest), **({"unwrapped": str(normalized)} if ci else {})}
    out_lua = out_dir / (input_path.stem + "_decompiled.lua")
    try:
        proc = subprocess.run([java, "-jar", str(jar), str(normalized)],
                              capture_output=True, timeout=120)
        stdout = (proc.stdout or b"").decode("utf-8", "replace")
        stderr = (proc.stderr or b"").decode("utf-8", "replace")
        if proc.returncode != 0 or not stdout.strip():
            out_lua.unlink(missing_ok=True)
            return {"ok": False, "error": stderr.strip()[:1200] or "unluac returned no source",
                    "code": proc.returncode, "jar": str(jar),
                    **({"unwrapped": str(normalized), "container": ci.format} if ci else {})}
        out_lua.write_text(stdout, encoding="utf-8")
        valid, msg = validate_lua_source(out_lua)
        if not valid:
            out_lua.unlink(missing_ok=True)
            return {"ok": False, "error": "Lua validation failed: " + msg, "code": proc.returncode,
                    "jar": str(jar), **({"unwrapped": str(normalized)} if ci else {})}
        return {"ok": True, "out": str(out_lua), "code": proc.returncode, "jar": str(jar),
                "validation": msg, **({"unwrapped": str(normalized), "container": ci.format,
                "container_chunks": ci.chunks} if ci else {})}
    except Exception as e:
        return {"ok": False, "error": str(e), "jar": str(jar),
                **({"unwrapped": str(normalized)} if ci else {})}


def run_lua_xor(input_path, out_dir, key_hex=None):
    """XOR preview against normalized Lua payload when a container is present."""
    input_path=Path(input_path); out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    try: normalized, ci = _prepare_lua_input(input_path,out_dir)
    except Exception as exc: return {"ok":False,"error":str(exc)}
    data=normalized.read_bytes()
    try: key=bytes.fromhex(key_hex) if key_hex else bytes([0x11,0x21,0x36,0x47])
    except ValueError: return {"ok":False,"error":"invalid XOR key hex"}
    out=bytes(data[i]^key[i%len(key)] for i in range(len(data)))
    dest=out_dir/(input_path.name+".xor"); dest.write_bytes(out)
    return {"ok":True,"out":str(dest),"bytes":len(out),**({"container":ci.format,"normalized":str(normalized)} if ci else {})}


def run_zip_tree(src_dir, dest_zip):
    src_dir = Path(src_dir)
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in src_dir.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(src_dir).as_posix())
    return {"ok": True, "out": str(dest_zip)}


def run_unzip(src, dest_dir):
    """Extract ZIP entries only beneath dest_dir; reject traversal and symlinks."""
    src = Path(src)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    root = dest_dir.resolve()
    with zipfile.ZipFile(src, "r") as z:
        for info in z.infolist():
            # ZIP paths use '/', but reject Windows separators too.
            name = info.filename.replace("\\", "/")
            member = Path(name)
            if member.is_absolute() or any(part == ".." for part in member.parts):
                raise ValueError(f"unsafe ZIP entry path: {info.filename!r}")
            target = (root / member).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"ZIP entry escapes destination: {info.filename!r}")
            # ZIP archives can encode Unix symlinks in external attributes.
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"symlink ZIP entry is not allowed: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info, "r") as src_file, target.open("wb") as dst_file:
                shutil.copyfileobj(src_file, dst_file, length=1024 * 1024)
    n = sum(1 for item in root.rglob("*") if item.is_file())
    return {"ok": True, "out": str(root), "files": n}


def run_hash_file(path, out_txt=None):
    import hashlib
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "error": "input file not found"}
    size = path.stat().st_size
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(4 * 1024 * 1024)
            if not block:
                break
            md5.update(block)
            sha1.update(block)
            sha256.update(block)
    lines = [
        f"file={path}",
        f"size={size}",
        f"md5={md5.hexdigest()}",
        f"sha1={sha1.hexdigest()}",
        f"sha256={sha256.hexdigest()}",
    ]
    report = "\n".join(lines)
    if out_txt:
        Path(out_txt).write_text(report, encoding="utf-8")
    return {"ok": True, "report": report, "out": str(out_txt) if out_txt else None}


def run_string_scan(path, out_txt=None, min_len=4):
    from lua_string_recover import _iter_ascii_file
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "error": "input file not found"}
    found_count = 0
    retained = []
    for value in _iter_ascii_file(path, min_len=min_len):
        found_count += 1
        if len(retained) < 5000:
            retained.append(value)
    if out_txt:
        Path(out_txt).write_text("\n".join(retained), encoding="utf-8")
    return {"ok": True, "count": found_count, "out": str(out_txt) if out_txt else None}


def run_lua_bytecode_strings(input_path, out_dir):
    """Extract printable strings from normalized Lua bytecode/container."""
    input_path=Path(input_path); out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    try: normalized, ci = _prepare_lua_input(input_path,out_dir)
    except Exception as exc: return {"ok":False,"error":str(exc)}
    data=normalized.read_bytes(); strings=[]; cur=bytearray()
    for b in data:
        if 32<=b<127 or b in (9,): cur.append(b)
        else:
            if len(cur)>=4: strings.append(cur.decode("ascii","ignore"))
            cur.clear()
    if len(cur)>=4: strings.append(cur.decode("ascii","ignore"))
    seen=set(); uniq=[]
    for value in strings:
        if value not in seen: seen.add(value); uniq.append(value)
    dest=out_dir/(input_path.stem+"_strings.txt")
    payload, scrubbed = scrub_foreign_branding("\n".join(uniq[:8000]))
    dest.write_text(payload,encoding="utf-8")
    return {"ok":True,"mode":"strings_fallback","lua_header":data[:4]==b"\x1bLua",
            "count":len(uniq),"out":str(dest),"watermarks_scrubbed":scrubbed,
            "note":"Full decompile requires a compatible Lua decompiler; strings were extracted from normalized payload",
            **({"container":ci.format,"container_chunks":ci.chunks,"normalized":str(normalized)} if ci else {})}


def is_luas_header(data: bytes) -> bool:
    """True if file starts with Lua 5.3-style header (including LuaS / slua variants)."""
    if len(data) < 12:
        return False
    if data[:4] != b"\x1bLua":
        return False
    return data[4] in (0x53, 0x51, 0x52, 0x54) or data[4:5] == b"S"


def extract_lua_constants(input_path, out_dir, max_strings=5000):
    """Extract likely constants from Lua bytecode, including wrapped containers."""
    input_path=Path(input_path); out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    try: normalized, ci = _prepare_lua_input(input_path,out_dir)
    except Exception as exc: return {"ok":False,"error":str(exc)}
    data=normalized.read_bytes()
    if not is_luas_header(data): return {"ok":False,"error":"not a Lua header","magic":data[:8].hex()}
    strings=[]; i=12; n=len(data)
    while i+5<n:
        ln=int.from_bytes(data[i:i+4],"little")
        if 2<=ln<=4096 and i+4+ln<=n:
            chunk=data[i+4:i+4+ln]
            if chunk and chunk[-1]==0: chunk=chunk[:-1]
            if chunk and all(32<=b<127 or b in (9,10,13) for b in chunk):
                try:
                    value=chunk.decode("utf-8","strict")
                    if len(value)>=2: strings.append(value); i+=4+ln; continue
                except UnicodeDecodeError: pass
        i+=1
    cur=bytearray()
    for b in data:
        if 32<=b<127: cur.append(b)
        else:
            if len(cur)>=4: strings.append(cur.decode("ascii","ignore"))
            cur.clear()
    if len(cur)>=4: strings.append(cur.decode("ascii","ignore"))
    seen=set(); uniq=[]
    for value in strings:
        if value not in seen: seen.add(value); uniq.append(value)
    dest=out_dir/(input_path.stem+"_constants.txt")
    payload, scrubbed = scrub_foreign_branding("\n".join(uniq[:max_strings]))
    dest.write_text(payload,encoding="utf-8")
    return {"ok":True,"mode":"lua_constants","count":len(uniq),"out":str(dest),"header":data[:16].hex(),
            "watermarks_scrubbed":scrubbed,
            **({"container":ci.format,"container_chunks":ci.chunks,"normalized":str(normalized)} if ci else {})}


def run_lua_multi_xor(input_path, out_dir, keys=None):
    """
    Try several common single-byte and short multi-byte XOR keys on body after header.
    Writes best candidates (highest printable ratio) for manual inspection / re-unluac.
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        normalized, ci = _prepare_lua_input(input_path, out_dir)
    except Exception:
        normalized, ci = input_path, None
    data = bytearray(normalized.read_bytes())
    if len(data) < 32:
        return {"ok": False, "error": "file too small"}

    # Lua 5.1-5.4 headers are followed by the main-function upvalue count.
    header_len = 34 if is_luas_header(data) else 0
    body = data[header_len:]

    if keys is None:
        keys = [
            bytes([0x11, 0x21, 0x36, 0x47]),
            bytes([0x18]),
            bytes([0x55]),
            bytes([0xAA]),
            bytes([0x5A]),
            bytes([0x00, 0x01, 0x02, 0x03]),
            b"ALVSIA",
            b"PUBGM",
            b"Tencent",
        ]

    results = []
    for key in keys:
        out = bytearray(body)
        for i in range(len(out)):
            out[i] ^= key[i % len(key)]
        printable = sum(1 for b in out if 32 <= b < 127)
        ratio = printable / max(1, len(out))
        cand = bytes(data[:header_len]) + bytes(out)
        name = f"{input_path.stem}_xor_{key.hex()[:16]}.bin"
        dest = out_dir / name
        dest.write_bytes(cand)
        results.append({"key": key.hex(), "ratio": round(ratio, 4), "out": str(dest)})

    results.sort(key=lambda x: -x["ratio"])
    return {"ok": True, "mode": "multi_xor", "candidates": results[:8], "best": results[0] if results else None}


from lua_intelligence import analyze_file, IntelligenceConfig

def _run_lua_smart_legacy(input_path, out_dir, jars_dir=None):
    """
    Unified Smart Lua pipeline:
    1) identify source, bytecode dialect, container and confidence
    2) run protection-pattern detection only (no standard engine execution)
    3) pass pattern recovery and compatible engines into one candidate selector
    4) validate candidates, retain valid alternatives, and report partial recovery honestly
    5) use constants/strings/XOR only as clearly labelled fallback diagnostics
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = input_path.read_bytes()
    report = {"file": str(input_path), "size": len(data), "steps": []}
    info = detect_lua(input_path)
    if info.kind == "unknown":
        report["steps"].append({
            "step": "detect", "ok": False,
            "note": "standard Lua signature not recognized; checking known protection patterns before fallback",
            "format": info.format, "confidence": info.confidence,
        })
    else:
        report["steps"].append({"step": "detect", "ok": True, "format": info.format,
                                 "version": info.version, "wrapped": info.wrapped,
                                 "container": info.container, "chunks": info.container_chunks})

    # Normalize a comment-prefixed Lua/LuaJIT payload for every downstream
    # engine. The original input remains untouched and is still used for
    # independent strings/constants recovery.
    work_input = input_path
    prefix_note = next((n for n in info.notes if n.startswith("comment_prefix_offset=")), None)
    if prefix_note:
        try:
            offset = int(prefix_note.split("=", 1)[1])
            if offset <= 0 or offset >= len(data):
                raise ValueError("invalid embedded Lua payload offset")
            normalized_path = out_dir / (input_path.stem + "_embedded_payload.luac")
            normalized_path.write_bytes(data[offset:])
            work_input = normalized_path
            report["steps"].append({
                "step": "extract_comment_prefixed_payload",
                "ok": True,
                "offset": offset,
                "payload_size": normalized_path.stat().st_size,
                "out": str(normalized_path),
            })
        except Exception as exc:
            report["steps"].append({"step": "extract_comment_prefixed_payload",
                                    "ok": False, "error": str(exc)})
            work_input = input_path

    # ── Step 1: recursively unwrap recognized Lua containers ────────────────
    # Each layer is materialized separately and re-detected. We stop on a
    # stable payload, a repeated digest, or the configured depth budget.
    max_layers = max(1, min(16, int(os.environ.get("ALVSIA_LUA_MAX_UNWRAP_LAYERS", "8"))))
    seen_payloads = set()
    current_path = work_input
    for layer_index in range(max_layers):
        try:
            current_data = current_path.read_bytes()
            digest = hashlib.sha256(current_data).hexdigest()
            if digest in seen_payloads:
                report["steps"].append({
                    "step": "unwrap_stop",
                    "ok": False,
                    "reason": "repeated-payload",
                    "layer": layer_index,
                })
                break
            seen_payloads.add(digest)
            current_info = detect_lua(current_path)
            if not current_info.wrapped:
                break
            payload, ci = unwrap_lua_container(current_data)
            if not payload or payload == current_data:
                report["steps"].append({
                    "step": "unwrap_stop",
                    "ok": False,
                    "reason": "empty-or-unchanged-payload",
                    "layer": layer_index,
                })
                break
            unwrapped_path = out_dir / (
                input_path.stem + f"_unwrapped_l{layer_index + 1}.luac"
            )
            unwrapped_path.write_bytes(payload)
            current_path = unwrapped_path
            work_input = unwrapped_path
            report["steps"].append({
                "step": "unwrap",
                "ok": True,
                "layer": layer_index + 1,
                "container": ci.format,
                "chunks": ci.chunks,
                "bytes": len(payload),
                "out": str(unwrapped_path),
            })
        except Exception as exc:
            report["steps"].append({
                "step": "unwrap",
                "ok": False,
                "layer": layer_index + 1,
                "error": f"{type(exc).__name__}: {exc}",
            })
            break

    # ── Protected-format preflight (diagnostics only) ────────────────────
    vm_partial_seen = False
    protected_partial_seen = False
    pattern_candidate = None
    try:
        from lua_engine.streaming_decompiler import decompile_large
        pattern_result = decompile_large(
            work_input, out_dir, jars_dir=jars_dir, preflight_only=True
        )
        report["steps"].append({
            "step": "protected_pattern_preflight",
            **pattern_result,
        })
        if pattern_result.get("ok") and pattern_result.get("recovered") is True:
            candidate = Path(str(pattern_result.get("out") or ""))
            if candidate.is_file() and candidate.suffix.lower() == ".lua":
                pattern_candidate = candidate
                report["steps"].append({
                    "step": "pattern_candidate_staged",
                    "ok": True,
                    "pattern_id": pattern_result.get("pattern_id"),
                    "file": str(candidate),
                })
        if pattern_result.get("recovered") is False:
            protected_partial_seen = True
            vm_partial_seen = pattern_result.get("mode") == "bgmi_vm_partial"
            report["steps"].append({
                "step": "vm_partial_not_final" if vm_partial_seen else "protected_partial_not_final",
                "ok": False,
                "note": "Protection analysis is diagnostic only; compatible decompiler engines will still be tried",
                "pattern_id": pattern_result.get("pattern_id"),
                "protos_parsed": pattern_result.get("protos_parsed", 0),
                "main_instructions": pattern_result.get("main_code_count", 0),
                "main_constants": pattern_result.get("main_const_count", 0),
                "parse_errors": pattern_result.get("parse_errors", 0),
            })
    except Exception as exc:
        report["steps"].append({
            "step": "protected_pattern_preflight",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        })

    # ── One engine registry and one candidate-selection pipeline ──────────
    try:
        from lua_engine.orchestrator import (
            EngineSpec, build_engine_registry, run_decompiler_pipeline,
        )
        normalized_info = detect_lua(work_input)
        registry = build_engine_registry(normalized_info, jars_dir=jars_dir)
        if pattern_candidate is not None:
            def _run_pattern_candidate(_src, dst, candidate=pattern_candidate):
                shutil.copy2(candidate, dst)
                return True, "protection-pattern recovery candidate"
            registry.append(EngineSpec(
                "protected_pattern_recovery",
                (normalized_info.format,),
                _run_pattern_candidate,
                -10,
            ))
        out_lua = out_dir / (input_path.stem + "_decompiled.lua")
        pipeline = run_decompiler_pipeline(
            work_input, out_lua, normalized_info,
            jars_dir=jars_dir, registry=registry,
        )
        if pattern_candidate is not None and pipeline.get("selected_engine") == "source_passthrough":
            protected_partial_seen = True
            report["steps"].append({
                "step": "pattern_candidate_rejected",
                "ok": False,
                "note": "Recovered candidate did not validate; returning wrapper source only as partial output",
            })
        if pattern_candidate is not None:
            pattern_candidate.unlink(missing_ok=True)
        report["steps"].append({"step": "engine_orchestrator", **pipeline})
        if pipeline.get("ok"):
            report["ok"] = True
            report["vm_obfuscated"] = bool(vm_partial_seen)
            report["source_recovered"] = not protected_partial_seen
            report["artifact_kind"] = (
                "vm_wrapper_source" if vm_partial_seen
                else "protected_wrapper_source" if protected_partial_seen
                else "lua_source"
            )
            report["final_status"] = "PARTIAL" if protected_partial_seen else "SUCCESS"
            return {
                "ok": True,
                "mode": (
                    "smart_orchestrated_vm_wrapper" if vm_partial_seen
                    else "smart_orchestrated_partial" if protected_partial_seen
                    else "smart_orchestrated"
                ),
                "out": pipeline.get("out"),
                "selected_engine": pipeline.get("selected_engine"),
                **report,
            }
    except Exception as exc:
        report["steps"].append({
            "step": "engine_orchestrator",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        })

    # ── Step 4: partial recovery ─────────────────────────────────────────────
    cr = extract_lua_constants(work_input, out_dir)
    report["steps"].append({"step": "constants", **cr})

    sr = run_lua_bytecode_strings(work_input, out_dir)
    report["steps"].append({"step": "strings", **sr})

    xr = run_lua_multi_xor(work_input, out_dir)
    report["steps"].append({"step": "multi_xor", **{k: xr[k] for k in ("ok", "mode", "best") if k in xr}})

    # Honest final status: never SUCCESS decompile without validated source
    final_status = "PARTIAL"
    if validate_decompile_text is not None:
        # scan any .lua written in out_dir
        for cand in out_dir.glob("*_decompiled.lua"):
            v = validate_decompile_text(cand.read_text(encoding="utf-8", errors="replace"))
            report["steps"].append({"step": "validate_source", "file": str(cand), **v})
            # This legacy text classifier is diagnostic only. It cannot
            # upgrade PARTIAL to SUCCESS: only a concrete engine candidate
            # accepted by the Smart Lua validator may do that.
        else:
            # strings file is recovery only
            for cand in out_dir.glob("*_strings.txt"):
                v = validate_decompile_text(cand.read_text(encoding="utf-8", errors="replace"))
                report["steps"].append({"step": "validate_strings", "file": str(cand), **v})
            final_status = "PARTIAL"

    stage_path = out_dir / (input_path.stem + "_STAGE_REPORT.txt")
    lines = [
        "ALVISIA PRO LUA STAGE REPORT",
        "file=%s" % input_path,
        "size=%s" % report.get("size"),
        "final_status=%s" % final_status,
        "mode=smart_fallback",
        "note=all compatible decompiler engines failed validation — recovery artifacts only",
        "",
    ]
    for st in report.get("steps") or []:
        lines.append(str(st))
    stage_path.write_text("\n".join(lines), encoding="utf-8")
    report["stage_report"] = str(stage_path)
    report["final_status"] = final_status

    return {
        "ok": final_status == "SUCCESS",
        "mode": "smart_fallback",
        "final_status": final_status,
        "note": "PARTIAL: detect/unpack/strings may exist; decompile source NOT validated",
        **report,
    }





def run_lua_smart(input_path, out_dir, jars_dir=None):
    """Program-intelligence front door with legacy engine orchestration as a validated adapter."""
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Multi-GB inputs must not fall through to the legacy whole-file pipeline.
    # Containers are inflated to disk in bounded chunks; only a resulting Lua
    # payload within the parser budget is passed to the in-memory legacy engines.
    max_in_memory = int(os.environ.get(
        "ALVSIA_LUA_MAX_IN_MEMORY_BYTES", str(256 * 1024 * 1024)
    ))
    max_in_memory = max(16 * 1024 * 1024, min(max_in_memory, 512 * 1024 * 1024))
    input_size = input_path.stat().st_size if input_path.is_file() else 0
    if input_size > max_in_memory:
        from lua_engine.streaming_decompiler import (
            preflight_magic, stream_inflate_zlib, stream_inflate_deflate_container,
        )
        from lua_string_recover import recover_strings_file

        fmt = preflight_magic(input_path)
        work_input = input_path
        unwrap_report = None
        streamed_path = out_dir / (input_path.stem + "_stream_unwrapped.luac")
        try:
            if fmt == "zlib":
                ok, message = stream_inflate_zlib(input_path, streamed_path)
                unwrap_report = {"ok": ok, "format": fmt, "message": message}
                if ok:
                    work_input = streamed_path
            elif fmt == "chunked_deflate":
                ok, message = stream_inflate_deflate_container(input_path, streamed_path)
                unwrap_report = {"ok": ok, "format": fmt, "message": message}
                if ok:
                    work_input = streamed_path
            elif fmt == "gzip":
                import gzip
                total = 0
                with gzip.open(input_path, "rb") as source, streamed_path.open("wb") as target:
                    while True:
                        block = source.read(4 * 1024 * 1024)
                        if not block:
                            break
                        total += len(block)
                        if total > 4 * 1024 * 1024 * 1024:
                            raise ValueError("gzip output exceeds 4 GiB streaming cap")
                        target.write(block)
                work_input = streamed_path
                unwrap_report = {"ok": True, "format": fmt, "bytes_out": total}
        except Exception as exc:
            unwrap_report = {"ok": False, "format": fmt,
                             "error": f"{type(exc).__name__}: {exc}"}

        if work_input != input_path and work_input.stat().st_size <= max_in_memory:
            try:
                legacy = _run_lua_smart_legacy(work_input, out_dir, jars_dir=jars_dir)
                legacy["input_bytes"] = input_size
                legacy["stream_unwrap"] = unwrap_report
                legacy["mode"] = "smart_streaming_large_input"
                return legacy
            except Exception as exc:
                decompile_report = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        else:
            decompile_report = {
                "ok": False,
                "error": (
                    f"input/payload exceeds in-memory Lua parser budget ({max_in_memory} bytes); "
                    "large-file scanning and container inflation remain streaming, "
                    "but full Lua 5.3 source reconstruction is not yet streaming"
                ),
            }
        try:
            recovery = recover_strings_file(
                work_input if work_input.is_file() else input_path,
                out_dir / "large_file_recovery", input_path.stem,
            )
        except Exception as exc:
            recovery = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return {
            "ok": False,
            "mode": "smart_streaming_large_input",
            "final_status": "PARTIAL",
            "input_bytes": input_size,
            "stream_unwrap": unwrap_report,
            "decompile": decompile_report,
            "streaming_recovery": recovery,
            "note": (
                "Large input was processed without whole-file RAM loading. "
                "Recovery artifacts are diagnostic; no full decompile SUCCESS is claimed."
            ),
        }

    intelligence = analyze_file(
        input_path, out_dir / "intelligence",
        IntelligenceConfig(
            max_depth=int(os.environ.get("ALVSIA_LUA_MAX_DEPTH", "12")),
            max_artifacts=int(os.environ.get("ALVSIA_LUA_MAX_ARTIFACTS", "128")),
            max_file_bytes=int(os.environ.get("ALVSIA_LUA_MAX_BYTES", str(256 * 1024 * 1024))),
            max_elapsed_seconds=float(os.environ.get("ALVSIA_LUA_MAX_SECONDS", "45")),
        ),
    )
    try:
        legacy = _run_lua_smart_legacy(input_path, out_dir, jars_dir=jars_dir)
    except Exception as exc:
        legacy = {"ok": False, "final_status": "FAILED",
                  "error": f"{type(exc).__name__}: {exc}"}
    result = dict(legacy)
    result["intelligence"] = intelligence.to_dict()
    result["intelligence_report"] = intelligence.report_path
    result["layer_count"] = len(intelligence.artifacts)
    result["layer_graph_root"] = intelligence.root_id
    result["analysis_status"] = intelligence.status

    # Candidate fusion is an explicit validation layer: engine output is only
    # considered a recovery candidate until structural evidence is measured.
    try:
        from lua_intelligence.candidates import score_source_candidate, candidates_json
        candidates = []
        out_value = result.get("out")
        if out_value and Path(str(out_value)).is_file():
            candidates.append(score_source_candidate(
                Path(str(out_value)),
                dialect=str(result.get("format") or result.get("version") or "unknown"),
                engine=str(result.get("selected_engine") or "legacy-smart"),
            ))
        if candidates:
            result["candidate_manifest"] = candidates_json(candidates)
            best = max(candidates, key=lambda c: c.rank())
            result["candidate_score"] = best.score
            result["candidate_status"] = best.status
            manifest = out_dir / (input_path.stem + "_candidates.json")
            import json
            manifest.write_text(
                json.dumps(result["candidate_manifest"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result["candidate_manifest_path"] = str(manifest)
    except Exception as exc:
        # Candidate scoring must never turn a valid legacy result into a crash.
        result["candidate_fusion_error"] = f"{type(exc).__name__}: {exc}"
    return result

# ---------------------------------------------------------------------------
# LUA ENGINE v5.5 — unified detection / analysis / fallback
# ---------------------------------------------------------------------------

def run_lua_universal(input_path, out_dir, jars_dir=None):
    """Single deterministic LUA entry point used by the Android bridge."""
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        analysis = analyze_lua(input_path, out_dir)
        if not analysis.get("ok"):
            # Unknown input is not a successful LUA operation.
            return analysis

        info = detect_lua(input_path)
        report_path = out_dir / (input_path.stem + "_analysis.json")
        import json
        report_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

        result = decompile_lua(input_path, out_dir, jars_dir=jars_dir)
        result["analysis"] = analysis
        result["report"] = str(report_path)

        # A successful decompile must have a validated Lua source file.
        if result.get("ok") and result.get("out"):
            valid, msg = validate_lua_source(result["out"])
            result["validation"] = msg
            if not valid:
                result["ok"] = False
                result["error"] = "output validation failed: " + msg
                try:
                    Path(result["out"]).unlink()
                except Exception:
                    pass
        if not result.get("ok"):
            # Static artifacts remain useful even when no decompiler is available.
            strings = run_lua_bytecode_strings(input_path, out_dir)
            result["fallback_strings"] = strings
            result["note"] = (
                "Decompile unavailable; analysis/report/string artifacts were generated. "
                "No false SUCCESS was reported."
            )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc), "mode": "universal"}

def run_lua_analysis(input_path, out_dir):
    input_path = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    import json
    try:
        report = analyze_lua(input_path, out_dir)
        dest = out_dir / (input_path.stem + "_analysis.json")
        dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        report["out"] = str(dest)
        return report
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def run_lua_clean(input_path, out_dir):
    input_path = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if detect_lua(input_path).kind != "source":
        return {"ok": False, "error": "source Lua text is required for cleanup"}
    dest = out_dir / (input_path.stem + "_clean.lua")
    try:
        return clean_lua_source(input_path, dest)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def run_pubg_lua_decrypt(input_path, out_dir, key_hex=None):
    """Decode the ALVISIA/BGMI Lua bytecode transform when an explicit key is supplied."""
    input_path = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    key_hex = key_hex or os.environ.get("SERVER_LUA_XOR_KEY_HEX", "").strip()
    key_file = out_dir.parent.parent / "LUA_TOOL" / "lua_xor_key.txt"
    if not key_hex and key_file.is_file():
        key_hex = key_file.read_text(encoding="utf-8", errors="replace").strip()
    if not key_hex:
        return {"ok": False, "error": "Lua XOR key is required for BGMI transform"}
    try:
        key = bytes.fromhex(key_hex)
    except ValueError:
        return {"ok": False, "error": "Lua XOR key is not valid hexadecimal"}
    try:
        raw = input_path.read_bytes()
        out = transform_bgmi_lua(raw, key, decrypt=True)
        dest = out_dir / (input_path.stem + "_decrypted.luac")
        dest.write_bytes(out)
        return {
            "ok": True, "mode": "bgmi-lua-transform",
            "out": str(dest), "bytes": len(out),
            "lua_header": out[:8].hex(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

# ---------------------------------------------------------------------------
# REBRAND — string replace brand/watermark/channel (NO network, NO bot token)
# ---------------------------------------------------------------------------

# Watermark strings that the rebrand tool searches for and replaces.
# Only ALVSIA-tier brand strings are listed here.
KNOWN_BRANDS = [
    "ALVSIA",
    "ALVSIA PRO",
    "ALVSIA PREMIUM",
    "ALVSIA PRIVATE TOOL",
    "ALVSIA PRO MAX",
    "t.me/ALVSIA_PRO",
    "t.me/ALVSIA",
]

DEFAULT_BRAND = "@ALVSIA_PRO"
DEFAULT_CHANNEL = "t.me/ALVSIA_PRO"
DEFAULT_WATERMARK = "@ALVSIA_PRO | t.me/ALVSIA_PRO"

# Third-party credit lines that ship inside imported scripts. ALVSIA never
# re-publishes another channel's branding, so recovered report text is
# rewritten to the owner's brand before it is written to OUT/.
FOREIGN_BRAND_TOKENS = (
    "SRC_HUB",
    "SRC HUB",
    "SRCHUB",
    "XTHrlen",
    "XThrlen",
    "XTHRLEN",
    "ALECTO",
    "Alecto",
    "Original" + "OnwerALV",
    "Kapten" + " Jack",
)
FOREIGN_CHANNEL_TOKENS = (
    "t.me/SRC_HUB",
    "t.me/XTHrlen",
    "t.me/XThrlen",
    "t.me/ALECTO",
    "https://t.me/SRC_HUB",
    "https://t.me/XTHrlen",
    "https://t.me/XThrlen",
    "https://t.me/ALECTO",
    "t.me/" + "Original" + "OnwerALV",
    "https://t.me/" + "Original" + "OnwerALV",
)


def scrub_foreign_branding(text, brand=DEFAULT_BRAND, channel=DEFAULT_CHANNEL):
    """Replace third-party channel/credit tokens with the owner's branding.

    Only report text (strings/constants dumps) is rewritten; the staged input
    is never modified. Returns ``(cleaned_text, replacements)``.
    """
    if not text:
        return text, 0
    channel_at = "@" + channel.split("/")[-1].lstrip("@")
    replacements = 0
    # Longest / most specific forms first so "@SRC_HUB" never degrades into
    # "@ALVSIA PRO" via the bare-token pass below.
    for token in sorted(FOREIGN_CHANNEL_TOKENS, key=len, reverse=True):
        if token in text:
            replacements += text.count(token)
            text = text.replace(token, "https://" + channel)
    for token in ("@SRC_HUB", "@XTHrlen", "@XThrlen", "@ALECTO", "@" + "Original" + "OnwerALV"):
        if token in text:
            replacements += text.count(token)
            text = text.replace(token, channel_at)
    for token in FOREIGN_BRAND_TOKENS:
        if token in text:
            replacements += text.count(token)
            text = text.replace(token, brand)
    return text, replacements


def scrub_output_text_files(out_root, max_file_bytes=8 * 1024 * 1024):
    """Normalize known legacy credits in generated OUT text artifacts only.

    Inputs under IN/WORK and binary assets are never touched.
    """
    root = Path(out_root) / "OUT"
    allowed = {".txt", ".json", ".csv", ".md", ".log", ".lua", ".xml", ".ini", ".cfg"}
    stats = {"files": 0, "replacements": 0}
    if not root.is_dir():
        return stats
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in allowed:
            continue
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            original = path.read_bytes()
            decoded = original.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        cleaned, count = scrub_foreign_branding(decoded)
        if not count:
            continue
        fd, temp_name = tempfile.mkstemp(prefix=".alvsia-brand-", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(cleaned.encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, str(path))
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
        stats["files"] += 1
        stats["replacements"] += count
    return stats


def _load_rebrand_config(out_root):
    """
    Manual override from WORK/rebrand_config.txt (key=value lines):
      brand=ALVSIA PRO
      channel=t.me/ALVSIA_PRO
      watermark=ALVSIA PRO | t.me/ALVSIA_PRO
    Missing keys fall back to defaults.
    """
    cfg = {
        "brand": DEFAULT_BRAND,
        "channel": DEFAULT_CHANNEL,
        "watermark": DEFAULT_WATERMARK,
    }
    p = Path(out_root) / "WORK" / "rebrand_config.txt"
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip().lower(), v.strip()
            if k in cfg and v:
                cfg[k] = v
    # keep watermark consistent if only brand/channel set
    if cfg["watermark"] == DEFAULT_WATERMARK and (
        cfg["brand"] != DEFAULT_BRAND or cfg["channel"] != DEFAULT_CHANNEL
    ):
        cfg["watermark"] = "%s | %s" % (cfg["brand"], cfg["channel"])
    return cfg


def _build_replace_map(cfg):
    """Map old brand tokens -> new brand / channel / watermark."""
    brand = cfg["brand"]
    channel = cfg["channel"]
    watermark = cfg["watermark"]
    # normalize channel forms
    ch_bare = channel.replace("https://", "").replace("http://", "").lstrip("/")
    if ch_bare.startswith("t.me/"):
        ch_at = "@" + ch_bare[5:]
        ch_url = "https://" + ch_bare
    elif ch_bare.startswith("@"):
        ch_at = ch_bare
        ch_url = "https://t.me/" + ch_bare[1:]
        ch_bare = "t.me/" + ch_bare[1:]
    else:
        ch_at = "@" + ch_bare
        ch_url = "https://t.me/" + ch_bare
        ch_bare = "t.me/" + ch_bare

    pairs = []
    # specific known full strings first (longest first)
    known_sorted = sorted(KNOWN_BRANDS, key=len, reverse=True)
    for old in known_sorted:
        low = old.lower()
        if "t.me/" in low or low.startswith("http"):
            pairs.append((old, ch_url if old.lower().startswith("http") else ch_bare))
        elif old.startswith("@"):
            pairs.append((old, ch_at if "hub" in low or "thrlen" in low or "alecto" in low else "@" + brand.replace(" ", "")))
        else:
            pairs.append((old, brand))
    # generic fallbacks
    pairs.append(("SRC_HUB", brand.replace(" ", "_")))
    pairs.append(("XThrlen", brand.replace(" ", "")))
    return pairs, watermark


def run_rebrand_scan(path, out_txt=None):
    """Scan file or directory for known brand strings. Report only."""
    path = Path(path)
    hits = []
    files = []
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = [f for f in path.rglob("*") if f.is_file() and f.stat().st_size < 50_000_000]
    else:
        return {"ok": False, "error": "path not found"}

    for f in files:
        try:
            data = f.read_bytes()
        except Exception:
            continue
        # try text decode for .lua/.txt/.ini; else raw search
        text = None
        if f.suffix.lower() in (".lua", ".txt", ".ini", ".json", ".xml", ".csv"):
            try:
                text = data.decode("utf-8")
            except Exception:
                try:
                    text = data.decode("latin-1")
                except Exception:
                    text = None
        for brand in KNOWN_BRANDS:
            b = brand.encode("utf-8")
            count = data.count(b)
            if count:
                hits.append({"file": str(f), "brand": brand, "count": count})
            if text and brand in text and not count:
                hits.append({"file": str(f), "brand": brand, "count": text.count(brand)})

    lines = ["ALVSIA REBRAND SCAN", "path=%s" % path, "hits=%s" % len(hits)]
    for h in hits[:200]:
        lines.append("%(count)s  %(brand)s  %(file)s" % h)
    report = "\n".join(lines)
    if out_txt:
        Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
        Path(out_txt).write_text(report, encoding="utf-8")
    return {"ok": True, "hits": len(hits), "details": hits[:100], "out": str(out_txt) if out_txt else None, "report": report}


def run_rebrand_file(input_path, out_dir, out_root=None, brand=None, channel=None, watermark=None):
    """
    Rebrand a single text-like file (lua/txt/ini) or binary string-replace.
    Auto defaults to ALVSIA PRO; manual via args or WORK/rebrand_config.txt.
    Does NOT add network/Telegram bot calls.
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = _load_rebrand_config(out_root or out_dir.parent.parent)
    if brand:
        cfg["brand"] = brand
    if channel:
        cfg["channel"] = channel
    if watermark:
        cfg["watermark"] = watermark
    elif brand or channel:
        cfg["watermark"] = "%s | %s" % (cfg["brand"], cfg["channel"])

    pairs, wm = _build_replace_map(cfg)
    data = input_path.read_bytes()
    original = data
    replaced = 0
    notes = []

    # Prefer UTF-8 text path for .lua source
    is_text = input_path.suffix.lower() in (".lua", ".txt", ".ini", ".json", ".xml", ".csv")
    if is_text:
        try:
            text = data.decode("utf-8")
            for old, new in pairs:
                if old in text:
                    c = text.count(old)
                    text = text.replace(old, new)
                    replaced += c
                    notes.append("%s x%d -> %s" % (old, c, new))
            # ensure watermark marker present once if file had any brand
            if replaced and wm and wm not in text and "WATERMARK" in text.upper():
                # leave structure; user can edit
                pass
            data = text.encode("utf-8")
        except Exception as e:
            notes.append("text-fail: %s — binary fallback" % e)
            is_text = False

    if not is_text:
        for old, new in pairs:
            ob, nb = old.encode("utf-8"), new.encode("utf-8")
            if ob in data:
                # same-length pad/truncate to avoid breaking binary offsets when possible
                if len(nb) < len(ob):
                    nb = nb + b" " * (len(ob) - len(nb))
                elif len(nb) > len(ob):
                    nb = nb[: len(ob)]
                c = data.count(ob)
                data = data.replace(ob, nb)
                replaced += c
                notes.append("%s x%d (bin len=%d)" % (old, c, len(ob)))

    dest = out_dir / (input_path.stem + "_rebrand" + input_path.suffix)
    dest.write_bytes(data)
    changed = data != original
    return {
        "ok": True,
        "mode": "rebrand_file",
        "brand": cfg["brand"],
        "channel": cfg["channel"],
        "watermark": cfg["watermark"],
        "replaced": replaced,
        "changed": changed,
        "out": str(dest),
        "notes": notes[:40],
        "note": "String rebrand only — no Telegram bot / no phone-home",
    }


def run_rebrand_tree(src_dir, out_dir, out_root=None, brand=None, channel=None, watermark=None):
    """Rebrand all text-like files under a directory (e.g. unpacked PAK tree)."""
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not src_dir.is_dir():
        return {"ok": False, "error": "src not a directory"}

    results = []
    total_replaced = 0
    for f in src_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".lua", ".txt", ".ini", ".json", ".xml", ".csv", ".uasset", ".uexp"):
            # still try lua-named without suffix
            if b"\x1bLua" == f.read_bytes()[:4] if f.stat().st_size > 4 else False:
                pass
            elif f.suffix.lower() not in (".lua", ".txt", ".ini"):
                continue
        rel = f.relative_to(src_dir)
        dest_parent = out_dir / rel.parent
        dest_parent.mkdir(parents=True, exist_ok=True)
        r = run_rebrand_file(f, dest_parent, out_root=out_root, brand=brand, channel=channel, watermark=watermark)
        # write with original name under out tree
        final = dest_parent / f.name
        if Path(r["out"]).is_file():
            Path(r["out"]).replace(final)
            r["out"] = str(final)
        total_replaced += r.get("replaced", 0)
        if r.get("changed"):
            results.append(r)

    summary = out_dir / "_rebrand_report.txt"
    lines = [
        "ALVSIA REBRAND TREE",
        "src=%s" % src_dir,
        "files_changed=%s" % len(results),
        "total_replaced=%s" % total_replaced,
    ]
    for r in results[:100]:
        lines.append("%s replaced=%s" % (r.get("out"), r.get("replaced")))
    summary.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "mode": "rebrand_tree",
        "files_changed": len(results),
        "total_replaced": total_replaced,
        "out": str(out_dir),
        "report": str(summary),
        "note": "String rebrand only — no Telegram bot / no phone-home",
    }


def run_rebrand_auto(input_path, out_dir, out_root=None):
    """Convenience: auto ALVSIA PRO defaults on file or directory."""
    p = Path(input_path)
    if p.is_dir():
        return run_rebrand_tree(p, out_dir, out_root=out_root)
    return run_rebrand_file(p, out_dir, out_root=out_root)


def run_rebrand(input_path, out_dir, cfg_path=None, auto=False, out_root=None):
    """Bridge entry: dispatch to file or tree based on input type.

    Args:
        input_path: .lua/.txt file OR unpacked directory tree
        out_dir:    destination directory
        cfg_path:   path to WORK/rebrand_config.txt (manual mode)
        auto:       True = ALVSIA PRO defaults; False = read cfg_path overrides
        out_root:   parent of WORK/ (used to locate rebrand_config.txt)

    Returns: dict from run_rebrand_file or run_rebrand_tree.
    """
    p = Path(input_path) if input_path else None
    if p is None or not p.exists():
        return {"ok": False, "error": "input not found: %r" % input_path}

    # Resolve out_root from explicit arg or derive from out_dir
    if out_root is None:
        out_root = Path(out_dir).parent  # OUT/REBRAND → OUT, then look for WORK sibling

    if auto:
        # Auto mode: ALVSIA PRO defaults, no manual config needed
        return run_rebrand_auto(p, out_dir, out_root=out_root)

    # Manual mode: try cfg_path; if not present, look for WORK/rebrand_config.txt
    # under out_root (which is where _load_rebrand_config looks).
    if cfg_path:
        cfg_file = Path(cfg_path)
        if cfg_file.is_file():
            # _load_rebrand_config expects the file at <out_root>/WORK/rebrand_config.txt
            # If the caller passed a different path, copy it to that location
            # so the existing loader picks it up.
            target_work_dir = Path(out_root) / "WORK"
            target_work_dir.mkdir(parents=True, exist_ok=True)
            target = target_work_dir / "rebrand_config.txt"
            if cfg_file.resolve() != target.resolve():
                try:
                    target.write_text(cfg_file.read_text(encoding="utf-8"),
                                      encoding="utf-8")
                except Exception:
                    pass  # best-effort; loader will fall back to defaults
    # Dispatch to file or tree handler (both call _load_rebrand_config internally)
    if p.is_dir():
        return run_rebrand_tree(p, out_dir, out_root=out_root)
    return run_rebrand_file(p, out_dir, out_root=out_root)


# ── Missing features added for full 17-module coverage ──────────────────────

def run_lua_analyze(input_path, out_dir):
    """Analyze Lua/LuaJIT bytecode: format detection + obfuscation report."""
    from pathlib import Path
    p = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    report_lines = ["ALVSIA LUA ANALYZER", "file=%s" % p.name, "size=%s bytes" % len(raw)]
    # Detect format
    if raw[:4] == b"\x1bLua":
        ver_byte = raw[4] if len(raw) > 4 else 0
        ver = "Lua5.1" if ver_byte == 0x51 else "Lua5.2" if ver_byte == 0x52 else "Lua5.3" if ver_byte == 0x53 else "Lua5.4" if ver_byte == 0x54 else "LuaUnknown(0x%02x)" % ver_byte
        report_lines.append("format=%s bytecode" % ver)
    elif raw[:4] == b"\x1bLJs":
        report_lines.append("format=LuaJIT bytecode")
    elif len(raw) > 4 and raw[0] == 0x1b and raw[1:4] == b"LJ\x02":
        report_lines.append("format=LuaJIT2")
    elif b"function" in raw[:200] or b"local" in raw[:200]:
        report_lines.append("format=Lua source (plaintext)")
    else:
        report_lines.append("format=unknown/binary blob")
    # XOR probe
    xor_candidates = []
    for k in range(1, 256):
        dec = bytes(b ^ k for b in raw[:64])
        if dec[:4] in (b"\x1bLua", b"\x1bLJs"):
            xor_candidates.append("0x%02x" % k)
    if xor_candidates:
        report_lines.append("xor_layer_candidates=%s" % ",".join(xor_candidates))
    else:
        report_lines.append("xor_layer=none_detected")
    # String density (obfuscation indicator)
    printable = sum(1 for b in raw if 32 <= b <= 126)
    density = printable / max(len(raw), 1)
    report_lines.append("printable_density=%.2f%%" % (density * 100))
    if density < 0.15:
        report_lines.append("obfuscation=HIGH (low string density)")
    elif density < 0.35:
        report_lines.append("obfuscation=MEDIUM")
    else:
        report_lines.append("obfuscation=LOW (readable)")
    out_file = out_dir / (p.stem + "_analysis.txt")
    out_file.write_text("\n".join(report_lines), encoding="utf-8")
    return {"ok": True, "out": str(out_file), "report": "\n".join(report_lines[:6])}


def run_lua_constants(input_path, out_dir):
    """Extract string constants and numbers from Lua bytecode."""
    from pathlib import Path
    import re
    p = Path(input_path); out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    strings = []
    cur = bytearray()
    for b in raw:
        if 32 <= b <= 126:
            cur.append(b)
        else:
            if len(cur) >= 4:
                strings.append(cur.decode("ascii", errors="replace"))
            cur = bytearray()
    if len(cur) >= 4:
        strings.append(cur.decode("ascii", errors="replace"))
    strings = list(dict.fromkeys(strings))  # dedupe preserving order
    out_file = out_dir / (p.stem + "_constants.txt")
    out_file.write_text("\n".join(strings), encoding="utf-8")
    return {"ok": True, "count": len(strings), "out": str(out_file)}


def run_obb_extract(input_path, out_dir):
    """Safely extract OBB/ZIP entries without allowing paths outside out_dir."""
    import shutil
    import zipfile
    from pathlib import Path

    p = Path(input_path)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    try:
        with zipfile.ZipFile(p, "r") as zf:
            entries = zf.infolist()
            validated = []
            # Validate every member before writing anything, preventing ZIP-slip
            # archives from partially extracting outside the destination.
            for info in entries:
                member = info.filename.replace(chr(92), "/")
                if member.startswith("/") or (len(member) >= 2 and member[1] == ":"):
                    return {"ok": False, "error": "unsafe absolute archive path rejected"}
                target = (root / member).resolve()
                if target != root and root not in target.parents:
                    return {"ok": False, "error": "unsafe archive path rejected: %s" % info.filename}
                # Do not materialize archive symlinks; they can redirect later writes.
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    return {"ok": False, "error": "symlink archive entry rejected: %s" % info.filename}
                validated.append((info, target))

            count = 0
            for info, target in validated:
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
        return {"ok": True, "extracted": count, "out": str(root)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_obb_rezip(input_path, out_file):
    """Repack a folder (or file) into a .obb ZIP."""
    import zipfile
    from pathlib import Path
    p = Path(input_path); out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.is_file()]
        with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f, f.relative_to(p))
        return {"ok": True, "packed": len(files), "out": str(out_file)}
    elif p.is_file():
        import shutil
        shutil.copy2(p, out_file)
        return {"ok": True, "packed": 1, "out": str(out_file), "note": "single file copied"}
    return {"ok": False, "error": "input not found"}


def run_strings_scan(input_path, out_dir):
    """Extract printable ASCII strings using bounded-memory streaming."""
    from pathlib import Path

    p = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not p.is_file():
        return {"ok": False, "error": "input file not found"}

    out_file = out_dir / ("strings_%s.txt" % p.stem)
    seen = set()
    count = 0
    cur = bytearray()
    max_run = 1024 * 1024

    def emit_run(handle, run):
        nonlocal count
        if len(run) < 4:
            return
        value = run.decode("ascii", errors="replace")
        if value not in seen:
            seen.add(value)
            handle.write(value + "\n")
            count += 1

    with p.open("rb") as source, out_file.open("w", encoding="utf-8") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            for b in chunk:
                if 32 <= b <= 126:
                    cur.append(b)
                    if len(cur) >= max_run:
                        emit_run(target, cur)
                        cur.clear()
                else:
                    emit_run(target, cur)
                    cur.clear()
        emit_run(target, cur)

    return {"ok": True, "count": count, "out": str(out_file)}


def run_export_report(input_path, out_dir):
    """Generate a file report without loading the complete input into memory."""
    import hashlib
    from pathlib import Path
    import zipfile

    p = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not p.is_file():
        return {"ok": False, "error": "input file not found"}

    digest = {"md5": hashlib.md5(), "sha1": hashlib.sha1(), "sha256": hashlib.sha256()}
    with p.open("rb") as source:
        head = source.read(16)
        for h in digest.values():
            h.update(head)
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            for h in digest.values():
                h.update(chunk)

    size = p.stat().st_size
    lines = [
        "ALVSIA FILE REPORT",
        "name=%s" % p.name,
        "size=%s bytes" % size,
        "MD5=%s" % digest["md5"].hexdigest(),
        "SHA1=%s" % digest["sha1"].hexdigest(),
        "SHA256=%s" % digest["sha256"].hexdigest(),
        "head_hex=%s" % head.hex(),
    ]
    if head[:2] == b"PK":
        try:
            with zipfile.ZipFile(p) as zf:
                lines.append("type=ZIP/OBB entries=%s" % len(zf.infolist()))
        except Exception:
            lines.append("type=ZIP(corrupt)")
    elif head[:4] == b"\x1bLua":
        lines.append("type=Lua bytecode")
    elif head[:4] == b"\x04\x22\x4d\x18" or head[:4] == b"\x28\xb5\x2f\xfd":
        lines.append("type=Zstd compressed")
    else:
        lines.append("type=binary/unknown")

    out_file = out_dir / ("report_%s.txt" % p.stem)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "out": str(out_file), "sha256": digest["sha256"].hexdigest()}


# ──────────────────────────────────────────────────────────────────────────────
# SM4KeyFinder — integrated from ALVSIA source research (ALVSIA private source_py.zip)
# Finds SM4_SECRET_NEW candidates inside .so / APK / OBB binary files.
# UI-agnostic: returns plain Python data; no Rich/Kivy dependency.
# ──────────────────────────────────────────────────────────────────────────────

import re as _re


class SM4KeyFinder:
    """Scan ELF .so files for embedded SM4_SECRET_NEW candidates.

    Candidates match the positional pattern ``aA0`` repeating for exactly
    20 characters (lower · UPPER · digit, cycle repeating).  Found at the
    offset where they appear in the binary, both as UTF-8 runs and as
    UTF-16-LE runs (common in stripped BGMI .so blobs).

    Usage::

        finder = SM4KeyFinder('/path/to/lib/arm64-v8a')
        keys = finder.find_keys()          # list[tuple[int, str]]
        unique = list(dict.fromkeys(s for _, s in keys))
    """

    # 20-char aA0-pattern: 6 complete triples (aA0) + 2-char tail (aA) = 6×3+2 = 20
    _CANDIDATE_RE_UTF8   = _re.compile(rb'(?:[a-z][A-Z]\d){6}[a-z][A-Z]')
    _CANDIDATE_RE_UTF16  = _re.compile(rb'(?:[\x20-\x7e]\x00){20}')
    _CHUNK_SIZE          = 8 * 1024 * 1024  # 8 MB

    @staticmethod
    def is_sm4_new_candidate(s: str) -> bool:
        """Return True iff *s* matches the aA0-repeating 20-char pattern."""
        if len(s) != 20:
            return False
        for i, c in enumerate(s):
            pos = i % 3
            if pos == 0 and not c.islower():   return False
            if pos == 1 and not c.isupper():   return False
            if pos == 2 and not c.isdigit():   return False
        return True

    @staticmethod
    def scan_file(filepath, progress_cb=None) -> list:
        """Scan one binary file for SM4_SECRET_NEW candidates.

        Returns ``list[tuple[int, str]]`` — (absolute_byte_offset, candidate_string).
        *progress_cb*, if supplied, is called as ``progress_cb(bytes_done, bytes_total)``.
        """
        results: list = []
        seen: set = set()
        data = Path(filepath).read_bytes()
        total = len(data)
        offset = 0
        while offset < total:
            end   = min(offset + SM4KeyFinder._CHUNK_SIZE + 40, total)
            chunk = data[offset:end]

            # UTF-8 run
            for m in SM4KeyFinder._CANDIDATE_RE_UTF8.finditer(chunk):
                abs_off = offset + m.start()
                if abs_off in seen: continue
                seen.add(abs_off)
                s = m.group(0).decode('ascii', errors='ignore')
                if SM4KeyFinder.is_sm4_new_candidate(s):
                    results.append((abs_off, s))

            # UTF-16-LE run
            for m in SM4KeyFinder._CANDIDATE_RE_UTF16.finditer(chunk):
                abs_off = offset + m.start()
                if abs_off in seen: continue
                seen.add(abs_off)
                s = m.group(0)[::2].decode('ascii', errors='ignore')
                if len(s) == 20 and ' ' not in s and SM4KeyFinder.is_sm4_new_candidate(s):
                    results.append((abs_off, s))

            if progress_cb:
                progress_cb(min(end, total), total)
            offset += SM4KeyFinder._CHUNK_SIZE

        return results

    def __init__(self, so_folder: str = '.'):
        self.so_folder  = Path(so_folder)
        self.found_keys: set = set()

    def find_keys(self) -> list:
        """Scan all ``*.so`` files under *so_folder*.

        Returns deduplicated ``list[tuple[int, str]]`` sorted by offset.
        """
        all_results: list = []
        for so_path in sorted(self.so_folder.rglob('*.so')):
            try:
                hits = SM4KeyFinder.scan_file(so_path)
                for off, key in hits:
                    if key not in self.found_keys:
                        self.found_keys.add(key)
                        all_results.append((off, key))
            except Exception:
                pass
        return sorted(all_results)


# ──────────────────────────────────────────────────────────────────────────────
# SM4KeyFinder — v2: adds SM4_SECRET_2 and SM4_SECRET_4 candidate detection
# Integrated into ALVSIA PRO (ALVSIA private source)
# SM4_SECRET_NEW already handled by the earlier SM4KeyFinder class.
# This adds the two remaining SM4 secret variants used in older BGMI builds.
# ──────────────────────────────────────────────────────────────────────────────

class SM4AllKeyFinder(SM4KeyFinder):
    """Extends SM4KeyFinder to also detect SM4_SECRET_2 and SM4_SECRET_4 candidates.

    *SM4_SECRET_4* pattern: 20 alphanum chars, no uppercase, digit-heavy (≥10 digits,
    ≥5 lowercase, 0 uppercase).  Used in PAK encryption method EM_SM4_4.

    *SM4_SECRET_2* pattern: 20 chars, contains ``$`` or ``*``, ≥5 uppercase, ≥3 lowercase,
    ≥1 digit.  Used in PAK encryption method EM_SM4_2.

    Returns a dict keyed by secret type::

        {
          'SM4_SECRET_NEW': [(offset, key), ...],
          'SM4_SECRET_4':   [(offset, key), ...],
          'SM4_SECRET_2':   [(offset, key), ...],
        }
    """

    @staticmethod
    def is_sm4_4_candidate(s: str) -> bool:
        """All-alphanumeric, no uppercase, ≥10 digits, ≥5 lowercase."""
        if len(s) != 20 or not all(c.isalnum() for c in s):
            return False
        d = sum(1 for c in s if c.isdigit())
        l = sum(1 for c in s if c.islower())
        u = sum(1 for c in s if c.isupper())
        return d >= 10 and l >= 5 and u == 0

    @staticmethod
    def is_sm4_2_candidate(s: str) -> bool:
        """Contains $ or *, ≥5 uppercase, ≥3 lowercase, ≥1 digit."""
        if len(s) != 20:
            return False
        has_special = any(c in '$*' for c in s)
        u = sum(1 for c in s if c.isupper())
        l = sum(1 for c in s if c.islower())
        d = sum(1 for c in s if c.isdigit())
        return has_special and u >= 5 and l >= 3 and d >= 1

    def find_all_keys(self) -> dict:
        """Scan all ``.so`` files under *so_folder* for all three SM4 secret types.

        Returns ``{'SM4_SECRET_NEW': [...], 'SM4_SECRET_4': [...], 'SM4_SECRET_2': [...]}``.
        Each list contains ``(offset, key_string)`` tuples, deduplicated.
        """
        results: dict = {'SM4_SECRET_NEW': [], 'SM4_SECRET_4': [], 'SM4_SECRET_2': []}
        seen_new: set = set()
        seen_4:   set = set()
        seen_2:   set = set()

        _CHUNK   = 8 * 1024 * 1024
        _UTF16RE = _re.compile(rb'(?:[\x20-\x7e]\x00){20}')
        _UTF8RE  = _re.compile(rb'[\x21-\x7e]{20}')  # any 20 printable ASCII (no space)

        for so_path in sorted(Path(self.so_folder).rglob('*.so')):
            try:
                data  = so_path.read_bytes()
                total = len(data)
                off   = 0
                while off < total:
                    end   = min(off + _CHUNK + 40, total)
                    chunk = data[off:end]

                    # UTF-8 run
                    for m in _UTF8RE.finditer(chunk):
                        s = m.group(0).decode('ascii', errors='ignore')
                        abs_off = off + m.start()
                        if SM4KeyFinder.is_sm4_new_candidate(s) and s not in seen_new:
                            seen_new.add(s); results['SM4_SECRET_NEW'].append((abs_off, s))
                        elif SM4AllKeyFinder.is_sm4_4_candidate(s) and s not in seen_4:
                            seen_4.add(s);   results['SM4_SECRET_4'].append((abs_off, s))
                        elif SM4AllKeyFinder.is_sm4_2_candidate(s) and s not in seen_2:
                            seen_2.add(s);   results['SM4_SECRET_2'].append((abs_off, s))

                    # UTF-16-LE run
                    for m in _UTF16RE.finditer(chunk):
                        s = m.group(0)[::2].decode('ascii', errors='ignore')
                        if len(s) != 20 or ' ' in s:
                            continue
                        abs_off = off + m.start()
                        if SM4KeyFinder.is_sm4_new_candidate(s) and s not in seen_new:
                            seen_new.add(s); results['SM4_SECRET_NEW'].append((abs_off, s))
                        elif SM4AllKeyFinder.is_sm4_4_candidate(s) and s not in seen_4:
                            seen_4.add(s);   results['SM4_SECRET_4'].append((abs_off, s))
                        elif SM4AllKeyFinder.is_sm4_2_candidate(s) and s not in seen_2:
                            seen_2.add(s);   results['SM4_SECRET_2'].append((abs_off, s))

                    off += _CHUNK
            except Exception:
                pass

        return results


# ──────────────────────────────────────────────────────────────────────────────
# BinaryURLScanner — scan static .so / APK binaries for embedded URLs
# Integrated from url_scanner.py (ALVSIA private source.zip)
# Detects: http/https/ws/ftp URLs, host:port patterns near context keywords,
# raw IP:port patterns, and long base64 blobs near URL context keywords.
# Pure-Python, no external deps, Android-safe.
# ──────────────────────────────────────────────────────────────────────────────

class BinaryURLScanner:
    """Scan ELF ``.so`` / APK binaries for embedded URLs and server addresses.

    Usage::

        scanner = BinaryURLScanner()
        results = scanner.scan_file('/path/to/libUE4.so')
        for kind, value in results:
            print(kind, value)
    """

    _RE_URL     = _re.compile(
        rb'(https?|wss?|ftp|sftp|rtsp|rtmp)://[^\x00-\x20\x7f\s<>"\'{}|\\^`\[\]]{4,200}',
        _re.IGNORECASE,
    )
    _RE_HOST    = _re.compile(
        rb'([a-zA-Z0-9-]{2,63}(?:\.[a-zA-Z0-9-]{1,63})+\.[a-zA-Z]{2,10})'
        rb'(?::(\d{1,5}))?',
    )
    _RE_IP      = _re.compile(rb'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b')
    _RE_B64     = _re.compile(rb'[A-Za-z0-9+/]{40,}={0,2}')
    _CTX_KW     = [b'url', b'host', b'connect', b'endpoint', b'server',
                   b'proxy', b'gateway', b'base', b'api', b'link', b'path']
    _CHUNK      = 8 * 1024 * 1024

    # Private IP ranges — excluded from host results to reduce noise
    _PRIVATE_IP = _re.compile(
        rb'^(?:127\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)'
    )

    def _ctx_ok(self, data: bytes, start: int, end: int) -> bool:
        lo = max(0, start - 60)
        hi = min(len(data), end + 60)
        ctx = data[lo:hi].lower()
        return any(k in ctx for k in self._CTX_KW)

    def scan_bytes(self, data: bytes) -> list:
        """Return ``list[tuple[str, str]]`` — (kind, value)."""
        results: list = []
        seen: set = set()

        def add(kind: str, raw: bytes) -> None:
            val = raw.decode('utf-8', errors='replace').strip()
            if val and val not in seen:
                seen.add(val)
                results.append((kind, val))

        # 1. Full URLs
        for m in self._RE_URL.finditer(data):
            add('URL', m.group(0))

        # 2. host:port near context keywords
        for m in self._RE_HOST.finditer(data):
            host = m.group(1)
            port = m.group(2) or b''
            if not self._ctx_ok(data, m.start(), m.end()):
                continue
            raw = host + (b':' + port if port else b'')
            add('HOST', raw)

        # 3. IP:port
        for m in self._RE_IP.finditer(data):
            ip_bytes = m.group(0)
            if self._PRIVATE_IP.match(ip_bytes):
                continue
            add('IP', ip_bytes)

        # 4. Long base64 near context keywords (obfuscated URLs)
        for m in self._RE_B64.finditer(data):
            if not self._ctx_ok(data, m.start(), m.end()):
                continue
            add('B64', m.group(0)[:120])

        return results

    def scan_file(self, filepath) -> list:
        """Scan one binary file.  Returns list of (kind, value) tuples."""
        data = Path(filepath).read_bytes()
        return self.scan_bytes(data)

    def scan_folder(self, folder_path: str, exts=('.so', '.obb', '.apk')) -> dict:
        """Scan all matching files under *folder_path*.

        Returns ``{filename: [(kind, value), ...]}`` for files with results.
        """
        out: dict = {}
        for p in sorted(Path(folder_path).rglob('*')):
            if p.suffix.lower() not in exts or not p.is_file():
                continue
            try:
                hits = self.scan_file(p)
                if hits:
                    out[p.name] = hits
            except Exception:
                pass
        return out


# ──────────────────────────────────────────────────────────────────────────────
# PUBGLuaConverter — PUBG Mobile Lua bytecode → Standard Lua 5.3 converter
# Integrated from PUBGM.py (ALVSIA private source.zip)
# Converts BGMI/PUBG Mobile scrambled Lua bytecode to standard Lua 5.3 format
# so it can be decompiled with luadec / unluac.
# ──────────────────────────────────────────────────────────────────────────────

import struct as _struct

# PUBG XOR key extracted from libUE4.so sub_777C014 (32-byte repeating key)
PUBG_XOR_KEY = bytes([
    0x11, 0x21, 0x36, 0x47, 0x46, 0x57, 0xA7, 0x8D,
    0x9D, 0x84, 0x90, 0xD8, 0xAB, 0x00, 0x8C, 0x35,
    0x26, 0x1A, 0xF7, 0xE4, 0x58, 0x05, 0xB8, 0xB3,
    0x15, 0x07, 0xD0, 0x2C, 0x1E, 0x8F, 0xF6, 0xC8,
])

# Verified opcode mapping: PUBG/BGMI opcode → Standard Lua 5.3 opcode
PUBG_TO_STD_OPCODE = {
    0: 0, 1: 1, 17: 0, 18: 1, 20: 3, 21: 4, 22: 5, 23: 6,
    24: 7, 26: 9, 27: 10, 28: 11, 29: 12, 31: 31, 32: 32,
    33: 33, 34: 34, 35: 35, 36: 36, 37: 37, 38: 38, 39: 39,
    40: 40, 41: 41, 42: 42, 43: 43, 44: 44, 45: 45, 46: 46,
    47: 47,
}


class PUBGLuaConverter:
    """Convert PUBG Mobile / BGMI Lua bytecode to standard Lua 5.3 format.

    The converter:

    1. XOR-decrypts the string-constant pool (bytes after the 0x22-byte header)
       using ``PUBG_XOR_KEY``.
    2. Remaps scrambled opcodes to standard Lua 5.3 opcodes via
       ``PUBG_TO_STD_OPCODE``.
    3. Rewrites the Lua header to the standard Lua 5.3 signature so that
       decompilers accept the output.

    Usage::

        converter = PUBGLuaConverter()
        std_bytes = converter.convert_file('/path/to/scrambled.luac')
        Path('/out/fixed.luac').write_bytes(std_bytes)
    """

    _LUA53_HEADER = (
        b'\x1bLua'       # magic
        b'\x53'          # version 5.3
        b'\x00'          # format 0
        b'\x19\x93\r\n\x1a\n'  # LUAC_DATA
        b'\x04'          # sizeof_int
        b'\x08'          # sizeof_size_t
        b'\x04'          # sizeof_Instruction
        b'\x08'          # sizeof_lua_Integer
        b'\x08'          # sizeof_lua_Number
        b'\x78\x56\x00\x00\x00\x00\x00\x00'   # LUAC_INT
        b'\x00\x00\x00\x00\x00\x28\x77\x40'   # LUAC_NUM
    )
    _HDR_LEN = 33
    _HEADER_ENCRYPTED_START = 0x22  # bytes before this are NOT XOR-encrypted

    @staticmethod
    def _xor_decrypt(data: bytes) -> bytes:
        key = PUBG_XOR_KEY
        kl  = len(key)
        return bytes(b ^ key[i % kl] for i, b in enumerate(data))

    def convert_bytes(self, data: bytes) -> bytes:
        """Convert *data* (raw PUBG .luac bytes) to standard Lua 5.3 bytes."""
        if len(data) < self._HDR_LEN:
            raise ValueError("data too short to be a Lua bytecode file")
        # Decrypt the portion after the unencrypted header prefix
        header   = data[:self._HEADER_ENCRYPTED_START]
        body_enc = data[self._HEADER_ENCRYPTED_START:]
        body     = self._xor_decrypt(body_enc)
        decrypted = header + body

        # Remap opcodes in all instruction words (every u32 that encodes an instruction)
        result = self._remap_opcodes(decrypted)
        # Rewrite the Lua header so luadec / unluac accept the file
        return self._LUA53_HEADER + result[self._HDR_LEN:]

    def _remap_opcodes(self, data: bytes) -> bytes:
        """Walk the top-level proto and remap PUBG opcodes to standard ones."""
        # Simple approach: scan all aligned u32 words and remap op field (bits 0-5)
        # This is fast and works for most well-formed files.
        ba = bytearray(data)
        i  = self._HDR_LEN
        while i + 4 <= len(ba):
            raw = _struct.unpack_from('<I', ba, i)[0]
            op  = raw & 0x3F
            if op in PUBG_TO_STD_OPCODE:
                std_op = PUBG_TO_STD_OPCODE[op]
                new_raw = (raw & ~0x3F) | std_op
                _struct.pack_into('<I', ba, i, new_raw)
            i += 4
        return bytes(ba)

    def convert_file(self, input_path: str, output_path: str | None = None) -> bytes:
        """Convert one ``.luac`` file.  If *output_path* is given, write the result there.

        Returns the converted bytes regardless.
        """
        data   = Path(input_path).read_bytes()
        result = self.convert_bytes(data)
        if output_path:
            Path(output_path).write_bytes(result)
        return result

    def convert_folder(self, input_dir: str, output_dir: str,
                       glob_pat: str = '*.luac') -> dict:
        """Convert all matching files in *input_dir*, writing to *output_dir*.

        Returns ``{filename: 'OK' | 'FAIL: <reason>'}`` for each file processed.
        """
        src_dir = Path(input_dir)
        dst_dir = Path(output_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        report: dict = {}
        for p in sorted(src_dir.glob(glob_pat)):
            try:
                out_path = dst_dir / p.name
                self.convert_file(str(p), str(out_path))
                report[p.name] = 'OK'
            except Exception as exc:
                report[p.name] = f'FAIL: {exc}'
        return report
