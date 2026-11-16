import os
from pathlib import Path

import alvsia_features


def test_native_unluac_rs_fallback_is_strict(monkeypatch, tmp_path):
    binary = tmp_path / "unluac-rs"
    binary.write_text("placeholder", encoding="utf-8")
    binary.chmod(0o755)

    monkeypatch.setenv("ALVSIA_UNLUAC_RS_BIN", str(binary))
    found = alvsia_features._find_native_unluac_rs(tmp_path / "jars")
    assert found == binary


def test_run_unluac_uses_native_fallback_when_java_unluac_missing(monkeypatch, tmp_path):
    source = tmp_path / "input.luac"
    source.write_bytes(b"\x1bLua\x53\x00\x19\x93\r\n\x1a\n")
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(alvsia_features, "_pick_jar", lambda jars_dir: None)

    def fake_fallback(input_path, out_lua, timeout=120):
        out_lua.write_text("local x = 1\nreturn x\n", encoding="utf-8")
        return {"ok": True, "out": str(out_lua), "engine": "native-test"}

    monkeypatch.setattr(alvsia_features, "_run_native_unluac_rs", fake_fallback)
    result = alvsia_features.run_unluac(source, out)
    assert result["ok"] is True
    assert result["engine"] == "native-test"
    assert Path(result["out"]).read_text(encoding="utf-8").startswith("local x")
