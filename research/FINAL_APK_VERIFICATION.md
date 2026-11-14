> **HISTORICAL BASELINE — NOT CURRENT RELEASE STATUS.** This report records validation for engine commit `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e` and the historical Final Release Pipeline run `43585187257`. It remains evidence only for that exact source commit and artifact. It does **not** describe the current PR #25 HEAD or the APK currently being built. For live status and archive provenance, see [DELIVERABLE_ARCHIVE_AUDIT_20261114.md](DELIVERABLE_ARCHIVE_AUDIT_20261114.md) and [PR #25](https://github.com/papaalvisia-creator/alvsia-pro-550/pull/25). Do not treat this historical report as proof that the current branch release is complete.

---

# FINAL APK VERIFICATION — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit (engine code):** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Commit (reports):** `b68df651`
- **Status:** **PASS — signed APK built, signed (V2+V3), audited, and uploaded by CI**

## 1. Result summary

The signed release APK was produced by the **Final Release Pipeline** in GitHub
Actions and passed the full release audit. Local production is not possible in
this sandbox (no Android SDK/NDK/JDK/keystore), so the authoritative build path
is CI — which completed successfully.

| Field | Value |
|---|---|
| APK file | `ALVSIA_SMART_PREMIUM_6.0.0-xop-signed.apk` |
| APK size | **34,503,233 bytes** (~32.9 MB) |
| APK SHA-256 | `b08c5dd2f171f8f39b2ecdc52488ba6c85653db65474bfeb630ddc8d478b5c11` |
| Signature schemes | **V1 = false, V2 = true, V3 = true** (as mandated) |
| Signer cert DN | `CN=ALVSIA PREMIUM, OU=ALVSIA, O=ALVSIA PRO, L=Makassar, ST=Sulawesi, C=ID` |
| Signer cert SHA-256 | `99b33815c88a17abbcfe22be15250363f6dfc79c11ffc980e71b62b74b1f295c` |
| Signer key size | 4096 bits |
| Public key SHA-256 | `783c160d6900430acb670326c6d3f73a4acbb447a8c8c16263bea427ce421a19` |
| App identity | `6.0.0-smart-premium` (versionCode 100), package `com.alvsia.pro` |
| ABI | `arm64-v8a` only |
| Artifact (zip) | `ALVSIA_SMART_PREMIUM_6.0.0-final-xop-signed`, 59,268,998 bytes |
| Artifact ID | `14109853179` |

## 2. CI runs (all green)

| Workflow | Run | Commit | Result |
|---|---|---|---|
| Final Release Pipeline | [43585187257](https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/43585187257) | `7575d0b7` | **success** |
| Android Security Validation | [43585779725](https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/43585779725) | `b68df651` | **success** |
| ALVSIA release safety audit | [43585779707](https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/43585779707) | `b68df651` | **success** |

### Final Release Pipeline steps (all success)

```
8  Build native Smart Lua engines            success
9  Source and Lua validation                 success
10 Reference corpus research status          success
11 Prepare sealed release                    success
12 Build unsigned APK                        success
13 Sign baseline for XOP                     success
14 Build XopProtector and pack candidate     success
15 Sign final XOP APK and verify             success
16 Upload final APK and audit                success
```

### Android Security Validation steps 1–35 (all success)

Steps 1–20 (security source checks, sealed-payload crypto, Lua/PAK regressions,
JDK/Rust/NDK, native engine build) succeeded, then 21–35 (debug build, sealed
release, XopProtector, sign, fingerprint/size report, upload, manifest debug
check, CERT_SHA256 check, branch restriction, Telegram report) all succeeded.
The previously-failing **"Run Tencent PAK extraction regressions"** (step 15)
now passes.

> Note: the Android Security Validation workflow names its artifact
> `ALVISIA_PRO_5.5.2-xop_candidate_signed` (a legacy label in that workflow).
> The **actual** app identity in the build is `6.0.0-smart-premium` (versionCode
> 100), confirmed by the release audit and the Final Release Pipeline artifact
> name `ALVSIA_SMART_PREMIUM_6.0.0-final-xop-signed`.

## 3. Release audit (`tools/audit_release_apk.py`) — PASS

Selected PASS lines from the audit on the final APK:

```
PASS APK ZIP integrity
PASS Xop protector config is valid JSON
PASS Xop native SO protection enabled
PASS Xop proxy detection and NetGuard enabled
PASS Xop SO decryption uses lazy mode
PASS Xop RASP enforce action enabled
PASS Xop dex_hmac is a populated SHA-256 HMAC
PASS Xop code_hmac is a populated SHA-256 HMAC
PASS Xop code_methods_hmac is a populated SHA-256 HMAC
PASS Xop application signing certificate fingerprint is populated
PASS Xop asset encryption enabled
PASS native RASP library packaged
PASS Android ARM64 Smart Lua native decompiler packaged
PASS unluac-rs executable is Android ARM64 ELF
PASS Android ARM64 Luau v3-v9 decompiler packaged
PASS Luau decompiler executable is Android ARM64 ELF
PASS Chaquopy app bundle packaged
PASS sealed JAR index packaged
PASS Xop encrypted asset index packaged
PASS Xop PAS1 encrypted sealed JAR index packaged
PASS dependency version metadata absent from APK
PASS sensitive local rebrand/build metadata absent from APK
PASS sealed Python loader packaged
```

Sealed-payload audit: `RESULT=PASS` — all protected Python payloads are AES-GCM
sealed (`.alv`), no plaintext source/bytecode, VCS metadata absent.

## 4. Manifest / config checks

- No `android:debuggable="true"` in manifest (step 32 PASS).
- `CERT_SHA256` present in `app/build.gradle.kts` (step 33 PASS).
- Branch restriction holds (step 34 PASS).
- Compiled manifest excludes `android.permission.DUMP`, unused
  `DELETE_PACKAGES`, and unused `CHANGE_NETWORK_STATE`.

## 5. Local environment (why CI is the build path)

```
ANDROID_HOME=            (unset)
ANDROID_SDK_ROOT=        (unset)
java / javac / gradle    (not installed)
release keystore (.jks/.keystore)  (none present)
```

A signed APK cannot be produced locally without fabricating signing material
(forbidden). The CI pipeline injects the owner's keystore and Android SDK/NDK, so
it is the authoritative build path. This is an environment fact, not a defect.

## 6. Honest notes

1. The APK is **signed with the owner's 4096-bit key** and verified V2+V3 (V1
   disabled). It is uploaded as a CI artifact; publishing to a public release is
   a separate maintainer action.
2. The XopProtector/ReArk pipeline ran and the final XOP-signed APK passed
   `apksigner verify` and the release audit.
3. Runtime/device install testing is still required — a green build and a valid
   signature are necessary but not sufficient proof of on-device correctness.

## 7. Verdict

The final APK is **built, signed (V2+V3), audited, and uploaded** by CI with a
verified SHA-256, certificate, and package identity. Status: **PASS** (device
runtime testing remains a separate follow-up).
