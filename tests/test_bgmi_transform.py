"""Regression tests for the BGMI Lua 5.3 structure/opcode normalizer."""
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.bgmi import is_bgmi_lua, transform_bgmi_lua
from lua_engine.decompiler53 import decompile_file


def _bgmi_string(data: bytes, key: bytes) -> bytes:
    raw = bytes(value ^ key[i % len(key)] for i, value in enumerate(data)) if key else data
    size = len(raw) + 1
    if size < 0xFF:
        return bytes([size]) + raw
    return b"\xff" + struct.pack("<I", size) + raw


def _make_bgmi_chunk(key: bytes, literal: bytes) -> bytes:
    # Lua 5.3 header with BGMI's 4-byte size_t ABI.
    header = (
        b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a"
        + bytes([4, 4, 4, 8, 8])
        + struct.pack("<q", 0x5678)
        + struct.pack("<d", 370.5)
    )
    assert len(header) == 33
    out = bytearray(header)
    out.append(0)  # main proto upvalue count
    out.extend(b"\x00")  # source name = null
    out.extend(struct.pack("<ii", 0, 0))  # line-defined and last-line-defined
    out.extend(bytes([0, 0, 2]))  # params, vararg, max stack

    # BGMI opcode 18 maps to standard Lua 5.3 LOADK (opcode 1).
    loadk = 18
    # Standard RETURN opcode 38, returning register 0.
    ret = 38 | (2 << 23)
    out.extend(struct.pack("<I", 2))
    out.extend(struct.pack("<II", loadk, ret))

    out.extend(struct.pack("<I", 1))  # constants
    out.append(4)  # TString
    out.extend(_bgmi_string(literal, key))
    out.extend(struct.pack("<I", 0))  # upvalues
    out.extend(struct.pack("<I", 0))  # child prototypes

    # BGMI line info is a stream of signed-byte deltas, followed by absolute count.
    out.extend(struct.pack("<I", 2))
    out.extend(bytes([1, 1]))
    out.extend(struct.pack("<I", 0))  # no absolute-line records
    out.extend(struct.pack("<I", 0))  # local variables
    out.extend(struct.pack("<I", 0))  # upvalue names
    return bytes(out)


def test_bgmi_detection_and_opcode_normalization():
    key = b"ALVISIA-test-key"
    literal = b"ALVISIA_BGMI_LITERAL_42"
    src = _make_bgmi_chunk(key, literal)
    assert is_bgmi_lua(src)

    normalized = transform_bgmi_lua(src, key, decrypt=True)
    assert normalized[:4] == b"\x1bLua"
    assert normalized[4] == 0x53
    assert normalized[13] == 8  # output is standard Lua 5.3 size_t ABI
    assert literal in normalized
    # First instruction was BGMI opcode 18 and must become standard LOADK 1.
    code_start = 33 + 1 + 1 + 4 + 4 + 3 + 4
    assert struct.unpack_from("<I", normalized, code_start)[0] & 0x3F == 1

    with tempfile.TemporaryDirectory() as td:
        src_path = Path(td) / "test_bgmi.luac"
        out_path = Path(td) / "test_bgmi.lua"
        src_path.write_bytes(normalized)
        result = decompile_file(src_path, out_path)
        assert result.get("ok"), result
        text = out_path.read_text(encoding="utf-8", errors="replace")
        assert "return" in text
        assert "ALVISIA_BGMI_LITERAL_42" in text


def test_structure_only_mode_preserves_encrypted_string_bytes():
    key = b"ALVISIA-test-key"
    literal = b"BGMI_STRING_SHOULD_REMAIN_ENCRYPTED"
    src = _make_bgmi_chunk(key, literal)
    normalized = transform_bgmi_lua(src, b"", decrypt=True)
    cipher = bytes(value ^ key[i % len(key)] for i, value in enumerate(literal))
    assert cipher in normalized
    assert literal not in normalized


def test_long_strings_use_standard_size_t_in_normalized_chunk():
    key = b"ALVISIA-test-key"
    literal = b"L" * 280
    src = _make_bgmi_chunk(key, literal)
    normalized = transform_bgmi_lua(src, key, decrypt=True)
    assert b"\xff" + struct.pack("<Q", len(literal) + 1) + literal in normalized
    with tempfile.TemporaryDirectory() as td:
        src_path = Path(td) / "long_bgmi.luac"
        out_path = Path(td) / "long_bgmi.lua"
        src_path.write_bytes(normalized)
        result = decompile_file(src_path, out_path)
        assert result.get("ok"), result
        assert len(out_path.read_text(encoding="utf-8", errors="replace")) > 50


def test_roundtrip_standard_to_bgmi_and_back_is_byte_exact():
    """Encrypt (standard->BGMI) then decrypt (BGMI->standard) must round-trip."""
    key = b"ALVISIA-roundtrip-key"
    literal = b"ROUNDTRIP_LITERAL_9000"
    src = _make_bgmi_chunk(key, literal)

    standard = transform_bgmi_lua(src, key, decrypt=True)
    bgmi = transform_bgmi_lua(standard, key, decrypt=False)
    restored = transform_bgmi_lua(bgmi, key, decrypt=True)

    # Header ABI flips back to the BGMI 4-byte size_t when encrypting.
    assert bgmi[12:16] == b"\x04\x04\x04\x08"
    # And the full standard chunk is reproduced byte-for-byte.
    assert restored == standard
    assert literal in restored

    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "roundtrip.lua"
        src_path = Path(td) / "roundtrip.luac"
        src_path.write_bytes(restored)
        result = decompile_file(src_path, out_path)
        assert result.get("ok"), result
        assert "ROUNDTRIP_LITERAL_9000" in out_path.read_text(encoding="utf-8", errors="replace")


def main():
    tests = (
        test_bgmi_detection_and_opcode_normalization,
        test_structure_only_mode_preserves_encrypted_string_bytes,
        test_long_strings_use_standard_size_t_in_normalized_chunk,
        test_roundtrip_standard_to_bgmi_and_back_is_byte_exact,
    )
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("BGMI Lua normalization regression: PASS (3/3)")


if __name__ == "__main__":
    main()
