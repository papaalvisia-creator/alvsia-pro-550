#!/usr/bin/env python3
"""Guard that the 10-menu / 59-subtool Smart catalog stays aligned."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
catalog = (ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt").read_text(encoding="utf-8")
profile = (ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt").read_text(encoding="utf-8")
home = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/HomeScreen.kt").read_text(encoding="utf-8")
submenus = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt").read_text(encoding="utf-8")
router = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartModuleRouter.kt").read_text(encoding="utf-8")

catalog_items = [(int(i), name) for i, name in re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', catalog)]
expected_ids = list(range(1, 11))
expected_names = [
    "SMART APK", "SMART PAK", "SMART OBB", "SMART LUA", "SMART CRYPTO",
    "SMART FORENSICS", "SMART MODDING", "SMART NATIVE", "SMART WORKSPACE",
    "SMART ENGINE LAB",
]
assert [i for i, _ in catalog_items] == expected_ids
assert [name for _, name in catalog_items] == expected_names
assert len(catalog_items) == 10

profile_names = re.findall(r'ModuleChip\("[^"]*"\s*,\s*"([^"]+)"\s*\)', profile)
assert profile_names == expected_names

title_section = submenus.split("fun title(moduleId: Int)", 1)[1].split("fun forModule", 1)[0]
for module_id, name in catalog_items:
    pattern = rf'(?m)^\s*{module_id}\s*->\s*"{re.escape(name)}"\s*$'
    assert re.search(pattern, title_section), f"SubMenus.title missing: {module_id} -> {name}"

icon_section = home.split("private fun moduleIcon(id: Int)", 1)[1].split("@Composable", 1)[0]
icon_ids = [int(i) for i in re.findall(r'(?m)^\s*(\d+)\s*->\s*"', icon_section)]
assert icon_ids == expected_ids

calls = re.findall(r'SubTool\(\s*"([^"]+)"([^\n]*)', submenus)
declared_ids = [sid for sid, _ in calls]
assert len(declared_ids) == 59
assert len(set(declared_ids)) == 59
assert sum("enabled = false" not in tail for _, tail in calls) == 59
assert "10 menus / 59 unique submenu contract" in submenus
assert "10-menu / 59-subtool" in router

# The 59 enabled subtools must all resolve to a real dispatch path:
# either a native screen, a router alias, or the pending-adapter registry.
import sys
sys.path.insert(0, str(ROOT / "app/src/main/python"))
from pending_subtool_adapters import PENDING_ADAPTERS  # noqa: E402
for sid, _tail in calls:
    if "enabled = false" in _tail:
        continue
    assert (sid in PENDING_ADAPTERS
            or re.search(rf'"{re.escape(sid)}"', router)
            or f'"{sid}"' in router), f"enabled subtool has no route: {sid}"

print("MODULE CATALOG CONSISTENCY: PASS (10/10 Smart menus, 59 unique subtools, 59 enabled all routed, profile/home/router parity)")
