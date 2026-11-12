package com.alvsia.pro.tool

data class SubTool(
    val id: String,
    val title: String,
    val desc: String,
    val guide: String,
    val needsFile: Boolean = true
)

/**
 * ALVSIA PRO Smart Tool Catalog.
 *
 * The visible UI is intentionally small. Legacy engines remain available only
 * as internal providers selected by SmartModuleRouter/bridge adapters.
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
            SubTool("lua_decompile", "SMART LUA DECOMPILER", "Detect → normalize → recover → validate Lua/LuaJIT/protected layers", "Select Lua/bytecode/container. One pipeline automatically selects compatible engines and validates the final source."),
            SubTool("lua_analyze", "SMART LUA ANALYZE", "Format, VM/protection, constants, strings and XOR diagnostics", "Select Lua/bytecode. Analysis is automatic and feeds the decompiler recovery pipeline."),
            SubTool("lua_smart_protect", "SMART LUA PROTECT", "Balanced protection with syntax + differential validation", "Select Lua source. The unified protection pipeline validates before publishing output."),
            SubTool("lua_smart_protect_strong", "SMART LUA PROTECT · STRONG", "Strong protection profile with validation", "Select Lua source. Strong mode is still handled by the same Smart Lua protection mechanism."),
            SubTool("lua_compile", "SMART LUA COMPILE / RECOMPILE", "Compile validated Lua source back to bytecode", "Select Lua source. The engine detects the target version and uses an available compatible compiler; no fake bytecode is produced."),
            SubTool("lua_protect_encrypt", "SMART LUA PROTECT · ENCRYPT / RESTORE", "Authenticated ALVLUA package encryption and restore", "Select Lua or ALVLUA and provide the existing protection key configuration."),
            SubTool("lua_vm_protect", "SMART LUA PROTECT · VM", "VM-style protected Lua wrapper", "Select Lua source. Uses the existing validated VM provider behind the single Smart Lua mechanism."),
            SubTool("lua_patch_byte", "SMART LUA INJECT", "Validated byte patch, hook injection and repack path", "Select Lua/PAK input and provide the existing injection configuration. Injection remains one Smart Lua operation family.")
        )
        2 -> listOf(
            SubTool("pak_smart_inspect", "SMART PAK INSPECT", "Auto-detect PAK version, index, encryption, compression and integrity", "Select .pak. The engine inspects first and chooses the compatible provider."),
            SubTool("pak_full_unpack", "SMART PAK UNPACK", "Decrypt → extract → verify", "Select .pak. Output is written only after integrity checks pass."),
            SubTool("pak_repack_full", "SMART PAK MODIFY / REPACK", "Apply edited tree → rebuild → verify", "Select original .pak and use the existing WORK/MOD or staged edit tree."),
            SubTool("pak_deep_auto", "SMART PAK AUTO RECOVERY", "Deep encryption/compression probing including SM4_NEW", "Select .pak. Candidate transforms are validated before an output is accepted."),
            SubTool("pak_deep_integrity_audit", "SMART PAK INTEGRITY", "Read-only slot, overlap, duplicate and SHA-256 audit", "Select .pak. Source is never modified.")
        )
        3 -> listOf(
            SubTool("obb_smart_inspect", "SMART OBB INSPECT", "Auto-detect ZIP/OBB structure and integrity", "Select .obb/.zip."),
            SubTool("obb_unzip", "SMART OBB EXTRACT", "Safe bounded extraction with traversal/symlink/duplicate checks", "Select .obb/.zip."),
            SubTool("obb_rezip", "SMART OBB REBUILD", "Rebuild edited tree into OBB/ZIP", "Select the edited source tree or staged archive."),
            SubTool("obb_integrity_audit", "SMART OBB INTEGRITY", "CRC, path, duplicate, symlink and size-limit audit", "Select .obb/.zip. Source is never modified.")
        )
        4 -> listOf(
            SubTool("data_auto_recover", "SMART DATA RECOVERY", "Auto-detect XOR/AES/SM4/SIMPLE1 and validate candidates", "Select binary/data input and provide only the configuration required by a candidate transform."),
            SubTool("sm4_find_all", "SMART SM4 NEW", "SM4_SECRET_NEW + legacy SM4 secret detection", "Select authorized .so/.bin material. Uses the SM4_NEW candidate set already present in the source; missing candidates are never invented."),
            SubTool("xor_single_byte", "SMART XOR", "Single/multi-key XOR probing and recovery", "Select binary input."),
            SubTool("str_recover", "SMART STRING RECOVERY", "Strings + constants + bounded recovery", "Select Lua/binary input."),
            SubTool("metadata_v39_decode", "SMART METADATA", "Validated IL2CPP metadata v39 decode", "Select authorized global-metadata.dat.")
        )
        5 -> listOf(
            SubTool("so_url_dump", "SMART SO ANALYZE", "URLs, strings, entropy and crypto-pattern analysis", "Select .so/.bin."),
            SubTool("url_scan_so", "SMART URL SCAN", "URL/IP/host extraction from authorized binaries", "Select .so/.apk/.obb."),
            SubTool("frida_jni_hook", "SMART JNI TRACE", "Generate bounded review scripts; no live process execution", "Select target .so."),
            SubTool("audit_apk", "SMART APK AUDIT", "Structural APK and native coverage audit", "Select .apk."),
            SubTool("audit_lua", "SMART LUA AUDIT", "Static Lua anti-RE/obfuscation audit", "Select .lua/.luac.")
        )
        6 -> listOf(
            SubTool("clear_work", "CLEAR WORKSPACE", "Clear task workspace", "No input required.", needsFile = false),
            SubTool("export_report", "EXPORT REPORT", "File/session summary", "Select a file."),
            SubTool("hash_scan", "HASH / INTEGRITY", "MD5/SHA-1/SHA-256", "Select a file.")
        )
        7 -> listOf(
            SubTool("priv_lua_parse", "PRIVATE LUA PARSER", "Private bytecode analysis provider", "Select .luac."),
            SubTool("priv_lua_convert", "PRIVATE LUA CONVERT", "BGMI/HePing conversion provider", "Select .luac or folder."),
            SubTool("priv_pak_manifest", "PRIVATE PAK MANIFEST", "PAK entry manifest", "Select .pak.")
        )
        else -> emptyList()
    }
}