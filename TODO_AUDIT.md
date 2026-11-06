# ALVSIA PRO — Audit & Repair Plan

## Fase 1 — Audit
- [x] Akses repo & clone
- [x] Inventaris struktur (Kotlin/Java/Python/JNI/Gradle/assets)
- [x] Periksa PR #95 dan riwayat commit
- [x] Klasifikasi 23 test gagal: bug nyata vs test usang
- [x] Audit 19 modul & katalog (ToolCatalog.kt IDs 1–19 terverifikasi)

## Fase 2 — Perbaikan Lua Tools (prioritas)
- [x] Fix BGMI line-info branch swap
- [x] Fix size_t ABI-aware string read/write
- [x] Fix structure-only mode (tanpa key)
- [x] Validasi hasil decompile sebelum klaim sukses
- [x] Deteksi bytecode multi-versi + LuaJIT
- [x] Penanganan EF BF BD (bukti korupsi teks) — detector melaporkan jumlah/rasio & membatasi confidence ≤ 0.30
- [x] Uji round-trip byte-exact standard↔BGMI (test_bgmi_transform.py)

## Fase 3 — Perbaikan lain
- [x] Perbaiki test usang agar sesuai arsitektur saat ini (vanta/master_upgrade/permission_matrix)
- [x] Perbaiki bug modul lain yang terbukti:
  - [x] Hardcoded master/admin password dihapus (env + hmac.compare_digest, fail-closed)
  - [x] Semua extractall() diganti safe-extract (zip-slip guard)
  - [x] Helper keamanan dipindah ke atas (hindari NameError saat run langsung)
  - [x] SKIN_TOOL & BGMI_CSV download: commit-pinned + verifikasi git blob SHA-1
  - [x] AssetVault.materializeJars: zero plaintext JAR setelah ditulis

## Fase 4 — Build & PR
- [x] Jalankan seluruh test (204 passed, 5 skipped, 25 subtests)
- [x] Build/validasi APK — GitHub Actions PASS (run 41698323483): APK 23.217.410 byte, SHA-256 6ae21603…, v2+v3 terverifikasi, cert pin 99b33815… cocok, validator RESULT=PASS
- [ ] Validasi perangkat Android — belum dilakukan (di luar CI)
- [x] Branch baru + PR + laporan

## Catatan / Belum Terselesaikan
- Zoul.lua (1.004.870 byte, SHA-256 d129479b…ce53f, 159.411 `EF BF BD`): sampel tidak ada di repo; kerusakan terbukti akibat binary→text, pemulihan byte mustahil tanpa binary asli (tidak memfabrikasi data).
- Verifikasi fungsional end-to-end Lua Reconstruction/Extractor/Protector/Inject pada perangkat nyata belum dijalankan.

## APK installability fix (build 1168, run 41760231457)

Device reported `INSTALL_FAILED_INVALID_APK` ("paket tidak valid"). Root cause: the manifest uses
`android:extractNativeLibs="false"`, which requires every `lib/<abi>/*.so` to be ZIP_STORED and
page-aligned. XopProtector re-injected `libprotector.so`, `libc++_shared.so` and `libshadowhook.so`
with DEFLATE, producing a mixed-compression APK that PackageManager rejects.

Fix: `tools/normalize_apk_packaging.py` rewrites only the compression method of `lib/**/*.so`;
the validation workflow now runs normalize -> `zipalign -p -f 4` -> `apksigner sign` ->
`apksigner verify` -> `normalize --check` -> `zipalign -c -p 4`.

Verified on build 1168:
- `PASS: normalised 3 native librar(y/ies) to STORED`
- `PASS: every lib/**/*.so entry is stored uncompressed`
- 9/9 native libraries STORED, data offsets page-aligned (4096)
- `zipalign -c -p -v 4`: Verification successful
- APK Signature Scheme v2 block present; cert pin `99b33815...f295c` matched
- `AndroidManifest.xml` and `resources.arsc` byte-identical to the previous build
  (package identity, permissions, version, extractNativeLibs untouched)
- 43/43 release audit checks PASS, `RESULT=PASS`
- APK 25.736.732 bytes, SHA-256 `610c3dbfd5123d680bdb0ec420da02d9ea882e341c16b3bcf4e8ebc75b4ac744`

## Third-party channel credits in recovered Lua reports (build 1170)

