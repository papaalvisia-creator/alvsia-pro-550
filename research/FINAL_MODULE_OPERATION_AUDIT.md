> **HISTORICAL BASELINE — NOT CURRENT RELEASE STATUS.** This report records validation for engine commit `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e` and the historical Final Release Pipeline run `43585187257`. It remains evidence only for that exact source commit and artifact. It does **not** describe the current PR #25 HEAD or the APK currently being built. For live status and archive provenance, see [DELIVERABLE_ARCHIVE_AUDIT_20261114.md](DELIVERABLE_ARCHIVE_AUDIT_20261114.md) and [PR #25](https://github.com/papaalvisia-creator/alvsia-pro-550/pull/25). Do not treat this historical report as proof that the current branch release is complete.

---

# FINAL MODULE & OPERATION AUDIT — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit:** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Scope:** menu surface, submenu grouping, legacy provider dispatch, operation-ID coverage, and least-privilege grants.

## 1. Public menu surface — 7 Smart menus

Source: `app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt` (verified by
`tests/test_studio_catalog.py::test_seven_smart_menus_are_the_public_catalog`).

| # | Menu | One-line role |
|---|---|---|
| 1 | SMART LUA | decompile · analyze · protect · compile/recompile · inject |
| 2 | SMART PAK | detect · inspect · unpack · modify · repack · integrity |
| 3 | SMART OBB | detect · extract · modify · rebuild · integrity |
| 4 | SMART DATA | XOR · AES · SM4 · strings · metadata recovery |
| 5 | SMART ANALYSIS | SO · URL · JNI trace · APK/Lua audit |
| 6 | WORKSPACE & REPORT | workspace · hash · reports |
| 7 | ALVSIA PRIVATE | private analysis providers |

## 2. Submenu grouping — 22 visible submenus

19 legacy module groups + 3 new capability groups = **22 visible submenus**
(`SubMenus.forModule`). The docstring in `SubMenus.kt` ("22 visible Smart submenu
groups") matches the code exactly.

| Menu | Legacy module groups | Capability group |
|---|---|---|
| 1 SMART LUA | 5 Decompiler, 15 String Recovery, 16 Inject, 18 Protect | — |
| 2 SMART PAK | 1 Unpack, 2 Rebuild, 3 Compact, 14 Deep Engine | smart_asset_modding |
| 3 SMART OBB | 4 OBB Engine | — |
| 4 SMART DATA | 6 File Scan, 12 XOR, 13 Decrypt | smart_crypto_compression |
| 5 SMART ANALYSIS | 10 SO Analyzer, 11 JNI Trace, 17 Anti-RE Audit | smart_binary_forensics |
| 6 WORKSPACE & REPORT | 7 Workspace, 8 Report Export, 9 Rebrand | — |
| 7 ALVSIA PRIVATE | 19 Private Engine | — |

## 3. Legacy providers — 19, each registered exactly once

Source: `UnifiedEngineFacade.kt` mapping (verified by
`test_unified_facade_registers_each_legacy_provider_exactly_once`).

```
1 -> {5,15,16,18}   2 -> {1,2,3,14}   3 -> {4}      4 -> {6,12,13}
5 -> {10,11,17}     6 -> {7,8,9}      7 -> {19}
```

Union = {1..19}, each appearing exactly once → **19 providers, no duplicates**.
This resolves the earlier "22 vs 19" mismatch: the facade had listed 22 slots
with modules 6/10/14 duplicated; it is now aligned to the 19 real providers.

## 4. Operation IDs — 89 legacy operations preserved

Source: `SubMenus.legacyOperations` (verified by
`test_exactly_nineteen_submenu_groups_cover_all_legacy_modules`).

- **89 unique legacy operation IDs** across the 19 groups — all preserved, none
  removed, none duplicated.
- **14 additional capability action entries** in the 3 new capability groups:
  - `smart_asset_modding`: asset_extract, asset_integrity, asset_rebuild, asset_inject (4)
  - `smart_crypto_compression`: crypto_probe, transform_probe, crypto_sm4, crypto_zstd, crypto_selftest (5)
  - `smart_binary_forensics`: binary_strings, binary_hash, binary_endpoints, binary_xor_probe, binary_behavior_triage (5)
- **Total SubTool action entries = 103** (89 legacy + 14 capability). New
  capabilities are purely additive; no legacy ID is dropped.

## 5. Least-privilege operation grants

Source: `OperationGrants.kt`. One JWT grant per operation, mapped to a small
allowlist:

```
pak_tools, obb_tools, skin_obb, lua_tools, file_scan, workspace,
export_report, rebrand, so_analyzer, frida_tracer, xor_suite,
decrypt_engine, string_recover, lua_inject, anti_re_audit,
lua_protector, alvsia_private_tool, game_patch, apk_audit
```

That is **19 allowlisted operations**. `obtainAndInstall` refuses any operation
not in the set ("operation is not allowlisted") and refuses if the panel grant is
rejected or the engine rejects the JWT. No wildcard, no implicit trust.

## 6. Dispatch integrity

`SmartModuleRouter` carries `legacyModuleId: Int? = null`; `MainActivity` routes
through `UnifiedEngineFacade.resolve` and `SmartEnginePlanner.plan(sub,
operation, …)`, then `engine.runSub(...)`. `ToolWorkspaceScreen` no longer shows a
manual "SELECT OPERATION" selector — routing is explicit and internal. All of
these are asserted by `test_legacy_provider_dispatch_is_internal_and_explicit`.

## 7. Audit findings

| Check | Result |
|---|---|
| 7 public menus | PASS |
| 22 visible submenus (19 legacy + 3 capability) | PASS |
| 19 providers, no duplicate | PASS |
| 89 legacy operation IDs preserved & unique | PASS |
| 19 allowlisted grant operations | PASS |
| No implicit/wildcard grant | PASS |
| Internal explicit dispatch | PASS |

## 8. Verdict

The menu/operation surface is **consistent and audited**: 7 menus, 22 submenus,
19 providers, 89 legacy operations (+14 additive capability actions), 19
least-privilege grants. The historical 22-vs-19 provider mismatch is resolved.
Status: **PASS.**
