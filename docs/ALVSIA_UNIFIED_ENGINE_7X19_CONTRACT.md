# ALVSIA Unified Engine — 7 Menu / 19 Submenu Contract

Status: Approved implementation target
Date: 2026-11-13
Branch: feat/alvsia-unified-engine-7x19-20261113
Base: feat/alvsia-smart-premium-v1-20261112

## Non-negotiable product contract

- Exactly **7** visible top-level menus.
- Exactly **19** visible submenu entries across those menus.
- The existing **19 legacy module IDs (1..19)** remain stable internal capability/provider identities.
- All useful legacy operations remain available inside their owning submenu as operations/actions; they must not be deleted merely to reduce the visible submenu count.
- No extra top-level menu, submenu, hidden duplicate catalog, or legacy navigation surface is permitted.
- One Unified Engine owns routing, execution lifecycle, adapters, pipelines, validation, recovery, reporting, and provider selection.
- Domain-specific engines remain specialized providers behind the Unified Engine; "one engine" means one orchestration and contract layer, not one algorithm for every file format.
- Preserve authentication, signed operation grants, SessionGate, Unaux policy, private sealed-runtime gate, Xop asset handling, TLS policy, and existing permissions/login behavior.

## Fixed menu-to-submenu-to-legacy-module mapping

| Visible menu | Submenu (one per legacy module) | Legacy module ID | Legacy module capability |
|---|---|---:|---|
| SMART LUA | SMART LUA DECOMPILER | 5 | Lua detection, analysis, decompile and conversion routing |
| SMART LUA | SMART LUA STRING RECOVERY | 15 | String restore, constant pool, cross-reference |
| SMART LUA | SMART LUA INJECT | 16 | Byte patch, hook insertion, mod/repack handoff |
| SMART LUA | SMART LUA PROTECT | 18 | Balanced/strong protection, authenticated encrypt/restore, VM wrapper |
| SMART PAK | SMART PAK UNPACK | 1 | Full extraction, index listing, info, CSV |
| SMART PAK | SMART PAK REBUILD | 2 | Repack, inject, encrypt/decrypt restore |
| SMART PAK | SMART PAK COMPACT | 3 | Delete entry, empty/compact operations |
| SMART PAK | SMART PAK DEEP ENGINE | 14 | Deep crypto/compression probes, integrity, SM4 candidate scan |
| SMART OBB | SMART OBB ENGINE | 4 | Inspect, extract, rebuild, integrity |
| SMART DATA | SMART FILE SCAN & METADATA | 6 | Strings, hashes, metadata v39 |
| SMART DATA | SMART XOR ENGINE | 12 | Single/multi-key XOR and supported legacy XOR operations |
| SMART DATA | SMART DECRYPT ENGINE | 13 | AES, SM4, SIMPLE1 and explicitly labelled compatibility transforms |
| SMART ANALYSIS | SMART SO ANALYZER | 10 | SO analysis, URL/string extraction, AES pattern analysis, safe patch workflow |
| SMART ANALYSIS | SMART JNI TRACE | 11 | Frida/JNI script generation and trace command generation |
| SMART ANALYSIS | SMART ANTI-RE AUDIT | 17 | APK, Lua, SO and source triage audits |
| WORKSPACE & REPORT | SMART WORKSPACE | 7 | Workspace lifecycle and safe cleanup |
| WORKSPACE & REPORT | SMART REPORT EXPORT | 8 | File/session report export |
| WORKSPACE & REPORT | SMART REBRAND | 9 | Auto/manual rebrand and brand scan |
| ALVSIA PRIVATE | ALVSIA PRIVATE ENGINE | 19 | Sealed private providers: Lua parse/convert, PAK manifest, private crypto and analysis utilities |

Total: 7 menus, 19 submenus, 19 legacy module IDs. Every legacy module ID must appear exactly once in this mapping.

## Unified Engine architecture and implementation status

### Implemented on this branch

`UI (7 menus / 19 submenu groups)`
→ `UnifiedEngineFacade.resolve(menuId, action)`
→ `ToolEngine.runSub(providerModuleId, operationId, ...)`
→ `PythonBridgeRunner`
→ `alvsia_bridge_impl.run_tool`
→ `existing domain/provider implementation`
→ `validated result/log + workspace output`

- `SubMenus.kt` groups the 19 stable legacy module IDs exactly once.
- Each of the 89 legacy operation declarations is retained as an action inside its owning submenu workspace.
- `UnifiedEngineFacade.kt` validates the visible-menu/provider relationship before dispatch.
- `MainActivity` sends the resolved provider ID and operation ID through the shared `ToolEngine.runSub` entry point.
- The Python bridge remains the central operation dispatcher; the old module IDs are internal provider identities, not visible navigation entries.

### Remaining work before calling the full Unified Engine complete

- Formalize a typed provider registry for all 19 modules and their 89 operations; the current facade mapping is the first routing boundary, not yet the complete provider metadata registry.
- Consolidate common progress, cancellation, resource limits, error classification, and output postconditions across all providers.
- Audit each adapter's authorization scope and verify that every operation reaches the correct implementation.
- Run real input-to-output fixtures for PAK, OBB, Lua, data, SO, and private providers; static catalog coverage is not functional proof.
- Keep operations read-only where appropriate and require atomic output plus evidence before reporting success.

The visible submenu is a capability group, not a loss of its original operations. Its internal operation selector/configuration exposes the retained actions without creating additional submenu navigation entries.

## Required provider contract

Each provider must declare:
- stable legacy module ID and supported operation IDs;
- accepted input kinds and bounded size/streaming policy;
- required authorization scope;
- output artifacts and report schema;
- cancellation/progress behavior;
- deterministic error classification;
- validation/postcondition checks;
- test fixtures and real sample acceptance evidence.

No provider may return success solely because a process exited with code 0. Success requires a validated output artifact or an explicit read-only report with evidence.

## Migration and release gates

1. Inventory every legacy operation and its current Kotlin/Python/asset/native implementation.
2. Build an explicit operation-to-provider registry; flag missing, duplicate, placeholder, or unreachable operations.
3. Implement the 7/19 catalog and nested action selection without increasing the visible submenu count.
4. Route all operations through the Unified Engine facade; keep adapters for compatible legacy implementations.
5. Rebuild only broken or unsafe providers; preserve correct algorithms and stable IDs.
6. Add contract tests for complete 1..19 coverage, unique submenu IDs, operation reachability, authorization scopes, and output validation.
7. Run Python regression tests, Android unit/compile tests, debug/release builds, Xop packaging/signing audits, and ARM64 device-level smoke tests.
8. Do not merge or call the APK final until required checks are green and PAK/Lua/OBB operations have real input-to-output evidence.

## Explicitly out of scope for this branch

- Agent installation or Agent Zero/agentes.chat work.
- Live server, autostart, panel, login, permission, TLS pin, or production data changes.
- Merging this branch into main or merging PR #19 without separate approval.
- Claiming full functionality based only on catalog coverage, static tests, or a green Gradle build.
