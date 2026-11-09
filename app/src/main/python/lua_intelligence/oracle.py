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
    """Conservative streaming syntax/structure oracle without executing Lua."""
    try:
        size = path.stat().st_size
        h = hashlib.sha256()
        balance = {"(": 0, "[": 0, "{": 0}
        pairs = {")": "(", "]": "[", "}": "{"}
        mismatches = tokens = kw = control = 0
        keywords = {
            "and","break","do","else","elseif","end","false","for","function","goto",
            "if","in","local","nil","not","or","repeat","return","then","true","until","while",
        }
        # The scanner deliberately works chunk-by-chunk so multi-megabyte files never
        # need to be materialized as one Python string.
        carry = ""
        with path.open("rb") as fh:
            while True:
                raw = fh.read(1024 * 1024)
                if not raw:
                    break
                h.update(raw)
                text = carry + raw.decode("utf-8", "replace")
                carry = text[-128:]
                scan = text[:-128] if len(text) > 128 else ""
                parts = re.findall(
                    r"[A-Za-z_][A-Za-z0-9_]*|\\d+(?:\\.\\d+)?|==|~=|<=|>=|\\.\\.\\.|[{}()\\[\\],;:.+*/%^#=<>~-]",
                    scan,
                )
                tokens += len(parts)
                kw += sum(t in keywords for t in parts)
                control += sum(t in {"if","for","while","repeat","function","do"} for t in parts)
                for tok in parts:
                    if tok in balance:
                        balance[tok] += 1
                    elif tok in pairs:
                        if balance[pairs[tok]] <= 0:
                            mismatches += 1
                        else:
                            balance[pairs[tok]] -= 1
        tokens += len(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\\d+(?:\\.\\d+)?|==|~=|<=|>=|\\.\\.\\.|[{}()\\[\\],;:.+*/%^#=<>~-]", carry))
        remaining = sum(balance.values())
        if size == 0:
            return OracleResult(False, "parser", 0.0, {"error": "empty source"})
        score = max(0.0, 1.0 - min(1.0, (mismatches + remaining) / max(1, tokens // 20 + 1)))
        return OracleResult(
            mismatches == 0 and remaining == 0, "parser", score,
            {"bytes": size, "tokens": tokens, "keywords": kw,
             "control_tokens": control, "delimiter_errors": mismatches,
             "open_delimiters": remaining, "sha256": h.hexdigest()},
        )
    except OSError as exc:
        return OracleResult(False, "parser", 0.0, {"error": str(exc)})

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
    """Streaming dialect-neutral structural signature."""
    token_count = 0
    keyword_counts = {}
    strings = functions = returns = 0
    keywords = {"function","return","if","then","elseif","else","end","for","while","repeat","until","local"}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\\d+(?:\\.\\d+)?|==|~=|<=|>=|\\.\\.\\.|\\S", line)
                token_count += len(tokens)
                for k in keywords:
                    n = tokens.count(k)
                    if n:
                        keyword_counts[k] = keyword_counts.get(k, 0) + n
                strings += len(re.findall(r"""(?:"(?:\\\\.|[^"\\\\])*"|'(?:\\\\.|[^'\\\\])*')""", line))
                functions += line.count("function")
                returns += line.count("return")
    except OSError as exc:
        raise exc
    return {
        "token_count": token_count,
        "keyword_counts": {k: keyword_counts[k] for k in sorted(keyword_counts)},
        "string_literals": strings,
        "function_markers": functions,
        "return_markers": returns,
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
