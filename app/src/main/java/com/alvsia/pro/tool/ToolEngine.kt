package com.alvsia.pro.tool


import android.content.Context
import com.alvsia.pro.sec.SessionGate
import com.alvsia.pro.asset.AssetVault
import android.net.Uri
// Chaquopy imported via PythonBridgeRunner reflection — no direct compile-time dep
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

class ToolEngine(private val context: Context) {
    companion object { const val MAX_DIRECT_FILE_BYTES = 5L * 1024L * 1024L * 1024L }
    private val workDir = File(context.filesDir, "work").also { it.mkdirs() }
    private val engineDir = File(context.filesDir, "orchard").also { it.mkdirs() }
    private val jarsDir = File(context.filesDir, "citrus").also { it.mkdirs() }

    fun outputDir(): File {
        WorkPaths.ensureTree()
        return WorkPaths.alvsiaRoot()
    }

    @Volatile private var ramEngine: ByteArray? = null

    /** Keep engine in process memory only ? do not write tool source to storage. */
    fun installEngineBytes(engine: ByteArray?) {
        if (engine == null || engine.isEmpty()) return
        ramEngine?.fill(0)
        ramEngine = engine.copyOf()
        // purge any legacy on-disk engine from older builds
        try {
            File(engineDir, "mango_kernel.py").delete()
            File(engineDir, "__init__.py").delete()
        } catch (_: Exception) {
        }
    }

    fun wipeEngine() {
        ramEngine?.fill(0)
        ramEngine = null
    }

    fun hasRamEngine(): Boolean = ramEngine != null && ramEngine!!.isNotEmpty()

