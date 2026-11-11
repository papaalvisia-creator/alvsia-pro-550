package com.alvsia.pro.tool

import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.mutableStateListOf
import java.util.concurrent.ConcurrentHashMap

enum class TaskStatus { RUNNING, COMPLETED, ERROR }

data class LiveTask(
    val id: String,
    val moduleId: Int,
    val subId: String,
    val title: String,
    val startedAt: Long,
    val fileLabel: String = "",
    val fileSizeBytes: Long? = null,
    val status: TaskStatus = TaskStatus.RUNNING,
    val progress: Int? = null,
    val stage: String = "STARTING",
    val logs: List<String> = emptyList(),
    val updatedAt: Long = startedAt
)

object TaskCenter {
    val tasks = mutableStateListOf<LiveTask>()

    fun start(moduleId: Int, subId: String, title: String, fileLabel: String = "", fileSizeBytes: Long? = null): String {
        val id = "${moduleId}_${subId}_${System.nanoTime()}"
        tasks.add(
            0,
            LiveTask(
                id = id,
                moduleId = moduleId,
                subId = subId,
                title = title,
                startedAt = System.currentTimeMillis(),
                fileLabel = fileLabel,
                fileSizeBytes = fileSizeBytes
            )
        )
        return id
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    // Engine callbacks can arrive once per chunk. Coalesce progress-only UI updates
    // so a multi-GB import cannot enqueue thousands of Compose mutations and exhaust
    // the main-thread queue. This does not alter the underlying work or percentage;
    // it only reduces redraw frequency.
    private val lastPostedProgressAt = ConcurrentHashMap<String, Long>()

    fun update(
        id: String,
        stage: String? = null,
        progress: Int? = null,
        logs: List<String>? = null,
        clearProgress: Boolean = false
    ) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            // Engine callbacks arrive from Dispatchers.IO. Never mutate the
            // Compose-backed task list from an engine/background thread.
            // Progress-only callbacks are coalesced to protect the UI from a
            // multi-GB staging stream producing thousands of main-thread posts.
            if (progress != null && logs == null && !clearProgress) {
                val now = System.currentTimeMillis()
                var shouldPost = false
                lastPostedProgressAt.compute(id) { _, previous ->
                    if (previous == null || now - previous >= 120L) {
                        shouldPost = true
                        now
                    } else {
                        previous
                    }
                }
                if (!shouldPost) return
            }
            mainHandler.post {
                update(id, stage, progress, logs, clearProgress)
            }
            return
        }
        val index = tasks.indexOfFirst { it.id == id }
        if (index < 0) return
        val old = tasks[index]
        tasks[index] = old.copy(
            stage = stage ?: old.stage,
            progress = if (clearProgress) null else (progress ?: old.progress),
            logs = logs ?: old.logs,
            updatedAt = System.currentTimeMillis()
        )
    }

    fun complete(id: String, success: Boolean, logs: List<String>) {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            mainHandler.post { complete(id, success, logs) }
            return
        }
        val index = tasks.indexOfFirst { it.id == id }
        if (index < 0) return
        val old = tasks[index]
        lastPostedProgressAt.remove(id)
        tasks[index] = old.copy(
            status = if (success) TaskStatus.COMPLETED else TaskStatus.ERROR,
            progress = if (success) 100 else old.progress,
            stage = if (success) "COMPLETED" else "NEEDS ATTENTION",
            logs = logs,
            updatedAt = System.currentTimeMillis()
        )
    }

    fun find(id: String?): LiveTask? = id?.let { wanted -> tasks.firstOrNull { it.id == wanted } }

    fun activeCount(): Int = tasks.count { it.status == TaskStatus.RUNNING }

    fun clearFinished() {
        tasks.removeAll { it.status != TaskStatus.RUNNING }
    }
}
