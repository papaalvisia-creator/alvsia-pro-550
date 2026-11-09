# ALVSIA PRO — Lua Smart Decompile + Lua Smart Protector Audit
Date: 2026-11-09
Repository: papaalvisia-creator/alvsia-pro-550
Working branch: feat/lua-intelligence-orchestrator-20261107

## Objective
Build two integrated, extensible Lua engines:
1. **Lua Smart Decompile** — identify dialects and containers, recursively recover layered payloads, decompile compatible bytecode, analyze VM wrappers, validate outputs, and report fidelity honestly.
2. **Lua Smart Protector** — safely parse source, apply semantics-preserving transformations, compile with a real target compiler, optionally virtualize/transform bytecode, encrypt assets with authenticated encryption, and verify runtime compatibility and tamper detection.

This document is an engineering audit and implementation plan, not a claim that either engine is complete.

## Scope and truthfulness
Target dialect matrix:
- PUC Lua 5.1, 5.2, 5.3, 5.4, 5.5
- LuaJIT 2.0/2.1 (including architecture/GC64-sensitive bytecode variants)
- Luau bytecode versions supported by a pinned, tested backend
- GLua and embedded/vendor dialects through explicit adapters and fixtures

Every decompile result must use a fidelity status: LOSSLESS, SEMANTIC, PARTIAL, DISASSEMBLY, STRINGS_ONLY, UNSUPPORTED, or FAILED. Stripped debug names, comments, and formatting cannot generally be reconstructed from bytecode. Unknown/custom encrypted payloads may remain unsupported until their format is understood.

## Source audit — Smart Decompile
Current `run_lua_smart()` in `app/src/main/python/alvsia_features.py`:
- Reads the complete input using `read_bytes()` before detection.
- May create a comment-prefix slice, then unwraps only one container layer.
- Runs protected-pattern preflight once, then builds one registry and invokes one engine pipeline.
- Does not recursively enqueue recovered artifacts and re-detect them as L1 → L2 → L3 → …
- Falls back to constants, strings, and XOR candidates; those artifacts must never be mistaken for recovered source.
- A source passthrough candidate is not evidence that an obfuscated wrapper has been devirtualized.

Required architecture:
- File-backed `LayerArtifact` graph: artifact ID, SHA-256, size, parent ID, detected dialect/format, transformation, confidence, status, output path.
- Recursive work queue; every valid output is re-detected and offered to compatible extractors/engines.
- Cycle detection by content hash; bounded depth, total expansion ratio/bytes, wall-clock budget, and per-engine timeout.
- Streaming hash/copy/decompression and file-backed intermediates; do not hold input + multiple candidates in RAM.
- Sandboxed/static analysis by default. Never execute an unknown input script just to discover its payload.
- Candidate ranking based on parser/compiler validation, semantic evidence, and fidelity—not printable ratio alone.
- Preserve original input and intermediate artifacts with a machine-readable manifest and diagnostics.

Large-file gates:
- Test 5 MB, 50 MB, and larger generated fixtures.
- Verify no truncation, bounded peak memory, bounded expansion, cancellation, disk-full handling, and cleanup of temporary files.
- Ensure the Android UI reports progress and a useful error instead of crashing or returning a generic read failure.

## Source audit — Smart Protector
Current `lua_engine/lua_protector.py` findings:
1. `_rename_locals()` uses regular expressions over source text. It is not scope-aware and can rename identifiers in strings/comments or collide across nested scopes; it can change program behavior.
2. `_encode_strings_in_source()` uses a regex for double-quoted strings only. It does not correctly parse escaped quotes, long-bracket strings, comments, or dialect-specific syntax.
3. `_inject_dead_code()` inserts text based on line prefixes, not an AST. This can alter lexical/scope behavior and is not a dependable protection pass.
4. `compile_lua_bytecode()` explicitly emits a synthetic Lua 5.3-looking stub with XOR-wrapped source; it is not a real Lua compiler output and must not be described as genuine bytecode compilation.
5. `encrypt_lua()` uses AES-256-GCM v2, which is the correct family of authenticated encryption, but the current KDF uses PBKDF2-HMAC-SHA256 with only 4096 iterations. The header checksum is a truncated MD5 value, not a CRC32. If no key is supplied, a plaintext `.alv_key` file is written next to the ciphertext.
6. Legacy v1 custom XOR/block-mix code remains for backward decryption. Do not use custom mixing as a new protection algorithm; keep legacy decoding isolated and clearly marked.
7. Full mode currently chains regex obfuscation → synthetic bytecode stub → AES-GCM. This is not yet a verified VM-based protection pipeline and must not be marketed as maximum-strength protection.

