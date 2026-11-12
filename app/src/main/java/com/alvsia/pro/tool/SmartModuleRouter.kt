package com.alvsia.pro.tool

/**
 * Maps the compact visible Smart catalog to the existing provider IDs.
 *
 * This is intentionally internal: users see Smart engines, while old providers
 * remain compatible implementation modules. No legacy menu is exposed.
 */
object SmartModuleRouter {
    fun backendModule(visibleModuleId: Int, subId: String): Int = when (visibleModuleId) {
        1 -> when {
            subId.startsWith("lua_protect") || subId == "lua_vm_protect" ||
                subId == "lua_smart_protect" || subId == "lua_smart_protect_strong" -> 18
            subId.startsWith("lua_patch") || subId.startsWith("lua_inject") -> 16
            else -> 5
        }
        2 -> when {
            subId.startsWith("pak_deep") || subId == "pak_deep_integrity_audit" -> 14
            subId == "pak_smart_inspect" || subId == "pak_full_unpack" -> 1
            else -> 2
        }
        3 -> 4
        4 -> when {
            subId.startsWith("sm4_") -> 10
            subId.startsWith("str_") -> 15
            subId == "metadata_v39_decode" -> 6
            subId.startsWith("xor_") -> 12
            else -> 13
        }
        5 -> when {
            subId.startsWith("frida_") -> 11
            subId.startsWith("audit_") -> 17
            else -> 10
        }
        6 -> when (subId) {
            "clear_work" -> 7
            "hash_scan" -> 6
            else -> 8
        }
        7 -> 19
        else -> visibleModuleId
    }

    fun normalizedSubId(visibleModuleId: Int, subId: String): String = when {
        visibleModuleId == 2 && subId == "pak_smart_inspect" -> "pak_info"
        visibleModuleId == 2 && subId == "pak_deep_auto" -> "pak_deep_auto"
        visibleModuleId == 3 && subId == "obb_smart_inspect" -> "obb_info"
        visibleModuleId == 4 && subId == "data_auto_recover" -> "dec_auto"
        visibleModuleId == 5 && subId == "so_url_dump" -> "so_url_dump"
        else -> subId
    }
}