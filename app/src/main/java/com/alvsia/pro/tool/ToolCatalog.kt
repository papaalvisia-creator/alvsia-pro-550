package com.alvsia.pro.tool

import com.alvsia.pro.ui.home.ToolItem
import org.json.JSONArray
import org.json.JSONObject

/** ALVSIA SMART PREMIUM 6.0.0 public catalog: exactly 10 main menus. */
object ToolCatalog {
    fun defaults(): List<ToolItem> = listOf(
        ToolItem(1, "SMART APK", "Structure · manifest · DEX · resources · signature"),
        ToolItem(2, "SMART PAK", "Profile · explore · extract · inject · rebuild · verify"),
        ToolItem(3, "SMART OBB", "Inspect · extract · Mini-OBB · GamePatch · verify"),
        ToolItem(4, "SMART LUA", "Analyze · bytecode · decompile · convert · protect · inject"),
        ToolItem(5, "SMART CRYPTO", "XOR · AES · SM4 · ZUC · key-pattern recovery"),
        ToolItem(6, "SMART FORENSICS", "File detection · hashes · strings · entropy · evidence"),
        ToolItem(7, "SMART MODDING", "UAsset · UEXP · skins · ZSDIC · offsets · resources"),
        ToolItem(8, "SMART NATIVE", "ELF · SO · symbols · ABI · XREF · authorized tracing"),
        ToolItem(9, "SMART WORKSPACE", "Files · favorites · batch queue · progress · outputs"),
        ToolItem(10, "SMART ENGINE LAB", "Registry · diagnostics · regression · large-file tests")
    )

    fun parseCore(bytes: ByteArray?): List<ToolItem> {
        if (bytes == null || bytes.size < 16) return defaults()
        return try {
            val magic = bytes.copyOfRange(0, 8).toString(Charsets.US_ASCII)
            if (magic != "ALVCAT01") return defaults()
            val json = bytes.copyOfRange(8, bytes.size).toString(Charsets.UTF_8)
            val root = JSONObject(json)
            val arr: JSONArray = root.optJSONArray("tools") ?: return defaults()
            val merged = defaults().associateBy { it.id }.toMutableMap()
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                val id = o.optInt("id", -1)
                if (id in 1..defaults().size) {
                    merged[id] = ToolItem(id, o.optString("title", merged[id]?.title ?: "Tool $id"), o.optString("desc", merged[id]?.desc ?: ""))
                }
            }
            merged.values.sortedBy { it.id }
        } catch (_: Exception) {
            defaults()
        }
    }
}