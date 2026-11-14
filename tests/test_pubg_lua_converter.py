from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"))

from alvsia_features import PUBGLuaConverter, run_pubg_lua_decrypt
from alvsia_private import ALVSIA_BGMI_XOR_KEY, LuaOpcodeConverter
from lua_engine.bgmi import transform_bgmi_lua
from lua_engine.decompiler53 import load_chunk


def _standard_chunk_with_binary_string(line_numbers: tuple[int, ...] = ()) -> bytes:
    header = (
        b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
        + b"\x04\x08\x04\x08\x08"
        + bytes.fromhex("7856000000000000")
        + bytes.fromhex("0000000000287740")
    )
    return (
        header
        + struct.pack("<B", 0)
        + struct.pack("<B", 0)
        + struct.pack("<ii", 0, 0)
        + struct.pack("<BBB", 0, 0, 2)
        + struct.pack("<I", max(1, len(line_numbers)))
        + b"".join(struct.pack("<I", 38) for _ in range(max(1, len(line_numbers))))
        + struct.pack("<I", 1)
        + struct.pack("<BB", 4, 4)
        + b"\xff\xfeA"
        + struct.pack("<I", 0)  # upvalue count
        + struct.pack("<I", 0)  # nested prototype count
        + struct.pack("<I", len(line_numbers))
        + b"".join(struct.pack("<i", line) for line in line_numbers)
        + struct.pack("<I", 0)  # local variable count
        + struct.pack("<I", 0)  # upvalue-name count
    )


def test_pubg_converter_uses_structured_bgmi_parser_and_preserves_binary_strings():
    standard = _standard_chunk_with_binary_string()
    encrypted_bgmi = transform_bgmi_lua(
        standard, key=ALVSIA_BGMI_XOR_KEY, decrypt=False
    )
    converted = PUBGLuaConverter().convert_bytes(encrypted_bgmi)
    expected = bytearray(standard)
    expected[13] = 8  # emit the standard ARM64 Lua 5.3 size_t layout
    assert converted == bytes(expected)


def test_pubg_converter_reconstructs_signed_line_deltas_and_absolute_checkpoints():
    expected_lines = (300, 301, 500, 499)
    standard = _standard_chunk_with_binary_string(expected_lines)
    encrypted_bgmi = transform_bgmi_lua(
        standard, key=ALVSIA_BGMI_XOR_KEY, decrypt=False
    )
    converted = PUBGLuaConverter().convert_bytes(encrypted_bgmi)
    proto = load_chunk(converted)
    assert proto.lineinfo == list(expected_lines)
    assert converted[13] == 8


def test_shared_opcode_converter_rejects_oversized_file_before_read(tmp_path):
    converter = LuaOpcodeConverter("bgmi")
    source = tmp_path / "too-large.bgmi"
    with source.open("wb") as handle:
        handle.truncate(converter.MAX_INPUT_BYTES + 1)
    from unittest.mock import patch
    with patch.object(Path, "read_bytes", side_effect=AssertionError("must reject before buffering")):
        with pytest.raises(ValueError, match="32 MiB safety cap"):
            converter.convert_file(str(source))


def test_pubg_converter_rejects_unknown_variant_instead_of_bytewise_corruption():
    standard = _standard_chunk_with_binary_string()
    with pytest.raises(ValueError, match="unsupported variant field sizes"):
        PUBGLuaConverter().convert_bytes(standard)


def test_pubg_converter_enforces_file_size_cap_before_reading(tmp_path):
    converter = PUBGLuaConverter()
    source = tmp_path / "oversized.luac"
    with source.open("wb") as handle:
        handle.truncate(converter.MAX_INPUT_BYTES + 1)
    with pytest.raises(ValueError, match="32 MiB safety cap"):
        converter.convert_file(str(source))



def test_manual_bgmi_transform_enforces_size_cap_before_buffering(tmp_path):
    source = tmp_path / "oversized-bgmi.luac"
    with source.open("wb") as handle:
        handle.truncate(32 * 1024 * 1024 + 1)
    result = run_pubg_lua_decrypt(
        source, tmp_path / "out", key_hex="0011223344556677"
    )
    assert result["ok"] is False
    assert "32 MiB safety cap" in result["error"]
