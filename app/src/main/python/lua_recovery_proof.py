"""Bytecode-to-source recovery proof layer.

The proof is deliberately stronger than a syntax check: when a compatible
compiler is available, compile the recovered source and compare normalized
VM listings against the original bytecode. A passing proof means the recovered
source reproduces the observed instruction-level program under that compiler.
It does not pretend that comments, formatting, or stripped local names are
recoverable when the input no longer contains them.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def _find_luac() -> Path | None:
    configured = os.environ.get("ALVSIA_LUAC", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates += [
        Path("/data/data/com.alvsia.pro/files/EXES/luac"),
        Path("/data/data/com.alvsia.pro/files/chaquopy/AssetFinder/EXES/luac"),
    ]
    for name in ("luac5.4", "luac5.3", "luac53", "luac5.2", "luac5.1", "luac"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    return None


def _listing_signature(luac: Path, chunk: Path) -> tuple[str, int, str]:
    """Return a stable signature from luac -l -l, ignoring debug addresses."""
    proc = subprocess.run(
        [str(luac), "-l", "-l", str(chunk)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(text.strip()[:1000] or "luac listing failed")

    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        # Keep instruction/opcode/operand information and constants. Remove
        # source paths and line-number columns, which can differ after recovery.
        if re.match(r"^\d+\s+\[.*?\]\s+\d+\s+", line):
            line = re.sub(r"^\d+\s+\[[^]]*\]\s+\d+\s+", "", line)
            line = re.sub(r"\s+;\s*.*$", "", line)
            lines.append(line)
        elif line.startswith("constants (") or line.startswith("locals (") or line.startswith("upvalues ("):
            # Debug metadata is evidence, not semantic identity.
            if not line.startswith(("locals (", "upvalues (")):
                lines.append(line)
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(lines), payload.decode("utf-8", "replace")


def prove_roundtrip(original: str | Path, recovered_source: str | Path) -> dict:
    """Try an instruction-level round-trip proof; never executes Lua code."""
    src = Path(original)
    recovered = Path(recovered_source)
    if not src.is_file() or not recovered.is_file():
        return {"status": "UNPROVEN", "reason": "input or recovered source missing"}
    luac = _find_luac()
    if luac is None:
        return {"status": "UNPROVEN", "reason": "compatible luac compiler unavailable"}

    with tempfile.TemporaryDirectory(prefix="alvsia-proof-") as td:
        compiled = Path(td) / "recovered.luac"
        try:
            compile_proc = subprocess.run(
                [str(luac), "-o", str(compiled), str(recovered)],
                capture_output=True, text=True, timeout=180, check=False,
            )
            if compile_proc.returncode != 0 or not compiled.is_file():
                detail = (compile_proc.stderr or compile_proc.stdout or "").strip()
                return {"status": "UNPROVEN", "reason": "recovered source does not compile",
                        "detail": detail[:1000], "compiler": str(luac)}
            original_sig, original_lines, _ = _listing_signature(luac, src)
            recovered_sig, recovered_lines, _ = _listing_signature(luac, compiled)
            if original_sig == recovered_sig:
                return {
                    "status": "ROUNDTRIP_VERIFIED",
                    "confidence": 1.0,
                    "compiler": str(luac),
                    "original_instruction_lines": original_lines,
                    "recovered_instruction_lines": recovered_lines,
                    "signature": original_sig,
                    "claim": "recovered source reproduces the observed VM listing",
                }
            return {
                "status": "DIVERGED",
                "confidence": 0.0,
                "compiler": str(luac),
                "original_instruction_lines": original_lines,
                "recovered_instruction_lines": recovered_lines,
                "original_signature": original_sig,
                "recovered_signature": recovered_sig,
            }
        except subprocess.TimeoutExpired:
            return {"status": "UNPROVEN", "reason": "round-trip compiler/listing timeout",
                    "compiler": str(luac)}
        except Exception as exc:
            return {"status": "UNPROVEN",
                    "reason": f"{type(exc).__name__}: {exc}"}


__all__ = ["prove_roundtrip"]
