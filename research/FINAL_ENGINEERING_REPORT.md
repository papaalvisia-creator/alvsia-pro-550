> **HISTORICAL BASELINE — NOT CURRENT RELEASE STATUS.** This report records validation for engine commit `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e` and the historical Final Release Pipeline run `43585187257`. It remains evidence only for that exact source commit and artifact. It does **not** describe the current PR #25 HEAD or the APK currently being built. For live status and archive provenance, see [DELIVERABLE_ARCHIVE_AUDIT_20261114.md](DELIVERABLE_ARCHIVE_AUDIT_20261114.md) and [PR #25](https://github.com/papaalvisia-creator/alvsia-pro-550/pull/25). Do not treat this historical report as proof that the current branch release is complete.

---

# FINAL ENGINEERING REPORT — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14 (UTC)
- **Branch:** `fix/engine-repair-20261114`
- **Starting HEAD:** `aed20fb9107997fc10993474f81ceb2b73035926` (matched the reported historical commit)
- **New commits (this session):**
  - `87623309` — fix(lua/pak): bound memory for large Lua chunks + recover partial PAK extraction
  - `7575d0b7` — fix(ci): honour pytest.skip in script-mode PAK extraction runner
- **Status:** DONE — engine work complete; signed APK built/signed/audited by CI (see FINAL_APK_VERIFICATION.md).

## 1. What was verified at the start (not assumed)

The reported commit `aed20fb9` **was** the current HEAD of the working branch. The
repository was cloned fresh with the authorized PAT (token never printed), the
private reference corpus `kumpulan-source-tool` was cloned (85 files, 275 MB, 5
PAK samples), and the full test suite was run against the real checkout.

The stale research documents claimed "425 passed / 12 failed" and "423 passed /
12 failed / 6 skipped". The **actual** reproducible baseline on `aed20fb9` was:

```
449 passed, 6 skipped   (pytest, after installing zstandard)
```

The 12 "stale-architecture" tests referenced in `TEST_FAILURE_CLASSIFICATION.md`
had already been aligned to the 6.0 architecture in commit `d42bfbf2`. The
423/425 discrepancy is therefore **reconciled**: the authoritative number is the
reproducible run, not the historical notes.

## 2. Real defects found and fixed this session

### 2.1 Unbounded in-memory decompile of large Lua chunks (OOM-kill)

**Symptom.** Decompiling the real extracted `CharacterBase.lua` (22,755,773 bytes,
from `game_patch_4.7.0.21752.pak`) killed the process with SIGKILL (exit 137).
Peak memory exceeded the 3.8 GB sandbox.

**Root cause.** `run_lua_smart` only routed inputs larger than **256 MB** to the
bounded streaming path. A 22.7 MB Lua 5.3 chunk declared **921,357 instructions**
across its prototypes; the pure-Python parser/decompiler expanded that into
several GB of Python objects before the OS OOM-killer intervened.

**Fix.**
- Added `Reader.skip()` and `estimate_chunk_work()` to
  `lua_engine/decompiler53.py`. The estimator walks a chunk's structure reading
  only counts and skipping payload bytes — **O(1) extra memory**, never raises,
  and reports partial counts on desync (0.01 s / 43 MB for the 22.7 MB file).
- Added `_lua_work_exceeds_budget()` and wired it into `run_lua_smart`. A Lua 5.3
  chunk whose declared instruction count exceeds a safe budget (default
  400,000, override `ALVSIA_LUA_MAX_INSTRUCTIONS`) is routed to the existing
  bounded streaming recovery path instead of the in-memory decompiler.
- Result on the real file: **PARTIAL**, peak memory **≈50 MB**, no OOM-kill,
  diagnostic string recovery still produced (5,181 strings, xor_1f best key).

### 2.2 Partial PAK extraction aborted the whole PAK→Lua pipeline

**Symptom.** `core_patch_4.6.0.21546.pak` extracts 163/239 entries (76 blocked on
unavailable SM4 material). `smart_archive_lua_engine.execute()` returned early
with `incomplete PAK extraction` and **never scanned or recovered the 20 Lua files
that were successfully extracted**.

