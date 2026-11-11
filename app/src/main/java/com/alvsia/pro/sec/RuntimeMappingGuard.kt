package com.alvsia.pro.sec

import android.content.Context
import java.io.File

/**
 * ALVSIA runtime executable-mapping guard.
 *
 * Looks for high-confidence executable mappings originating from writable or
 * suspicious locations. Normal system, APK, APEX and application-library
 * mappings are not blacklisted.
 */
object RuntimeMappingGuard {
    private val suspiciousPrefixes = listOf(
        "/data/local/tmp/",
        "/data/local/tmp",
        "/sdcard/",
        "/storage/emulated/",
        "/mnt/runtime/",
        "/data/user/0/com.alvsia.pro/cache/",
        "/data/user/0/com.alvsia.pro/code_cache/",
        "/data/user/0/com.alvsia.pro/files/"
    )

    fun executableForeignMappings(ctx: Context): List<String> {
        ctx.applicationContext
        return try {
            File("/proc/self/maps").useLines { lines ->
                lines.mapNotNull { line ->
                    val fields = line.trim().split(Regex("\\s+"), limit = 6)
                    if (fields.size < 2 || 'x' !in fields[1]) return@mapNotNull null
                    val name = fields.getOrNull(5)?.trim().orEmpty()
                    if (name.isBlank() || name.startsWith("[") || name == "anon_inode:[vdso]") return@mapNotNull null
                    val normalized = name.lowercase()
                    val suspicious = suspiciousPrefixes.any { normalized.startsWith(it) }
                    if (suspicious) name else null
                }.distinct().take(16).toList()
            }
        } catch (_: Throwable) {
            emptyList()
        }
    }

    fun signals(ctx: Context): List<String> =
        executableForeignMappings(ctx).map { "foreign_exec_map:" + it.take(180) }
}
