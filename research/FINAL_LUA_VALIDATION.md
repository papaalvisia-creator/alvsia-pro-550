> **HISTORICAL BASELINE — NOT CURRENT RELEASE STATUS.** This report records validation for engine commit `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e` and the historical Final Release Pipeline run `43585187257`. It remains evidence only for that exact source commit and artifact. It does **not** describe the current PR #25 HEAD or the APK currently being built. For live status and archive provenance, see [DELIVERABLE_ARCHIVE_AUDIT_20261114.md](DELIVERABLE_ARCHIVE_AUDIT_20261114.md) and [PR #25](https://github.com/papaalvisia-creator/alvsia-pro-550/pull/25). Do not treat this historical report as proof that the current branch release is complete.

---

# FINAL LUA VALIDATION — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit:** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Scope:** Smart Lua decompiler pipeline — detection, parse, decompile, syntax validation, bounded-memory streaming for large chunks, and honest per-file status classification.

## 1. Honest status vocabulary

Every Lua file receives exactly one of the following statuses. No file is ever
reported as `EXACT_SOURCE_RECOVERY` unless its output recompiles byte-for-byte
equivalent; nothing is falsely promoted.

| Status | Meaning |
|---|---|
| **EXACT_SOURCE_RECOVERY** | Output recompiles and matches the original chunk semantically and structurally. |
| **ROUNDTRIP_VERIFIED** | Output recompiles with `luac5.3` without error (structural round-trip). |
| **SEMANTICALLY_VALID** | Parses and passes a semantic differential oracle. |
| **STRUCTURALLY_VALID** | `luac5.3` accepts the output as valid Lua. |
| **PARTIAL_RECOVERY** | Decompiler produced output but it is not fully valid; recovery artifacts (strings/constants) still produced. |
| **SYNTAX_INVALID** | Output does not compile (`luac5.3` error). |
| **UNSUPPORTED_FORMAT** | Custom/protected bytecode the standard parser cannot faithfully decode. |
| **BLOCKED** | Requires authorized material not present. |

## 2. Corpus classification result (25 Lua files)

Source: `research/LUA_CLASSIFICATION.json`.

| Kind | Count |
|---|---|
| Lua bytecode | 23 |
| Lua text source | 2 |
| **Total** | **25** |

| Validation outcome | Count |
|---|---|
| STRUCTURALLY_VALID (recompiles) | 4 |
| SYNTAX_INVALID (custom-VM protected) | 16 |
| Deferred large (>6 MB, streamed) | 3 (2 distinct files, one duplicated across PAKs) |

### The 4 structurally valid outputs

| File | Size | Output lines |
|---|---|---|
| `WindowBarrierLuaData_Livik.lua` | 92,091 | 19,810 |
| `WindowBarrierLuaData_Baltic.lua` | 264,870 | 60,616 |
| `UIConfig.lua` | 16,899 | 1,021 |
| `BlueberryOctopusGrenadeConfig.lua` | 1,508 | 41 |

These four produce Lua source that `luac5.3` accepts — the strongest honest
result short of an exact-source proof.

### The 16 syntax-invalid outputs (honest PARTIAL / UNSUPPORTED_FORMAT)

All 16 are PUBG/BGMI game Lua whose header claims Lua 5.3 but whose opcodes and
constants are remapped/encrypted by a custom VM. The decompiler emits text, but
`luac5.3` rejects it (typically "too many C levels (limit is 200)" or "near
'_rNNN'" from the synthetic register naming). These are classified
**SYNTAX_INVALID**, never success. Examples: `itemtips_panel.lua`,
`config_ugc_copilot.lua`, `CreativeActorDataManager.lua`,
`WeaponAvatarComponent.lua`, `ParachutingControl.lua`, and 11 others.

## 3. Large-file bounded-memory handling (the OOM fix)

### Defect

A 22.7 MB `CharacterBase.lua` declares **921,357 instructions**. Decompiling
that chunk in memory expands to >3.8 GB and OOM-killed the sandbox (exit 137).
The previous 256 MB byte-size threshold was too coarse: the file is only 22.7 MB
but declares enormous work.

### Fix

Two new primitives in `app/src/main/python/lua_engine/decompiler53.py`:

- `Reader.skip(n)` — advances the cursor without copying bytes, so walking a
  huge chunk never materialises per-instruction byte copies.
- `estimate_chunk_work(data)` — walks prototype headers using `skip()`, reading
  only counts, and returns `{completed, instructions, constants, protos,
  bytes_consumed, error}`. It never raises.

In `app/src/main/python/alvsia_features.py`, `_lua_work_exceeds_budget()` reads
the first 5 header bytes, and only for genuine Lua 5.3 chunks larger than the
in-memory-safe size (256 KB) runs the estimator. If declared instructions exceed
`ALVSIA_LUA_MAX_INSTRUCTIONS` (default 400,000), `run_lua_smart` routes to the
bounded streaming recovery path instead of in-memory decompilation.

### Verified behaviour

- Estimator on the real 22.7 MB chunk: **0.01 s**, reports 921,357 instructions
  and the exact desync offset — without allocating the chunk.
- Estimator on small chunks: matches the real parser's instruction count.
- Estimator on truncated input: returns `completed=false`, never raises.
- Large declared work → streaming path (no OOM). Small chunk → in-memory path.

### Streaming recovery result on the 22.7 MB file

`final_status = PARTIAL`, `mode = smart_fallback`. The standard parser desyncs at
offset **3,770,851** with `invalid instruction count -1711276015` (custom-VM
protection — genuine, not a parser bug). The bounded streaming recovery still
produced:

- **13,258** plain strings,
- **5,181** strings under best single-byte key `0x1f` (printable ratio 0.31),
- 8 multi-byte XOR candidate string sets (PU BG / igame / slua / LuaS / BGMI / …),
- 37 candidate keys ranked.

Memory stayed bounded (~50 MB peak), no OOM.

## 4. Regression tests

`tests/test_large_lua_memory_budget.py` — **6/6 PASS**:

- `test_estimator_reports_declared_work_without_allocating`
- `test_estimator_matches_real_parser_on_small_chunk`
- `test_estimator_never_raises_on_truncated_input`
- `test_large_declared_work_routes_to_bounded_streaming_path`
- `test_small_chunk_stays_on_in_memory_path`
- `test_partial_recovery_is_classified_as_partial_not_failed`

`tests/test_lua53_standard_decompile.py` — 3/3 PASS (standard Lua 5.3 chunks
parse and recompile). This locks the earlier fix where the debug section had been
parsed with the Lua 5.4 layout.

## 5. Honest blockers

1. **Custom-VM protected bytecode (16 files):** the opcode map and constant
   encoding are proprietary. Standard decompilation cannot recover exact source.
   Classified SYNTAX_INVALID / UNSUPPORTED_FORMAT. A full recovery would require
   the game's VM opcode map, which is not available and must not be fabricated.
2. **22.7 MB / 31 MB single chunks:** handled by bounded streaming; exact-source
   recovery is blocked by the same custom-VM protection, not by memory.
3. **Lua 5.4:** layout supported but no 5.4 corpus sample exists to verify.

## 6. Verdict

The Lua pipeline is **honest and bounded**. Standard Lua 5.3 chunks decompile to
recompilable source (4 verified). Protected PUBG/BGMI chunks are classified
SYNTAX_INVALID / PARTIAL with recovery artifacts, never faked as success. Large
chunks no longer OOM. Status: **PASS (with documented custom-VM blocker).**
