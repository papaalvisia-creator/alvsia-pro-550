# ALVSIA SMART PREMIUM 6.0.0 — APK Security Audit (read-only)

Scope: static review of the Android security surface. **No locked item was
changed** during this audit. This report does **not** claim the APK is
"100% unhackable" — no client-side protection can be. It records the current
posture, what is enforced, and the residual risks that remain by design.

## Locked items — verified unchanged

| Item | Value found | Status |
|---|---|---|
| Package / applicationId | `com.alvsia.pro` | unchanged |
| versionName | `6.0.0-smart-premium` (versionCode 100) | unchanged |
| Panel host | `alvsiapanel.unaux.com` | unchanged |
| TLS pins | SPKI `84+S6cn1vo+IjlQMR5mvqIe5XKMPh28WV9xYVtFKTkk=` for panel host | unchanged |
| Login / session | `SessionGate` (Keystore HMAC, 8h TTL, 3 strikes) | unchanged |
| Telegram | privacy-hardened `TelegramNotifier` (no indexing/upload) | unchanged |
| Permissions | manifest set (see below) | unchanged |
| Production server | as configured | unchanged |
| Autostart / user data / signing creds | as configured | unchanged |

## Release build hardening (`app/build.gradle.kts`)

- `isMinifyEnabled = true`, `isShrinkResources = true`, `isCrunchPngs = true`.
- `isDebuggable = false`, `isJniDebuggable = false` — no debug attach in release.
- Signing: `enableV1Signing = false`, `enableV2Signing = true`,
  `enableV3Signing = true` (V2/V3 only, as mandated).
- ABI restricted to `arm64-v8a` only (`ndk.abiFilters`).
- R8 full mode + 127-line `proguard-rules.pro`.

## Manifest surface

- Exported components: **only** `.MainActivity` (LAUNCHER — required).
- `.tool.ToolExecutionService`: `exported=false`, `foregroundServiceType=dataSync`.
- `androidx FileProvider`: `exported=false`, `grantUriPermissions=true`;
  `file_paths.xml` is scoped to `ALVSIA/OUT/` and `ALVSIA/TASKS/` only (no broad
  storage exposure).
- `android:allowBackup="false"`; `backup_rules.xml` and `data_extraction_rules.xml`
  exclude **all** domains from cloud backup and device transfer.
- `android:usesCleartextTraffic="false"`; `networkSecurityConfig` enforces
  `cleartextTrafficPermitted="false"` globally with system trust anchors.

## Transport security

- `network_security_config.xml`: base config = no cleartext, system CAs only.
- Panel domain `alvsiapanel.unaux.com` carries an SPKI `<pin-set>` (SHA-256),
  CA + hostname validation kept enabled.
- `NetworkGuard` detects HTTP/SSL proxy properties, VPN, known MITM proxy ports
  (8080/8888/9090/1080/4444/8118/3128/10809), and suspicious DNS.

## Runtime / integrity

- `SessionGate`: token not persisted (process restart = fresh login); HMAC-SHA256
  token integrity via Android Keystore key (`alvsia.session.hmac.v3`); TTL
  `age in 0..SESSION_TTL`; `MAX_STRIKES=3`; `runtimeHostile(ctx)` recheck at each
  dispatch; **fail-closed** when the native RASP lib is not loaded in release
  (`native_rasp_unavailable`).
- Native RASP: `rasp_guard` target built from `app/src/main/cpp/rasp_guard.cpp`
  via CMake (`externalNativeBuild`), loaded at runtime through `NativeGuard`.
- Python operation gate `_alvsia_require_operation` requires
  `ALVSIA_APK_SESSION==1` **and** a valid server-signed RSA grant bound to a
  64-hex session + device id; a marker-only env var is rejected (asserted by
  `tests/test_pak_extraction.py` and `tools/e2e_pak_lua.py`).
- Additional guards present: `DexGuardian`, `DualVmGuard`, `FridaProbe`,
  `AntiHook`, `RuntimeMappingGuard`, `IntegrityBomb`, `MemoryGuard`,
  `ProguardShield`, `StrHide`, `TacticalNotifier`.

## Residual risks (honest, by design — not defects to "fix" blindly)

1. **Client-side controls are bypassable in principle.** A determined attacker
   with a rooted device, Frida, and unlimited time can patch checks. RASP raises
   cost; it does not make the APK unhackable.
2. **SPKI pin rotation.** The config notes the pin was measured on 2026-10-26 and
   has no verified backup pin. Certificate/key rotation on the panel host will
   break pinning until re-measured — operational risk, not a code bug.
3. **`MANAGE_EXTERNAL_STORAGE` / broad media permissions** are present for the
   file-tooling purpose. They are powerful; keep the Play/enterprise justification
   current.
4. **RSA grant verification** depends on the embedded public key material and the
   server's signing hygiene; compromise of the signing key defeats the gate.
5. **Chaquopy/Python runtime** ships interpreted modules; string obfuscation
   (`StrHide`) helps but Python bytecode is inherently more readable than native.

## Recommendation

No code change is required to satisfy the mandate's "audit/harden without
breaking" — the posture already enforces the locked items correctly. The only
follow-ups are operational (pin re-measurement before rotation, permission
justification) and are flagged for the maintainer, not auto-applied.
