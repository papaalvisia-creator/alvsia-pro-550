#!/usr/bin/env python3
"""Regression tests: SM4 key material must never be embedded in the source tree.

These tests enforce the security remediation that moved every SM4 secret out of
``alvsia_ultimate.py`` / ``alvsia_core.py`` and into the single authorized
provider ``sm4_material``. They also prove the provider fails closed when no
material is supplied and works when it is.
"""
import ast
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY_ROOT = ROOT / "app/src/main/python"
sys.path.insert(0, str(PY_ROOT))

FORBIDDEN_LITERALS = {
    "09ea7a1d9e6528b72b48",
    "eb691efea914241317a8",
    ">gahRZFL4r2*TByfx6#X",
    "Q0hVTKey$as*1ZFlQCiA",
    "xG2qW5lP7lV2iN5fN5pG",
    "xT1cJ6dL5wC0kK1rB4dK",
    "qC4jS5bZ6fL5xE6nD4zA",
    "gD4jQ2aL3bS3lC3xT0iW",
    "xU1yQ8wE9zY3gZ3bT5aE",
    "uQ3cO2dX7xY4xU7gH7iS",
    "gW1fR0jK6wQ4oN0oK1kZ",
    "aJ4pV7iZ7pU4wP2aC2cZ",
    "cX6jT3cM2oT3vK0kJ1qN",
    "iT2vS0cS6yT6cZ1sE1lO",
    "hM1pH9iY8wM9hT4lN5uJ",
    "kG6bC8jK0fL0dE4sH4mL",
    "dB6lB3vE0eZ8wM8rI0aC",
    "tP7sP7nI9rA2vQ4cV5yQ",
    "aT0cL1yN4pT3sZ7eM2vY",
    "uV6fU8fC9zN3mP5dH8mN",
    "rT6aQ6oZ1yM0gO5tO1aN",
    "jU5bH7lQ0fM9hK2kI0oF",
    "iQ0eM0mJ7uT0kV6kL5zY",
    "fO3kW1fE6eD0pU1kY7xK",
    "rG0lR2rZ5vM6mW5lM1rR",
    "wD2rP3lP9xF4mE1eC5jS",
}


def test_no_embedded_sm4_literals_in_any_python_module():
    offenders = []
    for py_file in PY_ROOT.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for literal in FORBIDDEN_LITERALS:
            if literal in text:
                offenders.append(f"{py_file.relative_to(ROOT)} -> {literal[:6]}…")
                break
    assert not offenders, "embedded SM4 material remains: " + "; ".join(offenders)


def test_no_hardcoded_sm4_secret_assignments_ast():
    """AST check: SM4_SECRET_* must not be assigned a string literal."""
    offenders = []
    for py_file in PY_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not any(n.startswith("SM4_SECRET") for n in names):
                continue
            if any(n.endswith(("_VERSION", "_COUNT", "_SET", "_EXPECTED_COUNT")) for n in names):
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 16:
                offenders.append(f"{py_file.name}:{node.lineno} {names[0]}")
            if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                for elt in value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and len(elt.value) >= 16:
                        offenders.append(f"{py_file.name}:{node.lineno} {names[0]}[...]")
                        break
    assert not offenders, "hardcoded SM4 secret assignments: " + "; ".join(offenders)


def test_provider_fails_closed_without_material(monkeypatch):
    import sm4_material
    monkeypatch.delenv(sm4_material.ENV_INLINE, raising=False)
    monkeypatch.delenv(sm4_material.ENV_FILE, raising=False)
    sm4_material.clear_material()
    assert sm4_material.is_available() is False
    with pytest.raises(sm4_material.Sm4MaterialUnavailable):
        sm4_material.require_secret_2()
    with pytest.raises(sm4_material.Sm4MaterialUnavailable):
        sm4_material.require_secret_4()
    with pytest.raises(sm4_material.Sm4MaterialUnavailable):
        sm4_material.require_candidates()


def test_provider_accepts_authorized_material():
    import sm4_material
    try:
        sm4_material.install_material(
            secret_2="synthetic-secret-two-0001",
            secret_4="synthetic-secret-four-0002",
            candidates=["synthetic-candidate-0003"],
            source="test",
        )
        assert sm4_material.require_secret_2() == "synthetic-secret-two-0001"
        assert sm4_material.require_secret_4() == "synthetic-secret-four-0002"
        assert list(sm4_material.require_candidates()) == ["synthetic-candidate-0003"]
        assert sm4_material.is_available() is True
    finally:
        sm4_material.clear_material()


def test_provider_loads_from_environment(monkeypatch):
    import sm4_material
    sm4_material.clear_material()
    monkeypatch.setenv(
        sm4_material.ENV_INLINE,
        '{"secret_2": "env-secret-two-0001", "candidates": ["env-candidate-0002"]}',
    )
    try:
        assert sm4_material.require_secret_2() == "env-secret-two-0001"
        assert list(sm4_material.require_candidates()) == ["env-candidate-0002"]
    finally:
        sm4_material.clear_material()
        monkeypatch.delenv(sm4_material.ENV_INLINE, raising=False)


def test_core_derive_sm4_key_fails_closed_then_works():
    import alvsia_core as core
    import sm4_material
    from pathlib import PurePath

    sm4_material.clear_material()
    core.PakCrypto._derive_sm4_key.cache_clear()
    with pytest.raises(sm4_material.Sm4MaterialUnavailable):
        core.PakCrypto._derive_sm4_key(PurePath("sample"), core.EM_SM4_2)

    try:
        core.set_authorized_sm4_candidates(["synthetic-candidate-0003"])
        sm4_material.install_material(secret_2="synthetic-secret-two-0001")
        key = core.PakCrypto._derive_sm4_key(PurePath("sample"), core.EM_SM4_2)
        assert isinstance(key, bytes) and len(key) == 16
    finally:
        core.clear_authorized_sm4_candidates()
        sm4_material.clear_material()


def test_security_release_check_scans_all_modules():
    source = (ROOT / "tools/security_release_check.py").read_text(encoding="utf-8")
    assert "FORBIDDEN_SM4_LITERALS" in source
    assert "PY.rglob(\"*.py\")" in source
    assert "sm4_material.py" in source
