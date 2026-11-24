# -*- coding: utf-8 -*-
"""Acceptance tests for the previously-pending subtool adapters.

Each test proves the adapter (a) produces and verifies a REAL output
artifact, (b) fails closed with a clear error when prerequisites are
missing, and (c) never reports success for a no-op.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"))

from pending_subtool_adapters import PENDING_ADAPTERS, dispatch_pending  # noqa: E402


def _make_zip(path: Path, entries: dict[str, bytes], compress=zipfile.ZIP_STORED):
    with zipfile.ZipFile(path, "w", compress) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


@pytest.fixture()
def workdir(tmp_path):
    (tmp_path / "WORK").mkdir()
    (tmp_path / "OUT").mkdir()
    return tmp_path


# ── registry ────────────────────────────────────────────────────────

def test_registry_contains_19_enabled_subtools():
    assert len(PENDING_ADAPTERS) == 19
    for sid, runner in PENDING_ADAPTERS.items():
        assert callable(runner), sid


def test_dispatch_fails_closed_for_unknown_subtool():
    result = dispatch_pending("no_such_pending_subtool")
    assert result["ok"] is False
    assert "not registered" in result["error"]


def test_dispatch_fails_closed_on_exception():
    # non-existent paths must produce ok=False, never raise
    result = dispatch_pending("lab_large_file_benchmark", input_path=None, output_dir=None)
    assert result["ok"] is False
    assert "not found" in result["error"]


# ── batch 1: archive ────────────────────────────────────────────────

def test_pak_selective_extract_prefix_and_exact(workdir):
    src = _make_zip(workdir / "game.pak", {
        "content/lua/a.lua": b"-- a",
        "content/lua/b.lua": b"-- b",
        "other/c.bin": b"\x00\x01",
    })
    (workdir / "WORK" / "select_entries.txt").write_text(
        "content/lua/\nother/c.bin\n", encoding="utf-8")
    result = dispatch_pending("pak_selective_extract",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    out = Path(result["out"])
    assert (out / "content/lua/a.lua").read_bytes() == b"-- a"
    assert (out / "content/lua/b.lua").read_bytes() == b"-- b"
    assert (out / "other/c.bin").read_bytes() == b"\x00\x01"
    assert result["selected_files"] == 3


def test_pak_selective_extract_no_config_fails_closed(workdir):
    src = _make_zip(workdir / "game.pak", {"a.lua": b"x"})
    result = dispatch_pending("pak_selective_extract",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert "select_entries.txt" in result["error"]


def test_pak_selective_extract_no_match_fails_closed(workdir):
    src = _make_zip(workdir / "game.pak", {"a.lua": b"x"})
    (workdir / "WORK" / "select_entries.txt").write_text("missing/entry\n", encoding="utf-8")
    result = dispatch_pending("pak_selective_extract",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert "no archive entry matched" in result["error"]


def test_pak_selective_extract_all(workdir):
    src = _make_zip(workdir / "game.pak", {"a.lua": b"x", "b/c.bin": b"y"})
    (workdir / "WORK" / "select_entries.txt").write_text("ALL\n", encoding="utf-8")
    result = dispatch_pending("pak_selective_extract",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result


def test_apk_compare_resource_diff(workdir):
    apk_a = _make_zip(workdir / "old.apk", {
        "classes.dex": b"dex\n0123", "res/a.xml": b"AAAA", "res/b.xml": b"BBBB"})
    apk_b = _make_zip(workdir / "new.apk", {
        "classes.dex": b"dex\nCHANGED", "res/b.xml": b"BBBB",
        "res/c.xml": b"CCCC"})
    (workdir / "WORK" / "compare_base.txt").write_text(str(apk_b), encoding="utf-8")
    result = dispatch_pending("apk_compare_resource_diff",
                              input_path=apk_a, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert result["added"] == 1       # res/c.xml
    assert result["removed"] == 1     # res/a.xml
    assert result["changed"] == 1     # classes.dex
    payload = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
    assert payload["added"][0]["name"] == "res/c.xml"
    assert Path(result["report"]).is_file()
    assert Path(result["json"]).stat().st_size > 0


def test_apk_compare_diff_requires_base(workdir):
    apk_a = _make_zip(workdir / "old.apk", {"a": b"a"})
    result = dispatch_pending("apk_compare_resource_diff",
                              input_path=apk_a, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert "compare_base.txt" in result["error"]


def test_mini_obb_zsdic_adapter(workdir):
    src = _make_zip(workdir / "skin.obb", {
        "zsdic/dict1.bin": b"\x28\xb5\x2f\xfd" + b"\x11" * 32,
        "assets/skin.uasset": b"\x9e\x2a\x9c\x81" + b"\x00" * 64,
    })
    result = dispatch_pending("mini_obb_zsdic_adapter",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert result["zsdic_entries"] == 1
    assert result["zsdic_detail"][0]["zstd_magic"] is True
    assert Path(result["report"]).is_file()


def test_gamepatch_obb_repacker_preserves_order_and_content(workdir):
    entries = {
        "index.bin": b"IDX1",
        "a/skin.uasset": b"\x9e\x2a\x9c\x81" + b"\x00" * 32,
        "a/skin.uexp": b"\x01\x02\x03",
    }
    src = _make_zip(workdir / "base.obb", entries, compress=zipfile.ZIP_DEFLATED)
    tree = workdir / "WORK" / "OBB"
    (tree / "a").mkdir(parents=True)
    (tree / "index.bin").write_bytes(b"IDX2")           # edited
    (tree / "a" / "skin.uasset").write_bytes(entries["a/skin.uasset"])
    (tree / "a" / "skin.uexp").write_bytes(entries["a/skin.uexp"])
    (tree / "a" / "new.txt").write_bytes(b"new file")  # appended
    result = dispatch_pending("gamepatch_obb_repacker",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    dest = Path(result["out"])
    with zipfile.ZipFile(dest) as zf:
        names = [i.filename for i in zf.infolist() if not i.is_dir()]
        # base order preserved, new files appended
        assert names[:3] == ["index.bin", "a/skin.uasset", "a/skin.uexp"]
        assert "a/new.txt" in names
        assert zf.read("index.bin") == b"IDX2"
        assert zf.read("a/new.txt") == b"new file"
        assert zf.testzip() is None
    assert result["base_entries_preserved"] == 3
    assert len(result["sha256"]) == 64


def test_gamepatch_repacker_requires_tree(workdir):
    src = _make_zip(workdir / "base.obb", {"index.bin": b"IDX"})
    result = dispatch_pending("gamepatch_obb_repacker",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert "tree not found" in result["error"]


# ── batch 2: lua / crypto ───────────────────────────────────────────

def test_lua_round_trip_validator_requires_recovered(workdir):
    (workdir / "orig.luac").write_bytes(b"\x1bLuaQ")
    result = dispatch_pending("lua_round_trip_validator",
                              input_path=workdir / "orig.luac",
                              output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert "recovered_source.txt" in result["error"]


def test_lua_round_trip_validator_reports_unproven_without_luac(workdir):
    # prove_roundtrip returns UNPROVEN when no compatible luac exists
    # (sandbox), which the adapter must surface as ok=False, never fake it.
    (workdir / "orig.luac").write_bytes(b"\x1bLuaQ")
    (workdir / "recovered.lua").write_text("print('x')\n", encoding="utf-8")
    (workdir / "WORK" / "recovered_source.txt").write_text(
        str(workdir / "recovered.lua"), encoding="utf-8")
    result = dispatch_pending("lua_round_trip_validator",
                              input_path=workdir / "orig.luac",
                              output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert result["status"] in ("UNPROVEN", "DIVERGED")
    assert Path(result["report"]).is_file()


def test_crypto_output_validator_zip_and_hash(workdir):
    target = _make_zip(workdir / "dec_out.zip", {"a.txt": b"hello"})
    import hashlib
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (workdir / "WORK" / "expected_hash.txt").write_text(digest, encoding="utf-8")
    result = dispatch_pending("crypto_output_validator",
                              input_path=target, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert "zip" in result["recognized_formats"]
    assert result["hash_match"] is True


def test_crypto_output_validator_hash_mismatch_fails(workdir):
    target = workdir / "blob.bin"
    target.write_bytes(b"\x28\xb5\x2f\xfd" + b"data")  # zstd magic
    (workdir / "WORK" / "expected_hash.txt").write_text("00" * 32, encoding="utf-8")
    result = dispatch_pending("crypto_output_validator",
                              input_path=target, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert result["hash_match"] is False
    assert "zstd" in result["recognized_formats"]


def test_crypto_output_validator_unknown_format_fails(workdir):
    target = workdir / "random.bin"
    target.write_bytes(os.urandom(256))
    result = dispatch_pending("crypto_output_validator",
                              input_path=target, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is False
    assert result["recognized_formats"] == []


# ── batch 3: modding / unreal / zsdic ───────────────────────────────

def _uasset_bytes(names: list[str]) -> bytes:
    name_blob = b""
    for n in names:
        raw = n.encode("utf-8") + b"\x00"
        name_blob += struct.pack("<i", len(raw)) + raw
    header = bytearray(0x60)
    header[0:4] = b"\x9e\x2a\x9c\x81"                      # magic (file byte order)
    struct.pack_into("<I", header, 0x04, 514)           # file version
    struct.pack_into("<I", header, 0x18, len(names))    # name count
    name_offset = 0x60
    struct.pack_into("<I", header, 0x1C, name_offset)   # name offset
    return bytes(header) + name_blob


def test_modding_uasset_inspector(workdir):
    src = workdir / "skin.uasset"
    src.write_bytes(_uasset_bytes(["Head", "Body", "Skin_01"]))
    result = dispatch_pending("modding_uasset_uexp_inspector",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    info = result["info"]
    assert info["is_uasset"] is True
    assert info["name_count"] == 3
    assert info["names"] == ["Head", "Body", "Skin_01"]
    assert info["file_version_ue4"] == 514
    assert Path(result["report"]).is_file()


def test_modding_uasset_inspector_rejects_non_ue(workdir):
    src = workdir / "plain.bin"
    src.write_bytes(b"not an unreal asset")
    result = dispatch_pending("modding_uasset_uexp_inspector",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is False


def test_modding_ue4_string_id_extractor(workdir):
    src = workdir / "skin.uasset"
    src.write_bytes(_uasset_bytes(["Head", "Skin_01"]) + b"\x00" + b"PlayerNameRef" + b"\x00\x00")
    result = dispatch_pending("modding_ue4_string_id_extractor",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert result["name_table"] == 2
    assert result["ascii_runs"] >= 1
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "Skin_01" in text


def test_modding_skin_pair_finder_directory(workdir):
    base = workdir / "assets"
    (base / "skins").mkdir(parents=True)
    (base / "skins" / "123.uasset").write_bytes(b"a")
    (base / "skins" / "123.uexp").write_bytes(b"b")
    (base / "skins" / "124.uasset").write_bytes(b"c")
    (base / "skins" / "124.uexp").write_bytes(b"d")
    (base / "readme.txt").write_bytes(b"r")
    result = dispatch_pending("modding_skin_pair_finder",
                              input_path=base, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    kinds = {p["kind"] for p in result["pair_detail"]}
    assert "uasset+uexp" in kinds
    assert "numeric-id-set" in kinds


def test_modding_skin_pair_finder_archive(workdir):
    src = _make_zip(workdir / "skins.obb", {
        "skins/123.uasset": b"a", "skins/123.uexp": b"b"})
    result = dispatch_pending("modding_skin_pair_finder",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert any(p["kind"] == "uasset+uexp" for p in result["pair_detail"])


def test_modding_zsdic_analyzer(workdir):
    src = workdir / "zsdic" / "dict.bin"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"\x28\xb5\x2f\xfd" + b"\xab\xcd\xef\x01" + b"\x00" * 100)
    (src.parent / "size.txt").write_text("123=2048\n", encoding="utf-8")
    result = dispatch_pending("modding_zsdic_analyzer",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    info = result["info"]
    assert info["zstd_dictionary"] is True
    assert info["dict_id_hex"] == "abcdef01"
    assert "size.txt" in info["companion_files"]
    assert len(info["sha256"]) == 64


def test_modding_offset_size_fixer_rebuild(workdir):
    tree = workdir / "WORK" / "OBB"
    (tree / "a").mkdir(parents=True)
    (tree / "index.bin").write_bytes(b"IDX")
    (tree / "a" / "x.bin").write_bytes(b"data")
    result = dispatch_pending("modding_offset_size_fixer",
                              input_path=None, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert result["mode"] == "rebuild"
    with zipfile.ZipFile(result["out"]) as zf:
        assert zf.testzip() is None
        assert len(zf.infolist()) == 2


def test_modding_offset_size_fixer_verify_ok(workdir):
    src = _make_zip(workdir / "check.obb", {"a": b"1", "b/c": b"2"})
    result = dispatch_pending("modding_offset_size_fixer",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert result["mode"] == "verify"
    assert result["issues"] == []


def test_modding_resource_mapping_recovery(workdir):
    src = _make_zip(workdir / "orig.obb", {
        "keep.bin": b"keep", "edit.bin": b"old"})
    tree = workdir / "WORK" / "MOD"
    tree.mkdir()
    (tree / "edit.bin").write_bytes(b"new content")
    (tree / "added.bin").write_bytes(b"added")
    result = dispatch_pending("modding_resource_mapping_recovery",
                              input_path=src, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert result["replaced"] == 1
    assert result["added"] == 1
    assert result["untouched"] == 1
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "edit.bin" in text and "added.bin" in text


# ── batch 4: workspace / lab ────────────────────────────────────────

def test_native_xref_analyzer_dex(workdir):
    src = workdir / "classes.dex"
    src.write_bytes(b"dex\n035\x00" + b"Lcom/example/Class;" * 20)
    result = dispatch_pending("native_xref_reference_analyzer",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert result["format"] == "DEX"
    assert result["tracked"] >= 1
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "Lcom/example/Class;" in text


def test_native_xref_analyzer_rejects_other(workdir):
    src = workdir / "plain.txt"
    src.write_text("hello", encoding="utf-8")
    result = dispatch_pending("native_xref_reference_analyzer",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is False


def test_workspace_file_manager(workdir):
    (workdir / "INPUT" / "job").mkdir(parents=True)
    (workdir / "INPUT" / "job" / "in.pak").write_bytes(b"PK\x03\x04")
    (workdir / "OUT" / "PAK").mkdir(parents=True)
    (workdir / "OUT" / "PAK" / "out.bin").write_bytes(b"result")
    (workdir / "WORK" / "xor_key.txt").write_text("DEADBEEF", encoding="utf-8")
    result = dispatch_pending("workspace_file_manager",
                              input_path=workdir, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert result["total_files"] == 3
    assert result["sections"]["INPUT"] == 1
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "in.pak" in text and "xor_key.txt" in text


def test_workspace_file_manager_cleanup(workdir):
    (workdir / "WORK" / "junk.bin").write_bytes(b"junk")
    (workdir / "WORK" / "cleanup.txt").write_text("clear-work\n", encoding="utf-8")
    result = dispatch_pending("workspace_file_manager",
                              input_path=workdir, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert result["cleanup"] == ["clear-work"]
    assert not (workdir / "WORK" / "junk.bin").exists()
    # cleanup.txt itself was consumed by the cleanup
    assert not any(workdir.joinpath("WORK").rglob("junk*"))


def test_workspace_resume_cancel_progress(workdir):
    tasks = workdir / "TASKS"
    t1 = tasks / "task-1"
    t1.mkdir(parents=True)
    (t1 / "status.json").write_text(
        json.dumps({"status": "RUNNING", "progress": 42}), encoding="utf-8")
    (t1 / "run.log").write_text("log", encoding="utf-8")
    (t1 / "WORK").mkdir()
    (t1 / "WORK" / "staged.bin").write_bytes(b"s")
    t2 = tasks / "task-2"
    t2.mkdir(parents=True)
    (t2 / "status.json").write_text(
        json.dumps({"status": "COMPLETED"}), encoding="utf-8")
    (workdir / "WORK").mkdir(exist_ok=True)
    (workdir / "WORK" / "cancel.txt").write_text("task-1\n", encoding="utf-8")
    result = dispatch_pending("workspace_resume_cancel_progress",
                              input_path=workdir, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    by_task = {t["task"]: t for t in result["tasks"]}
    assert by_task["task-1"]["resumable"] is True
    assert by_task["task-1"]["status"] == "RUNNING"
    assert result["cancelled"] == ["task-1"]
    assert (t1 / "CANCEL_REQUESTED").is_file()


def test_lab_engine_registry_lists_registered_operations(workdir):
    result = dispatch_pending("lab_engine_registry",
                              input_path=None, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert "lua.decompile" in result["registered_operations"]
    assert "archive.extract" in result["registered_operations"]
    assert result["missing"] == []
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "SMART LUA ENGINE" in text
    assert "tencent-pak" in text


def test_lab_regression_diff_compare_zip(workdir):
    ref = _make_zip(workdir / "ref.zip", {"a.txt": b"1", "b.txt": b"2"})
    cand = _make_zip(workdir / "cand.zip", {"a.txt": b"1", "c.txt": b"3"})
    (workdir / "WORK").mkdir(exist_ok=True)
    (workdir / "WORK" / "regression_base.txt").write_text(str(ref), encoding="utf-8")
    result = dispatch_pending("lab_regression_diff_compare",
                              input_path=cand, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert result["identical"] is False
    text = Path(result["report"]).read_text(encoding="utf-8")
    assert "+ c.txt" in text and "- b.txt" in text


def test_lab_regression_diff_compare_identical(workdir):
    ref = workdir / "ref.bin"
    ref.write_bytes(b"same bytes")
    (workdir / "WORK").mkdir(exist_ok=True)
    (workdir / "WORK" / "regression_base.txt").write_text(str(ref), encoding="utf-8")
    result = dispatch_pending("lab_regression_diff_compare",
                              input_path=ref, output_dir=workdir / "OUT",
                              work_dir=workdir / "WORK")
    assert result["ok"] is True, result
    assert result["identical"] is True


def test_lab_large_file_benchmark(workdir):
    src = workdir / "big.bin"
    payload = os.urandom(3 * 1024 * 1024)
    src.write_bytes(payload)
    result = dispatch_pending("lab_large_file_benchmark",
                              input_path=src, output_dir=workdir / "OUT")
    assert result["ok"] is True, result
    assert result["bytes"] == len(payload)
    assert result["integrity"] is True
    assert result["mib_per_s"] > 0
    # benchmark copy must not be left behind as a deliverable
    assert not (workdir / "OUT" / "big.bin.benchcopy").exists()
    assert Path(result["report"]).is_file()
