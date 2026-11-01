# ALVSIA PRO

<p align="center">
  <strong>Android Toolkit for PAK, OBB, Lua & Binary Analysis</strong><br/>
  A modular workspace for game-resource inspection, file transformation and security analysis.
</p>

<p align="center">
  <a href="https://github.com/ALVISIA8/alvsia-pro-550"><img alt="Repository" src="https://img.shields.io/badge/repository-ALVISIA8%2Falvsia--pro--550-181717?logo=github"></a>
  <img alt="Platform" src="https://img.shields.io/badge/platform-Android-3DDC84?logo=android&logoColor=white">
  <img alt="Architecture" src="https://img.shields.io/badge/ABI-arm64--v8a-blue">
  <img alt="Minimum SDK" src="https://img.shields.io/badge/minimum%20SDK-26-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-5.5.2--hardened-informational">
</p>

<p align="center">
  <a href="https://t.me/ALVSIA_PRO">Telegram Channel</a> ·
  <a href="https://t.me/OriginalOnwerALV">Developer Contact</a>
</p>

---

## Overview

**ALVSIA PRO** is an Android-based toolkit focused on inspecting, analyzing and processing game-related assets and binary resources. Its workspace brings together PAK archive operations, OBB handling, Lua analysis, native-library inspection, data recovery and application security diagnostics.

The project combines an Android interface with Kotlin/JVM components, a Python-powered tool layer and native code. Release builds are configured with code shrinking and resource optimization. Security controls are implemented in multiple application layers; their effectiveness must be validated against the exact release artifact and target device.

> **Project status:** This repository contains application source and build configuration. A successful source build does not by itself certify that every tool has passed on-device testing or that a release is ready for distribution.

## Key capabilities

- **Archive workflows** — inspect, extract, rebuild and compact PAK archives.
- **Game asset workflows** — manage OBB files and related resource data.
- **Lua tooling** — inspect, decompile, clean, protect and inject Lua content.
- **Binary analysis** — inspect native shared libraries, strings and XOR patterns.
- **Data recovery** — recover strings and export analysis reports.
- **Security analysis** — inspect APK, Lua and native-library security signals.
- **Workspace management** — organize inputs, intermediate files and final outputs.

## Tool catalog

The application source documents the following 19 tool areas. Availability and behavior can vary by build configuration and should be confirmed on the target device.

| # | Tool | Main purpose |
|---:|---|---|
| 01 | PAK Unpack | List and extract PAK archive contents |
| 02 | PAK Rebuild | Repack archives and process entries |
| 03 | PAK Compact | Remove selected entries and compact archives |
| 04 | OBB Tools | Inspect, extract and rebuild OBB data |
| 05 | Lua Tools | Detect, inspect, decompile and clean Lua content |
| 06 | File Scan | Scan files and calculate common hashes |
| 07 | Workspace | Manage tool input, work and output directories |
| 08 | Export Report | Export session and file-analysis summaries |
| 09 | Rebrand | Apply supported branding/resource changes |
| 10 | SO Analyzer | Inspect native shared libraries and embedded data |
| 11 | Frida Tracer | Assist authorized runtime instrumentation analysis |
| 12 | XOR Suite | Run XOR-oriented inspection and transformation workflows |
| 13 | Decrypt Engine | Run supported format and cipher analysis routines |
| 14 | PAK Deep Analysis | Perform deeper archive and content inspection |
| 15 | String Recover | Recover and inspect embedded strings |
| 16 | Lua Inject | Apply supported Lua bytecode modifications |
| 17 | Anti-RE Audit | Produce application and binary security observations |
| 18 | Lua Protector | Apply supported Lua protection workflows |
| 19 | ALVSIA Private Tool | Owner-controlled private analysis functionality |

Use these capabilities only with files and applications you own or are authorized to assess.

## Platform and build configuration

| Property | Current source configuration |
|---|---|
| Android application ID | com.alvsia.pro |
| Display/version name | 5.5.2-hardened |
| Version code | 98 |
| Minimum Android SDK | 26 (Android 8.0) |
| Target Android SDK | 34 |
| Compile SDK | 34 |
| Native ABI | arm64-v8a |
| Java/Kotlin target | 17 |
| Python runtime (Chaquopy) | 3.8 |
| Native build system | CMake 3.22.1 |

