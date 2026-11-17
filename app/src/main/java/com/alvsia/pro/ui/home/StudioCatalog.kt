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
    // Output Browser handoff targets the same seven public Smart modules.
    // Legacy provider IDs are resolved later by SmartModuleRouter.
    val all: List<StudioItem> = listOf(
        StudioItem("lua", "SMART LUA", "Decompiler, Protect, Compiler/Recompiler and Inject", "🌙", listOf(1)),
        StudioItem("pak", "SMART PAK", "Inspect, unpack, modify, rebuild and verify PAK archives", "📦", listOf(2)),
        StudioItem("obb", "SMART OBB", "Inspect, extract, rebuild and verify OBB packages", "💾", listOf(3)),
        StudioItem("data", "SMART DATA", "XOR, AES, SM4, strings and data recovery", "🔑", listOf(4)),
        StudioItem("analysis", "SMART ANALYSIS", "Native, SO, APK and runtime analysis", "🔬", listOf(5)),
        StudioItem("workspace", "WORKSPACE & REPORT", "Hash, provenance, reports and shared outputs", "📊", listOf(6)),
        StudioItem("private", "ALVSIA PRIVATE", "Sealed private providers and owner-only workflows", "⚙️", listOf(7))
    )

    fun moduleIds(studio: StudioItem): List<Int> = studio.moduleIds

    fun find(id: String): StudioItem? = all.firstOrNull { it.id == id }

    fun hasCompleteUniqueCoverage(): Boolean {
        val ids = all.flatMap { it.moduleIds }
        return ids.size == 7 && ids.toSet().size == 7 && ids.toSet() == (1..7).toSet()
    }
}