Imported scripts embed their author's watermark in the string table, e.g.
`-- Dump By @SRC_HUB / Dev : @XTHrlen`. `run_lua_bytecode_strings()` and
`extract_lua_constants()` wrote that text verbatim into `OUT/`, so ALVSIA
output displayed another channel even though the app itself only references
`t.me/ALVSIA_PRO` and the active `alvsiapanel.unaux.com` panel.

`alvsia_features.scrub_foreign_branding()` now rewrites known third-party
brand/channel tokens to the owner's brand in generated report files only.
Staged input and decompiled source are never modified; the replacement count
is surfaced as `watermarks_scrubbed`.

Verified on build 1170 (run 41768295623): native libraries STORED and
page-aligned, `zipalign -c -p 4` Verification successful, `RESULT=PASS`,
`JOB_STATUS: success`, 224 tests passing.
APK SHA-256 `911d9e3c3d233870700fbe4c108c6de4b3f2c7443c08f3ecc077a46241828f30`.

## Current continuation status — 2026-11-06

This section supersedes any earlier successful-build status above when assessing PR #99's current head.

- [x] Live Unaux panel PHP files uploaded by the owner; owner reports panel login, APK login and Telegram notifications are working.
- [x] Main branch changes merged into the PR branch; PR #99 branch is up to date with main and GitHub reports it mergeable. It remains draft.
- [x] Prevent normal login/tool events from being mislabeled as THREAT and remove duplicate threat-alert calls.
- [x] Extend notifier detail redaction to HWID/device identifiers, location fields and IPv4 addresses.
- [x] Integrate bounded PAK/OBB archive engine and archive regression tests into the PR branch; correct the archive test's literal newline syntax defect.
- [x] Quarantine live-process GameGuardian offset dumper, socket C2/shell utility, IP/geolocation Telegram injector and direct Telegram file-upload dumper in the source-tool repository.
- [ ] Execute source tests and Android validation on the current head. GitHub Actions runs 42090892030 (Android), 42090891940 (release audit), 42090892292 (module catalog), and 42090279095 (source tools) all show runner_id=0 and steps=[]; retry did not allocate a runner.
- [ ] Complete current-head Gradle build, signed XopProtector APK, final artifact audit and real Android installation test.

- [x] Correct workspace README identity in `WorkPaths.kt`: display label is now ALVSIA PRO 5.5.2 and owner is @ALVSIA_PRO (commit c918f68bd1f6cbec6b9ff551698debd672b63778).
- [x] Add a regression test ensuring workspace README branding stays on @ALVSIA_PRO (commit c582f036624d39b11138a153f15ccd2d1603e3f6).
- [ ] Latest PR-head checks (run 42166076121 module catalog, 42166076001 release audit, 42166075948 Android validation) ended in failure with no step details available; the connector reports null steps for available jobs. Treat this as pre-step runner/check infrastructure failure until logs or runner details are available, not as a source-test result.
Earlier PASS records in this file refer to older commits/runs and are not evidence that the current PR head has been built or installed.


## GitHub-hosted runner allocation diagnosis — 2026-11-06

- [x] Inspected the latest PR-head run metadata and job records directly.
- The latest release-audit job (run 42166734653, job 127724849902), Android validation job (run 42166734498, job 127724849721), and module-catalog job (run 42166734493, job 127724849236) were each created and marked failed about one second after starting.
- All three jobs request the standard `ubuntu-latest` label, but report `runner_id=0`, empty `runner_name`, `runner_group_id=0`, and `steps=[]`. The Actions log endpoint returns an empty body. No checkout or workflow step ran.
- This confirms the immediate blocker is before job execution: GitHub did not assign a hosted runner. It is not a failing Gradle task, Python test, workflow command, or source compilation error.
- Repository workflow configuration already requests GitHub-hosted Ubuntu runners; the signed-release workflow independently uses `ubuntu-22.04`. Changing source code or retrying jobs cannot provision an account-level hosted runner.
- [ ] Account-level GitHub Actions availability/billing/spending limit or hosted-runner service restriction must be checked by the repository/account owner in GitHub Settings → Billing & licensing → Usage (and Actions settings). The connected repository API exposes no permission to inspect or change account billing or hosted-runner entitlements.
- [ ] After hosted-runner allocation is restored, rerun the current PR-head checks, then complete Gradle build, signing, artifact validation and device installation test.
- No APK build or test pass is claimed for the current PR head.
