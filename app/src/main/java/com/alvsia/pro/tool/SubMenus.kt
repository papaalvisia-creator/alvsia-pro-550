package com.alvsia.pro.tool

data class SubTool(
    val id: String,
    val title: String,
    val desc: String,
    val guide: String,
    val needsFile: Boolean = true
)

object SubMenus {
    fun title(moduleId: Int): String = when (moduleId) {
        1  -> "PAK Unpack"
        2  -> "PAK Rebuild"
        3  -> "PAK Compact"
        4  -> "OBB Tools"
        5  -> "SMART LUA"
        6  -> "File Scan"
        7  -> "Workspace"
        8  -> "Export Report"
        9  -> "Rebrand"
        10 -> "SO Analyzer"
        11 -> "Frida Tracer"
        12 -> "XOR Suite"
        13 -> "Decrypt Engine"
        14 -> "PAK Deep"
        15 -> "String Recover"
        16 -> "Lua Inject"
        17 -> "Anti-RE Audit"
        18 -> "Lua Protector"
        19 -> "ALVSIA PRIVATE TOOL"
        else -> "Module $moduleId"
    }

    fun forModule(moduleId: Int): List<SubTool> = when (moduleId) {

        // ── 1 PAK Unpack ─────────────────────────────────────────────────
        1 -> listOf(
            SubTool("pak_full_unpack",   "Full Unpack",   "Decrypt + extract tree",
                "Select .pak → OUT/PAK/<n>/"),
            SubTool("pak_list",          "List Index",    "All entry paths",
                "Select .pak → index list under OUT/PAK/"),
            SubTool("pak_info",          "Quick Info",    "Header · size · hash",
                "Select .pak → OUT/PAK/info.txt"),
            SubTool("pak_csv",           "Dump CSV",      "Export index CSV",
                "Select .pak → OUT/PAK/index.csv"),
        )

        // ── 2 PAK Rebuild ─────────────────────────────────────────────────
        2 -> listOf(
            SubTool("pak_repack_full",        "Smart Repack",    "Inject edited tree",
                "Edit OUT/PAK/<stem>/ then select original .pak"),
            SubTool("pak_inject",             "Inject Files",    "Merge WORK/MOD",
                "Put files in WORK/MOD matching internal paths"),
            SubTool("pak_encrypt",            "Encrypt PAK",     "SIMPLE1 whole-file lock",
                "Select .pak → *_enc.pak"),
            SubTool("pak_decrypt_restore",    "Decrypt Restore", "SIMPLE1 unlock",
                "Select locked .pak → *_dec.pak"),
        )

        // ── 3 PAK Compact ─────────────────────────────────────────────────
        3 -> listOf(
            SubTool("pak_delete_entry", "Delete + Compact", "Remove paths",
                "Write paths to WORK/delete_targets.txt then select .pak"),
            SubTool("pak_delete_all",   "Empty Compact",    "Strip all entries",
                "Select .pak → valid empty compact"),
        )

        // ── 4 OBB Tools ───────────────────────────────────────────────────
        4 -> listOf(
            SubTool("obb_unzip", "Unzip OBB", "Extract zip/obb",
                "Select .obb/.zip → OUT/OBB/<n>/"),
            SubTool("obb_rezip", "Rezip OBB", "Folder to .obb",
                "Select unpacked folder / original .obb stem tree"),
            SubTool("obb_info",  "OBB Info",  "Size listing",
                "Select .obb/.zip"),
            SubTool("obb_integrity_audit", "OBB Integrity Audit", "Read-only ZIP/OBB CRC, path traversal, symlink, duplicate-entry and size-limit checks",
                "Select .obb/.zip → OUT/OBB/*.integrity_audit.json; archive is never extracted or modified"),
        )

        // ── 5 SMART LUA — exactly four public engines ───────────────────────
        5 -> listOf(
            SubTool(
                "smart_lua_decompiler",
                "SMART LUA DECOMPILER",
                "Detect → route → Universal IR → adapters → recovery → semantic validation",
                "Select Lua/LuaJIT/PUBG/BGMI/T24/VM-obfuscated input. The engine chooses the internal route automatically."
            ),
            SubTool(
                "smart_lua_protect",
                "SMART LUA PROTECT",
                "Detect → route → IR → protection → strong/VM → validation",
                "Select Lua source. Protection strategy is selected internally and validated before output."
            ),
            SubTool(
                "smart_lua_compile",
                "SMART LUA COMPILER / RECOMPILER",
                "Source → bytecode or bytecode → source → bytecode with round-trip validation",
                "Select Lua source or compatible bytecode. Compiler dialect is detected and validated automatically."
            ),
            SubTool(
                "smart_lua_inject",
                "SMART LUA INJECT",
                "Detect → route → IR → patch/hook/repack → integrity validation",
                "Select Lua/bytecode. Configure injection strategy internally through WORK/lua_inject_config.txt."
            ),
        )

        // ── 6 File Scan ───────────────────────────────────────────────────
        6 -> listOf(
            SubTool("string_scan", "String Scanner", "ASCII strings",
                "Select any file → OUT/SCAN/strings.txt"),
            SubTool("hash_scan",   "Hash File",      "MD5 SHA1 SHA256",
                "Select file → OUT/SCAN/hash.txt"),
            SubTool("metadata_v39_decode", "IL2CPP Metadata v39 Decoder", "Decode and validate the offline global-metadata.dat v39 header",
                "Select authorized global-metadata.dat v39 → OUT/SCAN/*_metadata_decoded.dat + JSON report"),
        )

        // ── 7 Workspace ───────────────────────────────────────────────────
        7 -> listOf(
            SubTool("clear_work", "Clear Workspace", "Wipe WORK + OUT",
                "No file needed", needsFile = false),
        )

        // ── 8 Export Report ───────────────────────────────────────────────
        8 -> listOf(
            SubTool("export_report", "File Report", "Info summary",
                "Select .pak or any file"),
        )

        // ── 9 Rebrand ─────────────────────────────────────────────────────
        9 -> listOf(
            SubTool("rebrand_auto",   "Auto ALVSIA PRO",   "Replace known brands",
                "Select .lua / unpacked folder / text. brand=ALVSIA PRO channel=t.me/ALVSIA_PRO"),
            SubTool("rebrand_manual", "Manual Rebrand",    "Use WORK/rebrand_config.txt",
                "Edit WORK/rebrand_config.txt (brand= channel= watermark=) then select file/folder"),
            SubTool("rebrand_scan",   "Scan Brands",       "Detect watermarks only",
                "Select file or folder → OUT/REBRAND/scan.txt (no write)"),
        )

        // ── 10 SO Analyzer ────────────────────────────────────────────────
        10 -> listOf(
            SubTool("so_xor_scan",    "XOR Brute-Scan",   "All 256 single-byte keys + URL extract",
                "Select .so / .bin → OUT/SO/xor_results.txt  (shows all decoded URLs per key)"),
            SubTool("so_multi_xor",   "Multi-Byte XOR",   "Custom key list from WORK/xor_keys.txt",
                "One key per line (hex or utf8). Select binary → OUT/SO/multikey_results.txt"),
            SubTool("so_url_dump",    "URL/String Dump",  "Extract plaintext endpoints",
                "Select .so → OUT/SO/urls.txt + strings.txt"),
            SubTool("so_aes_probe",   "AES Key Probe",    "Scan for AES-related patterns; does not recover secret keys",
                "Select .so → OUT/SO/aes_keys.txt  (entropy + pattern scan)"),
            SubTool("so_patch_url",   "Patch Plaintext URL", "Replace an existing URL in a .so binary",
                "CONFIG: old_url=<existing URL> and new_url=<same-length or shorter URL>; output is written under OUT/SO/"),
            SubTool("url_scan_so",      "URL Scanner",    "Extract all embedded URLs, IPs and host:port from .so / APK binaries",
                "Select .so file or folder of .so files → OUT/URLSCAN/urls_found.txt"),
            SubTool("sm4_find_all",    "SM4 Key Finder+", "Scan .so for SM4_SECRET_NEW + SM4_SECRET_4 + SM4_SECRET_2 candidates",
                "Select folder containing arm64-v8a/*.so → OUT/SM4/sm4_all_keys.txt"),
            SubTool("so_dump_audit", "Offline Dump Analyzer", "Read-only hash, bounded entropy and printable-string report for an existing authorized dump; no live process access or key extraction",
                "Select authorized .dmp/.bin → OUT/SO/*.offline_dump.json"),

        )

        // ── 11 Frida Tracer ───────────────────────────────────────────────
        11 -> listOf(
            SubTool("frida_jni_hook",  "JNI URL Tracer",  "Generate a script to observe JNI_OnLoad; manual review required",
                "Select the target .so → OUT/FRIDA/jni_hook_<name>.js"),
            SubTool("frida_js_dump",   "JS Script Dump",  "Export generated Frida script for manual use",
                "Enter target package in CONFIG; script is saved under OUT/FRIDA/", needsFile = false),
            SubTool("frida_spawn",     "Spawn + Trace",   "Generate Frida spawn/trace commands",
                "Enter target package in CONFIG; command file is saved under OUT/FRIDA/", needsFile = false),
        )

        // ── 12 XOR Suite ──────────────────────────────────────────────────
        12 -> listOf(
            SubTool("xor_single_byte", "Single-Byte Scan",  "Try all 256 keys, show readable candidates",
                "Select any binary → OUT/XOR/single_scan.txt  (sorted by readability score)"),
            SubTool("xor_custom_key",  "Custom XOR Key",    "Apply specific key to file",
                "Put key in WORK/xor_key.txt (hex bytes e.g. DEADBEEF). Select file → OUT/XOR/*_xored.*"),
            SubTool("xor_luas_strip",  "LuaS Strip-XOR",   "Strip LuaS header then XOR",
                "Select .luac with XOR-wrapped LuaS → OUT/XOR/*_stripped.lua"),
            SubTool("xor_batch",       "Batch XOR",         "Apply same key to all files in WORK/BATCH/",
                "Drop files in WORK/BATCH/, enter key in CONFIG → OUT/XOR/batch/", needsFile = false),
            SubTool("xor_selftest", "XOR Known-Vector Self-Test", "Verify repeating-key XOR against a fixed known ciphertext and round-trip fixture",
                "No input required → OUT/XOR/xor_selftest.json", needsFile = false),
        )

        // ── 13 Decrypt Engine ─────────────────────────────────────────────
        13 -> listOf(
            SubTool("dec_auto",        "Auto-Detect",       "Probe supported transforms; validate output before use",
                "Select encrypted blob → OUT/DEC/auto_result.bin  (first successful algo wins)"),
            SubTool("dec_aes_cbc",     "AES-CBC Decrypt",   "Key+IV from WORK/aes_config.txt",
                "aes_config.txt: key=<hex32> iv=<hex16>. Select ciphertext → OUT/DEC/*_aes.bin"),
            SubTool("dec_aes_ecb",     "AES-ECB Decrypt",   "Key from WORK/aes_config.txt",
                "aes_config.txt: key=<hex32>. Select ciphertext → OUT/DEC/*_ecb.bin"),
            SubTool("dec_zuc",         "ZUC-like Fallback", "Approximate stream transform; not standards-compliant ZUC",
                "zuc_config.txt: key=<hex32> iv=<hex16>. Select ciphertext → OUT/DEC/*_zuc.bin"),
            SubTool("dec_sm4",         "SM4 Block",         "Key from WORK/sm4_config.txt",
                "sm4_config.txt: key=<hex32> mode=CBC|ECB iv=<hex16>. → OUT/DEC/*_sm4.bin"),
            SubTool("dec_simple1",     "SIMPLE1 Restore",   "Alvsia SIMPLE1 reversal",
                "Select SIMPLE1-encrypted .pak or blob → OUT/DEC/*_simple1.bin"),
            SubTool("dec_selftest", "AES Known-Answer Self-Test", "Verify AES-ECB and AES-CBC against fixed NIST test vectors",
                "No input required → OUT/DEC/decrypt_selftest.json", needsFile = false),
        )

        // ── 14 PAK Deep ───────────────────────────────────────────────────
        14 -> listOf(
            SubTool("pak_deep_aes",    "AES-SHA1 PAK",      "Decrypt AES-CBC PAK with SHA1-derived key",
                "CONFIG: passphrase=<text> plus iv=<32 hex chars>, or key=<32 hex chars> plus iv=<32 hex chars>. Select .pak → OUT/PAKD/"),
            SubTool("pak_deep_zstd",   "Zstd Decompress",   "Decompress Zstd-compressed entries",
                "Select .pak or raw Zstd blob → OUT/PAKD/*_zstd/"),
            SubTool("pak_deep_zuc",    "ZUC-like PAK",      "Approximate stream transform then ZIP extraction; not standard ZUC",
                "zuc_config.txt required. Select .pak → OUT/PAKD/*_zuc/"),
            SubTool("pak_deep_sm4",    "SM4-PAK",           "SM4 decrypt then PAK unpack",
                "sm4_config.txt required. Select .pak → OUT/PAKD/*_sm4/"),
            SubTool("pak_deep_auto",   "Deep Auto-Probe",   "Try all encryption combos",
                "Select .pak → OUT/PAKD/probe_report.txt + first successful extract"),
            SubTool("pak_deep_integrity_audit", "PAK Integrity & Slot Fingerprint", "Read-only validation of payload/block ranges, overlapping slots, duplicate content hashes and SHA-256 fingerprints",
                "Select .pak → OUT/PAKD/*.integrity_audit.json; source PAK is never modified"),
            SubTool("sm4_keyfind",     "SM4 Key Finder",    "Scan .so files for embedded SM4_SECRET_NEW candidates (aA0-pattern)",
                "Select a folder containing arm64-v8a/*.so → OUT/SM4/sm4_keys.txt"),
        )

        // ── 15 String Recover ─────────────────────────────────────────────
        15 -> listOf(
            SubTool("str_recover",     "String Restore",    "Recover candidate readable strings; not guaranteed deobfuscation",
                "Select .luac → OUT/STR/*_strings_recovered.txt"),
            SubTool("str_constant_pool","Constant Pool",    "Extract embedded Lua bytecode strings (not a full typed parser)",
                "Select .luac → OUT/STR/*_constants_typed.txt"),
            SubTool("str_xref",        "String XRef",       "Search byte offsets for a supplied string",
                "Select .luac → OUT/STR/*_xref.txt"),
        )

        // ── 16 Lua Inject — backend compatibility ID only ─────────────────
        // The visible Inject tools live exclusively inside SMART LUA (module 05).
        // Module 16 remains reserved so existing grants/dispatch IDs stay stable.
        16 -> emptyList()

        // ── 17 Anti-RE Audit ──────────────────────────────────────────────
        17 -> listOf(
            SubTool("audit_apk",       "APK Audit",         "Scan APK for weak anti-RE posture",
                "Select .apk → OUT/AUDIT/report.txt  (ProGuard gaps, strings, native coverage)"),
            SubTool("audit_lua",       "LUA Audit",         "Find unhashed strings, naked function names",
                "Select .lua / .luac → OUT/AUDIT/lua_report.txt"),
            SubTool("audit_so",        "SO Coverage",       "Check native lib for exported symbols, debug info",
                "Select .so → OUT/AUDIT/so_report.txt"),
            SubTool("anti_re_source_triage", "Obfuscation & Behavior Triage", "Static indicators for encoded payloads, dynamic execution, process-memory APIs and anti-cheat evasion patterns; never executes input",
                "Select .py/.lua/.js/.cpp → OUT/AUDIT/*.source_triage.json"),
        )

        // ── 18 Lua Protector — backend compatibility ID only ───────────────
        // The visible Protect tools live exclusively inside SMART LUA (module 05).
        // Module 18 remains reserved so existing grants/dispatch IDs stay stable.
        18 -> emptyList()

        // Module 19 — ALVSIA PRIVATE TOOL (sealed runtime required)
    19 -> listOf(
        SubTool("priv_zuc_decrypt",   "ZUC-128 Decrypt",       "ZUC-128 stream cipher decrypt (16-byte key + IV)",
            "Select encrypted .bin → OUT/ALVSIA_PRIVATE/*_zuc_dec.bin"),
        SubTool("priv_aes_scan",      "AES Key Scanner",       "Scan binary for AES S-box, Rcon, expanded key schedules, and high-entropy candidates",
            "Select .so / .bin → OUT/ALVSIA_PRIVATE/aes_scan.txt"),
        SubTool("priv_xor_recover",   "XOR Key Recovery",      "IC-based multi-byte XOR key recovery from ciphertext",
            "Select encrypted .bin → OUT/ALVSIA_PRIVATE/xor_keys.txt"),
        SubTool("priv_lua_parse",     "Lua Bytecode Parser",   "Extract all string and number constants from Lua 5.1/5.3/BGMI bytecode",
            "Select .luac → OUT/ALVSIA_PRIVATE/*_parsed.txt"),
        SubTool("priv_lua_convert",   "BGMI→Std Lua",          "Convert BGMI scrambled Lua bytecode to standard Lua 5.3 (XOR + opcode remap)",
            "Select .luac file or folder → OUT/ALVSIA_PRIVATE/bgmi_std/*.luac"),
        SubTool("priv_lua_heping",    "HePing→Std Lua",        "Convert HePing JY (和平精英) scrambled Lua bytecode to standard Lua 5.3",
            "Select .luac file or folder → OUT/ALVSIA_PRIVATE/heping_std/*.luac"),
        SubTool("priv_compress_fit",  "Compression Best-Fit",  "Find zlib/zstd level that fits data into a target size budget",
            "Select .bin + set target_size in config → OUT/ALVSIA_PRIVATE/*_compressed.bin"),
        SubTool("priv_apk_audit",     "APK Auditor",           "Structural APK audit: package, DEX count, native arches, signing block V2/V3",
            "Select .apk → OUT/ALVSIA_PRIVATE/apk_audit.txt"),
        SubTool("priv_apk_manifest",  "APK Manifest",          "Extract raw AndroidManifest.xml from APK and identify package name",
            "Select .apk → OUT/ALVSIA_PRIVATE/AndroidManifest.raw.xml"),
        SubTool("priv_str_recover",   "String Recovery",       "Multi-strategy string constant recovery: XOR, base64, reversed, raw printable",
            "Select .bin / .so → OUT/ALVSIA_PRIVATE/strings_recovered.txt"),
        SubTool("priv_entropy_map",   "Entropy Map",           "Per-block entropy analysis: find encrypted, compressed, code and padding regions",
            "Select .bin / .so → OUT/ALVSIA_PRIVATE/entropy_map.txt"),
        SubTool("priv_pak_manifest",  "PAK Manifest CSV",      "Generate CSV manifest of all entries in a TencentPak file",
            "Select .pak → OUT/ALVSIA_PRIVATE/*_manifest.csv"),
    )

    else -> emptyList()
    }
}
