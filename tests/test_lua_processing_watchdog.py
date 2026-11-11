import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from lua_engine.decompiler53 import Decompiler, Proto, Reader
from lua_engine.orchestrator import EngineSpec, run_decompiler_pipeline
from lua_engine.streaming_decompiler import stream_decompile_lua53
from module_adapters import dispatch


def test_local_scope_lookup_uses_active_last_declaration():
    proto = Proto()
    proto.numparams = 0
    proto.code = [0] * 10
    proto.locvars = [
        {"name": "outer", "startpc": 0, "endpc": 10},
        {"name": "inner", "startpc": 3, "endpc": 5},
    ]
    proto.upvalues = []
    proto.constants = []
    proto.protos = []

    decompiler = Decompiler(proto)
    assert decompiler._local_at(2, 0) == "outer"
    assert decompiler._local_at(3, 0) == "inner"
    assert decompiler._local_at(4, 0) == "inner"
    assert decompiler._local_at(5, 0) == "outer"
    assert decompiler._local_at(10, 0) is None


def test_lua53_reader_checks_cooperative_deadline():
    reader = Reader(b"\\x00" * 2048, deadline=0.0)
    for _ in range(1023):
        reader._read(1)
    try:
        reader._read(1)
    except TimeoutError as exc:
        assert "deadline exceeded" in str(exc)
    else:
        raise AssertionError("expired parser deadline was not enforced")


def test_streaming_lua53_returns_timeout_instead_of_trying_more_candidates(tmp_path):
    source = tmp_path / "timeout.luac"
    source.write_bytes(b"fixture bytecode")
    output = tmp_path / "timeout.lua"
    with patch.dict(os.environ, {
        "ALVSIA_SEALED_RUNTIME": "1",
        "ALVSIA_LUA53_TIMEOUT_SECONDS": "10",
    }):
        with patch(
            "lua_engine.decompiler53.decompile_bytes",
            side_effect=TimeoutError("fixture deadline"),
        ):
            ok, note = stream_decompile_lua53(source, output)
    assert not ok
    assert "lua53_total_budget_exceeded" in note
    assert not output.exists()


def test_adapter_dispatch_uses_complete_smart_lua_engine(tmp_path, monkeypatch):
    import alvsia_features

    source = tmp_path / "input.luac"
    source.write_bytes(b"Lua fixture")
    produced = tmp_path / "smart-output.lua"
    produced.write_text("return 42\\n", encoding="utf-8")
    destination = tmp_path / "out" / "expected.lua"
    calls = []

    def fake_smart(input_path, output_dir, jars_dir=None):
        calls.append((Path(input_path), Path(output_dir), Path(jars_dir)))
        return {"ok": True, "out": str(produced), "final_status": "SUCCESS"}

    monkeypatch.setattr(alvsia_features, "run_lua_smart", fake_smart)
    result = dispatch(
        "lua", "decompile",
        input_path=source,
        output_path=destination,
        jars_dir=tmp_path / "jars",
    )
    assert result["ok"] is True, result
    assert result["out"] == str(destination)
    assert destination.read_text(encoding="utf-8") == "return 42\\n"
    assert calls == [(source, destination.parent, tmp_path / "jars")]


def test_pipeline_watchdog_stops_before_starting_another_engine(tmp_path, monkeypatch):
    source = tmp_path / "input.luac"
    source.write_bytes(b"fixture")
    called = []

    def should_not_run(_src, _dst):
        called.append(True)
        return False, "must not run"

    info = SimpleNamespace(format="luac", version="Lua 5.3")
    with patch.dict(os.environ, {"ALVSIA_LUA_PIPELINE_TIMEOUT_SECONDS": "30"}):
        with patch("lua_engine.orchestrator.time.monotonic", side_effect=[100.0, 131.0]):
            result = run_decompiler_pipeline(
                source,
                tmp_path / "result.lua",
                info,
                registry=[EngineSpec("never", ("luac",), should_not_run)],
            )
    assert called == []
    assert result["results"][0]["engine"] == "pipeline_watchdog"
    assert "budget exceeded" in result["results"][0]["note"]
