from pathlib import Path

from lua_engine import engine


def test_decompile_lua_prefers_native_fallback_when_java_unluac_missing(monkeypatch, tmp_path):
    source = tmp_path / "sample.luac"
    # Lua 5.3 signature; the detector is allowed to reject malformed payloads,
    # so stub detection for this plumbing test.
    source.write_bytes(b"placeholder")

    monkeypatch.setattr(
        engine,
        "detect_lua",
        lambda path: type("Info", (), {
            "kind": "bytecode",
            "format": "luac",
            "version": "Lua 5.3",
            "notes": (),
        })(),
    )
    monkeypatch.setattr(engine, "_pick_unluac_jar", lambda jars_dir: None)
    monkeypatch.setattr(engine, "_find_java", lambda: None)

    def fake_native(input_path, output_path, timeout=120):
        output_path.write_text("return 1\n", encoding="utf-8")
        return {"ok": True, "out": str(output_path), "engine": "unluac-rs", "validation": "stub"}

    monkeypatch.setattr(engine, "_run_native_unluac_rs", fake_native)
    monkeypatch.setattr(engine, "validate_lua_source", lambda path: (True, "stub"))

    result = engine.decompile_lua(source, tmp_path / "out")
    assert result["ok"] is True
    assert result["engine"] == "unluac-rs"
    assert Path(result["out"]).read_text(encoding="utf-8") == "return 1\n"
