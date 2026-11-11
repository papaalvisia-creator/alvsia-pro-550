import sys
import stat
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))
from archive_engine import detect_archive, inspect_archive, extract_archive, repack_obb, repack_pak
import alvsia_core


def test_obb_roundtrip_and_inspection():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "src"
        source.mkdir()
        (source / "nested").mkdir()
        (source / "nested" / "sample.lua").write_text("return 42\n", encoding="utf-8")
        archive = root / "sample.obb"
        result = repack_obb(source, archive)
        assert result["ok"], result
        assert detect_archive(archive)["format"] == "obb-zip"
        info = inspect_archive(archive)
        assert info["ok"] and info["entries"] == 1
        out = root / "out"
        extracted = extract_archive(archive, out)
        assert extracted["ok"], extracted
        assert (out / "nested" / "sample.lua").read_text(encoding="utf-8") == "return 42\n"


def test_zip_slip_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        archive = root / "unsafe.obb"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../escape.txt", "no")
        result = extract_archive(archive, root / "out")
        assert not result["ok"]
        assert "unsafe archive path" in result["error"]


def test_duplicate_zip_targets_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        archive = root / "duplicate.obb"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("same.txt", "first")
            zf.writestr("same.txt", "second")
        result = extract_archive(archive, root / "out")
        assert not result["ok"]
        assert "duplicate archive target" in result["error"]


def test_zip_symlink_entry_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        archive = root / "symlink.obb"
        info = zipfile.ZipInfo("linked.txt")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(info, "target.txt")
        result = extract_archive(archive, root / "out")
        assert not result["ok"]
        assert "symbolic-link" in result["error"]


def test_extraction_does_not_follow_predictable_temp_symlink():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        archive = root / "sample.obb"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("payload.txt", "archive-data")
        out = root / "out"
        out.mkdir()
        sentinel = root / "sentinel.txt"
        sentinel.write_text("keep-me", encoding="utf-8")
        (out / "payload.txt.alvsia-tmp").symlink_to(sentinel)
        result = extract_archive(archive, out)
        assert result["ok"], result
        assert sentinel.read_text(encoding="utf-8") == "keep-me"
        assert (out / "payload.txt").read_text(encoding="utf-8") == "archive-data"


def test_repack_does_not_follow_predictable_temp_symlink():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source"
        source.mkdir()
        (source / "payload.txt").write_text("archive-data", encoding="utf-8")
        sentinel = root / "sentinel.txt"
        sentinel.write_text("keep-me", encoding="utf-8")
        output = root / "sample.obb"
        (root / "sample.obb.alvsia-tmp").symlink_to(sentinel)
        result = repack_obb(source, output)
        assert result["ok"], result
        assert sentinel.read_text(encoding="utf-8") == "keep-me"
        assert zipfile.is_zipfile(output)


def test_pak_dispatch_uses_authenticated_core_contract():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pak = root / "sample.pak"
        pak.write_bytes(b"PAK0" + bytes(64))
        old_unpack = alvsia_core.run_pak_unpack
        old_repack = alvsia_core.run_pak_smart_repack
        try:
            calls = []
            alvsia_core.run_pak_unpack = lambda src, dest: (
                calls.append(("unpack", str(src), str(dest))) or {"ok": True, "files": 1}
            )
            result = extract_archive(pak, root / "pak_out")
            assert result["ok"] and result["format"] == "tencent-pak", result
            assert calls and calls[0][0] == "unpack"

            alvsia_core.run_pak_smart_repack = lambda base, modified, out: (
                calls.append(("repack", str(base), str(modified), str(out))) or {"ok": True}
            )
            result = repack_pak(pak, root, root / "rebuilt.pak")
            assert result["ok"], result
            assert any(item[0] == "repack" for item in calls)
        finally:
            alvsia_core.run_pak_unpack = old_unpack
            alvsia_core.run_pak_smart_repack = old_repack


def test_non_archive_rejected():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.bin"
        p.write_bytes(b"")
        assert not detect_archive(p)["ok"]


if __name__ == "__main__":
    test_obb_roundtrip_and_inspection()
    test_zip_slip_rejected()
    test_duplicate_zip_targets_rejected()
    test_zip_symlink_entry_rejected()
    test_extraction_does_not_follow_predictable_temp_symlink()
    test_repack_does_not_follow_predictable_temp_symlink()
    test_pak_dispatch_uses_authenticated_core_contract()
    test_non_archive_rejected()
    print("ARCHIVE ENGINE TEST: PASS (8/8)")


def test_extreme_zip_compression_ratio_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        archive = root / "bomb.obb"
        info = zipfile.ZipInfo("huge.txt")
        info.compress_type = zipfile.ZIP_DEFLATED
        payload = b"A" * (2 * 1024 * 1024)
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(info, payload)
        result = extract_archive(archive, root / "out")
        assert not result["ok"]
        assert "compression ratio" in result["error"]
