package com.alvsia.pro.tool

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import java.io.File

/** Persists previous process-exit diagnostics; never changes runtime behavior. */
object RuntimeExitDiagnostics {
    private const val FILE_NAME = "runtime_exit_diagnostic.txt"
    private var previousHandler: Thread.UncaughtExceptionHandler? = null

    fun installExceptionRecorder(context: Context) {
        try {
            if (previousHandler != null) return
            previousHandler = Thread.getDefaultUncaughtExceptionHandler()
            val delegate = previousHandler
            Thread.setDefaultUncaughtExceptionHandler { thread, error ->
                try {
                    File(context.filesDir, FILE_NAME).writeText(
                        "reason=JAVA_UNCAUGHT_EXCEPTION\n" +
                            "thread=" + thread.name + "\n" +
                            "error=" + error.javaClass.name + ": " + (error.message ?: "") + "\n" +
                            "was_tool_active=" + context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE).getBoolean("tool_active", false) + "\n" +
                            "last_tool=" + context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE).getString("last_tool", "") + "\n",
                        Charsets.UTF_8
                    )
                } catch (_: Throwable) {}
                delegate?.uncaughtException(thread, error)
            }
        } catch (_: Throwable) {}
    }

    fun recordPreviousExit(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return
            val latest = am.getHistoricalProcessExitReasons(context.packageName, 0, 8).firstOrNull() ?: return
            val prefs = context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE)
            val text = buildString {
                appendLine("timestamp=" + latest.timestamp)
                appendLine("reason=" + reasonName(latest.reason) + "(" + latest.reason + ")")
                appendLine("status=" + latest.status)
                appendLine("description=" + latest.description.orEmpty().take(1200))
                appendLine("was_tool_active=" + prefs.getBoolean("tool_active", false))
                appendLine("last_tool=" + prefs.getString("last_tool", ""))
                appendLine("tool_started_at=" + prefs.getLong("tool_started_at", 0L))
            }
            File(context.filesDir, FILE_NAME).writeText(text, Charsets.UTF_8)
        } catch (_: Throwable) {}
    }

    fun markToolStart(context: Context, moduleId: Int, subId: String) {
        try { context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE).edit()
            .putBoolean("tool_active", true).putString("last_tool", "$moduleId:$subId")
            .putLong("tool_started_at", System.currentTimeMillis()).apply()
        } catch (_: Throwable) {}
    }

    fun markToolEnd(context: Context) {
        try { context.getSharedPreferences("runtime_exit", Context.MODE_PRIVATE).edit().putBoolean("tool_active", false).apply() } catch (_: Throwable) {}
    }

    private fun reasonName(reason: Int): String = when (reason) {
        1 -> "EXIT_SELF"; 2 -> "SIGNALED"; 3 -> "LOW_MEMORY"; 4 -> "APP_CRASH";
        5 -> "APP_ANR"; 6 -> "INITIALIZATION_FAILURE"; 7 -> "PERMISSION_CHANGE";
        8 -> "EXCESSIVE_RESOURCE_USAGE"; 9 -> "USER_REQUESTED"; 10 -> "USER_STOPPED";
        else -> "OTHER"
    }
}