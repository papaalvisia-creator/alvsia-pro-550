"""VANTA red-team regression checks for high-impact static findings.

These checks are intentionally conservative and do not claim runtime security.
They guard against regressions in the reviewed source tree.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "app/src/main/python"
ULTIMATE = (PY / "alvsia_ultimate.py").read_text(encoding="utf-8")
CORE = (PY / "alvsia_core.py").read_text(encoding="utf-8")
BRIDGE = (PY / "alvsia_bridge.py").read_text(encoding="utf-8") + "\n" + (PY / "alvsia_bridge_impl.py").read_text(encoding="utf-8")
GRADLE = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
MANIFEST = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
NATIVE = ROOT / "app/src/main/cpp/rasp_guard.cpp"
CODEMAGIC = (ROOT / "codemagic.yaml").read_text(encoding="utf-8")
PANEL_CLIENT = (ROOT / "app/src/main/java/com/alvsia/pro/panel/PanelClient.kt").read_text(encoding="utf-8")
MAIN_ACTIVITY = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
TOOL_ENGINE = (ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolEngine.kt").read_text(encoding="utf-8")
ASSET_VAULT = (ROOT / "app/src/main/java/com/alvsia/pro/asset/AssetVault.kt").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/android-validation.yml").read_text(encoding="utf-8")



def _load_standalone_python_function(name):
    """Load a small stdlib-only function from source without importing the app."""
    import ast
    source_tree = ast.parse(ULTIMATE)
    function = next(
        node for node in source_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {"Path": Path, "os": __import__("os"), "re": re}
    exec(compile(module, str(PY / "alvsia_ultimate.py"), "exec"), namespace)
    return namespace[name]


def test_captcha_parser_accepts_bounded_arithmetic_and_rejects_code():
    solve = _load_standalone_python_function("_safe_captcha_integer")
    assert solve("7 + 5 * 2") == 17
    assert solve("(20 - 8) // 3") == 4
    for malicious in (
        "__import__('os').system('echo unsafe')",
        "open('/tmp/alvsia-test', 'w')",
        "1 / 0",
        "9 ** 99",
        "1" * 300,
    ):
        try:
            solve(malicious)
        except (ValueError, SyntaxError, ZeroDivisionError):
            pass
        else:
            raise AssertionError(f"Captcha parser accepted invalid input: {malicious!r}")


def test_zip_extractor_rejects_path_traversal():
    import tempfile
    import zipfile
    extract = _load_standalone_python_function("_alvsia_safe_extract_zip")
    with tempfile.TemporaryDirectory(prefix="alvsia-vanta-") as temp:
        tmp_path = Path(temp)
        archive_path = tmp_path / "malicious.zip"
        output = tmp_path / "out"
        outside = tmp_path / "escape.txt"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("../escape.txt", "must-not-write")
        with zipfile.ZipFile(archive_path) as archive:
            try:
                extract(archive, output)
            except ValueError as exc:
                assert "Unsafe ZIP entry path rejected" in str(exc)
            else:
                raise AssertionError("ZIP traversal entry was not rejected")
        assert not outside.exists(), "ZIP traversal wrote outside destination"


def test_no_reported_master_passwords_remain():
    forbidden = ("ALVSIA_2027", "ALVSIA_MASTER_20277")
    source = "\n".join((ULTIMATE, CORE, BRIDGE))
    for secret in forbidden:
        assert secret not in source, f"Hardcoded red-team credential remains: {secret}"


def test_captcha_does_not_use_eval():
    # The constrained arithmetic parser is retained as the only sanctioned
    # expression evaluator; Python eval() must never appear in the engine.
    assert "def _safe_captcha_integer(" in ULTIMATE
    assert not re.search(r"(?<![A-Za-z0-9_])eval\s*\(", ULTIMATE), (
        "Unsafe eval() remains in alvsia_ultimate.py"
    )


def test_no_direct_zip_extractall_calls():
    source = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                        for p in PY.rglob("*.py"))
    assert not re.search(r"\.extractall\s*\(", source), (
        "Direct ZipFile.extractall/ZipFile-like extractall call remains; use validated paths"
    )


def test_release_hardening_is_enabled():
    assert "isMinifyEnabled = true" in GRADLE
    assert "isShrinkResources = true" in GRADLE
    assert "proguard-rules.pro" in GRADLE
    assert "networkSecurityConfig" in MANIFEST
    assert "CERT_SHA256" in GRADLE
    assert NATIVE.is_file(), "Native RASP source is missing"


def test_release_tls_pinning_fails_closed():
    # Release transport uses pinned TLS always — no loose client path.
    assert "clientPinned.newCall(req).execute()" in PANEL_CLIENT
    assert "clientPinned.newCall(req).execute().use" in PANEL_CLIENT
    assert "certificatePinner(Vault.certPinner())" in PANEL_CLIENT
    assert "clientLoose.newBuilder" in PANEL_CLIENT
    assert "_pinGrace" not in PANEL_CLIENT


def test_release_seals_asset_jars_and_disables_plaintext_fallback():
    assert "AssetVault.materializeJars(context, jarsDir)" in TOOL_ENGINE
    assert "dest.writeBytes(bytes)" in ASSET_VAULT
    assert "bytes.fill(0)" in ASSET_VAULT
    assert "tools/seal_assets.py" in CODEMAGIC
    assert "tools/seal_assets.py" in WORKFLOW


def test_login_enforces_rasp_before_local_tool_initialization():
    # The new panel authenticates login/session; it does not publish the legacy CoreBundle API.
    login = MAIN_ACTIVITY.find("val res = withContext(Dispatchers.IO) { panel.login(key, hwid) }")
    catalog = MAIN_ACTIVITY.find("tools = ToolCatalog.defaults()")
    assert login >= 0 and catalog > login, "local tool catalog must initialize only after panel login"
    gate = MAIN_ACTIVITY[login:catalog]
    assert "Guard.checkAndReport(" in gate
    assert "if (!safeAfterLogin)" in gate
    assert "SessionGate.lock(this@MainActivity)" in gate


def test_new_panel_uses_unaux_jwt_grants_without_legacy_corebundle():
    main = MAIN_ACTIVITY
    panel = PANEL_CLIENT
    vault = (ROOT / "app/src/main/java/com/alvsia/pro/panel/Vault.kt").read_text(encoding="utf-8")
    runner = (ROOT / "app/src/main/java/com/alvsia/pro/tool/PythonBridgeRunner.kt").read_text(encoding="utf-8")
    assert "tool_fetch.php" not in main + panel + vault
    assert "fetchCore(" not in main + panel
    # Current Unaux contract: short-lived JWT grants over operation_grant.php.
    assert "requestOperationGrant(" in panel
    assert "operation_grant.php" in vault
    assert "OperationGrants" in runner or "OperationGrantClient" in runner
    assert "SessionGate.unlock(this@MainActivity, tok, license)" in main
    assert "SessionGate.isTokenCurrent(token)" in runner
    assert "ToolCatalog.defaults()" in main



def test_login_uses_new_panel_and_preserves_otp_removal():
    assert "panel.login(key, hwid)" in MAIN_ACTIVITY
    assert "ToolCatalog.defaults()" in MAIN_ACTIVITY
    assert "panel.fetchCore(license, hwid)" not in MAIN_ACTIVITY
    assert "tool_fetch.php" not in MAIN_ACTIVITY + PANEL_CLIENT
    assert not (ROOT / "app/src/main/java/com/alvsia/pro/ui/otp/OtpScreen.kt").exists(), \
        "OtpScreen.kt must be deleted — full OTP removal"
    import subprocess
    grep = subprocess.run(
        ["grep", "-rlni", "otp", str(ROOT / "app")],
        capture_output=True, text=True
    )
    assert grep.returncode != 0, f"OTP references remain in app/:\n{grep.stdout}"
    assert grep.stdout.strip() == "", f"OTP references remain in app/:\n{grep.stdout}"


def test_apk_session_requires_native_gate_authorization():
    assert "def _valid_apk_session():" in BRIDGE
    assert "SessionGate.isSessionAuthorized()" in BRIDGE
    assert "if not _valid_apk_session():" in BRIDGE
    assert "ALVSIA_APK_SESSION" in CORE


def test_core_operation_gate_requires_panel_session_and_device_binding():
    import ast
    import os
    import time
    from unittest.mock import patch

    tree = ast.parse(CORE)
    node = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "_alvsia_require_operation")
    namespace = {"_ALVSIA_CORE_ACTIVE_PROOF": None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(PY / "alvsia_core.py"), "exec"), namespace)
    require = namespace["_alvsia_require_operation"]
    with patch.dict(os.environ, {"ALVSIA_APK_SESSION": "1"}, clear=False):
        os.environ.pop("ALVSIA_EXPECTED_SESSION_ID", None)
        os.environ.pop("ALVSIA_EXPECTED_DEVICE_ID", None)
        try:
            require({"pak.unpack"})
        except RuntimeError as exc:
            assert "authorization failed" in str(exc).lower()
        else:
            raise AssertionError("Core accepted a session marker without identity binding")
        os.environ["ALVSIA_EXPECTED_SESSION_ID"] = "a" * 64
        os.environ["ALVSIA_EXPECTED_DEVICE_ID"] = "b" * 64
        try:
            require({"pak.unpack"})
        except RuntimeError as exc:
            assert "grant missing" in str(exc).lower()
        else:
            raise AssertionError("Core accepted identity binding without an RSA grant")
        namespace["_ALVSIA_CORE_ACTIVE_PROOF"] = {
            "session_id": "a" * 64,
            "device_id": "b" * 64,
            "_expires_epoch": time.time() + 300,
            "operation_id": "pak_tools",
        }
        assert require({"pak.unpack"}) is True


def test_bridge_requires_apk_session_gate():
    assert "if not _valid_apk_session():" in BRIDGE
    assert "ALVSIA_SESSION_TOKEN" in BRIDGE



def test_external_data_downloads_are_commit_pinned_and_integrity_checked():
    # These data downloads are pinned to immutable Git commits and checked against
    # the upstream Git blob ID/size before the downloaded file is accepted.
    assert "/SKIN_TOOL/main/SKIN_TOOL.zip" not in ULTIMATE
    assert "/BGMI_CSV/main/PUBG.csv" not in ULTIMATE
    assert "/BGMI_CSV/main/BGMI.csv" not in ULTIMATE
    assert "5c7ad2b4996fcd468bf245be43580d1fe131423e" in ULTIMATE
    assert "d013eca408f85d073c195e42a363b49076babd1d" in ULTIMATE
    assert "_verify_pinned_git_blob" in ULTIMATE
    assert "cbd3d0e257963b54f34a908b6864040c7f96fbb1" in ULTIMATE
    assert "2601457787bd2d793880fb1a8c485d0e76144942" in ULTIMATE
    assert "ac72bf1d3ca5f0ae72b65c1845c9c471e4a4a6af" in ULTIMATE


def test_codemagic_release_signing_fails_closed_and_pins_certificate():
    sign_block = CODEMAGIC.split("- name: Sign and verify release APK", 1)[1]
    assert 'CM_KEYSTORE_PASSWORD:?' in sign_block
    assert 'apksigner" verify --verbose --print-certs' in sign_block
    assert 'EXPECTED_CERT_SHA256="$(grep -oE' in sign_block
    assert 'ACTUAL_CERT_SHA256' in sign_block
    assert 'test "$ACTUAL_CERT_SHA256" = "$EXPECTED_CERT_SHA256"' in sign_block
    assert '99b33815c88a17abbcfe22be15250363f6dfc79c11ffc980e71b62b74b1f295c' in GRADLE
    assert 'ALVISIA_PRO_5.5.0_unsigned.apk' not in CODEMAGIC
    assert 'groups:\n        - signing' in CODEMAGIC
    assert '- name: Validate release signing configuration' in CODEMAGIC


def test_runtime_gate_rechecks_live_hooks_after_unlock():
    session_gate = (ROOT / "app/src/main/java/com/alvsia/pro/sec/SessionGate.kt").read_text(encoding="utf-8")
    native_guard = (ROOT / "app/src/main/java/com/alvsia/pro/sec/NativeGuard.kt").read_text(encoding="utf-8")
    gate = session_gate[session_gate.find("fun allowTools(ctx: Context)"):]
    live_check = gate.find("if (runtimeHostile(ctx))")
    unlocked_branch = gate.find("if (!NativeGate.sessionUnlocked)")
    assert live_check >= 0, "every tool dispatch must re-check live hook/tracer indicators"
    assert unlocked_branch > live_check, "live guard must run before the unlocked-session shortcut"
    assert "fun isNativeLoaded(): Boolean = nativeLoaded" in native_guard
    assert "native_rasp_unavailable" in session_gate, "release must fail closed if JNI RASP failed to load"
    guard = (ROOT / "app/src/main/java/com/alvsia/pro/sec/Guard.kt").read_text(encoding="utf-8")
    hard = guard.split("private val HARD_RUNTIME_MARKERS", 1)[1].split(")", 1)[0]
    soft = guard.split("private val SOFT_HOOK_MARKERS", 1)[1].split(")", 1)[0]
    # Hard markers block every dispatch; soft hook/root markers degrade only.
    assert "frida" in hard
    assert "magisk" not in hard and "zygisk" not in hard, (
        "root-only markers must not trigger a hard block on every tool call"
    )
    assert "dobby" in soft and "zygisk" in soft


if __name__ == "__main__":
    checks = [
        test_captcha_parser_accepts_bounded_arithmetic_and_rejects_code,
        test_zip_extractor_rejects_path_traversal,
        test_no_reported_master_passwords_remain,
        test_captcha_does_not_use_eval,
        test_no_direct_zip_extractall_calls,
        test_release_hardening_is_enabled,
        test_release_tls_pinning_fails_closed,
        test_release_seals_asset_jars_and_disables_plaintext_fallback,
        test_login_enforces_rasp_before_engine_fetch,
        test_login_fails_closed_when_panel_engine_is_missing,
        test_apk_session_requires_native_token_shape,
        test_core_operation_gate_rejects_marker_only_bypass,
        test_bridge_requires_apk_session_gate,
        test_external_data_downloads_are_commit_pinned_and_integrity_checked,
        test_codemagic_release_signing_fails_closed_and_pins_certificate,
        test_runtime_gate_rechecks_live_hooks_after_unlock,
    ]
    for check in checks:
        check()
        print("PASS", check.__name__)
    print(f"VANTA STATIC REGRESSION: PASS ({len(checks)}/{len(checks)})")
