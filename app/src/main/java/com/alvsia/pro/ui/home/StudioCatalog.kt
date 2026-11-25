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
        StudioItem("apk", "SMART APK", "APK structure, manifest, DEX and signature audit", "📱", listOf(1)),
        StudioItem("pak", "SMART PAK", "PAK profile, explore, extract, inject and rebuild", "📦", listOf(2)),
        StudioItem("obb", "SMART OBB", "OBB inspect, extract, repack and integrity", "🗃️", listOf(3)),
        StudioItem("lua", "SMART LUA", "Lua analyze, bytecode, decompile, convert and inject", "🌙", listOf(4)),
        StudioItem("crypto", "SMART CRYPTO", "XOR, AES, SM4, ZUC and key-pattern tools", "🔐", listOf(5)),
        StudioItem("forensics", "SMART FORENSICS", "File detection, strings, entropy and evidence", "🔎", listOf(6)),
        StudioItem("modding", "SMART MODDING", "UAsset, UEXP, skins, ZSDIC and resource mapping", "🧩", listOf(7)),
        StudioItem("native", "SMART NATIVE", "ELF, SO, symbols, ABI and authorized trace", "⚙️", listOf(8)),
        StudioItem("workspace", "SMART WORKSPACE", "Files, favorites, batch jobs, progress and outputs", "🗂️", listOf(9)),
        StudioItem("engine-lab", "SMART ENGINE LAB", "Engine registry, self-test, regression and benchmark", "🧪", listOf(10))
    )

    fun moduleIds(studio: StudioItem): List<Int> = studio.moduleIds
    fun find(id: String): StudioItem? = all.firstOrNull { it.id == id }
    fun hasCompleteUniqueCoverage(): Boolean {
        val ids = all.flatMap { it.moduleIds }
        return ids.size == 10 && ids.toSet().size == 10 && ids.toSet() == (1..10).toSet()
    }
}