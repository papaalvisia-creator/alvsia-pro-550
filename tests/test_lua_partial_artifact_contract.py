from pathlib import Path

import smart_lua_engine


def test_cleaned_string_recovery_artifact_is_partial_not_adapter_failure(monkeypatch, tmp_path):
    source = tmp_path / "CharacterBase.luac"
    source.write_bytes(b"\x00\xffnot-a-source")
    output = tmp_path / "OUT"
    stale_workspace = tmp_path / "private-workspace"
    stale_workspace.mkdir()
    stale_artifact = stale_workspace / "strings.txt"
    stale_artifact.write_text("recovered strings", encoding="utf-8")
    stale_artifact.unlink()
    stale_workspace.rmdir()

    monkeypatch.setattr(
        smart_lua_engine,
        "run_lua_smart",
        lambda *_args, **_kwargs: {
            "ok": False,
            "out": None,
            "string_artifact": str(stale_artifact),
            "final_status": "PARTIAL_STRING_RECOVERY",
            "publish_gate": "BLOCKED",
            "strings_recovered": True,
            "string_count": 13258,
        },
    )

    result = smart_lua_engine.decompile(source, output)

    assert result["ok"] is True
    assert result["final_status"] == "PARTIAL_STRING_RECOVERY"
    assert result["artifact_kind"] == "string_recovery"
    assert result["partial_recovery"] is True
    assert result["artifact_available"] is False
    assert result["out"] is None
    assert result["source_recovered"] is False
    assert not list(output.iterdir())
