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
`t.me/ALVSIA_PRO`, `t.me/OriginalOnwerALV` and `alvsiapanel.unaux.com`.

`alvsia_features.scrub_foreign_branding()` now rewrites known third-party
brand/channel tokens to the owner's brand in generated report files only.
Staged input and decompiled source are never modified; the replacement count
is surfaced as `watermarks_scrubbed`.

Verified on build 1170 (run 41768295623): native libraries STORED and
page-aligned, `zipalign -c -p 4` Verification successful, `RESULT=PASS`,
`JOB_STATUS: success`, 224 tests passing.
APK SHA-256 `911d9e3c3d233870700fbe4c108c6de4b3f2c7443c08f3ecc077a46241828f30`.
