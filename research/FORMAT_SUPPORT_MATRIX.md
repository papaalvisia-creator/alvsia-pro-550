# FORMAT SUPPORT MATRIX — ALVSIA SMART PREMIUM 6.0.0

Status legend: **SUPPORTED** (verified end-to-end in this session), **PARTIAL**
(parses but output not fully valid), **BLOCKED** (requires authorized material),
**UNSUPPORTED** (custom/protected, not standard).

## Archive / container formats

| Format | Detection | Parse | Extract | Repack | Status | Evidence |
|---|---|---|---|---|---|---|
| Tencent PAK v14 (encrypted index) | magic + encrypted index | YES | YES | YES | **SUPPORTED** | 5 corpus PAKs parsed; 21752 2/2, 21756 5/7, core_patch 163/239 |
| Tencent PAK v14 (SM4-encrypted entries) | per-entry `encrypted` flag | YES | NO | NO | **BLOCKED** | 76+2 entries fail closed: "SM4 candidate material is not authorized/supplied" |
| ZIP (deflate) | `PK\x03\x04` | YES | YES | YES | **SUPPORTED** | 2 corpus ZIPs (`file .zip` 77 MB, PUBG Lua zip 56 MB) |
| Zstandard frame | `28 b5 2f fd` | YES | YES | n/a | **SUPPORTED** | PAK 21756 zstd block decode |
| ZLIB / raw DEFLATE | `78 xx` / heuristic | YES | YES | n/a | **SUPPORTED** | `tests/test_pak_extraction.py` |
| GZIP | `1f 8b` | YES | YES | n/a | **SUPPORTED** | archive_engine |
| LZ4 / LZMA | frame magic | partial | partial | n/a | **PARTIAL** | codec present, limited corpus coverage |

## Lua formats

| Format | Detection | Parse | Decompile | Status | Evidence |
|---|---|---|---|---|---|
| Lua 5.3 standard bytecode | `\x1bLuaS` | YES | YES (structurally valid) | **SUPPORTED** | Regression `test_lua53_standard_decompile.py`; output recompiles with luac5.3 |
| Lua 5.1 bytecode | `\x1bLuaQ` | partial | partial | **PARTIAL** | parser exists, no corpus sample |
| Lua 5.4 bytecode | `\x1bLuaT` | no | no | **UNSUPPORTED** | not targeted |
| LuaJIT bytecode | `\x1bLJ` | partial | partial | **PARTIAL** | `luajit_decompiler.py` present |
| Luau bytecode | varint header | partial | partial | **PARTIAL** | `multi_format.py` |
| Lua 5.3 text source | heuristic | YES | passthrough | **SUPPORTED** | byte-exact passthrough |
| PUBG Mobile protected Lua 5.3 | `\x1bLuaS` + encrypted source/opcodes | parse OK | output garbage | **PARTIAL / UNSUPPORTED SEMANTICS** | 23 extracted files; 16 outputs syntax-invalid, 4 structurally valid, source strings encrypted (`Q?j$*...`) |
| Hybrid lineinfo (byte+abslineinfo) | header ok, debug mismatch | YES (fallback mode) | partial | **PARTIAL** | `lineinfo_mode="byte_abs"` fallback |

## Key finding (this session)

The pure-Python Lua 5.3 decompiler previously **failed to parse any genuine
Lua 5.3 bytecode** because `load_proto` used the Lua **5.4** debug layout
(1-byte line deltas + `abslineinfo`). Authoritative Lua 5.3 `lundump.c`
stores `lineinfo` as `int[ ]` (4 bytes each) and has **no** `abslineinfo`.
This was fixed (`lua_engine/decompiler53.py`) and locked with a regression
test. Standard Lua 5.3 chunks now parse and produce recompilable source.

## Residual limitations (honest)

- PUBG Mobile game Lua uses a custom/protected VM; header says "Lua 5.3" but
  opcodes/constants are remapped/encrypted. Decompilation yields partial,
  often syntax-invalid output. This is classified honestly as PARTIAL, never
  as success.
- SM4-encrypted PAK entries cannot be extracted without authorized key
  material. This is a **material blocker**, not a code defect, and is never
  bypassed.
