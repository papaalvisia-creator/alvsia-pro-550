package com.alvsia.pro.sec

import android.content.Context

/**
 * Security-event adapter.
 *
 * Keeps the existing emit API while routing threat reports through the same
 * authenticated Unaux session and server-side Telegram relay as operational
 * notifications. License values, HWIDs, device model/build identifiers,
 * coordinates, storage paths and file contents are never included.
 */
object ThreatReport {
    private val acceptedKinds = setOf("TAMPER", "FRIDA", "ROOT", "DEBUG", "SIG_BLOCK", "THREAT")

    @Suppress("UNUSED_PARAMETER")
    fun emit(ctx: Context, kind: String, detail: String, license: String = "") {
        val event = kind.trim().uppercase().takeIf { it in acceptedKinds } ?: "THREAT"
        val safeDetail = detail
            .replace(
                Regex("(?i)\\b(token|api[_-]?key|password|license(?:[_-]?key)?|session[_-]?token|hwid|device[_-]?id)\\b\\s*[:=]\\s*[^\\s,;]+"),
                "\\$1=[REDACTED]"
            )
            .replace(Regex("(?i)https?://[^\\s]+"), "[URL REDACTED]")
            .replace(Regex("(?i)(/data/[^\\s]+|/storage/[^\\s]+|/sdcard/[^\\s]+)"), "[PATH REDACTED]")
            .replace(Regex("(?i)\\b(latitude|longitude|lat|lon|lng|location)\\s*[:=]\\s*[^\\s,;]+"), "\\$1=[REDACTED]")
            .take(1200)

        // The legacy license argument is retained for source compatibility,
        // but deliberately ignored. PanelClient binds the relay to its active session.
        TelegramNotifier.notify(ctx, event, safeDetail)
    }
}
