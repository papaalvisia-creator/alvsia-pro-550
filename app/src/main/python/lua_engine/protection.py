"""ALVSIA Smart Lua Protection core.

Source-level, deterministic protection layers for Lua/Luau. Profiles compose
into one engine and never depend on closed/proprietary protector code.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

KEYWORDS = {"and","break","do","else","elseif","end","false","for","function","goto","if","in","local","nil","not","or","repeat","return","then","true","until","while","self"}

@dataclass(frozen=True)
class ProtectionProfile:
    name: str
    rename_locals: bool = True
    encode_strings: bool = False
    compact: bool = False

PROFILES = {
    "balanced": ProtectionProfile("balanced", True, False, True),
    "strong": ProtectionProfile("strong", True, True, True),
    "source": ProtectionProfile("source", False, False, False),
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
    body = token[1:-1]
    chars, i = [], 0
    mapping = {"n":10,"r":13,"t":9,"b":8,"f":12,"v":11,"a":7}
    while i < len(body):
        if body[i] != "\\":
            chars.append(ord(body[i])); i += 1; continue
        if i + 1 >= len(body):
            return token
        esc = body[i + 1]
        if esc in mapping: chars.append(mapping[esc])
        elif esc in ("\\", '"', "'"): chars.append(ord(esc))
        else: return token
        i += 2
    return '""' if not chars else "string.char(" + ",".join(map(str, chars)) + ")"

def protect_source(source: str, profile: ProtectionProfile | str = "balanced") -> str:
    if isinstance(profile, str):
        if profile not in PROFILES: raise ValueError(f"unknown protection profile: {profile}")
        profile = PROFILES[profile]
    mapping, used, counter, out = {}, set(KEYWORDS), 0, []
    for m in _TOKEN.finditer(source):
        kind, value = m.lastgroup, m.group()
        if kind == "ident" and profile.rename_locals and value not in KEYWORDS:
            prev = "".join(out[-4:])
            if re.search(r"\blocal\s+(?:function\s+)?$", prev):
                while f"_a{counter:x}" in used: counter += 1
                mapping[value] = f"_a{counter:x}"; used.add(mapping[value]); counter += 1
            value = mapping.get(value, value)
        elif kind == "string" and profile.encode_strings:
            value = _string_expr(value)
        if profile.compact and kind == "space":
            value = "\n" if "\n" in value and out and not out[-1].endswith(("\n",";")) else ""
        out.append(value)
    return "".join(out)

def protect_bytes(source: bytes, profile: ProtectionProfile | str = "balanced") -> bytes:
    return protect_source(source.decode("utf-8"), profile).encode("utf-8")
