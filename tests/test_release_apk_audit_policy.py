#!/usr/bin/env python3
"""Regression tests for baseline-vs-final Xop APK audit policy."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_release_apk", ROOT / "tools/audit_release_apk.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def run_audit(config_bytes, required):
    checks = []
    report = []
    MODULE._audit_xop_config(
        config_bytes,
        required,
        lambda ok, message: checks.append((bool(ok), message)),
        report,
    )
    return checks, report


def test_baseline_missing_config_is_deferred_not_failed():
    checks, report = run_audit(None, required=False)
    assert checks == []
    assert any("deferred to final XOP packaging" in item for item in report)


def test_final_missing_config_fails_closed():
    checks, report = run_audit(None, required=True)
    assert checks == [(False, "Xop protector config packaged")]
    assert report == []


def test_valid_final_config_passes_required_controls():
    config = {
        "protect_so": True,
        "detect_proxy": True,
        "net_guard": True,
        "so_decrypt_mode": "lazy",
        "rasp_action": 2,
        "dex_hmac": "a" * 64,
        "code_hmac": "b" * 64,
        "code_methods_hmac": "c" * 64,
        "app_sign_sha256": "d" * 64,
        "encrypt_assets": True,
    }
    import json
    checks, report = run_audit(json.dumps(config).encode(), required=True)
    assert checks and all(ok for ok, _ in checks)
    assert any("legacy field" in item for item in report)


def test_malformed_final_config_fails_closed():
    checks, _ = run_audit(b"{not-json", required=True)
    assert checks and checks[0] == (False, "Xop protector config is valid JSON")


if __name__ == "__main__":
    test_baseline_missing_config_is_deferred_not_failed()
    test_final_missing_config_fails_closed()
    test_valid_final_config_passes_required_controls()
    test_malformed_final_config_fails_closed()
    print("RELEASE APK AUDIT POLICY: PASS")
