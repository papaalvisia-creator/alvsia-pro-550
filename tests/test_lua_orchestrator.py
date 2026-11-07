from pathlib import Path
import sys
from unittest.mock import patch

PY_ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"
sys.path.insert(0, str(PY_ROOT))

import alvsia_features
from alvsia_bridge import configure_unluac_rs
from lua_engine.orchestrator import EngineSpec, build_engine_registry, run_decompiler_pipeline
from lua_engine.detector import LuaInfo
from lua_engine.engine import validate_lua_source


def _info(fmt="luac", version="Lua 5.3"):
    return LuaInfo("bytecode", version, fmt, 8, "1b4c7561", 0.99)


def test_pipeline_runs_compatible_engines_and_keeps_valid_alternates(tmp_path):
    source = tmp_path / "input.luac"
    source.write_bytes(b"\x1bLua\x53\x00\x00\x00")

    def first(_src, dst):
        Path(dst).write_text("return 1\n", encoding="utf-8")
        return True, "first engine"

    def second(_src, dst):
        Path(dst).write_text("return 2\n", encoding="utf-8")
        return True, "second engine"

    specs = [
        EngineSpec("first", ("luac",), first, 10),
        EngineSpec("second", ("luac",), second, 20),
        EngineSpec("wrong_format", ("luajit",), second, 1),
    ]
    output = tmp_path / "result.lua"
    result = run_decompiler_pipeline(source, output, _info(), registry=specs)

    assert result["ok"] is True
    assert result["selected_engine"] == "first"
    assert output.read_text(encoding="utf-8") == "return 1\n"
    assert source.read_bytes() == b"\x1bLua\x53\x00\x00\x00"
    assert result["engines_attempted"] == ["first", "second"]
    assert "Lua 5.3 parser accepted source" in result["results"][0]["note"]
    alternate = Path(result["alternates_dir"]) / "second.lua"
    assert alternate.read_text(encoding="utf-8") == "return 2\n"


def test_pipeline_rejects_invalid_output_and_removes_candidate(tmp_path):
    source = tmp_path / "input.luac"
    source.write_bytes(b"fixture")
    output = tmp_path / "result.lua"

    def invalid(_src, dst):
        Path(dst).write_text("not a Lua program", encoding="utf-8")
        return True, "claimed success"

    result = run_decompiler_pipeline(
        source, output, _info(),
        registry=[EngineSpec("broken", ("luac",), invalid)],
    )

    assert result["ok"] is False
    assert result["selected_engine"] is None
    assert not output.exists()
    assert result["results"][0]["ok"] is False
    assert "rejected" in result["results"][0]["note"]


def test_pipeline_reports_engine_failures_without_fake_output(tmp_path):
    source = tmp_path / "input.luac"
    source.write_bytes(b"fixture")
    output = tmp_path / "result.lua"

    def fail(_src, _dst):
        return False, "unsupported bytecode"

    result = run_decompiler_pipeline(
        source, output, _info(),
        registry=[EngineSpec("unsupported", ("luac",), fail)],
    )

    assert result["ok"] is False
    assert not output.exists()
    assert result["results"][0]["note"] == "unsupported bytecode"



def test_smart_pipeline_continues_after_partial_vm_diagnostics(tmp_path):
    source = tmp_path / "protected.luac"
    source.write_bytes(b"\\x1bLua\\x53" + bytes(40))
    output = tmp_path / "protected_decompiled.lua"

    def fake_pipeline(src, dst, info, jars_dir=None, registry=None):
        Path(dst).write_text("return 42\\n", encoding="utf-8")
        return {
            "ok": True,
            "out": str(dst),
            "selected_engine": "fixture_engine",
            "engines_attempted": ["fixture_engine"],
            "results": [],
        }

    partial = {
        "ok": False,
        "mode": "bgmi_vm_partial",
        "recovered": False,
        "protos_parsed": 3,
        "main_code_count": 12,
        "main_const_count": 4,
        "parse_errors": 1,
        "note": "partial VM structure only",
    }
    with patch("lua_engine.streaming_decompiler.decompile_large", return_value=partial):
        with patch("lua_engine.orchestrator.run_decompiler_pipeline", side_effect=fake_pipeline):
            result = alvsia_features.run_lua_smart(source, tmp_path)

    assert result["ok"] is True
    assert result["selected_engine"] == "fixture_engine"
    assert result["final_status"] == "PARTIAL"
    assert result["vm_obfuscated"] is True
    assert result["source_recovered"] is False
    assert result["artifact_kind"] == "vm_wrapper_source"
    assert Path(result["out"]).read_text(encoding="utf-8") == "return 42\\n"
    assert any(step.get("step") == "vm_partial_not_final" for step in result["steps"])



