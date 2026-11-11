package com.alvsia.pro.tool

import android.content.Context
import android.os.Environment
import java.io.File

object WorkPaths {
    @Volatile private var appFallback: File? = null

    fun bindApp(ctx: Context) {
        if (appFallback == null) {
            appFallback = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "ALVSIA").also { it.mkdirs() }
        }
    }

    fun alvsiaRoot(): File {
        return try {
            val dl = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            val root = File(dl, "ALVSIA")
            if (!root.exists()) root.mkdirs()
            val canUsePublicRoot = try {
                if (!root.isDirectory) {
                    false
                } else {
                    val probe = File.createTempFile(".alvsia-write-probe-", ".tmp", root)
                    probe.delete()
                }
            } catch (_: Exception) {
                false
            }
            if (canUsePublicRoot) root else appFallback ?: root
        } catch (_: Exception) {
            appFallback ?: File("/sdcard/Download/ALVSIA")
        }
    }

    fun dirIn(): File = File(alvsiaRoot(), "IN").also { it.mkdirs() }
    fun dirWork(): File = File(alvsiaRoot(), "WORK").also { it.mkdirs() }
    fun dirOut(): File = File(alvsiaRoot(), "OUT").also { it.mkdirs() }

    fun moduleOut(moduleId: Int): File {
        val name = moduleName(moduleId)
        return File(dirOut(), name).also { it.mkdirs() }
    }

    /**
     * Isolated workspace for one live task. Every concurrent tool run gets its
     * own IN/WORK/OUT tree so switching tools or running another task cannot
     * overwrite an active task's staged bytes or intermediate output.
     */
    fun taskRoot(taskId: String): File {
        val safe = taskId.replace(Regex("[^A-Za-z0-9._-]"), "_").take(160).ifBlank { "task" }
        return File(alvsiaRoot(), "TASKS/$safe").also { it.mkdirs() }
    }

    fun taskModuleOut(taskId: String, moduleId: Int): File {
        val name = moduleName(moduleId)
        return File(taskRoot(taskId), "OUT/$name").also { it.mkdirs() }
    }

    fun taskModuleIn(taskId: String, moduleId: Int): File {
        val name = moduleName(moduleId)
        return File(taskRoot(taskId), "IN/$name").also { it.mkdirs() }
    }

    fun taskModuleWork(taskId: String, moduleId: Int): File {
        val name = moduleName(moduleId)
        return File(taskRoot(taskId), "WORK/$name").also { it.mkdirs() }
    }


    fun moduleIn(moduleId: Int): File {
        val name = moduleName(moduleId)
        return File(dirIn(), name).also { it.mkdirs() }
    }

    fun moduleWork(moduleId: Int): File {
        val name = moduleName(moduleId)
        return File(dirWork(), name).also { it.mkdirs() }
    }

    /** Back-compat for older calls */
    fun moduleDir(moduleId: Int, sub: String = "out"): File {
        return when (sub.lowercase()) {
            "in", "input" -> moduleIn(moduleId)
            "work" -> moduleWork(moduleId)
            else -> moduleOut(moduleId)
        }
    }

    private fun moduleName(moduleId: Int): String = when (moduleId) {
        1, 2, 3 -> "PAK"
        4 -> "OBB"
        5 -> "LUA"
        6 -> "SCAN"
        7 -> "ASSET"
        8 -> "REPORT"
        9 -> "REBRAND"
        10 -> "SO"
        11 -> "FRIDA"
        12 -> "XOR"
        13 -> "DEC"
        14 -> "PAKD"
        15 -> "STR"
        16 -> "LINJ"
        17 -> "AUDIT"
        18 -> "LPROTECT"
        19 -> "ALVSIA_PRIVATE"
        else -> "MISC"
    }

    fun ensureTree() {
        // Create only the three stable roots. Module folders are created lazily
        // by moduleIn/moduleWork/moduleOut when a tool actually needs them.
        // Eagerly creating 57 empty folders on every app/tool start made the
        // user's output workspace noisy and obscured real artifacts.
        dirIn(); dirWork(); dirOut()
    }

    fun readme(ctx: Context) {
        bindApp(ctx)
        ensureTree()
        val f = File(alvsiaRoot(), "README_EN.txt")
        try {
            f.writeText(
                """
                ALVSIA PRO 5.5.2 - modern I/O
                ====================================
                Root: Download/ALVSIA/

                  IN/<MODULE>/    created only when needed
                  WORK/<MODULE>/  created only when needed
                  OUT/<MODULE>/   legacy results, created on demand

                  TASKS/<TASK_ID>/IN/<MODULE>/    verified task input
                  TASKS/<TASK_ID>/WORK/<MODULE>/  isolated task workspace
                  TASKS/<TASK_ID>/OUT/<MODULE>/   final task output

                Output Browser indexes both OUT/ and TASKS/*/OUT/.

                Modules: PAK OBB LUA SCAN ASSET REPORT REBRAND SO FRIDA XOR DEC PAKD STR LINJ AUDIT LPROTECT ALVSIA_PRIVATE

                Key:  @ALVSIA_PRO
                Owner: @ALVSIA_PRO
                """.trimIndent()
            )
        } catch (_: Exception) {
        }
    }
}
