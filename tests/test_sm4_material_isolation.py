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

def test_security_scanner_does_not_embed_plaintext_key_values():
    scanner = (ROOT / "tools/security_release_check.py").read_text(encoding="utf-8")
    test_source = Path(__file__).read_text(encoding="utf-8")
    assert "FORBIDDEN_SM4_LITERALS =" not in scanner
    assert "FORBIDDEN_" + "LITERALS =" not in test_source
    assert "SECRET_NAME_PREFIXES" in scanner
    assert "_looks_like_historical_sm4_candidate" in scanner
    assert "value.isalnum()" in scanner
    assert 'ch in "$*"' in scanner
    assert "PY.rglob(\"*.py\")" in scanner


def test_historical_candidate_shape_detector_covers_all_three_legacy_families():
    import importlib.util

    scanner_path = ROOT / "tools/security_release_check.py"
    spec = importlib.util.spec_from_file_location("alvsia_security_release_check", scanner_path)
    scanner = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(scanner)

    # Construct only synthetic shapes at runtime; do not place historical
    # candidate values in this test source or its compiled constants.
    family_new = "".join([
        "a", "B", "1", "c", "D", "2", "e", "F", "3", "g",
        "H", "4", "i", "J", "5", "k", "L", "6", "m", "N",
    ])
    family_four = "".join([
        "a1", "b2", "c3", "d4", "e5", "f6", "g7", "h8", "i9", "j0",
    ])
    family_two = "".join(["ABcD", "$*", "EFgh", "1234567890"])

    assert scanner._looks_like_historical_sm4_candidate(family_new)
    assert scanner._looks_like_historical_sm4_candidate(family_four)
    assert scanner._looks_like_historical_sm4_candidate(family_two)
    assert not scanner._looks_like_historical_sm4_candidate("ordinary-test-value")


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
    assert "FORBIDDEN_SM4_LITERALS" not in source
    assert "PY.rglob(\"*.py\")" in source
    assert "sm4_material.py" in source
