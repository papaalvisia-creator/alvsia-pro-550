import sys
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
    test_pak_dispatch_uses_authenticated_core_contract()
    test_non_archive_rejected()
    print("ARCHIVE ENGINE TEST: PASS (4/4)")
