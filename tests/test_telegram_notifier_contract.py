"""Static contract tests for the Android Telegram operational notifier."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/src/main/java/com/alvsia/pro/sec/TelegramNotifier.kt"


class TelegramNotifierContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_delivery_uses_authenticated_panel_relay_not_client_credentials(self):
        self.assertIn("PanelHolder.client", self.source)
        self.assertIn("sendOperationalEvent", self.source)
        self.assertNotIn("Vault.tgToken()", self.source)
        self.assertNotIn("Vault.tgChatId()", self.source)
        self.assertNotRegex(self.source, r"\b\d{7,}:[A-Za-z0-9_-]{20,}\b")

    def test_operational_event_families_are_registered(self):
        for event in (
            "SESSION_OK", "SESSION_START", "SESSION_END", "TOOL_OK",
            "TOOL_ERROR", "FILE_LOADED", "SCAN_COMPLETE", "PATCH_OK",
            "ERROR", "TAMPER", "FRIDA", "ROOT", "DEBUG", "SIG_BLOCK",
            "THREAT", "ENGINE_CAP", "BUILD_OK", "BUILD_FAIL",
            "STARTUP_OK", "STARTUP_FAIL", "MODULE_STATUS", "HEARTBEAT",
        ):
            self.assertIn(f'"{event}"', self.source)

    def test_notifications_are_bounded_and_sanitized(self):
        self.assertIn("MAX_MESSAGE_LEN = 4096", self.source)
        self.assertIn("MAX_QUEUE = 128", self.source)
        self.assertIn("sanitize(detail)", self.source)
        self.assertIn("[REDACTED]", self.source)
        self.assertIn("[PATH REDACTED]", self.source)

    def test_file_reports_are_selected_file_only(self):
        self.assertIn("notifyFileLoaded", self.source)
        self.assertIn("if (!selectedFile.isFile) return", self.source)
        self.assertIn("selectedFile.name", self.source)
        self.assertIn("selectedFile.length()", self.source)
        self.assertNotIn("sendDocument", self.source)
        self.assertNotIn("sendPhoto", self.source)

    def test_no_automatic_storage_crawl_or_file_delta_upload(self):
        self.assertNotIn("walkTopDown()", self.source)
        self.assertNotIn("Environment.getExternalStorageDirectory()", self.source)
        self.assertIn("Full storage indexing is not part of operational notifications", self.source)
        self.assertIn("Background file-delta reporting is not part of operational notifications", self.source)
        self.assertIn("Automatic file upload is not supported", self.source)

    def test_module_scan_and_heartbeat_events_are_wired_to_activity(self):
        activity = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
        self.assertIn("TelegramNotifier.notifyModuleStatus(", activity)
        self.assertIn("TelegramNotifier.notifyScanComplete(", activity)
        self.assertIn("TelegramNotifier.notifyHeartbeat(", activity)
        self.assertIn('"SIG_BLOCK"', activity)
        self.assertIn("TelegramNotifier.notifySessionStart(", activity)
        self.assertIn("5 * 60_000L", activity)

    def test_telegram_payload_excludes_device_identifiers(self):
        self.assertNotIn("Build.MANUFACTURER", self.source)
        self.assertNotIn("Build.MODEL", self.source)
        self.assertNotIn("DEVICE:", self.source)
        self.assertNotIn("Hwid.deviceId", self.source)

    def test_message_html_is_escaped(self):
        self.assertIn('replace("&", "&amp;")', self.source)
        self.assertIn('replace("<", "&lt;")', self.source)
        self.assertIn('replace(">", "&gt;")', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
