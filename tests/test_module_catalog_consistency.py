#!/usr/bin/env python3
"""Guard the exact seven-menu / nineteen-submenu Unified Engine contract."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
catalog = (ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt").read_text(encoding="utf-8")
profile = (ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt").read_text(encoding="utf-8")
home = (ROOT / "app/src/main/java/com/alvsia/pro/ui/home/HomeScreen.kt").read_text(encoding="utf-8")
main = (ROOT / "app/src/main/java/com/alvsia/pro/MainActivity.kt").read_text(encoding="utf-8")
submenus = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt").read_text(encoding="utf-8")
bridge_impl = (ROOT / "app/src/main/python/alvsia_bridge_impl.py").read_text(encoding="utf-8")

catalog_items = [(int(i), name) for i, name in re.findall(r'ToolItem\(\s*(\d+)\s*,\s*"([^"]+)"', catalog)]
expected_ids = list(range(1, 8))
assert [i for i, _ in catalog_items] == expected_ids
assert len(catalog_items) == 7

profile_names = re.findall(r'ModuleChip\(\s*"[^"]*"\s*,\s*"([^"]+)"\s*\)', profile)
catalog_names = [name for _, name in catalog_items]
assert profile_names == catalog_names

title_section = submenus.split("fun title(moduleId: Int)", 1)[1].split("fun forModule", 1)[0]
for module_id, name in catalog_items:
    pattern = rf'(?m)^\s*{module_id}\s*->\s*"{re.escape(name)}"\s*$'
    assert re.search(pattern, title_section), f"SubMenus.title mismatch: {module_id} -> {name}"

icon_section = home.split("private fun moduleIcon(id: Int)", 1)[1].split("@Composable", 1)[0]
icon_ids = [int(i) for i in re.findall(r'(?m)^\s*(\d+)\s*->\s*"[^"]+"', icon_section)]
assert icon_ids == expected_ids

group_section = submenus.split("fun forModule(moduleId: Int)", 1)[1].split("private fun moduleGroup", 1)[0]
legacy_ids = [int(x) for x in re.findall(r'moduleGroup\(\s*(\d+)\s*,', group_section)]
assert len(legacy_ids) == 19, f"expected exactly 19 submenu groups, got {len(legacy_ids)}"
assert sorted(legacy_ids) == list(range(1, 20)), f"legacy module coverage mismatch: {legacy_ids}"

legacy_section = submenus.split("private fun legacyOperations", 1)[1]
operation_ids = re.findall(r'SubTool\(\s*"([a-zA-Z0-9_]+)"', legacy_section)
assert len(operation_ids) == 89, f"expected 89 retained legacy operations, got {len(operation_ids)}"
assert len(operation_ids) == len(set(operation_ids)), "legacy operation IDs must be unique"

private_ids = [x for x in operation_ids if x.startswith("priv_")]
assert len(private_ids) == 12, f"expected all 12 private operations, got {len(private_ids)}"
for sub_id in private_ids:
    assert f'"{sub_id}"' in bridge_impl, f"private operation missing from bridge: {sub_id}"
assert "ALVSIA_SEALED_RUNTIME" in bridge_impl
assert "operation.legacyModuleId" in main
assert "actions = sub.actions" in main and "onSelectAction" in main

print("UNIFIED CATALOG: PASS (7 menus, 19 submenus, 19 legacy modules, 89 retained operations)")
