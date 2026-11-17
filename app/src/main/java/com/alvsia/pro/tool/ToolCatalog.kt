package com.alvsia.pro.tool

import com.alvsia.pro.ui.home.ToolItem
import org.json.JSONArray
import org.json.JSONObject

/**
 * ALVSIA PRO 5.5.0 — 19-module catalog.
 * Modules 1-9: original. 10-18: v5.5.0 additions. 19: ALVSIA PRIVATE TOOL (sealed runtime).
 */
object ToolCatalog {
    fun defaults(): List<ToolItem> = listOf(
        // --- ORIGINAL ---
        ToolItem(1,  "PAK Unpack",      "Extract · list · info · CSV"),
        ToolItem(2,  "PAK Rebuild",     "Repack · inject · encrypt · decrypt"),
        ToolItem(3,  "PAK Compact",     "Delete entry · empty · clean"),
        ToolItem(4,  "OBB Tools",       "Unzip · rezip · info"),
        ToolItem(5,  "SMART LUA",       "Decompiler · Protect · Compiler/Recompiler · Inject"),
        ToolItem(6,  "File Scan",       "Strings · hash · report"),
        ToolItem(7,  "Workspace",       "Clear WORK/OUT"),
        ToolItem(8,  "Export Report",   "Session / file summary"),
        ToolItem(9,  "Rebrand",         "ALVSIA PRO auto · manual brand/channel"),
        // --- NEW v5.5.0 ---
        ToolItem(10, "SO Analyzer",     "XOR-brute · URL extract · AES probe · plaintext URL patch"),
        ToolItem(11, "Frida Tracer",    "Generate JNI hook scripts and Frida spawn/trace commands"),
        ToolItem(12, "XOR Suite",       "Single-byte scan · multi-key · LuaS strip · batch"),
        ToolItem(13, "Decrypt Engine",  "AES-CBC/ECB · ZUC-like fallback · SM4 · SIMPLE1 · auto-detect"),
        ToolItem(14, "PAK Deep",        "AES-SHA1 PAK · Zstd decompress · ZUC-like fallback · SM4"),
        ToolItem(15, "String Recover",  "Obfuscated string restore · constant pool dump"),
        ToolItem(16, "Lua Inject",      "Legacy backend adapter — public access is SMART LUA INJECT"),
        ToolItem(17, "Anti-RE Audit",   "Detect weak points in target APK · generate report"),
        ToolItem(18, "Lua Protector",   "Legacy backend adapter — public access is SMART LUA PROTECT"),
        // --- PRIVATE MODULE ---
        ToolItem(19, "ALVSIA PRIVATE TOOL", "Private analysis suite · sealed runtime required"),
    )

    fun parseCore(bytes: ByteArray?): List<ToolItem> {
        if (bytes == null || bytes.size < 16) return defaults()
        return try {
            val magic = bytes.copyOfRange(0, 8).toString(Charsets.US_ASCII)
            if (magic != "ALVCAT01") return defaults()
            val json = bytes.copyOfRange(8, bytes.size).toString(Charsets.UTF_8)
            val root = JSONObject(json)
            val arr: JSONArray = root.optJSONArray("tools") ?: return defaults()
            val out = ArrayList<ToolItem>(arr.length().coerceAtLeast(defaults().size))
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                out.add(ToolItem(
                    id    = o.optInt("id", i + 1),
                    title = o.optString("title", "Tool ${i+1}"),
                    desc  = o.optString("desc", "")
                ))
            }
            // Always expose the complete local catalog. Server entries override matching
            // IDs, while missing modules are filled from defaults to prevent menu gaps.
            val merged = defaults().associateBy { it.id }.toMutableMap()
            out.forEach { item -> merged[item.id] = item }
            merged.values.sortedBy { it.id }
        } catch (_: Exception) {
            defaults()
        }
    }
}
