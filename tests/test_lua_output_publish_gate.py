from pathlib import Path

import alvsia_features


def test_smart_lua_publish_gate_blocks_string_only(monkeypatch, tmp_path):
    source = tmp_path / "sample.luac"
    source.write_bytes(b"not-source")
    out = tmp_path / "OUT"

    def fake_internal(_input, workspace, jars_dir=None):
        strings = Path(workspace) / "sample_strings.txt"
        strings.write_text("hello\\nworld\\n", encoding="utf-8")
        return {
            "ok": True,
            "final_status": "PARTIAL_STRING_RECOVERY",
            "artifact_kind": "string_recovery",
            "source_recovered": False,
            "strings_recovered": True,
            "out": str(strings),
        }

    monkeypatch.setattr(alvsia_features, "_run_lua_smart_internal", fake_internal)
    result = alvsia_features.run_lua_smart(source, out)

    assert result["publish_gate"] == "BLOCKED"
    assert result["ok"] is False
    assert result["out"] is None
    assert list(out.iterdir()) == []


def test_smart_lua_publish_gate_publishes_only_validated_lua(monkeypatch, tmp_path):
    source = tmp_path / "sample.luac"
    source.write_bytes(b"input")
    out = tmp_path / "OUT"

    def fake_internal(_input, workspace, jars_dir=None):
        candidate = Path(workspace) / "sample_decompiled.lua"
        candidate.write_text("return 42\\n", encoding="utf-8")
        return {
            "ok": True,
            "final_status": "STRUCTURALLY_VALID",
            "artifact_kind": "lua_source",
            "source_recovered": True,
            "out": str(candidate),
        }

    monkeypatch.setattr(alvsia_features, "_run_lua_smart_internal", fake_internal)
    result = alvsia_features.run_lua_smart(source, out)

    assert result["publish_gate"] == "PASSED"
    assert result["ok"] is True
    assert Path(result["out"]).name == "sample_decompiled.lua"
    assert [p.name for p in out.iterdir()] == ["sample_decompiled.lua"]
    assert Path(result["out"]).read_text(encoding="utf-8") == "return 42\\n"


def test_smart_lua_publish_gate_preserves_structural_validation_level(monkeypatch, tmp_path):
    source = tmp_path / "high_work.luac"
    source.write_bytes(b"fixture")
    out = tmp_path / "OUT"

    def fake_internal(_input, workspace, jars_dir=None):
        candidate = Path(workspace) / "high_work_native.lua"
        candidate.write_text("local x = 42\\nreturn x\\n", encoding="utf-8")
        return {
            "ok": True,
            "final_status": "STRUCTURALLY_VALID",
            "validation_level": "syntax_only",
            "roundtrip_proof": "NOT_RUN",
            "artifact_kind": "lua_source",
            "source_recovered": True,
            "out": str(candidate),
        }

    monkeypatch.setattr(alvsia_features, "_run_lua_smart_internal", fake_internal)
    result = alvsia_features.run_lua_smart(source, out)

    assert result["ok"] is True
    assert result["publish_gate"] == "PASSED"
    assert result["final_status"] == "STRUCTURALLY_VALID"
    assert result["validation_level"] == "syntax_only"
    assert result["roundtrip_proof"] == "NOT_RUN"
    assert [p.name for p in out.iterdir()] == ["high_work_decompiled.lua"]
