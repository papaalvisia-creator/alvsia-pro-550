"""Regression tests for the offline T24 Lua 5.3 normalizer."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src" / "main" / "python"))

from lua_engine.t24 import convert_t24_to_standard, convert_t24_file  # noqa: E402


def _enc_string(value, key):
    raw = bytes(byte ^ key[i % len(key)] for i, byte in enumerate(value))
    size = len(raw) + 1
    assert size < 255
    return bytes([size]) + raw


def _t24_fixture(key):
    header = (
        b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
        + bytes([4, 8, 4, 8, 8])
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
    )
    assert len(header) == 33
    out = bytearray(header)
    out.append(0)
    out.extend(_enc_string(b"@sample.lua", key))
    out.extend(struct.pack("<ii", 0, 0))
    out.extend(bytes([0, 0, 2]))
    out.extend(struct.pack("<i", 2))
    out.extend(struct.pack("<II", 18, 38 | (2 << 23)))
    out.extend(struct.pack("<i", 1))
    out.append(4)
    out.extend(_enc_string(b"ALVSIA_T24_FIXTURE_2026", key))
    out.extend(struct.pack("<i", 0))
    out.extend(struct.pack("<i", 0))
    out.extend(struct.pack("<i", 2))
    out.extend(bytes([1, 1]))
    out.extend(struct.pack("<i", 0))
    out.extend(struct.pack("<i", 0))
    out.extend(struct.pack("<i", 0))
    return bytes(out)


class T24LuaTests(unittest.TestCase):
    def test_normalizes_opcodes_and_decrypts_strings(self):
        key = b"ALVSIA-t24-test-key"
        source = _t24_fixture(key)
        output, report = convert_t24_to_standard(source, key)
        self.assertEqual(output[:4], b"\x1bLua")
        self.assertEqual(output[4], 0x53)
        self.assertEqual(output[13], 8)
        self.assertIn(b"ALVSIA_T24_FIXTURE_2026", output)
        self.assertIn(b"@sample.lua", output)
        code_offset = 34 + (1 + len(b"@sample.lua")) + 8 + 3 + 4
        self.assertEqual(struct.unpack_from("<I", output, code_offset)[0] & 0x3F, 1)
        self.assertTrue(report["ok"] and report["strings_decoded"])
        self.assertEqual(report["format"], "T24 Lua 5.3")

    def test_structure_only_mode_keeps_encrypted_strings(self):
        key = b"ALVSIA-t24-test-key"
        source = _t24_fixture(key)
        output, report = convert_t24_to_standard(source, b"")
        encrypted = _enc_string(b"ALVSIA_T24_FIXTURE_2026", key)[1:]
        self.assertIn(encrypted, output)
        self.assertNotIn(b"ALVSIA_T24_FIXTURE_2026", output)
        self.assertTrue(report["ok"] and not report["strings_decoded"])

    def test_rejects_wrong_header_and_truncated_chunks(self):
        source = _t24_fixture(b"test-key")
        with self.assertRaisesRegex(ValueError, "header"):
            convert_t24_to_standard(b"not a lua file", b"test-key")
        with self.assertRaisesRegex(ValueError, "truncated|unexpected"):
            convert_t24_to_standard(source[:-3], b"test-key")

    def test_file_writer_preserves_original_and_writes_separate_output(self):
        key = b"ALVSIA-t24-test-key"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.luac"
            target = Path(directory) / "sample_standard.luac"
            original = _t24_fixture(key)
            source.write_bytes(original)
            report = convert_t24_file(source, target, key)
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(target.read_bytes().startswith(b"\x1bLua"))
            self.assertTrue(report["ok"] and report["output"] == str(target))


if __name__ == "__main__":
    unittest.main(verbosity=2)
