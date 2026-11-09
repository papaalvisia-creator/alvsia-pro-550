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
from lua_intelligence.fusion import FusionCandidate, fuse_candidates


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


def _engine_timeout(default: int = 180) -> int:
    """Use tighter limits in the Android app so a stalled parser cannot hold the UI job."""
    if os.environ.get("ALVSIA_SEALED_RUNTIME") == "1":
        return min(default, 90)
    return default


def _run_unluac_rs(binary: Path, src: Path, dst: Path) -> tuple[bool, str]:
    """Run the pinned CLI without a shell and require its requested output file."""
    dst.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [
                str(binary), "-i", str(src), "-o", str(dst),
                "--generate-mode", "strict",
            ],
            capture_output=True, text=True, timeout=_engine_timeout(), check=False,
        )
    except subprocess.TimeoutExpired:
        dst.unlink(missing_ok=True)
        return False, f"unluac-rs timed out after {_engine_timeout()} seconds"
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


def _find_luau_decompiler_cli(jars_dir: Optional[str]) -> Optional[Path]:
    configured = os.environ.get("ALVSIA_LUAU_DECOMPILER_BIN", "").strip()
    candidates = [Path(configured)] if configured else []
    if jars_dir:
        root = Path(jars_dir)
        candidates.extend((
            root / "luau-decompiler",
            root / "luau-decompiler-cli",
            root / "bin" / "luau-decompiler",
        ))
    found = shutil.which("luau-decompiler")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _run_luau_decompiler_cli(binary: Path, src: Path, dst: Path) -> tuple[bool, str]:
    dst.unlink(missing_ok=True)
    try:
        proc = subprocess.run(
            [str(binary), str(src), "-o", str(dst)],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except subprocess.TimeoutExpired:
        dst.unlink(missing_ok=True)
        return False, f"Luau decompiler CLI timed out after {_engine_timeout()} seconds"
    except Exception as exc:
        dst.unlink(missing_ok=True)
        return False, f"Luau decompiler CLI launch failed: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        dst.unlink(missing_ok=True)
        detail = (proc.stderr or proc.stdout or "no diagnostic").strip()
        return False, f"Luau decompiler CLI exit={proc.returncode}: {detail[:700]}"
    if not dst.is_file() or dst.stat().st_size == 0:
        dst.unlink(missing_ok=True)
        return False, "Luau decompiler CLI exited successfully but produced no source file"
    detail = (proc.stderr or "Luau source emitted").strip()
    return True, f"Luau decompiler CLI: {detail[:400]}"


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


def _copy_lua_source(src: Path, dst: Path) -> tuple[bool, str]:
    shutil.copy2(src, dst)
    return True, "validated Lua source passthrough"


def build_engine_registry(info, jars_dir: Optional[str] = None) -> list[EngineSpec]:
    """Return only engines compatible with the detected format/version."""
    from .streaming_decompiler import (
        stream_decompile_lua53,
        stream_decompile_luajit,
        stream_unluac_jar,
    )

    specs: list[EngineSpec] = []
    if info.format == "lua-source":
        specs.append(EngineSpec(
            "source_passthrough", ("lua-source",), _copy_lua_source, 0,
        ))
    unluac_rs = _find_unluac_rs(jars_dir)
    luau_version = None
    if info.format == "luau":
        try:
            luau_version = int(str(info.version).rsplit("v", 1)[-1])
        except (TypeError, ValueError):
            luau_version = None
    # The pinned PumbaaDev parser handles Luau bytecode v3-v9. Versions
    # 10+ remain opt-in upstream because opcode semantics can diverge.
    luau_supported = luau_version is not None and 3 <= luau_version <= 9
    luau_decompiler = _find_luau_decompiler_cli(jars_dir)
    if info.format == "luau" and luau_supported and luau_decompiler:
        specs.append(EngineSpec(
            "pumbaadev_luau_decompiler_v0_2",
            ("luau",),
            lambda src, dst, binary=luau_decompiler: _run_luau_decompiler_cli(binary, src, dst),
            5,
        ))
    # Luau stays on the dedicated PumbaaDev backend. The unluac-rs CLI is
    # not a Luau engine and is never selected for this format.
    if unluac_rs and (
        info.format in ("luac", "luac-unknown")
        or (info.format == "luajit" and info.version == "LuaJIT 2.1")
    ):
        # Keep the proven local Lua 5.3 engine first; use unluac-rs as the
        # multi-dialect fallback. LuaJIT 2.0 is deliberately not routed here.
        priority = 20 if info.format == "luac" and info.version == "Lua 5.3" else 10
        specs.append(EngineSpec(
            "unluac_rs_v1_4_4",
            ("luac", "luac-unknown", "luajit"),
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
    deep_scan: Optional[bool] = None,
) -> dict:
    """Run compatible engines, validate each result, and select a real output.

    Every engine receives a distinct candidate path. Failed/invalid candidates
    are removed. The original input is never modified. Valid alternatives are
    retained beside the selected output for transparent comparison.
    """
    if deep_scan is None:
        # The installed Android app prefers a quick, memory-bounded result.
        # Deep comparison remains opt-in for explicit diagnostics.
        deep_scan = os.environ.get("ALVSIA_LUA_DEEP_SCAN", "0") == "1"

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
        valid_candidates.append((
            spec, candidate,
            (str(note) + "; " + str(validation_note))[:700],
        ))
        # In normal app operation, stop as soon as a real, validated source
        # exists. Running every compatible parser after success can waste
        # minutes and trigger Android low-memory process kills. Deep scan is
        # explicitly opt-in and retains alternate engine outputs.
        if not deep_scan:
            break

    selected_name = None
    fusion = None
    if valid_candidates:
        # Deep mode is the only mode allowed to fuse multiple engines. The
        # quick Android path preserves its historical first-valid behavior.
        if deep_scan and len(valid_candidates) > 1:
            fusion = fuse_candidates([
                FusionCandidate(spec.name, candidate, note)
                for spec, candidate, note in valid_candidates
            ])
            if fusion.status != "CONSENSUS" or fusion.selected_engine is None:
                # Multiple independent outputs that disagree are evidence of
                # uncertainty, not permission to publish the first candidate.
                # Preserve candidates for diagnostics and return explicit
                # failure rather than a false SUCCESS.
                alternate_dir.mkdir(parents=True, exist_ok=True)
                for spec, candidate, note in valid_candidates:
                    retained = alternate_dir / (spec.name + ".lua")
                    candidate.replace(retained)
                    results.append(EngineResult(
                        spec.name, True, str(retained),
                        note + "; retained because fusion has no consensus",
                    ))
                return {
                    "ok": False,
                    "out": None,
                    "selected_engine": None,
                    "engines_attempted": [item.engine for item in results],
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
                    "alternates_dir": str(alternate_dir),
                    "fusion": {
                        "status": fusion.status,
                        "confidence": fusion.confidence,
                        "scores": fusion.scores,
                        "agreement": fusion.agreement,
                        "reasons": list(fusion.reasons),
                    },
                    "error": "multiple validated candidates disagree; semantic consensus required",
                }
            selected_tuple = next(
                item for item in valid_candidates
                if item[0].name == fusion.selected_engine
            )
            selected_spec, selected_path, selected_note = selected_tuple
        else:
            selected_spec, selected_path, selected_note = valid_candidates[0]

        selected_path.replace(destination)
        selected_name = selected_spec.name
        fusion_note = ""
        if fusion is not None:
            fusion_note = (
                f"; fusion={fusion.status}; confidence={fusion.confidence:.3f}; "
                f"agreement={fusion.agreement.get(selected_spec.name, 0)}"
            )
        results.append(EngineResult(
            selected_spec.name, True, str(destination),
            selected_note + "; validated Lua source" + fusion_note, True,
        ))
        if len(valid_candidates) > 1:
            alternate_dir.mkdir(parents=True, exist_ok=True)
            for spec, candidate, note in valid_candidates:
                if candidate == selected_path:
                    continue
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
        "engines_attempted": [item.engine for item in results],
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
        "fusion": ({
            "status": fusion.status,
            "confidence": fusion.confidence,
            "scores": fusion.scores,
            "agreement": fusion.agreement,
            "reasons": list(fusion.reasons),
        } if fusion is not None else None),
        "error": None if selected_name else (
            "no compatible installed decompiler produced validated Lua source"
        ),
    }
