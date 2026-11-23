package com.alvsia.pro.ui.home

data class StudioItem(
    val id: String,
    val title: String,
    val description: String,
    val icon: String,
    val moduleIds: List<Int>
)

object StudioCatalog {
    val all: List<StudioItem> = listOf(
        StudioItem("home", "HOME", "File detection, workspace reports and engine health", "🏠", listOf(1)),
        StudioItem("lua", "LUA", "Smart analyze, recovery, T24, XOR, protect and inject", "🌙", listOf(2)),
        StudioItem("pak", "PAK / OBB", "Inspect, extract, inject and rebuild archives", "📦", listOf(3)),
        StudioItem("asset", "ASSET / UE", "UAsset, UExp, LOCRES and UMAP classification", "🧩", listOf(4)),
        StudioItem("apk", "APK / DEX", "APK audit, DEX reporting and URL recovery scan", "📱", listOf(5)),
        StudioItem("native", "NATIVE", "SO audit, native strings and ABI dependencies", "⚙️", listOf(6)),
        StudioItem("crypto", "CRYPTO / RECOVERY", "AES, ZUC and string recovery", "🔐", listOf(7)),
        StudioItem("forensic", "FORENSIC / STRING", "File reports, strings, entropy and hex preview", "🔎", listOf(8)),
        StudioItem("batch", "BATCH / DEV LAB", "Batch audit, regression comparison and self-test", "🧪", listOf(9))
    )

    fun moduleIds(studio: StudioItem): List<Int> = studio.moduleIds
    fun find(id: String): StudioItem? = all.firstOrNull { it.id == id }
    fun hasCompleteUniqueCoverage(): Boolean {
        val ids = all.flatMap { it.moduleIds }
        return ids.size == 9 && ids.toSet().size == 9 && ids.toSet() == (1..9).toSet()
    }
}
