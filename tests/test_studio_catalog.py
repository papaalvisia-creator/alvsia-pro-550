import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt"
MENUS = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
ROUTER = ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt"
MAIN = ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt"


class SmartCatalogTests(unittest.TestCase):
    def test_nine_smart_modules_are_the_public_catalog(self):
        source = CATALOG.read_text(encoding="utf-8")
        items = re.findall(r'ToolItem\\(\\s*(\\d+)\\s*,\\s*"([^"]+)"', source)
        self.assertEqual([int(i) for i, _ in items], list(range(1, 10)))
        self.assertEqual(
            [name for _, name in items],
            ["HOME", "LUA", "PAK / OBB", "ASSET / UE", "APK / DEX", "NATIVE",
             "CRYPTO / RECOVERY", "FORENSIC / STRING", "BATCH / DEV LAB"],
        )

    def test_public_subtools_are_exactly_33_and_unique(self):
        menus = MENUS.read_text(encoding="utf-8")
        all_ids = re.findall(r'SubTool\\(\\s*"([^"]+)"', menus)
        expected = [
            "universal_file_detect", "workspace_report", "engine_health",
            "lua_smart_analyze", "lua_recovery_normalize", "lua_t24_convert", "lua_multi_xor", "lua_protect_transform", "lua_custom_inject",
            "pak_info", "pak_extract", "pak_lua_inject", "pak_repack",
            "asset_uasset_classify", "asset_uexp_classify", "asset_locres_umap_classify", "asset_report",
            "apk_audit", "dex_report", "url_scan",
            "so_audit", "native_strings", "abi_dependency_report",
            "aes_scan", "zuc_decrypt", "string_recovery",
            "file_report", "strings", "entropy", "hex_preview",
            "batch_audit", "regression_compare", "self_test",
        ]
        self.assertEqual(all_ids, expected)
        self.assertEqual(len(all_ids), 33)
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_output_handoff_catalog_targets_nine_smart_modules(self):
        source = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/StudioCatalog.kt").read_text(encoding="utf-8")
        entries = re.findall(
            r'StudioItem\("([^"]+)",\s*"([^"]+)",.*?listOf\(([^)]*)\)\)',
            source,
        )
        self.assertEqual(len(entries), 9)
        ids = [int(value) for _, _, raw in entries for value in re.findall(r"\d+", raw)]
        self.assertEqual(ids, list(range(1, 10)))

    def test_legacy_provider_dispatch_is_internal_and_reachable(self):
        router = ROUTER.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("SmartModuleRouter.backendModule", main)
        self.assertIn("SmartModuleRouter.normalizedSubId", main)
        self.assertIn("engine.runSub(dispatchModuleId, dispatchSubId", main)
        self.assertIn('subId == "lua_smart_protect"', router)
        self.assertIn('subId == "pak_smart_inspect"', router)
        self.assertIn('subId == "obb_smart_inspect"', router)
        self.assertIn('subId == "data_auto_recover"', router)


if __name__ == "__main__":
    unittest.main()
