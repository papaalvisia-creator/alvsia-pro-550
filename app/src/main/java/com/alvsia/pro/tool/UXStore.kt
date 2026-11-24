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
            prefs.getStringSet(KEY_FAVORITES, emptySet()) ?: emptySet()
        } catch (_: Exception) {
            emptySet()
        }
    }
}
