import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.detector import detect_lua
from lua_engine.streaming_decompiler import stream_decompile_lua53
from lua_string_recover import _iter_ascii_file, recover_strings_file
from alvsia_features import run_hash_file, run_string_scan


class TestLargeFileStreaming(unittest.TestCase):
    def test_detector_reads_only_header_for_large_luac(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "large.luac"
            with path.open("wb") as output:
                output.write(b"\x1bLua\x53\x00")
                output.truncate(1024 * 1024 * 1024)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                info = detect_lua(path)
            self.assertEqual(info.kind, "bytecode")
            self.assertEqual(info.format, "luac")
            self.assertEqual(info.size, 1024 * 1024 * 1024)

    def test_string_recovery_uses_file_stream_not_read_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "sample.bin"
            source.write_bytes(b"PlayerCharacter function ServerRPC\x00" + b"\x00" * (2 * 1024 * 1024))
            out = root / "out"
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                with patch("lua_string_recover.DEFAULT_SAMPLE_LIMIT", 4096):
                    result = recover_strings_file(source, out, "sample")
            self.assertTrue(result["ok"], result)
            text = (out / "sample_strings_plain.txt").read_text(encoding="utf-8")
            self.assertIn("PlayerCharacter", text)
            self.assertTrue(result["streaming"])

    def test_string_iterator_scans_sparse_one_gib_file_with_bounded_memory(self):
        # Sparse fixture keeps repository storage small while exercising a
        # full 1-GiB sequential scan and both file boundaries.
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sparse-1g.bin"
            size = 1024 * 1024 * 1024
            with path.open("wb") as output:
                output.write(b"BEGIN_GB_SCAN")
                output.truncate(size - 32)
                output.seek(size - 20)
                output.write(b"END_GB_SCAN")
                output.truncate(size)

            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                strings = list(_iter_ascii_file(path, chunk_size=1024 * 1024))

            self.assertIn("BEGIN_GB_SCAN", strings)
            self.assertIn("END_GB_SCAN", strings)

    def test_string_iterator_preserves_multibyte_xor_phase_across_chunks(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "xor.bin"
            expected = b"prefix_PlayerCharacter_suffix"
            key = b"PUBG"
            encoded = bytes(value ^ key[i % len(key)] for i, value in enumerate(expected))
            path.write_bytes(encoded)
            recovered = list(_iter_ascii_file(
                path, min_len=4, xor_multi_key=key, chunk_size=7
            ))
            self.assertEqual(recovered, ["prefix_PlayerCharacter_suffix"])

    def test_generic_hash_streams_without_whole_file_read(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "hash-large.bin"
            payload = b"ALVSIA_HASH_STREAM" + b"\\x00" * (2 * 1024 * 1024)
            source.write_bytes(payload)
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                result = run_hash_file(source)
            self.assertTrue(result["ok"], result)
            self.assertIn(f"size={len(payload)}", result["report"])
            self.assertIn(f"sha256={hashlib.sha256(payload).hexdigest()}", result["report"])

    def test_generic_string_scan_uses_streaming_iterator(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "strings-large.bin"
            source.write_bytes(b"FIRST_PLAYER\\x00" + b"\\x00" * (2 * 1024 * 1024) + b"LAST_CHARACTER")
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                result = run_string_scan(source)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["count"], 2)

    def test_lua53_parser_rejects_over_budget_before_loading(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "large.luac"
            with source.open("wb") as output:
                output.write(b"\x1bLua\x53")
                output.truncate(16 * 1024 * 1024 + 1)
            with patch.dict(os.environ, {"ALVSIA_LUA53_MAX_IN_MEMORY_BYTES": str(16 * 1024 * 1024)}):
                ok, message = stream_decompile_lua53(source, Path(td) / "out.lua")
            self.assertFalse(ok)
            self.assertIn("lua53_parser_memory_limit", message)


if __name__ == "__main__":
    unittest.main()
