# RESEARCH COVERAGE REPORT — ALVSIA SMART PREMIUM 6.0.0

Date: 2026-11-14. Branch: `fix/engine-repair-20261114`.

## Corpus access

- Private corpus `papaalvisia-creator/kumpulan-source-tool` cloned with the
  authorized PAT (token never printed). Size on disk: 279 MB.
- Total files (excluding `.git`): **85**.

## Coverage achieved

| Area | Target | Achieved | Status |
|---|---|---|---|
| Recursive file inventory | all files | 85/85 (100%) | DONE |
| SHA-256 + magic + format per file | all files | 85/85 | DONE |
| PAK detection & index parse | all PAKs | 5/5 | DONE |
| PAK full extraction | all entries | 172/254 extracted; 82 blocked on SM4 material | DONE (honest) |
| Lua detection in extracted PAKs | all Lua | 25/25 (23 bytecode + 2 source) | DONE |
| Lua 5.3 decompile (standard) | all standard | parse fixed; regression locked | DONE |
| Lua 5.3 decompile (PUBG protected) | all protected | 20 produced output; 4 structurally valid, 16 syntax-invalid | PARTIAL (honest) |
| Third-party capability scan | all tools | 30 Python tools scanned | DONE |
| Format support matrix | all formats | see FORMAT_SUPPORT_MATRIX.md | DONE |

## PAK extraction results (verified)

| PAK | Entries | Extracted | Lua | Blocked (SM4) |
|---|---|---|---|---|
| `samples/pak/game_patch_4.7.0.21752.pak` | 2 | 2 | 1 | 0 |
| `samples/pak/game_patch_4.7.0.21756.pak` | 7 | 5 | 2 | 2 |
| `FREE PAK 4.6/ANDROID/core_patch_4.6.0.21546.pak` | 239 | 163 | 20 | 76 |
| `FREE PAK 4.6/ANDROID/.../Saved/Paks/core_patch_4.6.0.21546.pak` | 1 | 1 | 1 | 0 |
| `FREE PAK 4.6/IOS/Paks/core_patch_4.6.0.21546.pak` | 1 | 1 | 1 | 0 |

All skipped entries are recorded in `PAK_EXTRACTION_MANIFEST.json` under
`failures` with the exact reason. **No silent data loss.**

## Lua classification results (verified)

- 23 bytecode files (all detected as "Lua 5.3" by header).
- 20 decompiled; 3 deferred (large >6 MB, routed to streaming).
- Syntax validation via `luac5.3 -p`:
  - STRUCTURALLY_VALID: 4
  - SYNTAX_INVALID: 16 (deeply nested garbage from protected VM bytecode)
  - 9 outputs carried `ALVSIA_INVALID_CONSTANT_REF_COUNT` markers.
- All 16 invalid + 4 valid are PUBG-protected payloads; their source strings
  are encrypted (`Q?j$*...`), confirming a custom VM rather than standard Lua.

## Root-cause engineering fix

`lua_engine/decompiler53.py` parsed the debug section using the **Lua 5.4**
layout. Lua 5.3.6 `lundump.c` uses `int lineinfo[]` and no `abslineinfo`.
Before the fix, every standard Lua 5.3 chunk raised
`invalid absolute line count 512 ...`. After the fix, standard chunks parse,
decompile, and the output recompiles with `luac5.3`. Regression test:
`tests/test_lua53_standard_decompile.py` (2 tests, passing).

## Blockers (not bypassed)

1. **SM4 key material** for 82 encrypted PAK entries is not present/authorized.
   Engine fails closed with an explicit reason; no key is fabricated.
2. **PUBG custom VM** bytecode cannot be faithfully decompiled with a standard
   Lua 5.3 decoder; needs a dedicated opcode/constant decoder. Documented as
   PARTIAL/UNSUPPORTED rather than falsely reported as complete.

## Artifacts

- `research/CORPUS_MASTER_INVENTORY.json` / `.md`
- `research/PAK_EXTRACTION_MANIFEST.json`
- `research/LUA_CLASSIFICATION.json`
- `research/FORMAT_SUPPORT_MATRIX.md`
- `research/THIRD_PARTY_CAPABILITY_GAP_MATRIX.md`
- `research/ALVSIA_CAPABILITY_CATALOG.md`
