package com.alvsia.pro.sec

import android.content.Context
import android.util.Log
import com.alvsia.pro.BuildConfig
import java.io.File
import java.net.URI
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

/**
 * ALVSIA PRO Telegram operational notifier.
 *
 * Keeps owner notifications for session, tool, scan, patch and error events.
 * Only sends bounded operational summaries. It never crawls storage, hashes
 * arbitrary files, uploads file contents, collects IP/GPS, or sends license
 * keys, HWIDs, session tokens, absolute paths, or continuous device telemetry.
 *
 * Delivery uses the authenticated Unaux PanelClient session and the panel's
 * server-side Telegram relay. No bot token or chat ID is read or stored by
 * this APK component.
 */
object TelegramNotifier {
    private const val TAG = "ALVISIA_Telegram"
    private const val MAX_QUEUE = 128

    enum class Channel { BUILD, RUNTIME, ERROR, FILE_INTEL }

    private data class Event(
        val kind: String,
        val detail: String,
        val timestamp: Long,
        val correlationId: String,
        val attempts: Int = 0
    )

    private val queue = ConcurrentLinkedQueue<Event>()
    private val runnerStarted = AtomicBoolean(false)
    @Volatile private var appContext: Context? = null

    private val knownEvents = setOf(
        "SESSION_OK", "SESSION_START", "SESSION_END",
        "TOOL_OK", "TOOL_ERROR", "FILE_LOADED", "SCAN_COMPLETE", "PATCH_OK",
        "ERROR", "TAMPER", "FRIDA", "ROOT", "DEBUG",
        "SIG_BLOCK", "THREAT", "ENGINE_CAP", "BUILD_OK",
        "BUILD_FAIL", "STARTUP_OK", "STARTUP_FAIL", "MODULE_STATUS", "HEARTBEAT"
    )

    fun bindApplicationContext(ctx: Context) {
        appContext = ctx.applicationContext
    }

    /** Existing call-site API retained for compatibility. License is intentionally never transmitted. */
    fun notify(ctx: Context, kind: String, detail: String = "", license: String = "") {
        bindApplicationContext(ctx)
        if (kind !in knownEvents) {
            Log.w(TAG, "Ignored unsupported event: ${kind.take(48)}")
            return
        }
        val safeDetail = sanitize(detail).take(1400)
        if (queue.size >= MAX_QUEUE) {
            Log.w(TAG, "Notification queue full; event dropped: $kind")
            return
        }
        val id = "alv-" + System.currentTimeMillis().toString(16) + "-" +
            Integer.toHexString(kind.hashCode())
        queue.offer(Event(kind, safeDetail, System.currentTimeMillis(), id))
        startWorker()
    }

    /** Session-start equivalent of ultra_notifications.py, with non-secret fields only. */
    fun notifySessionStart(ctx: Context) {
        val version = runCatching {
            ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "unknown"
        }.getOrDefault("unknown")
        notify(
            ctx, "SESSION_START",
            "Application session started\n" +
                "App: $version\nBuild: ${if (BuildConfig.DEBUG) "debug" else "release"}"
        )
    }

    /** File-loaded report is limited to a caller-selected file's name and size. */
    fun notifyFileLoaded(ctx: Context, selectedFile: File, sourceApkName: String? = null) {
        if (!selectedFile.isFile) return
        val detail = buildString {
            append("Selected workspace file loaded\n")
            append("Name: ").append(selectedFile.name.take(160)).append('\n')
            append("Size: ").append(selectedFile.length()).append(" bytes")
            if (!sourceApkName.isNullOrBlank()) {
                append("\nSource APK: ").append(File(sourceApkName).name.take(160))
            }
        }
        notify(ctx, "FILE_LOADED", detail)
    }

    /** Scan report contains aggregate counts only; raw URLs and file paths are omitted. */
    fun notifyScanComplete(ctx: Context, total: Int, countsByType: Map<String, Int>) {
        val detail = buildString {
            append("Scan completed\nTotal findings: ").append(total.coerceAtLeast(0))
            countsByType.entries.take(20).forEach {
                append("\n").append(sanitize(it.key).take(48)).append(": ")
                    .append(it.value.coerceAtLeast(0))
            }
        }
        notify(ctx, "SCAN_COMPLETE", detail)
    }

    /** Patch report reveals only endpoint hosts, never URL query strings or credentials. */
    fun notifyPatchResult(ctx: Context, oldUrl: String, newUrl: String, method: String, fileName: String) {
        val detail = "Patch completed\nFile: ${File(fileName).name.take(160)}" +
            "\nOld host: ${safeHost(oldUrl)}\nNew host: ${safeHost(newUrl)}" +
            "\nMethod: ${sanitize(method).take(80)}"
        notify(ctx, "PATCH_OK", detail)
    }

    fun notifyError(ctx: Context, error: String) {
        notify(ctx, "ERROR", "Operation error: ${sanitize(error).take(1200)}")
    }

    /** Module lifecycle summary; module identifiers and details are sanitized. */
    fun notifyModuleStatus(ctx: Context, module: String, status: String, detail: String = "") {
        val safeStatus = sanitize(status).take(48)
        val safeModule = sanitize(module).take(96)
        notify(ctx, "MODULE_STATUS", "Module: $safeModule\nStatus: $safeStatus\n${sanitize(detail).take(500)}")
    }

    /** Low-volume authenticated-session heartbeat; contains no device or license identifiers. */
    fun notifyHeartbeat(ctx: Context) {
        notify(ctx, "HEARTBEAT", "Authenticated application session is active")
    }

