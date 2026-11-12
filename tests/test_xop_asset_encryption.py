import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class XopAssetEncryptionWiringTests(unittest.TestCase):
    def test_final_release_enables_xop_asset_encryption(self):
        text = (ROOT / ".github/workflows/alvsia-final-release.yml").read_text(encoding="utf-8")
        self.assertIn("--encrypt-assets", text)
        self.assertIn("AssetsEncryptor.java", text)
        self.assertIn('rel.startsWith("chaquopy/")', text)
        self.assertIn('rel.startsWith("engine_licenses/")', text)

    def test_validation_enables_xop_asset_encryption(self):
        text = (ROOT / ".github/workflows/android-validation.yml").read_text(encoding="utf-8")
        self.assertIn("--encrypt-assets", text)
        self.assertIn("AssetsEncryptor.java", text)
        self.assertIn('rel.startsWith("chaquopy/")', text)

    def test_runtime_routes_sealed_jars_through_protector_assets(self):
        text = (ROOT / "app/src/main/java/com/alvsia/pro/asset/AssetVault.kt").read_text(encoding="utf-8")
        self.assertIn('Class.forName("com.yqsh.protector.shell.ProtectorAssets")', text)
        self.assertIn('readBytes.invoke(null, ctx, "nx/i.dat")', text)
        self.assertIn('readBytes.invoke(null, ctx, "nx/$file")', text)

    def test_audit_requires_xop_asset_encryption(self):
        text = (ROOT / "tools/audit_release_apk.py").read_text(encoding="utf-8")
        self.assertIn('xop_config.get("encrypt_assets") is True', text)
        self.assertIn('"assets/protector/aenc/nx/i.dat"', text)
        self.assertIn('startswith(b"PAS1")', text)

if __name__ == "__main__":
    unittest.main()
