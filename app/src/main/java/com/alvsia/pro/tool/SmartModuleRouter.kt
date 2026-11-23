package com.alvsia.pro.tool

/**
 * Normalizes the 9-menu / 33-tool public catalog to authenticated, existing
 * provider operations. Public IDs never become arbitrary Python operations.
 */
object SmartModuleRouter {
    fun backendModule(visibleModuleId: Int, subId: String): Int = when (subId) {
        "universal_file_detect" -> 10
        "workspace_report" -> 6
        "engine_health" -> 12

        "lua_smart_analyze" -> 5
        "lua_recovery_normalize" -> 5
        "lua_t24_convert" -> 19
        "lua_multi_xor" -> 5
        "lua_protect_transform" -> 18
        "lua_custom_inject" -> 16

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

        "file_report" -> 6
        "strings" -> 6
        "entropy" -> 19
        "hex_preview" -> 19

        "batch_audit", "regression_compare" -> 19
        "self_test" -> 12
        else -> visibleModuleId
    }

    fun normalizedSubId(visibleModuleId: Int, subId: String): String = when (subId) {
        "universal_file_detect" -> "so_dump_audit"
        "workspace_report", "dex_report", "asset_report", "file_report" -> "hash_scan"
        "engine_health", "self_test" -> "xor_selftest"

        "lua_smart_analyze" -> "lua_analyze"
        "lua_recovery_normalize" -> "lua_decompile"
        "lua_t24_convert" -> "pubg_lua_convert"
        "lua_multi_xor" -> "lua_multi_xor"
        "lua_protect_transform" -> "lua_smart_protect"
        "lua_custom_inject", "pak_lua_inject" -> "lua_mod_repack"

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