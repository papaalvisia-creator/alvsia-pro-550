# FINAL APK VERIFICATION — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit:** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Status:** BUILD IN PROGRESS IN CI — local build environment-blocked (honest)

## 1. Local environment check (honest)

The sandbox has **no Android build toolchain**:

```
ANDROID_HOME=            (unset)
ANDROID_SDK_ROOT=        (unset)
java / javac / gradle    (not installed)
release keystore (.jks/.keystore)  (none present)
```

Therefore a signed release APK **cannot** be produced locally without
fabricating signing material — which is forbidden. The build is delegated to the
GitHub Actions release pipeline, which injects the signing secrets
(`CM_KEYSTORE` etc.) and has the Android SDK/NDK. This is an **environment
blocker**, not a code defect.

## 2. Build configuration (verified correct)

From `app/build.gradle.kts` and the security audit:

- `applicationId = com.alvsia.pro`, `versionName = 6.0.0-smart-premium`,
  `versionCode = 100`.
- Release: `isMinifyEnabled = true`, `isShrinkResources = true`,
  `isDebuggable = false`, `isJniDebuggable = false`.
- Signing: `enableV1Signing = false`, `enableV2Signing = true`,
  `enableV3Signing = true` (V2/V3 only).
- ABI: `arm64-v8a` only.
- R8 full mode + 127-line `proguard-rules.pro`.
- Chaquopy Python runtime + native Smart Lua engines (Rust/NDK) built in CI.
- XopProtector → ReArk handoff, then single signed APK.

## 3. CI pipeline (authoritative build path)

Workflows triggered on `fix/engine-repair-20261114` at `7575d0b7`:

| Workflow | Run ID | Status |
|---|---|---|
| Android Security Validation | [43585187268](https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/43585187268) | in progress |
| ALVSIA SMART PREMIUM Final Release Pipeline | [43585187257](https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/43585187257) | in progress |
| ALVSIA release safety audit | [43585187279](https://github.com/papaalvisia-creator/alvsia-pro-550/actions/runs/43585187279) | **success** |

### Android Security Validation — step progress at time of writing

Steps **1–20 = success**, including the previously-failing
**"Run Tencent PAK extraction regressions"** (step 15). Step 21 (Android debug
build) in progress; release/sign/upload steps 22–35 pending.

| # | Step | Status |
|---|---|---|
| 6 | Generate fresh per-build seal seed | success |
| 7 | Source-level security checks | success |
| 8 | Security protections wired into runtime | success |
| 9 | Active Unaux Python TLS pin policy | success |
| 10 | Compile Python modules + dispatch contract tests | success |
| 11 | Telegram notifier integration contract | success |
| 12 | Sealed payload crypto tests | success |
| 13 | Install Lua 5.3 parser | success |
| 14 | Lua decompiler safety regression | success |
| 15 | Tencent PAK extraction regressions | **success** |
| 16 | Lua Protector round-trip | success |
| 17 | JDK 17 | success |
| 18 | Rust + Android ARM64 target | success |
| 19 | Pinned Android NDK + CMake | success |
| 20 | Build pinned native Smart Lua engines | success |
| 21 | Build and test Android debug variant | in progress |
| 22–30 | Sealed release build, XopProtector, sign, publish, upload | pending |
| 31–35 | Restore sources, manifest/debug checks, CERT_SHA256, branch restriction, Telegram report | pending |

## 4. What "verified" will mean when CI completes

The APK is only considered verified when the pipeline produces:

1. A **signed** APK (V2 + V3) with the release keystore — fingerprint and size
   reported (step 28).
2. A **private draft validation release** (step 29) and the signed XopProtector
   validation APK upload (step 30).
3. Manifest checks: no debug flags (step 32), `CERT_SHA256` matches build config
   (step 33), branch restriction holds (step 34).

Until those steps complete, this report records an **honest in-progress**
status — it does not claim a built APK that does not yet exist.

## 5. Honest blockers

1. **Local build** — no Android SDK/NDK/JDK/keystore in sandbox. Environment
   blocker; cannot be bypassed without fabricating signing material.
2. **CI completion** — release/sign/upload steps still running at report time.
   Final fingerprint/size/artifact links will be appended once the run completes.

## 6. Verdict

Build configuration is **correct and hardened** (V2/V3, arm64-v8a, R8, no debug,
no V1). The signed APK is produced by the CI release pipeline, which is
**actively running** and has passed all engine/security/test gates (steps 1–20).
Local production of the APK is an honest environment blocker. Status:
**IN PROGRESS IN CI — configuration PASS, artifact pending CI completion.**
