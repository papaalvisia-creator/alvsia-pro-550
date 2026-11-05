# ALVSIA PRO — Full Reference Source Integration Registry

Audit baseline: user-provided `file_gabungan_referensi_source.zip`  
Archive SHA-256: `754129f13a96805f6905314c6685798cc66dabf0e8b568f9346864ade0be7af0`  
Manifest: `ALVISIA8/kumpulan-source-tool/source-tools/REFERENCE_BUNDLE_20261103/INCOMING_MANIFEST.sha256`  
Baseline application: PR #96 head `65d016351d5e40da4c0e6f60c1ec089009b29d86`

## Non-negotiable project target

Bring every source entry in the supplied bundle into the ALVSIA PRO capability inventory. Do not silently omit a source because it overlaps another engine. Reuse or consolidate duplicate functionality only after recording the source-to-app mapping and preserving its distinct behavior. A source file being present in the repository, a menu, or a catalog is not proof that its full behavior is implemented.

Branding requested by the owner:
- Public channel / project-facing tool output: `@ALVSIA_PRO`
- Personal Telegram contact: `@OriginalOnwerALV` (preserve exactly)

Replace legacy owner branding in project-owned code, UI, generated reports and output templates. Preserve legally required third-party license/provenance notices and do not rewrite upstream authorship metadata as if it were original ALVSIA authorship.

## Verified baseline facts

- The incoming manifest records **34 file entries**: 20 Python entries, 4 Lua/source entries, 2 JARs and 8 other/native/assets entries.
- The two `py_decryptor` entries have the same SHA-256 and are byte-identical duplicates in the manifest.
- PR #96 currently describes 19 top-level modules, 86 catalog sub-tools and 23 sealed Python modules. These are app catalog/inventory counts, not counts of imported source files.
- PR #96 lists seven reference-derived diagnostic sub-tools: Lua format probe, PAK integrity audit, OBB integrity audit, offline authorized-dump analyzer, static source triage, XOR known-vector self-test and AES known-answer self-test.
- PR #96 also records an IL2CPP Metadata v39 decoder addition. The supplied bundle manifest does not contain a file named `dump.py`; verify the actual source provenance before attributing that decoder to this bundle.
- The separate PR #91 describes further reference audit work, but it is draft/unmerged. Do not count its code as part of the PR #96 baseline APK unless merged or independently cherry-picked.
- No full per-file source-to-app parity audit or complete 34-entry functional test result is established by this registry's creation.

## Complete incoming file inventory and current disposition

Legend:
- **Existing overlap — verify parity:** app-side capability is documented, but exact feature parity with this source has not been established.
- **Integrated diagnostic:** a specific limited diagnostic capability is described in PR #96; this does not mean the entire source file was ported.
- **Candidate — audit and map:** source must be reviewed and each distinct useful capability mapped to an app module/dispatch/test.
- **Duplicate entry:** same bytes as another manifest entry; retain record, avoid duplicate implementation.

