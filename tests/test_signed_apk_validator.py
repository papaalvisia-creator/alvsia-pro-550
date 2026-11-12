"""Regression tests for signed APK certificate fingerprint enforcement."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validate_signed_apk as validator  # noqa: E402

PIN = "99b33815c88a17abbcfe22be15250363f6dfc79c11ffc980e71b62b74b1f295c"


class SignedApkCertificatePinTests(unittest.TestCase):
    def test_reads_release_certificate_pin_from_gradle_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "build.gradle.kts"
            config.write_text(
                f'buildConfigField("String", "CERT_SHA256", "\\"{PIN}\\"")\n',
                encoding="utf-8",
            )
            self.assertEqual(validator.expected_certificate_sha256(config), PIN)

    def test_normalizes_colon_separated_apksigner_fingerprint(self):
        colon_pin = ":".join(PIN[i:i + 2] for i in range(0, len(PIN), 2))
        output = f"Signer #1 certificate SHA-256 digest: {colon_pin}\n"
        self.assertEqual(validator.certificate_sha256(output), PIN)

    def test_alignment_check_requires_16k_page_alignment(self):
        self.assertEqual(
            validator.alignment_check_args(Path("zipalign"), Path("candidate.apk")),
            ["zipalign", "-c", "-P", "16", "-v", "4", "candidate.apk"],
        )

    def test_rejects_missing_certificate_fingerprint(self):
        with self.assertRaises(SystemExit):
            validator.certificate_sha256("Verified using v2 scheme: true")

    def test_rejects_missing_release_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "build.gradle.kts"
            config.write_text('buildConfigField("String", "PROTO", "2")\n', encoding="utf-8")
            with self.assertRaises(SystemExit):
                validator.expected_certificate_sha256(config)


    def test_reads_active_gradle_package_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "build.gradle.kts"
            config.write_text(
                'applicationId = "com.alvsia.pro"\n'
                'versionCode = 100\n'
                'versionName = "6.0.0-smart-premium"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                validator.expected_package_identity(config),
                ("com.alvsia.pro", "100", "6.0.0-smart-premium"),
            )

    def test_rejects_missing_gradle_package_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "build.gradle.kts"
            config.write_text('versionCode = 100\n', encoding="utf-8")
            with self.assertRaises(SystemExit):
                validator.expected_package_identity(config)

    def test_parses_aapt_package_identity(self):
        output = "package: name='com.alvsia.pro' versionCode='100' versionName='6.0.0-smart-premium'\n"
        self.assertEqual(
            validator.package_identity(output),
            ("com.alvsia.pro", "100", "6.0.0-smart-premium"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
