from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
ROUTER = ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt"
CATALOG_TEXT = CATALOG.read_text(encoding="utf-8")
ROUTER_TEXT = ROUTER.read_text(encoding="utf-8")

EXPECTED = {
    1: ["universal_file_detect", "workspace_report", "engine_health"],
    2: ["lua_smart_analyze", "lua_recovery_normalize", "lua_t24_convert", "lua_multi_xor", "lua_protect_transform", "lua_custom_inject"],
    3: ["pak_info", "pak_extract", "pak_lua_inject", "pak_repack"],
    4: ["asset_uasset_classify", "asset_uexp_classify", "asset_locres_umap_classify", "asset_report"],
    5: ["apk_audit", "dex_report", "url_scan"],
    6: ["so_audit", "native_strings", "abi_dependency_report"],
    7: ["aes_scan", "zuc_decrypt", "string_recovery"],
    8: ["file_report", "strings", "entropy", "hex_preview"],
    9: ["batch_audit", "regression_compare", "self_test"],
}

def test_catalog_is_exactly_9x33():
    assert CATALOG_TEXT.count("SubTool(") == 34
    assert sum(len(v) for v in EXPECTED.values()) == 33
    for ids in EXPECTED.values():
        for sub_id in ids:
            assert f'SubTool("{sub_id}"' in CATALOG_TEXT
    declared = __import__("re").findall(r'SubTool\(\s*"([^"]+)"', CATALOG_TEXT)
    assert len(declared) == 33
    assert len(set(declared)) == 33
    assert declared == [sid for ids in EXPECTED.values() for sid in ids]

def test_all_public_ids_are_explicitly_routed():
    for ids in EXPECTED.values():
        for sub_id in ids:
            assert f'"{sub_id}"' in ROUTER_TEXT
    assert "Public IDs never become arbitrary Python operations" in ROUTER_TEXT

def test_no_ai_namespace_in_smart_catalog():
    assert "com.alvsia.ai.uncensored" not in CATALOG_TEXT
