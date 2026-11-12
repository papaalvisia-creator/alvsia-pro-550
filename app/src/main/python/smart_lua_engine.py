# -*- coding: utf-8 -*-
"""ALVSIA PRO Smart Lua — four-engine orchestration layer.

The UI exposes exactly four Lua engines. Detection, routing, IR, dialect
adapters, recovery, validation and legacy fallbacks stay internal to the
selected engine. This module never creates a separate detector/tool surface.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


ENGINE_NAMES = {
    "decompile": "SMART LUA DECOMPILER",
    "protect": "SMART LUA PROTECT",
    "compile": "SMART LUA COMPILER / RECOMPILER",
    "inject": "SMART LUA INJECT",
}


def _read_probe(path: Path, limit: int = 1_048_576) -> bytes:
    with path.open("rb") as fh:
        return fh.read(limit)


def detect(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"kind": "missing", "confidence": 0.0, "routes": []}
    data = _read_probe(p)
    head = data[:16]
    text = data[: min(len(data), 65536)]
    routes = []
    if head.startswith(b"\x1bLua"):
        version = head[4] if len(head) > 4 else 0
        routes.append("lua53" if version == 0x53 else "lua-bytecode")
    elif head.startswith(b"\x1bLJ"):
        routes.append("luajit")
    else:
        try:
            decoded = text.decode("utf-8")
            if any(tok in decoded for tok in ("function ", "local ", "return ", "--")):
                routes.append("lua-source")
        except UnicodeDecodeError:
            pass

    low = data.lower()
    if b"t24" in low or b"tencent" in low:
        routes.append("t24")
    if any(x in low for x in (b"pubg", b"bgmi", b"gname", b"ue4")):
        routes.append("pubg-bgmi")
    if b"alvseal" in low or b"alvlua" in low or b"vm" in low:
        routes.append("vm-obfuscated")
    if not routes:
        routes.append("unknown-binary")
    return {
        "kind": routes[0],
        "routes": routes,
        "size": p.stat().st_size,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "confidence": 0.95 if routes[0] in ("lua53", "luajit", "lua-source") else 0.55,
    }


def _validate_output(path: Path, suffixes: tuple[str, ...] = ()) -> dict:
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "error": "engine reported success without a non-empty output"}
    if suffixes and path.suffix.lower() not in suffixes:
        return {"ok": False, "error": "unexpected output type"}
    return {"ok": True, "out": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def decompile(input_path, output_dir, jars_dir=None):
    """Detector -> route -> Universal recovery -> validation -> fallback."""
    src, out = Path(input_path), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    info = detect(src)
    lines = ["ENGINE=SMART LUA DECOMPILER",
             "DETECT=" + ",".join(info["routes"])]
    try:
        from alvsia_features import run_lua_smart, run_pubg_lua_decrypt
        # PUBG/BGMI normalization is an internal adapter, never a separate tool.
        if "pubg-bgmi" in info["routes"]:
            try:
                normalized = out / (src.stem + "_pubg_normalized")
                r = run_pubg_lua_decrypt(src, out)
                if isinstance(r, dict) and r.get("ok") and r.get("out"):
                    normalized = Path(str(r["out"]))
                    lines.append("ROUTE=PUBG/BGMI ADAPTER")
                    src_for_decompile = normalized
                else:
                    src_for_decompile = src
                    lines.append("ROUTE=PUBG/BGMI ADAPTER -> standard recovery fallback")
            except Exception as exc:
                src_for_decompile = src
                lines.append("ROUTE=PUBG/BGMI ADAPTER fallback: " + str(exc)[:240])
        else:
            src_for_decompile = src

        result = run_lua_smart(src_for_decompile, out, jars_dir=jars_dir)
        if not isinstance(result, dict):
            return {"ok": False, "error": "Smart Lua recovery returned invalid result", "diagnostic": lines}
        result = dict(result)
        result.setdefault("diagnostic", lines)
        result["engine"] = ENGINE_NAMES["decompile"]
        if result.get("ok") and result.get("out"):
            check = _validate_output(Path(str(result["out"])), (".lua",))
            if not check["ok"]:
                result.update(check)
                result["ok"] = False
            else:
                result.update(check)
                result["diagnostic"] = lines
                return result
        result["diagnostic"] = lines
        return result
    except Exception as exc:
        return {"ok": False, "engine": ENGINE_NAMES["decompile"],
                "error": f"{type(exc).__name__}: {exc}", "diagnostic": lines}


def protect(input_path, output_path, profile="auto"):
    """Detector -> route -> IR/profile -> protect -> semantic validation."""
    src, dst = Path(input_path), Path(output_path)
    info = detect(src)
    try:
        if profile == "vm":
            from alvsia_vm_protect import vm_protect
            result = vm_protect(src, dst, output_format="lua", num_decoys=1024)
        else:
            from lua_engine.protection_pipeline import protect_file
            selected = "strong" if profile in ("auto", "strong") else "balanced"
            result = protect_file(src, dst, selected)
        result = dict(result or {})
        result["engine"] = ENGINE_NAMES["protect"]
        result["routes"] = info["routes"]
        if result.get("ok"):
            result.update(_validate_output(dst, (".lua",)))
        return result
    except Exception as exc:
        return {"ok": False, "engine": ENGINE_NAMES["protect"],
                "error": f"{type(exc).__name__}: {exc}", "routes": info["routes"]}


def _find_compiler(kind: str):
    candidates = ("luajit", "luajit-2.1") if kind == "luajit" else (
        "luac5.4", "luac5.3", "luac", "lua5.3"
    )
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def _compile_source(src: Path, dst: Path, dialect: str) -> dict:
    compiler = _find_compiler("luajit" if dialect == "luajit" else "lua53")
    if not compiler:
        return {"ok": False, "error": "compatible Lua compiler not installed on device",
                "dialect": dialect}
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dialect == "luajit":
        cmd = [compiler, "-b", str(src), str(dst)]
    else:
        cmd = [compiler, "-o", str(dst), str(src)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "dialect": dialect}
    stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        return {"ok": False, "error": stderr[:1200] or "compiler failed", "dialect": dialect}
    result = _validate_output(dst, (".luac", ".bin"))
    result["dialect"] = dialect
    if proc.returncode != 0:
        result["ok"] = False
    return result


def compile_or_recompile(input_path, output_dir, jars_dir=None):
    """Source -> bytecode or bytecode -> source -> bytecode with round-trip checks."""
    src, out = Path(input_path), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    info = detect(src)
    dialect = "luajit" if "luajit" in info["routes"] else "lua53"
    source = src
    temporary = None
    try:
        if info["kind"] != "lua-source":
            from alvsia_features import run_lua_smart
            temporary = Path(tempfile.mkdtemp(prefix="alvsia-recompile-")) / (src.stem + ".lua")
            recovered = run_lua_smart(src, temporary.parent, jars_dir=jars_dir)
            if not isinstance(recovered, dict) or not recovered.get("ok") or not recovered.get("out"):
                return {"ok": False, "engine": ENGINE_NAMES["compile"],
                        "error": "bytecode could not be recovered into validated source",
                        "routes": info["routes"]}
            candidate = Path(str(recovered["out"]))
            if not candidate.is_file():
                return {"ok": False, "engine": ENGINE_NAMES["compile"], "error": "recovery output missing"}
            candidate.rename(temporary)
            source = temporary
        dst = out / (src.stem + "_recompiled.luac")
        result = _compile_source(source, dst, dialect)
        result["engine"] = ENGINE_NAMES["compile"]
        result["routes"] = info["routes"]
        if result.get("ok"):
            # Structural round-trip oracle: re-decompile and require a valid source artifact.
            with tempfile.TemporaryDirectory(prefix="alvsia-roundtrip-") as td:
                from alvsia_features import run_lua_smart
                rt = run_lua_smart(dst, Path(td), jars_dir=jars_dir)
                result["round_trip"] = bool(isinstance(rt, dict) and rt.get("ok") and rt.get("out"))
                if not result["round_trip"]:
                    result["ok"] = False
                    result["error"] = "round-trip validation failed"
        return result
    finally:
        if temporary:
            shutil.rmtree(temporary.parent, ignore_errors=True)


def inject(input_path, output_dir, mode="auto"):
    """Detector -> route -> IR -> patch/hook/repack -> integrity validation."""
    src, out = Path(input_path), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    info = detect(src)
    try:
        import alvsia_ultimate as ultimate
        # Auto mode selects the least destructive real injector available.
        # A config file can request hook/patch/repack without adding UI tools.
        config = out.parent / "WORK" / "lua_inject_config.txt"
        cfg = {}
        if config.is_file():
            for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip().lower()] = v.strip()
        selected = cfg.get("mode", mode)
        if selected == "patch":
            result = ultimate.lua_patch_bytecode(str(src), out, cfg.get("offset", ""), cfg.get("patch_hex", ""))
        elif selected == "hook":
            result = ultimate.lua_inject_hook(str(src), out, cfg.get("hook_path"))
        elif selected == "repack":
            result = ultimate.lua_mod_repack(str(src), out)
        else:
            # Default is validated hook/patch engine selection based on config.
            if cfg.get("offset") and cfg.get("patch_hex"):
                result = ultimate.lua_patch_bytecode(str(src), out, cfg["offset"], cfg["patch_hex"])
            elif cfg.get("hook_path"):
                result = ultimate.lua_inject_hook(str(src), out, cfg["hook_path"])
            else:
                return {"ok": False, "engine": ENGINE_NAMES["inject"],
                        "error": "no injection plan configured; use WORK/lua_inject_config.txt",
                        "routes": info["routes"]}
        result = dict(result or {})
        result["engine"] = ENGINE_NAMES["inject"]
        result["routes"] = info["routes"]
        reported = result.get("out") or result.get("output")
        if result.get("ok") and reported:
            result.update(_validate_output(Path(str(reported))))
        elif result.get("ok"):
            result["ok"] = False
            result["error"] = "injector reported success without an output artifact"
        return result
    except Exception as exc:
        return {"ok": False, "engine": ENGINE_NAMES["inject"],
                "error": f"{type(exc).__name__}: {exc}", "routes": info["routes"]}
