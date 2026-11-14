# Deliverable Archive Audit — ALVSIA SMART PREMIUM 6.0.0

**Inspection date:** 2026-11-14  
**Working branch:** fix/engine-repair-20261114  
**Working HEAD at inspection:** be76aed468e7fc148f17bea3ac9fbae15dc2654f  
**PR #24:** open, 36 commits / 30 files  
**PR #25:** open draft, 94 commits / 67 files at inspection

This report audits the two user-provided deliverables and the separately retrieved GitHub APK artifact. It does not treat files from different commits as one release.

## 1. Files inspected

| File | Size | SHA-256 | Role |
|---|---:|---|---|
| _workspace_ALVSIA_SMART_PREMIUM_6.0.0_deliverables.rar | 5,046,452 B | 2bdf32dc60dd7278011d044e63ab6aafa52a3cc8b8e67f81f4d617d9692f6842 | Source/workspace snapshot |
| _workspace_outputs_ALVSIA_FINAL_REPORTS_6.0.0.zip | 23,016 B | fbf057e6004281c1e050d91ebc7bb103cbea5869a4c38c4cce30a196e40246de | Markdown reports only |
| GitHub artifact 14109853179 from run 43585187257 | 59,268,998 B | Artifact ZIP downloaded and inspected | Signed APK + audit evidence |

The reports ZIP contains Markdown reports; it does not contain the APK. The signed APK is a separate GitHub Actions artifact.

## 2. RAR source snapshot findings

The RAR was safely listed and extracted. It contains 618 files, including:

- 299 .pyc compiled Python files;
- 8 __pycache__ / .pytest_cache directories;
- no .git directory;
- no APK;
- no keystore or private signing-key file.

The archive's own README_INDEX.md identifies remote HEAD 59facc42 and PR #24. That is not the current PR #25 working snapshot. The RAR is therefore an older source snapshot, not the source corresponding to the newer reports and APK.

### Critical security finding

The RAR source still embeds historical SM4 material:

- two legacy SM4 constants in alvsia_core.py;
- a 19-entry candidate list and legacy constants in alvsia_ultimate.py;
- compiled Python bytecode caches also retain candidate-shaped constants.

The actual values are deliberately omitted from this report. The archived tools/security_release_check.py nevertheless printed SECURITY SOURCE CHECK: PASS. Its checks were insufficient to detect these historical candidate families. That PASS is not reliable evidence that the RAR is free of embedded SM4 material.

A separate scan found no common GitHub/AWS/Slack token patterns, no .env, and no .jks, .keystore, .p12, .pfx, .pem, or .key files. That does not offset the SM4 finding.

### Packaging hygiene

The 299 .pyc files and cache directories are generated artifacts and should not be shipped in a source deliverable. The archive also contains duplicate JAR copies:
- unluac.jar and unluac_2025_12_23.jar are byte-identical;
- unluac_pro.jar under app/libs and app/src/main/assets/unluac are byte-identical.

These duplicates and caches inflate the archive and make provenance less clear.

## 3. Reports ZIP does not match the RAR snapshot

The reports ZIP records:
- engine commit 7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e;
- reports commit b68df651;
- Final Release Pipeline run 43585187257;
- claimed regression result 455 passed, 6 skipped;
- signed APK SHA-256 b08c5dd2f171f8f39b2ecdc52488ba6c85653db65474bfeb630ddc8d478b5c11.

The RAR instead identifies PR #24 / HEAD 59facc42, and its own README and TODO disagree on test counts (425/12/6 versus 423/12/6). The reports ZIP describes a later state than the RAR. They must not be presented as a single synchronized source-and-report package. The reports ZIP also claims 29 protected Python modules, while the RAR's scanner and the current branch's release scanner count 28; reconcile the module inventory before issuing a new final report.

The signed APK inside GitHub artifact 14109853179 was independently extracted and its SHA-256 matched the reports ZIP. A separate older APK ZIP present in the workspace has SHA-256 48da331a793e438152f5feb204131526cfa463b1d9d1349dd0040f6dfdf71d28; it is a different APK and must not be confused with the b08c5dd2 artifact.

## 4. Independent test of the RAR snapshot

The RAR source was compiled with compileall successfully, and its archived tools/security_release_check.py returned PASS.

A full pytest collection could not be reproduced in this environment because PyCryptodome and Zstandard are absent. Running the suite with those two dependency-gated files excluded produced:

413 passed, 14 failed, 11 skipped

The 14 failures break down as:
- 12 stale architecture-contract tests still expecting the old 18-tool surface;
- one Lua syntax test requiring luac5.3, unavailable in this environment;
- one Zstandard test requiring the missing zstandard package.

This local result is not a replacement for the reports ZIP's CI run; it demonstrates that the RAR snapshot itself does not reproduce the claimed later 455/6 baseline in this environment.

## 5. What is corrected on the current GitHub branch

The current PR #25 source differs materially from the RAR:

- alvsia_core.py now obtains SM4 material through the empty-by-default authorized provider;
- alvsia_ultimate.py leaves legacy SM4 values unset and uses the provider;
- security_release_check.py detects the three historical SM4 candidate families and AST-scans application Python sources;
- regression tests now exercise all three detector families;
- source-export hygiene now rejects .pyc, __pycache__, .pytest_cache, .env, and local signing/private-key files when no .git checkout metadata is present;
- the Smart Lua path has a bounded native unluac-rs fallback for high-work Lua 5.3 input.

The current branch is the continuation target. Do not restore the RAR's embedded SM4 values or cache files.

## 6. Current unresolved items

| Item | State |
|---|---|
| RAR security and packaging | FAIL — do not redistribute |
| Reports ZIP vs RAR provenance | MISMATCH — different source states |
| Reports ZIP APK | Historical CI artifact verified by hash; not built from the current PR #25 HEAD |
| Current PR #25 APK | New Final Release Pipeline still required |
| Private corpus revalidation | BLOCKED_AUTHORIZATION — REFERENCE_CORPUS_TOKEN Actions secret is not configured |
| 78 SM4-blocked PAK entries | Still require authorized material; no keys are fabricated |
| Protected PUBG/BGMI custom-VM Lua | Partial/unsupported until a validated opcode mapping is available |
| Device runtime/install validation | Still required; CI signature/build checks are not device proof |
| PAK 21752 device discrepancy | Reports say 2/2 written, but the earlier device log showed 1 written / 1 skipped; must be rerun on device |
| TLS backup pin | Current audit notes only one enforced Unaux SPKI pin and no backup pin; leave unchanged until owner explicitly authorizes rotation |

## 7. Required release packaging rule

Generate a new source archive only from the final approved PR #25 commit after its CI and APK build complete. Exclude all Python bytecode caches and test caches, include a manifest with the exact source commit and SHA-256 values, and pair the reports and signed APK from that same commit/run. Do not reuse the audited RAR or mix its contents with the later reports ZIP.

**Verdict:** The reports ZIP contains useful later CI evidence and a verified historical signed APK artifact. The RAR is stale, contains embedded SM4 material and generated caches, and its own security PASS is invalid. The two deliverables are not a coherent final release package.