def test_optional_unluac_rs_adapter_runs_strict_cli_without_shell(tmp_path):
    binary = tmp_path / "unluac-cli"
    binary.write_text(
        "#!/usr/bin/env python3\\n"
        "import pathlib, sys\\n"
        "args = sys.argv[1:]\\n"
        "assert args[0] == '-i' and args[2] == '-o'\\n"
        "assert args[-2:] == ['--generate-mode', 'strict']\\n"
        "pathlib.Path(args[3]).write_text('return 42\\n', encoding='utf-8')\\n",
        encoding="utf-8",
    )
    binary.chmod(0o700)
    source = tmp_path / "input.luac"
    source.write_bytes(b"\\x1bLua\\x51" + bytes(40))
    output = tmp_path / "output.lua"
    info = LuaInfo("bytecode", "Lua 5.1", "luac", 45, "1b4c7561", 0.99)

    specs = build_engine_registry(info, jars_dir=str(tmp_path))
    assert any(spec.name == "unluac_rs_v1_4_4" for spec in specs)
    lua55_specs = build_engine_registry(
        LuaInfo("bytecode", "Lua 5.5", "luac", 45, "1b4c756155", 0.99),
        jars_dir=str(tmp_path),
    )
    assert any(spec.name == "unluac_rs_v1_4_4" for spec in lua55_specs)
    luau_v7_specs = build_engine_registry(
        LuaInfo("bytecode", "Luau bytecode v7", "luau", 45, "07030001", 0.88),
        jars_dir=str(tmp_path),
    )
    assert any(spec.name == "unluac_rs_v1_4_4" for spec in luau_v7_specs)
    luau_v14_specs = build_engine_registry(
        LuaInfo("bytecode", "Luau bytecode v14", "luau", 45, "0e030001", 0.88),
        jars_dir=str(tmp_path),
    )
    assert not any(spec.name == "unluac_rs_v1_4_4" for spec in luau_v14_specs)
    result = run_decompiler_pipeline(
        source, output, info, jars_dir=str(tmp_path)
    )

    assert result["ok"] is True, result
    assert result["selected_engine"] == "unluac_rs_v1_4_4"
    assert output.read_text(encoding="utf-8") == "return 42\\n"


def test_bridge_registers_only_existing_executable_unluac_binary(tmp_path, monkeypatch):
    binary = tmp_path / "libunluac-cli.so"
    binary.write_bytes(b"android-arm64-cli-fixture")
    binary.chmod(0o700)
    monkeypatch.delenv("ALVSIA_UNLUAC_RS_BIN", raising=False)

    assert configure_unluac_rs(str(binary)) is True
    assert __import__("os").environ["ALVSIA_UNLUAC_RS_BIN"] == str(binary.resolve())

    binary.chmod(0o600)
    assert configure_unluac_rs(str(binary)) is False
    assert "ALVSIA_UNLUAC_RS_BIN" not in __import__("os").environ


def test_smart_lua_plain_source_uses_shared_registry_and_validator(tmp_path):
    source = tmp_path / "plain.lua"
    source.write_text("local answer = 40 + 2\\nreturn answer\\n", encoding="utf-8")
    result = alvsia_features.run_lua_smart(source, tmp_path / "out")

    assert result["ok"] is True, result
    assert result["selected_engine"] == "source_passthrough"
    assert result["final_status"] == "SUCCESS"
    assert result["source_recovered"] is True
    assert Path(result["out"]).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_unknown_encrypted_payload_checks_pattern_recovery_before_nonlua_fallback(tmp_path):
    source = tmp_path / "encrypted.payload"
    source.write_bytes(b"ALVLUA1" + bytes(48))
    out = tmp_path / "out"
    out.mkdir()
    recovered = out / "encrypted_recovered.lua"
    recovered.write_text("return 42\\n", encoding="utf-8")
    pattern = {
        "ok": True,
        "recovered": True,
        "mode": "alvlua1_payload",
        "pattern_id": "ALVLUA1_PAYLOAD",
        "out": str(recovered),
    }
    with patch("lua_engine.streaming_decompiler.decompile_large", return_value=pattern):
        result = alvsia_features.run_lua_smart(source, out)

    assert result["ok"] is True, result
    assert result["selected_engine"] == "protected_pattern_recovery"
    assert result["final_status"] == "SUCCESS"
    assert any(step.get("step") == "detect" and step.get("ok") is False for step in result["steps"])
    assert Path(result["out"]).read_text(encoding="utf-8") == "return 42\\n"


def test_validator_marks_structural_fallback_when_matching_parser_missing(tmp_path):
    source = tmp_path / "fallback.lua"
    source.write_text("local answer = 42\\nreturn answer\\n", encoding="utf-8")
    with patch("lua_engine.engine.shutil.which", return_value=None):
        valid, note = validate_lua_source(source, expected_version="Lua 5.3")
    assert valid is True
    assert "structural heuristic accepted" in note
    assert "matching Lua parser unavailable" in note
