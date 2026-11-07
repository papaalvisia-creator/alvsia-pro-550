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
import types
import unittest
from unittest.mock import patch
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "app" / "src" / "main" / "python"
sys.path.insert(0, str(PY))

from lua_engine.streaming_decompiler import (
    preflight_magic,
    stream_inflate_deflate_container,
    stream_inflate_zlib,
    decompile_large,
    probe_lua_header,
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
            p.write_bytes(b"-- exported Lua chunk\n-- metadata\n" +
                          b"\x1bLua\x53\x00" + b"\x19\x93\x0d\x0a\x1a\x0a" +
                          b"\x00" * 32)
            self.assertEqual(preflight_magic(p), "embedded_luac_53")

    def test_comment_prefixed_luajit_magic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "prefixed.lj"
            p.write_bytes(b"-- exported LuaJIT chunk\n" + b"\x1bLJ\x02" + b"\x00" * 16)
            self.assertEqual(preflight_magic(p), "embedded_luajit")

    def test_arbitrary_binary_embedded_magic_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "wrapped.bin"
            p.write_bytes(b"BIN\x00garbage\x1bLua\x53" + b"\x00" * 32)
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


class TestVersionSpecificFallbacks(unittest.TestCase):
    def test_non_53_luac_never_uses_lua53_python_parser(self):
        class EmptyRegistry:
            def detect(self, src):
                return []

        for version in (0x51, 0x52, 0x54):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as td:
                src = Path(td) / "version.luac"
                src.write_bytes(b"\x1bLua" + bytes((version, 0)) + b"\x00" * 64)
                out = Path(td) / "out"
                with patch("lua_engine.pattern_registry.get_registry",
                           return_value=EmptyRegistry()):
                    with patch("lua_engine.streaming_decompiler.stream_decompile_lua53",
                               side_effect=AssertionError("wrong Lua version")) as parser:
                        result = decompile_large(src, out, jars_dir=None)
                self.assertFalse(result["ok"], result)
                self.assertIn("no Python decompiler", result.get("error", ""))
                parser.assert_not_called()

    def test_luajit_disassembly_is_not_reported_as_source_decompile(self):
        class EmptyRegistry:
            def detect(self, src):
                return []

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "sample.lj"
            src.write_bytes(bytes.fromhex("1b4c4a02") + bytes(20))
            out = Path(td) / "out"
            with patch("lua_engine.pattern_registry.get_registry",
                       return_value=EmptyRegistry()):
                with patch("lua_engine.streaming_decompiler.stream_decompile_luajit",
                           return_value=(True, "fixture disassembly")):
                    result = decompile_large(src, out, jars_dir=None)
            self.assertFalse(result["ok"], result)
            self.assertTrue(result["analysis_ok"], result)
            self.assertFalse(result["source_recovered"], result)
            self.assertEqual(result["artifact_kind"], "disassembly")
            self.assertTrue(result["out"].endswith(".asm.txt"))



class TestLuaCandidateDeduplication(unittest.TestCase):
    def test_candidates_with_same_prefix_but_different_payload_are_all_tried(self):
        base = b"\x1bLua\x53" + b"A" * 4091
        source = base + b"0"
        bgmi = base + b"B"
        heping = base + b"C"

        class FakeConverter:
            def __init__(self, variant="bgmi"):
                self.variant = variant

            def convert_bytes(self, _data):
                return bgmi if self.variant == "bgmi" else heping

        def accept_only_heping(candidate):
            if bytes(candidate)[-1:] != b"C":
                raise ValueError("fixture rejects this candidate")
            return object()

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "candidate.luac"
            dst = Path(td) / "candidate.lua"
            src.write_bytes(source)
            fake_private = types.SimpleNamespace(LuaOpcodeConverter=FakeConverter)
            with patch.dict(sys.modules, {"alvsia_private": fake_private}):
                with patch("lua_engine.decompiler53.load_chunk",
                           side_effect=accept_only_heping):
                    with patch("lua_engine.decompiler53.decompile_bytes",
                               return_value="return 7"):
                        with patch("lua_engine.streaming_decompiler.validate_lua_source",
                                   return_value=(True, "fixture source accepted")):
                            from lua_engine.streaming_decompiler import stream_decompile_lua53
                            ok, message = stream_decompile_lua53(src, dst)

            self.assertTrue(ok, message)
            self.assertIn("variant=heping", message)
            self.assertEqual(dst.read_text(encoding="utf-8"), "return 7")

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

    def test_embedded_78da_inside_raw_deflate_is_not_a_member_boundary(self):
        # Level-0 raw DEFLATE stores payload bytes verbatim, including this
        # marker-like pair. A parser must follow decoder EOF, not split on
        # every occurrence of 78 DA.
        payload1 = (
            b"\x1bLua\x53\x00" + b"\x19\x93\x0d\x0a\x1a\x0a"
            + b"A" * 4096 + b"\x78\xda" + b"B" * 4096
        )
        payload2 = b"SECOND_MEMBER"
        def raw_deflate(payload):
            co = zlib.compressobj(0, zlib.DEFLATED, -15)
            return co.compress(payload) + co.flush()
        first = raw_deflate(payload1)
        second = raw_deflate(payload2)
        # Real-world chunk containers may include a short separator between
        # the end of one raw stream and the next 78DA header.
        container = b"\x78\xda" + first + b"CLMM" + (b"\x0d" * 13) + b"\x78\xda" + second
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "false-marker.bin"
            dst = Path(td) / "out.luac"
            src.write_bytes(container)
            ok, msg = stream_inflate_deflate_container(src, dst)
            self.assertTrue(ok, msg)
            self.assertEqual(dst.read_bytes(), payload1 + payload2)

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




class TestStandardZlib(unittest.TestCase):
    def test_standard_zlib_levels_are_streamed(self):
        payload = b"\x1bLua\x53\x00" + b"\x19\x93\x0d\x0a\x1a\x0a" + b"LuaPayload" * 20
        for level in (0, 6, 9):
            wrapped = zlib.compress(payload, level)
            with tempfile.TemporaryDirectory() as td:
                src = Path(td) / "input.z"
                dst = Path(td) / "out.luac"
                src.write_bytes(wrapped)
                ok, msg = stream_inflate_zlib(src, dst)
                self.assertTrue(ok, msg)
                self.assertEqual(dst.read_bytes(), payload)
                self.assertEqual(preflight_magic(src), "zlib")

class TestProtectionPatternFallback(unittest.TestCase):
    def test_preflight_only_never_runs_standard_decompiler_backends(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "plain.luac"
            src.write_bytes(bytes.fromhex("1b4c75615300") + bytes(40))
            out = root / "out"
            with patch(
                "lua_engine.streaming_decompiler.stream_unluac_jar",
                side_effect=AssertionError("standard engine must be orchestrator-owned"),
            ):
                with patch(
                    "lua_engine.streaming_decompiler.stream_decompile_lua53",
                    side_effect=AssertionError("standard engine must be orchestrator-owned"),
                ):
                    result = decompile_large(src, out, preflight_only=True)
            self.assertFalse(result["ok"])
            self.assertEqual(result["mode"], "pattern_preflight")
            self.assertFalse((out / "plain_decompiled.lua").exists())

    def test_partial_or_invalid_pattern_results_do_not_stop_fallback(self):
        """Only a validated full source artifact may count as recovery."""
        calls = []

        class FakePattern:
            def __init__(self, pattern_id, confidence, outcome):
                self.id = pattern_id
                self.label = pattern_id
                self.confidence_boost = confidence
                self.outcome = outcome

            def deobfuscator(self, src, out):
                calls.append(self.id)
                if self.outcome == "partial":
                    report = out / "partial_structure.json"
                    report.write_text("{}", encoding="utf-8")
                    return {
                        "ok": True, "recovered": False, "mode": "partial_analysis",
                        "out": str(report),
                    }
                artifact = out / (self.id + ".lua")
                if self.outcome == "invalid":
                    artifact.write_text("this is not Lua source", encoding="utf-8")
                else:
                    artifact.write_text("return 42\n", encoding="utf-8")
                return {
                    "ok": True, "recovered": True, "mode": "fixture_recovery",
                    "out": str(artifact),
                }

        class FakeRegistry:
            def detect(self, src):
                return [
                    FakePattern("partial_vm_report", 0.99, "partial"),
                    FakePattern("invalid_source_claim", 0.80, "invalid"),
                    FakePattern("compatible_fallback", 0.60, "valid"),
                ]

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "protected.bin"
            src.write_bytes(b"not-a-standard-lua-header")
            out = Path(td) / "out"
            with patch("lua_engine.pattern_registry.get_registry", return_value=FakeRegistry()):
                result = decompile_large(src, out, jars_dir=None)


            self.assertTrue(result["ok"])
            self.assertEqual(result["pattern_id"], "compatible_fallback")
            self.assertEqual(calls, [
                "partial_vm_report", "invalid_source_claim", "compatible_fallback"
            ])
            self.assertEqual(
                [item["id"] for item in result["pattern_attempts"]],
                ["partial_vm_report", "invalid_source_claim", "compatible_fallback"],
            )
            self.assertFalse((out / "invalid_source_claim.lua").exists())
            self.assertTrue(Path(result["out"]).is_file())


class TestLuaHeaderDiagnostics(unittest.TestCase):
    def test_reports_bad_lua53_check_bytes_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "wrapped.luac"
            raw = (
                bytes((0x1B,)) + b"Lua\x53\x00BADBAD"
                + b"\x04\x08\x04\x08\x08"
                + b"\x78\x56\x00\x00\x00\x00\x00\x00"
                + struct.pack("<d", 370.5)
                + b"\x00" * 64
            )
            src.write_bytes(raw)
            report = probe_lua_header(src)
            self.assertEqual(report["magic_offset"], 0)
            self.assertEqual(report["version"], 0x53)
            self.assertFalse(report["luac_data_ok"])
            self.assertEqual(report["field_sizes"], [4, 8, 4, 8, 8])
            self.assertEqual(report["size"], len(raw))
            self.assertEqual(src.read_bytes(), raw)

    def test_counts_utf8_replacement_markers_without_decoding_input(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "damaged.bin"
            raw = bytes((0x1B,)) + b"Lua\x53" + bytes((0xEF, 0xBF, 0xBD)) * 3
            src.write_bytes(raw)
            report = probe_lua_header(src)
            self.assertEqual(report["utf8_replacement_markers"], 3)
            self.assertEqual(src.read_bytes(), raw)

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
