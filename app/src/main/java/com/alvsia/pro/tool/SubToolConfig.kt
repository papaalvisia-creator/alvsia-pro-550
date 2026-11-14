package com.alvsia.pro.tool

/**
 * ALVISIA PRO 5.5.2 — SubToolConfig (UX Sprint 1)
 *
 * Inline config schema for subtools that previously required manual
 * WORK config-file creation. The ToolWorkspace renders an inline form
 * from this schema, and on RUN writes the config file transparently
 * before invoking the bridge.
 *
 * This eliminates the biggest UX friction point: users no longer need
 * to open a file manager to create xor_key.txt, aes_config.txt, etc.
 */
data class SubToolConfig(
    val field: String,           // logical field name (e.g. "key_hex")
    val label: String,           // UI label (e.g. "Key (hex)")
    val type: ConfigType,        // TEXT, HEX, MULTILINE, FILE_PICK, INT, BOOL
    val hint: String = "",       // placeholder/help text
    val default: String? = null, // default value
    val required: Boolean = true,
    val workFileName: String? = null  // if set, value written to WORK config files
)

enum class ConfigType {
    TEXT,        // free text input
    HEX,         // hexadecimal input (validates 0-9a-fA-F)
    MULTILINE,   // multiline text (for Lua source, etc.)
    FILE_PICK,   // file picker button
    PATH,        // filesystem path input (file or directory)
    INT,         // integer input
    BOOL          // toggle switch
}

/**
 * Returns the config schema for a subtool, or empty list if no inline
 * config is needed (the subtool works without config files).
 *
 * Each entry maps to a field that the ToolWorkspace renders as an
 * inline form. On RUN, the app writes each field's value to
 * WORK config files transparently before calling the bridge.
 */
