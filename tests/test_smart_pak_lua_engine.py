from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from smart_pak_lua_engine import _probe_lua


def test_probe_lua_magic_at_offset_zero(tmp_path):
    p = tmp_path / "payload.bin"
    p.write_bytes(b"\x1bLua\x53\x00\x19" + b"\x00" * 64)
    result = _probe_lua(p)
    assert result["candidate"] is True
    assert result["kind"] == "bytecode"


def test_probe_lua_magic_inside_wrapper(tmp_path):
    p = tmp_path / "payload.dat"
    p.write_bytes(b"WRAPPER" * 20 + b"\x1bLua\x53" + b"\x00" * 64)
    result = _probe_lua(p)
    assert result["candidate"] is True
    assert result["magic_offset"] > 0


def test_probe_lua_rejects_arbitrary_binary(tmp_path):
    p = tmp_path / "texture.bin"
    p.write_bytes(bytes(range(256)) * 128)
    result = _probe_lua(p)
    assert result["candidate"] is False


def test_probe_lua_source_markers(tmp_path):
    p = tmp_path / "script.txt"
    p.write_text("local x = 1\nfunction test()\n return x\nend\n", encoding="utf-8")
    result = _probe_lua(p)
    assert result["candidate"] is True
    assert result["kind"] == "source-probe"


def test_regression_sample_fingerprint():
    manifest = ROOT / "tests/fixtures/pak_regression_manifest.json"
    data = manifest.read_text(encoding="utf-8")
    assert "game_patch_4.7.0.21752.pak" in data
    assert "e47e93bd934ec830b2b908c5806ce1779354237e1825c7b73a8c2b37d8880968" in data


def test_select_best_compression_picks_smallest_and_falls_back():
    from alvsia_core import PakCompression, CM_ZLIB, CM_NONE
    # Highly compressible payload: a real codec must beat raw.
    data = b"ALVSIA" * 4096
    result = PakCompression.select_best_compression(data)
    assert result["original_size"] == len(data)
    assert result["method"] in (CM_ZLIB, 6)  # zlib or zstd
    assert len(result["data"]) < len(data)
    assert result["saved_bytes"] == len(data) - len(result["data"])

    # Incompressible random payload: must fall back to raw (CM_NONE).
    import os
    rnd = os.urandom(2048)
    fallback = PakCompression.select_best_compression(rnd)
    assert fallback["method"] == CM_NONE
    assert fallback["data"] == rnd
    assert fallback["saved_bytes"] == 0

