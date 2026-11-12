"""Unified Smart Lua engine.

One mechanism for Lua decompile, analysis, protection, compile/recompile and
injection. Existing engines are providers behind this router, never separate
user-facing tools.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


from sm4_secret_registry import (
    SM4_SECRET_NEW,
    SM4_SECRET_NEW_VERSION,
    SM4_SECRET_NEW_EXPECTED_COUNT,
    validate_sm4_secret_set,
)


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _result(ok: bool, operation: str, **extra: Any) -> dict:
    out = {"ok": bool(ok), "module": "lua", "operation": operation}
    out.update(extra)
    return out


def detect(input_path: str | Path) -> dict:
    p = Path(input_path)
    if not p.is_file():
        return _result(False, "detect", error="input file not found")
    with p.open("rb") as fh:
        head = fh.read(64)
    if head.startswith(b"\x1bLua"):
        version = head[4] if len(head) > 4 else None
        return _result(True, "detect", format="lua-bytecode", version=hex(version) if version else None)
    if head.startswith(b"\x1bLJ"):
        return _result(True, "detect", format="luajit-bytecode")
    try:
        p.read_text(encoding="utf-8")
        return _result(True, "detect", format="lua-source")
    except UnicodeDecodeError:
        return _result(True, "detect", format="binary/unknown")


def decompile(input_path, output_dir, jars_dir=None) -> dict:
    from alvsia_features import run_lua_smart, run_lua_analyze
    p = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Recovery runs first so optional diagnostics can never delay or suppress
    # the primary decompilation result.
    result = dict(run_lua_smart(p, out, jars_dir=jars_dir) or {})
    result.update({"module": "lua", "operation": "decompile"})
    if not result.get("ok") or not result.get("out"):
        if result.get("ok"):
            return _result(False, "decompile",
                           error="decompiler reported success without a source artifact",
                           diagnostics=result)
        return result

    artifact = Path(str(result["out"]))
    if not artifact.is_file() or artifact.stat().st_size <= 0 or artifact.suffix.lower() != ".lua":
        return _result(False, "decompile",
                       error="decompiler output failed source-artifact validation",
                       diagnostics=result)
    result["output_bytes"] = artifact.stat().st_size
    result["sha256"] = _sha256_file(artifact)

    # Format/constant/VM analysis is part of this engine, not a separate menu.
    # It is deliberately post-recovery and non-fatal.
    try:
        result["analysis"] = run_lua_analyze(str(p), out / "_smart_analysis")
    except Exception as exc:
        result["analysis"] = {"ok": False, "error": type(exc).__name__}
    return result


def analyze(input_path, output_dir) -> dict:
    from alvsia_features import run_lua_analyze
    p = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = run_lua_analyze(str(p), out)
    return _result(bool(isinstance(report, dict) and report.get("ok", True)), "analyze", report=report)


def protect(input_path, output_path, profile="balanced") -> dict:
    from lua_engine.protection_pipeline import protect_file
    return dict(protect_file(input_path, output_path, profile))


def _find_luac(jars_dir=None, work_dir=None) -> Path | None:
    candidates = []
    env = os.environ.get("ALVSIA_LUAC", "").strip()
    if env:
        candidates.append(Path(env))
    for root in (jars_dir, work_dir):
        if root:
            r = Path(root)
            candidates.extend([r / "luac", r / "EXES" / "luac"])
    candidates.extend([
        Path("/data/data/com.alvsia.pro/files/EXES/luac"),
        Path("/data/data/com.alvsia.pro/files/chaquopy/AssetFinder/EXES/luac"),
    ])
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    for name in ("luac", "luac5.3", "luac53", "luac5.1"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def compile_source(input_path, output_dir, jars_dir=None, work_dir=None) -> dict:
    src = Path(input_path)
    if not src.is_file():
        return _result(False, "compile", error="input Lua source not found")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    compiler = _find_luac(jars_dir, work_dir)
    if compiler is None:
        return _result(False, "compile", error="compatible luac compiler is not packaged or executable; no fake bytecode was generated")
    dest = out / (src.stem + ".luac")
    try:
        proc = subprocess.run(
            [str(compiler), "-o", str(dest), str(src)],
            capture_output=True, timeout=120,
        )
        if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", "replace").strip()
            return _result(False, "compile", error=err[:1200] or "luac compilation failed", compiler=str(compiler))
        raw = dest.read_bytes()
        if not raw.startswith(b"\x1bLua"):
            dest.unlink(missing_ok=True)
            return _result(False, "compile", error="compiler output failed Lua bytecode validation", compiler=str(compiler))
        return _result(True, "compile", out=str(dest), bytes=dest.stat().st_size,
                       sha256=hashlib.sha256(raw).hexdigest(), compiler=str(compiler))
    except subprocess.TimeoutExpired:
        dest.unlink(missing_ok=True)
        return _result(False, "compile", error="compiler timeout; output discarded", compiler=str(compiler))


def inject(input_path, output_dir, sub_id, work_dir) -> dict:
    import alvsia_ultimate as ult
    import json
    src = Path(input_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else out / "WORK"
    config = work / "lua_inject_config.json"
    data = {}
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except Exception as exc:
            return _result(False, "inject", error="invalid WORK/lua_inject_config.json: " + str(exc)[:240])
    mode = str(data.get("mode") or "").strip().lower()
    if sub_id == "lua_patch_byte" or mode == "patch":
        cfg = work / "lua_patch.json"
        if cfg.is_file() and not data:
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
            except Exception as exc:
                return _result(False, "inject", error="invalid WORK/lua_patch.json: " + str(exc)[:240])
        result = ult.lua_patch_bytecode(
            src, out, str(data.get("offset", "")),
            str(data.get("patch_hex", data.get("bytes", ""))),
        )
        return _result(bool(isinstance(result, dict) and result.get("ok")), "inject",
                       mode="patch", out=result.get("out") if isinstance(result, dict) else None,
                       result=result)
    if sub_id == "lua_inject_hook" or mode == "hook":
        hook = Path(data.get("hook_path", work / "lua_hook.lua"))
        result = ult.lua_inject_hook(src, out, str(hook))
        return _result(bool(isinstance(result, dict) and result.get("ok")), "inject",
                       mode="hook", out=result.get("out") if isinstance(result, dict) else None,
                       result=result)
    if sub_id == "lua_mod_repack" or mode == "repack":
        mod_dir = Path(data.get("mod_dir", work / "MOD"))
        if not mod_dir.is_dir():
            return _result(False, "inject", error="WORK/MOD is required for PAK repack")
        dest = out / (src.stem + "_modded.pak")
        import alvsia_core as core
        result = core.run_pak_smart_repack(src, mod_dir, dest)
        if not result.get("ok"):
            result = core.run_pak_repack(src, mod_dir, dest)
        return _result(bool(result.get("ok")), "inject", mode="pak-repack",
                       out=result.get("out") or str(dest) if result.get("ok") else None,
                       result=result)
    return _result(False, "inject", error="no valid injection plan; configure WORK/lua_inject_config.json")


def protect_encrypt(input_path, output_dir, work_dir, restore=False) -> dict:
    # Keep the existing ALVLUA1 authenticated format for compatibility.
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    src = Path(input_path)
    key_file = Path(work_dir) / "lua_protect_key.txt"
    if not key_file.is_file():
        return _result(False, "protect", error="WORK/lua_protect_key.txt is required")
    key_hex = key_file.read_text(encoding="utf-8").strip()
    if len(key_hex) != 64:
        return _result(False, "protect", error="Lua protection key must be 64 hex characters")
    key = bytes.fromhex(key_hex)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw = src.read_bytes()
    if not restore:
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
        cipher.update(b"ALVLUA1")
        ciphertext, tag = cipher.encrypt_and_digest(raw)
        dest = out / (src.stem + ".alvlua")
        dest.write_bytes(b"ALVLUA1" + nonce + tag + ciphertext)
        return _result(True, "protect", mode="encrypt", out=str(dest), bytes=dest.stat().st_size)
    if len(raw) < 35 or raw[:7] != b"ALVLUA1":
        return _result(False, "protect", error="invalid ALVLUA1 payload")
    nonce, tag, ciphertext = raw[7:19], raw[19:35], raw[35:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce, mac_len=16)
    cipher.update(b"ALVLUA1")
    try:
        plain = cipher.decrypt_and_verify(ciphertext, tag)
    except ValueError:
        return _result(False, "protect", error="authentication failed")
    dest = out / (src.stem + ".lua")
    dest.write_bytes(plain)
    return _result(True, "protect", mode="restore", out=str(dest), bytes=len(plain))


def vm_protect(input_path, output_dir) -> dict:
    from alvsia_vm_protect import vm_protect
    src = Path(input_path)
    dest = Path(output_dir) / (src.stem + ".alvlua3.lua")
    return dict(vm_protect(src, dest, output_format="lua", num_decoys=1024))


def execute(operation, input_path, output_dir, **kwargs) -> dict:
    sm4 = validate_sm4_secret_set()
    if not sm4["ok"]:
        return _result(False, str(operation), error="authoritative SM4 4.7 key-set validation failed", sm4=sm4)
    op = str(operation).strip().lower()
    if op == "decompile":
        return decompile(input_path, output_dir, jars_dir=kwargs.get("jars_dir"))
    if op == "analyze":
        return analyze(input_path, output_dir)
    if op == "protect":
        import json
        work = Path(kwargs.get("work_dir") or Path(output_dir) / "WORK")
        cfg = work / "lua_protect_config.json"
        config = {}
        if cfg.is_file():
            try:
                config = json.loads(cfg.read_text(encoding="utf-8"))
            except Exception as exc:
                return _result(False, "protect", error="invalid WORK/lua_protect_config.json: " + str(exc)[:240])
        mode = str(config.get("mode") or "profile").strip().lower()
        if mode == "encrypt":
            return protect_encrypt(input_path, output_dir, work, restore=False)
        if mode == "restore":
            return protect_encrypt(input_path, output_dir, work, restore=True)
        if mode == "vm":
            return vm_protect(input_path, output_dir)
        profile = str(config.get("profile") or kwargs.get("profile", "balanced")).lower()
        if profile not in ("balanced", "strong"):
            return _result(False, "protect", error="profile must be balanced or strong")
        return protect(input_path, output_dir, profile)
    if op == "compile":
        return compile_source(input_path, output_dir, jars_dir=kwargs.get("jars_dir"), work_dir=kwargs.get("work_dir"))
    if op == "inject":
        return inject(input_path, output_dir, kwargs.get("sub_id", ""), kwargs.get("work_dir"))
    if op == "encrypt":
        return protect_encrypt(input_path, output_dir, kwargs.get("work_dir"), restore=False)
    if op == "restore":
        return protect_encrypt(input_path, output_dir, kwargs.get("work_dir"), restore=True)
    if op == "vm-protect":
        return vm_protect(input_path, output_dir)
    return _result(False, op, error="unsupported Smart Lua operation")
