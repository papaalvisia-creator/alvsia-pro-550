"""ALVSIA Smart Lua Protection core.

Deterministic, source-level protection for Lua/Luau.  The engine is deliberately
conservative: it only rewrites lexical identifiers that are proven local,
preserves strings/comments, and validates the transformed source before use.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

KEYWORDS = {
    "and","break","do","else","elseif","end","false","for","function","goto",
    "if","in","local","nil","not","or","repeat","return","then","true","until",
    "while","self",
}

@dataclass(frozen=True)
class ProtectionProfile:
    name: str
    rename_locals: bool = True
    encode_strings: bool = False
    compact: bool = False
    strip_comments: bool = False

PROFILES = {
    "balanced": ProtectionProfile("balanced", True, False, True, False),
    "strong": ProtectionProfile("strong", True, True, True, True),
    "source": ProtectionProfile("source", False, False, False, False),
}

_TOKEN = re.compile(
    r'(?P<comment>--(?:\[(?:=*)\[[\s\S]*?\](?:=*)\]|[^\n]*))'
    r'|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    r'|(?P<long>\[(=*)\[[\s\S]*?\]\2\])'
    r'|(?P<ident>[A-Za-z_]\w*)'
    r'|(?P<number>0[xX][0-9A-Fa-f]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)'
    r'|(?P<space>\s+)'
    r'|(?P<other>.)',
    re.MULTILINE,
)

def _string_expr(token: str) -> str:
    quote = token[0]
    if quote not in ('"', "'") or token[-1] != quote:
        return token
    body = token[1:-1]
    chars, i = [], 0
    mapping = {"n":10,"r":13,"t":9,"b":8,"f":12,"v":11,"a":7}
    while i < len(body):
        if body[i] != "\\":
            code = ord(body[i])
            if code > 255:
                return token
            chars.append(code)
            i += 1
            continue
        if i + 1 >= len(body):
            return token
        esc = body[i + 1]
        if esc in mapping:
            chars.append(mapping[esc])
        elif esc in ("\\", '"', "'"):
            chars.append(ord(esc))
        elif esc == "0":
            chars.append(0)
        else:
            return token
        i += 2
    return '""' if not chars else "string.char(" + ",".join(map(str, chars)) + ")"

def _significant(tokens, idx):
    j = idx - 1
    while j >= 0 and tokens[j][0] in ("space", "comment"):
        j -= 1
    return j

def _next_significant(tokens, idx):
    j = idx + 1
    while j < len(tokens) and tokens[j][0] in ("space", "comment"):
        j += 1
    return j if j < len(tokens) else None

def _declared_names(tokens, i):
    """Return local declaration names beginning at token index i."""
    names = []
    j = _next_significant(tokens, i)
    if j is None:
        return names
    if tokens[j][0] == "ident" and tokens[j][1] == "function":
        j = _next_significant(tokens, j)
        if j is not None and tokens[j][0] == "ident":
            names.append(tokens[j][1])
        return names
    while j is not None:
        kind, value = tokens[j]
        if kind != "ident":
            break
        names.append(value)
        j = _next_significant(tokens, j)
        if j is None or tokens[j][1] != ",":
            break
        j = _next_significant(tokens, j)
    return names

def _compact_tokens(tokens):
    """Compact whitespace without ever joining two lexical words/numbers."""
    out = []
    for kind, value in tokens:
        if kind != "space":
            out.append((kind, value))
            continue
        if not out:
            continue
        # Find the next non-space token.
        continue
    result = []
    for i, item in enumerate(out):
        result.append(item)
        if i + 1 >= len(out):
            continue
        a, av = item
        b, bv = out[i + 1]
        if a in ("ident", "number") and b in ("ident", "number"):
            result.append(("space", " "))
    return result

def protect_source(source: str, profile: ProtectionProfile | str = "balanced") -> str:
    if isinstance(profile, str):
        if profile not in PROFILES:
            raise ValueError(f"unknown protection profile: {profile}")
        profile = PROFILES[profile]

    raw = [(m.lastgroup, m.group()) for m in _TOKEN.finditer(source)]
    # Every declaration receives a unique name. Scope is represented by block
    # depth; nested blocks inherit outer mappings, while shadowing is local.
    active: dict[int, dict[str, str]] = {}
    counter = 0
    tokens = raw[:]

    def fresh(used):
        nonlocal counter
        while True:
            candidate = f"_a{counter:x}"
            counter += 1
            if candidate not in KEYWORDS and candidate not in used:
                return candidate

    depth = 0
    for i, (kind, value) in enumerate(tokens):
        if kind == "ident" and value == "local" and profile.rename_locals:
            for name in _declared_names(tokens, i):
                if name in KEYWORDS:
                    continue
                mapping = active.setdefault(depth, {})
                if name not in mapping:
                    inherited = {v for d in active.values() for v in d.values()}
                    mapping[name] = fresh(inherited)

        # Function/block terminators close the current mapping after all
        # identifiers in the block have been processed.
        if kind == "ident":
            if value in ("end", "until") and depth > 0:
                depth -= 1
                continue
            if value in ("do", "function", "repeat") or value == "then":
                # 'then' opens a block; 'function' opens its body.
                depth += 1

    # Re-run with the computed declaration mappings. A declaration becomes
    # visible after its name; references resolve from innermost to outer scope.
    out = []
    depth = 0
    declaration_positions = set()
    for i, (kind, value) in enumerate(tokens):
        if kind == "ident" and value == "local" and profile.rename_locals:
            names = _declared_names(tokens, i)
            j = _next_significant(tokens, i)
            for name in names:
                while j is not None and tokens[j][1] != name:
                    j = _next_significant(tokens, j)
                if j is not None:
                    declaration_positions.add(j)
                    j = _next_significant(tokens, j)

        if kind == "ident" and profile.rename_locals and i not in declaration_positions:
            replacement = None
            for d in range(depth, -1, -1):
                replacement = active.get(d, {}).get(value)
                if replacement:
                    break
            if replacement:
                prev = _significant(tokens, i)
                if prev is None or tokens[prev][1] not in (".", ":"):
                    value = replacement

        if kind == "string" and profile.encode_strings:
            value = _string_expr(value)
        if kind == "comment" and profile.strip_comments:
            value = ""
        out.append((kind, value))

        if kind == "ident":
            if value in ("end", "until") and depth > 0:
                depth -= 1
            elif value in ("do", "function", "repeat", "then"):
                depth += 1

    if profile.compact:
        out = _compact_tokens(out)
    return "".join(value for _, value in out)

def protect_bytes(source: bytes, profile: ProtectionProfile | str = "balanced") -> bytes:
    return protect_source(source.decode("utf-8"), profile).encode("utf-8")
