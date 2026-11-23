package com.alvsia.pro.tool

data class SubTool(
    val id: String,
    val title: String,
    val desc: String,
    val guide: String,
    val needsFile: Boolean = true
)

/** ALVSIA SMART PREMIUM 6.0.0 — public contract: 9 menus / 33 sub-tools. */
object SubMenus {
    fun title(moduleId: Int): String = when (moduleId) {
        1 -> "HOME"
        2 -> "LUA"
        3 -> "PAK / OBB"
        4 -> "ASSET / UE"
        5 -> "APK / DEX"
        6 -> "NATIVE"
        7 -> "CRYPTO / RECOVERY"
        8 -> "FORENSIC / STRING"
        9 -> "BATCH / DEV LAB"
        else -> "Module $moduleId"
    }

    fun forModule(moduleId: Int): List<SubTool> = when (moduleId) {
        1 -> listOf(
            SubTool("universal_file_detect", "UNIVERSAL FILE DETECT", "Identify file family, signatures, entropy and likely Smart route", "Select any supported artifact. Detection is read-only and evidence-based."),
            SubTool("workspace_report", "WORKSPACE REPORT", "Workspace inventory, hashes and task evidence", "Select a file or workspace artifact to generate a compact report."),
            SubTool("engine_health", "ENGINE HEALTH", "Run provider self-checks and report available Smart backends", "Runs internal provider self-tests; no source file is required.", needsFile = false)
        )
        2 -> listOf(
            SubTool("lua_smart_analyze", "SMART ANALYZE", "Fingerprint Lua/LuaJIT/T24/BGMI layers before transformation", "Select Lua or bytecode. The analyzer chooses the next recovery path."),
            SubTool("lua_recovery_normalize", "RECOVERY / NORMALIZE", "Automatic recovery → normalization → validated pure Lua source", "Select Lua/bytecode input. Only a validated non-empty Lua source artifact is promoted."),
            SubTool("lua_t24_convert", "T24 / BGMI CONVERT", "T24/BGMI/PUBG dialect conversion with structural validation", "Select authorized Lua/bytecode conversion input."),
            SubTool("lua_multi_xor", "MULTI-XOR", "Probe supported XOR layers and validate structural candidates", "Select a binary/Lua candidate. Results are promoted only when validation succeeds."),
            SubTool("lua_protect_transform", "PROTECT / TRANSFORM", "Balanced/strong Lua protection and transform pipeline", "Select Lua source and choose the protection configuration."),
            SubTool("lua_custom_inject", "CUSTOM LUA→PAK INJECT", "Patch/inject Lua into a PAK workflow with integrity checks", "Select the base PAK/Lua input and provide the declared WORK/MOD configuration.")
        )
        3 -> listOf(
            SubTool("pak_info", "PAK INFO", "Inspect PAK version, index, entries, encryption and compression", "Select a Tencent/UE PAK. Inspection is read-only."),
            SubTool("pak_extract", "EXTRACT", "Decrypt/parse/extract PAK contents and verify extraction", "Select a PAK. Extraction is isolated under the task workspace."),
            SubTool("pak_lua_inject", "LUA INJECT", "Inject or repack Lua changes through the validated PAK pipeline", "Select the base PAK and configure the staged modification tree."),
            SubTool("pak_repack", "REPACK MODIFIED TREE", "Rebuild a modified PAK and verify the resulting archive", "Select the base PAK and prepare WORK/MOD or the staged edit tree.")
        )
        4 -> listOf(
            SubTool("asset_uasset_classify", "UASSET CLASSIFY", "Classify UAsset headers, names, exports and imports", "Select a .uasset or related Unreal asset."),
            SubTool("asset_uexp_classify", "UEXP / UBULK CLASSIFY", "Classify UExp/UBulk payloads and linked asset families", "Select .uexp/.ubulk/.uasset material."),
            SubTool("asset_locres_umap_classify", "LOCRES / UMAP CLASSIFY", "Classify localization/map assets and structural metadata", "Select .locres/.umap or related Unreal files."),
            SubTool("asset_report", "ASSET REPORT", "Generate hashes, size, type and structural evidence for assets", "Select an asset or asset workspace.")
        )
        5 -> listOf(
            SubTool("apk_audit", "APK / PACKAGE / SIGNATURE AUDIT", "APK structure, manifest, package identity and signing posture audit", "Select an APK. Audit is read-only; no application code is executed."),
            SubTool("dex_report", "DEX / BYTECODE REPORT", "Static DEX/bytecode metadata and string evidence", "Select an APK/DEX artifact for offline analysis."),
            SubTool("url_scan", "URL / ENDPOINT SCAN & RECOVERY", "Recover and classify URL/endpoint indicators from native/application data", "Select an APK/SO/binary for static scanning and recovery."),
        )
        6 -> listOf(
            SubTool("so_audit", "ELF / SO AUDIT", "Native ELF/SO headers, strings, entropy and dependency indicators", "Select an ELF/SO/native binary."),
            SubTool("native_strings", "NATIVE STRINGS", "Bounded native string extraction and evidence report", "Select an ELF/SO/binary."),
            SubTool("abi_dependency_report", "ABI / DEPENDENCY REPORT", "Native ABI and dependency-oriented inspection", "Select an ELF/SO/native library.")
        )
        7 -> listOf(
            SubTool("aes_scan", "AES CANDIDATE SCAN", "Static AES candidate/configuration discovery", "Select authorized binary material; candidates are reported with evidence."),
            SubTool("zuc_decrypt", "ZUC DECRYPT", "Configured ZUC transform with validation", "Select authorized encrypted material and provide the required configuration."),
            SubTool("string_recovery", "STRING RECOVERY", "Recover strings/constants through the Smart recovery provider", "Select Lua/binary/application data."),
        )
        8 -> listOf(
            SubTool("file_report", "FILE REPORT", "File type, size, hashes and structural evidence", "Select any supported file."),
            SubTool("strings", "STRINGS", "Bounded printable-string extraction", "Select any supported binary or text artifact."),
            SubTool("entropy", "ENTROPY", "Entropy map and high-entropy region report", "Select a binary artifact."),
            SubTool("hex_preview", "HEX PREVIEW", "Bounded hexadecimal preview with offsets and file evidence", "Select a binary artifact.")
        )
        9 -> listOf(
            SubTool("batch_audit", "BATCH AUDIT", "Run repeatable static audit operations over a staged batch", "Prepare a batch/workspace input. The engine keeps task outputs isolated."),
            SubTool("regression_compare", "REGRESSION / COMPARE", "Compare regression outputs and summarize pass/fail evidence", "Select a regression workspace or supported corpus artifact."),
            SubTool("self_test", "SELF TEST", "Run provider self-tests and report failures without modifying inputs", "Runs internal provider self-tests; outputs are diagnostic only.", needsFile = false)
        )
        else -> emptyList()
    }
}
