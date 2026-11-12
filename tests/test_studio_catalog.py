import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt"
MENUS = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
ROUTER = ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt"
MAIN = ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt"


class SmartCatalogTests(unittest.TestCase):
    def test_seven_smart_modules_are_the_public_catalog(self):
        source = CATALOG.read_text(encoding="utf-8")
        items = re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', source)
        self.assertEqual([int(i) for i, _ in items], list(range(1, 8)))
        self.assertEqual(
            [name for _, name in items],
            ["SMART LUA", "SMART PAK", "SMART OBB", "SMART DATA",
             "SMART ANALYSIS", "WORKSPACE & REPORT", "ALVSIA PRIVATE"],
        )

    def test_smart_lua_has_four_public_engines_and_unique_subtool_ids(self):
        menus = MENUS.read_text(encoding="utf-8")
        lua = menus.split("1 -> listOf(", 1)[1].split("\n        2 -> listOf(", 1)[0]
        lua_ids = re.findall(r'SubTool\(\s*"([^"]+)"', lua)
        self.assertEqual(
            lua_ids,
            ["lua_decompile", "lua_smart_protect", "lua_compile", "lua_patch_byte"],
        )
        all_ids = re.findall(r'SubTool\(\s*"([^"]+)"', menus)
        self.assertTrue(all_ids)
        self.assertEqual(len(all_ids), len(set(all_ids)), "SubTool IDs must be unique")
        self.assertIn("metadata_v39_decode", all_ids)

    def test_output_handoff_catalog_targets_the_same_seven_smart_modules(self):
        source = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/StudioCatalog.kt").read_text(encoding="utf-8")
        entries = re.findall(
            r'StudioItem\\("([^"]+)",\\s*"([^"]+)",.*?listOf\\(([^)]*)\\)\\)',
            source,
        )
        self.assertEqual(len(entries), 7)
        ids = [int(value) for _, _, raw in entries for value in re.findall(r"\\d+", raw)]
        self.assertEqual(ids, list(range(1, 8)))

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
