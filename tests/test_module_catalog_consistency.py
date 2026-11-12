#!/usr/bin/env python3
"""Guard that the compact seven-module Smart catalog stays aligned."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
catalog = (ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt").read_text(encoding="utf-8")
profile = (ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt").read_text(encoding="utf-8")
home = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/HomeScreen.kt").read_text(encoding="utf-8")
submenus = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt").read_text(encoding="utf-8")

catalog_items = [(int(i), name) for i, name in re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', catalog)]
expected_ids = list(range(1, 8))
assert [i for i, _ in catalog_items] == expected_ids, (
    f"ToolCatalog IDs must be exactly 1..7 in order; got {[i for i, _ in catalog_items]}"
)
assert len(catalog_items) == 7, f"expected 7 catalog entries, got {len(catalog_items)}"

profile_names = re.findall(r'ModuleChip\(\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)', profile)
catalog_names = [name for _, name in catalog_items]
assert profile_names == catalog_names, (
    "ProfileScreen module labels/order diverge from ToolCatalog: "
    f"profile={profile_names!r}; catalog={catalog_names!r}"
)

title_section = submenus.split("fun title(moduleId: Int)", 1)[1].split("fun forModule", 1)[0]
for module_id, name in catalog_items:
    expected = f'{module_id}  -> "{name}"' if module_id < 10 else f'{module_id} -> "{name}"'
    # Whitespace-insensitive mapping check.
    pattern = rf'(?m)^\s*{module_id}\s*->\s*"{re.escape(name)}"\s*$'
    assert re.search(pattern, title_section), f"SubMenus.title missing or mismatched mapping: {module_id} -> {name}"

icon_section = home.split("private fun moduleIcon(id: Int)", 1)[1].split("@Composable", 1)[0]
icon_ids = [int(i) for i in re.findall(r'(?m)^\s*(\d+)\s*->\s*"[^"]+"', icon_section)]
assert icon_ids == expected_ids, f"HomeScreen must map icon IDs 1..7 in order; got {icon_ids}"


# The private module must be fully wired from its UI submenu into the sealed bridge.
private_submenu = submenus.split("7 -> listOf(", 1)[1].split("\n    )", 1)[0]
private_ids = re.findall(r'SubTool\(\s*"([^"]+)"', private_submenu)
assert len(private_ids) == 3, f"expected 3 private providers, got {len(private_ids)}"
bridge_private = (ROOT / "app/src/main/python/alvsia_bridge_impl.py").read_text(encoding="utf-8")
dispatch_section = bridge_private.split("ALVSIA PRIVATE TOOL — sealed runtime required", 1)[1].split("# ── ZUC-128 decrypt", 1)[0]
for sub_id in private_ids:
    assert f'"{sub_id}"' in dispatch_section, f"private subtool is not registered in sealed bridge: {sub_id}"
assert 'ALVSIA_SEALED_RUNTIME' in dispatch_section, "private module must retain its sealed-runtime gate"

print("MODULE CATALOG CONSISTENCY: PASS (7/7 Smart modules, profile/home/submenu parity, 3 private providers wired to sealed bridge)")