| # | Source entry | Manifest SHA-256 | Disposition at baseline |
|---:|---|---|---|
| 1 | `GAME_PATCH_TOOL.py` | `107097fbfb7b7e181e2f2f62b607df3a685555b19b535c9af577c2c39e6627fa` | Candidate — audit token exposure, replace any embedded credential with secret configuration; map legitimate patch-analysis functions |
| 2 | `GRW TOOL (1).py` | `0b8a655b988c183e6519b95e3ccf479a954bf32c9b3ea4c79e7f8e8d09cc44bc` | Candidate — audit and map all functions |
| 3 | `GRWTOOL_no_login (1).py` | `fe9b9f6ef35b5a2e0d1a108bc1097a819e480ee73882c92322ed6f19df951a21` | Candidate — audit and map all functions |
| 4 | `HR_DHAMA.py` | `5731f64fdd572b373641fb4d70ac1490917a9fd380b99ad51976568b28074417` | Existing crypto overlap — verify each cipher/mode/format against known-answer vectors |
| 5 | `LUADEC` | `1a9d70dc0b67a3cdee48c19c1753ff7e9dc3e1c92ad6da123ba5f905616b32ce` | Candidate Lua engine — identify architecture, version support and Android compatibility |
| 6 | `LUCKY_HUB_BYPASS_DUMPER.py` | `2d67ab97faf34992931d3e46c63c404a14771a19aafc9cf3706634a799` | Candidate — inspect every function and map safe, authorized analysis capabilities |
| 7 | `LUCKY_HUB_LUA_TOOL.py` | `60da6875cc88c399051fdbbed2a716a90471d9a2a17ed1e0f32e064ab9fba1f4` | Existing Lua overlap — verify parity and distinct workflows |
| 8 | `LUCKY_HUB_PY_PROTECTOR.py` | `5323679a84398b5eb1eb6f452df861e130d16b089ed8bb4b4d210089008123e3` | Existing protection overlap — verify formats, round-trip and runtime compatibility |
| 9 | `MASTER ANOGS.py` | `ff946e791e11ae0f3817cadf3a94a7ea1425bc217c842a768150cd0ff084e044` | Candidate — audit and map all functions |
| 10 | `MASTER.py` | `ec658bb3bc7a4639c78a21c098a7397cd7332f57ee00be9eed7e5c3c149d820c` | Existing XOR/binary analysis overlap — verify parity |
| 11 | `MASTERDECOMPILE.py` | `c585b6f6ff4efee2a80a7d2f392d55b7115435ea2ee1154aab2aaaa9f6d231dc` | Existing Lua/decompile overlap — map all reconstruction paths |
| 12 | `MASTEROBB.py` | `772805ebed424582ddb36aadf80f2852344a24b0b5d146db7d24a94750dde5f0` | Existing OBB/PAK overlap — map unique archive and workflow features |
| 13 | `PPH.py` | `820e2a9375a92fe7dfc03cf6029038c02d0c0098cff10c3a7dcb97af01dac2c6` | Existing crypto/format overlap — audit and map each capability |
| 14 | `README.md` | `ad5cd6fb27b887f82caac1b1189ee675c023f2bd07b659ba837a0e6d6aebe01a` | Documentation — extract feature inventory and dependencies |
| 15 | `aes_dump.py` | `9dd5dc78b278310af9cf7d02d4c6e903f5a7001dbce9b123ee8dddb2efab2e7a` | Existing AES/dump-analysis overlap — map offline authorized-file workflows |
| 16 | `bypass.cpp` | `95d7e785be1151240c1e36547ac3e90cd3b996e17a6e640f84f0b450efae9670` | Candidate — inspect and map legitimate diagnostics; do not silently discard source |
| 17 | `command` | `fab0a02f7f26ead62b1c1d308292504ebef6a412052f6ad19225d3c811207148` | Candidate — identify invocation contract and dependencies |
| 18 | `decode.html` | `ab93960fc62c61eec1f47a9cacee30553bcb5edf4bcf24cdd9d9382117500429` | Candidate — inspect UI/decoder behavior and web-runtime dependencies |
| 19 | `kaifee_decode_tool.so` | `f8035ee82c23463a0feac33d63575b8c590e5df09e29f914348de4d2e0281db8` | Native asset — identify ABI/architecture, exported symbols and safe invocation contract |
| 20 | `kashmiri_paste.lua` | `3c6ed8718936bb8c83bd99d9b48df8e4fd79e25b4ac8f391e5a4115dcf1971ab` | Lua/source — classify format and intended workflow |
| 21 | `luac` | `8f2de75bcab08e4a7f70776da1f948dad3a6e6c72ad730b14017e0d7c848906c` | Native executable — identify ABI, Lua version and compatibility |
| 22 | `magic noban.lua` | `0e13b093a014970d1a0cd15d56f51147afd6cf982d3d243ea5778b7d6ef8ba9d` | Lua/source — inspect and map legitimate Lua analysis/format functions |
| 23 | `mem_dump.py` | `86ea24decf2fa09279840fd8f828cdafe9db35b1a3e703f2db53ba28063e8938` | Candidate dump tooling — map offline dump parsing and authorized diagnostics |
| 24 | `nadeem without firewall.lua` | `11bfa54d29df95fd8da66f8c7cbcc8b9ecb54584811374569426a487d510abc6` | Lua/source — classify and map all legitimate transformations |
| 25 | `pak-tool-v5.0.py` | `110ded0899e188541706bc525ed5df11f690eaeabf36d45c950fcedf5e53fac3` | Existing PAK overlap — slot fingerprints and non-slot integrity checks remain explicit parity candidates |
| 26 | `php2shell_checker.py` | `19b1fe9f66b157d19d4550f1dfc1e499c5839bb1dd870182f461a65a3644dace` | Candidate — map static PHP/config security-checking functions |
| 27 | `py_decryptor (1).py` | `c0d5a10a383d6596b79beae52ae57065d28e29183fd94bd0470b10db0c8d957e` | Candidate — inspect payload formats and map supported offline recovery |
| 28 | `py_decryptor.py` | `c0d5a10a383d6596b79beae52ae57065d28e29183fd94bd0470b10db0c8d957e` | Duplicate entry of #27 — preserve provenance, do not duplicate code |
| 29 | `referensi.py` | `f3c608c7062bf25645e099fa23775ba53389092e6348f30eef3bfaecaeb49525` | Existing XOR/SO/crypto overlap — map all distinct functions and parity |
| 30 | `run com` | `4473f0d7667bbbd3ffd75ca5a00f36680e94eb0eb02da1c3a4ad9c67fc8be60d` | Candidate launcher — identify command behavior and replace external assumptions |
| 31 | `run_kaifee_so.py` | `cc179213d755c969e1da124b1afd5121d20346db509b0ee6c9c884283aed47bf` | Native wrapper — map ABI, invocation and error handling |
| 32 | `unluac.jar` | `98be0fa84ac73ca66dce2842a2e4512226f4c611b6500dc96415571fc5538fcc` | Existing Lua decompiler asset — verify version support and real round-trip fixtures |
| 33 | `unluac_pro.jar` | `34e64690c1cc8f6e3d68741cc4eca659cb1fed9bf870fecb511a2cc16fbc0838` | Existing Lua decompiler candidate — verify compatibility and provenance |

