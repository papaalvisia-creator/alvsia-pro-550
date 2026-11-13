import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt"
MENUS = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
ROUTER = ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt"
MAIN = ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt"
STUDIOS = ROOT / "app/src/main/java/com/alvsia/pro/ui/home/StudioCatalog.kt"


class SmartCatalogTests(unittest.TestCase):
    def test_seven_smart_menus_are_the_public_catalog(self):
        source = CATALOG.read_text(encoding="utf-8")
        items = re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', source)
        self.assertEqual([int(i) for i, _ in items], list(range(1, 8)))
        self.assertEqual(
            [name for _, name in items],
            ["SMART LUA", "SMART PAK", "SMART OBB", "SMART DATA",
             "SMART ANALYSIS", "WORKSPACE & REPORT", "ALVSIA PRIVATE"],
        )

    def test_exactly_nineteen_submenu_groups_cover_all_legacy_modules(self):
        menus = MENUS.read_text(encoding="utf-8")
        group_section = menus.split("fun forModule(moduleId: Int)", 1)[1].split("private fun moduleGroup", 1)[0]
        ids = [int(x) for x in re.findall(r'moduleGroup\(\s*(\d+)\s*,', group_section)]
        self.assertEqual(len(ids), 19)
        self.assertEqual(sorted(ids), list(range(1, 20)))
        all_actions = re.findall(r'SubTool\(\s*"([a-zA-Z0-9_]+)"', menus.split("private fun legacyOperations", 1)[1])
        self.assertEqual(len(all_actions), 89)
        self.assertEqual(len(all_actions), len(set(all_actions)))

    def test_lua_menu_groups_the_four_original_lua_capability_modules(self):
        menus = MENUS.read_text(encoding="utf-8")
        lua = menus.split("1 -> listOf(", 1)[1].split("\n        2 -> listOf(", 1)[0]
        ids = [int(x) for x in re.findall(r'moduleGroup\(\s*(\d+)\s*,', lua)]
        self.assertEqual(ids, [5, 15, 16, 18])
        for action in ("lua_decompile", "str_recover", "lua_patch_byte", "lua_smart_protect"):
            self.assertIn(f'"{action}"', menus)

    def test_output_handoff_catalog_targets_the_same_seven_smart_menus(self):
        source = STUDIOS.read_text(encoding="utf-8")
        entries = re.findall(r'StudioItem\("([^"]+)",\s*"([^"]+)",.*?listOf\(([^)]*)\)\)', source)
        self.assertEqual(len(entries), 7)
        ids = [int(value) for _, _, raw in entries for value in re.findall(r"\d+", raw)]
        self.assertEqual(ids, list(range(1, 8)))

    def test_legacy_provider_dispatch_is_internal_and_explicit(self):
        router = ROUTER.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("legacyModuleId: Int? = null", router)
        self.assertIn("operation.legacyModuleId", main)
        self.assertIn("actions = sub.actions", main)
        self.assertIn("onSelectAction", main)
        self.assertIn("engine.runSub(dispatchModuleId, dispatchSubId", main)


if __name__ == "__main__":
    unittest.main()
