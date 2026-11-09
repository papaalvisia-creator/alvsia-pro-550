"""ALVISIA LUA Engine v5.5.

Standalone, dependency-light analysis/decompile helpers used by the Android bridge.
The engine never reports success merely because an output file was created.
"""
from .detector import detect_lua
from .container import unwrap_lua_container, ContainerInfo
from .engine import analyze_lua, decompile_lua, validate_lua_source
from .bgmi import transform_bgmi_lua
from .orchestrator import build_engine_registry, run_decompiler_pipeline
from .protection import ProtectionProfile, PROFILES, protect_source, protect_bytes
from .protection_pipeline import protect_file

__all__ = [
    "detect_lua", "analyze_lua", "decompile_lua",
    "unwrap_lua_container", "ContainerInfo",
    "validate_lua_source", "transform_bgmi_lua",
    "build_engine_registry", "run_decompiler_pipeline",
    "ProtectionProfile", "PROFILES", "protect_source", "protect_bytes", "protect_file",
]
