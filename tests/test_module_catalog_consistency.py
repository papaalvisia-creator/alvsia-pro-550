#!/usr/bin/env python3
"""Guard the seven-menu / expanded-submenu Unified Engine contract."""
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
assert len(legacy_ids) == 19, f"expected exactly 19 legacy submenu groups, got {len(legacy_ids)}"
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
facade = (ROOT / "app/src/main/java/com/alvsia/pro/tool/UnifiedEngineFacade.kt").read_text(encoding="utf-8")
assert "action.legacyModuleId" in facade
assert "UnifiedEngineFacade.resolve" in main
assert "actions = sub.actions" in main and "onSelectAction" in main

workspace = (ROOT / "app/src/main/java/com/alvsia/pro/ui/tool/ToolWorkspaceScreen.kt").read_text(encoding="utf-8")
planner = (ROOT / "app/src/main/java/com/alvsia/pro/tool/SmartEnginePlanner.kt").read_text(encoding="utf-8")
assert "SELECT OPERATION" not in workspace, "legacy operations must not appear as a nested picker"
assert "showActionPicker" not in workspace
assert "SmartEnginePlanner.resolve" in workspace
assert "fun plan(" in planner
assert "SmartEnginePlanner.plan(sub, operation" in main
assert "for ((index, stageRoute) in routes.withIndex())" in main
for provider_id in range(1, 21):
    assert f"            {provider_id} ->" in planner, f"Smart planner missing provider {provider_id}"
assert "detection?.suggestedSubtool" in planner
asset_group_calls = [line for line in group_section.splitlines() if line.strip() == "assetGroup()"]
assert len(asset_group_calls) == 1
assert len(legacy_ids) + len(asset_group_calls) == 20
assert "SMART ASSET MODDING ENGINE" in submenus
assert "asset_smart" in submenus
assert "legacyModuleId = 20" in submenus
assert '20 -> choose("asset_smart")' in planner
assert "providerModuleId" in facade

print("UNIFIED CATALOG: PASS (7 menus, 20 submenus: 19 legacy providers + Smart Asset provider, 89 retained legacy operations; no nested operation picker)")
assert len(asset_group_calls) == 1
assert len(legacy_ids) + len(asset_group_calls) == 20
assert "SMART ASSET MODDING ENGINE" in submenus
assert "asset_smart" in submenus
assert "legacyModuleId = 20" in submenus
assert '20 -> choose("asset_smart")' in planner
assert "providerModuleId" in facade

print("UNIFIED CATALOG: PASS (7 menus, 20 submenus: 19 legacy providers + Smart Asset provider, 89 retained legacy operations; no nested operation picker)")
