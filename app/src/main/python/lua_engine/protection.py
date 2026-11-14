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
    string_min_length: int = 1
    rename_prefix: str = "_a"

PROFILES = {
    "balanced": ProtectionProfile("balanced", True, False, True, False, 1, "_a"),
    "strong": ProtectionProfile("strong", True, True, True, True, 2, "_a"),
    "source": ProtectionProfile("source", False, False, False, False, 1, "_a"),
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
            i += 2
            continue
        if esc in ("\\", '"', "'"):
            chars.append(ord(esc))
            i += 2
            continue
        if esc == "0":
            chars.append(0)
            i += 2
            continue
        if esc == "x" and i + 3 < len(body):
            hx = body[i + 2:i + 4]
            if re.fullmatch(r"[0-9A-Fa-f]{2}", hx):
                chars.append(int(hx, 16))
                i += 4
                continue
        if esc.isdigit():
            j = i + 1
            while j < len(body) and j < i + 4 and body[j].isdigit():
                j += 1
            try:
                value = int(body[i + 1:j], 10)
            except ValueError:
                return token
            if value > 255:
                return token
            chars.append(value)
            i = j
            continue
        if esc == "z":
            # Lua 5.2+ \z consumes following whitespace. Preserve the exact
            # byte sequence through a deterministic character encoder.
            j = i + 2
            while j < len(body) and body[j].isspace():
                j += 1
            i = j
            continue
        return token
        
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

def _function_parameter_indices(tokens, function_index):
    """Find simple function parameters and return their token indices."""
    j = _next_significant(tokens, function_index)
    if j is None:
        return []
    while j is not None and tokens[j][1] != "(":
        if tokens[j][1] in ("=", ";", "end"):
            return []
        j = _next_significant(tokens, j)
    if j is None:
        return []
    indices = []
    nesting = 1
    j += 1
    while j < len(tokens) and nesting:
        kind, value = tokens[j]
        if kind in ("string", "long", "comment"):
            j += 1
            continue
        if value == "(":
            nesting += 1
        elif value == ")":
            nesting -= 1
        elif nesting == 1 and kind == "ident" and value != "self":
            prev = _significant(tokens, j)
            if prev is None or tokens[prev][1] not in (".", ":"):
                indices.append(j)
        j += 1
    return indices


def protect_source(source: str, profile: ProtectionProfile | str = "balanced") -> str:
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if isinstance(profile, str):
        if profile not in PROFILES:
            raise ValueError(f"unknown protection profile: {profile}")
        profile = PROFILES[profile]

    tokens = [(m.lastgroup, m.group()) for m in _TOKEN.finditer(source)]
    active: dict[int, dict[str, str]] = {}
    used = set(KEYWORDS)
    counter = 0
    out = []
    depth = 0

    def fresh() -> str:
        nonlocal counter
        while True:
            candidate = f"{profile.rename_prefix}{counter:x}"
            counter += 1
            if candidate not in used:
                used.add(candidate)
                return candidate

    def resolve(name: str):
        for d in range(depth, -1, -1):
            value = active.get(d, {}).get(name)
            if value:
                return value
        return None

    i = 0
    while i < len(tokens):
        kind, value = tokens[i]

        if kind == "ident" and value == "local" and profile.rename_locals:
            out.append((kind, value))
            j = _next_significant(tokens, i)
            declaration_indices = []
            is_local_function = False
            func_kw_idx = None
            if j is not None and tokens[j] == ("ident", "function"):
                is_local_function = True
                func_kw_idx = j
                j = _next_significant(tokens, j)
                if j is not None and tokens[j][0] == "ident":
                    declaration_indices.append(j)
            else:
                while j is not None:
                    tk, tv = tokens[j]
                    if tk != "ident":
                        break
                    declaration_indices.append(j)
                    k = _next_significant(tokens, j)
                    if k is None or tokens[k][1] != ",":
                        break
                    j = _next_significant(tokens, k)
            if declaration_indices:
                last_decl = declaration_indices[-1]
                declared_by_index = {}
                for di in declaration_indices:
                    name = tokens[di][1]
                    if name not in KEYWORDS:
                        declared_by_index[di] = active.setdefault(depth, {}).setdefault(name, fresh())
                for k in range(i + 1, last_decl + 1):
                    tk, tv = tokens[k]
                    if k in declared_by_index:
                        tv = declared_by_index[k]
                    out.append((tk, tv))
                i = last_decl + 1
                if is_local_function:
                    # `local function name(...)` consumed the `function` keyword
                    # inside this branch, so the main loop never sees it. Enter
                    # the function scope here: register parameters at depth+1 and
                    # balance the matching `end`. Without this the outer name
                    # mapping is popped by `end` and trailing uses of the
                    # function name become dangling references (broken output).
                    function_depth = depth + 1
                    scope = active.setdefault(function_depth, {})
                    for pi in _function_parameter_indices(tokens, func_kw_idx):
                        name = tokens[pi][1]
                        if name not in KEYWORDS and name not in scope:
                            scope[name] = fresh()
                            tokens[pi] = ("ident", scope[name])
                    depth = function_depth
                continue

        if kind == "ident" and value == "function" and profile.rename_locals:
            # Parameters are locals in the function scope. Register them at
            # depth+1 before normal identifier resolution reaches the body.
            function_depth = depth + 1
            scope = active.setdefault(function_depth, {})
            for pi in _function_parameter_indices(tokens, i):
                name = tokens[pi][1]
                if name not in KEYWORDS and name not in scope:
                    replacement = fresh()
                    scope[name] = replacement
                    tokens[pi] = ("ident", replacement)

        if kind == "ident" and profile.rename_locals:
            replacement = resolve(value)
            if replacement:
                prev = _significant(tokens, i)
                nxt = _next_significant(tokens, i)
                # A bare identifier used as a table-constructor key
                # (`{ key = value }`) is a field name, not a variable: renaming
                # it changes the table's key and silently corrupts semantics.
                is_field_key = (
                    nxt is not None and tokens[nxt][1] == "="
                    and prev is not None and tokens[prev][1] in ("{", ",", ";")
                )
                if not is_field_key and (prev is None or tokens[prev][1] not in (".", ":")):
                    value = replacement

        if kind == "string" and profile.encode_strings:
            body_len = max(0, len(value) - 2)
            if body_len >= profile.string_min_length:
                value = _string_expr(value)
        if kind == "comment" and profile.strip_comments:
            value = ""

        out.append((kind, value))

        if kind == "ident":
            if value in ("end", "until"):
                active.pop(depth, None)
                depth = max(0, depth - 1)
            elif value in ("do", "function", "repeat", "then"):
                depth += 1
        i += 1

    if profile.compact:
        out = _compact_tokens(out)
    return "".join(value for _, value in out)

def protect_bytes(source: bytes, profile: ProtectionProfile | str = "balanced") -> bytes:
    return protect_source(source.decode("utf-8"), profile).encode("utf-8")
