package com.alvsia.pro.tool

data class SubTool(
    val id: String,
    val title: String,
    val desc: String,
    val guide: String,
    val needsFile: Boolean = true,
    val enabled: Boolean = true,
    val statusNote: String = "Backend adapter sedang diintegrasikan."
)

/**
 * ALVSIA SMART PREMIUM 6.0.0 — 10 menus / 59 unique submenu contract.
 * Items without a verified backend remain visible but disabled; they cannot
 * be dispatched as if they were operational.
 */
object SubMenus {
    fun title(moduleId: Int): String = when (moduleId) {
        1 -> "SMART APK"
        2 -> "SMART PAK"
        3 -> "SMART OBB"
        4 -> "SMART LUA"
        5 -> "SMART CRYPTO"
        6 -> "SMART FORENSICS"
        7 -> "SMART MODDING"
        8 -> "SMART NATIVE"
        9 -> "SMART WORKSPACE"
        10 -> "SMART ENGINE LAB"
        else -> "Module $moduleId"
    }

    fun forModule(moduleId: Int): List<SubTool> = when (moduleId) {
        1 -> listOf(
            SubTool("apk_structure_inspector", "APK STRUCTURE INSPECTOR", "Read-only APK package structure, ZIP entries, DEX presence and native ABI inventory.", "Select an APK. The audit does not execute application code.", enabled = true),
            SubTool("apk_manifest_permission_audit", "MANIFEST & PERMISSION AUDIT", "Extract the binary manifest and report package identity and declared permissions.", "Select an APK. Raw manifest extraction is preserved as an output artifact.", enabled = true),
            SubTool("apk_dex_bytecode_inspector", "DEX / BYTECODE INSPECTOR", "Inspect DEX metadata and bytecode indicators without executing the target application.", "Select an APK or DEX file.", enabled = true),
            SubTool("apk_resource_table_inspector", "RESOURCE TABLE INSPECTOR", "Decode Android resources.arsc tables, resource IDs and linked resource names.", "This dedicated resource-table adapter is not wired yet.", enabled = false),
            SubTool("apk_compare_resource_diff", "APK COMPARE & RESOURCE DIFF", "Compare two APK resource inventories and report added, removed and changed entries.", "Select APK A as input; put the absolute path of APK B in WORK/compare_base.txt.", enabled = true),
            SubTool("apk_signature_integrity_verify", "APK SIGNATURE & INTEGRITY VERIFY", "Audit APK signing blocks, package structure and integrity indicators.", "Select an APK. Signature verification is read-only.", enabled = true)
        )
        2 -> listOf(
            SubTool("pak_profile_fingerprint", "PAK PROFILE & FINGERPRINT", "Identify PAK version, index layout, encryption and compression profile.", "Select a Tencent/UE PAK. Inspection is read-only.", enabled = true),
            SubTool("pak_explorer_info", "PAK EXPLORER / INFO", "List archive entries and export an index report.", "Select a PAK to inspect its entry index.", enabled = true),
            SubTool("pak_extract_unpak", "PAK EXTRACT / UNPAK", "Extract archive contents into an isolated task workspace and verify written files.", "Select a PAK. Original input is never overwritten.", enabled = true),
            SubTool("pak_selective_extract", "PAK SELECTIVE EXTRACT", "Extract selected archive entries or a selected path prefix only.", "List entry names or path prefixes (one per line) in WORK/select_entries.txt, or a single ALL line.", enabled = true),
            SubTool("pak_entry_compare_replace", "PAK ENTRY COMPARE & REPLACE", "Stage replacement files and inject them through the validated PAK workflow.", "Select the base PAK and prepare the declared WORK/MOD replacement tree.", enabled = true),
            SubTool("pak_rebuild_repack", "PAK REBUILD / REPACK", "Rebuild a modified archive and verify its index and output structure.", "Select the base PAK and stage the modification tree.", enabled = true),
            SubTool("pak_compact_rebuild_verify", "PAK COMPACT & REBUILD VERIFY", "Run the PAK integrity/compact rebuild path and report skipped or invalid entries.", "Select a PAK. Keep the original archive unchanged.", enabled = true)
        )
        3 -> listOf(
            SubTool("obb_format_inspector", "OBB FORMAT INSPECTOR", "Inspect ZIP-based OBB structure, entries, sizes and archive integrity.", "Select an OBB or ZIP archive.", enabled = true),
            SubTool("obb_extractor", "OBB EXTRACTOR", "Extract OBB contents with safe path checks into an isolated workspace.", "Select an OBB or ZIP archive.", enabled = true),
            SubTool("mini_obb_zsdic_adapter", "MINI-OBB / OBBZSDIC ADAPTER", "Handle Mini-OBB and OBBZSDIC-specific index and repack formats.", "Scans the container for ZSDIC dictionary entries and writes a structured inventory report.", enabled = true),
            SubTool("gamepatch_obb_repacker", "GAMEPATCH / OBB REPACKER", "Rebuild GamePatch OBB variants while preserving required index and size metadata.", "Repacks the edited OBB tree (WORK/OBB or OUT/OBB/<stem>) preserving base entry order and metadata.", enabled = true),
            SubTool("obb_integrity_pair_validator", "OBB INTEGRITY & PAIR VALIDATOR", "Validate OBB archive structure and report paired-file consistency evidence.", "Select the OBB artifact. Pair-aware multi-file validation is being expanded.", enabled = true)
        )
        4 -> listOf(
            SubTool("lua_smart_analyze", "LUA SMART ANALYZE", "Fingerprint Lua/LuaJIT/T24/BGMI layers before transformation.", "Select Lua or bytecode. Analysis is read-only.", enabled = true),
            SubTool("lua_vm_version_detector", "LUA VM / VERSION DETECTOR", "Detect Lua version, bytecode header, VM family and likely dialect.", "Select a Lua or bytecode file.", enabled = true),
            SubTool("lua_bytecode_inspector", "LUA BYTECODE INSPECTOR", "Parse bytecode metadata, constants, strings, numbers and prototypes.", "Select a supported Lua bytecode file.", enabled = true),
            SubTool("lua_smart_decompile", "LUA SMART DECOMPILE", "Run the unified multi-backend decompiler with structural validation.", "Select Lua bytecode. Failed candidates are not promoted as source.", enabled = true),
            SubTool("lua_recovery_normalize", "LUA RECOVERY & NORMALIZE", "Recover supported wrappers/layers, normalize and validate the recovered Lua source.", "Select Lua or bytecode input.", enabled = true),
            SubTool("lua_t24_bgmi_pubg_converter", "LUA T24 / BGMI / PUBG CONVERTER", "Convert supported T24/BGMI/PUBG Lua dialects with structural checks.", "Select an authorized Lua/bytecode conversion input.", enabled = true),
            SubTool("lua_protect_compile", "LUA PROTECT & COMPILE", "Compose protection and compilation with reproducible validation.", "Protects the Lua source, then compiles it; the compiled artifact is hash-verified.", enabled = true),
            SubTool("lua_custom_inject", "LUA CUSTOM INJECT", "Stage Lua modifications and inject/repack through the validated PAK workflow.", "Select the base PAK and provide the staged Lua modification tree.", enabled = true),
            SubTool("lua_round_trip_validator", "LUA ROUND-TRIP VALIDATOR", "Compile/decompile a fixture and compare structural equivalence.", "Input the original .luac; put the recovered .lua path in WORK/recovered_source.txt.", enabled = true)
        )
        5 -> listOf(
            SubTool("crypto_xor_multi_xor", "XOR / MULTI-XOR ENGINE", "Recover candidate XOR keys and validate candidate plaintext structure.", "Select authorized binary or Lua material.", enabled = true),
            SubTool("crypto_aes_candidate_transform", "AES CANDIDATE & TRANSFORM", "Scan AES indicators and run the configured automatic recovery transform.", "Select authorized encrypted material and supply any required configuration.", enabled = true),
            SubTool("crypto_sm4_engine", "SM4 ENGINE", "Use the existing PAK SM4 engine path and SM4 key-family detection.", "Select a supported PAK or authorized binary input.", enabled = true),
            SubTool("crypto_zuc_engine", "ZUC ENGINE", "Run ZUC-128 decryption with explicit key/IV configuration and validation.", "Enter a 16-byte key and 16-byte IV. No key is guessed.", enabled = true),
            SubTool("crypto_key_pattern_scanner", "KEY / PATTERN SCANNER", "Scan supported binaries for AES and SM4 key-pattern indicators.", "Select an authorized .so, APK, OBB or binary file.", enabled = true),
            SubTool("crypto_output_validator", "CRYPTO OUTPUT VALIDATOR", "Validate decrypted output against format-specific known-answer and structure checks.", "Validates structure (zip/luac/lua/zstd/gzip/elf/dex/png/jpg) and optional sha256 from WORK/expected_hash.txt.", enabled = true)
        )
        6 -> listOf(
            SubTool("forensics_universal_file_detection", "UNIVERSAL FILE DETECTION", "Fingerprint file family, magic, likely format and suggested engine route.", "Select any supported artifact. Detection is read-only.", enabled = true),
            SubTool("forensics_file_signature_hash", "FILE SIGNATURE & HASH INSPECTOR", "Report file signature, size, hashes and structural metadata.", "Select any file.", enabled = true),
            SubTool("forensics_string_url_recovery", "STRING & URL RECOVERY", "Recover strings and URL/endpoint indicators from supported binary inputs.", "Select an APK, SO, Lua or binary artifact.", enabled = true),
            SubTool("forensics_entropy_region", "ENTROPY / REGION ANALYZER", "Map high/low entropy blocks and report offsets for forensic triage.", "Select a binary artifact.", enabled = true),
            SubTool("forensics_hex_structure_viewer", "HEX & STRUCTURE VIEWER", "Generate bounded binary structure and hexadecimal evidence reports.", "Select a binary artifact.", enabled = true),
            SubTool("forensics_evidence_report", "EVIDENCE REPORT GENERATOR", "Generate a compact, reproducible report with hashes and processing evidence.", "Select an artifact to generate a report.", enabled = true)
        )
        7 -> listOf(
            SubTool("modding_uasset_uexp_inspector", "UASSET / UEXP INSPECTOR", "Inspect Unreal UAsset/UEXP headers, names, exports and imports.", "Parses UE package summary, name table, export and import tables into a report.", enabled = true),
            SubTool("modding_ue4_string_id_extractor", "UE4 STRING & ID EXTRACTOR", "Extract UE4 names, identifiers and string references.", "Extracts name-table entries plus ASCII/UTF-16LE string references.", enabled = true),
            SubTool("modding_skin_pair_finder", "SKIN PAIR FINDER", "Discover matching skin/resource pairs and report candidate mappings.", "Pairs .uasset+.uexp siblings and numeric-id sets from a directory or OBB.", enabled = true),
            SubTool("modding_zsdic_analyzer", "ZSDIC ANALYZER", "Inspect ZSDIC dictionaries, indexes and related archive metadata.", "Inspects ZSDIC dictionary magic, dict id, sizes and companion index files.", enabled = true),
            SubTool("modding_offset_size_fixer", "OFFSET / SIZE FIXER", "Recalculate supported offsets and sizes before a validated rebuild.", "Rebuilds the edited tree with consistent offsets, or verifies an archive for offset errors.", enabled = true),
            SubTool("modding_resource_mapping_recovery", "RESOURCE MAPPING & RECOVERY", "Recover resource-to-entry mappings and compare original/modded assets.", "Compares the original archive inventory with the modded tree (WORK/MOD or OUT/MOD).", enabled = true)
        )
        8 -> listOf(
            SubTool("native_elf_so_inspector", "ELF / SO INSPECTOR", "Inspect ELF headers, native strings, sections and binary indicators.", "Select an ELF/SO file or a directory of native libraries.", enabled = true),
            SubTool("native_strings_symbols", "NATIVE STRINGS & SYMBOLS", "Extract bounded printable strings and report native symbol indicators.", "Select an ELF/SO/native binary.", enabled = true),
            SubTool("native_abi_dependency_report", "ABI / DEPENDENCY REPORT", "Report native ABI and dependency indicators from supported ELF files.", "Select an ELF/SO/native library.", enabled = true),
            SubTool("native_xref_reference_analyzer", "XREF & REFERENCE ANALYZER", "Trace supported cross-references and static reference relationships.", "Static ELF/SO and DEX reference analysis: symbol-to-site counts, no execution.", enabled = true),
            SubTool("native_authorized_runtime_trace", "AUTHORIZED RUNTIME TRACE ADAPTER", "Run authorized, user-controlled runtime diagnostics on a permitted target.", "Runtime trace adapter remains gated until its device/consent checks are verified.", enabled = false)
        )
        9 -> listOf(
            SubTool("workspace_file_manager", "FILE WORKSPACE MANAGER", "Manage staged input, work, output and task artifacts.", "Inventory of INPUT/WORK/OUT/TASKS with sizes and hashes; optional cleanup via WORK/cleanup.txt.", enabled = true),
            SubTool("workspace_recent_files_favorites", "RECENT FILES & FAVORITES", "Browse recent input URIs and favorite Smart Engine shortcuts.", "Recent file references and favorite tools are refreshed from the local UX store.", enabled = true),
            SubTool("workspace_batch_job_queue", "BATCH JOB QUEUE", "Review active, completed and failed jobs with per-task progress and logs.", "This view reports current-session tasks; multi-file enqueue is a separate pending capability.", enabled = true),
            SubTool("workspace_resume_cancel_progress", "RESUME / CANCEL / PROGRESS CENTER", "Resume supported jobs, cancel work and inspect live progress.", "Task journal status, resumable WORK trees and cancel requests via WORK/cancel.txt.", enabled = true),
            SubTool("workspace_output_browser_history", "OUTPUT BROWSER & HISTORY", "Browse validated outputs from legacy OUT and task-isolated TASKS output folders.", "Open the output browser to preview, share or continue with another Smart Engine.", enabled = true)
        )
        10 -> listOf(
            SubTool("lab_engine_registry", "ENGINE REGISTRY & CAPABILITY MATRIX", "Show installed providers, format coverage and verified capability status.", "Enumerates providers, registered operations and verified format coverage.", enabled = true),
            SubTool("lab_engine_self_test", "ENGINE SELF-TEST & DIAGNOSTICS", "Run internal provider self-tests and report available engine health.", "No file required. Self-test is diagnostic and does not modify inputs.", needsFile = false, enabled = true),
            SubTool("lab_regression_diff_compare", "REGRESSION / DIFFERENTIAL COMPARE", "Compare reference and candidate outputs and report structural differences.", "Input the candidate; put the reference path in WORK/regression_base.txt.", enabled = true),
            SubTool("lab_large_file_benchmark", "LARGE-FILE BENCHMARK & VALIDATION", "Measure streaming throughput, memory bounds and output integrity.", "Streams the input (hash + copy + verify) and reports throughput and peak RSS.", enabled = true)
        )
        else -> emptyList()
    }
}