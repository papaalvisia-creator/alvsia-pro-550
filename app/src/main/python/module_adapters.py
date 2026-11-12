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



def _lua_unified(operation: str, input_path: str | Path,
                 output_dir: str | Path | None = None,
                 output_path: str | Path | None = None,
                 jars_dir: str | Path | None = None,
                 work_dir: str | Path | None = None,
                 sub_id: str = "", profile: str = "balanced") -> dict:
    """Single Smart Lua mechanism; providers are selected internally.

    Accept output_path for older callers and output_dir for the unified bridge.
    A requested decompiler filename is materialized only from a real validated
    source artifact returned by the engine.
    """
    import shutil
    from smart_lua_engine import execute

    requested = Path(output_path) if output_path is not None else None
    target_dir = Path(output_dir) if output_dir is not None else (
        requested.parent if requested is not None else None
    )
    if target_dir is None:
        return {"ok": False, "module": "lua", "operation": operation,
                "error": "output_dir or output_path is required"}
    target_dir.mkdir(parents=True, exist_ok=True)
    result = execute(
        operation,
        input_path,
        target_dir,
        jars_dir=jars_dir,
        work_dir=work_dir,
        sub_id=sub_id,
        profile=profile,
    )
    result = dict(result or {})
    if operation == "decompile" and result.get("ok") and requested is not None:
        reported = result.get("out")
        candidate = Path(str(reported)) if reported else None
        if candidate is None or not candidate.is_file() or candidate.stat().st_size <= 0:
            result.update({"ok": False, "error": "decompiler returned no valid source artifact"})
        elif candidate.suffix.lower() != ".lua":
            result.update({"ok": False, "error": "decompiler output is not a Lua source file"})
        else:
            requested.parent.mkdir(parents=True, exist_ok=True)
            if candidate.resolve() != requested.resolve():
                shutil.copy2(candidate, requested)
            result["out"] = str(requested)
            result["output_bytes"] = requested.stat().st_size
    result.update({"module": "lua", "operation": operation})
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


def _data_smart(operation: str, input_path: str | Path,
                output_dir: str | Path, work_dir: str | Path | None = None) -> dict:
    from smart_data_engine import execute
    result = execute(operation, input_path, output_dir, work_dir=work_dir)
    result = dict(result or {})
    result.update({"module": "data", "operation": operation})
    return result


def _archive_smart(operation: str, input_path: str | Path | None,
                  output_dir: str | Path | None = None,
                  work_dir: str | Path | None = None,
                  archive_kind: str = "auto") -> dict:
    from smart_archive_engine import execute
    target_dir = Path(output_dir) if output_dir is not None else (
        Path(input_path).parent / "_alvsia_archive_out" if input_path else Path("_alvsia_archive_out")
    )
    result = execute(
        operation, input_path, target_dir,
        work_dir=work_dir, archive_kind=archive_kind,
    )
    result = dict(result or {})
    result.update({"module": "archive", "operation": operation})
    return result



def _pak_lua_smart(input_path: str | Path, output_dir: str | Path,
                   work_dir: str | Path | None = None) -> dict:
    from smart_pak_lua_engine import execute
    result = execute(input_path, output_dir, work_dir=work_dir, archive_kind="pak")
    result = dict(result or {})
    result.update({"module": "archive", "operation": "smart-lua-scan"})
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


_ADAPTERS: dict[tuple[str, str], Callable[..., dict]] = {
    ("lua", "decompile"): lambda **kw: _lua_unified("decompile", **kw),
    ("lua", "analyze"): lambda **kw: _lua_unified("analyze", **kw),
    ("lua", "protect"): lambda **kw: _lua_unified("protect", **kw),
    ("lua", "compile"): lambda **kw: _lua_unified("compile", **kw),
    ("lua", "inject"): lambda **kw: _lua_unified("inject", **kw),
    ("lua", "encrypt"): lambda **kw: _lua_unified("encrypt", **kw),
    ("lua", "restore"): lambda **kw: _lua_unified("restore", **kw),
    ("lua", "vm-protect"): lambda **kw: _lua_unified("vm-protect", **kw),
    ("string-recovery", "recover"): _string_recover,
    ("archive", "inspect"): lambda **kw: _archive_smart("inspect", **kw),
    ("archive", "extract"): lambda **kw: _archive_smart("extract", **kw),
    ("archive", "rebuild"): lambda **kw: _archive_smart("rebuild", **kw),
    ("archive", "integrity"): lambda **kw: _archive_smart("integrity", **kw),
    ("archive", "smart-lua-scan"): _pak_lua_smart,
    ("data", "recover"): lambda **kw: _data_smart("recover", **kw),
    ("data", "xor"): lambda **kw: _data_smart("xor", **kw),
    ("data", "sm4"): lambda **kw: _data_smart("sm4", **kw),
    ("data", "metadata"): lambda **kw: _data_smart("metadata", **kw),
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
