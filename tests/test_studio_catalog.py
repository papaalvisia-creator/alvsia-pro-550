import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "app/src/main/java/com/alvsia/pro/ui/home/StudioCatalog.kt"


class StudioCatalogTests(unittest.TestCase):
    def test_seven_studios_cover_each_legacy_module_exactly_once(self):
        source = CATALOG.read_text(encoding="utf-8")
        entries = re.findall(
            r'StudioItem\("([^"]+)",\s*"([^"]+)",.*?listOf\(([^)]*)\)\)',
            source,
        )
        self.assertEqual(len(entries), 7, "The UI catalog must expose exactly seven Studios")

        ids = []
        studio_ids = []
        for studio_id, title, raw_ids in entries:
            studio_ids.append(studio_id)
            ids.extend(int(value) for value in re.findall(r"\d+", raw_ids))
            self.assertTrue(title.strip(), f"Studio {studio_id} needs a visible title")

        self.assertEqual(len(set(studio_ids)), 7, "Studio identifiers must be unique")
        self.assertEqual(len(ids), 19, "Every legacy module must be assigned")
        self.assertEqual(len(set(ids)), 19, "A module must not be assigned twice")
        self.assertEqual(set(ids), set(range(1, 20)), "Module IDs 1..19 must remain reachable")


    def test_declared_subtool_inventory_has_unique_ids(self):
        menus = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt").read_text(encoding="utf-8")
        subtool_ids = re.findall(r'SubTool\(\s*"([^"]+)"', menus)
        self.assertEqual(len(subtool_ids), 86, "Update the documented sub-tool inventory when tools change")
        self.assertEqual(len(set(subtool_ids)), 86, "Sub-tool IDs must be unique")
        self.assertIn("metadata_v39_decode", subtool_ids)

    def test_studio_navigation_keeps_legacy_module_dispatch(self):
        home = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/HomeScreen.kt").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
        studio = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/StudioScreen.kt").read_text(encoding="utf-8")

        self.assertIn("StudioCatalog.all", home)
        self.assertIn("StudioCatalog.moduleIds(studio)", studio)
        self.assertIn("moduleId = t.id", main)
        self.assertIn("SubMenus.forModule(moduleId)", main)
        self.assertIn("engine.runSub(moduleId, sub.id, uri, extra)", main)


if __name__ == "__main__":
    unittest.main()
