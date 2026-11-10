#!/usr/bin/env python3
"""Regression checks that release security controls remain wired into runtime."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class SecurityWiringTests(unittest.TestCase):
    def test_manifest_security_baseline(self):
        m = read("app/src/main/AndroidManifest.xml")
        self.assertIn('android:allowBackup="false"', m)
        self.assertIn('android:networkSecurityConfig="@xml/network_security_config"', m)
        self.assertIn('android:name=".AlvisiaApp"', m)

    def test_unaux_tls_pin_is_strictly_configured(self):
        x = read("app/src/main/res/xml/network_security_config.xml")
        self.assertIn("alvsiapanel.unaux.com", x)
        self.assertIn('cleartextTrafficPermitted="false"', x)
        pins = re.findall(r'<pin digest="SHA-256">([^<]+)</pin>', x)
        self.assertTrue(pins, "missing TLS SPKI pin")
        import base64
        for pin in pins:
            self.assertEqual(len(base64.b64decode(pin, validate=True)), 32)

    def test_sensitive_screens_enable_capture_and_tapjacking_protection(self):
        activity = read("app/src/main/java/com/alvsia/pro/MainActivity.kt")
        self.assertIn("FLAG_SECURE", activity)
        self.assertIn("filterTouchesWhenObscured = true", activity)

    def test_flag_secure_is_applied_at_activity_creation_and_never_cleared(self):
        activity = read("app/src/main/java/com/alvsia/pro/MainActivity.kt")
        self.assertIn("window.setFlags(", activity)
        self.assertIn("WindowManager.LayoutParams.FLAG_SECURE", activity)
        self.assertNotIn("window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)", activity)

    def test_network_proxy_detection_and_guard_health_are_wired(self):
        network = read("app/src/main/java/com/alvsia/pro/sec/NetworkGuard.kt")
        rasp = read("app/src/main/java/com/alvsia/pro/sec/RaspEngine.kt")
        self.assertIn("fun detect_proxy(ctx: Context)", network)
        self.assertIn("fun net_guard(ctx: Context)", network)
        self.assertIn("cm.defaultProxy", network)
        self.assertIn("ProxySelector.getDefault()", network)
        self.assertIn("NetworkGuard.detect_proxy(ctx)", rasp)
        self.assertIn("NetworkGuard.net_guard(ctx)", rasp)

    def test_xop_apk_size_guard_measures_apk_not_dex(self):
        integrity = read("app/src/main/java/com/alvsia/pro/sec/IntegrityBomb.kt")
        self.assertIn("APK_MIN_BYTES", integrity)
        self.assertIn("APK_MAX_BYTES", integrity)
        self.assertIn("private fun apkSizeOk(ctx: Context)", integrity)
        self.assertIn("File(ctx.applicationInfo.sourceDir)", integrity)
        self.assertIn("apk.length() in APK_MIN_BYTES..APK_MAX_BYTES", integrity)
        self.assertIn("DexGuardian.evaluate(ctx)", integrity)
        self.assertNotIn("DEX_MAX", integrity)
        self.assertNotIn("private fun dexSizeOk", integrity)

    def test_medium_lua_chunks_bypass_in_process_art_unluac(self):
        runner = read("app/src/main/java/com/alvsia/pro/tool/UnluacRunner.kt")
        self.assertIn("ART_SAFE_LIMIT = 256L * 1024L", runner)
        self.assertIn("Python fallback will handle this input", runner)
        self.assertIn("normalizedSize > ART_SAFE_LIMIT", runner)

    def test_pinned_panel_transport_does_not_follow_redirects(self):
        client = read("app/src/main/java/com/alvsia/pro/panel/PanelClient.kt")
        self.assertIn(".followRedirects(false)", client)
        self.assertIn(".followSslRedirects(false)", client)

    def test_backup_and_device_transfer_are_explicitly_excluded(self):
        manifest = read("app/src/main/AndroidManifest.xml")
        self.assertIn('android:fullBackupContent="@xml/backup_rules"', manifest)
        self.assertIn('android:dataExtractionRules="@xml/data_extraction_rules"', manifest)
        rules = read("app/src/main/res/xml/backup_rules.xml")
        extraction = read("app/src/main/res/xml/data_extraction_rules.xml")
        self.assertIn('<exclude domain="sharedpref" path="." />', rules)
        self.assertIn('<device-transfer>', extraction)
        self.assertIn('<exclude domain="sharedpref" path="." />', extraction)

    def test_release_never_falls_back_to_plaintext_jars(self):
        engine = read("app/src/main/java/com/alvsia/pro/tool/ToolEngine.kt")
        self.assertIn("if (!com.alvsia.pro.BuildConfig.DEBUG)", engine)
        self.assertIn("sealedCount > 0 || !com.alvsia.pro.BuildConfig.DEBUG", engine)
        self.assertIn("Debug/CI only fallback", engine)

    def test_file_provider_is_limited_to_output_files(self):
        paths = read("app/src/main/res/xml/file_paths.xml")
        self.assertIn('path="ALVSIA/OUT/"', paths)
        self.assertIn('path="Download/ALVSIA/OUT/"', paths)
        self.assertNotIn('path="."', paths)
        self.assertNotIn("<cache-path", paths)
        manifest = read("app/src/main/AndroidManifest.xml")
        self.assertIn('android:exported="false"', manifest)

    def test_zip_extraction_rejects_path_traversal(self):
        engine = read("app/src/main/java/com/alvsia/pro/tool/ToolEngine.kt")
        self.assertIn("private fun safeZipTarget(root: File, entryName: String): File?", engine)
        self.assertGreaterEqual(engine.count("safeZipTarget(dest,"), 2)
        self.assertIn('target.path.startsWith(prefix)', engine)
        self.assertIn('WARN skipped unsafe archive path', engine)

    def test_obb_extractor_rejects_symlink_entries(self):
        features = read("app/src/main/python/alvsia_features.py")
        self.assertIn("mode == 0o120000", features)
        self.assertIn("symlink archive entry rejected", features)

    def test_sealed_asset_materialization_rejects_path_segments(self):
        vault = read("app/src/main/java/com/alvsia/pro/asset/AssetVault.kt")
        self.assertIn("private fun isSafeAssetName(name: String): Boolean", vault)
        self.assertIn("private fun safeJarTarget(root: File, name: String): File?", vault)
        self.assertIn("target.parentFile == canonicalRoot", vault)
        self.assertIn("!isSafeAssetName(file)", vault)
        self.assertIn("safeJarTarget(jarsDir, name) ?: continue", vault)
        self.assertIn("dest.readBytes().contentEquals(bytes)", vault)
        self.assertIn("Length alone is not integrity", vault)

    def test_runtime_security_bootstrap_is_wired(self):
        app = read("app/src/main/java/com/alvsia/pro/AlvisiaApp.kt")
        self.assertIn("RaspEngine.start(this)", app)
        self.assertIn("Guard.checkAndReport(this)", app)
        self.assertIn("EnvProbe.report(this)", app)

    def test_every_protected_dispatch_rechecks_integrity_and_session(self):
        gate = read("app/src/main/java/com/alvsia/pro/sec/SessionGate.kt")
        self.assertIn("fun allowTools(ctx: Context)", gate)
        self.assertIn("runtimeHostile(ctx)", gate)
        self.assertIn("DualVmGuard.inspect(ctx)", gate)
        self.assertIn("IntegrityBomb.isCompromised(ctx)", gate)
        self.assertIn("if (!sessionOk)", gate)
        self.assertIn("SESSION_TTL", gate)

    def test_hook_scanners_only_block_executable_map_paths(self):
        guard = read("app/src/main/java/com/alvsia/pro/sec/Guard.kt")
        frida = read("app/src/main/java/com/alvsia/pro/sec/FridaProbe.kt")
        anti_hook = read("app/src/main/java/com/alvsia/pro/sec/AntiHook.kt")
        native = read("app/src/main/cpp/rasp_guard.cpp")
        for source in (guard, frida, anti_hook):
            self.assertIn("'x' !in fields[1]", source)
            self.assertIn('getOrNull(5)', source)
        self.assertIn("map_line_has_exec_marker", native)
        self.assertNotIn("if (strstr(buf, MAP_NEEDLES[i]))", native)
        self.assertNotIn("if (strstr(buf, LATE_LIB_NEEDLES[i]))", native)

    def test_hook_marker_severity_avoids_protector_self_block(self):
        guard = read("app/src/main/java/com/alvsia/pro/sec/Guard.kt")
        frida = read("app/src/main/java/com/alvsia/pro/sec/FridaProbe.kt")
        anti_hook = read("app/src/main/java/com/alvsia/pro/sec/AntiHook.kt")
        native_guard = read("app/src/main/java/com/alvsia/pro/sec/NativeGuard.kt")
        rasp = read("app/src/main/java/com/alvsia/pro/sec/RaspEngine.kt")
        native = read("app/src/main/cpp/rasp_guard.cpp")

        self.assertIn("HARD_RUNTIME_MARKERS", guard)
        self.assertIn("SOFT_HOOK_MARKERS", guard)
        self.assertIn("SOFT_HOOK_LIBRARY_MARKERS", frida)
        self.assertIn('out += "hooklib:$it"', frida)
        self.assertIn('out += "hooklib:$it"', anti_hook)
        self.assertIn('if (signal.startsWith("hooklib:")) soft += signal', rasp)
        self.assertIn('"linjector"', native_guard)
        maps_block = native.split("static const char* MAP_NEEDLES[] = {", 1)[1].split("};", 1)[0]
        late_block = native.split("static const char* LATE_LIB_NEEDLES[] = {", 1)[1].split("};", 1)[0]
        for soft_marker in ("shadowhook", "bytehook", "libdobby", "xposed"):
            self.assertNotIn(soft_marker, maps_block)
            self.assertNotIn(soft_marker, late_block)

    def test_rasp_layers_include_debug_hook_memory_and_integrity(self):
        rasp = read("app/src/main/java/com/alvsia/pro/sec/RaspEngine.kt")
        for marker in ("Debug.isDebuggerConnected()", "FridaProbe.signals()",
                       "MemoryGuard.detectPtrace()", "IntegrityBomb.evaluate(ctx)",
                       "DualVmGuard.inspect(ctx)", "NativeGuard.antiDump()"):
            self.assertIn(marker, rasp)

    def test_sealed_payloads_fail_closed_and_release_signing_is_verified(self):
        guard = read("app/src/main/java/com/alvsia/pro/sec/NativeGuard.kt")
        seal = read("tools/seal_python.py")
        yaml = read("codemagic.yaml")
        self.assertIn("decryptSealedPayload", guard)
        self.assertIn("AES/GCM/NoPadding", guard)
        self.assertIn("ALVSEAL2", seal)
        self.assertIn("CM_KEY_ALIAS", yaml)
        self.assertIn("apksigner", yaml)
        self.assertIn("CERT_SHA256", yaml)

if __name__ == "__main__":
    unittest.main(verbosity=2)
