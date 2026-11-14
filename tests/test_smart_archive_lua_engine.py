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


def test_diverged_bytecode_is_not_counted_as_success(tmp_path):
    """A created artifact is not proof of success: a decompiled chunk whose
    roundtrip proof diverges must be STRUCTURALLY_VALID, never SUCCESS."""
    import shutil
    import subprocess
    luac = shutil.which("luac5.3") or shutil.which("luac")
    if not luac:
        import pytest
        pytest.skip("luac compiler not available")
    src = tmp_path / "s.lua"
    src.write_text(
        "local function add(a,b) return a+b end\n"
        "local t = {x=1,y=2,name='hi'}\n"
        "local total = 0\n"
        "for i=1,10 do total = total + add(i,t.x) end\n"
        "print(total, t.name)\nreturn total\n",
        encoding="utf-8",
    )
    chunk = tmp_path / "s.luac"
    subprocess.run([luac, "-o", str(chunk), str(src)], check=True)

    import zipfile
    archive = tmp_path / "b.obb"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("assets/test.luac", chunk.read_bytes())

    result = execute(archive, tmp_path / "OUT", archive_kind="obb", deep_lua=True)
    statuses = {r["status"] for r in result["successes"]}
    assert "SUCCESS" not in statuses
    assert result["recovery"]["success"] == 0
    assert result["recovery"]["partial"] >= 1
    for r in result["partials"]:
        assert r["status"] in {"STRUCTURALLY_VALID", "PARTIAL_RECOVERY"}
