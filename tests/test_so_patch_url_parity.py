"""Regression tests for multi-occurrence, non-destructive SO URL patching."""
import ast
import hashlib
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/src/main/python/alvsia_ultimate.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
FUNCTION = next(node for node in TREE.body
                if isinstance(node, ast.FunctionDef) and node.name == "so_patch_url")
ISOLATED = ast.Module(body=[FUNCTION], type_ignores=[])
NAMESPACE = {"Path": Path}
exec(compile(ISOLATED, str(SOURCE), "exec"), NAMESPACE)
so_patch_url = NAMESPACE["so_patch_url"]


class SoPatchUrlParityTests(unittest.TestCase):
    def test_patches_all_exact_occurrences_and_preserves_offsets(self):
        old = b"https://old.example/a"
        new = b"https://new.example"
        original = b"HEAD\\x00" + old + b"\\x00MID\\x00" + old + b"\\x00TAIL"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "libsample.so"
            out = root / "out"
            source.write_bytes(original)
            result = so_patch_url(str(source), str(out), old.decode(), new.decode())
            self.assertTrue(result["ok"], result)
            patched = Path(result["out"]).read_bytes()
            padded = new + b"\\x00" * (len(old) - len(new))
            self.assertEqual(patched, original.replace(old, padded))
            self.assertEqual(result["patched_count"], 2)
            self.assertEqual(result["patched_offsets"], [
                "0x%X" % original.find(old),
                "0x%X" % original.rfind(old),
            ])
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(result["original_sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(result["output_sha256"], hashlib.sha256(patched).hexdigest())

    def test_rejects_longer_replacement_without_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "lib.so"
            source.write_bytes(b"https://a")
            result = so_patch_url(str(source), str(root / "out"),
                                  "https://a", "https://long.example")
            self.assertFalse(result["ok"])
            self.assertFalse((root / "out" / "patched_lib.so").exists())
            self.assertEqual(source.read_bytes(), b"https://a")

    def test_missing_url_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "lib.so"
            source.write_bytes(b"no endpoint here")
            result = so_patch_url(str(source), str(root / "out"),
                                  "https://missing.example", "https://new.example")
            self.assertFalse(result["ok"])
            self.assertIn("not found", result["error"])

    def test_requires_both_urls(self):
        result = so_patch_url("unused", "unused", "", "https://new")
        self.assertFalse(result["ok"])
        self.assertIn("required", result["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
