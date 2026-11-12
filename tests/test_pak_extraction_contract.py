#!/usr/bin/env python3
"""Regression tests for truthful Tencent PAK extraction and unknown-size ZSTD frames."""
import sys
from pathlib import Path, PurePath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

import alvsia_core as core


def _fake_pak(tmp_path, monkeypatch, writer):
    pak = object.__new__(core.TencentPakFile)
    pak._mount_point = PurePath()
    pak._index = {
        PurePath("Game/Assets"): {
            "one.bin": SimpleNamespace(uncompressed_size=3),
            "two.bin": SimpleNamespace(uncompressed_size=4),
        }
    }
    pak._index_parse_stats = {"file_entries": 2, "loaded_directories": 1}
    pak._write_to_disk = writer
    monkeypatch.setattr(core, "BASE_DIR", tmp_path / "debug")
    return pak


def test_dump_reports_every_successful_file(tmp_path, monkeypatch):
    def writer(target, entry):
        Path(target).write_bytes(b"x" * entry.uncompressed_size)

    pak = _fake_pak(tmp_path, monkeypatch, writer)
    stats = pak.dump(tmp_path / "out")

    assert stats["ok"] is True
    assert stats["expected_files"] == 2
    assert stats["written_files"] == 2
    assert stats["skipped_files"] == 0
    assert stats["written_bytes"] == 7
    assert len(list((tmp_path / "out").rglob("*.*"))) == 2


def test_dump_counts_unexpected_decompression_errors(tmp_path, monkeypatch):
    def writer(target, entry):
        if Path(target).name == "one.bin":
            Path(target).write_bytes(b"abc")
            return
        raise RuntimeError("error determining content size from frame header")

    pak = _fake_pak(tmp_path, monkeypatch, writer)
    stats = pak.dump(tmp_path / "out")

    assert stats["ok"] is False
    assert stats["expected_files"] == 2
    assert stats["written_files"] == 1
    assert stats["skipped_files"] == 1
    assert "content size" in stats["failures"][0]["error"]


def test_run_pak_unpack_rejects_empty_index(tmp_path, monkeypatch):
    class EmptyPak:
        def __init__(self, _path):
            pass

        def dump(self, _out):
            return {
                "ok": False,
                "expected_files": 0,
                "written_files": 0,
                "skipped_files": 0,
            }

    monkeypatch.setattr(core, "_alvsia_require_operation", lambda _ops: None)
    monkeypatch.setattr(core, "TencentPakFile", EmptyPak)
    result = core.run_pak_unpack(tmp_path / "sample.pak", tmp_path / "out")

    assert result["ok"] is False
    assert "no extractable file entries" in result["error"]


def test_zstd_frame_without_content_size_is_supported():
    zstandard = pytest.importorskip("zstandard")
    payload = (b"ALVSIA-Pak-ZSTD-unknown-content-size-" * 4096) + b"end"
    frame = zstandard.ZstdCompressor(write_content_size=False).compress(payload)

    decoded = core.PakCompression.decompress_block(
        frame, None, core.CM_ZSTD, max_output_size=len(payload)
    )

    assert decoded == payload


def test_zstd_unknown_content_size_respects_output_limit():
    zstandard = pytest.importorskip("zstandard")
    payload = b"A" * (128 * 1024)
    frame = zstandard.ZstdCompressor(write_content_size=False).compress(payload)

    with pytest.raises(Exception):
        core.PakCompression.decompress_block(
            frame, None, core.CM_ZSTD, max_output_size=1024
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_pak_writer_ignores_predictable_temp_symlink(tmp_path):
    pak = object.__new__(core.TencentPakFile)
    pak._file_content = memoryview(b"new")
    target = tmp_path / "inside.bin"
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"must-remain-unchanged")
    predictable = Path(str(target) + ".alvsia-tmp")
    predictable.symlink_to(outside)
    entry = SimpleNamespace(
        encryption_method=0,
        compression_method=core.CM_NONE,
        offset=0,
        size=3,
        encrypted=False,
        uncompressed_size=3,
    )

    core.TencentPakFile._write_to_disk(pak, target, entry)

    assert target.read_bytes() == b"new"
    assert outside.read_bytes() == b"must-remain-unchanged"
    assert predictable.is_symlink()


def test_legacy_extract_all_does_not_report_partial_success(tmp_path, monkeypatch):
    class LegacyPak:
        _index = {PurePath("Game"): {"one.bin": object(), "two.bin": object()}}
        def __init__(self, _path):
            pass
        def extract_all(self, out):
            Path(out, "one.bin").write_bytes(b"one")

    monkeypatch.setattr(core, "_alvsia_require_operation", lambda _ops: None)
    monkeypatch.setattr(core, "TencentPakFile", LegacyPak)
    result = core.run_pak_unpack(tmp_path / "sample.pak", tmp_path / "out")
    assert result["ok"] is False
    assert "incomplete legacy PAK extraction" in result["error"]


def test_legacy_manual_extract_does_not_report_partial_success(tmp_path, monkeypatch):
    class LegacyPak:
        _index = {PurePath("Game"): {"one.bin": object(), "two.bin": object()}}
        def __init__(self, _path):
            pass
        def _write_to_disk(self, target, _entry):
            if Path(target).name == "two.bin":
                raise OSError("simulated write failure")
            Path(target).write_bytes(b"one")

    monkeypatch.setattr(core, "_alvsia_require_operation", lambda _ops: None)
    monkeypatch.setattr(core, "TencentPakFile", LegacyPak)
    result = core.run_pak_unpack(tmp_path / "sample.pak", tmp_path / "out")
    assert result["ok"] is False
    assert "incomplete manual PAK extraction" in result["error"]
    assert result["failures"][0]["path"].endswith("two.bin")
