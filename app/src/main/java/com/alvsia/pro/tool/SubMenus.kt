package com.alvsia.pro.tool

data class SubTool(
    val id: String,
    val title: String,
    val desc: String,
    val guide: String,
    val needsFile: Boolean = true
)

/**
 * ALVSIA SMART PREMIUM 6.0.0 — compact public catalog.
 *
 * Public navigation is intentionally fixed at 7 menus / 22 sub-tools.
 * Legacy providers remain internal behind SmartModuleRouter and the
 * authenticated Python bridge.
 */
object SubMenus {
    fun title(moduleId: Int): String = when (moduleId) {
        1 -> "SMART LUA"
        2 -> "SMART PAK"
        3 -> "SMART OBB"
        4 -> "SMART DATA"
        5 -> "SMART ANALYSIS"
        6 -> "WORKSPACE & REPORT"
        7 -> "ALVSIA PRIVATE"
        else -> "Module $moduleId"
    }

    fun forModule(moduleId: Int): List<SubTool> = when (moduleId) {
        1 -> listOf(
            SubTool("lua_decompile", "SMART LUA DECOMPILER", "Detect → route → recovery → validated pure Lua source", "Select Lua/LuaJIT/PUBG/BGMI/T24/VM input. Only a validated non-empty .lua artifact is accepted."),
            SubTool("lua_smart_protect", "SMART LUA PROTECT", "Protect → strong/VM/encrypt → validate", "Select Lua source. The engine selects the internal protection profile and validates the result."),
            SubTool("lua_compile", "SMART LUA COMPILER / RECOMPILER", "Source ↔ bytecode with dialect detection and round-trip validation", "Select Lua source or compatible bytecode. Compiler/provider selection is automatic."),
            SubTool("lua_patch_byte", "SMART LUA INJECT", "Detect → patch/hook/mod integration → integrity validation", "Select Lua/bytecode/PAK input and use the task configuration for the requested patch or repack.")
        )
        2 -> listOf(
            SubTool("pak_smart_inspect", "SMART PAK INSPECT", "Auto-detect version, index, encryption, compression and integrity", "Select .pak. Inspection is read-only and chooses the compatible internal provider."),
            SubTool("pak_full_unpack", "SMART PAK UNPACK", "Decrypt → extract → verify", "Select .pak. Output is accepted only after extraction verification."),
            SubTool("pak_repack_full", "SMART PAK MODIFY / REPACK", "Apply edited tree → rebuild → verify", "Select the original .pak and use the existing WORK/MOD or staged edit tree."),
            SubTool("pak_deep_auto", "SMART PAK AUTO RECOVERY", "Deep encryption/compression probing including SM4_NEW", "Select .pak. Candidate transforms are validated before an output is accepted.")
        )
        3 -> listOf(
            SubTool("obb_smart_inspect", "SMART OBB INSPECT", "Auto-detect ZIP/OBB structure and integrity", "Select .obb/.zip. Inspection is read-only and reports CRC/path/duplicate/symlink findings."),
            SubTool("obb_unzip", "SMART OBB EXTRACT", "Safe bounded extraction with traversal/symlink/duplicate checks", "Select .obb/.zip. Extraction is bounded and path-safe."),
            SubTool("obb_rezip", "SMART OBB REBUILD", "Rebuild edited tree into OBB/ZIP with validation", "Select the edited source tree or staged archive.")
        )
        4 -> listOf(
            SubTool("data_auto_recover", "SMART DATA RECOVERY", "Auto-detect XOR/AES/SM4/SIMPLE1 and validate candidates", "Select binary/data input. Only candidates passing structural validation are promoted."),
            SubTool("sm4_find_all", "SMART SM4 / XOR", "SM4_NEW candidate set plus single/multi-key XOR probing", "Select authorized binary material. Existing source-backed candidate material is used; no keys are invented."),
            SubTool("str_recover", "SMART STRING / METADATA RECOVERY", "Strings, constants and validated metadata recovery", "Select Lua/binary/global-metadata input. Recovery is bounded and reports its evidence.")
        )
        5 -> listOf(
            SubTool("so_url_dump", "SMART SO / URL ANALYZE", "Native strings, URLs, entropy and crypto-pattern analysis", "Select .so/.bin/.apk/.obb for static analysis only."),
            SubTool("frida_jni_hook", "SMART JNI TRACE", "Generate bounded review scripts without live process execution", "Select target .so. The tool generates review artifacts; it does not execute a live hook."),
            SubTool("audit_apk", "SMART APK / LUA AUDIT", "Structural APK, native and Lua anti-RE posture audit", "Select .apk/.lua/.luac. The audit is read-only.")
        )
        6 -> listOf(
            SubTool("clear_work", "CLEAR WORKSPACE", "Clear the task workspace", "No input required.", needsFile = false),
            SubTool("export_report", "EXPORT REPORT / HASH", "File/session summary with MD5, SHA-1 and SHA-256 integrity", "Select a file. The report records size, hashes and engine evidence.")
        )
        7 -> listOf(
            SubTool("priv_lua_parse", "PRIVATE LUA PARSER", "Private bytecode analysis provider", "Select authorized .luac."),
            SubTool("priv_lua_convert", "PRIVATE LUA CONVERT", "BGMI/HePing conversion provider", "Select authorized .luac or conversion workspace."),
            SubTool("priv_pak_manifest", "PRIVATE PAK MANIFEST", "PAK entry manifest and provider-level inspection", "Select authorized .pak.")
        )
        else -> emptyList()
    }
}
