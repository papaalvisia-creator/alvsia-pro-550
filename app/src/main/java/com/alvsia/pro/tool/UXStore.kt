package com.alvsia.pro.tool

import android.content.Context
import android.net.Uri
import android.util.Log

/**
 * ALVSIA PRO 5.5.2 — RecentFiles + Favorites (UX Sprint 1)
 *
 * SharedPreferences-backed helpers for:
 *  - Recent Files carousel (last 10 file paths used by any tool)
 *  - Favorites (starred subtools — appear at top of SubMenu screen)
 *
 * No external dependencies — pure SharedPreferences.
 */
object UXStore {
    private const val TAG = "ALVSIA_UXStore"
    private const val PREFS_NAME = "alvsia_ux_store"
    private const val KEY_RECENT = "recent_files"
    private const val KEY_FAVORITES = "favorites"
    private const val MAX_RECENT = 10

    // ── Recent Files ──────────────────────────────────────────────────

    /**
     * Add a file URI to the recent list (most recent first).
     * Duplicates are moved to the front. List is capped at MAX_RECENT.
     */
    fun addRecent(ctx: Context, uri: Uri) {
        try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val current = getRecentList(ctx).toMutableList()
            val uriStr = uri.toString()
            current.remove(uriStr)
            current.add(0, uriStr)
            while (current.size > MAX_RECENT) current.removeAt(current.size - 1)
            prefs.edit().putString(KEY_RECENT, current.joinToString("\n")).apply()
        } catch (e: Exception) {
            Log.w(TAG, "addRecent failed: ${e.message}")
        }
    }

    /**
     * Get the list of recent file URIs (most recent first).
     */
    fun getRecentList(ctx: Context): List<String> {
        return try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val raw = prefs.getString(KEY_RECENT, "") ?: ""
            if (raw.isBlank()) emptyList() else raw.split("\n").filter { it.isNotBlank() }
        } catch (e: Exception) {
            emptyList()
        }
    }

    /**
     * Get recent file URIs as display strings (last path segment, truncated).
     */
    fun getRecentDisplayNames(ctx: Context): List<Pair<String, String>> {
        return getRecentList(ctx).mapNotNull { uriStr ->
            try {
                val uri = Uri.parse(uriStr)
                val name = uri.lastPathSegment?.substringAfterLast('/') ?: "file"
                val display = if (name.length > 30) "..." + name.takeLast(27) else name
                display to uriStr
            } catch (_: Exception) {
                null
            }
        }
    }

    /** Remove one URI from the recent list without disturbing the remaining order. */
    fun removeRecent(ctx: Context, uriString: String) {
        try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val updated = getRecentList(ctx).filterNot { it == uriString }
            prefs.edit().putString(KEY_RECENT, updated.joinToString("\n")).apply()
        } catch (_: Exception) {}
    }

    /**
     * Clear all recent files.
     */
    fun clearRecent(ctx: Context) {
        try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().remove(KEY_RECENT).apply()
        } catch (_: Exception) {}
    }

    // ── Favorites ─────────────────────────────────────────────────────

    /**
     * Toggle favorite status for a subtool ID.
     */
    fun toggleFavorite(ctx: Context, subtoolId: String) {
        try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val favorites = getFavoritesSet(ctx).toMutableSet()
            if (subtoolId in favorites) {
                favorites.remove(subtoolId)
            } else {
                favorites.add(subtoolId)
            }
            prefs.edit().putStringSet(KEY_FAVORITES, favorites).apply()
        } catch (_: Exception) {}
    }

    /**
     * Check if a subtool is favorited.
     */
    fun isFavorite(ctx: Context, subtoolId: String): Boolean {
        return try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val favorites = prefs.getStringSet(KEY_FAVORITES, emptySet()) ?: emptySet()
            subtoolId in favorites
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Get the set of favorited subtool IDs.
     */
    fun getFavoritesSet(ctx: Context): Set<String> {
        return try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val stored = prefs.getStringSet(KEY_FAVORITES, emptySet())?.toSet() ?: emptySet()
            val legacyAliases = mapOf(
                "universal_file_detect" to "forensics_universal_file_detection",
                "workspace_report" to "forensics_evidence_report",
                "engine_health" to "lab_engine_self_test",
                "pak_info" to "pak_explorer_info",
                "pak_extract" to "pak_extract_unpak",
                "pak_repack" to "pak_rebuild_repack",
                "pak_lua_inject" to "lua_custom_inject",
                "asset_uasset_classify" to "modding_uasset_uexp_inspector",
                "asset_uexp_classify" to "modding_uasset_uexp_inspector",
                "asset_locres_umap_classify" to "modding_resource_mapping_recovery",
                "asset_report" to "forensics_evidence_report",
                "apk_audit" to "apk_structure_inspector",
                "dex_report" to "apk_dex_bytecode_inspector",
                "url_scan" to "forensics_string_url_recovery",
                "so_audit" to "native_elf_so_inspector",
                "native_strings" to "native_strings_symbols",
                "abi_dependency_report" to "native_abi_dependency_report",
                "aes_scan" to "crypto_aes_candidate_transform",
                "zuc_decrypt" to "crypto_zuc_engine",
                "string_recovery" to "forensics_string_url_recovery",
                "file_report" to "forensics_file_signature_hash",
                "strings" to "forensics_string_url_recovery",
                "entropy" to "forensics_entropy_region",
                "hex_preview" to "forensics_hex_structure_viewer",
                "batch_audit" to "workspace_batch_job_queue",
                "regression_compare" to "lab_regression_diff_compare",
                "self_test" to "lab_engine_self_test",
                "lua_t24_convert" to "lua_t24_bgmi_pubg_converter",
                "lua_multi_xor" to "crypto_xor_multi_xor",
                "lua_protect_transform" to "lua_protect_compile"
            )
            val migrated = stored.mapTo(mutableSetOf()) { legacyAliases[it] ?: it }
            if (migrated != stored) prefs.edit().putStringSet(KEY_FAVORITES, migrated).apply()
            migrated
        } catch (e: Exception) {
            emptySet()
        }
    }
}
