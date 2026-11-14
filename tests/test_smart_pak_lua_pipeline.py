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
        lua_chunk = bytes([0x1b]) + b"Lua" + bytes([0x53, 0x00, 0x19, 0x93, 13, 10, 0x1a, 10])
        bytecode.write_bytes(lua_chunk)
        wrapped_binary.write_bytes(b"WRAPPER" + bytes([0]) + lua_chunk)
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
    sample_zstd = data["game_patch_4.7.0.21756.pak"]
    assert sample_zstd["size"] == 713299
    assert sample_zstd["sha256"] == "dc6a229d388889b599e154a1354eb48a0ecd0c2e762f68a4837be598f70bd578"
    assert sample_zstd["source"] == (
        "papaalvisia-creator/kumpulan-source-tool:"
        "samples/pak/game_patch_4.7.0.21756.pak"
    )



def test_smart_pak_lua_processes_written_entries_when_other_entries_are_blocked(
    tmp_path, monkeypatch
):
    import smart_archive_lua_engine
    import smart_pak_lua_engine

    source = tmp_path / "partial.pak"
    source.write_bytes(b"pak")
    output = tmp_path / "out"
    captured = {}

    def fake_archive_execute(path, out, work_dir=None, archive_kind="auto",
                             deep_lua=True):
        captured.update({
            "path": Path(path),
            "archive_kind": archive_kind,
            "deep_lua": deep_lua,
        })
        return {
            "ok": True,
            "engine": "SMART ARCHIVE/LUA",
            "extraction_complete": False,
            "extract": {
                "ok": False,
                "stats": {"expected_files": 2, "written_files": 1,
                          "skipped_files": 1, "on_disk": 1},
            },
            "blocked_entries": [{"path": "protected.uasset",
                                 "classification": "BLOCKED_AUTHORIZATION"}],
            "recovery": {"attempted": 1, "success": 0, "partial": 1, "failed": 0},
            "partials": [{"path": "available.luac",
                          "status": "PARTIAL_RECOVERY"}],
            "out": str(out),
        }

    monkeypatch.setattr(smart_archive_lua_engine, "execute", fake_archive_execute)
    result = smart_pak_lua_engine.execute(source, output)

    assert captured["path"] == source
    assert captured["archive_kind"] == "pak"
    assert captured["deep_lua"] is True
    assert result["ok"] is True
    assert result["final_status"] == "PARTIAL"
    assert result["extraction_complete"] is False
    assert result["decompile"]["partial"] == 1
    assert result["blocked_entries"][0]["classification"] == "BLOCKED_AUTHORIZATION"
    assert Path(result["report"]).is_file()


def test_smart_pak_lua_reports_success_only_when_extraction_and_recovery_are_complete(
    tmp_path, monkeypatch
):
    import smart_archive_lua_engine
    import smart_pak_lua_engine

    source = tmp_path / "complete.pak"
    source.write_bytes(b"pak")
    output = tmp_path / "out"

    monkeypatch.setattr(
        smart_archive_lua_engine,
        "execute",
        lambda *args, **kwargs: {
            "ok": True,
            "extraction_complete": True,
            "recovery": {"attempted": 1, "success": 1, "partial": 0, "failed": 0},
            "out": str(output),
        },
    )
    result = smart_pak_lua_engine.execute(source, output)
    assert result["ok"] is True
    assert result["final_status"] == "SUCCESS"
    assert result["decompile"]["success"] == 1


if __name__ == "__main__":
    test_limits_and_detection()
    test_real_pak_manifest_entry()
    print("SMART PAK/LUA PIPELINE CONTRACT: PASS")


