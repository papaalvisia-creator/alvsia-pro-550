from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_recovery_proof import prove_roundtrip


def test_roundtrip_proof_missing_files_is_unproven(tmp_path):
    result = prove_roundtrip(tmp_path / "missing.luac", tmp_path / "missing.lua")
    assert result["status"] == "UNPROVEN"


def test_roundtrip_proof_never_executes_source(tmp_path):
    original = tmp_path / "original.luac"
    recovered = tmp_path / "recovered.lua"
    original.write_bytes(b"not-a-real-chunk")
    recovered.write_text("error('must never execute')\n", encoding="utf-8")
    result = prove_roundtrip(original, recovered)
    assert result["status"] in {"UNPROVEN", "DIVERGED", "ROUNDTRIP_VERIFIED"}
    assert "must never execute" not in str(result)
