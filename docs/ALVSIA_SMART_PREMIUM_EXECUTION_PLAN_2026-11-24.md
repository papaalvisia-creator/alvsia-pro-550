# ALVSIA SMART PREMIUM 6.0.0 — Execution Plan and Release Gates

**Contract:** 10 main menus / 59 submenus  
**Package:** `com.alvsia.pro`  
**Target:** Android API 26+, ARM64 (`arm64-v8a`)  
**Working branch:** `feat/smart-premium-10x59-ui-refresh-20261124`  
**Production safety:** no changes to live Unaux panel, database, autostart services, production signing material, or main branch during implementation.

## Work sequence

### Phase 0 — Freeze and baseline
- Record main/base commit, current PR head, source hashes, Gradle/AGP/Kotlin/Chaquopy/NDK versions, package ID, versionCode, and signing-certificate fingerprint.
- Keep all implementation on this feature branch. Do not force-push or overwrite main.
- Preserve a known-good build path and all original source/archive files.

### Phase 1 — Source archive audit
Audit these five owner-designated archives, including nested archives:
1. `IkramTool_V130_4.7.zip`
2. `TOOL.zip`
3. `RegulerResault_ALVSIA_tool_no_on_vip_engine.zip`
4. `MANKS-TOOL_ALVSIA.zip`
5. `_workspace_ALVSIA_TOOL_PREMIUM_v4.0.1.zip`

For each archive:
- Verify ZIP CRC, list every entry, record size and SHA-256, and recursively inspect nested archives.
- Identify Python, Lua, JAR, native ELF/SO, data/configuration, and reference/test assets.
- Run static source review and Python AST checks; do not execute opaque binaries or unknown scripts during inventory.
- Deduplicate exact files by SHA-256 while preserving provenance and archive-relative paths.
- Classify each capability as: reusable, adapt, reference/test-only, incompatible with Android ARM64, duplicate, unsafe, or unresolved.
- Do not ship regression corpora, desktop executables/DLLs, unrelated payloads, or unreviewed secrets.

**Input gate:** the five raw ZIPs must be readable before this phase can be marked complete. The current GitHub `main` tree has no `.zip` entries; the existing source-fusion test currently names only the first three archives. Do not claim all-five audit or integration until the raw archives are actually available and hashed.

### Phase 2 — 10/59 catalog and compatibility map
- Implement the approved 10 menu / 59 unique submenu IDs from `ALVSIA_SMART_PREMIUM_10_MENU_59_SUBMENU_CONTRACT.md`.
- Map every current 9/33 public ID and every working legacy route to a new ID or explicit compatibility alias.
- Preserve existing tool behavior, operation names, permission policy, and output formats.
- Require every visible submenu to have a concrete capability adapter and a truthful availability state; never create a fake-success button.
- Combine related steps into direct workflows (especially PAK inspect/extract/replace/rebuild/verify) without deep nested navigation.

### Phase 3 — Strengthen existing engines
For every retained operation, review:
- Input validation, format/version detection, bounds checks, malformed-file handling, and safe error reporting.
- Streaming/large-file behavior, memory ceilings, cancellation, resumability, and temporary-file cleanup.
- Fallback selection based on detected format, not blind trial that can corrupt output.
- Output integrity, hashes, round-trip checks, and atomic output promotion.
- Regression fixtures and negative/malformed-input tests.

Priority engine families: APK/DEX, Tencent PAK/OBB, Lua/LuaJIT/T24/BGMI, XOR/AES/SM4/ZUC, UAsset/UEXP/ZSDIC, ELF/SO, and workspace/batch.

### Phase 4 — Add the 17 new submenu capabilities
Implement only after source review and backend mapping. Candidate capabilities are defined in the 10/59 contract. Every new entry must have:
- Unique stable ID and menu owner.
- Concrete backend adapter.
- Permission and input requirements.
- Unit/integration fixture.
- Failure/unsupported-format behavior.
- Output validation and user-facing progress/result.

