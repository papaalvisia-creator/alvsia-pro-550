package com.alvsia.pro.tool

/**
 * Normalizes the 10-menu / 59-subtool public catalog to authenticated,
 * existing provider operations. Legacy public IDs remain explicit aliases.
 * Disabled catalog entries are blocked in SubMenuScreen until their adapter
 * and acceptance tests are complete.
 */
object SmartModuleRouter {
    fun backendModule(visibleModuleId: Int, subId: String): Int = when (subId) {
        // 10 x 59 public IDs — verified provider routes
        "apk_structure_inspector", "apk_dex_bytecode_inspector",
        "apk_signature_integrity_verify", "apk_manifest_permission_audit" -> 17

        "pak_profile_fingerprint", "pak_explorer_info", "pak_extract_unpak" -> 1
        "pak_entry_compare_replace", "pak_rebuild_repack" -> 2
        "pak_compact_rebuild_verify" -> 3

        "obb_format_inspector", "obb_extractor", "obb_integrity_pair_validator" -> 4

        "lua_smart_analyze", "lua_vm_version_detector",
        "lua_smart_decompile", "lua_recovery_normalize" -> 5
        "lua_bytecode_inspector", "lua_t24_bgmi_pubg_converter" -> 19
        "lua_custom_inject" -> 16

        "crypto_xor_multi_xor", "crypto_aes_candidate_transform",
        "crypto_sm4_engine", "crypto_zuc_engine", "crypto_key_pattern_scanner" -> 19

        "forensics_universal_file_detection" -> 10
        "forensics_file_signature_hash" -> 6
        "forensics_string_url_recovery", "forensics_entropy_region",
        "forensics_hex_structure_viewer", "forensics_evidence_report" -> 19

        "native_elf_so_inspector", "native_abi_dependency_report" -> 10
        "native_strings_symbols" -> 6
        "lab_engine_self_test" -> 12

        // Legacy 9 x 33 public IDs — kept as compatibility aliases
        "universal_file_detect" -> 10
        "workspace_report" -> 6
        "engine_health" -> 12

        "lua_smart_analyze_legacy" -> 5
        "lua_smart_analyze_old" -> 5
        "lua_recovery_normalize_legacy" -> 5
        "lua_t24_convert" -> 19
        "lua_multi_xor" -> 5
        "lua_protect_transform" -> 18
        "lua_custom_inject_legacy" -> 16

        "pak_info" -> 1
        "pak_extract" -> 1
        "pak_lua_inject" -> 16
        "pak_repack" -> 2

        "asset_uasset_classify", "asset_uexp_classify",
        "asset_locres_umap_classify" -> 19
        "asset_report" -> 6

        "apk_audit" -> 17
        "dex_report" -> 6
        "url_scan" -> 10

        "so_audit", "native_strings", "abi_dependency_report" -> 10

        "aes_scan" -> 19
        "zuc_decrypt" -> 13
        "string_recovery" -> 15

        "file_report", "strings" -> 6
        "entropy", "hex_preview" -> 19

        "batch_audit", "regression_compare" -> 19
        "self_test" -> 12
        else -> visibleModuleId
    }

    fun normalizedSubId(visibleModuleId: Int, subId: String): String = when (subId) {
        // 10 x 59 public IDs — verified provider routes
        "apk_structure_inspector", "apk_dex_bytecode_inspector",
        "apk_signature_integrity_verify" -> "priv_apk_audit"
        "apk_manifest_permission_audit" -> "priv_apk_manifest"

        "pak_profile_fingerprint" -> "pak_info"
        "pak_explorer_info" -> "pak_list"
        "pak_extract_unpak" -> "pak_full_unpack"
        "pak_entry_compare_replace" -> "pak_inject"
        "pak_rebuild_repack" -> "pak_repack_full"
        "pak_compact_rebuild_verify" -> "pak_integrity_audit"

        "obb_format_inspector" -> "obb_info"
        "obb_extractor" -> "obb_unzip"
        "obb_integrity_pair_validator" -> "obb_integrity_audit"

        "lua_smart_analyze", "lua_vm_version_detector" -> "lua_analyze"
        "lua_bytecode_inspector" -> "priv_lua_parse"
        "lua_smart_decompile", "lua_recovery_normalize" -> "lua_decompile"
        "lua_t24_bgmi_pubg_converter" -> "pubg_lua_convert"
        "lua_custom_inject" -> "lua_mod_repack"

        "crypto_xor_multi_xor" -> "priv_xor_recover"
        "crypto_aes_candidate_transform" -> "dec_auto"
        "crypto_sm4_engine" -> "pak_deep_sm4"
        "crypto_zuc_engine" -> "priv_zuc_decrypt"
        "crypto_key_pattern_scanner" -> "sm4_find_all"

        "forensics_universal_file_detection" -> "so_dump_audit"
        "forensics_file_signature_hash" -> "hash_scan"
        "forensics_string_url_recovery" -> "priv_str_recover"
        "forensics_entropy_region" -> "priv_entropy_map"
        "forensics_hex_structure_viewer", "forensics_evidence_report" -> "priv_dump_audit"

        "native_elf_so_inspector", "native_abi_dependency_report" -> "so_dump_audit"
        "native_strings_symbols" -> "string_scan"
        "lab_engine_self_test" -> "xor_selftest"

        // Legacy 9 x 33 aliases
        "universal_file_detect" -> "so_dump_audit"
        "workspace_report", "dex_report", "asset_report", "file_report" -> "hash_scan"
        "engine_health", "self_test" -> "xor_selftest"

        "lua_recovery_normalize_legacy" -> "lua_decompile"
        "lua_t24_convert" -> "pubg_lua_convert"
        "lua_multi_xor" -> "lua_multi_xor"
        "lua_protect_transform" -> "lua_smart_protect"
        "lua_custom_inject_legacy", "pak_lua_inject" -> "lua_mod_repack"

        "pak_info" -> "pak_info"
        "pak_extract" -> "pak_full_unpack"
        "pak_repack" -> "pak_repack_full"

        "asset_uasset_classify", "asset_uexp_classify",
        "asset_locres_umap_classify" -> "priv_dump_audit"

        "apk_audit" -> "audit_apk"
        "url_scan" -> "so_url_dump"

        "so_audit", "native_strings", "abi_dependency_report" -> "so_dump_audit"

        "aes_scan" -> "priv_aes_scan"
        "zuc_decrypt" -> "dec_zuc"
        "string_recovery" -> "str_recover"

        "strings" -> "string_scan"
        "entropy" -> "priv_entropy_map"
        "hex_preview" -> "priv_dump_audit"

        "batch_audit", "regression_compare" -> "priv_dump_audit"
        else -> subId
    }
}