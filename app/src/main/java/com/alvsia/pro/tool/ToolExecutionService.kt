package com.alvsia.pro.tool

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import java.util.concurrent.atomic.AtomicInteger

/**
 * Keeps the app process at foreground importance while one or more tools are
 * actually executing. The tool engines still run in their existing coroutine/
 * Chaquopy/native paths; this service only protects process priority from
 * low-memory/background reclaim during long operations.
 */
class ToolExecutionService : Service() {
    companion object {
        private const val CHANNEL_ID = "alvsia_tool_execution"
        private const val NOTIFICATION_ID = 5501
        private val activeRuns = AtomicInteger(0)

        fun isActive(): Boolean = activeRuns.get() > 0

        fun begin(context: Context) {
            activeRuns.incrementAndGet()
            val intent = Intent(context, ToolExecutionService::class.java).apply {
                action = "BEGIN"
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (_: Throwable) {
                // Tool execution itself remains independent; priority protection is best-effort.
            }
        }

        fun end(context: Context) {
            val remaining = activeRuns.updateAndGet { current -> (current - 1).coerceAtLeast(0) }
            if (remaining == 0) {
                try { context.stopService(Intent(context, ToolExecutionService::class.java)) } catch (_: Throwable) {}
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("ALVSIA PRO")
            .setContentText("Tool process sedang berjalan")
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setOngoing(true)
            .setCategory(Notification.CATEGORY_PROGRESS)
            .setOnlyAlertOnce(true)
            .build()
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        } catch (_: Throwable) {
            stopSelf()
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_NOT_STICKY

    override fun onDestroy() {
        activeRuns.set(0)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    "ALVSIA tool execution",
                    NotificationManager.IMPORTANCE_LOW
                )
            )
        }
    }
}
