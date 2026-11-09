import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from module_adapters import dispatch, list_adapters


def test_adapter_registry_is_deterministic_and_fail_closed():
    first = list_adapters()
    second = list_adapters()
    assert first == second
    assert {"module": "lua", "operation": "decompile"} in first
    assert {"module": "lua", "operation": "protect"} in first
    assert {"module": "string-recovery", "operation": "recover"} in first
    assert {"module": "archive", "operation": "inspect"} in first
    assert {"module": "archive", "operation": "extract"} in first
    assert {"module": "program-intelligence", "operation": "analyze"} in first

    result = dispatch("not-registered", "anything")
    assert not result["ok"]
    assert result["error"] == "adapter operation not registered"


def test_string_recovery_adapter_uses_existing_engine(tmp_path):
    source = tmp_path / "sample.bin"
    source.write_bytes(b"function PlayerCharacter local Server RPC self " * 4)
    result = dispatch(
        "string-recovery",
        "recover",
        input_path=source,
        output_dir=tmp_path / "out",
    )
    assert result["ok"], result
    assert result["module"] == "string-recovery"
    assert result["operation"] == "recover"
    assert result["candidate_count"] > 0


def test_archive_inspect_adapter_uses_existing_engine(tmp_path):
    import zipfile
    archive = tmp_path / "sample.obb"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("nested/sample.lua", "return 42\n")
    result = dispatch("archive", "inspect", input_path=archive)
    assert result["ok"], result
    assert result["format"] == "obb-zip"
    assert result["entries"] == 1
