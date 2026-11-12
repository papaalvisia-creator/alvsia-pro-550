from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from smart_archive_lua_engine import execute


def test_smart_obb_routes_embedded_lua_source(tmp_path):
    archive = tmp_path / "sample.obb"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("assets/scripts/test.lua", "local x = 1\nfunction test()\n return x\nend\n")

    result = execute(archive, tmp_path / "OUT", archive_kind="obb", deep_lua=False)
    assert result["format"] == "obb-zip"
    assert result["scan"]["lua_candidates"] == 1
    assert result["recovery"]["attempted"] == 1
    assert result["recovery"]["success"] == 1
    assert (tmp_path / "OUT" / "smart_archive_lua_report.json").is_file()


def test_smart_obb_does_not_promote_random_binary(tmp_path):
    archive = tmp_path / "binary.obb"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("assets/data.bin", bytes(range(256)) * 8)

    result = execute(archive, tmp_path / "OUT", archive_kind="obb", deep_lua=False)
    assert result["ok"] is False
    assert result["scan"]["lua_candidates"] == 0
    assert result["recovery"]["attempted"] == 0
