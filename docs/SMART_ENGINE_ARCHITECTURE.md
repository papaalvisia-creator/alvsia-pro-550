# ALVSIA PRO Smart Engine Architecture

## Public module surface

The Android home/profile catalog exposes seven modules only:

1. SMART LUA
2. SMART PAK
3. SMART OBB
4. SMART DATA
5. SMART ANALYSIS
6. WORKSPACE & REPORT
7. ALVSIA PRIVATE

Legacy module IDs remain stable provider/authentication identifiers. They are not a second public catalog. `SmartModuleRouter` is the only UI-to-provider mapping point.

## SMART LUA — exactly four public engines

The Lua submenu exposes exactly:

- SMART LUA DECOMPILER
- SMART LUA PROTECT
- SMART LUA COMPILER / RECOMPILER
- SMART LUA INJECT

Detector, routing, analysis, Universal IR/provider adapters, recovery, protection profiles, encryption/restore, VM protection, compiler selection, patch/hook/repack, validation and legacy fallback remain internal to the selected engine. Do not add these internal stages as public menu items.

Internal work configuration:
- `WORK/lua_protect_config.json`: `mode` = profile/encrypt/restore/vm; profile = balanced/strong.
- `WORK/lua_protect_key.txt`: 32-byte hex key for the authenticated ALVLUA1 compatibility format.
- `WORK/lua_inject_config.json`: mode = patch/hook/repack and the corresponding provider fields.
- `WORK/lua_patch.json` remains accepted for the legacy patch workflow.

ALVLUA1 encryption and restore are streamed in bounded chunks. Restore writes to a temporary file and publishes plaintext only after GCM authentication succeeds.

## SMART PAK and SMART OBB

Both use `smart_archive_engine.execute` as their shared archive facade. The facade detects archive type, routes to the retained PAK/OBB providers, applies safe extraction limits, rebuilds to a new output artifact, and emits integrity reports. It never overwrites the selected input.

PAK modification tree: `WORK/MOD` or `OUT/PAK/<base-name>`.
OBB modification tree: `OUT/OBB/<base-name>` or `WORK/OBB`.

## SMART DATA

`smart_data_engine.execute` centralizes auto recovery, XOR probing, SM4 candidate search and metadata v39 decode. Existing string recovery remains available through the registered legacy provider adapter. The SM4 4.7-modders candidate set is centralized in `sm4_secret_registry.py` and validated as 23 unique values. SM4 scans process .so and .bin inputs in bounded chunks with overlap handling.

## Safety and validation invariants

- Never claim success without a real output artifact or a completed report.
- Preserve original input files; write new artifacts atomically where supported.
- Keep large binary scans streaming and bounded-memory.
- Keep authentication, signed operation grants, Unaux policy, session gates, and sealed private-tool restrictions intact.
- Legacy providers may be used as adapters/fallbacks but must not become duplicate public menus.
- The compact catalog, SmartModuleRouter, bridge dispatch, regression fixtures and release audits must agree before release.
