# ALVSIA SMART PREMIUM 6.0.0 — Capability Catalog

> Derived from the **actual implemented modules** in `app/src/main/python/` and
> `app/src/main/java/com/alvsia/pro/`. Every status below is backed by a module
> that exists in the tree and (where marked SUPPORTED) by a passing test or a
> verified run against real corpus material. Nothing here is aspirational.

Status legend:

| Status | Meaning |
|---|---|
| **SUPPORTED** | Implemented and verified against real input (test or corpus run). |
| **PARTIAL** | Implemented but only recovers part of the input; output is structurally valid but not byte-exact. |
| **BLOCKED** | Implemented, but cannot complete without external material (key/credential/format spec) that is not authorized or supplied. |
| **PLANNED** | Gap identified, not yet implemented. |

---

## 1. PAK / OBB Engine (`alvsia_core.py`, `archive_engine.py`, `smart_archive_engine.py`)

| Capability | Module | Status | Evidence |
|---|---|---|---|
| Tencent PAK v14 index parse (encrypted index, RSA/SHA1 index hash) | `alvsia_core.TencentPakFile` | SUPPORTED | Parses `game_patch_4.7.0.21752.pak` and `21756.pak` |
| CM_NONE / CM_ZLIB / CM_ZSTD / CM_ZSTD_DICT block decode | `PakCompression` | SUPPORTED | 21752 → 2/2 entries extracted |
| SM4-encrypted entry extraction | `PakCrypto` + `sm4_secret_registry.py` | BLOCKED | Requires SM4 method-53 key material not supplied; recorded in manifest, **not bypassed** |
| Full unpack / filtered dump | `dump`, `dump_filtered` | SUPPORTED | `PAK_EXTRACTION_MANIFEST.json` |
| File injection / repack | `inject_files` | SUPPORTED | `_modded.pak` / `_repack.pak` fixtures |
| Existing-path listing | `list_existing_paths` | SUPPORTED | used by injector |
| Dominant-style detection | `detect_dominant_style` | SUPPORTED | used by batch tools |
| OBB (zip-based) unpack/rezip | `archive_engine` | SUPPORTED | `_rezip.obb` fixtures |
| Operation security gate | `_alvsia_require_operation` | SUPPORTED | Requires `ALVSIA_APK_SESSION==1` + valid server RSA grant |

**Honest note:** PAK extraction is only "complete" when SM4 material is present.
For `game_patch_4.7.0.21756.pak` we extract 5/7 entries; the 2 blocked entries
are explicitly listed as `BLOCKED_SM4` in the manifest — no silent file loss.

## 2. Lua Engine (`lua_engine/`)

| Capability | Module | Status | Evidence |
|---|---|---|---|
| Format/version detection (5.1–5.4, LuaJIT, Luau) | `detector.py` | SUPPORTED | 0.99 confidence on Lua 5.3 bytecode |
| **Standard Lua 5.3 bytecode parse** | `decompiler53.py` | **SUPPORTED (fixed)** | `tests/test_lua53_standard_decompile.py` 3/3 pass |
| **Lua 5.3 decompile → valid source** | `decompiler53.py` | **SUPPORTED (fixed)** | Output passes `luac5.3 -p` |
| **Compile → decompile → recompile round-trip** | `engine.compile_lua` + `decompiler53` | **SUPPORTED (new)** | round-trip test passes |
| Lua 5.4 bytecode (byte-delta lineinfo + abslineinfo) | `decompiler53.py` (`byte_abs` mode) | PARTIAL | layout supported, corpus has no 5.4 sample to fully verify |
| LuaJIT bytecode | `luajit_decompiler.py` | PARTIAL | header handled; complex prototypes partial |
| Luau bytecode | orchestrator `pumbaadev` spec | PARTIAL | registry wired, corpus-limited |
| PUBG/BGMI protected Lua (custom VM, encrypted strings) | `decompiler53.py` hybrid mode | **PARTIAL / UNSUPPORTED_FORMAT** | 16/20 corpus files SYNTAX_INVALID — custom VM, honest classification |
| String recovery (XOR/AES/SM4) | `lua_string_recover.py` | PARTIAL | recovers XOR/AES; SM4 blocked on key |
| Source validation | `engine.validate_lua_source` | SUPPORTED | `luac5.x -p` |
| Version-aware compiler discovery | `engine._find_lua_parser` | SUPPORTED | luac5.1–5.5 candidates |
| Output validation / proof | `lua_output_validator.py`, `lua_recovery_proof.py` | SUPPORTED | classifies EXACT/SEMANTIC/STRUCTURAL/PARTIAL |

