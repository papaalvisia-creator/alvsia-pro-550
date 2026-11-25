#!/usr/bin/env python3
"""Regression test for sealed Python package semantics.

The sealed loader must expose package __path__/__package__ semantics for
packages such as lua_engine and lua_intelligence. Otherwise their relative
imports fail at runtime after release sealing.
"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/src/main/python/sealed_loader.py").read_text(encoding="utf-8")
tree = ast.parse(SOURCE)

# The package set must be derived from the sealed module map.
assert "_PACKAGES" in SOURCE
assert 'any(other.startswith(name + ".") for other in _MAP)' in SOURCE

# Loader must report package status to importlib and preserve package context.
assert "def is_package(self, fullname: str) -> bool:" in SOURCE
assert "return fullname in _PACKAGES" in SOURCE
assert "is_package=(fullname in _PACKAGES)" in SOURCE
assert "module.__package__ = self.fullname" in SOURCE
assert 'module.__package__ = self.fullname.rpartition(".")[0]' in SOURCE

# Static AST guard: the finder must call spec_from_loader with is_package.
calls = [
    n for n in ast.walk(tree)
    if isinstance(n, ast.Call)
    and isinstance(n.func, ast.Attribute)
    and n.func.attr == "spec_from_loader"
]
assert calls, "sealed loader no longer constructs importlib specs"
assert any(
    any(k.arg == "is_package" for k in call.keywords)
    for call in calls
), "sealed loader spec does not preserve package semantics"

print("SEALED LOADER PACKAGE CONTEXT: PASS")
print("- lua_engine/lua_intelligence can retain relative-import package context")
