"""Parity tests for safe file-scanning capabilities adapted from source tools."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src" / "main" / "python"))

from alvsia_features import BinaryURLScanner  # noqa: E402


def test_binary_url_scanner_extracts_url_host_and_public_ip():
    data = (
        b"url=https://cdn.example.com/assets/index.bin\x00"
        b"api endpoint api.game.example.net:8443\x00"
        b"gateway=8.8.8.8:443\x00"
        b"127.0.0.1:8080"
    )
    hits = BinaryURLScanner().scan_bytes(data)
    values = {value for _, value in hits}
    assert "https://cdn.example.com/assets/index.bin" in values
    assert "api.game.example.net:8443" in values
    assert "8.8.8.8:443" in values
    assert "127.0.0.1:8080" not in values


def test_binary_url_scanner_deduplicates_results():
    data = b"https://cdn.example.com/a\x00https://cdn.example.com/a"
    hits = BinaryURLScanner().scan_bytes(data)
    urls = [value for kind, value in hits if kind == "URL"]
    assert urls == ["https://cdn.example.com/a"]


def test_binary_url_scanner_reads_a_selected_file_only():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "sample.so"
        path.write_bytes(b"connect=https://service.example.org/v1")
        hits = BinaryURLScanner().scan_file(str(path))
        assert any(kind == "URL" and value.startswith("https://service.example.org") for kind, value in hits)
