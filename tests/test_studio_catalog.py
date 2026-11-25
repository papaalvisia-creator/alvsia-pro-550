import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt"
MENUS = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
ROUTER = ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt"
MAIN = ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt"

EXPECTED_NAMES = [
    "SMART APK", "SMART PAK", "SMART OBB", "SMART LUA", "SMART CRYPTO",
    "SMART FORENSICS", "SMART MODDING", "SMART NATIVE", "SMART WORKSPACE",
    "SMART ENGINE LAB",
]

class SmartCatalogTests(unittest.TestCase):
    def test_ten_smart_menus_are_the_public_catalog(self):
        source = CATALOG.read_text(encoding="utf-8")
        items = re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', source)
        self.assertEqual([int(i) for i, _ in items], list(range(1, 11)))
        self.assertEqual([name for _, name in items], EXPECTED_NAMES)

    def test_public_subtools_are_exactly_59_and_unique(self):
        menus = MENUS.read_text(encoding="utf-8")
        ids = re.findall(r'SubTool\(\s*"([^"]+)"', menus)
        self.assertEqual(len(ids), 59)
        self.assertEqual(len(ids), len(set(ids)))

    def test_studio_catalog_has_complete_ten_menu_coverage(self):
        source = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/StudioCatalog.kt").read_text(encoding="utf-8")
        entries = re.findall(r'StudioItem\("([^"]+)",\s*"([^"]+)",.*?listOf\(([^)]*)\)\)', source)
        self.assertEqual(len(entries), 10)
        ids = [int(value) for _, _, raw in entries for value in re.findall(r"\d+", raw)]
        self.assertEqual(ids, list(range(1, 11)))

    def test_legacy_provider_dispatch_remains_explicit(self):
        router = ROUTER.read_text(encoding="utf-8")
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("SmartModuleRouter.backendModule", main)
        self.assertIn("SmartModuleRouter.normalizedSubId", main)
        self.assertIn(' "pak_info" -> "pak_info"', router)
        self.assertIn('"lua_t24_convert" -> "pubg_lua_convert"', router)
        self.assertIn('"zuc_decrypt" -> "dec_zuc"', router)

if __name__ == "__main__":
    unittest.main()