    fun installJarsFromAssets() {
        val jarNames = listOf(
            "unluac_2025_12_23.jar",  // newest — try first
            "unluac_pro.jar",
            "unluac_patched.jar",
            "unluac.jar",
        )

        // Release builds must never fall back to plaintext bundled JARs. Remove legacy
        // copies first so an upgrade cannot keep using a previously materialized fallback.
        if (!com.alvsia.pro.BuildConfig.DEBUG) {
            for (name in jarNames) {
                try { File(jarsDir, name).delete() } catch (_: Exception) { }
            }
        }

        // Sealed assets are the only accepted source in release builds.
        val sealedCount = try {
            AssetVault.materializeJars(context, jarsDir)
        } catch (_: Exception) {
            0
        }
        if (sealedCount > 0 || !com.alvsia.pro.BuildConfig.DEBUG) return

        // Debug/CI only fallback for unsealed development assets.
        for (name in jarNames) {
            val dest = File(jarsDir, name)
            if (dest.exists() && dest.length() > 1000L) continue
            val assetBytes = AssetVault.readAssetBytes(context, "unluac/$name") ?: continue
            try {
                if (assetBytes.size <= 1000) continue
                dest.writeBytes(assetBytes)
                dest.setReadable(true, true)
            } catch (_: Exception) {
            } finally {
                assetBytes.fill(0)
            }
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
    }

    private fun copyUri(uri: Uri, dest: File, onProgress: ((String, Int?) -> Unit)? = null): String? {
        return try {
            val declaredSize = context.contentResolver.query(
                uri, arrayOf(android.provider.OpenableColumns.SIZE), null, null, null
            )?.use { cursor ->
                if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else null
            }
            if (declaredSize != null && declaredSize > MAX_DIRECT_FILE_BYTES) return null

            val digest = MessageDigest.getInstance("SHA-256")
            val source = context.contentResolver.openInputStream(uri) ?: return null
            var total = 0L
            var lastProgressAt = 0L
            var lastProgress = -1
            source.use { ins ->
                val buffer = ByteArray(1024 * 1024)
                FileOutputStream(dest).use { outs ->
                    while (true) {
                        val count = ins.read(buffer)
                        if (count < 0) break
                        total += count
                        if (declaredSize != null && declaredSize > 0L) {
                            val pct = ((total * 100L) / declaredSize).toInt().coerceIn(0, 100)
                            val now = System.currentTimeMillis()
                            // The bytes continue streaming at full speed; only the
                            // visual callback is throttled. This prevents a 1 MiB
                            // callback cadence from flooding Compose for multi-GB files.
                            if (pct != lastProgress || now - lastProgressAt >= 120L) {
                                onProgress?.invoke("STAGING INPUT", pct)
                                lastProgress = pct
                                lastProgressAt = now
                            }
                        }
                        if (total > MAX_DIRECT_FILE_BYTES) {
                            throw IllegalArgumentException("direct file import exceeds 5 GB")
                        }
                        digest.update(buffer, 0, count)
                        outs.write(buffer, 0, count)
                    }
                    if (declaredSize != null && declaredSize > 0L) {
                        onProgress?.invoke("STAGING INPUT", 100)
                    }
                    outs.flush()
                    outs.fd.sync()
                }
            }
            if (dest.isFile && dest.length() > 0) {
                digest.digest().joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
            } else null
        } catch (_: Exception) {
            try { dest.delete() } catch (_: Exception) { }
            null
        }
    }

    private fun stageInput(uri: Uri?, moduleId: Int, taskId: String, onProgress: ((String, Int?) -> Unit)? = null): Pair<String, List<String>> {
        val notes = mutableListOf<String>()
        if (uri == null) return "" to notes
        val nameHint = uri.lastPathSegment?.substringAfterLast('/') ?: "input.bin"
        val safe = nameHint.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "input.bin" }
        val declaredSize = context.contentResolver.query(
            uri, arrayOf(android.provider.OpenableColumns.SIZE), null, null, null
        )?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else null
        }
        if (declaredSize != null && declaredSize > MAX_DIRECT_FILE_BYTES) {
            notes.add("X Selected file exceeds the 5 GB per-file import limit")
            return "" to notes
        }
        // All stages in one Smart Engine task share the same immutable IN snapshot.
        // Reusing it avoids copying a multi-GB source once per internal implementation.
        val snapshot = File(WorkPaths.taskModuleIn(taskId, moduleId), safe)
        if (snapshot.isFile && snapshot.length() > 0L) {
            val snapshotHash = try { sha256(snapshot) } catch (_: Exception) { "" }
            if (snapshotHash.isNotBlank()) {
                notes.add("OK INPUT reused from same Smart Engine task -> ${snapshot.absolutePath}")
                notes.add("size ${snapshot.length()} bytes")
                notes.add("SHA-256 ${snapshotHash}")
                notes.add("OK all pipeline stages share the verified immutable input snapshot")
                onProgress?.invoke("INPUT VERIFIED", null)
                return snapshot.absolutePath to notes
            }
        }
        val staged = File(WorkPaths.taskModuleWork(taskId, moduleId), "in_${System.currentTimeMillis()}_$safe")
        onProgress?.invoke("STAGING INPUT", 0)
        val sourceHash = copyUri(uri, staged, onProgress)
        if (sourceHash == null) {
            notes.add("X Failed to read selected file or per-file 5 GB limit was exceeded")
            return "" to notes
        }
        val stagedHash = try { sha256(staged) } catch (_: Exception) { "" }
        if (stagedHash.isBlank() || stagedHash != sourceHash) {
            try { staged.delete() } catch (_: Exception) { }
            notes.add("X INPUT integrity check failed; staged bytes do not match source stream")
            return "" to notes
        }
        // Also copy a snapshot under IN/ and verify it byte-for-byte.
        try {
            val snap = File(WorkPaths.taskModuleIn(taskId, moduleId), safe)
            staged.copyTo(snap, overwrite = true)
            val snapshotHash = sha256(snap)
            if (snapshotHash != sourceHash) {
                try { snap.delete() } catch (_: Exception) { }
                notes.add("X INPUT snapshot integrity check failed")
                return "" to notes
            }
            notes.add("OK INPUT staged -> ${snap.absolutePath}")
        } catch (_: Exception) {
            notes.add("OK INPUT staged (work only) -> ${staged.absolutePath}")
        }
        notes.add("size ${staged.length()} bytes")
        notes.add("SHA-256 ${sourceHash}")
        notes.add("OK INPUT source/staged bytes verified identical")
        onProgress?.invoke("INPUT VERIFIED", null)
        return staged.absolutePath to notes
    }

    /**
     * Inline config forms write to the compatibility WORK/ directory.
     * Task-isolated execution must copy only the selected subtool's declared
     * settings into TASKS/<id>/WORK before the Python bridge starts.
     */
    private fun stageTaskConfigs(taskId: String, subId: String, lines: MutableList<String>): Boolean {
        val configs = subToolConfig(subId)
        if (configs.isEmpty()) return true

        val taskWork = File(WorkPaths.taskRoot(taskId), "WORK").also { it.mkdirs() }
        val legacyWork = WorkPaths.dirWork()
        var valid = true

        configs.mapNotNull { it.workFileName?.takeIf { name -> name.isNotBlank() } }
            .distinct()
            .forEach { name ->
                if (name == "." || name == ".." || name.any { it == '/' || it == 92.toChar() }) {
                    lines.add("X CONFIG invalid work-file name")
                    valid = false
                    return@forEach
                }
                val source = File(legacyWork, name)
                val destination = File(taskWork, name)
                val required = configs.filter { it.workFileName == name }.any { it.required }

                if (!source.isFile) {
                    destination.delete()
                    if (required) {
                        lines.add("X CONFIG missing: WORK/$name")
                        valid = false
                    } else {
                        lines.add("NOTE optional config not supplied: $name")
                    }
                    return@forEach
                }
                if (source.length() > 1_048_576L) {
                    lines.add("X CONFIG too large: WORK/$name (limit 1 MiB)")
                    valid = false
                    return@forEach
                }
                try {
                    source.copyTo(destination, overwrite = true)
                    if (!destination.isFile || !source.readBytes().contentEquals(destination.readBytes())) {
                        destination.delete()
                        lines.add("X CONFIG integrity check failed: WORK/$name")
                        valid = false
                    } else {
                        lines.add("OK CONFIG staged -> WORK/$name")
                    }
                } catch (failure: Throwable) {
                    destination.delete()
                    lines.add("X CONFIG staging failed: $name (${failure.javaClass.simpleName})")
                    valid = false
                }
            }
        return valid
    }

    fun run(toolId: Int, inputUri: Uri?, extraName: String?, taskId: String = "standalone_${System.nanoTime()}"): List<String> {
        try {
            SessionGate.allowTools(context)
        } catch (e: SecurityException) {
            val reason = e.message?.removePrefix("BLOCKED:") ?: "gate_fail"
            return listOf("X Session blocked: $reason — re-login required")
        }
        // Pre-tool permission check (zero-confirmation: no app-side dialog)
        if (com.alvsia.pro.sec.PermissionManager.isBlocked(context, toolId)) {
            val summary = com.alvsia.pro.sec.PermissionManager.statusSummary(context, toolId)
            return listOf(
                "X Permissions BLOCKED for tool $toolId",
                "status: $summary",
                "Grant the missing permission(s) via system Settings and retry."
            )
        }
        return runSub(toolId, "mod_$toolId", inputUri, extraName, taskId = taskId)
    }

    fun runSub(moduleId: Int, subId: String, inputUri: Uri?, extraName: String?, onProgress: ((String, Int?) -> Unit)? = null, taskId: String = "standalone_${System.nanoTime()}"): List<String> {
        try {
            SessionGate.allowTools(context)
        } catch (e: SecurityException) {
            val reason = e.message?.removePrefix("BLOCKED:") ?: "gate_fail"
            return listOf("X Session blocked: $reason — re-login required")
        }
        // Pre-tool permission check (zero-confirmation: no app-side dialog)
        if (com.alvsia.pro.sec.PermissionManager.isBlocked(context, moduleId)) {
            val summary = com.alvsia.pro.sec.PermissionManager.statusSummary(context, moduleId)
            return listOf(
                "X Permissions BLOCKED for module $moduleId",
                "status: $summary",
                "Grant the missing permission(s) via system Settings and retry."
            )
        }
        WorkPaths.bindApp(context)
        WorkPaths.readme(context)
        WorkPaths.ensureTree()
        installJarsFromAssets()

        val lines = mutableListOf<String>()
        onProgress?.invoke("PREPARING", null)
        lines.add("> ${SubMenus.title(moduleId)} | $subId")
        lines.add("PIPELINE IN -> WORK -> OUT")

        if (!stageTaskConfigs(taskId, subId, lines)) {
            lines.add("X CONFIGURATION FAILED: required settings were not staged; engine was not started")
            return lines
        }

        val (inputPath, stageNotes) = stageInput(inputUri, moduleId, taskId, onProgress)
        lines.addAll(stageNotes)

        // Bridge first for all modules; native fallback below
        onProgress?.invoke("ENGINE PROCESSING", null)

        if (inputPath.isEmpty() && needsInput(moduleId, subId)) {
            lines.add("X No input file ? use SELECT FILE")
            lines.add("hint: output folder ${WorkPaths.taskModuleOut(taskId, moduleId).absolutePath}")
            return lines
        }

        // Smart Asset Engine stays local and isolated from the Python bridge.
        if (moduleId == 20) {
            onProgress?.invoke("SMART ASSET ANALYSIS", null)
            lines.addAll(SmartAssetEngine.run(subId, inputPath, taskId))
            return lines
        }

        try {
            File(WorkPaths.taskRoot(taskId), "sub_cmd.txt").writeText(subId)
        } catch (_: Exception) {
        }

        // All Lua operations now enter the single Smart Lua Python mechanism.
        // The bridge owns detection, provider selection, validation and fallback;
        // this Kotlin layer only stages/isolates the task and reports progress.

        // Bridge for heavier modules
        try {
            if (PythonBridgeRunner.isReady()) {
                // Inject session flag into Python env before calling bridge
                if (SessionGate.sessionOk) {
                    PythonBridgeRunner.setEnv("ALVSIA_APK_SESSION", "1")
                    PythonBridgeRunner.setEnv("ALVSIA_SEALED_RUNTIME", "1")
                } else {
                    PythonBridgeRunner.clearEnv("ALVSIA_APK_SESSION")
                    PythonBridgeRunner.clearEnv("ALVSIA_SOFT_AUTH")
                }
                val (bridgeOk, bridgeLines) = PythonBridgeRunner.runBridge(
                    moduleId = moduleId,
                    subId = subId,
                    inputPath = inputPath,
                    extraName = null,
                    workDirPath = WorkPaths.taskRoot(taskId).absolutePath,
                    jarsDirPath = jarsDir.absolutePath
                )
                lines.addAll(bridgeLines)
                mirrorMsvToOut(moduleId, taskId, lines)
                if (!bridgeOk) {
                    lines.add("X OUT -> operation failed; see engine diagnostics above")
                } else {
                    lines.add("OK OUT -> ${WorkPaths.taskModuleOut(taskId, moduleId).absolutePath}")
                }
                return lines
            } else {
                lines.add("... Python runtime not ready -> native fallback")
                lines.add("... Chaquopy diagnostic: ${PythonBridgeRunner.startupDiagnostic()}")
            }
        } catch (e: Exception) {
            lines.add("... bridge: ${e.message ?: e.javaClass.simpleName}")
            lines.add("... native fallback")
        }

        // A failed decompile must never fall through to the generic native
        // fallback, which may only copy the selected bytecode into OUT/.
        // Keep the original input in IN/ and report a truthful failure instead.
        if (subId == "lua_decompile" || subId.contains("unluac")) {
            lines.add("X DECOMPILE FAILED: no decompiler produced validated Lua source")
            lines.add("Input preserved under IN/; no fake .lua output was created")
            lines.add("Inspect the input-format/header diagnostic above; no source bytes were guessed or patched.")
            return lines
        }

        // Only route to native implementations that actually match the selected module.
        onProgress?.invoke("NATIVE PROCESSING", null)
        // Older routing sent PAK Compact to OBB extraction, Frida to hashing, and
        // Export Report to string scanning whenever Chaquopy was unavailable.
        when {
            moduleId == 7 && subId == "clear_work" -> {
                try {
                    WorkPaths.taskRoot(taskId).deleteRecursively()
                    WorkPaths.taskRoot(taskId).mkdirs()
                    lines.add("OK workspace cleared (native)")
                } catch (e: Exception) {
                    lines.add("X workspace clear failed: ${e.message ?: e.javaClass.simpleName}")
                }
                return lines
            }
            moduleId == 4 -> return when (subId) {
                "obb_info", "obb_unzip" -> lines + runObb(subId, inputPath, taskId)
                "obb_rezip" -> lines + runObbRepack(subId, inputPath, taskId)
                else -> lines + listOf("X Unsupported OBB subtool in native fallback: $subId")
            }
            moduleId == 6 -> return when (subId) {
                "string_scan" -> lines + runStrings(subId, inputPath, taskId)
                "hash_scan" -> lines + runHash(subId, inputPath, taskId)
                else -> lines + listOf("X Unsupported scan subtool in native fallback: $subId")
            }
            moduleId == 8 && inputPath.isNotEmpty() -> {
                val input = File(inputPath)
                val report = File(WorkPaths.taskModuleOut(taskId, 8), "report_${input.name}_${System.currentTimeMillis()}.txt")
                return try {
                    val sha256 = digest(input, "SHA-256")
                    report.writeText(
                        "ALVSIA FILE REPORT\nname=${input.name}\npath=${input.absolutePath}\nsize=${input.length()}\nsha256=$sha256\n",
                        Charsets.UTF_8
                    )
                    lines.add("OK OUTPUT -> ${report.absolutePath}")
                    lines
                } catch (e: Exception) {
                    lines.add("X report failed: ${e.message ?: e.javaClass.simpleName}")
                    lines
                }
            }
        }

        return lines + nativeFallback(moduleId, subId, inputPath, extraName, taskId)
    }

    private fun needsInput(moduleId: Int, subId: String): Boolean {
        // Only these actions are designed to run without a selected input file.
        // Decrypt (13), String Recover (15), and Export Report (8) all require input.
        if (moduleId == 7 && subId == "clear_work") return false
        return subId !in setOf("frida_js_dump", "frida_spawn", "xor_batch", "xor_selftest", "dec_selftest")
    }

    private fun mirrorMsvToOut(moduleId: Int, taskId: String, lines: MutableList<String>) {
        try {
            val msv = File(context.filesDir, "MSV_WORK")
            if (!msv.exists()) return
            val dest = WorkPaths.taskModuleOut(taskId, moduleId)
            msv.walkTopDown().maxDepth(4).forEach { f ->
                if (f.isFile && f.length() > 0 && f.length() < 80_000_000) {
                    val rel = f.relativeTo(msv).path
                    val out = File(dest, rel)
                    out.parentFile?.mkdirs()
                    try {
                        f.copyTo(out, overwrite = true)
                    } catch (_: Exception) {
                    }
                }
            }
            lines.add("OK mirrored MSV_WORK -> ${dest.absolutePath}")
        } catch (e: Exception) {
            lines.add("... mirror skip: ${e.message}")
        }
    }

    // ?? Phase 2 proof: HASH ??
    private fun runHash(subId: String, inputPath: String, taskId: String): List<String> {
        val lines = mutableListOf<String>()
        if (inputPath.isEmpty()) {
            lines.add("X Select a file first")
            return lines
        }
        val f = File(inputPath)
        val outDir = WorkPaths.taskModuleOut(taskId, 6)
        try {
            val md5 = digest(f, "MD5")
            val sha1 = digest(f, "SHA-1")
            val sha256 = digest(f, "SHA-256")
            when (subId) {
                "hash_sha256" -> {
                    lines.add("SHA-256  $sha256")
                    val out = File(outDir, "sha256_${f.name}.txt")
                    out.writeText("file=${f.name}\nsize=${f.length()}\nSHA-256=$sha256\n")
                    lines.add("OK OUTPUT -> ${out.absolutePath}")
                }
                "hash_map" -> {
                    val parent = f.parentFile
                    val report = File(outDir, "hashmap_${System.currentTimeMillis()}.txt")
                    val sb = StringBuilder()
                    sb.appendLine("# hash map")
                    var n = 0
                    parent?.listFiles()?.filter { it.isFile }?.take(200)?.forEach { file ->
                        val h = digest(file, "SHA-256")
                        sb.appendLine("${file.name}\t${file.length()}\t$h")
                        n++
                    }
                    report.writeText(sb.toString())
                    lines.add("OK hashed $n files")
                    lines.add("OK OUTPUT -> ${report.absolutePath}")
                }
                else -> {
                    lines.add("MD5     $md5")
                    lines.add("SHA-1   $sha1")
                    lines.add("SHA-256 $sha256")
                    lines.add("size    ${f.length()} bytes")
                    val out = File(outDir, "hash_${f.name}.txt")
                    out.writeText(
                        "file=${f.name}\nsize=${f.length()}\nMD5=$md5\nSHA-1=$sha1\nSHA-256=$sha256\n"
                    )
                    lines.add("OK OUTPUT -> ${out.absolutePath}")
                }
            }
        } catch (e: Exception) {
            lines.add("X ${e.message ?: "hash failed"}")
        }
        return lines
    }

    private fun digest(f: File, algo: String): String {
        val md = MessageDigest.getInstance(algo)
        FileInputStream(f).use { ins ->
            val buf = ByteArray(8192)
            while (true) {
                val n = ins.read(buf)
                if (n <= 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    // ?? Phase 2 proof: OBB / ZIP ??
    private fun runObb(subId: String, inputPath: String, taskId: String): List<String> {
        val lines = mutableListOf<String>()
        if (inputPath.isEmpty()) {
            lines.add("X Select an .obb / .zip file first")
            return lines
        }
        val f = File(inputPath)
        val outDir = WorkPaths.taskModuleOut(taskId, 4)
        when (subId) {
            "obb_info" -> {
                lines.addAll(zipInfo(f, outDir))
            }
            "obb_antireset" -> {
                lines.addAll(zipExtract(f, File(outDir, "antireset_${stripExt(f.name)}")))
                lines.add("hint: anti-reset helpers extracted if zip-based OBB")
            }
            else -> {
                // obb_unzip default
                lines.addAll(zipExtract(f, File(outDir, "unpack_${stripExt(f.name)}")))
            }
        }
        return lines
    }

    private fun runObbRepack(subId: String, inputPath: String, taskId: String): List<String> {
        val lines = mutableListOf<String>()
        if (inputPath.isEmpty()) {
            lines.add("X Select source file / folder marker")
            return lines
        }
        val f = File(inputPath)
        val outDir = WorkPaths.taskModuleOut(taskId, 4)
        try {
            // If input is zip/obb, re-copy as staged repack baseline
            val dest = File(outDir, "repack_${f.name}")
            f.copyTo(dest, overwrite = true)
            lines.add("OK staged repack baseline -> ${dest.absolutePath}")
            lines.add("hint: edit unpacked tree under OUT/OBB then re-run with tools as needed")
        } catch (e: Exception) {
            lines.add("X ${e.message}")
        }
        return lines
    }

    private fun zipInfo(f: File, outDir: File): List<String> {
        val lines = mutableListOf<String>()
        try {
            ZipFile(f).use { zf ->
                var files = 0
                var dirs = 0
                var total = 0L
                val en = zf.entries()
                val index = StringBuilder()
                index.appendLine("# ${f.name} size=${f.length()}")
                while (en.hasMoreElements()) {
                    val e = en.nextElement()
                    if (e.isDirectory) dirs++ else {
                        files++
                        total += e.size
                    }
                    index.appendLine("${e.name}\t${e.size}")
                }
                lines.add("entries file=$files dir=$dirs")
                lines.add("uncompressed ~$total bytes")
                val rep = File(outDir, "info_${f.name}.txt")
                rep.writeText(index.toString())
                lines.add("OK OUTPUT -> ${rep.absolutePath}")
            }
        } catch (e: Exception) {
            lines.add("X not a zip/obb or corrupt: ${e.message}")
            lines.add("size ${f.length()} ? raw file kept under IN/")
        }
        return lines
    }

    /** Resolve archive paths before writing; reject traversal, absolute paths, and symlink escapes. */
    private fun safeZipTarget(root: File, entryName: String): File? {
        if (entryName.isBlank() || entryName.indexOf('\u0000') >= 0) return null
        return try {
            val canonicalRoot = root.canonicalFile
            val target = File(canonicalRoot, entryName).canonicalFile
            val prefix = canonicalRoot.path + File.separator
            if (target.path.startsWith(prefix)) target else null
        } catch (_: Exception) {
            null
        }
    }

    private fun zipExtract(f: File, dest: File): List<String> {
        val lines = mutableListOf<String>()
        dest.mkdirs()
        var count = 0
        try {
            ZipFile(f).use { zf ->
                val en = zf.entries()
                while (en.hasMoreElements()) {
                    val e = en.nextElement()
                    val out = safeZipTarget(dest, e.name)
                    if (out == null) {
                        lines.add("WARN skipped unsafe archive path")
                        continue
                    }
                    if (e.isDirectory) {
                        out.mkdirs()
                    } else {
                        out.parentFile?.mkdirs()
                        zf.getInputStream(e).use { ins ->
                            FileOutputStream(out).use { outs -> ins.copyTo(outs) }
                        }
                        count++
                    }
                }
            }
            lines.add("OK extracted $count files")
            lines.add("OK OUTPUT -> ${dest.absolutePath}")
        } catch (e: Exception) {
            // try ZipInputStream fallback
            try {
                count = 0
                ZipInputStream(BufferedInputStream(FileInputStream(f))).use { zis ->
                    var entry = zis.nextEntry
                    while (entry != null) {
                        val out = safeZipTarget(dest, entry.name)
                        if (out == null) {
                            lines.add("WARN skipped unsafe archive path")
                        } else if (entry.isDirectory) out.mkdirs()
                        else {
                            out.parentFile?.mkdirs()
                            FileOutputStream(out).use { outs -> zis.copyTo(outs) }
                            count++
                        }
                        zis.closeEntry()
                        entry = zis.nextEntry
                    }
                }
                lines.add("OK extracted $count files (stream)")
                lines.add("OK OUTPUT -> ${dest.absolutePath}")
            } catch (e2: Exception) {
                lines.add("X extract failed: ${e.message}")
                lines.add("... ${e2.message}")
            }
        }
        return lines
    }

    // ?? Phase 2 proof: STRINGS ??
    private fun runStrings(subId: String, inputPath: String, taskId: String): List<String> {
        val lines = mutableListOf<String>()
        if (inputPath.isEmpty()) {
            lines.add("X Select a binary / package file first")
            return lines
        }
        val f = File(inputPath)
        val outDir = WorkPaths.taskModuleOut(taskId, 6)
        val minLen = if (subId == "str_filter") 4 else 4
        try {
            val found = extractAsciiStrings(f, minLen)
            lines.add("OK strings found: ${found.size} (minLen=$minLen)")
            val out = File(outDir, "strings_${stripExt(f.name)}.txt")
            out.writeText(found.joinToString("\n"))
            lines.add("OK OUTPUT -> ${out.absolutePath}")
            found.take(12).forEach { lines.add("  | ${it.take(80)}") }
            if (found.size > 12) lines.add("  ... ${found.size - 12} more in file")
        } catch (e: Exception) {
            lines.add("X ${e.message}")
        }
        return lines
    }

    private fun extractAsciiStrings(f: File, minLen: Int): List<String> {
        val out = mutableListOf<String>()
        val cur = StringBuilder()
        FileInputStream(f).use { ins ->
            val buf = ByteArray(8192)
            while (true) {
                val n = ins.read(buf)
                if (n <= 0) break
                for (i in 0 until n) {
                    val c = buf[i].toInt() and 0xFF
                    if (c in 32..126) {
                        cur.append(c.toChar())
                    } else {
                        if (cur.length >= minLen) out.add(cur.toString())
                        cur.setLength(0)
                    }
                }
            }
        }
        if (cur.length >= minLen) out.add(cur.toString())
        return out.distinct()
    }

    private fun stripExt(name: String): String {
        val i = name.lastIndexOf('.')
        return if (i > 0) name.substring(0, i) else name
    }

    private fun nativeFallback(
        moduleId: Int,
        subId: String,
        inputPath: String,
        extraName: String?,
        taskId: String
    ): List<String> {
        val lines = mutableListOf<String>()
        when (moduleId) {
            7 -> {
                try {
                    WorkPaths.taskRoot(taskId).deleteRecursively()
                    WorkPaths.taskRoot(taskId).mkdirs()
                    lines.add("OK workspace cleared (native)")
                } catch (e: Exception) {
                    lines.add("X workspace clear failed: ${e.message ?: e.javaClass.simpleName}")
                }
            }
            4 -> return when (subId) {
                "obb_info", "obb_unzip" -> runObb(subId, inputPath, taskId)
                "obb_rezip" -> runObbRepack(subId, inputPath, taskId)
                else -> listOf("X Unsupported OBB subtool in native fallback: $subId")
            }
            6 -> return when (subId) {
                "string_scan" -> runStrings(subId, inputPath, taskId)
                "hash_scan" -> runHash(subId, inputPath, taskId)
                else -> listOf("X Unsupported scan subtool in native fallback: $subId")
            }
            else -> {
                lines.add("X Python bridge unavailable; this module was not executed.")
                lines.add("Chaquopy: ${PythonBridgeRunner.startupDiagnostic()}")
                lines.add("No placeholder output was created. Retry after the Python runtime is ready.")
            }
        }
        return lines
    }
}
