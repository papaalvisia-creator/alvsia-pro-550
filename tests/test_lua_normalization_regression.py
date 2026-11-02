import tempfile
import unittest
import zlib
from pathlib import Path

from lua_engine.detector import detect_lua
from lua_engine.engine import _normalized_input


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

    def test_arbitrary_binary_magic_is_not_stripped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "wrapped.bin"
            src.write_bytes(b"BIN\x00garbage\x1bLua\x53" + bytes(32))
            normalized, container = _normalized_input(src, root / "out")
            self.assertEqual(normalized, src)
            self.assertIsNone(container)


if __name__ == "__main__":
    unittest.main()
