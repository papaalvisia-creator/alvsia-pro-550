"""Executable regression tests for the four public Smart Lua engines."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "app/src/main/python/smart_lua_engine.py"
SPEC = importlib.util.spec_from_file_location("smart_lua_engine", ENGINE_PATH)
smart = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smart)


class SmartLuaEngineTests(unittest.TestCase):
    def test_detects_lua_53_bytecode_without_reading_whole_file(self):
        with tempfile.TemporaryDirectory() as td:
            sample = Path(td) / "sample.luac"
            sample.write_bytes(b"\\x1bLua\\x53" + b"\\x00" * 128)
            result = smart.detect(sample)
            self.assertEqual(result["kind"], "lua53")
            self.assertIn("lua53", result["routes"])
            self.assertEqual(len(result["sha256"]), 64)

    def test_detects_luajit_bytecode(self):
        with tempfile.TemporaryDirectory() as td:
            sample = Path(td) / "sample.lj"
            sample.write_bytes(b"\\x1bLJ" + b"\\x00" * 32)
            self.assertEqual(smart.detect(sample)["kind"], "luajit")

    def test_detects_source_and_unknown_input(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "sample.lua"
            source.write_text("local value = 7\\nreturn value\\n", encoding="utf-8")
            self.assertEqual(smart.detect(source)["kind"], "lua-source")
            binary = Path(td) / "unknown.bin"
            binary.write_bytes(bytes(range(1, 255)))
            self.assertEqual(smart.detect(binary)["kind"], "unknown-binary")

    def test_missing_input_fails_closed(self):
        result = smart.detect(Path("/definitely/not/a/real/alvsia-file.lua"))
        self.assertEqual(result["kind"], "missing")
        self.assertFalse(result["routes"])

    def test_output_validation_rejects_missing_and_empty_files(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.lua"
            self.assertFalse(smart._validate_output(missing)["ok"])
            missing.write_bytes(b"")
            self.assertFalse(smart._validate_output(missing)["ok"])
            missing.write_bytes(b"return true")
            self.assertTrue(smart._validate_output(missing, (".lua",))["ok"])
            self.assertFalse(smart._validate_output(missing, (".luac",))["ok"])

    def test_public_engine_names_are_exactly_four(self):
        self.assertEqual(
            list(smart.ENGINE_NAMES.values()),
            [
                "SMART LUA DECOMPILER",
                "SMART LUA PROTECT",
                "SMART LUA COMPILER / RECOMPILER",
                "SMART LUA INJECT",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
