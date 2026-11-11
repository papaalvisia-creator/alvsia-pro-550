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
                parts = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|~=|<=|>=|\.\.\.|[{}(),;:.+*/%^#=<>~\-\[\]]", scan)
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
        tail = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|~=|<=|>=|\.\.\.|[{}(),;:.+*/%^#=<>~\-\[\]]", carry)
        tokens += len(tail)
        kw += sum(t in keywords for t in tail)
        control += sum(t in {"if","for","while","repeat","function","do"} for t in tail)
        for tok in tail:
            if tok in balance:
                balance[tok] += 1
            elif tok in pairs:
                if balance[pairs[tok]] <= 0:
                    mismatches += 1
                else:
                    balance[pairs[tok]] -= 1
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
    """Streaming, dialect-neutral structural signature.

    Names are retained only as normalized lexical categories so harmless
    decompiler renaming does not break equivalence. Control-flow shape,
    operators, literals, calls and function/return structure remain visible.
    """
    token_count = 0
    keyword_counts = {}
    strings = functions = returns = assignments = calls = branches = loops = 0
    operators = {}
    identifiers = numbers = 0
    keywords = {
        "function","return","if","then","elseif","else","end","for","while",
        "repeat","until","local","do","break","goto",
    }
    control = {"if","elseif","else","for","while","repeat","until"}
    loop = {"for","while","repeat"}
    operator_set = {
        "+","-","*","/","%","^","#","==","~=","<=",">=","<",">","=",
        "..","and","or","not",
    }
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # Strip comments only for the structural token stream; strings
                # remain tokens so string-bearing candidates are distinguishable.
                tokens = re.findall(
                    r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|~=|<=|>=|\.\.\.|"
                    r"[{}(),;:.+*/%^#=<>~\-\[\]]", line
                )
                token_count += len(tokens)
                for token in tokens:
                    if token in keywords:
                        keyword_counts[token] = keyword_counts.get(token, 0) + 1
                    elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
                        identifiers += 1
                    elif re.fullmatch(r"\d+(?:\.\d+)?", token):
                        numbers += 1
                    if token in operator_set:
                        operators[token] = operators.get(token, 0) + 1
                functions += tokens.count("function")
                returns += tokens.count("return")
                assignments += tokens.count("=")
                branches += sum(tokens.count(k) for k in control)
                loops += sum(tokens.count(k) for k in loop)
                # A conservative call marker: identifier immediately followed
                # by an opening parenthesis, excluding declarations/control.
                for i in range(len(tokens) - 1):
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tokens[i]) and tokens[i + 1] == "(":
                        if tokens[i] not in {"if","for","while","function"}:
                            calls += 1
                strings += len(re.findall(
                    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""",
                    line,
                ))
    except OSError as exc:
        raise exc
    return {
        "token_count": token_count,
        "keyword_counts": {k: keyword_counts[k] for k in sorted(keyword_counts)},
        "operator_counts": {k: operators[k] for k in sorted(operators)},
        "string_literals": strings,
        "numeric_literals": numbers,
        "identifier_count": identifiers,
        "function_markers": functions,
        "return_markers": returns,
        "assignment_markers": assignments,
        "call_markers": calls,
        "branch_markers": branches,
        "loop_markers": loops,
    }

def differential_validate(original: Path, reconstructed: Path) -> OracleResult:
    """Compare two source candidates without executing either."""
    try:
        a, b = semantic_signature(original), semantic_signature(reconstructed)
    except OSError as exc:
        return OracleResult(False, "differential", 0.0, {"error": str(exc)})
    exact_keys = (
        "function_markers", "return_markers", "assignment_markers",
        "call_markers", "branch_markers", "loop_markers",
        "string_literals", "numeric_literals",
    )
    matches = sum(a[k] == b[k] for k in exact_keys) / len(exact_keys)
    identifier_ratio = min(a["identifier_count"], b["identifier_count"]) / max(
        1, max(a["identifier_count"], b["identifier_count"])
    )
    token_ratio = min(a["token_count"], b["token_count"]) / max(
        1, max(a["token_count"], b["token_count"])
    )
    operator_a = a["operator_counts"]
    operator_b = b["operator_counts"]
    operator_keys = set(operator_a) | set(operator_b)
    if operator_keys:
        operator_matches = sum(operator_a.get(k, 0) == operator_b.get(k, 0) for k in operator_keys) / len(operator_keys)
    else:
        operator_matches = 1.0
    score = (
        0.45 * matches
        + 0.20 * operator_matches
        + 0.15 * identifier_ratio
        + 0.20 * token_ratio
    )
    return OracleResult(score >= 0.75, "differential", score, {
        "original": a, "reconstructed": b,
        "exact_match_ratio": matches,
        "operator_match_ratio": operator_matches,
        "identifier_ratio": identifier_ratio,
        "token_ratio": token_ratio,
    })


def result_dict(result: OracleResult) -> dict:
    return asdict(result)
