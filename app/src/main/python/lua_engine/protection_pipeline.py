"""Unified Smart Lua protection pipeline.

The pipeline is deliberately deterministic and validation-first:
1. accept UTF-8 Lua/Luau source only;
2. apply the selected lexical protection profile;
3. validate the transformed source with the shared validator;
4. write atomically and return integrity metadata.

No network access, hidden telemetry, or runtime bypass behavior is involved.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import tempfile

from .engine import validate_lua_source
from .protection import PROFILES, protect_source


def protect_file(
    input_path: str | Path,
    output_path: str | Path,
    profile: str = "balanced",
    *,
    expected_version: str | None = None,
) -> dict:
    """Protect a Lua source file and publish it only after validation."""
    source = Path(input_path)
    destination = Path(output_path)

    if profile not in PROFILES:
        return {
            "ok": False,
            "error": f"unknown protection profile: {profile}",
            "profile": profile,
        }
    if not source.is_file():
        return {"ok": False, "error": "input file not found", "file": str(source)}

    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {
            "ok": False,
            "error": f"input is not valid UTF-8 Lua source: {exc}",
            "file": str(source),
        }

    transformed = protect_source(text, PROFILES[profile])
    valid, validation = validate_lua_source(
        transformed, expected_version=expected_version
    )
    if not valid:
        return {
            "ok": False,
            "error": "protected output failed validation: " + validation,
            "profile": profile,
            "validation": validation,
        }

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(transformed)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    finally:
        try:
            Path(temporary_name).unlink(missing_ok=True)
        except OSError:
            pass

    digest = sha256(destination.read_bytes()).hexdigest()
    return {
        "ok": True,
        "profile": profile,
        "out": str(destination),
        "sha256": digest,
        "input_size": len(raw),
        "output_size": destination.stat().st_size,
        "validation": validation,
    }
