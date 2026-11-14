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
    # A decompression error is a genuine failure, not a safety skip.
    assert stats["failed_files"] == 1
    assert stats["skipped_files"] == 0
    assert stats["blocked_files"] == 0
    assert "content size" in stats["failures"][0]["error"]


def test_dump_accepts_nested_entry_names_and_keeps_them_inside_root(tmp_path, monkeypatch):
    pak = object.__new__(core.TencentPakFile)
    pak._mount_point = PurePath()
    pak._index = {
        PurePath("Game"): {
            "Assets/Lua/BRPlayerCharacterBase.lua": SimpleNamespace(uncompressed_size=5),
        }
    }
    pak._index_parse_stats = {"file_entries": 1, "loaded_directories": 1}

    def writer(target, entry):
        Path(target).write_bytes(b"hello")

    pak._write_to_disk = writer
    monkeypatch.setattr(core, "BASE_DIR", tmp_path / "debug")
    stats = pak.dump(tmp_path / "out")

    assert stats["ok"] is True
    assert stats["written_files"] == 1
    assert (tmp_path / "out" / "Game" / "Assets" / "Lua" / "BRPlayerCharacterBase.lua").read_bytes() == b"hello"



def test_dump_accepts_root_level_entry(tmp_path, monkeypatch):
    pak = object.__new__(core.TencentPakFile)
    pak._mount_point = PurePath()
    pak._index = {
        PurePath(): {
            "root.bin": SimpleNamespace(uncompressed_size=4),
        }
    }
    pak._index_parse_stats = {"file_entries": 1, "loaded_directories": 1}
    pak._write_to_disk = lambda target, entry: Path(target).write_bytes(b"root")
    monkeypatch.setattr(core, "BASE_DIR", tmp_path / "debug")

    stats = pak.dump(tmp_path / "out")

    assert stats["ok"] is True
    assert stats["written_files"] == 1
    assert (tmp_path / "out" / "root.bin").read_bytes() == b"root"

def test_dump_rejects_nested_entry_path_escape(tmp_path, monkeypatch):
    pak = object.__new__(core.TencentPakFile)
    pak._mount_point = PurePath()
    pak._index = {
        PurePath("Game"): {
            "../outside.bin": SimpleNamespace(uncompressed_size=3),
        }
    }
    pak._index_parse_stats = {"file_entries": 1, "loaded_directories": 1}
    pak._write_to_disk = lambda target, entry: Path(target).write_bytes(b"bad")
    monkeypatch.setattr(core, "BASE_DIR", tmp_path / "debug")

    stats = pak.dump(tmp_path / "out")

    assert stats["ok"] is False
    assert stats["written_files"] == 0
    assert stats["skipped_files"] == 1
    assert not (tmp_path / "outside.bin").exists()

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
        compressed_blocks=[],
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


def test_dump_accounting_invariant_holds_on_mixed_outcomes(tmp_path, monkeypatch):
    """expected_entries == written + failed + blocked + skipped, always."""
    pak = object.__new__(core.TencentPakFile)
    pak._mount_point = PurePath()
    pak._index = {
        PurePath("Game"): {
            "ok.bin": SimpleNamespace(uncompressed_size=3),
            "blocked.bin": SimpleNamespace(uncompressed_size=3),
            "broken.bin": SimpleNamespace(uncompressed_size=3),
            "../escape.bin": SimpleNamespace(uncompressed_size=3),
        }
    }
    pak._index_parse_stats = {"file_entries": 4, "loaded_directories": 1}

    def writer(target, entry):
        name = Path(target).name
        if name == "ok.bin":
            Path(target).write_bytes(b"abc")
            return
        if name == "blocked.bin":
            raise core._sm4_material.Sm4MaterialUnavailable(
                "SM4 candidate material is not authorized/supplied"
            )
        raise RuntimeError("simulated decompression failure")

    pak._write_to_disk = writer
    monkeypatch.setattr(core, "BASE_DIR", tmp_path / "debug")
    stats = pak.dump(tmp_path / "out")

    assert stats["expected_entries"] == 4
    assert stats["written_files"] == 1
    assert stats["blocked_files"] == 1
    assert stats["failed_files"] == 1
    assert stats["skipped_files"] == 1  # the ../escape.bin safety skip
    assert stats["accounted_entries"] == 4
    assert stats["accounting_ok"] is True
    # A safety skip and a real failure keep ok=False.
    assert stats["ok"] is False
    # Blocked entries are recorded individually with an honest reason.
    assert stats["blocked_entries"] == [
        {"path": "Game/blocked.bin", "reason": "sm4_material_unavailable"}
    ]


