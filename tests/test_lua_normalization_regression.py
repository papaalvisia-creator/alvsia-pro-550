import tempfile
import unittest
import zlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app/src/main/python"))

from lua_engine.detector import detect_lua
from lua_engine.engine import _normalized_input
from lua_engine.container import unwrap_lua_container


class LuaNormalizationRegression(unittest.TestCase):
    def test_comment_prefixed_lua53_is_normalized_without_mutating_input(self):
        payload = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + bytes(48)
        original = b"-- exporter banner\n-- metadata\n" + payload
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "zoul_like.lua"
            src.write_bytes(original)
            info = detect_lua(src)
            self.assertEqual(info.format, "luac")
            self.assertTrue(any(n.startswith("comment_prefix_offset=") for n in info.notes))
            normalized, container = _normalized_input(src, root / "out")
            self.assertEqual(normalized.read_bytes(), payload)
            self.assertEqual(src.read_bytes(), original)
            self.assertEqual(container.format, "comment-prefix")

    def test_standard_zlib_levels_are_normalized(self):
        payload = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + bytes(48)
        for level in (0, 1, 6, 9):
            with self.subTest(level=level), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                src = root / "wrapped.bin"
                src.write_bytes(zlib.compress(payload, level))
                normalized, container = _normalized_input(src, root / "out")
                self.assertEqual(normalized.read_bytes(), payload)
                self.assertEqual(container.format, "zlib")
                self.assertEqual(src.read_bytes(), zlib.compress(payload, level))

    def test_zlib_wrapped_comment_prefixed_lua_is_normalized(self):
        payload = b"-- exported by tool\n#!/usr/bin/env lua\n" + (
            b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + bytes(48)
        )
        wrapped = zlib.compress(payload, 6)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "banner_wrapped.lua"
            src.write_bytes(wrapped)
            normalized, container = _normalized_input(src, root / "out")
            expected = payload[payload.index(b"\x1bLua"):]
            self.assertEqual(normalized.read_bytes(), expected)
            self.assertEqual(src.read_bytes(), wrapped)
            self.assertEqual(container.format, "zlib")

    def test_arbitrary_binary_magic_is_not_stripped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "wrapped.bin"
            src.write_bytes(b"BIN\x00garbage\x1bLua\x53" + bytes(32))
            normalized, container = _normalized_input(src, root / "out")
            self.assertEqual(normalized, src)
            self.assertIsNone(container)


class ChunkedLuaContainerRegression(unittest.TestCase):
    @staticmethod
    def raw_deflate(payload, level=0):
        compressor = zlib.compressobj(level, zlib.DEFLATED, -15)
        return compressor.compress(payload) + compressor.flush()

    def test_realistic_members_use_decoder_eof_not_embedded_78da_markers(self):
        # Mirrors the real container layout: each raw stream is preceded by
        # 78 DA and separated by CLMM + 13 CR bytes. The second compressed
        # member itself contains 78 DA in its uncompressed data.
        first_payload = (
            b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
            + b"A" * 65536
        )
        second_payload = b"B" * 50000 + b"\x78\xda" + b"C" * 50000
        container = (
            b"\x78\xda" + self.raw_deflate(first_payload)
            + b"CLMM" + b"\x0d" * 13
            + b"\x78\xda" + self.raw_deflate(second_payload)
        )
        payload, info = unwrap_lua_container(container)
        self.assertEqual(payload, first_payload + second_payload)
        self.assertEqual(info.format, "chunked-raw-deflate")
        self.assertEqual(info.chunks, 2)
        self.assertIn("CLMM/padding separators detected", info.notes)

    def test_invalid_78da_candidate_before_real_member_is_skipped(self):
        payload = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + b"payload" * 64
        container = (
            b"\x78\xda\xff\xffnot-a-deflate-member"
            + b"\x78\xda" + self.raw_deflate(payload)
        )
        recovered, info = unwrap_lua_container(container)
        self.assertEqual(recovered, payload)
        self.assertEqual(info.chunks, 1)
        self.assertTrue(any("skipped invalid 78da candidates=" in n for n in info.notes))

    def test_output_limit_is_enforced_during_inflate(self):
        payload = b"\x1bLua\x53\x00" + b"A" * 10000
        container = b"\x78\xda" + self.raw_deflate(payload)
        with self.assertRaisesRegex(ValueError, "output limit"):
            unwrap_lua_container(container, max_output=1024)


if __name__ == "__main__":
    unittest.main()
