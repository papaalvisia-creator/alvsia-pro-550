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
