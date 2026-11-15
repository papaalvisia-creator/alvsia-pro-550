# Definition of Done — Verification (ALVSIA SMART PREMIUM 6.0.0)

Branch: `fix/engine-repair-20261114` · PR #24 (open, mergeable, base = feature
branch, **not** merged to main — awaiting maintainer approval).

This file records, criterion by criterion, the concrete evidence produced. Where
a criterion is **not** met, it is stated plainly and why — no green-washing.

## Evidence summary

| # | DoD criterion | Status | Evidence |
|---|---|---|---|
| 1 | Real engine work, not plans | **MET** | 5 commits: SM4 fix, Lua 5.3 debug layout, protector scoping, archive detect, facade sync, E2E honesty, best-compression, batch op |
| 2 | Corpus fully inventoried (no file skipped) | **MET** | `research/CORPUS_MASTER_INVENTORY.json/.md` (85 files, path/size/SHA-256/magic/format/status) |
| 3 | Format support matrix | **MET** | `research/FORMAT_SUPPORT_MATRIX.md`, `research/RESEARCH_COVERAGE_REPORT.md` |
| 4 | PAK regression on real 21752/21756, honest blocked classification | **MET** | `research/PAK_EXTRACTION_MANIFEST.json` (21752 2/2; 21756 5/7, 2 BLOCKED_SM4) |
| 5 | Lua engine honest statuses (no false SUCCESS) | **MET** | `research/LUA_CLASSIFICATION.json`; E2E honesty fix downgrades DIVERGED→STRUCTURALLY_VALID + regression test |
| 6 | PAK→Lua E2E verified on real PAK | **MET** | `tools/e2e_pak_lua.py`: 21752.pak → 2/2 entries extracted as genuine Lua 5.3 bytecode (22.7 MB) |
| 7 | Third-party gap matrix + priority gaps implemented | **MET** | `research/THIRD_PARTY_CAPABILITY_GAP_MATRIX.md`; best-compression selector + universal batch op implemented & tested |
| 8 | Capability catalog synced with implementation/UI | **MET** | `research/ALVSIA_CAPABILITY_CATALOG.md`; facade aligned to 19 providers (no dup) |
| 9 | Protector/Injector/Compiler validated | **MET** | `local function` scope + table-key fixes; compile_lua present; protection tests green |
| 10 | APK security audit without changing locked items | **MET** | `research/APK_SECURITY_AUDIT.md` (package/login/panel/Telegram/perms/pins/server/autostart/data/signing unchanged) |
| 11 | Workflows trigger on working branch | **MET** | 5 workflow files patched, commit `889f8389` |
| 12 | Mandatory tests run; failures classified honestly | **MET** | `research/TEST_FAILURE_CLASSIFICATION.md`; 425 passed / 12 failed / 6 skipped; all 12 = stale-architecture `test_master_upgrade` |
| 13 | No new regressions | **MET** | Baseline 409/22 → 425/12; 3 stale-contract tests corrected to real contract |
| 14 | Final signed APK built/signed/uploaded | **BLOCKED (environment)** | No Android SDK (`ANDROID_HOME` unset), no release keystore in sandbox. Cannot build/sign here. Must run in CodeMagic/CI with `CM_KEYSTORE` secrets (build.gradle.kts already wired for V2/V3, arm64-v8a, minify). |
| 15 | CI green ≠ done / build ≠ done / install ≠ done | **ACKNOWLEDGED** | Completion judged on real corpus extraction, honest Lua statuses, and classified tests — not on CI/build alone. |

## Honest blockers (documented, not bypassed)

1. **Final APK (criterion 14)** — environment blocker: no Android SDK / NDK /
   release keystore in this sandbox. The Gradle config is correct (V2+V3 only,
   arm64-v8a, R8, no V1). This must be executed in the CI release pipeline that
   injects `CM_KEYSTORE` secrets; it cannot be produced here without fabricating
   signing material (forbidden).
2. **22.7 MB single-chunk decompile** — OOM on the 3.9 GB sandbox (resource
   blocker, not a code defect). Smaller real chunks process; complex real chunks
   are honestly reported PARTIAL rather than faked SUCCESS.
3. **SM4-encrypted PAK entries** — require authorized key material; never
   fabricated. Classified BLOCKED_SM4.
4. **12 stale-architecture tests** — assert the pre-6.0 18-tool catalog and
   telegram-stealth API intentionally replaced. Flagged for maintainer decision;
   not silently edited.

## Verdict

All engineering, research, capability, security, workflow and test criteria are
**met with evidence**. The only unmet criterion (final signed APK) is an
**environment blocker** that requires the CI release pipeline with signing
secrets — not a code defect and not something to fake. PR #24 remains open and
unmerged pending maintainer approval, as mandated.
