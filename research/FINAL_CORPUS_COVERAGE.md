> **HISTORICAL BASELINE — NOT CURRENT RELEASE STATUS.** This report records validation for engine commit `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e` and the historical Final Release Pipeline run `43585187257`. It remains evidence only for that exact source commit and artifact. It does **not** describe the current PR #25 HEAD or the APK currently being built. For live status and archive provenance, see [DELIVERABLE_ARCHIVE_AUDIT_20261114.md](DELIVERABLE_ARCHIVE_AUDIT_20261114.md) and [PR #25](https://github.com/papaalvisia-creator/alvsia-pro-550/pull/25). Do not treat this historical report as proof that the current branch release is complete.

---

# FINAL CORPUS COVERAGE — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit:** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Corpus:** private `papaalvisia-creator/kumpulan-source-tool` (279 MB on disk)
- **Source of truth:** `research/CORPUS_MASTER_INVENTORY.json` (85 files, path / size / SHA-256 / magic / format)

## 1. Inventory completeness

**85 / 85 files inventoried (100%)** — every non-`.git` file has a path, byte
size, SHA-256, magic-byte signature and detected format. Nothing was skipped.

| Format | Count |
|---|---|
| Python source | 51 |
| Text / Markdown | 18 |
| Tencent PAK | 5 |
| UNKNOWN | 3 |
| YAML | 2 |
| Lua bytecode | 2 |
| ZIP archive | 2 |
| Lua source (text) | 1 |
| Shell script | 1 |
| **Total** | **85** |

## 2. PAK coverage

All **5 / 5** Tencent PAKs detected and index-parsed. Extraction results
(authoritative, from `PAK_EXTRACTION_MANIFEST.json`):

| PAK | Declared entries | Written | Blocked (SM4) | Failed | Skipped |
|---|---|---|---|---|---|
| `game_patch_4.7.0.21752.pak` | 2 | 2 | 0 | 0 | 0 |
| `game_patch_4.7.0.21756.pak` | 7 | 5 | 2 | 0 | 0 |
| `core_patch_4.6.0.21546.pak` (ANDROID) | 239 | 163 | 76 | 0 | 0 |
| `core_patch_4.6.0.21546.pak` (ANDROID Saved) | 1 | 1 | 0 | 0 | 0 |
| `core_patch_4.6.0.21546.pak` (IOS) | 1 | 1 | 0 | 0 | 0 |
| **Total** | **250** | **172** | **78** | **0** | **0** |

**Reconciliation note:** an earlier draft of `RESEARCH_COVERAGE_REPORT.md` quoted
"254 declared / 82 blocked". The manifest-derived, per-entry-verified figures are
**250 declared / 172 written / 78 blocked**, which satisfy the accounting
invariant `250 = 172 + 78 + 0 + 0`. The 250/172/78 numbers supersede the earlier
254/82 draft.

Every blocked entry is an SM4-encrypted payload with reason
`sm4_material_unavailable`. No entry is silently lost.

## 3. Lua coverage

| Metric | Value |
|---|---|
| Lua files discovered inside extracted PAKs | 25 (23 bytecode + 2 text source) |
| Bytecode decompiled (produced output) | 20 |
| Deferred to bounded streaming (>6 MB) | 3 (2 distinct files, 1 duplicated) |
| STRUCTURALLY_VALID (recompiles with `luac5.3`) | 4 |
| SYNTAX_INVALID (custom-VM protected) | 16 |

The 16 syntax-invalid files are PUBG/BGMI protected bytecode: the header claims
Lua 5.3 but opcodes/constants are remapped and source strings are encrypted
(`Q?j$*…`). They are classified honestly as PARTIAL / UNSUPPORTED_FORMAT — never
reported as success. Full details in `FINAL_LUA_VALIDATION.md`.

## 4. Format coverage summary

| Format family | Coverage | Status |
|---|---|---|
| Tencent PAK v14 (encrypted index) | 5/5 parsed, 172 entries extracted | SUPPORTED |
| Tencent PAK SM4 entries | fail-closed | BLOCKED (material) |
| ZIP / GZIP / ZLIB / raw DEFLATE | full | SUPPORTED |
| Zstandard | full | SUPPORTED |
| Lua 5.3 standard bytecode | parse + recompile | SUPPORTED |
| Lua 5.3 protected (PUBG/BGMI) | partial recovery | PARTIAL |
| Lua 5.1 / LuaJIT / Luau | parser present, no corpus sample | PARTIAL |
| Lua 5.4 | layout only, no sample | UNSUPPORTED |

Full matrix: `research/FORMAT_SUPPORT_MATRIX.md`.

## 5. Third-party source scan

30 Python tools in the corpus were scanned for capability gaps
(`research/THIRD_PARTY_CAPABILITY_GAP_MATRIX.md`). The highest-value gaps
(best-compression selector, universal batch archive op) were implemented and
tested; the remainder are documented, not silently dropped.

## 6. Honest gaps

1. **78 SM4-encrypted entries** — BLOCKED on authorized key material.
2. **16 protected Lua files** — custom VM; exact recovery needs the proprietary
   opcode map (not available, not fabricated).
3. **Lua 5.4 / 5.1 / LuaJIT / Luau** — no corpus samples to verify end-to-end.

## 7. Verdict

Corpus coverage is **complete and honest**: 85/85 files inventoried, 5/5 PAKs
parsed, 172 entries genuinely extracted, 25/25 Lua files classified. All gaps are
documented blockers, not hidden failures. Status: **PASS (with documented
material/format blockers).**
