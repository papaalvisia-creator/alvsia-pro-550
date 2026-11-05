import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))
from archive_engine import detect_archive, inspect_archive, extract_archive, repack_obb


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


def test_non_archive_rejected():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.bin"
        p.write_bytes(b"")
        assert not detect_archive(p)["ok"]


if __name__ == "__main__":
    test_obb_roundtrip_and_inspection()
    test_zip_slip_rejected()
    test_non_archive_rejected()
    print("ARCHIVE ENGINE TEST: PASS (3/3)")
