package com.alvsia.pro.tool

import com.alvsia.pro.ui.home.ToolItem
import org.json.JSONArray
import org.json.JSONObject

/** ALVSIA SMART PREMIUM public catalog: exactly 9 menus. */
object ToolCatalog {
    fun defaults(): List<ToolItem> = listOf(
        ToolItem(1, "HOME", "Universal detect · workspace report · engine health"),
        ToolItem(2, "LUA", "Smart analyze · recovery · T24/BGMI · XOR · protect · inject"),
        ToolItem(3, "PAK / OBB", "PAK inspect · extract · Lua inject · repack"),
        ToolItem(4, "ASSET / UE", "UAsset · UExp/UBulk · LOCRES/UMAP · asset reports"),
        ToolItem(5, "APK / DEX", "APK audit · DEX report · URL scan · package/signature audit"),
        ToolItem(6, "NATIVE", "ELF/SO audit · strings · ABI/dependency report"),
        ToolItem(7, "CRYPTO / RECOVERY", "AES · ZUC · string recovery · URL recovery"),
        ToolItem(8, "FORENSIC / STRING", "File report · strings · entropy · hex preview"),
        ToolItem(9, "BATCH / DEV LAB", "Batch audit · regression/compare · self test")
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