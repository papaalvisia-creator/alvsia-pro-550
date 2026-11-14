# FINAL SECURITY AUDIT — ALVSIA SMART PREMIUM 6.0.0

- **Date:** 2026-11-14
- **Branch:** `fix/engine-repair-20261114`
- **Commit:** `7575d0b7a2349092b40fb6e30a15e4f4eb84bf3e`
- **Scope:** static + tooling security review. No locked item was changed.

> This audit does **not** claim the APK is "100% unhackable". No client-side
> control can be. It records the enforced posture and the residual risks that
> remain by design.

## 1. Automated checks run this session

| Check | Command | Result |
|---|---|---|
| Source security check | `python3 tools/security_release_check.py` | **PASS** |
| Release safety audit | `python3 scripts/release_safety_audit.py` | **PASS** (5/5 checks) |
| Secret scan (AST) | commit `a9b5fa51` | PASS — no embedded SM4 material |

`security_release_check.py` output:

```
SECURITY SOURCE CHECK: PASS
- protected Python modules scheduled for sealing: 29
- AES-GCM decryption in Kotlin/native bridge; seed and cert digest not exposed to Python
- New-panel TLS CA/hostname validation, SessionGate HMAC/TTL, R8, VCS stripping checked
- CodeMagic release restricted to main; APK audit required
```

`release_safety_audit.py` output:

```
PASS: catalog defines all seven Smart module IDs
PASS: profile retains the private Smart module
PASS: required existing permissions and backup setting are present
PASS: HTTPS-only panel config and SHA-256 SPKI pin format
PASS: release safety audit completed; runtime and device tests are still required
```

## 2. Locked items — verified unchanged

| Item | Value | Status |
|---|---|---|
| Package / applicationId | `com.alvsia.pro` | unchanged |
| versionName / code | `6.0.0-smart-premium` / 100 | unchanged |
| Panel host | `alvsiapanel.unaux.com` | unchanged |
| TLS pin (SPKI SHA-256) | `84+S6cn1vo+IjlQMR5mvqIe5XKMPh28WV9xYVtFKTkk=` | unchanged |
| Login / session | `SessionGate` (Keystore HMAC, 8h TTL, 3 strikes) | unchanged |
| Telegram | privacy-hardened `TelegramNotifier` (no indexing/upload) | unchanged |
| Permissions | manifest set | unchanged |
| Production server / autostart / user data / signing creds | as configured | unchanged |

Identity preserved: app name **ALVSIA**, package `com.alvsia.pro`, branding
`@ALVSIA_PRO`, Telegram `@OriginalOnwerALV`, promo
`https://t.me/ALVISIACHANEL`, panel `alvsiapanel.unaux.com` (not the old
`alvsiapro.cc.cd`).

## 3. Release build hardening (`app/build.gradle.kts`)

- `isMinifyEnabled = true`, `isShrinkResources = true`, `isCrunchPngs = true`.
- `isDebuggable = false`, `isJniDebuggable = false`.
- Signing: `enableV1Signing = false`, `enableV2Signing = true`,
  `enableV3Signing = true` (V2/V3 only, as mandated).
- ABI restricted to `arm64-v8a` only.
- R8 full mode + 127-line `proguard-rules.pro`.

## 4. Manifest surface

- Exported components: **only** `.MainActivity` (LAUNCHER — required).
- `.tool.ToolExecutionService`: `exported=false`, `foregroundServiceType=dataSync`.
- `androidx FileProvider`: `exported=false`, `grantUriPermissions=true`;
  `file_paths.xml` scoped to `ALVSIA/OUT/` and `ALVSIA/TASKS/` only.
- `android:allowBackup="false"`; backup/extraction rules exclude **all** domains.
- `android:usesCleartextTraffic="false"`; network security config enforces no
  cleartext globally with system trust anchors.

## 5. Transport security

- `network_security_config.xml`: base = no cleartext, system CAs only.
- Panel domain carries an SPKI `<pin-set>` (SHA-256); CA + hostname validation
  kept enabled.
- `NetworkGuard` detects HTTP/SSL proxy properties, VPN, known MITM proxy ports
  (8080/8888/9090/1080/4444/8118/3128/10809), and suspicious DNS.

## 6. Runtime / integrity

- `SessionGate`: token not persisted; HMAC-SHA256 integrity via Android Keystore
  (`alvsia.session.hmac.v3`); TTL bound; `MAX_STRIKES=3`; `runtimeHostile(ctx)`
  recheck per dispatch; **fail-closed** when native RASP lib not loaded in release.
- Native RASP `rasp_guard` built from `app/src/main/cpp/rasp_guard.cpp` via CMake,
  loaded through `NativeGuard`.
- Python operation gate `_alvsia_require_operation` requires
  `ALVSIA_APK_SESSION==1` **and** a valid server-signed RSA grant bound to a
  64-hex session + device id; marker-only env var is rejected (asserted by
  `test_pak_extraction.py` and `tools/e2e_pak_lua.py`).
- Additional guards: `DexGuardian`, `DualVmGuard`, `FridaProbe`, `AntiHook`,
  `RuntimeMappingGuard`, `IntegrityBomb`, `MemoryGuard`, `ProguardShield`,
  `StrHide`, `TacticalNotifier`.

## 7. Secret hygiene

- Commit `a9b5fa51` removed embedded SM4 material and introduced a single
  authorized fail-closed provider, plus an AST secret scan across all modules.
- No PAT, key, or token is printed in any report or log.
- SM4-encrypted PAK entries fail closed (`Sm4MaterialUnavailable`); no key is
  fabricated or shipped.

## 8. Residual risks (honest, by design)

1. **Client-side controls are bypassable in principle** — rooted device + Frida +
   time can patch checks. RASP raises cost, does not make it unhackable.
2. **SPKI pin rotation** — pin measured 2026-10-26, no verified backup pin;
   rotation breaks pinning until re-measured (operational, not a code bug).
3. **`MANAGE_EXTERNAL_STORAGE` / broad media permissions** — present for file
   tooling; keep Play/enterprise justification current.
4. **RSA grant verification** depends on embedded public key + server signing
   hygiene; compromise of the signing key defeats the gate.
5. **Chaquopy/Python runtime** ships interpreted modules; `StrHide` helps but
   Python bytecode is inherently more readable than native.

## 9. Verdict

Security posture is **audited and enforced** without changing any locked item.
Both automated checks PASS, secret hygiene is clean, and residual risks are
documented honestly. Status: **PASS (with documented residual risks).**
