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


def _lua_decompile(input_path: str | Path, output_path: str | Path) -> dict:
    from lua_engine.detector import detect_lua
    from lua_engine.orchestrator import run_decompiler_pipeline
    src = Path(input_path)
    dst = Path(output_path)
    if not src.is_file():
        return {"ok": False, "module": "lua", "operation": "decompile",
                "error": "input file not found"}
    info = detect_lua(src)
    if info.kind == "unknown":
        return {"ok": False, "module": "lua", "operation": "decompile",
                "error": "unsupported or unrecognized Lua/Luau input",
                "format": info.format}
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_decompiler_pipeline(src, dst, info)
    except Exception as exc:
        return {"ok": False, "module": "lua", "operation": "decompile",
                "error": f"{type(exc).__name__}: {exc}"}
    if isinstance(result, dict):
        result = dict(result)
        result.setdefault("ok", False)
    else:
        result = {"ok": bool(result)}
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


_ADAPTERS: dict[tuple[str, str], Callable[..., dict]] = {
    ("lua", "decompile"): _lua_decompile,
    ("lua", "protect"): _lua_protect,
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
