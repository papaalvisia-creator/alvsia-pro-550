#!/usr/bin/env python3
"""Regression contract for the unified Smart PAK -> Lua pipeline."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from smart_pak_lua_engine import MAX_IMPORT_BYTES, _looks_like_lua


def test_limits_and_detection():
    assert MAX_IMPORT_BYTES == 5 * 1024 * 1024 * 1024
    with tempfile.TemporaryDirectory(prefix="alvsia-pak-lua-") as tmp:
        root = Path(tmp)
        source = root / "payload.lua"
        bytecode = root / "payload.luac"
        wrapped_binary = root / "payload.bin"
        source.write_text("local value = 1\nreturn value\n", encoding="utf-8")
        bytecode.write_bytes(b"\x1bLua\x53\x00\x19\x93\r\n\\x1a\n")
        wrapped_binary.write_bytes(b"WRAPPER\x00\x1bLua\x53\x00\x19\x93\r\n\\x1a\n")
        assert _looks_like_lua(source)
        assert _looks_like_lua(bytecode)
        assert _looks_like_lua(wrapped_binary)


def test_real_pak_manifest_entry():
    manifest = ROOT / "tests/fixtures/pak_regression_manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    sample = data["game_patch_4.7.0.21752.pak"]
    assert sample["size"] == 2704793
    assert sample["sha256"] == "e47e93bd934ec830b2b908c5806ce1779354237e1825c7b73a8c2b37d8880968"
    assert sample["source"] == (
        "papaalvisia-creator/kumpulan-source-tool:"
        "samples/pak/game_patch_4.7.0.21752.pak"
    )


if __name__ == "__main__":
    test_limits_and_detection()
    test_real_pak_manifest_entry()
    print("SMART PAK/LUA PIPELINE CONTRACT: PASS")