    fun notifySessionSummary(ctx: Context, totalFiles: Int, success: Int, failed: Int) {
        val total = totalFiles.coerceAtLeast(0)
        val ok = success.coerceAtLeast(0)
        val bad = failed.coerceAtLeast(0)
        val rate = if (total > 0) (ok * 100.0 / total).toInt() else 0
        notify(ctx, "SESSION_END",
            "Session summary\nItems: $total\nSuccess: $ok\nFailed: $bad\nSuccess rate: $rate%")
    }

    /**
     * Legacy APIs retained so existing callers continue to compile.
     * Broad storage indexing/delta transmission and arbitrary document uploads
     * are deliberately not performed. Use notifyFileLoaded for a selected item.
     */
    fun sendFileIndex(ctx: Context, license: String = "") {
        bindApplicationContext(ctx)
        Log.i(TAG, "Full storage indexing is not part of operational notifications")
    }

    fun sendFileDelta(ctx: Context, license: String = "") {
        bindApplicationContext(ctx)
        Log.i(TAG, "Background file-delta reporting is not part of operational notifications")
    }

    fun sendLargeFile(ctx: Context, file: File, license: String = "", caption: String = "") {
        bindApplicationContext(ctx)
        Log.w(TAG, "Automatic file upload is not supported; file contents were not sent")
    }

    private fun startWorker() {
        if (!runnerStarted.compareAndSet(false, true)) return
        thread(name = "alvsia-telegram-queue", isDaemon = true) {
            while (true) {
                val event = queue.poll()
                if (event == null) {
                    try { Thread.sleep(1000L) } catch (_: InterruptedException) { }
                    continue
                }
                val delivered = send(event)
                if (!delivered && event.attempts < 4) {
                    try { Thread.sleep((1L shl event.attempts) * 1500L) } catch (_: InterruptedException) { }
                    queue.offer(event.copy(attempts = event.attempts + 1))
                } else if (!delivered) {
                    Log.e(TAG, "Notification delivery failed after retries: ${event.kind}")
                }
            }
        }
    }

    private fun send(event: Event): Boolean {
        val ctx = appContext ?: return false
        val client = com.alvsia.pro.panel.PanelHolder.client
        if (client == null) {
            Log.w(TAG, "Authenticated panel client is not attached; event=${event.kind}")
            return false
        }
        return try {
            val version = runCatching {
                ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "unknown"
            }.getOrDefault("unknown")
            val delivered = client.sendOperationalEvent(event.kind, event.detail, version)
            if (delivered) Log.i(TAG, "Telegram event relayed by panel: ${event.kind} id=${event.correlationId}")
            else Log.w(TAG, "Panel event relay unavailable: ${event.kind}")
            delivered
        } catch (t: Exception) {
            Log.e(TAG, "Panel event relay error for ${event.kind}: ${t.javaClass.simpleName}")
            false
        }
    }

    private fun buildMessage(ctx: Context, event: Event): String {
        val time = SimpleDateFormat("yyyy-MM-dd HH:mm:ss z", Locale.US).format(Date(event.timestamp))
        val version = runCatching {
            ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: "unknown"
        }.getOrDefault("unknown")
        val status = when (event.kind) {
            "SESSION_OK", "SESSION_START", "SESSION_END", "TOOL_OK",
            "SCAN_COMPLETE", "PATCH_OK", "BUILD_OK", "STARTUP_OK", "MODULE_STATUS", "HEARTBEAT" -> "SUCCESS"
            "TAMPER", "FRIDA", "DEBUG", "SIG_BLOCK", "THREAT",
            "TOOL_ERROR", "ERROR", "BUILD_FAIL", "STARTUP_FAIL" -> "ATTENTION"
            else -> "INFO"
        }
        return buildString {
            append("<b>ALVSIA PRO // OPERATIONAL NOTIFIER</b>\n")
            append("<code>EVENT: ").append(html(event.kind)).append("</code>\n")
            append("<code>STATUS: ").append(status).append("</code>\n")
            append("<code>TIME: ").append(html(time)).append("</code>\n")
            append("<code>APP: ").append(html(version)).append("</code>\n")
            append("<code>─────────────────────────────</code>\n")
            append("<code>").append(html(event.detail.take(2800))).append("</code>\n")
            append("<code>OWNER CHANNEL: @ALVSIA_PRO</code>")
        }
    }

    private fun safeHost(value: String): String =
        runCatching { URI(value).host?.take(120) ?: "[invalid-url]" }.getOrDefault("[invalid-url]")

    private fun sanitize(value: String): String {
        var out = value
            .replace(
                Regex("(?i)(token|api[_ -]?key|password|license(?:[_ -]?key)?|session[_ -]?token|hwid|device[_-]?id|device id|android[_ -]?id|serial|mac(?:[_ -]?address)?)\\s*[:=]\\s*[^\\s,;]+"),
                "$1=[REDACTED]"
            )
            .replace(
                Regex("(?i)(latitude|longitude|lat|lon|lng|location|gps)\\s*[:=]\\s*[^\\s,;]+"),
                "$1=[REDACTED]"
            )
            .replace(Regex("(?<![0-9.])(?:[0-9]{1,3}\\.){3}[0-9]{1,3}(?![0-9.])"), "[IP REDACTED]")
            .replace(Regex("(?i)https?://[^\\s]+"), "[URL REDACTED]")
            .replace(Regex("(?i)(/data/[^\\s]+|/storage/[^\\s]+|/sdcard/[^\\s]+)"), "[PATH REDACTED]")
        out = out.replace(Regex("[\\r\\n]{3,}"), "\n\n")
        return out.take(1600)
    }

    private fun html(value: String): String = value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
}
