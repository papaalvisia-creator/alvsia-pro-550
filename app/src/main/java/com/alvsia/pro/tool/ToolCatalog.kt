package com.alvsia.pro.tool

import com.alvsia.pro.ui.home.ToolItem
import org.json.JSONArray
import org.json.JSONObject

/** Small visible catalog; legacy capabilities are providers behind Smart engines. */
object ToolCatalog {
    fun defaults(): List<ToolItem> = listOf(
        ToolItem(1, "SMART LUA", "One engine: decompile · analyze · protect · compile/recompile · inject"),
        ToolItem(2, "SMART PAK", "Detect · inspect · unpack · modify · repack · integrity"),
        ToolItem(3, "SMART OBB", "Detect · extract · modify · rebuild · integrity"),
        ToolItem(4, "SMART DATA", "XOR · AES · SM4 NEW · strings · metadata recovery"),
        ToolItem(5, "SMART ANALYSIS", "SO · URL · JNI trace · APK/Lua audit"),
        ToolItem(6, "WORKSPACE & REPORT", "Workspace · hash · reports"),
        ToolItem(7, "ALVSIA PRIVATE", "Private analysis providers")
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