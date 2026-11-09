# ALVSIA Smart Lua Decompiler — Expansion Plan

Status date: 2026-11-07  
Target repository: `papaalvisia-creator/alvsia-pro-550`  
Implementation branch: `feat/lua-intelligence-orchestrator-20261107`

## Objective

Build one user-facing Smart Lua workflow inside the existing Lua Center. The user selects a file once; ALVSIA identifies its dialect/container, selects only compatible local engines, runs bounded attempts, validates every output, compares successful alternatives, and produces one honest report. The orchestrator is internal; it must not create a maze of separate user-facing tools.

## Current implementation verified in this branch

- `lua_engine.detector` distinguishes standard Lua bytecode 5.1–5.5, LuaJIT bytecode, source, wrapped containers, and conservative Luau bytecode header candidates.
- `lua_engine.orchestrator` retains the ALVSIA Lua 5.3 and LuaJIT routes, adds a validated source-passthrough route, sends Lua 5.1–5.5 and LuaJIT 2.1 to pinned `unluac-rs`, and routes Luau v3–v9 to PumbaaDev with `unluac-rs` as a v3–v7 fallback.
- Each candidate writes to its own file. Validation now prefers a version-matched `luac -p` parser when available; if no matching parser exists, the structural fallback is explicitly reported as heuristic-only. Validated alternatives are retained and original input bytes are preserved.
- Smart Lua runs protection-pattern detection in preflight-only mode; standard decompiler engines execute exactly once inside the shared orchestrator. Full pattern recovery is staged as a candidate for the same validator/selector. Partial VM structure/constants reports cannot short-circuit engine routing or be labelled as recovered original source. If an engine only reconstructs a VM wrapper/interpreter, the result is marked `PARTIAL` and `vm_wrapper_source`.
- Android Security Validation is excluded from this feature branch. A Python-only workflow checks module syntax, Lua 5.3 parser acceptance/rejection, Lua engine tests, orchestration tests and streaming decompiler tests; no APK build is part of this workflow.
- Existing Unluac assets include three unique Git blobs (the generic and dated JAR names are identical content). They are not yet proven to be three independent engines.
- Existing LuaDec source candidate is not yet compiled or shipped.
- Lua 5.5 detection and Luau header recognition is wired into the detector. Luau is kept distinct from PUC Lua; its conservative header check is not a substitute for full bytecode parsing. The pinned unluac-rs v1.4.4 parser supports Luau bytecode v3–v7 only. PumbaaDev's pinned Luau decompiler supports v3–v9 and is the primary Luau candidate; bytecode v10+ is deliberately not routed to either.
- The Java/JAR route is optional and depends on a runtime and the configured JAR directory. The pinned unluac-rs v1.4.4 candidate has been built for `aarch64-linux-android` (API 24, NDK r27) and its ELF interpreter is `/system/bin/linker64`; it is not yet packaged into ALVSIA or run on-device. `tools/build_unluac_rs_android.sh` now defines the reproducible app-integration build path. Windows executables and Linux/glibc binaries are not Android engines.

## Engine and format inventory