### Phase 5 — UI redesign
Carry forward prior owner requirements:
- Professional blue/white neon-metallic visual system, cyan accents, silver details, restrained glow and shadows; remove the old olive/green tint.
- Clear brand/logo treatment and consistent typography.
- Preserve existing splash/logo/loading transition and startup audio assets/behavior unless separately approved.
- Task-oriented dashboard and direct workflow cards; avoid deep nested submenu trees.
- PAK and UnPAK become one understandable archive workflow with separate task actions.
- Lua analyze/decompile/recovery/protect/compile/inject tasks are discoverable and share appropriate file/context state.
- Favorites and Recent Files update immediately after mutations; Compose state must be observable, not only persisted.
- Preserve touch targets, empty/loading/error states, cancellation, progress, and output handoff.
- Do not request every permission at startup; keep the current per-tool, just-in-time permission policy.

### Phase 6 — Panel transport and APK protection
Active panel only: `https://alvsiapanel.unaux.com`.
- Preserve current login, captcha/cookie handshake, operation-grant protocol, HWID/session checks, and server authorization.
- Preserve fail-closed HTTPS, normal platform certificate/hostname validation, and SPKI pinning in Android and Python clients.
- The current `main` source already contains three SPKI entries in `Vault.kt`, `network_security_config.xml`, and `pinned_http.py`; `tests/test_pinned_http.py` checks the Python list. Add parity checks so all three locations stay identical.
- The three configured values are owner-supplied in source comments, but this environment could not resolve the live Unaux hostname during this audit. Therefore, the actual live-chain match and backup-key suitability remain **NOT VERIFIED HERE**. Do not invent, rotate, or silently replace pins. Verify live leaf/intermediate chain and certificate validity from a network that can resolve the host before release.
- Do not pin an unrelated root or intermediate merely to reach a count; each backup must be an actual, documented rotation candidate.
- Retain R8/minification/resource shrinking, v2/v3 signing with v1 disabled for minSdk 26, sealed Python/assets, native RASP, integrity checks, anti-debug/hook/Frida detection, SessionGate, operation grants, short-lived authorization, and fail-closed dispatch.
- Treat client-side obfuscation/encryption as reverse-engineering resistance, not as a place to store server secrets. Never add private signing keys, reusable panel credentials, or privileged secrets to the APK.
- Do not alter panel PHP/database, server configuration, production license data, keystore, or permissions merely to make the build pass.

### Phase 7 — Validation and release
Required evidence:
1. Catalog: exactly 10 menus / 59 unique IDs.
2. Every visible submenu maps to a real adapter; all legacy operations have regression coverage.
3. Python AST/syntax and Python unit/integration tests pass.
4. Kotlin/Compose compile and UI tests pass.
5. PAK/OBB/Lua round-trip and malformed-input tests pass.
6. Crypto known-answer vectors pass for each shipped transform.
7. Pin parity tests pass; live Unaux chain and rotation tests pass from a network with DNS access.
8. Release manifest, cleartext policy, R8, native ABI, Chaquopy payload inventory, and sealed-asset checks pass.
9. Android ARM64 release build succeeds; v2/v3 signer fingerprint matches the approved production certificate.
10. Install/startup/login/session/grant/permission and tool acceptance tests pass on a real supported device.
11. Final signed APK SHA-256 and build provenance are recorded.

## Current verified baseline (2026-11-24)
- Repository: `papaalvisia-creator/alvsia-pro-550`; default branch `main`.
- PR #28 is open, draft, and targets `main`; work remains isolated on its feature branch.
- Main currently exposes 9 menus / 33 subtools in `ToolCatalog.kt`, `StudioCatalog.kt`, and `SubMenus.kt`.
- Main currently includes Python pinning and Android XML/OkHttp pinning for `alvsiapanel.unaux.com`, with three configured SPKI entries.
- The current PR adds the 10/59 contract, records UI requirements, and makes the Favorites star/list update Compose state immediately.
- The live host could not be DNS-resolved from the current execution environment; live TLS validation is pending.
- The five raw ZIP archives are not present in the GitHub repository tree; complete archive audit is pending.
- No completed 6.0.0 APK or device acceptance is claimed by this plan.

## Stop conditions
Stop a release candidate if a legacy route is lost, an entry has no real backend, a pin mismatch occurs, login/grant/session behavior regresses, a permission policy changes unexpectedly, an input file is modified in place, a crypto known-answer test fails, or signing identity differs from the approved certificate.
