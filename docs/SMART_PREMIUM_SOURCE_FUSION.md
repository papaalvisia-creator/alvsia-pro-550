# ALVSIA SMART PREMIUM 6.0.0 — Source Fusion Contract

## Public catalog
- **7 visible menus**
- **22 visible sub-tools**
- Legacy provider IDs remain internal through `SmartModuleRouter`.

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

## Correct Smart Premium backends
The production tree resolves these capabilities through existing backend
contracts:
- `lua_engine` + `alvsia_features` + `module_adapters` for Smart Lua.
- `archive_engine` for PAK/OBB inspect/extract/rebuild/integrity.
- `smart_data_engine` for recovery/XOR/SM4/metadata.
- Existing authenticated `alvsia_bridge_impl` and `SmartModuleRouter` keep
  legacy providers behind the seven-menu public surface.

## Safety invariants
1. A button is not considered successful unless its backend returns a real
   validated artifact/report.
2. Lua decompile promotion accepts only a non-empty `.lua` source artifact.
3. Failed parsing/recovery never creates a fake success file.
4. The regression corpus is not bundled into the application.
5. Source imports do not weaken the existing login/session/grant gate.
6. The AI/Uncensored application is a separate project and is not used as
   the Smart Premium build base.
