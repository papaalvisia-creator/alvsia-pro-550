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

    def test_runtime_credentials_are_vault_backed_not_embedded(self):
        self.assertIn("Vault.tgToken()", self.source)
        self.assertIn("Vault.tgChatId()", self.source)
        self.assertNotRegex(self.source, r"\b\d{7,}:[A-Za-z0-9_-]{20,}\b")

    def test_operational_event_families_are_registered(self):
        for event in (
            "SESSION_OK", "SESSION_START", "SESSION_END", "TOOL_OK",
            "TOOL_ERROR", "FILE_LOADED", "SCAN_COMPLETE", "PATCH_OK",
            "ERROR", "TAMPER", "FRIDA", "ROOT", "DEBUG", "SIG_BLOCK",
            "THREAT", "ENGINE_CAP", "BUILD_OK", "BUILD_FAIL",
            "STARTUP_OK", "STARTUP_FAIL",
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

    def test_message_html_is_escaped(self):
        self.assertIn('replace("&", "&amp;")', self.source)
        self.assertIn('replace("<", "&lt;")', self.source)
        self.assertIn('replace(">", "&gt;")', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
