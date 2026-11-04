"""Evidence-only handling of UTF-8 replacement markers (the Zoul.lua failure).

The real Zoul.lua sample (1,004,870 bytes, SHA-256 d129479b...ce53f) contained
159,411 occurrences of EF BF BD, i.e. U+FFFD. That proves the bytes were decoded
as UTF-8 text before reaching the decompiler. These tests assert that the engine
*reports* that evidence and refuses to fabricate a recovery, rather than
silently producing a fake Lua file.

They also pin the proven root cause: decoding a binary as UTF-8 with
``errors="replace"`` and normalising line endings to CRLF reproduces the exact
damaged header observed on the device.

Standard library only: CI runs these under ``unittest`` discovery.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.detector import (  # noqa: E402
    detect_bytes,
    diagnose_text_corruption,
    read_lua_text_strict,
    restore_lua_header,
)

_LUA53_HEADER = (
    bytes.fromhex("1b4c7561530019930d0a1a0a0404040808")
    + b"\x78\x56" + b"\x00" * 6 + b"\x00" * 5 + b"\x28\x77\x40"
)

# Exact prefix reported by the device build in `first_48_bytes`.
_OBSERVED_DAMAGED_PREFIX = (
    "1b4c7561530019efbfbd0d0a1a0d0a04040408087856"
    "0000000000000000000000287740"
)


def _text_transport_damage(data: bytes) -> bytes:
    """Reproduce the exact corruption chain proven against the Zoul.lua header."""
    decoded = data.decode("utf-8", errors="replace").encode("utf-8")
    return re.sub(rb"\r\n|\r|\n", b"\r\n", decoded)


class DetectorEvidenceTests(unittest.TestCase):
    def test_detector_reports_replacement_markers_on_bytecode(self):
        corrupt = b"\x1bLua\x53\x00" + b"\xef\xbf\xbd" * 159 + b"tail"
        info = detect_bytes(corrupt)
        self.assertEqual(info.kind, "bytecode")
        # Corrupt bytecode must never be presented with high confidence.
        self.assertLessEqual(info.confidence, 0.30)
        joined = " ".join(info.notes)
        self.assertIn("utf8_replacement_markers=159", joined)
        self.assertIn("exact recovery requires the original binary", joined)

    def test_detector_does_not_flag_clean_bytecode(self):
        clean = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + b"\x00" * 40
        info = detect_bytes(clean)
        self.assertEqual(info.kind, "bytecode")
        self.assertFalse(any("utf8_replacement" in n for n in info.notes))

    def test_detector_does_not_flag_legitimate_utf8_source(self):
        src = 'local s = "caf\u00e9 \u2014 \u4f60\u597d"\nreturn s\n'.encode("utf-8")
        info = detect_bytes(src)
        self.assertEqual(info.kind, "source")
        self.assertFalse(any("utf8_replacement" in n for n in info.notes))


class TextTransportRootCauseTests(unittest.TestCase):
    def test_damaged_header_matches_observed_zoul_prefix_byte_for_byte(self):
        damaged = _text_transport_damage(_LUA53_HEADER)
        self.assertEqual(damaged.hex(), _OBSERVED_DAMAGED_PREFIX)

    def test_diagnose_reports_text_transport_corruption_and_lost_bytes(self):
        damaged = _text_transport_damage(_LUA53_HEADER)
        diag = diagnose_text_corruption(damaged)
        self.assertEqual(diag["verdict"], "text_transport_corruption")
        self.assertEqual(diag["utf8_replacement_markers"], 1)
        self.assertEqual(diag["lost_bytes"], 1)
        self.assertGreaterEqual(diag["crlf_pairs"], 2)
        self.assertIn("cannot be recovered", diag["note"])

    def test_diagnose_leaves_clean_bytecode_alone(self):
        self.assertEqual(diagnose_text_corruption(_LUA53_HEADER)["verdict"], "clean")

    def test_restore_lua_header_recovers_only_the_deterministic_header(self):
        damaged = _text_transport_damage(_LUA53_HEADER)
        restored, changed = restore_lua_header(damaged)
        self.assertGreaterEqual(changed, 1)
        self.assertEqual(restored[:17], _LUA53_HEADER[:17])
        self.assertTrue(restored.startswith(b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"))

    def test_restore_lua_header_is_a_noop_on_an_intact_header(self):
        restored, changed = restore_lua_header(_LUA53_HEADER)
        self.assertEqual(changed, 0)
        self.assertEqual(restored, _LUA53_HEADER)


class StrictTextReadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_lua_text_strict_refuses_bytecode(self):
        p = self.tmp / "chunk.luac"
        p.write_bytes(_LUA53_HEADER)
        with self.assertRaisesRegex(ValueError, "Lua bytecode, not source"):
            read_lua_text_strict(p)

    def test_read_lua_text_strict_refuses_non_utf8_binary(self):
        p = self.tmp / "blob.bin"
        p.write_bytes(b"\x93\xfe\xff\x00\x01")
        with self.assertRaisesRegex(ValueError, "refusing"):
            read_lua_text_strict(p)

    def test_read_lua_text_strict_accepts_plain_source(self):
        p = self.tmp / "ok.lua"
        p.write_text('local s = "caf\u00e9"\nreturn s\n', encoding="utf-8")
        self.assertIn("caf\u00e9", read_lua_text_strict(p))

    def test_clean_lua_source_refuses_binary_instead_of_corrupting_it(self):
        from lua_engine.engine import clean_lua_source
        src = self.tmp / "chunk.luac"
        src.write_bytes(_LUA53_HEADER)
        out = self.tmp / "out.lua"
        result = clean_lua_source(src, out)
        self.assertFalse(result["ok"])
        self.assertIn("refusing lossy text decode", result["error"])
        # Critically: no corrupted artefact may be produced.
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
