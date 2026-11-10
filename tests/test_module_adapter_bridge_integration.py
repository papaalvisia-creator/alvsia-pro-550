from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "app/src/main/python/alvsia_bridge_impl.py").read_text(encoding="utf-8")
ADAPTER = (ROOT / "app/src/main/python/module_adapters.py").read_text(encoding="utf-8")


def test_production_bridge_wires_unified_adapter_facade():
    assert 'from module_adapters import dispatch as _adapter_dispatch' in BRIDGE
    for sub_id in (
        "lua_decompile",
        "lua_smart_protect",
        "lua_smart_protect_strong",
        "str_recover",
        "obb_info",
        "obb_unzip",
    ):
        assert sub_id in BRIDGE
    assert '("lua", "decompile")' in ADAPTER
    assert '("lua", "protect")' in ADAPTER
    assert '("string-recovery", "recover")' in ADAPTER
    assert '("archive", "inspect")' in ADAPTER
    assert '("archive", "extract")' in ADAPTER


def test_adapter_gate_is_after_operation_grant():
    grant_pos = BRIDGE.index("core._alvsia_require_operation")
    adapter_pos = BRIDGE.index("from module_adapters import dispatch")
    assert grant_pos < adapter_pos