**Fix.** `execute()` now proceeds to scan/recover whenever at least one entry was
written to disk (`on_disk > 0`). Blocked entries stay visible via
`extraction_complete=false` and `blocked_entries`. Nothing is hidden; nothing is
faked. Result: all 20 extracted Lua files are now attempted and honestly
classified.

### 2.3 Bounded PARTIAL recoveries were miscounted as FAILED

**Symptom.** A streaming recovery that produced diagnostic artifacts returns
`ok=False, final_status="PARTIAL"`. The archive summary only recognised a
`partial_recovery` key, so these were counted as **failed**.

**Fix.** Added `_fallback_recovery_status()` which classifies
`final_status ∈ {PARTIAL, PARTIAL_RECOVERY, STRUCTURALLY_VALID}` as PARTIAL.
E2E now reports `partial: N, failed: 0` for these instead of `failed: N`.

### 2.4 CI test-runner bug: uncaught pytest.skip in script mode

**Symptom.** The `Android Security Validation` workflow failed at step
"Run Tencent PAK extraction regressions" (run 43578027078 and again on
`87623309`). The step runs `python3 tests/test_pak_extraction.py` directly. The
SM4 known-answer test calls `pytest.skip()` when no authorized key material is
supplied; in script mode that raises an uncaught `Skipped`, producing exit code 1.

**Fix.** `main()` in `tests/test_pak_extraction.py` now catches
`pytest.skip.Exception` and prints `SKIP` (no assertion weakened; the SM4 vector
still runs and asserts when material is supplied). Verified locally: script exits
0 with 5 executed + 1 honest skip; pytest collection unchanged (8 passed, 1
skipped). **CI step 15 now passes on `7575d0b7`.**

## 3. Test commands and results

```
python3 -m pytest -q                       -> 455 passed, 6 skipped, 25 subtests passed
python3 tests/test_pak_extraction.py       -> exit 0 (5 executed, 1 honest skip)
python3 tools/security_release_check.py    -> SECURITY SOURCE CHECK: PASS
```

## 4. Regression tests added

`tests/test_large_lua_memory_budget.py` (6 tests):
- estimator reports declared work without allocating,
- estimator matches the real parser on a small chunk,
- estimator never raises on truncated input,
- large declared work routes to the bounded streaming path,
- small chunk stays on the in-memory path,
- partial recovery is classified PARTIAL, not FAILED.

## 5. Honest status of remaining work

| Area | Status | Evidence / blocker |
|---|---|---|
| PAK extraction accounting | DONE | 21752 2/2; 21756 5/7; core_patch 163/239; Saved 1/1; iOS 1/1 |
| SM4-blocked entries (82) | BLOCKED | No authorized SM4 key material supplied; never fabricated |
| Large Lua chunk handling | DONE (bounded) | 22.7 MB → PARTIAL at ≈50 MB, no OOM |
| PUBG/BGMI custom-VM decompile | PARTIAL / UNSUPPORTED | Standard Lua 5.3 decoder cannot faithfully decode protected VM bytecode |
| Partial-extraction recovery | DONE | 20/20 extracted Lua attempted, honestly PARTIAL |
| CI test-runner | DONE | Step 15 green on `7575d0b7`; full CI green |
| Final signed APK | DONE | CI Final Release Pipeline produced `ALVSIA_SMART_PREMIUM_6.0.0-xop-signed.apk` (V2+V3, 34,503,233 bytes, SHA-256 `b08c5dd2…`); see FINAL_APK_VERIFICATION.md |

## 6. Residual risks

- The 400k-instruction budget is a heuristic; a legitimate chunk just under the
  budget could still be heavy. It is configurable and conservative.
- The estimator uses the standard Lua 5.3 layout; a hybrid/PUBG chunk may desync
  early and report a partial (lower) count. That only makes the gate *less*
  likely to trigger, never more, so it cannot cause a false OOM guard.
- Custom-VM Lua remains genuinely unsupported for faithful decompilation.