| Family / project | Role | Proposed ALVSIA disposition | Gate before runtime integration |
|---|---|---|---|
| Existing Unluac JAR variants | Standard Lua bytecode decompiler | Keep as a fallback engine | Identify exact source/version/license for each unique blob; test Lua 5.1–5.4 fixtures and stripped-debug cases |
| Existing ALVSIA Lua 5.3 streaming engine | Standard Lua 5.3 decompiler | Keep as preferred local engine where validated | Expand fixtures; compare semantic behavior, not just keyword balance |
| Existing ALVSIA LuaJIT route | LuaJIT disassembly/analysis | Keep as dedicated dialect route | Clearly label disassembly versus source reconstruction; add LuaJIT 2.0/2.1 fixtures |
| `zhangjiequan/luadec` | Native Lua 5.1 decompiler; 5.2/5.3 experimental | Build as a separate optional engine | Pin commit; MIT notice; Android ARM64 build; per-version fixtures and stripped-debug tests |
| `x3zvawq/unluac-rs` | Multi-dialect Rust decompiler; upstream advertises Lua 5.1–5.5, LuaJIT 2.1 and Luau v3–v7 | Primary PUC-Lua/LuaJIT engine and Luau fallback | MIT notice retained; pinned v1.4.4; Android ARM64 candidate compiled; finish Lua 5.5/Luau v7 fixture run, size/runtime validation and emulator execution before production enablement |
| `PumbaaDev/luau-decompiler` | Offline Rust Luau decompiler; upstream claims bytecode v3–v9 and MIT license | Primary Luau v3–v9 engine | Pinned commit `ee07098c31e11601a9ca434bc12932a4ded65f7b`; finish host v9 round-trip, Android ARM64 build/emulator smoke test and semantic fixture review before production enablement |
| Tovek | Luau decompiler | Secondary Luau comparison engine | Pin source and MIT license; build/test; compare output against primary Luau engine |
| luauDec | Luau decompiler / AST reconstruction | Research-only comparison candidate | Project is reported stale; assess source health and buildability before adoption |
| Unluau | Luau decompiler | Research-only fallback candidate | Apache-2.0 reported; alpha maturity and compatibility require fixture proof |
| `Coldzer0/LuaDecompiler` (cLuaDecompiler) | Lua 5.1–5.5 disassembly/decompilation, SSA and custom opcode tables | Research only; do not bundle by default | AGPL-3.0 obligations require a separate distribution decision; inspect implementation and Pascal/Lazarus Android feasibility |
| ByteVeil | Static Lua 5.1/Luau inspection, IR/CFG/SSA and partial lifting | Optional analysis backend | Verify license/dependencies; use for diagnostics and partial recovery, not as a universal source decompiler |
| ChunkSpy / LuaAssemblyTools | Bytecode inspection/disassembly | Diagnostic backend | Pin provenance/license and test parser compatibility; never label as full source decompilers |
| Lua 5.5 | New standard Lua dialect | First-class dialect through the unluac-rs candidate | Run official Lua 5.5 compiler fixture and re-parse output; retain parser-backed validation when available |
| Luau | Roblox Lua dialect, distinct from PUC Lua | First-class separate dialect: PumbaaDev v3–v9, unluac-rs fallback v3–v7 | Verify full serialized header and compile/decompile/re-compile with pinned official Luau compilers; v10+ remains unsupported by current candidates and must be reported honestly |
| Luraph (user's earlier “Luaraph”) | Commercial Lua/Luau obfuscator and VM virtualizer | Recognize and report protection family; separate authorized static-analysis workflow | Version fingerprints and lawful test fixtures required. No claim of generic devirtualization or universal recovery |
| “Lua ART” | Unidentified name | Keep unresolved in inventory | Do not invent a tool identity; add only after exact project, APK, link or artifact is identified |

## Smart Lua execution design

1. **Safe intake:** preserve original bytes; enforce file-size, time, memory and output limits; reject path traversal and unsafe archive paths.
2. **Container normalization:** detect supported wrappers/compression and extract only positively identified payloads into a private work directory.
3. **Dialect identification:** return format, version, confidence and evidence. Separate PUC Lua 5.x, LuaJIT, Luau and protected/unknown VM families.
4. **Protection triage:** detect known wrapper signatures and report confidence. Unknown/custom VM payloads remain analysis-only; never guess opcodes or silently rewrite data.
5. **Compatibility registry:** each engine declares dialect/version range, platform/ABI, license, provenance, executable/JAR hash, invocation contract, timeout and memory ceiling.
6. **Ordered engine attempts:** run only engines matching the detected dialect and available runtime. Keep each output isolated. Do not shell-interpolate user-controlled paths or flags.
7. **Validation:** validate parseability with the matching Lua/Luau parser/compiler where available. Structural keyword balancing is only a weak pre-check and must not be the sole release-quality validation.
8. **Comparison and selection:** compare multiple valid outputs using parser acceptance, control-flow/AST consistency, recovered function count, constants and confidence. Preserve valid alternatives for expert review.
9. **Honest result:** distinguish FULL, PARTIAL, DISASSEMBLY, STRINGS_ONLY, UNSUPPORTED and FAILED. Never label strings/constants as decompiled source.
10. **Report:** show detected dialect/version, attempted engines, engine versions, output validation, warnings, duration, and artifact hashes. Do not transmit source files, device location, private file lists or license secrets.

## Test corpus required

- Canonical Lua 5.1, 5.2, 5.3 and 5.4 bytecode produced by matching official compilers.
- Lua 5.5 and Luau fixtures only after their bytecode formats are explicitly supported.
- LuaJIT 2.0 and 2.1 fixtures.
- Stripped-debug and non-stripped chunks; nested functions, closures, varargs, loops, tables, upvalues and control-flow edge cases.
- Truncated, corrupt, wrong-endian, unsupported-version, oversized and malformed containers.
- Known wrapper fixtures and authorized Luraph samples by version; unknown/custom VM cases must return a bounded analysis report rather than fabricated source.
- Positive and negative tests for every engine, plus semantic/runtime comparison where a matching safe interpreter is available.
- Android ARM64 smoke tests on-device or emulator; CI host success alone does not prove Android runtime compatibility.

## Priority order

1. Audit and correct the existing orchestrator/JAR asset discovery and test harness.
2. Add a fixture-driven adapter contract so every engine can be plugged in without changing the user-facing Lua Center.
3. Evaluate and prototype `unluac-rs` for Android ARM64 as the broadest multi-dialect candidate.
4. Build and validate `luadec` for Lua 5.1–5.3 as a separate native fallback.
5. Complete PumbaaDev Luau v3–v9 fixture/runtime verification; evaluate Tovek only if coverage gaps remain.
6. Add Lua 5.5 only after detector/parser/compiler support is proven.
7. Add static protection-family identification for Luraph and other known wrappers; keep unsupported versions clearly marked.
8. Review APK size, startup latency, memory use, licensing and dependency footprint before enabling each runtime engine.

## Current CI state at time of this plan

The latest recorded Smart Lua Python validation run passed. The initial native ARM64 candidate build passed host fixtures for Lua 5.1–5.4 and LuaJIT 2.1. A later run passed Lua 5.5 but exposed the Luau v14 incompatibility in unluac-rs. The current candidate workflow now gates unluac-rs to Luau v3–v7, adds PumbaaDev for v3–v9, and includes v7/v9 host round-trip plus Android ARM64 emulator checks. Those expanded checks are pending. No ALVSIA APK build or release is part of this phase.

## Licensing and attribution

No upstream source, JAR or native binary is copied into ALVSIA solely because it appears in this inventory. Pin exact revisions, retain license texts and notices, record SHA-256 hashes, document modifications and check distribution obligations. AGPL/GPL or commercial/proprietary components require an explicit compatibility decision before bundling.

## Completion rule

A candidate is **INVENTORIED** when identified; **AUDITED** after source/license review; **BUILT** after an Android-compatible artifact exists; **INTEGRATED** after adapter/dispatch wiring; **TESTED** after fixture tests; and **VERIFIED** only after Android runtime tests pass. A documentation entry or successful desktop CI run alone never means an engine is fully integrated.
