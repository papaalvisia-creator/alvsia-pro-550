"""
ALVISIA PRO 5.5.0 — Master Upgrade regression tests.

These tests verify the master-upgrade deliverables in perbaikan_source.txt:
  §1  18 tool catalog intact (ToolCatalog + SubMenus)
  §2  OTP fully removed from source code
  §3  Startup race fixed (splash withTimeout + bounded init)
  §4  Lua decompiler streaming for large files
  §5  PermissionManager per-tool matrix + zero-confirmation
  §6  TelegramNotifier military HTML format + queue + chunked upload
  §7  Security & compatibility preserved (RASP, TLS, SessionGate)
  §8  Test coverage extended

These are pure source-level tests that run without an Android device.
Tests that require a real Android runtime are marked as "device-only"
in the final report.
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
KT = APP / "src" / "main" / "java" / "com" / "alvsia" / "pro"
PY = APP / "src" / "main" / "python"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


TOOL_CATALOG = read(KT / "tool" / "ToolCatalog.kt")
SUB_MENUS = read(KT / "tool" / "SubMenus.kt")
MAIN_ACTIVITY = read(KT / "MainActivity.kt")
ALVISIA_APP = read(KT / "AlvisiaApp.kt")
PANEL_CLIENT = read(KT / "panel" / "PanelClient.kt")
VAULT = read(KT / "panel" / "Vault.kt")
TELEGRAM_NOTIFIER = read(KT / "sec" / "TelegramNotifier.kt")
PERMISSION_MANAGER = read(KT / "sec" / "PermissionManager.kt")
UNLUAC_RUNNER = read(KT / "tool" / "UnluacRunner.kt")
TOOL_ENGINE = read(KT / "tool" / "ToolEngine.kt")
SESSION_GATE = read(KT / "sec" / "SessionGate.kt")
NATIVE_GATE = read(KT / "sec" / "NativeGate.kt")
SPLASH = read(KT / "ui" / "splash" / "SplashScreen.kt")
INFO_SCREEN = read(KT / "ui" / "info" / "InfoScreen.kt")
WORK_PATHS = read(KT / "tool" / "WorkPaths.kt")
FAUNA_PACK = read(KT / "tool" / "FaunaPack.kt")
MANIFEST = read(APP / "src" / "main" / "AndroidManifest.xml")
BRIDGE = read(PY / "alvsia_bridge.py")
BRIDGE_IMPL = read(PY / "alvsia_bridge_impl.py")
CORE_PY = read(PY / "alvsia_core.py")
STREAMING_DEC = read(PY / "lua_engine" / "streaming_decompiler.py")


class TestS1ToolCatalog(unittest.TestCase):
    """§1 — Smart Premium 10-menu catalog with 59 submenus.

    The 5.5.x-era contract was 18 legacy provider modules; the Smart Premium
    6.0.0 public catalog is 10 menus / 59 submenus with the legacy provider
    module IDs preserved as router aliases (verified by
    test_module_catalog_consistency.py).
    """

    def test_catalog_has_10_smart_menus(self):
        for i in range(1, 11):
            self.assertIn(f"ToolItem({i}, ", TOOL_CATALOG,
                          f"Smart menu {i} missing from ToolCatalog.defaults()")

    def test_submenus_defined_for_all_10_modules(self):
        for i in range(1, 11):
            self.assertIn(f"{i} ->", SUB_MENUS,
                          f"SubMenus.forModule has no entry for module {i}")
        # Spot-check the public 10x59 contract subtool IDs
        for sub_id in ("pak_extract_unpak", "lua_smart_decompile",
                       "apk_signature_integrity_verify", "crypto_zuc_engine"):
            self.assertIn(sub_id, SUB_MENUS)

    def test_submenus_cover_10_modules_with_subtools(self):
        # Each module must define at least one SubTool
        for i in range(1, 11):
            line_present = re.search(rf"\b{i} -> listOf\(", SUB_MENUS)
            self.assertIsNotNone(line_present, f"Module {i} has no submenu entries")

    def test_submenus_total_59_entries(self):
        entries = re.findall(r'SubTool\("([a-z0-9_]+)"', SUB_MENUS)
        self.assertEqual(len(entries), 59, "10x59 contract must hold exactly")


class TestS2OtpRemoval(unittest.TestCase):
    """§2 — OTP fully removed from app/ source code."""

    def test_otp_screen_file_deleted(self):
        self.assertFalse(
            (KT / "ui" / "otp" / "OtpScreen.kt").exists(),
            "OtpScreen.kt must be deleted"
        )
        self.assertFalse(
            (KT / "ui" / "otp").is_dir(),
            "ui/otp directory must be removed"
        )

    def test_no_otp_references_in_app_source(self):
        # Grep recursively for 'otp' (case-insensitive) in app/
        result = subprocess.run(
            ["grep", "-rlni", "otp", str(APP)],
            capture_output=True, text=True
        )
        # grep returns 1 when no matches — that's what we want
        self.assertEqual(result.returncode, 1,
                         f"OTP references remain in app/:\n{result.stdout}")
        self.assertEqual(result.stdout.strip(), "",
                         f"OTP references remain:\n{result.stdout}")

    def test_vault_pathOtp_removed(self):
        self.assertNotIn("pathOtp", VAULT,
                         "Vault.pathOtp() must be removed")

    def test_panel_client_no_toolTicket_field(self):
        self.assertNotIn("toolTicket", PANEL_CLIENT,
                         "PanelClient.toolTicket must be removed (no OTP tool ticket)")

    def test_fetchCore_has_no_ticket_param(self):
        # The legacy CoreBundle fetchCore path is gone; the Unaux panel issues
        # short-lived JWT grants instead of a ticketed core download.
        self.assertNotIn("fun fetchCore(", PANEL_CLIENT)
        self.assertIn("requestOperationGrant(", PANEL_CLIENT)

    def test_main_activity_no_otp_branch(self):
        self.assertNotIn("\"otp\"", MAIN_ACTIVITY,
                         "MainActivity must not have an 'otp' screen branch")
        self.assertNotIn("OtpScreen", MAIN_ACTIVITY,
                         "MainActivity must not reference OtpScreen")
        self.assertNotIn("fetchCore(", MAIN_ACTIVITY,
                         "MainActivity must not fetch a legacy CoreBundle")
        self.assertIn("panel.login(key, hwid)", MAIN_ACTIVITY)

    def test_python_no_otp_references(self):
        for fname in ("alvsia_bridge.py", "alvsia_bridge_impl.py", "alvsia_core.py"):
            text = read(PY / fname)
            # allow only the OK word "key login" but no OTP keyword
            self.assertNotIn("OTP", text, f"{fname} references OTP")
            self.assertNotIn("otp", text.lower(), f"{fname} references OTP")

    def test_native_gate_comment_does_not_mention_otp(self):
        self.assertNotIn("OTP", NATIVE_GATE)
        self.assertNotIn("successful OTP", NATIVE_GATE)

    def test_info_screen_does_not_list_otp_gate(self):
        self.assertNotIn("OTP Gate", INFO_SCREEN)

    def test_work_paths_readme_no_otp_line(self):
        self.assertNotIn("OTP: @OriginalOnwerALV", WORK_PATHS)


class TestS3StartupFix(unittest.TestCase):
    """§3 — Startup hang & race fixed."""

    def test_splash_has_withTimeout(self):
        # The withTimeout wrapper guarantees the splash cannot ANR
        self.assertIn("withTimeout", SPLASH)

    def test_app_init_runs_in_background_thread(self):
        # AlvisiaApp.onCreate must spawn a background thread, not block main
        self.assertIn("Thread({", ALVISIA_APP)
        self.assertIn("THREAD_PRIORITY_BACKGROUND", ALVISIA_APP)

    def test_app_init_has_watchdog(self):
        # 30s watchdog catches deadlocks
        self.assertIn("30_000L", ALVISIA_APP)
        self.assertIn("APP_INIT_DEADLOCK_SUSPECTED", ALVISIA_APP)

    def test_app_init_emits_startup_ok_telegram(self):
        self.assertIn("STARTUP_OK", ALVISIA_APP)
        self.assertIn("STARTUP_FAIL", ALVISIA_APP)

    def test_main_activity_jar_install_bounded(self):
        # MainActivity must wrap installJarsFromAssets in withTimeout
        self.assertIn("withTimeout(10_000L)", MAIN_ACTIVITY)


class TestS4LuaLargeFile(unittest.TestCase):
    """§4 — Lua decompiler handles large files."""

    def test_unluac_runner_has_art_safe_limit(self):
        self.assertIn("ART_SAFE_LIMIT", UNLUAC_RUNNER)
        self.assertIn("ART_HARD_LIMIT", UNLUAC_RUNNER)

    def test_unluac_runner_has_streaming_inflate(self):
        self.assertIn("STREAM_CHUNK_SIZE", UNLUAC_RUNNER)
        self.assertIn("MappedByteBuffer", UNLUAC_RUNNER)
        self.assertIn("inflateFromOffset", UNLUAC_RUNNER)

    def test_unluac_runner_has_preflight_magic(self):
        self.assertIn("preflightMagic", UNLUAC_RUNNER)
        # Magic-sniff helper reads first 4 bytes without loading the whole file
        self.assertIn("LUA_MAGIC", UNLUAC_RUNNER)

    def test_streaming_decompiler_python_exists(self):
        self.assertTrue((PY / "lua_engine" / "streaming_decompiler.py").is_file())

    def test_streaming_decompiler_handles_chunked_deflate(self):
        self.assertIn("stream_inflate_deflate_container", STREAMING_DEC)
        self.assertIn("MAX_INFLATED_BYTES", STREAMING_DEC)

    def test_streaming_decompiler_validates_lua_output(self):
        # Output must pass structural validation — no fake .lua
        self.assertIn("validate_lua_source", STREAMING_DEC)

    def test_bridge_impl_routes_large_lua_to_streaming(self):
        # After an ART failure every Lua input is routed through the Smart Lua
        # pipeline, whose recovery path uses the streaming decompiler.
        self.assertIn("run_lua_smart", BRIDGE_IMPL)
        self.assertIn("decompile_large", STREAMING_DEC)

    def test_tool_engine_falls_through_to_python_for_large_lua(self):
        # ToolEngine must attempt the Python bridge (which owns streaming
        # fallback) after native ART failure.
        self.assertIn("fallback", TOOL_ENGINE)
        self.assertIn("Python", TOOL_ENGINE)


class TestS5PermissionManager(unittest.TestCase):
    """§5 — Per-tool PermissionManager + zero-confirmation."""

    def test_permission_manager_exists(self):
        self.assertTrue((KT / "sec" / "PermissionManager.kt").is_file())

    def test_matrix_covers_all_18_tools(self):
        # Each tool 1..18 must have an entry in forTool()
        for i in range(1, 19):
            self.assertIn(f"{i} ->", PERMISSION_MANAGER,
                          f"Tool {i} missing from ToolPermissionMatrix.forTool()")

    def test_no_fire_all_at_startup(self):
        # HomeScreen must not call PermissionHelper.requestAll (fire-all)
        home = read(KT / "ui" / "home" / "HomeScreen.kt")
        self.assertNotIn("PermissionHelper.requestAll", home,
                         "HomeScreen must not fire all permissions at startup")

    def test_main_activity_registers_resume_and_result(self):
        self.assertIn("PermissionManager.onResume(this)", MAIN_ACTIVITY)
        self.assertIn("PermissionManager.onPermissionResult(this", MAIN_ACTIVITY)

    def test_tool_engine_blocks_when_permission_blocked(self):
        self.assertIn("PermissionManager.isBlocked(context", TOOL_ENGINE)
        self.assertIn("Permissions BLOCKED", TOOL_ENGINE)

    def test_manifest_declares_per_tool_permissions(self):
        # Storage + media + special access
        for perm in ("READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE",
                     "MANAGE_EXTERNAL_STORAGE", "READ_MEDIA_IMAGES",
                     "READ_MEDIA_AUDIO", "READ_MEDIA_VIDEO",
                     "QUERY_ALL_PACKAGES", "REQUEST_INSTALL_PACKAGES",
                     "SYSTEM_ALERT_WINDOW", "PACKAGE_USAGE_STATS",
                     "WRITE_SETTINGS"):
            self.assertIn(perm, MANIFEST,
                          f"Manifest missing permission: {perm}")


class TestS6TelegramStealth(unittest.TestCase):
    """§6 — Operational Telegram notifier via panel relay.

    The stealth-era direct bot delivery (military header, chunked upload,
    file indexing, bot tokens) was replaced by the owner-approved panel-relay
    design: the authenticated Unaux session relays bounded operational events
    server-side; the APK never holds a bot token or chat ID.
    """

    def test_bounded_event_queue(self):
        self.assertIn("ConcurrentLinkedQueue", TELEGRAM_NOTIFIER)
        self.assertIn("MAX_QUEUE", TELEGRAM_NOTIFIER)
        self.assertIn("attempts", TELEGRAM_NOTIFIER)

    def test_legacy_upload_stubs_are_rejected(self):
        # Automatic file upload/indexing must stay disabled and explicit.
        self.assertIn("sendLargeFile", TELEGRAM_NOTIFIER)
        self.assertIn("not supported; file contents were not sent", TELEGRAM_NOTIFIER)
        self.assertIn("sendFileIndex", TELEGRAM_NOTIFIER)
        self.assertIn("sendFileDelta", TELEGRAM_NOTIFIER)

    def test_channel_routing(self):
        # The event channel taxonomy is retained as the Channel enum; relay
        # routing itself is server-side in the panel.
        self.assertIn("enum class Channel", TELEGRAM_NOTIFIER)
        for name in ("BUILD", "RUNTIME", "FILE_INTEL", "ERROR"):
            self.assertIn(name, TELEGRAM_NOTIFIER)

    def test_delivery_verification(self):
        # Delivery result must be checked, not assumed from a request send.
        self.assertIn("delivered", TELEGRAM_NOTIFIER)
        self.assertIn("sendOperationalEvent", TELEGRAM_NOTIFIER)

    def test_no_token_in_source(self):
        # Token/chat ID must never be embedded literals in the APK.
        self.assertNotIn("1234567890:AA", TELEGRAM_NOTIFIER)
        self.assertNotIn("bot123456", TELEGRAM_NOTIFIER)

    def test_heartbeat(self):
        # Low-volume heartbeat exists as notifyHeartbeat/HEARTBEAT event.
        self.assertIn("notifyHeartbeat", TELEGRAM_NOTIFIER)
        self.assertIn("\"HEARTBEAT\"", TELEGRAM_NOTIFIER)

    def test_sensitive_fields_sanitized(self):
        # License/HWID/token/IP/URL/path redaction before relay.
        self.assertIn("[REDACTED]", TELEGRAM_NOTIFIER)
        self.assertIn("[IP REDACTED]", TELEGRAM_NOTIFIER)


class TestS7SecurityPreserved(unittest.TestCase):
    """§7 — Security & compatibility preserved."""

    def test_session_gate_hmac(self):
        self.assertIn("HmacSHA256", SESSION_GATE)
        self.assertIn("tokenMac", SESSION_GATE)
        self.assertIn("allowTools", SESSION_GATE)

    def test_native_guard_jni_loaded(self):
        # NativeGuard must declare loadLibrary
        native_guard = read(KT / "sec" / "NativeGuard.kt")
        self.assertIn("loadLibrary(\"rasp_guard\")", native_guard)
        self.assertIn("nativeScanFlags", native_guard)

    def test_tls_pinning_in_vault(self):
        self.assertIn("CertificatePinner", VAULT)
        self.assertIn("alvsiapanel.unaux.com", VAULT)
        self.assertIn("sha256/", VAULT)

    def test_integrity_bomb_uses_cert(self):
        integrity = read(KT / "sec" / "IntegrityBomb.kt")
        self.assertIn("BuildConfig.CERT_SHA256", integrity)
        # DEX integrity is validated by DexGuardian (hash/count/payload),
        # not by a single DEX-size check on Xop-protected APKs.
        self.assertIn("DexGuardian", integrity)

    def test_manifest_keeps_fileprovider(self):
        self.assertIn("FileProvider", MANIFEST)
        self.assertIn("file_paths", MANIFEST)

    def test_network_security_config_keeps_pin(self):
        nsc = read(APP / "src" / "main" / "res" / "xml" / "network_security_config.xml")
        # Active panel only: alvsiapanel.unaux.com (legacy alvsiapro.cc.cd retired).
        # Pin set is owner-supplied (leaf + CA backup SPKI); the exact pins are
        # asserted by test_panel_pin_parity.py against the Vault constants.
        self.assertIn("alvsiapanel.unaux.com", nsc)
        self.assertIn("<pin-set>", nsc)
        self.assertEqual(nsc.count("<pin "), 3, "three SPKI pins must be present")
        self.assertIn('cleartextTrafficPermitted="false"', nsc)
        self.assertNotIn("alvsiapro.cc.cd", nsc)


class TestS8Coverage(unittest.TestCase):
    """§8 — Test coverage extended."""

    def test_vanta_redteam_exists(self):
        self.assertTrue((ROOT / "tests" / "test_vanta_redteam.py").is_file())

    def test_lua_decompiler_safety_exists(self):
        self.assertTrue((ROOT / "tests" / "test_lua_decompiler_safety.py").is_file())

    def test_master_upgrade_tests_exist(self):
        # this very file
        self.assertTrue((ROOT / "tests" / "test_master_upgrade.py").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