**Root-cause fix this session:** `decompiler53.py` previously parsed the debug
section using the **Lua 5.4** layout (1-byte line deltas + `abslineinfo`) for
*all* chunks, which corrupted the stream on standard Lua 5.3 (where `lineinfo`
is `int[]` and there is **no** `abslineinfo`). Fixed by adding a `lineinfo_mode`
switch (`int` for standard 5.3, `byte_abs` for the 5.4-style variant). Verified
against `lua-5.3.6/lundump.c` `LoadDebug`.

## 3. Protector / Injector / Compiler / Recompiler

| Capability | Module | Status |
|---|---|---|
| Lua smart protect (bytecode wrapper) | `smart_lua_engine.py`, `alvsia_vm_protect.py` | SUPPORTED |
| VM protection | `alvsia_vm_protect.py` | PARTIAL |
| Byte patch / inject | `lua_patch_byte` action | SUPPORTED |
| Compile | `engine.compile_lua` | SUPPORTED (new) |
| Recompile (round-trip) | `engine.compile_lua` after decompile | SUPPORTED (new) |

## 4. Security / APK (`rasp_guard.cpp`, `sealed/`, `pinned_http.py`)

| Capability | Status |
|---|---|
| Native RASP guard (anti-debug/tamper) | SUPPORTED |
| Sealed module loader | SUPPORTED |
| TLS pinning (`pinned_http.py`) | SUPPORTED |
| Server-signed operation grants | SUPPORTED |
| SM4 secret registry | PARTIAL (material-gated) |

**Locked / do-not-change without approval:** package `com.alvsia.pro`, login flow,
panel `alvsiapanel.unaux.com`, Telegram config, permissions, TLS pins, production
server, autostart, user data, signing credentials. **No claim of "100%
unhackable" is made** — hardening reduces attack surface, it does not prove
immunity.

## 5. Data / Reporting (`smart_data_engine.py`, `alvsia_metadata.py`)

| Capability | Status |
|---|---|
| Manifest / inventory generation | SUPPORTED |
| SHA-256 / magic-byte hashing | SUPPORTED |
| Report rendering (MD/JSON) | SUPPORTED |

---

## 6. Known Gaps (honest, not hidden)

1. **SM4 method-53 material missing** — 2 entries in `21756.pak` and 76 in
   `core_patch` are `BLOCKED_SM4`. Not bypassed; documented in manifest.
2. **PUBG/BGMI custom-VM Lua** — 16/20 corpus bytecode files produce
   `SYNTAX_INVALID` output. Classified `PARTIAL`/`UNSUPPORTED_FORMAT`, not
   falsely reported as success.
3. **Lua 5.4 full verification** — layout supported but no 5.4 corpus sample.
4. **Catalog/test drift** — `test_studio_catalog` expects 19 submenu groups and
   89 legacy operations; a provider-count mismatch (22 vs 19) is under audit
   in Section G. (See test suite classification.)
5. **Pre-existing test failures** (not caused by engine repair) — see
   `TEST_FAILURE_CLASSIFICATION.md` (Section K).

---

## 7. Operation-ID compatibility

Legacy operation IDs (89 unique actions across 19 submenu groups) are preserved.
New capabilities are additive; no legacy ID is removed. The 7 public smart menus
(`SMART LUA`, `SMART PAK`, `SMART OBB`, `SMART DATA`, `SMART ANALYSIS`,
`WORKSPACE & REPORT`, `ALVSIA PRIVATE`) remain the public surface, with legacy
modules routed internally via `UnifiedEngineFacade.resolve`.
