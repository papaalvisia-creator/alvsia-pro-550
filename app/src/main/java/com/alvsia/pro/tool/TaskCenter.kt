package com.alvsia.pro.tool

import androidx.compose.runtime.mutableStateListOf

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

    fun update(
        id: String,
        stage: String? = null,
        progress: Int? = null,
        logs: List<String>? = null,
        clearProgress: Boolean = false
    ) {
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
        val index = tasks.indexOfFirst { it.id == id }
        if (index < 0) return
        val old = tasks[index]
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