Required Protector architecture:
- Parse with a dialect-aware lexer/parser and build a scope-aware AST. Reject unsupported syntax rather than silently applying unsafe regex transformations.
- Transformation passes are individually switchable, deterministic when seeded for tests, and semantics-preserving by default.
- Real bytecode compilation via pinned, matching Lua/LuaJIT/Luau compiler toolchains; record compiler version, target dialect, and ABI/bytecode version.
- Optional custom VM backend with explicit supported-language subset, opcode/constant encoding, integrity manifest, and runtime compatibility tests. Never claim cryptographic secrecy from obfuscation.
- AES-256-GCM or another vetted AEAD only for confidentiality/integrity; unique nonce per key; authenticated metadata; explicit key IDs and rotation.
- Derive keys from passphrases using a current, documented KDF profile; use Android Keystore or an equivalent protected key source where possible. Never silently export a generated key as plaintext beside the protected file.
- Stream large files through authenticated encryption/decryption; verify tag before publishing plaintext output.
- Keep v1 legacy decryption as a compatibility-only path until migration tests pass; no new v1/custom-cipher outputs.
- Add tamper, wrong-key, truncated-file, nonce/metadata, key-rotation, large-file, and cross-version round-trip tests.

## Integration contract
- Both engines share the dialect registry, parser/compiler inventory, format metadata, and test corpus.
- Protector outputs must carry a manifest sufficient for Smart Decompile to identify ALVSIA-owned wrappers and report the expected protection profile. This is metadata-assisted recovery, not a hidden master key.
- Smart Decompile must never bypass authentication or claim it can recover ciphertext without the authorized key.
- Protector must produce fixtures that Smart Decompile can identify, unwrap where authorized, and classify correctly.
- Android ARM64 packaging and on-device runtime validation are required before enabling either native engine in a release APK.

## Reference research
- Lua 5.5 manual and versioned official manuals: https://www.lua.org/manual/
- Lua official release/download and build guidance: https://lua.org/download.html
- LuaJIT compatibility and bytecode notes: https://luajit.org/luajit.html and https://luajit.org/extensions.html
- unluac-rs (MIT; candidate multi-dialect decompiler; pin exact revision and test before shipping): https://github.com/x3zvawq/unluac-rs
- PumbaaDev Luau decompiler (separate Luau backend; pin revision and verify opcode coverage): https://github.com/PumbaaDev/luau-decompiler
- LuaObfVM (Apache-2.0; reference for custom VM, opcode/constant transforms, anti-tamper; retain notices if ever reused): https://github.com/onlytrisdev/LuaObfVM
- Ferret (MIT; Lua 5.4 VM obfuscator reference and benchmark approach): https://github.com/LuaCrypt/ferret
- luaparse (version-configurable Lua 5.1–5.5/LuaJIT parser candidate; verify release maturity and grammar gaps): https://github.com/entropyMaker/luaparse
- OWASP Cryptographic Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

License rule: inventory every dependency and dataset before integration. Pin immutable revisions, preserve required notices, and do not copy proprietary/source-available implementations into ALVSIA.

## Execution order
P0. Protect current project state; no live-server/autostart changes and no APK release.
P1. Implement recursive file-backed decompile artifact graph with cycle/resource limits and tests.
P2. Fix large-file streaming and Android error handling; add 50 MB+ regression tests.
P3. Add parser-backed source validation and fidelity classification.
P4. Replace Protector regex transforms with AST/scope-aware passes; remove synthetic compile claims.
P5. Implement real compiler adapters and an explicit VM backend with supported-subset diagnostics.
P6. Upgrade AEAD/key lifecycle and streaming; retain legacy read compatibility.
P7. Cross-test Protector outputs through Smart Decompile and vice versa, then Android ARM64/device validation.
P8. Only after all gates pass, prepare a single final signed APK.

## Acceptance criteria
- No false SUCCESS for wrapper source, strings, disassembly, or partial output.
- Nested layers are traversed until no new unique candidate is found or a documented safety budget is reached.
- Large-file tests prove bounded memory and exact byte counts/hashes.
- Protector transformations pass differential execution tests against the original source on every supported runtime.
- Encryption rejects wrong keys and tampering; no plaintext key sidecar is emitted by default.
- CI is green, native binaries are packaged correctly, and Android runtime tests pass on device/emulator.
