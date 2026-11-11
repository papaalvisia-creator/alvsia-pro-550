package com.alvsia.pro.tool

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import java.io.File

/** Persists previous process-exit diagnostics; never changes runtime behavior. */
object RuntimeExitDiagnostics {
    private const val FILE_NAME = "runtime_exit_diagnostic.txt"
    private const val PREFS = "runtime_exit"
    private const val MAX_TRACE = 8000
    private var previousHandler: Thread.UncaughtExceptionHandler? = null

    fun installExceptionRecorder(context: Context) {
        try {
            if (previousHandler != null) return
            previousHandler = Thread.getDefaultUncaughtExceptionHandler()
            val delegate = previousHandler
            Thread.setDefaultUncaughtExceptionHandler { thread, error ->
                try {
                    val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    val report = buildString {
                        appendLine("ALVSIA CRASH FORENSICS")
                        appendLine("reason=JAVA_UNCAUGHT_EXCEPTION")
                        appendLine("timestamp=" + System.currentTimeMillis())
                        appendLine("thread=" + thread.name)
                        appendLine("error=" + error.javaClass.name + ": " + (error.message ?: ""))
                        appendLine("was_tool_active=" + prefs.getBoolean("tool_active", false))
                        appendLine("last_tool=" + prefs.getString("last_tool", "").orEmpty())
                        appendLine("task_id=" + prefs.getString("task_id", "").orEmpty())
                        appendLine("stage=" + prefs.getString("stage", "").orEmpty())
                        appendLine("progress=" + prefs.getString("progress", "").orEmpty())
                        appendMemory(context, this)
                        appendLine("stack_trace=" + error.stackTraceToString().take(MAX_TRACE))
                    }
                    persist(context, report)
                } catch (_: Throwable) {}
                delegate?.uncaughtException(thread, error)
            }
        } catch (_: Throwable) {}
    }

    fun recordPreviousExit(context: Context): String? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return null
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return null
            val latest = am.getHistoricalProcessExitReasons(context.packageName, 0, 8).firstOrNull() ?: return null
            val prefs = context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE)
            val text = buildString {
                appendLine("ALVSIA CRASH FORENSICS")
                appendLine("timestamp=" + latest.timestamp)
                appendLine("reason=" + reasonName(latest.reason) + "(" + latest.reason + ")")
                appendLine("status=" + latest.status)
                appendLine("description=" + latest.description.orEmpty().take(1200))
                appendLine("was_tool_active=" + prefs.getBoolean("tool_active", false))
                appendLine("last_tool=" + prefs.getString("last_tool", "").orEmpty())
                appendLine("task_id=" + prefs.getString("task_id", "").orEmpty())
                appendLine("stage=" + prefs.getString("stage", "").orEmpty())
                appendLine("progress=" + prefs.getString("progress", "").orEmpty())
                appendLine("tool_started_at=" + prefs.getLong("tool_started_at", 0L))
                appendMemory(context, this)
                appendLine("diagnosis=" + diagnosisFor(latest.reason))
            }
            persist(context, text)
            text
        } catch (_: Throwable) { null }
    }

    fun markToolStart(context: Context, moduleId: Int, subId: String) {
        try { context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE).edit()
            .putBoolean("tool_active", true).putString("last_tool", "$moduleId:$subId")
            .putLong("tool_started_at", System.currentTimeMillis()).apply()
        } catch (_: Throwable) {}
    }

    fun checkpoint(context: Context, moduleId: Int, subId: String, taskId: String?, stage: String?, progress: Int?) {
        try {
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            prefs.edit().putBoolean("tool_active", true).putString("last_tool", "$moduleId:$subId")
                .putString("task_id", taskId.orEmpty()).putString("stage", stage.orEmpty())
                .putString("progress", progress?.toString().orEmpty())
                .putLong("tool_started_at", prefs.getLong("tool_started_at", System.currentTimeMillis())).apply()
            val report = buildString {
                appendLine("ALVSIA LIVE CHECKPOINT")
                appendLine("timestamp=" + System.currentTimeMillis())
                appendLine("module=" + moduleId)
                appendLine("subtool=" + subId)
                appendLine("task_id=" + taskId.orEmpty())
                appendLine("stage=" + stage.orEmpty())
                appendLine("progress=" + (progress?.toString() ?: "LIVE"))
                appendMemory(context, this)
            }
            persist(context, report)
        } catch (_: Throwable) {}
    }

    fun markToolEnd(context: Context) {
        try { context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean("tool_active", false).apply() } catch (_: Throwable) {}
    }

    fun previousExitReport(context: Context): String? = try {
        File(context.filesDir, FILE_NAME).takeIf { it.exists() }?.readText(Charsets.UTF_8)
    } catch (_: Throwable) { null }

    private fun appendMemory(context: Context, out: StringBuilder) {
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
            val mi = ActivityManager.MemoryInfo()
            am?.getMemoryInfo(mi)
            if (am != null) {
                out.appendLine("device_available_ram=" + mi.availMem)
                out.appendLine("device_low_memory=" + mi.lowMemory)
                out.appendLine("device_threshold=" + mi.threshold)
            }
            val rt = Runtime.getRuntime()
            val used = rt.totalMemory() - rt.freeMemory()
            out.appendLine("app_heap_used=" + used)
            out.appendLine("app_heap_max=" + rt.maxMemory())
            out.appendLine("app_heap_free=" + (rt.maxMemory() - used))
        } catch (_: Throwable) {}
    }

    private fun persist(context: Context, text: String) {
        File(context.filesDir, FILE_NAME).writeText(text.take(16000), Charsets.UTF_8)
    }

    private fun diagnosisFor(reason: Int): String = when (reason) {
        2 -> "PROCESS_WAS_SIGNALED; inspect native/OS evidence"
        3 -> "LOW_MEMORY; Android reports process termination under memory pressure"
        4 -> "APP_CRASH; inspect exception/stack trace from previous checkpoint"
        5 -> "APP_ANR; inspect last checkpoint and main-thread work"
        8 -> "EXCESSIVE_RESOURCE_USAGE; inspect memory/CPU/I/O checkpoints"
        else -> "ANDROID_EXIT_REASON_AVAILABLE; correlate checkpoint data"
    }

    private fun reasonName(reason: Int): String = when (reason) {
        1 -> "EXIT_SELF"; 2 -> "SIGNALED"; 3 -> "LOW_MEMORY"; 4 -> "APP_CRASH";
        5 -> "APP_ANR"; 6 -> "INITIALIZATION_FAILURE"; 7 -> "PERMISSION_CHANGE";
        8 -> "EXCESSIVE_RESOURCE_USAGE"; 9 -> "USER_REQUESTED"; 10 -> "USER_STOPPED";
        else -> "OTHER"
    }
}