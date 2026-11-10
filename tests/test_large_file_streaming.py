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
from lua_string_recover import recover_strings_file


class TestLargeFileStreaming(unittest.TestCase):
    def test_detector_reads_only_header_for_large_luac(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "large.luac"
            with path.open("wb") as output:
                output.write(b"\\x1bLua\\x53\\x00")
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
            source.write_bytes(b"PlayerCharacter function ServerRPC\\x00" + b"\\x00" * (2 * 1024 * 1024))
            out = root / "out"
            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                with patch("lua_string_recover.DEFAULT_SAMPLE_LIMIT", 4096):
                    result = recover_strings_file(source, out, "sample")
            self.assertTrue(result["ok"], result)
            text = (out / "sample_strings_plain.txt").read_text(encoding="utf-8")
            self.assertIn("PlayerCharacter", text)
            self.assertTrue(result["streaming"])

    def test_lua53_parser_rejects_over_budget_before_loading(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "large.luac"
            with source.open("wb") as output:
                output.write(b"\\x1bLua\\x53")
                output.truncate(16 * 1024 * 1024 + 1)
            with patch.dict(os.environ, {"ALVSIA_LUA53_MAX_IN_MEMORY_BYTES": str(16 * 1024 * 1024)}):
                ok, message = stream_decompile_lua53(source, Path(td) / "out.lua")
            self.assertFalse(ok)
            self.assertIn("lua53_parser_memory_limit", message)


if __name__ == "__main__":
    unittest.main()
