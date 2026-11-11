"""Parity tests for safe file-scanning capabilities adapted from source tools."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src" / "main" / "python"))

from alvsia_features import BinaryURLScanner  # noqa: E402


class BinaryURLScannerParityTests(unittest.TestCase):
    def test_extracts_url_host_and_public_ip(self):
        data = (
            b"url=https://cdn.example.com/assets/index.bin\x00"
            b"api endpoint api.game.example.net:8443\x00"
            b"gateway=8.8.8.8:443\x00"
            b"127.0.0.1:8080"
        )
        hits = BinaryURLScanner().scan_bytes(data)
        values = {value for _, value in hits}
        self.assertIn("https://cdn.example.com/assets/index.bin", values)
        self.assertIn("api.game.example.net:8443", values)
        self.assertIn("8.8.8.8:443", values)
        self.assertNotIn("127.0.0.1:8080", values)

    def test_deduplicates_results(self):
        data = b"https://cdn.example.com/a\x00https://cdn.example.com/a"
        hits = BinaryURLScanner().scan_bytes(data)
        urls = [value for kind, value in hits if kind == "URL"]
        self.assertEqual(urls, ["https://cdn.example.com/a"])

    def test_reads_only_the_selected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.so"
            path.write_bytes(b"connect=https://service.example.org/v1")
            hits = BinaryURLScanner().scan_file(str(path))
            self.assertTrue(any(
                kind == "URL" and value.startswith("https://service.example.org")
                for kind, value in hits
            ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
