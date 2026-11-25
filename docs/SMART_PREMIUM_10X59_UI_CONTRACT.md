# ALVSIA SMART PREMIUM 6.0.0 — 10 Menu / 59 Submenu UI & Engineering Contract

**Target application:** `com.alvsia.pro`  
**Repository:** `papaalvisia-creator/alvsia-pro-550`  
**Target version:** `6.0.0-smart-premium`  
**Branch:** `feat/smart-premium-10x59-ui-refresh-20261124`  
**Status:** implementation contract; entries must not be advertised as operational until the matching backend and acceptance tests pass.

## Product rules

1. Keep the product limited to ALVSIA SMART TOOL. This contract does not include any separate AI product.
2. The new public catalog target is **10 main menus / 59 submenus**.
3. Preserve all working legacy operations. Reorganize labels and navigation without silently deleting existing routes.
4. Each visible operation must map to one Smart Engine workflow. Related steps may be composed inside that workflow; do not expose confusing nested menu trees.
5. Combine PAK and UnPAK under one archive workflow where appropriate. Keep inspect, extract, edit/inject, rebuild, and verification as clear task actions.
6. The UI must be task-oriented: choose an engine, select input, configure only relevant options, run, inspect progress/logs, and open the validated output.
7. Do not present a planned or unsupported backend as working. Mark it unavailable/coming only where the product design permits, or keep it hidden until wired.
8. Never overwrite source inputs by default. Use isolated work directories, temporary output, atomic promotion after validation, and explicit user confirmation for destructive actions.
9. Large-file operations must stream where possible, enforce limits, support cancellation, and report partial failures per file.
10. Every new or strengthened operation requires fixtures, regression tests, malformed-input tests, and Android ARM64 acceptance evidence.

## Main menu and submenu target

### 01 — SMART APK (6)
1. APK Structure Inspector
2. Manifest & Permission Audit
3. DEX / Bytecode Inspector
4. Resource Table Inspector
5. APK Compare & Resource Diff
6. APK Signature & Integrity Verify

### 02 — SMART PAK (7)
7. PAK Profile & Fingerprint
8. PAK Explorer / Info
9. PAK Extract / UnPAK
10. PAK Selective Extract
11. PAK Entry Compare & Replace
12. PAK Rebuild / Repack
13. PAK Compact & Rebuild Verify

### 03 — SMART OBB (5)
14. OBB Format Inspector
15. OBB Extractor
16. Mini-OBB / OBBZSDIC Adapter
17. GamePatch / OBB Repacker
18. OBB Integrity & Pair Validator

### 04 — SMART LUA (9)
19. Lua Smart Analyze
20. Lua VM / Version Detector
21. Lua Bytecode Inspector
22. Lua Smart Decompile (multi-backend)
23. Lua Recovery & Normalize
24. Lua T24 / BGMI / PUBG Converter
25. Lua Protect & Compile
26. Lua Custom Inject
27. Lua Round-trip Validator

### 05 — SMART CRYPTO (6)
28. XOR / Multi-XOR Engine
29. AES Candidate & Transform
30. SM4 Engine
31. ZUC Engine
32. Key / Pattern Scanner
33. Crypto Output Validator

### 06 — SMART FORENSICS (6)
34. Universal File Detection
35. File Signature & Hash Inspector
36. String & URL Recovery
37. Entropy / Region Analyzer
38. Hex & Structure Viewer
39. Evidence Report Generator

### 07 — SMART MODDING (6)
40. UAsset / UEXP Inspector
41. UE4 String & ID Extractor
42. Skin Pair Finder
43. ZSDIC Analyzer
44. Offset / Size Fixer
45. Resource Mapping & Recovery

### 08 — SMART NATIVE (5)
46. ELF / SO Inspector
47. Native Strings & Symbols
48. ABI / Dependency Report
49. XREF & Reference Analyzer
50. Authorized Runtime Trace Adapter

### 09 — SMART WORKSPACE (5)
51. File Workspace Manager
52. Recent Files & Favorites
53. Batch Job Queue
54. Resume / Cancel / Progress Center
55. Output Browser & History

### 10 — SMART ENGINE LAB (4)
56. Engine Registry & Capability Matrix
57. Engine Self-Test & Diagnostics
58. Regression / Differential Compare
59. Large-File Benchmark & Validation

**Count check:** 10 main menus; 59 uniquely numbered submenu entries.

## UI requirements carried forward from prior owner feedback

- Modern professional visual language: blue/white foundation, neon cyan highlights, metallic/silver details, restrained glow and shadows.
- Keep logo/brand treatment consistent with ALVSIA SMART PREMIUM.
- Splash, logo, loading transition, and existing startup audio treatment must remain coordinated; do not remove existing assets or audio without an explicit request.
- Prefer a single dashboard of clearly grouped Smart Engine cards and direct task actions over deep nested submenu navigation.
- Related operations should be unified in one workflow (notably PAK/UnPAK and Lua protect/compile/inject/decompile flows) while keeping each task discoverable.
- Recent Files and Favorites must update visually immediately after add/remove/toggle; state must be observable by Compose rather than only persisted to SharedPreferences.
- Maintain readable touch targets, responsive two-column cards where appropriate, clear empty/error/loading states, and concise operation-specific descriptions.
- Preserve the existing per-tool permission policy: ask only when a chosen operation actually needs a permission.

## Current-source reconciliation before UI replacement

The checked `main` branch currently exposes **9 menus / 33 subtools** in `ToolCatalog.kt`, `StudioCatalog.kt`, and `SubMenus.kt`. Do not mistake that current implementation count for the owner's new 10/59 target. The existing catalog must be mapped route-by-route to this target, retaining all working IDs or providing explicit compatibility aliases.

The checked source already includes Jetpack Compose screens, `UXStore`, task routing, `ToolEngine`, Lua JAR assets, and a blue/cyan dark theme. UI work must reuse and improve these components rather than replacing them blindly.

## Source-fusion and compatibility rules

- Audit each supplied source archive and nested archive by SHA-256; deduplicate exact copies.
- Treat source code as candidate implementations, not automatically trusted production code.
- Exclude destructive anti-user behavior, credential harvesting, SMS/bombing automation, and unrelated payloads.
- Do not ship Windows executables or desktop DLLs in the Android ARM64 APK. Prefer portable source/JVM backends or a verified ARM64 native build.
- Crypto integrations require known-answer vectors; parser/repacker integrations require round-trip fixtures and malformed-input tests.
- Protect original files and preserve stable outputs; only promote a generated artifact after its validation passes.
- A menu count is not proof of functionality. Each catalog entry needs an explicit engine capability and acceptance test.

## Release acceptance gates

1. Catalog count and uniqueness: 10 menus / 59 submenu IDs.
2. Every visible submenu has a concrete dispatch route and truthful capability state.
3. Existing working legacy routes pass regression tests.
4. Favorites and recent-file UI state refresh immediately after mutations.
5. Navigation, back behavior, empty states, progress, cancel, and output handoff pass Compose/UI tests.
6. Python syntax, JVM/Kotlin compile, unit tests, archive fixtures, crypto known-answer tests, and ARM64 build pass.
7. Install and exercise the release APK on a supported ARM64 Android device.
8. Verify package ID, version, signing certificate, APK integrity, and SHA-256.
9. Do not call the release complete until these gates have evidence.
