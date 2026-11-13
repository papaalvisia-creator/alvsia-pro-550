# ALVSIA Unified Engine — Legacy Operation Inventory

Baseline source: legacy `main` branch `app/src/main/java/com/alvsia/pro/tool/SubMenus.kt`.
Status: inventory only; each operation still requires source-to-runtime reachability and real-output verification before it can be marked integrated.

This inventory defines the internal operations retained behind the fixed **7 menu / 20 submenu** UI. These operation IDs are not additional menus or submenus.

| Legacy ID | Legacy module | Unified menu | Fixed submenu | Internal operation IDs |
|---:|---|---|---|---|
| 1 | PAK Unpack | SMART PAK | SMART PAK UNPACK | `pak_full_unpack`, `pak_list`, `pak_info`, `pak_csv` |
| 2 | PAK Rebuild | SMART PAK | SMART PAK REBUILD | `pak_repack_full`, `pak_inject`, `pak_encrypt`, `pak_decrypt_restore` |
| 3 | PAK Compact | SMART PAK | SMART PAK COMPACT | `pak_delete_entry`, `pak_delete_all` |
| 4 | OBB Tools | SMART OBB | SMART OBB ENGINE | `obb_unzip`, `obb_rezip`, `obb_info`, `obb_integrity_audit` |
| 5 | Lua Tools | SMART LUA | SMART LUA DECOMPILER | `lua_decompile`, `lua_analyze`, `lua_constants`, `lua_clean_source`, `lua_xor_crypt`, `lua_multi_xor`, `lua_format_probe`, `lua_vm_deobfuscate`, `pubg_lua_convert`, `t24_lua_decompile` |
| 6 | File Scan | SMART DATA | SMART FILE SCAN & METADATA | `string_scan`, `hash_scan`, `metadata_v39_decode` |
| 7 | Workspace | WORKSPACE & REPORT | SMART WORKSPACE | `clear_work` |
| 8 | Export Report | WORKSPACE & REPORT | SMART REPORT EXPORT | `export_report` |
| 9 | Rebrand | WORKSPACE & REPORT | SMART REBRAND | `rebrand_auto`, `rebrand_manual`, `rebrand_scan` |
| 10 | SO Analyzer | SMART ANALYSIS | SMART SO ANALYZER | `so_xor_scan`, `so_multi_xor`, `so_url_dump`, `so_aes_probe`, `so_patch_url`, `url_scan_so`, `sm4_find_all`, `so_dump_audit` |
| 11 | Frida Tracer | SMART ANALYSIS | SMART JNI TRACE | `frida_jni_hook`, `frida_js_dump`, `frida_spawn` |
| 12 | XOR Suite | SMART DATA | SMART XOR ENGINE | `xor_single_byte`, `xor_custom_key`, `xor_luas_strip`, `xor_batch`, `xor_selftest` |
| 13 | Decrypt Engine | SMART DATA | SMART DECRYPT ENGINE | `dec_auto`, `dec_aes_cbc`, `dec_aes_ecb`, `dec_zuc`, `dec_sm4`, `dec_simple1`, `dec_selftest` |
| 14 | PAK Deep | SMART PAK | SMART PAK DEEP ENGINE | `pak_deep_aes`, `pak_deep_zstd`, `pak_deep_zuc`, `pak_deep_sm4`, `pak_deep_auto`, `pak_deep_integrity_audit`, `sm4_keyfind` |
| 15 | String Recover | SMART LUA | SMART LUA STRING RECOVERY | `str_recover`, `str_constant_pool`, `str_xref` |
| 16 | Lua Inject | SMART LUA | SMART LUA INJECT | `lua_patch_byte`, `lua_inject_hook`, `lua_mod_repack` |
| 17 | Anti-RE Audit | SMART ANALYSIS | SMART ANTI-RE AUDIT | `audit_apk`, `audit_lua`, `audit_so`, `anti_re_source_triage` |
| 18 | Lua Protector | SMART LUA | SMART LUA PROTECT | `lua_smart_protect`, `lua_smart_protect_strong`, `lua_protect_encrypt`, `lua_protect_decrypt`, `lua_vm_protect` |
| 19 | ALVSIA Private Tool | ALVSIA PRIVATE | ALVSIA PRIVATE ENGINE | `priv_zuc_decrypt`, `priv_aes_scan`, `priv_xor_recover`, `priv_lua_parse`, `priv_lua_convert`, `priv_lua_heping`, `priv_compress_fit`, `priv_apk_audit`, `priv_apk_manifest`, `priv_str_recover`, `priv_entropy_map`, `priv_pak_manifest` |\n| 20 | Smart Asset Engine | SMART ANALYSIS | SMART ASSET MODDING ENGINE | `asset_fingerprint`, `asset_scan_ids`, `asset_context`, `asset_patch`, `asset_validate` |

## Inventory checks

- Legacy module IDs discovered: 1..19. New Smart Asset provider: 20.
- Unique legacy modules: 19 + 1 new Smart Asset provider.
- Internal operation declarations discovered: 89.
- Operation IDs must be unique or explicitly documented as shared aliases; all must resolve to a registered provider.
- No inventory row may be removed solely to reduce the visible submenu count.
- A submenu has no user-visible internal operation selector or nested tool list. The Smart Engine detects the input and selects/runs compatible internal stages automatically; required configuration fields remain inside the same workspace.

## Verification required per operation

1. Automatic input detection and internal route selection inside the owning Smart submenu; only required configuration fields are shown.
2. Smart router maps the action to the correct legacy provider ID.
3. Kotlin bridge passes the exact operation ID and the correct task/workspace context.
4. Python/native implementation exists and has authorization coverage.
5. Output/report is produced and validated; source input remains unchanged.
6. Regression test covers success, malformed input, cancellation/timeout, and failure without fake output.
