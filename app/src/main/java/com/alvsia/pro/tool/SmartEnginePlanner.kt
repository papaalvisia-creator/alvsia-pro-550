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
        fun hasConfig(file: String) = File(workDir, file).isFile && File(workDir, file).length() > 0L
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
                hasConfig("pak_encrypt.request") -> choose("pak_encrypt")
                name.contains("simple1") || name.endsWith(".enc.pak") -> choose("pak_decrypt_restore")
                else -> choose("pak_repack_full")
            }
            3 -> choose("pak_delete_entry")
            4 -> choose("obb_unzip")
            5 -> detected ?: if (detection?.type == FileMagic.FileType.PLAIN_TEXT || name.endsWith(".lua"))
                choose("lua_analyze", "lua_decompile") else choose("lua_decompile")
            6 -> if (name.contains("global-metadata")) choose("metadata_v39_decode")
                 else choose("string_scan")
            7 -> choose("clear_work")
            8 -> choose("export_report")
            9 -> if (hasConfig("rebrand_config.txt")) choose("rebrand_manual") else choose("rebrand_auto")
            10 -> when {
                hasConfig("patch_config.txt") -> choose("so_patch_url")
                hasConfig("xor_keys.txt") -> choose("so_multi_xor")
                hasConfig("so_folder.txt") -> choose("sm4_find_all")
                name.endsWith(".dmp") -> choose("so_dump_audit")
                else -> detected ?: choose("so_xor_scan")
            }
            11 -> when {
                name.endsWith(".so") -> choose("frida_jni_hook")
                hasConfig("frida_target.txt") -> choose("frida_spawn")
                else -> choose("frida_js_dump", "frida_jni_hook")
            }
            12 -> when {
                hasConfig("xor_key.txt") -> choose("xor_custom_key")
                hasFiles("BATCH") -> choose("xor_batch")
                name.endsWith(".luas") -> choose("xor_luas_strip")
                else -> choose("xor_single_byte")
            }
            13 -> choose("dec_auto")
            14 -> when {
                name.endsWith(".so") -> choose("sm4_keyfind")
                name.contains("integrity") -> choose("pak_deep_integrity_audit")
                else -> choose("pak_deep_auto")
            }
            15 -> if (hasConfig("xref_query.txt")) choose("str_xref")
                 else choose("str_recover")
            16 -> when {
                hasConfig("lua_patch.json") -> choose("lua_patch_byte")
                hasConfig("lua_hook.lua") -> choose("lua_inject_hook")
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
                hasConfig("lua_protect_key.txt") -> choose("lua_protect_encrypt")
                name.endsWith(".strong.lua") -> choose("lua_smart_protect_strong")
                name.endsWith(".vm.lua") -> choose("lua_vm_protect")
                else -> choose("lua_smart_protect")
            }
            19 -> when {
                hasConfig("zuc_config.txt") -> choose("priv_zuc_decrypt")
                hasConfig("compress_config.txt") -> choose("priv_compress_fit")
                name.contains("heping") -> choose("priv_lua_heping")
                name.contains("bgmi") -> choose("priv_lua_convert")
                name.endsWith(".apk") -> choose("priv_apk_audit")
                name.endsWith(".pak") -> choose("priv_pak_manifest")
                name.endsWith(".luac") -> choose("priv_lua_parse")
                name.endsWith(".so") -> choose("priv_aes_scan")
                name.endsWith(".bin") -> choose("priv_xor_recover")
                else -> choose("priv_entropy_map")
            }
            else -> detected ?: actions.first()
        }
        return selected
    }
}
