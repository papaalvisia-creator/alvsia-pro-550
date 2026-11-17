"""Unified module-adapter facade for ALVSIA PRO tool modules.

The adapter layer gives the Android bridge one deterministic Python entry point
without duplicating the underlying engines. Each operation is file-backed,
bounded, and returns a JSON-serializable result. No shell or network access is
introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    operation: str
    runner: Callable[..., dict]


def _lua_decompile(
    input_path: str | Path,
    output_path: str | Path,
    jars_dir: str | Path | None = None,
) -> dict:
    """Use the complete Smart Lua recovery path for the production adapter.

    The old adapter called run_decompiler_pipeline directly, bypassing the
    protected-pattern preflight, recursive layer analysis, and Smart Lua
    recovery stages exposed by alvsia_features.run_lua_smart.
    """
    import shutil

    src = Path(input_path)
    dst = Path(output_path)
    if not src.is_file():
        return {"ok": False, "module": "lua", "operation": "decompile",
                "error": "input file not found"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from alvsia_features import run_lua_smart
        result = run_lua_smart(src, dst.parent, jars_dir=str(jars_dir) if jars_dir else None)
    except Exception as exc:
        return {"ok": False, "module": "lua", "operation": "decompile",
                "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(result, dict):
        result = {"ok": bool(result)}
    else:
        result = dict(result)

    # Smart Lua may choose a descriptive artifact filename. Promote only an
    # existing, non-empty Lua source artifact; never fabricate output from a
    # diagnostic/partial report.
    reported = result.get("out")
    if result.get("ok") and reported:
        candidate = Path(str(reported))
        if candidate.is_file() and candidate.stat().st_size > 0 and candidate.suffix.lower() == ".lua":
            if candidate.resolve() != dst.resolve():
                shutil.copy2(candidate, dst)
            result["out"] = str(dst)
            result["output_bytes"] = dst.stat().st_size
    if result.get("ok") and (not dst.is_file() or dst.stat().st_size == 0):
        result["ok"] = False
        result["error"] = "Smart Lua reported success without a non-empty Lua source artifact"
    result.update({"module": "lua", "operation": "decompile"})
    return result


def _lua_protect(input_path: str | Path, output_path: str | Path,
                 profile: str = "balanced", expected_version: str | None = None) -> dict:
    from lua_engine.protection_pipeline import protect_file
    result = protect_file(input_path, output_path, profile, expected_version=expected_version)
    result = dict(result)
    result.update({"module": "lua", "operation": "protect"})
    return result


def _string_recover(input_path: str | Path, output_dir: str | Path) -> dict:
    from lua_string_recover import recover_strings
    src = Path(input_path)
    if not src.is_file():
        return {"ok": False, "module": "string-recovery", "operation": "recover",
                "error": "input file not found"}
    report = recover_strings(src.read_bytes(), Path(output_dir), src.stem)
    result = dict(report)
    result.update({"ok": True, "module": "string-recovery", "operation": "recover"})
    return result


def _archive_inspect(input_path: str | Path, output_file: str | Path | None = None) -> dict:
    from archive_engine import inspect_archive
    result = inspect_archive(input_path, output_file)
    result = dict(result)
    result.setdefault("module", "archive")
    result.setdefault("operation", "inspect")
    return result


def _archive_extract(input_path: str | Path, output_dir: str | Path) -> dict:
    from archive_engine import extract_archive
    result = extract_archive(input_path, output_dir)
    result = dict(result)
    result.setdefault("module", "archive")
    result.setdefault("operation", "extract")
    return result


def _intelligence_analyze(input_path: str | Path, output_dir: str | Path,
                          max_depth: int = 12, max_artifacts: int = 128) -> dict:
    from lua_intelligence.core import IntelligenceConfig, analyze_file
    config = IntelligenceConfig(max_depth=max_depth, max_artifacts=max_artifacts)
    result = analyze_file(input_path, output_dir, config)
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    result = dict(result)
    result.setdefault("ok", True)
    result.update({"module": "program-intelligence", "operation": "analyze"})
    return result



def _require_output(result: dict, expected_suffixes: tuple[str, ...] = ()) -> dict:
    """Turn engine-reported success into a verifiable adapter success."""
    if not isinstance(result, dict):
        return {"ok": False, "error": "engine returned a non-object result"}
    result = dict(result)
    reported = result.get("out") or result.get("output")
    if reported:
        candidate = Path(str(reported))
        if not candidate.is_file() or candidate.stat().st_size <= 0:
            result["ok"] = False
            result["error"] = "engine reported an output that does not exist or is empty"
            return result
        if expected_suffixes and candidate.suffix.lower() not in expected_suffixes:
            result["ok"] = False
            result["error"] = "engine output has an unexpected file type"
    return result


def _lua_inject_patch(input_path: str | Path, output_dir: str | Path,
                      offset: str, patch_hex: str) -> dict:
    """Validated adapter for the existing bytecode patch engine."""
    import alvsia_ultimate as ultimate
    src = Path(input_path)
    if not src.is_file():
        return {"ok": False, "module": "lua", "operation": "inject-patch",
                "error": "input file not found"}
    result = ultimate.lua_patch_bytecode(str(src), Path(output_dir), str(offset), str(patch_hex))
    result = _require_output(dict(result) if isinstance(result, dict) else {"ok": False, "error": str(result)})
    result.update({"module": "lua", "operation": "inject-patch"})
    return result


def _lua_inject_hook(input_path: str | Path, output_dir: str | Path,
                     hook_path: str | Path) -> dict:
    """Validated adapter for the existing hook-injection engine."""
    import alvsia_ultimate as ultimate
    src = Path(input_path)
    hook = Path(hook_path)
    if not src.is_file() or not hook.is_file():
        return {"ok": False, "module": "lua", "operation": "inject-hook",
                "error": "input or hook file not found"}
    result = ultimate.lua_inject_hook(str(src), Path(output_dir), str(hook))
    result = _require_output(dict(result) if isinstance(result, dict) else {"ok": False, "error": str(result)})
    result.update({"module": "lua", "operation": "inject-hook"})
    return result


def _lua_mod_repack(input_path: str | Path, mod_dir: str | Path,
                    output_path: str | Path) -> dict:
    """Use the existing Smart PAK repacker, with the legacy engine as fallback."""
    import alvsia_core as core
    src = Path(input_path)
    mods = Path(mod_dir)
    dest = Path(output_path)
    if not src.is_file() or not mods.is_dir():
        return {"ok": False, "module": "lua", "operation": "mod-repack",
                "error": "base PAK or modified tree not found"}
    result = core.run_pak_smart_repack(src, mods, dest)
    if not isinstance(result, dict) or not result.get("ok"):
        result = core.run_pak_repack(src, mods, dest)
    result = _require_output(dict(result) if isinstance(result, dict) else {"ok": False, "error": str(result)})
    result.update({"module": "lua", "operation": "mod-repack"})
    return result


def _lua_vm_protect(input_path: str | Path, output_path: str | Path,
                    num_decoys: int = 1024) -> dict:
    """Use the real ALVSEAL3 VM protector and verify the emitted artifact."""
    from alvsia_vm_protect import vm_protect
    src = Path(input_path)
    dest = Path(output_path)
    if not src.is_file():
        return {"ok": False, "module": "lua", "operation": "vm-protect",
                "error": "input file not found"}
    result = vm_protect(src, dest, output_format="lua", num_decoys=max(64, min(int(num_decoys), 4096)))
    result = _require_output(dict(result) if isinstance(result, dict) else {"ok": False, "error": str(result)}, (".lua",))
    result.update({"module": "lua", "operation": "vm-protect"})
    return result


def _archive_repack(input_path: str | Path, output_dir: str | Path) -> dict:
    """Repack an already extracted OBB tree without changing the archive engine."""
    from archive_engine import repack_obb
    src = Path(input_path)
    out = Path(output_dir)
    if not src.is_dir():
        return {"ok": False, "module": "archive", "operation": "repack",
                "error": "extracted archive directory not found"}
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (src.name + "_rezip.obb")
    result = repack_obb(src, dest)
    result = _require_output(dict(result) if isinstance(result, dict) else {"ok": False, "error": str(result)}, (".obb",))
    result.update({"module": "archive", "operation": "repack"})
    return result


def _smart_lua_decompile(input_path, output_path, jars_dir=None):
    from smart_lua_engine import decompile
    return decompile(input_path, Path(output_path).parent, jars_dir=jars_dir)


def _smart_lua_protect(input_path, output_path, profile="auto"):
    from smart_lua_engine import protect
    return protect(input_path, output_path, profile=profile)


def _smart_lua_compile(input_path, output_dir, jars_dir=None):
    from smart_lua_engine import compile_or_recompile
    return compile_or_recompile(input_path, output_dir, jars_dir=jars_dir)


def _smart_lua_inject(input_path, output_dir, mode="auto"):
    from smart_lua_engine import inject
    return inject(input_path, output_dir, mode=mode)


_ADAPTERS: dict[tuple[str, str], Callable[..., dict]] = {
    ("lua", "decompile"): _smart_lua_decompile,
    ("lua", "protect"): _smart_lua_protect,
    ("lua", "compile"): _smart_lua_compile,
    ("lua", "inject"): _smart_lua_inject,
    ("string-recovery", "recover"): _string_recover,
    ("archive", "inspect"): _archive_inspect,
    ("archive", "extract"): _archive_extract,
    ("program-intelligence", "analyze"): _intelligence_analyze,
}


def list_adapters() -> list[dict[str, str]]:
    return [
        {"module": module, "operation": operation}
        for module, operation in sorted(_ADAPTERS)
    ]


def dispatch(module: str, operation: str, **kwargs: Any) -> dict:
    """Dispatch exactly one registered operation.

    Unknown operations fail closed instead of falling through to arbitrary
    imports or shell commands.
    """
    key = (str(module).strip().lower(), str(operation).strip().lower())
    runner = _ADAPTERS.get(key)
    if runner is None:
        return {"ok": False, "module": key[0], "operation": key[1],
                "error": "adapter operation not registered"}
    try:
        return runner(**kwargs)
    except TypeError as exc:
        return {"ok": False, "module": key[0], "operation": key[1],
                "error": f"invalid adapter arguments: {exc}"}
    except Exception as exc:
        return {"ok": False, "module": key[0], "operation": key[1],
                "error": f"{type(exc).__name__}: {exc}"}
