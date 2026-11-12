#!/usr/bin/env python3
"""Seal protected ALVISIA Python modules for release packaging; restore source after build."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

AESGCM = None

def _aesgcm_class():
    # Restoring source after a failed CI step must not require the optional
    # sealing dependency. Import AES-GCM only for the --seal path.
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
        return _AESGCM
    except ImportError as exc:
        raise SystemExit("Missing dependency: install cryptography before sealing.") from exc

ROOT = Path(__file__).resolve().parents[1]
PY_ROOT = ROOT / "app/src/main/python"
OUT = PY_ROOT / "sealed"
BACKUP = Path(os.environ.get("ALVSIA_PY_BACKUP_DIR", str(Path(tempfile.gettempdir()) / "alvsia-python-source-backup")))
BUILD_ID = "ALVISIA-20261010-MAIN-SEAL1"
CERT_HEX = "99b33815c88a17abbcfe22be15250363f6dfc79c11ffc980e71b62b74b1f295c"
# Generated per build by CI/CodeMagic; this is obfuscation material, not a server secret.
SEED_ENV = "ALVSIA_SEAL_SEED_HEX"
MAGIC = b"ALVSEAL2"
MODULES = (
    "alvsia_bridge_impl.py",
    "alvsia_metadata.py",
    "alvsia_private.py",
    "alvsia_vm_protect.py",
    "lua_engine/pattern_registry.py",
    "alvsia_core.py",
    "alvsia_ultimate.py",
    "alvsia_ultimate_compat.py",
    "alvsia_features.py",
    "sm4_secret_registry.py",
    "pinned_http.py",
    "lua_output_validator.py",
    "lua_engine/lua_decompiler_final.py",
    "lua_engine/lua_protector.py",
    "lua_string_recover.py",
    "lua_engine/engine.py",
    "lua_engine/decompiler53.py",
    "lua_engine/bgmi.py",
    "lua_engine/t24.py",
    "lua_engine/luajit_decompiler.py",
    "lua_engine/container.py",
    "lua_engine/detector.py",
    "lua_engine/multi_format.py",
    "lua_engine/streaming_decompiler.py",
    "lua_engine/orchestrator.py",
    "lua_engine/protection.py",
    "lua_engine/protection_pipeline.py",
    "lua_engine/vm_deobfuscator.py",
)

def _seed() -> bytes:
    value = os.environ.get(SEED_ENV, "").strip()
    if len(value) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise SystemExit(f"{SEED_ENV} must be a per-build 64-character hexadecimal value.")
    return bytes.fromhex(value)

def _key() -> bytes:
    return hashlib.sha256(_seed() + bytes.fromhex(CERT_HEX) + BUILD_ID.encode()).digest()

def seal_payload(source: bytes, seed: bytes, cert_digest: bytes, build_id: str) -> bytes:
    """Create the exact ALVSEAL2 envelope consumed by NativeGuard.decryptSealedPayload."""
    if len(seed) != 32 or len(cert_digest) != 32 or not build_id or len(build_id) > 128:
        raise ValueError("invalid seal key material")
    key = hashlib.sha256(seed + cert_digest + build_id.encode("utf-8")).digest()
    nonce = os.urandom(12)
    encrypted = _aesgcm_class()(key).encrypt(nonce, source, MAGIC)
    return MAGIC + nonce + encrypted

def restore() -> None:
    manifest = BACKUP / "manifest.json"
    if not manifest.is_file():
        if BACKUP.exists():
            shutil.rmtree(BACKUP, ignore_errors=True)
        print("No protected Python backup to restore.")
        return
    for rel in json.loads(manifest.read_text(encoding="utf-8")):
        saved = BACKUP / rel
        target = PY_ROOT / rel
        if saved.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(saved), str(target))
    if OUT.exists():
        for item in OUT.glob("*.alv"):
            item.unlink()
        try:
            OUT.rmdir()
        except OSError:
            pass
    shutil.rmtree(BACKUP, ignore_errors=True)
    print("Protected Python source restored; generated sealed blobs removed.")

def seal() -> None:
    if BACKUP.exists():
        raise SystemExit(f"Backup already exists at {BACKUP}; restore it before sealing again.")
    sources = [PY_ROOT / rel for rel in MODULES]
    missing = [str(p.relative_to(ROOT)) for p in sources if not p.is_file()]
    if missing:
        raise SystemExit("Missing protected Python source(s): " + ", ".join(missing))
    # Validate the per-build secret before creating backups or touching source files.
    seed = _seed()
    cert_digest = bytes.fromhex(CERT_HEX)
    for cache in PY_ROOT.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    BACKUP.mkdir(parents=True)
    (BACKUP / "manifest.json").write_text(json.dumps(list(MODULES)), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    # pkgutil.get_data("sealed", ...) needs a real importable package on all
    # supported Chaquopy/Python versions; a bare namespace directory is not enough.
    (OUT / "__init__.py").write_text("\"\"\"Authenticated ALVSEAL2 payload resources.\"\"\"\n", encoding="utf-8")
    for stale_blob in OUT.glob("*.alv"):
        stale_blob.unlink()
    try:
        for rel, source in zip(MODULES, sources):
            name = rel.replace("/", "_")[:-3] + ".alv"
            (OUT / name).write_bytes(seal_payload(source.read_bytes(), seed, cert_digest, BUILD_ID))
        for rel, source in zip(MODULES, sources):
            saved = BACKUP / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(saved))
        print(f"Sealed {len(MODULES)} protected Python modules; plaintext sources moved outside Chaquopy source tree.")
    except Exception:
        restore()
        raise

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"--seal", "--restore"}:
        print("usage: seal_python.py --seal|--restore", file=sys.stderr)
        return 2
    if sys.argv[1] == "--seal":
        seal()
    else:
        restore()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
