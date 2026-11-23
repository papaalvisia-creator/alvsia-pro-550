#!/usr/bin/env python3
"""Bounded-memory regression tests for the authoritative SM4 candidate scanner."""
import ast
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "app/src/main/python"

registry_spec = importlib.util.spec_from_file_location(
    "sm4_secret_registry", PYTHON_ROOT / "sm4_secret_registry.py"
)
registry = importlib.util.module_from_spec(registry_spec)
registry_spec.loader.exec_module(registry)
sys.modules["sm4_secret_registry"] = registry

source = (PYTHON_ROOT / "alvsia_features.py").read_text(encoding="utf-8")
tree = ast.parse(source, filename="alvsia_features.py")
classes = [
    node for node in tree.body
    if isinstance(node, ast.ClassDef) and node.name in {"SM4KeyFinder", "SM4AllKeyFinder"}
]
assert {node.name for node in classes} == {"SM4KeyFinder", "SM4AllKeyFinder"}
namespace = {"Path": Path, "_re": re}
exec(compile(ast.Module(body=classes, type_ignores=[]), "sm4_scanner.py", "exec"), namespace)
SM4KeyFinder = namespace["SM4KeyFinder"]
SM4AllKeyFinder = namespace["SM4AllKeyFinder"]

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    sample = root / "libfixture.so"
    key = registry.SM4_SECRET_NEW[0]
    offset = SM4KeyFinder._CHUNK_SIZE - 5
    with sample.open("wb") as handle:
        handle.write(b"\x00" * offset)
        handle.write(key.encode("ascii"))
        handle.write(b"\\x00" * 128)

    single = SM4KeyFinder.scan_file(sample)
    assert (offset, key) in single, single

    grouped = SM4AllKeyFinder(str(root)).find_all_keys()
    assert (offset, key) in grouped["SM4_SECRET_NEW"], grouped

assert registry.validate_sm4_secret_set()["ok"]
print("SM4 STREAMING: PASS (23-key registry, cross-chunk UTF-8 detection, all-type scan)")
