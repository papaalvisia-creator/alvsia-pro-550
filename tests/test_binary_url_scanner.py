from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"))

from alvsia_features import BinaryURLScanner


def _put_at(buffer: bytearray, offset: int, prefix: bytes, value: bytes) -> None:
    target = offset - len(prefix)
    if len(buffer) < target:
        buffer.extend(b"\x00" * (target - len(buffer)))
    buffer.extend(prefix)
    buffer.extend(value)


def test_streaming_scan_file_matches_buffer_scan_across_chunk_boundaries(tmp_path, monkeypatch):
    scanner = BinaryURLScanner()
    scanner._CHUNK = 1024

    data = bytearray(b"A" * 993)
    _put_at(data, 1000, b"server ", b"https://api.example.com:8443/v1/path")
    _put_at(data, 2040, b"host=", b"cdn.example.net:8080")
    _put_at(
        data, 3070, b"endpoint=",
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/abcd",
    )
    _put_at(data, 4090, b"connect ", b"203.0.113.7:443")
    data.extend(b"Z" * 700)

    expected = scanner.scan_bytes(bytes(data))
    sample = tmp_path / "large_binary_scan.bin"
    sample.write_bytes(data)

    monkeypatch.setattr(
        Path, "read_bytes",
        lambda self: (_ for _ in ()).throw(AssertionError("whole-file read attempted")),
    )
    actual = scanner.scan_file(sample)

    assert sorted(actual) == sorted(expected)
    assert any(kind == "URL" and "api.example.com" in value for kind, value in actual)
    assert any(kind == "HOST" and "cdn.example.net" in value for kind, value in actual)
    assert any(kind == "B64" for kind, _ in actual)
    assert any(kind == "IP" and "203.0.113.7" in value for kind, value in actual)


def test_streaming_scan_file_handles_empty_input(tmp_path):
    scanner = BinaryURLScanner()
    sample = tmp_path / "empty.bin"
    sample.write_bytes(b"")
    assert scanner.scan_file(sample) == []
