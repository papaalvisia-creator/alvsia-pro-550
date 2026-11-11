"""Native-library packaging must stay installable.

A packer that recompresses a subset of ``lib/<abi>/*.so`` produces a mixed
compression APK. With ``android:extractNativeLibs="false"`` the package manager
rejects it (INSTALL_FAILED_INVALID_APK, surfaced on device as "paket tidak
valid"). These tests pin the normaliser that runs before signing.
"""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import normalize_apk_packaging as nap  # noqa: E402


def _build_apk(path: Path, native_methods: dict[str, int]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"\x03\x00\x08\x00manifest")
        archive.writestr("classes.dex", b"dex\n035\x00" + b"\x00" * 64, zipfile.ZIP_DEFLATED)
        archive.writestr("assets/protector/dexes.zip", b"PK\x03\x04payload", zipfile.ZIP_DEFLATED)
        for name, method in native_methods.items():
            archive.writestr(name, b"\x7fELF" + b"\x00" * 256, method)


class NativeLibraryPackagingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_check_flags_compressed_native_libraries(self):
        apk = self.tmp / "mixed.apk"
        _build_apk(apk, {
            "lib/arm64-v8a/libprotector.so": zipfile.ZIP_DEFLATED,
            "lib/arm64-v8a/librasp_guard.so": zipfile.ZIP_STORED,
        })
        problems = nap.native_lib_violations(apk)
        self.assertEqual(len(problems), 1)
        self.assertIn("libprotector.so", problems[0])

    def test_check_passes_when_all_native_libraries_are_stored(self):
        apk = self.tmp / "clean.apk"
        _build_apk(apk, {"lib/arm64-v8a/libprotector.so": zipfile.ZIP_STORED})
        self.assertEqual(nap.native_lib_violations(apk), [])

    def test_normalize_stores_native_libraries_and_preserves_everything_else(self):
        src = self.tmp / "mixed.apk"
        _build_apk(src, {
            "lib/arm64-v8a/libprotector.so": zipfile.ZIP_DEFLATED,
            "lib/arm64-v8a/libc++_shared.so": zipfile.ZIP_DEFLATED,
            "lib/arm64-v8a/librasp_guard.so": zipfile.ZIP_STORED,
        })
        out = self.tmp / "normalized.apk"
        changed = nap.normalize(src, out)

        self.assertEqual(changed, 2)
        self.assertEqual(nap.native_lib_violations(out), [])

        with zipfile.ZipFile(src) as a, zipfile.ZipFile(out) as b:
            # No entry may be added, removed or reordered.
            self.assertEqual([i.filename for i in a.infolist()],
                             [i.filename for i in b.infolist()])
            # Payload bytes must be identical for every entry.
            for info in a.infolist():
                self.assertEqual(a.read(info.filename), b.read(info.filename))
            # Non-native entries keep their original compression method.
            self.assertEqual(b.getinfo("classes.dex").compress_type, zipfile.ZIP_DEFLATED)
            self.assertEqual(b.getinfo("assets/protector/dexes.zip").compress_type,
                             zipfile.ZIP_DEFLATED)
            self.assertIsNone(b.testzip())

    def test_normalize_is_idempotent(self):
        src = self.tmp / "clean.apk"
        _build_apk(src, {"lib/arm64-v8a/libprotector.so": zipfile.ZIP_STORED})
        out = self.tmp / "again.apk"
        self.assertEqual(nap.normalize(src, out), 0)
        self.assertEqual(nap.native_lib_violations(out), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
