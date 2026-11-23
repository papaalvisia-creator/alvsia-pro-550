# ALVSIA SMART PREMIUM 6.0.0 — Source Fusion Contract

## Public catalog
- **9 visible menus**
- **33 visible sub-tools**
- The previous 7/22 catalog is the foundation being expanded, not the final UI.
- Every public sub-tool is normalized through `SmartModuleRouter` to an existing authenticated provider operation.

## Source families used

### 1. IkramTool V130 4.7
Used as a deep implementation reference for Lua recovery, multi-XOR,
BGMI/T24 conversion, Tencent PAK, custom SM4, UE/asset analysis and
Lua protection.

### 2. TOOL.zip
Used as the combined-pipeline reference for unpack/decompile, batch
processing, protection, Lua→PAK injection, rebuild verification and
crypto/compression behavior.

### 3. RegulerResault_ALVSIA_tool_no_on_vip_engine.zip
Used as regression evidence. Its successful outputs and known failures are
validation fixtures/evidence only; the corpus is not shipped wholesale in
the APK.

## Production integration contract
The 9/33 UI is not a cosmetic rename. The public IDs are mapped to real
providers already present in the correct `com.alvsia.pro` project:
- Smart Lua: `lua_engine`, `smart_lua_engine`, `module_adapters`,
  plus retained BGMI/T24 and VM/deobfuscation providers.
- PAK/OBB: `archive_engine`, `smart_archive_engine`,
  `smart_pak_lua_engine`, plus retained Tencent PAK providers.
- Data/crypto: `smart_data_engine`, SM4/XOR registries and existing
  authenticated recovery providers.
- APK/native/forensic: existing read-only audit, string, URL, ELF/SO,
  entropy and metadata providers behind the authenticated bridge.
- Batch/dev-lab operations are routed to existing diagnostic/self-test
  providers rather than inventing a new fake backend.

## Invariants
1. Exactly 9 public menus and 33 public sub-tools are shipped.
2. Every public ID has an explicit router mapping.
3. No public ID falls through to arbitrary Python execution.
4. A button is not considered successful unless its backend returns a real
   validated artifact/report.
5. Lua decompile promotion accepts only a non-empty `.lua` source artifact.
6. Failed parsing/recovery never creates a fake success file.
7. The regression corpus is not bundled into the application.
8. Source imports do not weaken the existing login/session/grant gate.
9. The AI/Uncensored application is a separate project and is not used as
   the Smart Premium build base.
