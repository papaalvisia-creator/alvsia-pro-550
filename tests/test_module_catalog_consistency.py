#!/usr/bin/env python3
"""Guard that the 9-menu / 33-tool Smart catalog stays aligned."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
catalog = (ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt").read_text(encoding="utf-8")
profile = (ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt").read_text(encoding="utf-8")
home = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/HomeScreen.kt").read_text(encoding="utf-8")
submenus = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt").read_text(encoding="utf-8")
router = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt").read_text(encoding="utf-8")

catalog_items = [(int(i), name) for i, name in re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', catalog)]
expected_ids = list(range(1, 10))
assert [i for i, _ in catalog_items] == expected_ids, (
    f"ToolCatalog IDs must be exactly 1..9 in order; got {[i for i, _ in catalog_items]}"
)
assert len(catalog_items) == 9, f"expected 9 catalog entries, got {len(catalog_items)}"

profile_names = re.findall(r'ModuleChip\(\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)', profile)
catalog_names = [name for _, name in catalog_items]
assert profile_names == catalog_names, (
    "ProfileScreen module labels/order diverge from ToolCatalog: "
    f"profile={profile_names!r}; catalog={catalog_names!r}"
)

title_section = submenus.split("fun title(moduleId: Int)", 1)[1].split("fun forModule", 1)[0]
for module_id, name in catalog_items:
    pattern = rf'(?m)^\s*{module_id}\s*->\s*"{re.escape(name)}"\s*$'
    assert re.search(pattern, title_section), f"SubMenus.title missing or mismatched mapping: {module_id} -> {name}"

icon_section = home.split("private fun moduleIcon(id: Int)", 1)[1].split("@Composable", 1)[0]
icon_ids = [int(i) for i in re.findall(r'(?m)^\s*(\d+)\s*->\s*"[^"]+"', icon_section)]
assert icon_ids == expected_ids, f"HomeScreen must map icon IDs 1..9 in order; got {icon_ids}"

declared_ids = re.findall(r'SubTool\(\s*"([^"]+)"', submenus)\nassert len(declared_ids) == 33, f"expected exactly 33 visible SubTool entries, got {len(declared_ids)}"\nassert len(set(declared_ids)) == 33, "public SubTool IDs must be unique"\nassert set(declared_ids) == {sid for ids in EXPECTED.values() for sid in ids}, "SubMenus IDs diverge from the locked 9x33 catalog"
assert "33 sub-tools" in submenus
assert "9 menus / 33 sub-tools" in router or "9-menu / 33-tool" in router

print("MODULE CATALOG CONSISTENCY: PASS (9/9 Smart menus, 33 sub-tools, profile/home/submenu/router parity)")
