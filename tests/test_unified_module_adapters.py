import json
from pathlib import Path


def test_unified_adapter_registry_contains_real_lua_and_archive_paths():
    import module_adapters

    adapters = {(item["module"], item["operation"]) for item in module_adapters.list_adapters()}
    required = {
        ("lua", "decompile"),
        ("lua", "protect"),
        ("lua", "inject-patch"),
        ("lua", "inject-hook"),
        ("lua", "mod-repack"),
        ("lua", "vm-protect"),
        ("string-recovery", "recover"),
        ("archive", "inspect"),
        ("archive", "extract"),
        ("archive", "repack"),
    }
    assert required.issubset(adapters)


def test_adapter_dispatch_fails_closed_for_unknown_operation():
    import module_adapters

    result = module_adapters.dispatch("lua", "does-not-exist")
    assert result["ok"] is False
    assert result["error"] == "adapter operation not registered"


def test_require_output_rejects_missing_artifact(tmp_path: Path):
    import module_adapters

    result = module_adapters._require_output({"ok": True, "out": str(tmp_path / "missing.lua")}, (".lua",))
    assert result["ok"] is False
    assert "does not exist" in result["error"]


def test_vm_adapter_clamps_decoy_budget_and_preserves_real_output(monkeypatch, tmp_path: Path):
    import module_adapters

    src = tmp_path / "sample.lua"
    src.write_text("return 7\\n", encoding="utf-8")
    captured = {}

    def fake_vm_protect(input_path, output_path, output_format, num_decoys):
        captured["num_decoys"] = num_decoys
        output_path.write_text("return 7\\n", encoding="utf-8")
        return {"ok": True, "out": str(output_path)}

    monkeypatch.setattr("alvsia_vm_protect.vm_protect", fake_vm_protect)
    out = tmp_path / "sample.alvlua3.lua"
    result = module_adapters._lua_vm_protect(src, out, num_decoys=999999)
    assert result["ok"] is True
    assert captured["num_decoys"] == 4096
    assert out.is_file() and out.stat().st_size > 0
