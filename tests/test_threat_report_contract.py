"""Contract tests for routing threat reports through the authenticated notifier."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/src/main/java/com/alvsia/pro/sec/ThreatReport.kt"


class ThreatReportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_existing_emit_api_is_preserved(self):
        self.assertIn("fun emit(ctx: Context, kind: String, detail: String, license: String = \"\")", self.source)

    def test_uses_authenticated_operational_notifier(self):
        self.assertIn("TelegramNotifier.notify(ctx, event, safeDetail)", self.source)
        self.assertNotIn("OkHttpClient", self.source)
        self.assertNotIn("Vault.pathSecurity()", self.source)

    def test_does_not_attach_device_or_license_identifiers(self):
        for forbidden in ("Hwid.deviceId", "Build.MANUFACTURER", "Build.MODEL",
                          '.put("license"', '.put("hwid"', '.put("model"'):
            self.assertNotIn(forbidden, self.source)

    def test_redacts_secrets_paths_urls_and_location_fields(self):
        for required in ("sensitiveField", "locationField", "[REDACTED]",
                         "[URL REDACTED]", "[PATH REDACTED]"):
            self.assertIn(required, self.source)

    def test_unknown_event_kind_falls_back_to_threat(self):
        self.assertIn('?: "THREAT"', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
