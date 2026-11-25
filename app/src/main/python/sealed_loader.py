# ALVISIA PRO sealed Python bootstrap; payloads are generated during release build.
from __future__ import annotations
import importlib.abc
import importlib.util
import os
import pkgutil
import sys

_MAGIC = b"ALVSEAL2"
_MAP = {
    "alvsia_bridge_impl": "alvsia_bridge_impl.alv",
    "alvsia_metadata": "alvsia_metadata.alv",
    "alvsia_private": "alvsia_private.alv",
    "alvsia_vm_protect": "alvsia_vm_protect.alv",
    "lua_engine.pattern_registry": "lua_engine_pattern_registry.alv",
    "alvsia_core": "alvsia_core.alv",
    "alvsia_ultimate": "alvsia_ultimate.alv",
    "alvsia_ultimate_compat": "alvsia_ultimate_compat.alv",
    "alvsia_features": "alvsia_features.alv",
    "sm4_secret_registry": "sm4_secret_registry.alv",
    "pinned_http": "pinned_http.alv",
    "lua_engine.lua_decompiler_final": "lua_engine_lua_decompiler_final.alv",
    "lua_engine.lua_protector": "lua_engine_lua_protector.alv",
    "lua_output_validator": "lua_output_validator.alv",
    "lua_string_recover": "lua_string_recover.alv",
    "lua_engine.engine": "lua_engine_engine.alv",
    "lua_engine.decompiler53": "lua_engine_decompiler53.alv",
    "lua_engine.bgmi": "lua_engine_bgmi.alv",
    "lua_engine.t24": "lua_engine_t24.alv",
    "lua_engine.luajit_decompiler": "lua_engine_luajit_decompiler.alv",
    "lua_engine.container": "lua_engine_container.alv",
    "lua_engine.detector": "lua_engine_detector.alv",
    "lua_engine.multi_format": "lua_engine_multi_format.alv",
    "lua_engine.streaming_decompiler": "lua_engine_streaming_decompiler.alv",
    "lua_engine.orchestrator": "lua_engine_orchestrator.alv",
    "lua_engine.protection": "lua_engine_protection.alv",
    "lua_engine.protection_pipeline": "lua_engine_protection_pipeline.alv",
    "lua_engine.vm_deobfuscator": "lua_engine_vm_deobfuscator.alv",
    # Batch 2 — previously plain-bytecode modules, now sealed
    "alvsia_reference_tools": "alvsia_reference_tools.alv",
    "archive_engine": "archive_engine.alv",
    "lua_engine": "lua_engine___init__.alv",
    "lua_engine.protector_registry": "lua_engine_protector_registry.alv",
    "lua_intelligence": "lua_intelligence___init__.alv",
    "lua_intelligence.candidates": "lua_intelligence_candidates.alv",
    "lua_intelligence.core": "lua_intelligence_core.alv",
    "lua_intelligence.fingerprint": "lua_intelligence_fingerprint.alv",
    "lua_intelligence.fusion": "lua_intelligence_fusion.alv",
    "lua_intelligence.ir": "lua_intelligence_ir.alv",
    "lua_intelligence.knowledge": "lua_intelligence_knowledge.alv",
    "lua_intelligence.layers": "lua_intelligence_layers.alv",
    "lua_intelligence.model": "lua_intelligence_model.alv",
    "lua_intelligence.oracle": "lua_intelligence_oracle.alv",
    "lua_intelligence.structure": "lua_intelligence_structure.alv",
    "lua_recovery_proof": "lua_recovery_proof.alv",
    "module_adapters": "module_adapters.alv",
    "pending_subtool_adapters": "pending_subtool_adapters.alv",
    "smart_archive_engine": "smart_archive_engine.alv",
    "smart_archive_lua_engine": "smart_archive_lua_engine.alv",
    "smart_data_engine": "smart_data_engine.alv",
    "smart_lua_engine": "smart_lua_engine.alv",
    "smart_pak_lua_engine": "smart_pak_lua_engine.alv",
    "smart_premium_source_fusion": "smart_premium_source_fusion.alv",
}

# A sealed package must be presented to Python as a real package. Without this,
# importlib executes lua_engine.__init__ as a flat module, so relative imports
# fail with "attempted relative import with no known parent package".
_PACKAGES = frozenset(
    name for name in _MAP
    if any(other.startswith(name + ".") for other in _MAP)
)

def _valid_session() -> bool:
    try:
        from com.alvsia.pro.sec import SessionGate
        return bool(SessionGate.isSessionAuthorized())
    except Exception:
        return False

class _SealedLoader(importlib.abc.Loader):
    def __init__(self, fullname: str, blob: str):
        self.fullname = fullname
        self.blob = blob

    def is_package(self, fullname: str) -> bool:
        return fullname in _PACKAGES

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if not _valid_session():
            raise ImportError("sealed runtime authorization missing")
        try:
            from com.alvsia.pro.sec import NativeGuard
            raw = pkgutil.get_data("sealed", self.blob)
            if raw is None:
                raise FileNotFoundError("sealed payload resource missing")
            guard = getattr(NativeGuard, "INSTANCE", None)
            if guard is not None:
                build_id = guard.sealBuildId()
                decrypted = guard.decryptSealedPayload(raw, build_id) if build_id else None
            else:
                build_id = NativeGuard.sealBuildId()
                decrypted = NativeGuard.decryptSealedPayload(raw, build_id) if build_id else None
            if decrypted is None:
                raise ValueError("native sealed payload decryption returned null")
            source = bytes(decrypted)
        except Exception as exc:
            raise ImportError("sealed payload authentication/decryption failed") from exc
        module.__file__ = "<ALVISIA-SEALED:%s>" % self.fullname
        # A package needs its own name as __package__ so .detector resolves
        # correctly to lua_engine.detector.
        if self.fullname in _PACKAGES:
            module.__package__ = self.fullname
        else:
            module.__package__ = self.fullname.rpartition(".")[0]
        code = compile(source, module.__file__, "exec")
        del source
        exec(code, module.__dict__)

class _SealedFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blob = _MAP.get(fullname)
        if blob is None:
            return None
        loader = _SealedLoader(fullname, blob)
        return importlib.util.spec_from_loader(
            fullname, loader, is_package=(fullname in _PACKAGES)
        )

_installed = False

def install() -> None:
    global _installed
    if _installed:
        return
    if os.environ.get("ALVSIA_SEALED_RUNTIME") != "1":
        raise RuntimeError("sealed runtime is not enabled for this build")
    if not _valid_session():
        raise RuntimeError("sealed runtime requires a valid APK session")
    sys.meta_path.insert(0, _SealedFinder())
    _installed = True