def test_dump_blocked_only_is_ok_and_truthful(tmp_path, monkeypatch):
    """All-blocked (SM4 unavailable) is an honest BLOCKED outcome, not failure."""
    pak = object.__new__(core.TencentPakFile)
    pak._mount_point = PurePath()
    pak._index = {
        PurePath("Config"): {
            "a.ini": SimpleNamespace(uncompressed_size=3),
            "b.ini": SimpleNamespace(uncompressed_size=3),
        }
    }
    pak._index_parse_stats = {"file_entries": 2, "loaded_directories": 1}

    def writer(target, entry):
        raise core._sm4_material.Sm4MaterialUnavailable(
            "SM4 candidate material is not authorized/supplied"
        )

    pak._write_to_disk = writer
    monkeypatch.setattr(core, "BASE_DIR", tmp_path / "debug")
    stats = pak.dump(tmp_path / "out")

    assert stats["expected_entries"] == 2
    assert stats["written_files"] == 0
    assert stats["blocked_files"] == 2
    assert stats["failed_files"] == 0
    assert stats["skipped_files"] == 0
    assert stats["accounting_ok"] is True
    assert stats["ok"] is True  # blocked is expected when material is withheld
    assert len(stats["blocked_entries"]) == 2


def test_commit_tmp_rejects_corrupted_entry_hash(tmp_path):
    """A tampered entry (matches neither plaintext nor raw SHA-1) fails closed."""
    import hashlib
    pak = object.__new__(core.TencentPakFile)
    pak._file_content = memoryview(b"correct-plaintext")
    # content_hash matches neither the written file nor the raw stored span.
    wrong_hash = hashlib.sha1(b"something-else-entirely").digest()
    entry = SimpleNamespace(
        encryption_method=0,
        compression_method=core.CM_NONE,
        offset=0,
        size=len(b"correct-plaintext"),
        encrypted=False,
        uncompressed_size=len(b"correct-plaintext"),
        compressed_blocks=[],
        content_hash=wrong_hash,
    )
    tmp = tmp_path / "candidate.bin"
    tmp.write_bytes(b"correct-plaintext")
    try:
        pak._commit_tmp(tmp, tmp_path / "final.bin", entry)
    except ValueError as exc:
        assert "SHA-1 mismatch" in str(exc)
    else:
        raise AssertionError("corrupted entry hash was accepted")


def test_commit_tmp_accepts_plaintext_or_raw_hash(tmp_path):
    """Either plaintext-SHA1 or raw-SHA1 semantics are accepted; size enforced."""
    import hashlib
    payload = b"ALVSIA-integrity-payload"
    pak = object.__new__(core.TencentPakFile)
    pak._file_content = memoryview(payload)
    base = dict(
        encryption_method=0, compression_method=core.CM_NONE, offset=0,
        size=len(payload), encrypted=False, uncompressed_size=len(payload),
        compressed_blocks=[],
    )
    # plaintext-hash semantics
    e1 = SimpleNamespace(content_hash=hashlib.sha1(payload).digest(), **base)
    f1 = tmp_path / "a.bin"; f1.write_bytes(payload)
    pak._commit_tmp(f1, tmp_path / "a.out", e1)
    assert (tmp_path / "a.out").read_bytes() == payload
    # size mismatch still fails even with a valid hash
    e2 = SimpleNamespace(content_hash=hashlib.sha1(payload).digest(),
                         **{**base, "uncompressed_size": len(payload) + 1})
    f2 = tmp_path / "b.bin"; f2.write_bytes(payload)
    try:
        pak._commit_tmp(f2, tmp_path / "b.out", e2)
    except ValueError as exc:
        assert "size mismatch" in str(exc)
    else:
        raise AssertionError("size mismatch was accepted")
