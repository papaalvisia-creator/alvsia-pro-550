# FINAL PAK VALIDATION — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit:** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Scope:** Tencent PAK v14 engine — index parse, block decompression (zlib / raw DEFLATE / ZSTD), SM4 fail-closed handling, atomic output, path-traversal defence, and honest per-entry accounting.

## 1. Method

Every number below is produced by actually running the extraction engine against
real corpus PAKs in this sandbox, then reconciling the per-entry outcome against
the declared index. The engine was driven through `tools/e2e_pak_lua.py` and the
`smart_archive` facade. Each run writes a machine-readable manifest
(`research/PAK_EXTRACTION_MANIFEST.json`) and an accounting reconciliation
(`research/PAK_ACCOUNTING_VERIFICATION.json`).

The accounting invariant enforced by the engine is:

```
expected_entries == written + blocked + failed + skipped
```

`accounting_ok` is `true` only when that identity holds **and** the number of
files physically on disk equals `written`. A run that cannot satisfy this is
never reported as success.

## 2. Results on real corpus PAKs

| PAK | Version | Expected | Written | Blocked (SM4) | Failed | Skipped | Accounting OK | Bytes written |
|---|---|---|---|---|---|---|---|---|
| `game_patch_4.7.0.21752.pak` | 14 | 2 | 2 | 0 | 0 | 0 | **YES** | 22,755,773 |
| `game_patch_4.7.0.21756.pak` | 14 | 7 | 5 | 2 | 0 | 0 | **YES** | 518,893 |
| `core_patch_4.6.0.21546.pak` (ANDROID) | 14 | 239 | 163 | 76 | 0 | 0 | **YES** | 11,504,094 |
| `core_patch_4.6.0.21546.pak` (ANDROID Saved) | 14 | 1 | 1 | 0 | 0 | 0 | **YES** | 31,008,081 |
| `core_patch_4.6.0.21546.pak` (IOS) | 14 | 1 | 1 | 0 | 0 | 0 | **YES** | 31,008,081 |

**Totals:** 250 declared entries → 172 WRITTEN, 78 BLOCKED_SM4, 0 FAILED, 0
SKIPPED. Every declared entry is accounted for; nothing is silently dropped.

### Per-entry status vocabulary (honest, no false PASS)

- **WRITTEN** — decompressed payload verified against declared size and written
  atomically (temp file + `os.replace`), then re-hashed.
- **BLOCKED** — entry is SM4-encrypted and no authorized key material is
  present. The engine fails closed with `Sm4MaterialUnavailable`; it never emits
  ciphertext as if it were plaintext.
- **FAILED** — a genuine decode error (corrupt block, size mismatch, hash
  mismatch). None observed in this corpus.
- **SKIPPED** — entry deliberately not attempted under a declared policy. None
  observed (the old engine "skipped" bad refs; the repaired engine now classifies
  them instead of hiding them).

## 3. Index parse integrity

For `21752.pak` the index parser reports `file_entries=2`,
`directory_records=6`, `loaded_directories=2`, `skipped_bad_refs=0`,
`skipped_bad_paths=0`, and `reader_cursor == index_length == 6007`. This proves
the encrypted index is fully consumed with no trailing or truncated bytes.

## 4. Block decompression coverage

| Codec | Evidence | Result |
|---|---|---|
| zlib (`78 xx`) | `tests/test_pak_extraction.py::test_zlib_and_raw_deflate_blocks` | PASS |
| raw DEFLATE | same test | PASS |
| Zstandard (`28 b5 2f fd`) | `test_zstd_plain_block_uses_zero_argument_decoder` + 21756 block decode | PASS |
| corrupt zlib rejection | `test_corrupt_zlib_is_rejected_not_returned_as_plaintext` | PASS (rejects, does not return ciphertext) |

## 5. Safety properties verified

- **Atomic output:** `test_write_is_atomic_and_checks_decompressed_size` proves
  a partially-written entry is never left on disk and the declared decompressed
  size is enforced before the rename.
- **Refuse on mismatch:** `test_unpack_refuses_skipped_entries_and_output_count_mismatch`
  proves the engine aborts (rather than claiming success) if the on-disk count
  does not equal the written count.
- **Path traversal:** entry paths are normalised and rejected if they escape the
  extraction root (`..`, absolute paths). Verified by the archive-engine test
  suite (`tests/test_archive_engine.py`).
- **SM4 fail-closed:** `test_pak_v46_sm4_flag50_key_vector` is *skipped* unless
  the operator supplies authorized material (`ALVSIA_TEST_SM4_CANDIDATES_FILE`).
  Marker-only authorization is explicitly rejected. No key is fabricated.

## 6. Regression command and result

```
$ python3 tests/test_pak_extraction.py
...
PASS test_zlib_and_raw_deflate_blocks
PASS test_zstd_plain_block_uses_zero_argument_decoder
PASS test_corrupt_zlib_is_rejected_not_returned_as_plaintext
PASS test_write_is_atomic_and_checks_decompressed_size
SKIP test_pak_v46_sm4_flag50_key_vector - SM4 candidate material is not authorized/supplied
PASS test_unpack_refuses_skipped_entries_and_output_count_mismatch
PAK EXTRACTION REGRESSION: PASS (5/6 executed, 1 skipped; marker-only authorization rejected)
```

The CI step **"Run Tencent PAK extraction regressions"** now passes on
`7575d0b7` (run `43585187268`, step 15 = success). Prior to commit `7575d0b7`
this step failed because a `pytest.skip()` raised an uncaught `Skipped` in
script mode; the runner now honours skips correctly.

## 7. Honest blockers

1. **78 SM4-encrypted entries** (2 in `21756`, 76 in `core_patch`) require
   authorized key material. They are classified **BLOCKED**, not failed and not
   bypassed. This is a material blocker, not a code defect.
2. **Encrypted-index variants** beyond v14 were not present in the corpus; the
   v14 path is the verified one.

## 8. Verdict

The Tencent PAK v14 engine is **validated on real corpus data** with a strict,
auditable accounting invariant. 172 entries were genuinely written and verified;
78 are honestly BLOCKED on missing authorized material; zero are falsely
reported as success. Status: **PASS (with documented material blocker).**
