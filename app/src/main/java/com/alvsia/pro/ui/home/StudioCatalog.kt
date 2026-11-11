package com.alvsia.pro.ui.home

/**
 * Seven user-facing workspaces. Module IDs remain the stable engine/API contract:
 * this catalog only groups the existing 19 modules for navigation.
 */
data class StudioItem(
    val id: String,
    val title: String,
    val description: String,
    val icon: String,
    val moduleIds: List<Int>
)

object StudioCatalog {
    val all: List<StudioItem> = listOf(
        StudioItem("pak", "PAK Studio", "Unpack, rebuild, compact and inspect PAK archives", "📦", listOf(1, 2, 3, 14)),
        StudioItem("obb", "OBB Studio", "Extract, rebuild and validate OBB packages", "💾", listOf(4)),
        StudioItem("lua", "Lua Studio", "Analyze, decompile, recover, inject and protect Lua", "🌙", listOf(5, 15, 16, 18)),
        StudioItem("file", "File Studio", "Scan files and manage the shared work area", "🗂️", listOf(6, 7)),
        StudioItem("security", "Security Studio", "Inspect native libraries, runtime traces and anti-RE posture", "🛡️", listOf(10, 11, 17)),
        StudioItem("crypto", "Crypto Studio", "XOR, decryption and private cryptographic utilities", "🔐", listOf(12, 13, 19)),
        StudioItem("project", "Project Studio", "Rebrand assets and export project reports", "🧩", listOf(8, 9))
    )

    fun moduleIds(studio: StudioItem): List<Int> = studio.moduleIds

    fun find(id: String): StudioItem? = all.firstOrNull { it.id == id }

    fun hasCompleteUniqueCoverage(): Boolean {
        val ids = all.flatMap { it.moduleIds }
        return ids.size == 19 && ids.toSet().size == 19 && ids.toSet() == (1..19).toSet()
    }
}
