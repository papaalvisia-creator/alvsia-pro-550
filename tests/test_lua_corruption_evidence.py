"""Evidence-only handling of UTF-8 replacement markers (the Zoul.lua failure).

The real Zoul.lua sample (1,004,870 bytes, SHA-256 d129479b...ce53f) contained
159,411 occurrences of EF BF BD, i.e. U+FFFD. That proves the bytes were decoded
as UTF-8 text before reaching the decompiler. These tests assert that the engine
*reports* that evidence and refuses to fabricate a recovery, rather than
silently producing a fake Lua file.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.detector import detect_bytes


def test_detector_reports_replacement_markers_on_bytecode():
    corrupt = b"\x1bLua\x53\x00" + b"\xef\xbf\xbd" * 159 + b"tail"
    info = detect_bytes(corrupt)
    assert info.kind == "bytecode"
    # Corrupt bytecode must never be presented with high confidence.
    assert info.confidence <= 0.30
    joined = " ".join(info.notes)
    assert "utf8_replacement_markers=159" in joined
    assert "exact recovery requires the original binary" in joined


def test_detector_does_not_flag_clean_bytecode():
    clean = b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a" + b"\x00" * 40
    info = detect_bytes(clean)
    assert info.kind == "bytecode"
    assert not any("utf8_replacement" in n for n in info.notes)


def test_detector_does_not_flag_legitimate_utf8_source():
    src = 'local s = "caf\u00e9 \u2014 \u4f60\u597d"\nreturn s\n'.encode("utf-8")
    info = detect_bytes(src)
    assert info.kind == "source"
    assert not any("utf8_replacement" in n for n in info.notes)


# ---------------------------------------------------------------------------
# Root-cause regression: binary -> UTF-8 text -> CRLF normalisation.
# ---------------------------------------------------------------------------

import re
import pytest

from lua_engine.detector import (
    diagnose_text_corruption,
    restore_lua_header,
    read_lua_text_strict,
)

_LUA53_HEADER = (
    bytes.fromhex("1b4c7561530019930d0a1a0a0404040808")
    + b"\x78\x56" + b"\x00" * 6 + b"\x00" * 5 + b"\x28\x77\x40"
)


def _text_transport_damage(data: bytes) -> bytes:
    """Reproduce the exact corruption chain proven against the Zoul.lua header."""
    decoded = data.decode("utf-8", errors="replace").encode("utf-8")
    return re.sub(rb"\r\n|\r|\n", b"\r\n", decoded)


def test_damaged_header_matches_observed_zoul_prefix_byte_for_byte():
    damaged = _text_transport_damage(_LUA53_HEADER)
    # Exact prefix reported by the device build in `first_48_bytes`.
    assert damaged.hex() == (
        "1b4c7561530019efbfbd0d0a1a0d0a040404080878560000000000000000000000287740"
    )


def test_diagnose_reports_text_transport_corruption_and_lost_bytes():
    damaged = _text_transport_damage(_LUA53_HEADER)
    diag = diagnose_text_corruption(damaged)
    assert diag["verdict"] == "text_transport_corruption"
    assert diag["utf8_replacement_markers"] == 1
    assert diag["lost_bytes"] == 1
    assert diag["crlf_pairs"] >= 2
    assert "cannot be recovered" in diag["note"]


def test_diagnose_leaves_clean_bytecode_alone():
    assert diagnose_text_corruption(_LUA53_HEADER)["verdict"] == "clean"


def test_restore_lua_header_recovers_only_the_deterministic_header():
    damaged = _text_transport_damage(_LUA53_HEADER)
    restored, changed = restore_lua_header(damaged)
    assert changed >= 1
    assert restored[:17] == _LUA53_HEADER[:17]
    # The body is never fabricated: the U+FFFD marker must still be gone only
    # because it lived in the header we rebuilt.
    assert restored.startswith(b"\x1bLua\x53\x00\x19\x93\x0d\x0a\x1a\x0a")


def test_restore_lua_header_is_a_noop_on_an_intact_header():
    restored, changed = restore_lua_header(_LUA53_HEADER)
    assert changed == 0
    assert restored == _LUA53_HEADER


def test_read_lua_text_strict_refuses_bytecode(tmp_path):
    p = tmp_path / "chunk.luac"
    p.write_bytes(_LUA53_HEADER)
    with pytest.raises(ValueError, match="Lua bytecode, not source"):
        read_lua_text_strict(p)


def test_read_lua_text_strict_refuses_non_utf8_binary(tmp_path):
    p = tmp_path / "blob.bin"
    p.write_bytes(b"\x93\xfe\xff\x00\x01")
    with pytest.raises(ValueError, match="refusing"):
        read_lua_text_strict(p)


def test_read_lua_text_strict_accepts_plain_source(tmp_path):
    p = tmp_path / "ok.lua"
    p.write_text('local s = "caf\u00e9"\nreturn s\n', encoding="utf-8")
    assert "caf\u00e9" in read_lua_text_strict(p)


def test_clean_lua_source_refuses_binary_instead_of_corrupting_it(tmp_path):
    from lua_engine.engine import clean_lua_source
    src = tmp_path / "chunk.luac"
    src.write_bytes(_LUA53_HEADER)
    out = tmp_path / "out.lua"
    result = clean_lua_source(src, out)
    assert result["ok"] is False
    assert "refusing lossy text decode" in result["error"]
    # Critically: no corrupted artefact may be produced.
    assert not out.exists()