**Manifest count correction:** the manifest header says 34 entries and includes 34 lines; this table enumerates 33 named entries. Reconcile the manifest line count before marking inventory complete. Do not invent the missing filename.

## Existing app-side mapping (documented, not yet full parity proof)

| Capability family | Existing ALVSIA implementation documented | Remaining parity work |
|---|---|---|
| Lua | `alvsia_features.py`, `lua_engine/streaming_decompiler.py`, `lua_engine` modules, Unluac runner, parser/converter | Map every Lua source, VM mapping, wrapper, version and reconstruction path; validate with fixtures |
| PAK | `alvsia_core.py`: TencentPakFile, unpack/repack/delete/compact/rebuild paths | Add/verify slot fingerprints, non-slot region scan and overlap checks |
| OBB | `run_obb_extract`, `run_obb_rezip`, ZIP path/symlink protections | Add/verify CRC audit, duplicate/path checks, bounded archive handling |
| XOR | Existing Lua XOR helpers and private XOR key recovery | Compare encodings, offsets, multi-key modes and false-positive rates |
| SO/native | Binary URL scanner, SM4 key candidate scanner, SO audit and string/URL paths | Map native assets and wrapper compatibility by ABI |
| Crypto/decrypt | ZUC, AES indicators, XOR recovery, compression helpers, SM4 and archive crypto paths | Verify every algorithm/mode/padding with known-answer vectors |
| APK | Existing APK analysis and manifest tools | Map each source-specific feature and preserve source files |
| Python protection/decrypt | Sealed Python payload inventory and private tool engine | Map each source payload format, test reversible workflows and error cases |
| PHP/config | No exact parity established in baseline | Inspect `php2shell_checker.py` and map static checks |

## Required per-source completion fields

For every source entry, extend this registry with:
1. Source functions/classes/CLI actions.
2. Required Python/Java/native dependencies and minimum versions.
3. Exact ALVSIA module, dispatch operation and UI destination.
4. Whether behavior is reused, adapted, wrapped or consolidated.
5. Positive fixture, negative fixture, malformed input and large-input tests.
6. Expected output and output validation.
7. Branding scan result (`@ALVSIA_PRO`; personal contact `@OriginalOnwerALV`).
8. Status: INVENTORIED → ANALYZED → MAPPED → IMPLEMENTED → DISPATCHED → TESTED → VERIFIED.

Do not mark a source as IMPLEMENTED just because a similarly named menu exists. Do not mark it VERIFIED until a representative end-to-end test passes. Keep original user source archives intact.

## Credential handling

Any embedded GitHub credential found in source must never be copied into the APK, source history, reports or this registry. Remove it from active code, load credentials from environment/CI secrets when needed, and rotate/revoke the exposed token at the provider. Do not print the token value in logs.

## Scope and safety

Preserve and implement legitimate source capabilities, including static analysis, authorized file/dump analysis, format conversion, decompilation, archive handling, cryptography, protection and diagnostics. For capabilities that would directly enable unauthorized access, evasion, stealth, cheating, or extraction from unrelated live processes, retain the source/provenance and provide safe analysis or authorized-use alternatives rather than shipping an operational misuse workflow.

## Current completion statement

This registry establishes the 34-entry manifest as the required source inventory baseline. It does **not** claim all 34 entries or all their functions are already integrated. The next implementation increments must fill the per-source mappings and tests above, then report exact counts by status.
