from pathlib import Path

from lua_engine.protection_pipeline import protect_file


def test_protect_file_validates_and_writes_atomically(tmp_path):
    source = tmp_path / "input.lua"
    output = tmp_path / "protected.lua"
    source.write_text(
        'local message = "hello"\nreturn message\n',
        encoding="utf-8",
    )

    result = protect_file(source, output, "strong")

    assert result["ok"] is True, result
    assert result["profile"] == "strong"
    assert output.is_file()
    assert result["sha256"]
    text = output.read_text(encoding="utf-8")
    assert "string.char(" in text
    assert '"hello"' not in text


def test_protect_file_rejects_binary_input_without_creating_output(tmp_path):
    source = tmp_path / "input.lua"
    output = tmp_path / "protected.lua"
    source.write_bytes(b"\x1bLua\x53\x00\xff")

    result = protect_file(source, output, "balanced")

    assert result["ok"] is False
    assert "UTF-8" in result["error"]
    assert not output.exists()


def test_protect_file_rejects_unknown_profile(tmp_path):
    source = tmp_path / "input.lua"
    output = tmp_path / "protected.lua"
    source.write_text("return 42\n", encoding="utf-8")

    result = protect_file(source, output, "does-not-exist")

    assert result["ok"] is False
    assert "unknown protection profile" in result["error"]
    assert not output.exists()


def test_protect_file_does_not_publish_invalid_transform(tmp_path, monkeypatch):
    source = tmp_path / "input.lua"
    output = tmp_path / "protected.lua"
    source.write_text("return 42\n", encoding="utf-8")

    monkeypatch.setattr(
        "lua_engine.protection_pipeline.validate_lua_source",
        lambda *args, **kwargs: (False, "forced rejection"),
    )
    result = protect_file(source, output, "balanced")

    assert result["ok"] is False
    assert "forced rejection" in result["error"]
    assert not output.exists()


def test_protect_file_reports_semantic_differential_gate(tmp_path):
    source = tmp_path / "input.lua"
    output = tmp_path / "protected.lua"
    source.write_text(
        'local function add(left, right)\n'
        '  local message = "hello"\n'
        '  return left + right, message\n'
        'end\n'
        'return add(1, 2)\n',
        encoding="utf-8",
    )

    result = protect_file(source, output, "strong")

    assert result["ok"] is True, result
    assert result["differential"]["function_markers"] == 1
    assert result["differential"]["return_markers"] == 2
