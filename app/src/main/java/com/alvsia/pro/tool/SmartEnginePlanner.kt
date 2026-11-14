package com.alvsia.pro.tool

import java.io.File

/**
 * Selects an internal implementation for a visible Smart submenu.
 *
 * The 89 legacy operation IDs stay implementation details. Selection is
 * based on detected input and existing workspace context; this class never
 * creates another navigation level or exposes an operation list to users.
 */
object SmartEnginePlanner {
    fun resolve(
        submenu: SubTool,
        actions: List<SubTool>,
        detection: FileMagic.DetectionResult?,
        inputName: String?,
        workDir: File
    ): SubTool {
        require(actions.isNotEmpty()) { "Smart submenu has no registered implementation" }
        val byId = actions.associateBy { it.id }
        val provider = submenu.legacyModuleId ?: actions.first().legacyModuleId ?: 0
        val name = inputName.orEmpty().lowercase()
        fun hasFiles(path: String): Boolean = File(workDir, path).let { dir ->
            dir.isDirectory && !dir.list().isNullOrEmpty()
        }
        fun choose(vararg ids: String): SubTool =
            ids.firstNotNullOfOrNull { byId[it] } ?: actions.first()

        // A format detector can nominate an implementation only inside this
        // submenu. Cross-menu suggestions are deliberately ignored.
        val detected = detection?.suggestedSubtool?.let { byId[it] }
        val selected = when (provider) {
            1 -> choose("pak_full_unpack")
            2 -> when {
                name.contains(".encrypt.") -> choose("pak_encrypt")
                name.contains("simple1") || name.endsWith(".enc.pak") -> choose("pak_decrypt_restore")
                else -> choose("pak_repack_full")
            }
            3 -> if (name.contains(".empty.")) choose("pak_delete_all") else choose("pak_delete_entry")
            4 -> choose("obb_unzip")
            5 -> when {
                name.contains(".constants.") -> choose("lua_constants")
                name.contains(".clean.") -> choose("lua_clean_source")
                name.contains(".multixor.") -> choose("lua_multi_xor")
                name.contains(".xor.") -> choose("lua_xor_crypt")
                name.contains("bgmi") || name.contains("pubg") -> choose("pubg_lua_convert")
                name.contains("t24") -> choose("t24_lua_decompile")
                detection?.suggestedSubtool == "lua_vm_deobfuscate" -> choose("lua_vm_deobfuscate")
                detection?.suggestedSubtool == "lua_format_probe" -> choose("lua_format_probe")
                detected != null -> detected
                detection?.type == FileMagic.FileType.PLAIN_TEXT || name.endsWith(".lua") ->
                    choose("lua_analyze", "lua_decompile")
                else -> choose("lua_decompile")
            }
            6 -> if (name.contains("global-metadata")) choose("metadata_v39_decode")
                 else choose("string_scan")
            7 -> choose("clear_work")
            8 -> choose("export_report")
            9 -> if (name.contains(".manual.")) choose("rebrand_manual") else if (name.contains(".scan.")) choose("rebrand_scan") else choose("rebrand_auto")
            10 -> when {
                name.contains(".patchurl.") -> choose("so_patch_url")
                name.contains(".multixor.") -> choose("so_multi_xor")
                name.contains(".sm4scan.") -> choose("sm4_find_all")
                name.endsWith(".dmp") -> choose("so_dump_audit")
                else -> detected ?: choose("so_xor_scan")
            }
            11 -> when {
                name.endsWith(".so") -> choose("frida_jni_hook")
                else -> choose("frida_spawn", "frida_js_dump", "frida_jni_hook")
            }
            12 -> when {
                name.contains(".xor.custom") -> choose("xor_custom_key")
                hasFiles("BATCH") -> choose("xor_batch")
                name.endsWith(".luas") -> choose("xor_luas_strip")
                else -> choose("xor_single_byte")
            }
            13 -> when {
                name.contains(".aes.cbc") -> choose("dec_aes_cbc")
                name.contains(".aes.ecb") -> choose("dec_aes_ecb")
                name.contains(".zuc.enc") -> choose("dec_zuc")
                name.contains(".sm4.enc") -> choose("dec_sm4")
                name.contains(".simple1.enc") -> choose("dec_simple1")
                else -> choose("dec_auto")
            }
            14 -> when {
                name.endsWith(".so") -> choose("sm4_keyfind")
                name.contains(".aes.") -> choose("pak_deep_aes")
                name.contains(".zuc.") -> choose("pak_deep_zuc")
                name.contains(".sm4.") -> choose("pak_deep_sm4")
                name.contains("integrity") -> choose("pak_deep_integrity_audit")
                else -> choose("pak_deep_auto")
            }
            15 -> when {
                name.contains(".constants.") -> choose("str_constant_pool")
                name.contains(".xref.") -> choose("str_xref")
                else -> choose("str_recover")
            }
            16 -> when {
                name.contains(".hook.") -> choose("lua_inject_hook")
                hasFiles("MOD") -> choose("lua_mod_repack")
                else -> choose("lua_patch_byte")
            }
            17 -> when {
                name.endsWith(".apk") -> choose("audit_apk")
                name.endsWith(".so") -> choose("audit_so")
                name.endsWith(".lua") || name.endsWith(".luac") -> choose("audit_lua")
                else -> choose("anti_re_source_triage", "audit_apk")
            }
            18 -> when {
                detection?.type == FileMagic.FileType.ALVLUA1_PROTECTED || name.endsWith(".alvlua") ->
                    choose("lua_protect_decrypt")
                name.contains(".encrypt.") -> choose("lua_protect_encrypt")
                name.endsWith(".strong.lua") -> choose("lua_smart_protect_strong")
                name.endsWith(".vm.lua") -> choose("lua_vm_protect")
                else -> choose("lua_smart_protect")
            }
            19 -> when {
                name.contains(".zuc.enc") -> choose("priv_zuc_decrypt")
                name.contains(".compress.") -> choose("priv_compress_fit")
                name.contains("heping") -> choose("priv_lua_heping")
                name.contains("bgmi") -> choose("priv_lua_convert")
                name.contains(".manifest.apk") -> choose("priv_apk_manifest")
                name.contains(".strings.") -> choose("priv_str_recover")
                name.contains(".xor.") -> choose("priv_xor_recover")
                name.endsWith(".apk") -> choose("priv_apk_audit")
                name.endsWith(".pak") -> choose("priv_pak_manifest")
                name.endsWith(".luac") -> choose("priv_lua_parse")
                name.endsWith(".so") -> choose("priv_aes_scan")
                name.endsWith(".bin") -> choose("priv_xor_recover")
                else -> choose("priv_entropy_map")
            }
            20 -> choose("asset_smart")
            else -> detected ?: actions.first()
        }
        return selected
    }
    /**
     * Build a short, safe pipeline for the selected Smart submenu.
     * Mutating alternatives remain singular; only compatible diagnostics and
     * built-in self-tests are chained automatically.
     */
    fun plan(submenu: SubTool, primary: SubTool, workDir: File): List<SubTool> {
        val actions = submenu.actions.associateBy { it.id }
        fun get(vararg ids: String): List<SubTool> = ids.mapNotNull { actions[it] }
        val provider = submenu.legacyModuleId ?: primary.legacyModuleId ?: 0
        val stages = when (provider) {
            // Full PAK unpack already owns its extraction/index validation pipeline.
            1, 2, 3, 5, 7, 8, 9, 16, 17, 18, 19 -> listOf(primary)
            4 -> if (primary.id == "obb_unzip")
                get("obb_info", "obb_integrity_audit", "obb_unzip") else listOf(primary)
            6 -> if (primary.id == "string_scan")
                get("string_scan", "hash_scan") else listOf(primary)
            10 -> if (primary.id == "so_xor_scan")
                get("so_xor_scan", "so_url_dump", "so_aes_probe") else listOf(primary)
            11 -> if (primary.id == "frida_spawn")
                get("frida_js_dump", "frida_spawn") else listOf(primary)
            12 -> if (primary.id == "xor_selftest") listOf(primary)
                else get("xor_selftest") + listOf(primary)
            13 -> if (primary.id == "dec_selftest") listOf(primary)
                else get("dec_selftest") + listOf(primary)
            14 -> if (primary.id == "pak_deep_auto")
                get("pak_deep_integrity_audit", "pak_deep_auto") else listOf(primary)
            15 -> when (primary.id) {
                "str_xref" -> get("str_recover", "str_xref")
                "str_constant_pool" -> listOf(primary)
                else -> listOf(primary)
            }
            else -> listOf(primary)
        }
        return stages.distinctBy { it.id }.ifEmpty { listOf(primary) }
    }

}
