"""Regression tests for the offline T24 Lua 5.3 normalizer."""
import struct
import sys
import tempfile
import pytest
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
    out.append(0)  # main upvalue count
    out.extend(_enc_string(b"@sample.lua", key))
    out.extend(struct.pack("<ii", 0, 0))
    out.extend(bytes([0, 0, 2]))  # params, vararg, max stack
    out.extend(struct.pack("<i", 2))  # code count
    out.extend(struct.pack("<II", 18, 38 | (2 << 23)))  # T24 LOADK, RETURN
    out.extend(struct.pack("<i", 1))  # constant count
    out.append(4)  # string constant
    out.extend(_enc_string(b"ALVSIA_T24_FIXTURE_2026", key))
    out.extend(struct.pack("<i", 0))  # upvalues
    out.extend(struct.pack("<i", 0))  # child prototypes
    out.extend(struct.pack("<i", 2))  # line-info count
    out.extend(bytes([1, 1]))
    out.extend(struct.pack("<i", 0))  # absolute line records
    out.extend(struct.pack("<i", 0))  # locals
    out.extend(struct.pack("<i", 0))  # upvalue names
    return bytes(out)


def test_t24_normalizes_opcodes_and_decrypts_strings():
    key = b"ALVSIA-t24-test-key"
    source = _t24_fixture(key)
    output, report = convert_t24_to_standard(source, key)
    assert output[:4] == b"\x1bLua"
    assert output[4] == 0x53
    assert output[13] == 8
    assert b"ALVSIA_T24_FIXTURE_2026" in output
    assert b"@sample.lua" in output
    # First instruction maps T24 opcode 18 to standard LOADK opcode 1.
    code_offset = 34 + (1 + len(b"@sample.lua")) + 8 + 3 + 4
    assert struct.unpack_from("<I", output, code_offset)[0] & 0x3F == 1
    assert report["ok"] and report["strings_decoded"]
    assert report["format"] == "T24 Lua 5.3"


def test_t24_structure_only_mode_keeps_encrypted_strings():
    key = b"ALVSIA-t24-test-key"
    source = _t24_fixture(key)
    output, report = convert_t24_to_standard(source, b"")
    encrypted = _enc_string(b"ALVSIA_T24_FIXTURE_2026", key)[1:]
    assert encrypted in output
    assert b"ALVSIA_T24_FIXTURE_2026" not in output
    assert report["ok"] and not report["strings_decoded"]


def test_t24_rejects_wrong_header_and_truncated_chunks():
    source = _t24_fixture(b"test-key")
    with pytest.raises(ValueError, match="header"):
        convert_t24_to_standard(b"not a lua file", b"test-key")
    with pytest.raises(ValueError, match="truncated|unexpected"):
        convert_t24_to_standard(source[:-3], b"test-key")


def test_t24_file_writer_preserves_original_and_writes_separate_output():
    key = b"ALVSIA-t24-test-key"
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "sample.luac"
        target = Path(directory) / "sample_standard.luac"
        original = _t24_fixture(key)
        source.write_bytes(original)
        report = convert_t24_file(source, target, key)
        assert source.read_bytes() == original
        assert target.read_bytes().startswith(b"\x1bLua")
        assert report["ok"] and report["output"] == str(target)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