fun subToolConfig(subId: String): List<SubToolConfig> = when (subId) {
    // Module 12 — XOR Suite
    "xor_custom_key" -> listOf(
        SubToolConfig(
            field = "key_hex",
            label = "XOR Key (hex)",
            type = ConfigType.HEX,
            hint = "e.g. DEADBEEF00112233",
            workFileName = "xor_key.txt"
        )
    )
    "xor_batch" -> listOf(
        SubToolConfig(
            field = "key_hex",
            label = "XOR Key (hex)",
            type = ConfigType.HEX,
            hint = "Applied to all files in WORK/BATCH/",
            workFileName = "xor_key.txt"
        )
    )

    // Module 10 — SO Analyzer
    "so_multi_xor" -> listOf(
        SubToolConfig(
            field = "keys",
            label = "XOR Keys (one per line, hex)",
            type = ConfigType.MULTILINE,
            hint = "e.g. DEADBEEF\n00112233",
            workFileName = "xor_keys.txt"
        )
    )
    "so_patch_url" -> listOf(
        SubToolConfig(
            field = "patch_config",
            label = "Patch Config",
            type = ConfigType.MULTILINE,
            hint = "old_url=https://old.example\nnew_url=https://new.example",
            workFileName = "patch_config.txt"
        )
    )

    // Module 11 — Frida Tracer
    "frida_js_dump", "frida_spawn" -> listOf(
        SubToolConfig(
            field = "target_pkg",
            label = "Target Package Name",
            type = ConfigType.TEXT,
            hint = "e.g. com.tencent.ig",
            workFileName = "frida_target.txt"
        )
    )

    // Module 13 — Decrypt Engine
    "dec_auto" -> listOf(
        SubToolConfig(
            field = "aes_config",
            label = "AES Candidate Config (optional)",
            type = ConfigType.MULTILINE,
            hint = "key=<hex32|48|64>\niv=<hex32> (IV enables CBC)",
            required = false,
            workFileName = "aes_config.txt"
        ),
        SubToolConfig(
            field = "zuc_config",
            label = "ZUC-like Candidate Config (optional)",
            type = ConfigType.MULTILINE,
            hint = "key=<hex>\niv=<hex>",
            required = false,
            workFileName = "zuc_config.txt"
        ),
        SubToolConfig(
            field = "sm4_config",
            label = "SM4 Candidate Config (optional)",
            type = ConfigType.MULTILINE,
            hint = "key=<32 hex chars>\nmode=ECB|CBC\niv=<32 hex chars>",
            required = false,
            workFileName = "sm4_config.txt"
        )
    )
    "dec_aes_cbc", "dec_aes_ecb" -> listOf(
        SubToolConfig(
            field = "aes_config",
            label = "AES Config",
            type = ConfigType.MULTILINE,
            hint = "key=<hex32>\niv=<hex32> (CBC requires IV)",
            workFileName = "aes_config.txt"
        )
    )
    "dec_zuc" -> listOf(
        SubToolConfig(
            field = "zuc_config",
            label = "ZUC Config",
            type = ConfigType.MULTILINE,
            hint = "key=<hex32>\niv=<hex16>",
            workFileName = "zuc_config.txt"
        )
    )
    "dec_sm4" -> listOf(
        SubToolConfig(
            field = "sm4_config",
            label = "SM4 Config",
            type = ConfigType.MULTILINE,
            hint = "key=<hex32>\nmode=CBC|ECB\niv=<hex16>",
            workFileName = "sm4_config.txt"
        )
    )

    // Module 14 — PAK Deep
    "pak_deep_aes" -> listOf(
        SubToolConfig(
            field = "passphrase",
            label = "PAK AES-SHA1 Config",
            type = ConfigType.MULTILINE,
            hint = "passphrase=<text>\niv=<hex32> (or key=<hex32>\niv=<hex32>)",
            workFileName = "pak_pass.txt"
        )
    )
    "pak_deep_zuc" -> listOf(
        SubToolConfig(
            field = "zuc_config",
            label = "ZUC Config",
            type = ConfigType.MULTILINE,
            hint = "key=<hex32>\niv=<hex16>",
            workFileName = "zuc_config.txt"
        )
    )
    "pak_deep_sm4" -> listOf(
        SubToolConfig(
            field = "sm4_config",
            label = "SM4 Config",
            type = ConfigType.MULTILINE,
            hint = "key=<hex32>\nmode=CBC|ECB\niv=<hex16>",
            workFileName = "sm4_config.txt"
        )
    )

    // Module 15 — String Recover
    "str_xref" -> listOf(
        SubToolConfig(
            field = "search",
            label = "String to Find",
            type = ConfigType.TEXT,
            hint = "search=<literal text>",
            workFileName = "xref_query.txt"
        )
    )

    // Module 16 — Lua Inject
    "lua_patch_byte" -> listOf(
        SubToolConfig(
            field = "patch_json",
            label = "Patch JSON",
            type = ConfigType.MULTILINE,
            hint = "offset=0x1234\npatch_hex=DEADBEEF",
            workFileName = "lua_patch.json"
        )
    )
    "lua_inject_hook" -> listOf(
        SubToolConfig(
            field = "hook_code",
            label = "Hook Lua Source",
            type = ConfigType.MULTILINE,
            hint = "Lua function to inject",
            workFileName = "lua_hook.lua"
        )
    )

    // Module 3 — PAK Compact
    "pak_delete_entry" -> listOf(
        SubToolConfig(
            field = "targets",
            label = "Paths to Delete (one per line)",
            type = ConfigType.MULTILINE,
            hint = "Internal PAK paths to remove",
            workFileName = "delete_targets.txt"
        )
    )

    // Module 9 — Rebrand
    "rebrand_manual" -> listOf(
        SubToolConfig(
            field = "rebrand_config",
            label = "Rebrand Config",
            type = ConfigType.MULTILINE,
            hint = "brand=ALVSIA PRO\nchannel=t.me/ALVSIA_PRO\nwatermark=...",
            workFileName = "rebrand_config.txt"
        )
    )

    // Module 18 — Lua Protector
    "lua_protect_encrypt", "lua_protect_decrypt" -> listOf(
        SubToolConfig(
            field = "key_hex",
            label = "Lua Protector Key (64 hex chars)",
            type = ConfigType.HEX,
            hint = "32-byte AES-256-GCM key as 64 hex chars",
            workFileName = "lua_protect_key.txt"
        )
    )


    // URL Scanner — input: .so file or folder
    "url_scan_so" -> listOf(
        SubToolConfig(
            field = "so_path",
            label = "Path to .so file or folder containing .so files",
            type = ConfigType.PATH,
            hint = "/sdcard/AlvsiaWork/lib/arm64-v8a",
            required = true,
            workFileName = "so_path.txt"
        )
    )

    // SM4 All-Type Key Finder — input: folder of .so files
    "sm4_find_all" -> listOf(
        SubToolConfig(
            field = "so_folder",
            label = "Folder containing .so files",
            type = ConfigType.PATH,
            hint = "/sdcard/AlvsiaWork/extracted_apk/lib/arm64-v8a",
            required = true,
            workFileName = "so_folder.txt"
        )
    )

    // PUBG/BGMI Lua Converter — input: .luac file or folder
    "pubg_lua_convert" -> listOf(
        SubToolConfig(
            field = "input_path",
            label = "Path to .luac file or folder of .luac files",
            type = ConfigType.PATH,
            hint = "/sdcard/AlvsiaWork/extracted_lua",
            required = true,
            workFileName = "lua_input.txt"
        )
    )

    // ALVISIA PRIVATE TOOL configs
    "priv_zuc_decrypt" -> listOf(
        SubToolConfig(field = "key", label = "ZUC Key (32 hex chars = 16 bytes)",
            type = ConfigType.HEX, hint = "0000000000000000ffffffffffffffff",
            required = true, workFileName = "zuc_config.txt"),
        SubToolConfig(field = "iv", label = "ZUC IV (32 hex chars = 16 bytes)",
            type = ConfigType.HEX, hint = "00000000000000000000000000000001",
            required = true, workFileName = "zuc_config.txt")
    )
    "priv_compress_fit" -> listOf(
        SubToolConfig(field = "method", label = "Method (zlib / zstd)",
            type = ConfigType.TEXT, hint = "zlib",
            required = false, workFileName = "compress_config.txt"),
        SubToolConfig(field = "target_size", label = "Target compressed size (bytes, 0 = no limit)",
            type = ConfigType.TEXT, hint = "4096",
            required = false, workFileName = "compress_config.txt")
    )

    // SM4 Key Finder — input: folder containing extracted .so files (or a .so path)
    "sm4_keyfind" -> listOf(
        SubToolConfig(
            field = "so_folder",
            label = "Folder containing .so files (or path to single .so)",
            type = ConfigType.PATH,
            hint = "/sdcard/AlvsiaWork/extracted_apk/lib/arm64-v8a",
            required = true,
            workFileName = "so_folder.txt"
        )
    )

    // Smart Asset Engine — optional user-supplied equal-length hex mappings.
    "asset_smart" -> listOf(
        SubToolConfig(
            field = "asset_patch_map",
            label = "Optional Asset Mapping (old_hex=new_hex, one per line)",
            type = ConfigType.MULTILINE,
            hint = "DEADBEEF=01020304",
            required = false,
            workFileName = "asset_patch_map.txt"
        )
    )

    // All other subtools — no inline config needed
    else -> emptyList()
}
