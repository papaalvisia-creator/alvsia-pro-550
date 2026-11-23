"""Source-fusion contract for ALVSIA SMART PREMIUM 6.0.0.

The three audited source families are treated as implementation references,
not as UI catalogs. Runtime code remains behind the existing authenticated
bridge and SmartModuleRouter.

This module is deliberately dependency-light so CI can verify the contract
without importing Android/Chaquopy classes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceFamily:
    name: str
    role: str
    capabilities: tuple[str, ...]


SOURCES = (
    SourceFamily(
        "IkramTool_V130_4.7.zip",
        "deep engine reference",
        (
            "lua recovery",
            "multi-xor",
            "BGMI/T24 conversion",
            "Tencent PAK",
            "SM4 custom",
            "UE/asset analysis",
            "Lua protection",
        ),
    ),
    SourceFamily(
        "TOOL.zip",
        "combined pipeline reference",
        (
            "unpack",
            "decompile",
            "batch-decompile",
            "protection",
            "Lua-to-PAK injection",
            "rebuild",
            "crypto/compression",
        ),
    ),
    SourceFamily(
        "RegulerResault_ALVSIA_tool_no_on_vip_engine.zip",
        "regression corpus reference",
        (
            "successful Lua outputs",
            "known decompile failures",
            "prototype/code-count regressions",
            "output validation evidence",
        ),
    ),
)


# Concrete backend contracts already present in the correct Smart Premium tree.
REQUIRED_BACKENDS = {
    "lua": (
        ("lua_engine", "transform_bgmi_lua"),
        ("alvsia_features", "run_lua_smart"),
        ("module_adapters", "dispatch"),
    ),
    "pak_obb": (
        ("archive_engine", "extract_archive"),
        ("archive_engine", "repack_pak"),
    ),
    "data": (
        ("smart_data_engine", "execute"),
        ("module_adapters", "dispatch"),
    ),
}


def source_inventory() -> dict:
    return {
        "sources": [s.name for s in SOURCES],
        "roles": {s.name: s.role for s in SOURCES},
        "capabilities": {s.name: list(s.capabilities) for s in SOURCES},
        "regression_corpus_is_runtime_data": False,
        "login_bypass_source_import": False,
    }
