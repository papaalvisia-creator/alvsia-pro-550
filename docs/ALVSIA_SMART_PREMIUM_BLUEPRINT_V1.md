# ALVSIA SMART PREMIUM — Build Blueprint v1

## Product identity
- APK display name: ALVSIA SMART PREMIUM
- New release line: 6.0.0-smart-premium
- Existing package identity remains unchanged during the first migration so login, panel, grants, signing and protected runtime compatibility are not broken.
- Splash, loading and in-tool progress language use the new ALVSIA SMART PREMIUM identity.
- Existing welcome audio remains the startup music asset until a dedicated new master is produced and validated; no unrelated audio asset is removed.

## UX rule
One visible Smart Engine per domain. Decompiler/compiler/protector/injector are internal capabilities of Smart Lua, not separate user-facing tools. The same consolidation principle applies to PAK, OBB, APK, Native and Transform.

## Core pipeline
INPUT -> PROGRAM DNA -> LAYER GRAPH -> PLAN -> ENGINE -> UNIVERSAL IR -> VALIDATE -> RECOVER/RETRY -> OUTPUT

## Workspace
- Mission-based processing.
- Original input is never mutated by default.
- File-backed intermediates and provenance.
- Resume/checkpoint architecture for long work.
- Import guard: maximum 5 GiB per individual imported file, repeatable across missions/imports; it is not a total app/workspace/job quota.
- Large files must use streaming/chunked processing and must not be read wholly into RAM.

## Security
The existing seven-layer SecurityFabric remains the baseline and is mapped to:
1. Build trust
2. Artifact trust
3. Channel/network trust
4. Crypto trust
5. Code/runtime trust
6. Environment/instrumentation trust
7. Response/degradation orchestration

Existing RASP, native guards, DEX/artifact integrity, sealed Python/assets, XopProtector packaging and panel trust controls remain defense-in-depth. New Smart Premium work must not bypass SessionGate, signed operation grants, TLS policy, private-module sealing or file safety.

## Upgrade path
Research and new adapters are added behind the engine registry. New formats, Lua dialects, validators, recovery strategies and protection methods must be pinned, licensed, hashed, fixture-tested and integrated without creating new user-facing submenu trees.

## Release gate
No Smart Premium APK is considered finished until:
- source/tests pass,
- debug/release build passes,
- native engines pass,
- security validation passes,
- XopProtector candidate passes,
- final v2/v3 signature verification passes,
- release audit returns PASS,
- final APK artifact is available.
