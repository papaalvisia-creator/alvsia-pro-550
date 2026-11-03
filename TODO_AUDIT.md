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
- [ ] Build/validasi APK — MENUNGGU GitHub Actions (sandbox tanpa JDK/Android SDK)
- [ ] Validasi perangkat Android — belum dilakukan
- [x] Branch baru + PR + laporan

## Catatan / Belum Terselesaikan
- Zoul.lua (1.004.870 byte, SHA-256 d129479b…ce53f, 159.411 `EF BF BD`): sampel tidak ada di repo; kerusakan terbukti akibat binary→text, pemulihan byte mustahil tanpa binary asli (tidak memfabrikasi data).
- Verifikasi fungsional end-to-end Lua Reconstruction/Extractor/Protector/Inject pada perangkat nyata belum dijalankan.
