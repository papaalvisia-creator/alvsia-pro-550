from pathlib import Path

from lua_engine.orchestrator import EngineSpec, run_decompiler_pipeline
from lua_engine.detector import LuaInfo


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
