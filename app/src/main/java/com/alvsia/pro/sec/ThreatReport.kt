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
    private val acceptedKinds = setOf("TAMPER", "FRIDA", "ROOT", "DEBUG", "SIG_BLOCK", "THREAT", "SOFT_THREAT")
    private val sensitiveField = Regex(
        "(?i)\\b(token|api[_-]?key|password|license(?:[_-]?key)?|session[_-]?token|hwid|device[_-]?id)\\b\\s*[:=]\\s*[^\\s,;]+"
    )
    private val locationField = Regex(
        "(?i)\\b(latitude|longitude|lat|lon|lng|location)\\s*[:=]\\s*[^\\s,;]+"
    )

    @Suppress("UNUSED_PARAMETER")
    fun emit(ctx: Context, kind: String, detail: String, license: String = "") {
        val event = kind.trim().uppercase().takeIf { it in acceptedKinds } ?: "THREAT"
        val safeDetail = sensitiveField.replace(detail) { match ->
            "${match.groupValues[1]}=[REDACTED]"
        }
            .replace(Regex("(?i)https?://[^\\s]+"), "[URL REDACTED]")
            .replace(Regex("(?i)(/data/[^\\s]+|/storage/[^\\s]+|/sdcard/[^\\s]+)"), "[PATH REDACTED]")
            .let { locationField.replace(it) { match -> "${match.groupValues[1]}=[REDACTED]" } }
            .take(1200)

        // The legacy license argument is retained for source compatibility,
        // but deliberately ignored. PanelClient binds the relay to its active session.
        // Isolated hook-library and proxy-port observations are low-confidence
        // heuristics, not proof of active compromise. Keep them in local RASP
        // diagnostics and reserve Telegram alerts for corroborated threats.
        val signals = safeDetail.split('|').map { it.trim() }.filter { it.isNotEmpty() }
        val lowConfidenceOnly = signals.isNotEmpty() && signals.all { signal ->
            signal.startsWith("executable_hook_library:shadowhook", ignoreCase = true) ||
                Regex("(?i)^proxy_port:[0-9]{1,5}$").matches(signal)
        }
        val routedEvent = if (event == "THREAT" && lowConfidenceOnly) "SOFT_THREAT" else event
        TelegramNotifier.notify(ctx, routedEvent, safeDetail)
    }
}
