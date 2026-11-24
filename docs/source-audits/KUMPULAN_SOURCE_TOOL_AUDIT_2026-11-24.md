# Recursive source audit — `kumpulan_source_tool.zip`

**Audit date:** 2026-11-24  
**Scope:** read-only inventory and static parsing. No source file or executable was run.  
**Original archive:** `/kumpulan_source_tool.zip` in the user's Library.  
**Root SHA-256:** `64b53a7a836be2e308d350a76aee1c630adac53411418c875468c3b9bc399573`

## Integrity and inventory

- Root ZIP CRC: PASS; 71 non-directory entries.
- Three nested ZIPs found and each passed CRC:
  - `4.6 MENU LUA SOURCE.zip` — 3 entries.
  - `LUA_TOOL.zip` — 6 entries.
  - `luatool.py.zip` — 3 entries.
- Recursive total: **83 files** across the root and nested archives.
- Python sources: **68**; AST parse PASS: **64**; parse/read failures: **4**.
- Exact duplicate groups: **3** (6 duplicate file instances).

## Capability evidence found

### Tencent PAK / archive engine
Multiple independent implementations expose overlapping Tencent PAK structures and operations:
`PakInfo`, `TencentPakInfo`, `PakCompressedBlock`, `TencentPakEntry`, `PakCrypto`, `PakCompression`, `TencentPakFile`, extraction, repacking, chunk handling, comparison, index rebuild, and integrity-oriented checks.

High-value candidates include `1.py`, `ATTC-4.5-TOOL.py`, `DHVIP.py`, `DSX43.py`, `GODXKAZUKI.py`, `HACKER42O.py`, `KAZUKII1_fixed.py`, `Star.py`, `T24XOR_tool_source.py`, `USMANxTOOL.py`, `WXNTOOL_2.py`, `bekit.py`, `fix.py`, `pak7 (3).py`, `skuy_pakcore.py`, `u5.py`, `v.py`, and `yt.py`.

### OBB / game patch workflows
Evidence includes generic OBB extract/repack, Mini-OBB, OBBZSDIC, GamePatch repack, index-to-CSV export, offset reads, size correction, and pair selection/validation. Candidate sources include `ATTC-4.5-TOOL.py`, `DHVIP.py`, `GODXKAZUKI.py`, `HACKER42O.py`, `T24XOR_tool_source.py`, `USMANxTOOL.py`, `ankit.py`, and `obb_tool_termux.py`.

### Lua / bytecode / conversion
Evidence includes Lua/LuaJIT environment detection, unluac/luadec invocation, Lua 5.3 compiler detection, BGMI↔standard conversion, T24/PUBG conversion, decompile/recompile, multi-XOR and candidate probing, Lua normalization, and Lua-to-PAK injection/repack workflows. Candidate sources include `7.py`, `ATTC-4.5-TOOL.py`, `GRW.py`, `HexaCore.py`, `JINSHIPAPA.py`, `T24XOR_tool_source.py`, `UltimateEngineTool.py`, `VINESHOP.py`, `ldz.py`, `lua.py`, `nadeem.py`, and `xxy.py`.

### Crypto / compression
SM4 implementations and key finders, ZUC, AES-related transforms, XOR/multi-XOR, zlib/Zstandard compression, and format-specific block transforms are present. Candidate sources include `ankit.py`, `sm4_finder_tr.py`, `T24XOR_tool_source.py`, `7.py`, and PAK engine variants.

### Unreal assets / skin and resource modding
Evidence includes UAsset/UEXP processing, asset beautification, skin ID/pair mapping, Mini skin workflows, ZSDIC operations, lobby index swapping, offset/size correction, and resource recovery. Candidate sources include `3.py`, `4.py`, `5.py`, `UassetUexp.py`, `GODXKAZUKI.py`, `HACKER42O.py`, `KAZUKII1_fixed.py`, `T24XOR_tool_source.py`, and `UltimateEngineTool.py`.

## Exact duplicates

1. `5_6255716464733461586.py` and `Hwid.py` — SHA-256 `42a3099e5431e085385b34297d7a105362a2a89219d3517c96c3eb3189a0b83f`.
2. `rjtool_core (1).py` and `rjtool_core.py` — SHA-256 `51d930c180b9b08cc6e994b6608c2e80d08e202eecb566d6bc3890aae2e34eef`.
3. `小文dd (1).py` and `小文dd.py` — SHA-256 `1dae3365032af2aa8d636929cbac3c11fd2fe4a1c950aece7299c39f8a9d4d18`.

Deduplicate exact copies at integration time; preserve one canonical copy and retain provenance.

## Python parse/read failures requiring review

- `Moddercore.py`, line 2376: incomplete expression `if  and extract_dir.exists():`; do not import until repaired and tested.
- `gen_enc.py`: UTF-8 decode failure at byte 0x93; inspect encoding (likely legacy Windows encoding) before parsing. No encoding conversion was written back to the archive.
- `rjtool_core.py` and `rjtool_core (1).py`: same duplicated malformed/obfuscated generated line 657; both fail with `SyntaxError: invalid decimal literal`. Treat as one unresolved source family, not two separate engines.

One valid Python file emitted a `SyntaxWarning` for an invalid escape in `shellfinder.py`; it parsed successfully but needs a small source-quality review before adoption.

## Android ARM64 compatibility and safety decisions

- The nested `LUA_TOOL.zip` contains `decyash.exe`, `luadec.exe`, and `lua53.dll`; these are desktop Windows binaries and must not be bundled as Android ARM64 executables.
- `unluac_patched.jar` is a JVM candidate, but its license, provenance, runtime compatibility, digest, and regression behavior must be verified before packaging.
- Native/no-extension payloads are evidence-only until file type, architecture, provenance, and license are established.
- Review all candidate code for destructive source mutation, unbounded memory use, automatic dependency installation, credential/key leakage, and network downloads. Keep original inputs unchanged and isolate generated outputs.
- Unrelated password-bypass or SMS-bombing utilities are excluded from ALVSIA SMART TOOL integration. Only authorized, read-only instrumentation/diagnostic workflows may be considered for a Frida-related module.

## Five-archive scope status

This is **one available source bundle**, not proof that all five owner-designated archives have been audited. The exact named archives below were not found in the current Library ZIP listing and remain pending byte-level access:
1. `IkramTool_V130_4.7.zip`
2. `TOOL.zip`
3. `RegulerResault_ALVSIA_tool_no_on_vip_engine.zip`
4. `MANKS-TOOL_ALVSIA.zip`
5. `_workspace_ALVSIA_TOOL_PREMIUM_v4.0.1.zip`

The findings above can already inform PAK/OBB/Lua/Crypto/Modding submenu mapping, but no capability is considered integrated until it has an Android-compatible adapter and acceptance tests.
