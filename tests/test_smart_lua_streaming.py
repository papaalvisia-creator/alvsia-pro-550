#!/usr/bin/env python3
"""Regression tests for bounded-memory authenticated ALVLUA1 protection."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "app/src/main/python"
sys.path.insert(0, str(PYTHON_ROOT))

from smart_lua_engine import protect_encrypt

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    work = root / "WORK"
    out = root / "OUT"
    work.mkdir()
    out.mkdir()
    (work / "lua_protect_key.txt").write_text("01" * 32, encoding="ascii")

    source = root / "large.lua"
    payload = (b"local value = 'ALVSIA'\n" * 100000) + b"return value\n"
    source.write_bytes(payload)

    encrypted = protect_encrypt(source, out, work, restore=False)
    assert encrypted.get("ok"), encrypted
    encrypted_path = Path(encrypted["out"])
    assert encrypted_path.read_bytes()[:7] == b"ALVLUA1"

    restored = protect_encrypt(encrypted_path, out, work, restore=True)
    assert restored.get("ok"), restored
    assert Path(restored["out"]).read_bytes() == payload

    tampered = root / "tampered.alvlua"
    corrupted = bytearray(encrypted_path.read_bytes())
    corrupted[-1] ^= 0x01
    tampered.write_bytes(corrupted)
    rejected = protect_encrypt(tampered, out, work, restore=True)
    assert not rejected.get("ok"), rejected
    assert not (out / "tampered.lua").exists()

print("SMART LUA STREAMING PROTECT: PASS (large-file round-trip and tamper rejection)")


# Smart Lua is an independent engine: an invalid optional SM4 registry must not
# block Lua decompile/protect/compile/inject routing.
import unittest
from unittest.mock import patch
import sm4_secret_registry
from smart_lua_engine import execute as execute_smart_lua

class TestSmartLuaSM4Isolation(unittest.TestCase):
    def test_invalid_sm4_registry_does_not_gate_lua_dispatch(self):
        with patch.object(sm4_secret_registry, "SM4_SECRET_NEW_EXPECTED_COUNT", 0):
            result = execute_smart_lua("unsupported-operation", None, None)
        self.assertFalse(result.get("ok"))
        self.assertIn("unsupported Smart Lua operation", result.get("error", ""))
        self.assertNotIn("SM4", result.get("error", ""))

if __name__ == "__main__":
    unittest.main()
