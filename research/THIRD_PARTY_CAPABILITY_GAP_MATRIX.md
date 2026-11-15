# THIRD-PARTY CAPABILITY GAP MATRIX

Scope: the ~30 Python tools in `kumpulan-source-tool` were statically scanned
(function names + capability keywords). Below is the comparison against the
ALVSIA engine (`app/src/main/python`). "Gap" = capability present in a
third-party tool but missing/weaker in ALVSIA.

| # | Capability | Third-party source(s) | How it works | ALVSIA equivalent | Gap | Integration / action | Risk | Test |
|---|---|---|---|---|---|---|---|---|
| 1 | PAK index parse/rebuild | `rjtool_core.py`, `AttcToolFor4.6.py` (`_load_index`,`_pack_index`,`_build_index_bytes`) | Tencent PAK v14 index decrypt + repack | `alvsia_core.TencentPakFile`, `compact_rebuild_pak` | none (ALVSIA equal/better) | already integrated | low | `test_pak_extraction.py` |
| 2 | SM4 decrypt (`_decrypt_sm4`,`_derive_sm4_key`) | `PREMIUM.py`,`UltimateEngineTool.py` | SM4-CBC with derived key per entry | `sm4_secret_registry.py` + `alvsia_core` SM4 path | **material gap** (key not present) | requires authorized key material; do NOT fabricate | high (auth) | fails-closed test exists |
| 3 | simple1/simple2 decrypt | `PREMIUM.py`,`UltimateEngineTool.py` | XOR/AES variants | `alvsia_core.run_file_simple1_crypt` | partial | verify parity on fixtures | low | add parity test |
| 4 | T24 → standard Lua convert | `T24XOR_tool_source`, `PREMIUM.py` (`_convert_t24_to_standard`) | XOR-obfuscated Lua deobfuscation | `lua_engine/t24.py` | partial | extend t24 XOR key recovery | low | `test_t24_lua.py` |
| 5 | Lua compile with luac | `PREMIUM.py` (`_compile_with_luac`) | invoke luac to produce bytecode | `lua_engine` orchestrator (decompile only) | **compile gap** | add version-aware compile adapter | med | new compile test |
| 6 | Lua compile with luatex | `PREMIUM.py` (`_compile_with_luatex`) | TeX-based variant | none | gap (niche) | low priority | low | n/a |
| 7 | Lua optimizer compile | `PREMIUM.py` (`_compile_with_optimizer`) | optimized bytecode | none | gap | optional | low | n/a |
| 8 | Lua version detect | `UltimateEngineTool.py` (`_detect_lua_version`) | header byte | `lua_engine/detector.py` | none (ALVSIA better) | integrated | low | `test_lua_engine.py` |
| 9 | unluac jar management | `UltimateEngineTool.py` (`_download_jar`,`_find_local_unluac`) | fetch/run unluac.jar | `lua_engine/orchestrator.py` | none | integrated | low | `test_unluac_jar.py` |
| 10 | best-compression selection | `UltimateEngineTool.py` (`_best_compress`) | try zlib/zstd pick smallest | `alvsia_core` repack | partial | add explicit best-of selector | low | add test |
| 11 | PAK footer update | `AttcToolFor4.6.py` (`_compute_updated_footer`) | recompute index hash/footer | `alvsia_core._pakdel_write_footer` | none | integrated | low | `test_pak_extraction_contract.py` |
| 12 | Batch PAK processing | many tools | loop over paks | `smart_pak_lua_engine` batch | partial | expose batch op | low | `test_smart_pak_lua_engine.py` |
| 13 | AES-GCM asset encryption | `valerrine.py`,`gen_enc` | AES-GCM | `alvsia_vm_protect`,`sealed_loader` | none | integrated | low | `test_xop_asset_encryption.py` |
| 14 | String recovery (XOR/AES/SM4) | `PREMIUM.py`,`rjtool_core.py` | brute-force string decrypt | `lua_string_recover.py` | partial | expand key search space | med | `test_crypto_string_recovery.py` (1 known failure) |
| 15 | Lua protector/obfuscator | `PREMIUM.py` | rename locals, encrypt strings | `lua_engine/lua_protector.py`,`protection_pipeline.py` | none (ALVSIA richer) | integrated | low | `test_lua_protection_pipeline.py` (3 failures) |
| 16 | Binary/ELF/DEX analyzer | `dump.py`,`Modders_Core` | string/hash dump | `alvsia_features`,`alvsia_metadata` | partial | add dedicated ELF/DEX inspector | low | new test |
| 17 | Signature detector | `PUBGM.py` | APK signature check | `alvsia_core` signing verify | none | integrated | low | `test_signed_apk_validator.py` |
| 18 | Safe patching/backup | `fix.py` | backup+patch | `archive_engine`,`alvsia_core.inject_files` | none | integrated | low | `test_pak_extraction_contract.py` |

## Priority gaps to implement (ordered)

1. **Lua compiler adapter** (rows 5,7): ALVSIA can decompile but has no
   first-class compile/recompile path for round-trip verification. This is the
   highest-value gap because round-trip validation is required by the mission.
2. **T24 deobfuscation parity** (row 4): extend XOR key recovery to match the
   third-party T24 tool on real fixtures.
3. **String recovery coverage** (row 14): the SM4 known-answer test currently
   fails; align with third-party `_decrypt_sm4` semantics.
4. **Best-compression selector** (row 10) and **batch PAK op** (row 12).

## License / safety note

All third-party sources are used for **behavioral comparison and clean-room
re-implementation only**. No credentials, private keys, server secrets, or
access material are extracted from them. SM4 material is never fabricated.
