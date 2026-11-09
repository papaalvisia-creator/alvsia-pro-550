"""Unified protector compatibility registry.

This is routing metadata for detection/static analysis. It does not embed
closed-source commercial protectors or copy their implementation.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ProtectorFamily:
    name: str
    dialects: tuple[str, ...]
    detection_signals: tuple[str, ...]
    handling: str

PROTECTOR_FAMILIES = (
    ProtectorFamily("luraph", ("lua","luajit","luau"), ("vm","loader","encrypted_constants"), "fingerprint_and_static_analysis"),
    ProtectorFamily("moonsec", ("lua","luau"), ("vm","dispatcher","encoded_constants"), "fingerprint_and_static_analysis"),
    ProtectorFamily("prometheus", ("lua",), ("control_flow_flattening","opaque_predicates"), "fingerprint_and_static_analysis"),
    ProtectorFamily("ironbrew2", ("luau",), ("vm","dispatcher"), "fingerprint_and_static_analysis"),
    ProtectorFamily("hercules", ("lua","luau"), ("vm","control_flow"), "fingerprint_and_static_analysis"),
    ProtectorFamily("moonveil", ("luau",), ("vm","control_flow"), "fingerprint_and_static_analysis"),
    ProtectorFamily("ironveil", ("luau",), ("vm",), "fingerprint_and_static_analysis"),
    ProtectorFamily("lua_obfuscator", ("lua","luau"), ("renamer","encoded_constants"), "fingerprint_and_static_analysis"),
)

def compatibility(dialect: str) -> list[str]:
    d = dialect.lower()
    return [x.name for x in PROTECTOR_FAMILIES if d in x.dialects]
