"""Safe parser/compiler and differential oracles for Smart Lua.

Oracles validate generated/trusted fixtures. Unknown input is never executed by default.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class OracleResult:
    ok: bool
    kind: str
    score: float
    details: dict


def _source_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_source(path: Path) -> OracleResult:
    """Conservative syntax/structure oracle without executing Lua."""
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        return OracleResult(False, "parser", 0.0, {"error": str(exc)})

    if not text.strip():
        return OracleResult(False, "parser", 0.0, {"error": "empty source"})

    # Strip comments only for structural token checks; long strings are preserved.
    tokens = re.findall(
        r"(?:::|==|~=|<=|>=|...|..|[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|"
        r"[{}()\[\],;:.+*/%^#=<>~-])",
        text,
    )
    keywords = {
        "and","break","do","else","elseif","end","false","for","function","goto",
        "if","in","local","nil","not","or","repeat","return","then","true","until","while",
    }
    balance = {"(": 0, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    mismatches = 0
    for tok in tokens:
        if tok in balance:
            balance[tok] += 1
        elif tok in pairs:
            if balance[pairs[tok]] <= 0:
                mismatches += 1
            else:
                balance[pairs[tok]] -= 1
    remaining = sum(balance.values())
    kw = sum(t in keywords for t in tokens)
    control = sum(t in {"if","for","while","repeat","function","do"} for t in tokens)
    score = max(0.0, 1.0 - min(1.0, (mismatches + remaining) / max(1, len(tokens) // 20 + 1)))
    return OracleResult(
        mismatches == 0 and remaining == 0,
        "parser",
        score,
        {"bytes": path.stat().st_size, "tokens": len(tokens), "keywords": kw,
         "control_tokens": control, "delimiter_errors": mismatches,
         "open_delimiters": remaining, "sha256": _source_digest(path)},
    )


def compile_trusted_fixture(
    source: Path,
    compiler: Optional[str] = None,
    timeout: float = 10.0,
) -> OracleResult:
    """Compile a trusted fixture with an explicitly selected Lua compiler.

    This is opt-in: no compiler is guessed and no unknown input is executed.
    """
    if not source.is_file():
        return OracleResult(False, "compiler", 0.0, {"error": "missing source"})
    compiler = compiler or os.environ.get("ALVSIA_LUA_COMPILER")
    if not compiler:
        return OracleResult(False, "compiler", 0.0, {"status": "not_configured"})
    executable = shutil.which(compiler)
    if not executable:
        return OracleResult(False, "compiler", 0.0, {"error": "compiler_not_found", "compiler": compiler})

    with tempfile.TemporaryDirectory(prefix="alvsia-oracle-") as td:
        out = Path(td) / "fixture.luac"
        try:
            proc = subprocess.run(
                [executable, "-o", str(out), str(source)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return OracleResult(False, "compiler", 0.0, {"error": str(exc)})
        ok = proc.returncode == 0 and out.is_file() and out.stat().st_size > 0
        return OracleResult(ok, "compiler", 1.0 if ok else 0.0, {
            "compiler": executable, "returncode": proc.returncode,
            "bytecode_bytes": out.stat().st_size if out.is_file() else 0,
            "stderr": proc.stderr.decode("utf-8", "replace")[-2000:],
        })


def semantic_signature(path: Path) -> dict:
    """Dialect-neutral structural signature used for differential validation."""
    text = path.read_text(encoding="utf-8", errors="replace")
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|~=|<=|>=|\.\.\.|\S", text)
    keywords = {"function","return","if","then","elseif","else","end","for","while","repeat","until","local"}
    return {
        "token_count": len(tokens),
        "keyword_counts": {k: tokens.count(k) for k in sorted(keywords) if k in tokens},
        "string_literals": len(re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', text)),
        "function_markers": text.count("function"),
        "return_markers": text.count("return"),
    }


def differential_validate(original: Path, reconstructed: Path) -> OracleResult:
    """Compare two source candidates without executing either."""
    try:
        a, b = semantic_signature(original), semantic_signature(reconstructed)
    except OSError as exc:
        return OracleResult(False, "differential", 0.0, {"error": str(exc)})
    keys = ("function_markers", "return_markers")
    matches = sum(a[k] == b[k] for k in keys)
    token_ratio = min(a["token_count"], b["token_count"]) / max(1, max(a["token_count"], b["token_count"]))
    score = 0.6 * (matches / len(keys)) + 0.4 * token_ratio
    return OracleResult(score >= 0.75, "differential", score, {"original": a, "reconstructed": b})


def result_dict(result: OracleResult) -> dict:
    return asdict(result)
