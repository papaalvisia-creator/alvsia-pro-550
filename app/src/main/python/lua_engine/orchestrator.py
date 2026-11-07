"""Unified, format-aware Lua decompiler orchestration.

This module coordinates the decompiler engines already shipped by ALVSIA.
It deliberately does not invent command-line flags for tools that have not
been inventoried or licensed. Missing engines are reported as unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional
import os
import shutil
import subprocess

from .engine import validate_lua_source, _find_java


@dataclass(frozen=True)
class EngineResult:
    engine: str
    ok: bool
    output: Optional[str] = None
    note: str = ""
    selected: bool = False


@dataclass(frozen=True)
class EngineSpec:
    name: str
    formats: tuple[str, ...]
    runner: Callable[[Path, Path], tuple[bool, str]]
    priority: int = 100


def _find_unluac_rs(jars_dir: Optional[str]) -> Optional[Path]:
    """Locate an explicitly installed Android-compatible unluac-rs CLI."""
    configured = os.environ.get("ALVSIA_UNLUAC_RS_BIN", "").strip()
    candidates = [Path(configured)] if configured else []
    if jars_dir:
        root = Path(jars_dir)
        candidates.extend((
            root / "unluac-cli",
            root / "bin" / "unluac-cli",
            root / "unluac-cli-aarch64",
        ))
    found = shutil.which("unluac-cli")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            if not os.access(candidate, os.X_OK):
                candidate.chmod(candidate.stat().st_mode | 0o100)
        except OSError:
            continue
        if os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_unluac_rs(binary: Path, src: Path, dst: Path) -> tuple[bool, str]:
    """Run the pinned CLI without a shell and require its requested output file."""
    dst.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [
                str(binary), "-i", str(src), "-o", str(dst),
                "--generate-mode", "strict",
            ],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired:
        dst.unlink(missing_ok=True)
        return False, "unluac-rs timed out after 180 seconds"
    except Exception as exc:
        dst.unlink(missing_ok=True)
        return False, f"unluac-rs launch failed: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        dst.unlink(missing_ok=True)
        detail = (proc.stderr or proc.stdout or "no diagnostic").strip()
        return False, f"unluac-rs exit={proc.returncode}: {detail[:700]}"
    if not dst.is_file() or dst.stat().st_size == 0:
        dst.unlink(missing_ok=True)
        return False, "unluac-rs exited successfully but produced no source file"
    detail = (proc.stderr or proc.stdout or "strict generation completed").strip()
    return True, f"unluac-rs strict mode: {detail[:400]}"


def _available_unluac(jars_dir: Optional[str]) -> bool:
    if not jars_dir or not _find_java():
        return False
    root = Path(jars_dir)
    names = (
        "unluac_2025_12_23.jar",
        "unluac_pro.jar",
        "unluac_patched.jar",
        "unluac.jar",
    )
    return any((root / name).is_file() and (root / name).stat().st_size > 1000
               for name in names)


def build_engine_registry(info, jars_dir: Optional[str] = None) -> list[EngineSpec]:
    """Return only engines compatible with the detected format/version."""
    from .streaming_decompiler import (
        stream_decompile_lua53,
        stream_decompile_luajit,
        stream_unluac_jar,
    )

    specs: list[EngineSpec] = []
    unluac_rs = _find_unluac_rs(jars_dir)
    if unluac_rs and (
        info.format in ("luac", "luac-unknown", "luau")
        or (info.format == "luajit" and info.version == "LuaJIT 2.1")
    ):
        # Keep the proven local Lua 5.3 engine first; use unluac-rs as the
        # multi-dialect fallback. LuaJIT 2.0 is deliberately not routed here.
        priority = 20 if info.format == "luac" and info.version == "Lua 5.3" else 10
        specs.append(EngineSpec(
            "unluac_rs_v1_4_4",
            ("luac", "luac-unknown", "luajit", "luau"),
            lambda src, dst, binary=unluac_rs: _run_unluac_rs(binary, src, dst),
            priority,
        ))
    if info.format == "luac" and info.version == "Lua 5.3":
        specs.append(EngineSpec(
            "alvsia_lua53", ("luac",),
            lambda src, dst: stream_decompile_lua53(src, dst), 10,
        ))
    elif info.format == "luajit":
        specs.append(EngineSpec(
            "alvsia_luajit_disassembler", ("luajit",),
            lambda src, dst: stream_decompile_luajit(src, dst), 10,
        ))

    if info.format in ("luac", "luac-unknown") and _available_unluac(jars_dir):
        specs.append(EngineSpec(
            "unluac_jar", ("luac", "luac-unknown"),
            lambda src, dst: stream_unluac_jar(src, dst, jars_dir=jars_dir),
            30,
        ))
    return sorted(specs, key=lambda item: item.priority)


def run_decompiler_pipeline(
    input_path: str | Path,
    output_path: str | Path,
    info,
    jars_dir: Optional[str] = None,
    *,
    registry: Optional[Iterable[EngineSpec]] = None,
) -> dict:
    """Run compatible engines, validate each result, and select a real output.

    Every engine receives a distinct candidate path. Failed/invalid candidates
    are removed. The original input is never modified. Valid alternatives are
    retained beside the selected output for transparent comparison.
    """
    source = Path(input_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    alternate_dir = destination.parent / (destination.stem + "_alternates")
    specs = list(registry) if registry is not None else build_engine_registry(
        info, jars_dir=jars_dir
    )
    specs = [spec for spec in specs if info.format in spec.formats]
    specs.sort(key=lambda item: item.priority)

    results: list[EngineResult] = []
    valid_candidates: list[tuple[EngineSpec, Path, str]] = []
    for index, spec in enumerate(specs, 1):
        candidate = destination.parent / (
            destination.stem + f".candidate_{index}_{spec.name}.lua"
        )
        candidate.unlink(missing_ok=True)
        try:
            ok, note = spec.runner(source, candidate)
        except Exception as exc:
            ok, note = False, f"{type(exc).__name__}: {exc}"
        if not ok or not candidate.is_file() or candidate.stat().st_size == 0:
            candidate.unlink(missing_ok=True)
            results.append(EngineResult(spec.name, False, note=str(note)[:800]))
            continue
        valid, validation_note = validate_lua_source(candidate, expected_version=info.version)
        if not valid:
            candidate.unlink(missing_ok=True)
            results.append(EngineResult(
                spec.name, False, note=("output rejected: " + validation_note)[:800]
            ))
            continue
        valid_candidates.append((spec, candidate, str(note)[:400]))

    selected_name = None
    if valid_candidates:
        selected_spec, selected_path, selected_note = valid_candidates[0]
        selected_path.replace(destination)
        selected_name = selected_spec.name
        results.append(EngineResult(
            selected_spec.name, True, str(destination),
            selected_note + "; " + "validated Lua source", True,
        ))
        if len(valid_candidates) > 1:
            alternate_dir.mkdir(parents=True, exist_ok=True)
            for spec, candidate, note in valid_candidates[1:]:
                retained = alternate_dir / (spec.name + ".lua")
                candidate.replace(retained)
                results.append(EngineResult(
                    spec.name, True, str(retained),
                    note + "; validated alternate",
                ))
    else:
        for spec, candidate, note in valid_candidates:
            candidate.unlink(missing_ok=True)

    return {
        "ok": selected_name is not None,
        "out": str(destination) if selected_name else None,
        "selected_engine": selected_name,
        "engines_attempted": [item.name for item in specs],
        "results": [
            {
                "engine": item.engine,
                "ok": item.ok,
                "output": item.output,
                "note": item.note,
                "selected": item.selected,
            }
            for item in results
        ],
        "alternates_dir": str(alternate_dir) if alternate_dir.is_dir() else None,
        "error": None if selected_name else (
            "no compatible installed decompiler produced validated Lua source"
        ),
    }
