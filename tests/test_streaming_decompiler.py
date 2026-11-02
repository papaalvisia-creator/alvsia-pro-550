"""
Test streaming Lua decompiler for large file handling.

Verifies that:
  • preflight_magic returns the correct label for each input kind
  • stream_inflate_deflate_container recovers Lua bytecode from
    a synthetic chunked-DEFLATE container
  • large input files (>8 MiB) do not crash the streaming path
"""
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "app" / "src" / "main" / "python"
sys.path.insert(0, str(PY))

from lua_engine.streaming_decompiler import (
    preflight_magic,
    stream_inflate_deflate_container,
    decompile_large,
)


class TestPreflightMagic(unittest.TestCase):
    def test_luac53_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.luac"
            p.write_bytes(b"\x1bLua\x53\x00" + b"\x00" * 32)
            self.assertEqual(preflight_magic(p), "luac_53")

    def test_comment_prefixed_luac53_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "prefixed.lua"
            p.write_bytes(b"-- exported Lua chunk\\n-- metadata\\n" +
                          b"\\x1bLua\\x53\\x00" + b"\\x19\\x93\\x0d\\x0a\\x1a\\x0a" +
                          b"\\x00" * 32)
            self.assertEqual(preflight_magic(p), "embedded_luac_53")

    def test_comment_prefixed_luajit_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "prefixed.lj"
            p.write_bytes(b"-- exported LuaJIT chunk\\n" + b"\\x1bLJ\\x02" + b"\\x00" * 16)
            self.assertEqual(preflight_magic(p), "embedded_luajit")

    def test_arbitrary_binary_embedded_magic_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wrapped.bin"
            p.write_bytes(b"BIN\\x00garbage\\x1bLua\\x53" + b"\\x00" * 32)
            self.assertTrue(preflight_magic(p).startswith("unknown_"))

    def test_luajit_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.lj"
            p.write_bytes(b"\x1bLJ" + b"\x00" * 16)
            self.assertEqual(preflight_magic(p), "luajit")

    def test_chunked_deflate_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.bin"
            p.write_bytes(b"\x78\xDA" + b"\x00" * 8)
            self.assertEqual(preflight_magic(p), "chunked_deflate")

    def test_gzip_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.gz"
            p.write_bytes(b"\x1f\x8b" + b"\x00" * 8)
            self.assertEqual(preflight_magic(p), "gzip")

    def test_unknown_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.bin"
            p.write_bytes(b"XXXX" + b"\x00" * 8)
            self.assertTrue(preflight_magic(p).startswith("unknown_"))

    def test_too_small(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x"
            p.write_bytes(b"\x1b")
            self.assertEqual(preflight_magic(p), "too_small")


class TestStreamInflate(unittest.TestCase):
    def test_recover_lua_payload_from_deflate(self):
        """Build a synthetic chunked-raw-DEFLATE container whose payload
        starts with the LuaS magic, and verify stream-inflate recovers it."""
        payload = b"\x1bLua\x53\x00" + b"\x19\x93\x0d\x0a\x1a\x0a" + b"PAYLOAD" * 4
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        compressed = co.compress(payload) + co.flush()
        chunked = b"\x78\xDA" + compressed + b"\x78\xDA" + compressed  # two chunks

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "input.luac"
            src.write_bytes(chunked)
            out = Path(td) / "out.luac"
            ok, msg = stream_inflate_deflate_container(src, out)
            self.assertTrue(ok, msg)
            self.assertTrue(out.is_file())
            recovered = out.read_bytes()
            # We inflated the payload twice; expect at least the first
            # occurrence of the Lua magic + PAYLOAD signature.
            self.assertTrue(recovered.startswith(b"\x1bLua\x53\x00"))
            self.assertIn(b"PAYLOAD", recovered)

    def test_reject_non_lua_payload(self):
        payload = b"NOT-LUA" * 100
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        compressed = co.compress(payload) + co.flush()
        chunked = b"\x78\xDA" + compressed
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "input.bin"
            src.write_bytes(chunked)
            out = Path(td) / "out.luac"
            ok, msg = stream_inflate_deflate_container(src, out)
            self.assertFalse(ok)
            self.assertIn("not Lua/LuaJIT", msg)
            self.assertFalse(out.exists())


class TestLargeInputDoesNotCrash(unittest.TestCase):
    def test_large_input_routes_to_streaming(self):
        """A 9-MiB chunked-DEFLATE input must not blow up decompile_large.

        We use a small synthetic compressed payload but pad the input
        to >8 MiB so the bridge would otherwise reject it via ART_SAFE_LIMIT.
        """
        payload = b"\x1bLua\x53\x00" + b"\x19\x93\x0d\x0a\x1a\x0a"
        co = zlib.compressobj(9, zlib.DEFLATED, -15)
        compressed = co.compress(payload) + co.flush()
        # Pad with junk to push the size above ART_SAFE_LIMIT (8 MiB).
        chunked = b"\x78\xDA" + compressed + b"\x00" * (9 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "large.luac"
            src.write_bytes(chunked)
            self.assertGreater(src.stat().st_size, 8 * 1024 * 1024)
            out_dir = Path(td) / "out"
            result = decompile_large(src, out_dir, jars_dir=None)
            # We don't require decompile success here (the payload is too
            # tiny to be a real Lua chunk) — only that it didn't crash.
            self.assertIsInstance(result, dict)
            self.assertIn("ok", result)
            self.assertIn("format", result)
            # Format is either the original chunked_deflate OR the unwrapped
            # luac_53 (after stream-inflate runs successfully).
            self.assertIn(result["format"], ("chunked_deflate", "luac_53"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