**Device compatibility:** the current Gradle configuration targets 64-bit ARM devices (arm64-v8a). 32-bit-only ARM devices are not included in this build configuration.

## Technology stack

- **Android:** Android Gradle Plugin, Kotlin and Jetpack Compose
- **Python integration:** Chaquopy
- **Native components:** C/C++ with CMake and JNI
- **Networking:** OkHttp
- **Release optimization:** R8/ProGuard and resource shrinking
- **Build automation:** CodeMagic workflow configuration (codemagic.yaml)
- **Archive/data libraries:** project-configured Python dependencies, including PyCryptodome, Requests, Rich and Zstandard

Exact dependency versions are defined by the Gradle files and build configuration in this repository.

## Repository layout

| Path | Description |
|---|---|
| app/ | Android application module, source code and resources |
| docs/ | Project documentation |
| tools/ | Build-time and maintenance utilities |
| scripts/ | Helper and automation scripts |
| tests/ | Test assets and automated checks |
| panel-migration/ | Panel integration/migration-related project material |
| .github/ | GitHub configuration and automation |
| codemagic.yaml | CodeMagic CI/CD workflow |
| CODEMAGIC_BUILD.md | Release build and artifact verification notes |
| CODEMAGIC_SETUP.md | CodeMagic setup guidance |
| SIGNING.md | Release signing notes |
| CHANGELOG_FINAL.md | Historical source change notes |

## Build

### Prerequisites

- Android SDK and a compatible Android build environment
- JDK 17
- Android NDK version configured by the app module
- CMake 3.22.1
- Access to the required private build/signing configuration

### Build a release APK

~~~bash
git clone https://github.com/ALVISIA8/alvsia-pro-550.git
cd alvsia-pro-550

./gradlew assembleRelease
~~~

The command builds the release variant; signing and final artifact naming depend on the configured CI/build environment. For the owner-managed CodeMagic process, follow [CODEMAGIC_BUILD.md](CODEMAGIC_BUILD.md) and [CODEMAGIC_SETUP.md](CODEMAGIC_SETUP.md).

### Release verification

Before distributing a build, verify the exact APK rather than relying only on a green CI status:

1. Confirm package ID, version name and version code.
2. Verify APK signature and expected signing certificate.
3. Confirm the artifact is the intended release variant.
4. Install on a supported ARM64 Android device.
5. Test login and panel connectivity in the intended environment.
6. Exercise each advertised tool with representative test files.
7. Review build logs and retain the release artifact's SHA-256 checksum.

Do not commit keystores, passwords, private keys, API tokens, panel credentials, signing seeds or other secrets to this repository.

## Security and responsible use

The application source includes layered security-related components and release hardening configuration. These are intended to increase tamper resistance and support threat detection, but **no client-side protection can guarantee that an application is impossible to reverse engineer, modify or bypass**.

Security claims should be tied to reproducible tests of a specific build. Do not interpret design documents, planned controls or build flags as proof that a control is active and effective in every distributed APK.

Only analyze software, game assets and devices for which you have permission. Do not use the toolkit to compromise systems, bypass access controls or distribute modified software without authorization.

## Documentation

- [CodeMagic release build](CODEMAGIC_BUILD.md)
- [CodeMagic setup](CODEMAGIC_SETUP.md)
- [Signing guidance](SIGNING.md)
- [Security notes](README_SECURITY.md)
- [Source changelog](CHANGELOG_FINAL.md)

## Support and updates

- **Telegram channel:** [@ALVSIA_PRO](https://t.me/ALVSIA_PRO)
- **Developer:** [@OriginalOnwerALV](https://t.me/OriginalOnwerALV)

For a useful bug report, include the app version, Android version, device ABI, affected tool, exact reproduction steps and relevant sanitized logs. Never attach passwords, license keys, tokens, private keys or personal data.

---

<p align="center">
  <strong>ALVSIA PRO</strong><br/>
  Built for structured Android resource analysis.<br/>
  <sub>By Kapten Jack</sub>
</p>
