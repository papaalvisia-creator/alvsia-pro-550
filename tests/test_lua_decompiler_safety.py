import sys
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_ROOT = ROOT / "app" / "src" / "main" / "python"
sys.path.insert(0, str(PY_ROOT))

from lua_engine.decompiler53 import Reader, decompile_file


class Lua53BoundsTests(unittest.TestCase):
    def test_reader_rejects_short_integer_with_offset(self):
        reader = Reader(b"\x01\x02")
        with self.assertRaisesRegex(ValueError, "truncated Lua chunk.*need 4 bytes, have 2"):
            reader.int_()

    def test_large_truncated_lua53_chunk_fails_without_false_success(self):
        # Reproduces the size class from the reported 5,583,230-byte input.
        # The prototype is intentionally malformed so the parser must reject it.
        header = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a\x04\x04\x04\x08\x08"
        data = header + b"\x00" * (5_583_230 - len(header))
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "large.luac"
            dst = Path(td) / "large.lua"
            src.write_bytes(data)
            result = decompile_file(src, dst)
            self.assertFalse(result["ok"])
            self.assertIn("decompile failed", result["error"])
            self.assertFalse(dst.exists())

    def test_valid_minimal_lua53_chunk_still_decompiles(self):
        # Minimal standard Lua 5.3 chunk with one RETURN instruction and _ENV.
        header = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + bytes([4, 4, 4, 8, 8])
        data = bytearray(header)
        data += struct.pack("<q", 0x5678)
        data += struct.pack("<d", 370.5)
        data += b"\x01"                  # main chunk has one upvalue
        data += b"\x00"                  # no source string
        data += struct.pack("<ii", 0, 0) # line definitions
        data += b"\x00\x01\x02"          # params, vararg, max stack
        data += struct.pack("<iI", 1, 38 | (1 << 23))  # RETURN A=0 B=1 C=0
        data += struct.pack("<i", 0)     # constants
        data += struct.pack("<i", 1) + b"\x01\x00"  # upvalue: instack, idx
        data += struct.pack("<i", 0)     # nested prototypes
        data += struct.pack("<i", 0)     # line info (signed-byte deltas)
        data += struct.pack("<i", 0)     # abslineinfo table (real Lua 5.3 debug format)
        data += struct.pack("<i", 0)     # local variables
        data += struct.pack("<i", 1) + b"\x05_ENV"   # upvalue name
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "valid.luac"
            dst = Path(td) / "valid.lua"
            src.write_bytes(data)
            result = decompile_file(src, dst)
            self.assertTrue(result["ok"], result)
            self.assertTrue(dst.is_file())
            self.assertIn("return", dst.read_text(encoding="utf-8"))

    def test_negative_instruction_count_is_rejected(self):
        # Valid Lua 5.3 header/check values followed by a negative instruction count.
        data = bytearray(b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a")
        data += bytes([4, 4, 4, 8, 8])
        data += (0x5678).to_bytes(8, "little", signed=True)
        data += struct.pack("<d", 370.5)
        data += b"\x00"                 # main upvalue count
        data += b"\x00"                 # source string absent
        data += struct.pack("<ii", 0, 0)  # line definitions
        data += b"\x00\x00\x02"         # params, vararg, max stack
        data += struct.pack("<i", -1)     # impossible instruction count
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "negative.luac"
            dst = Path(td) / "negative.lua"
            src.write_bytes(data)
            result = decompile_file(src, dst)
            self.assertFalse(result["ok"])
            self.assertIn("instruction count", result["error"])
            self.assertFalse(dst.exists())


if __name__ == "__main__":
    unittest.main()
