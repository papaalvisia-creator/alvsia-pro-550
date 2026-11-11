package com.alvsia.pro.tool

import com.alvsia.pro.sec.SessionGate
import com.alvsia.pro.panel.Hwid
import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.concurrent.locks.ReentrantLock

/**
 * Safe reflection-based runner for Chaquopy Python bridge.
 * When Chaquopy is packaged (e.g. in CodeMagic release builds), delegates to
 * alvsia_bridge. When Chaquopy is absent (e.g. in local/test builds),
 * allows clean execution of native fallback without ClassNotFoundException.
 */
object PythonBridgeRunner {
    @Volatile private var startupError: String = "startup not attempted"
    @Volatile private var appContext: Context? = null
    // Chaquopy hosts one process-wide Python runtime. Keep bridge calls single-flight
    // so concurrent tool jobs remain independent at the task layer without racing the
    // same interpreter/native engines and multiplying peak memory usage.
    private val bridgeLock = ReentrantLock()

    fun startupDiagnostic(): String = startupError

    fun isReady(): Boolean = try {
        val pyClass = Class.forName("com.chaquo.python.Python")
        val isStarted = pyClass.getMethod("isStarted").invoke(null) as Boolean
        isStarted
    } catch (_: Throwable) {
        false
    }

    fun startPlatform(app: android.app.Application) {
        appContext = app.applicationContext
        startupError = "startup in progress"
        try {
            val pyClass = Class.forName("com.chaquo.python.Python")
            val isStarted = pyClass.getMethod("isStarted").invoke(null) as Boolean
            if (!isStarted) {
                val platformClass = Class.forName("com.chaquo.python.android.AndroidPlatform")
                val platformInst = platformClass.getConstructor(android.content.Context::class.java).newInstance(app)
                // Chaquopy's Platform type differs by runtime version. Resolve the
                // actual start(Platform) overload from the instantiated AndroidPlatform
                // instead of loading the non-existent PythonPlatform class.
                val startMethod = pyClass.methods.firstOrNull { method ->
                    method.name == "start" &&
                        java.lang.reflect.Modifier.isStatic(method.modifiers) &&
                        method.parameterTypes.size == 1 &&
                        method.parameterTypes[0].isAssignableFrom(platformInst.javaClass)
                } ?: throw NoSuchMethodException(
                    "Python.start(AndroidPlatform) overload not found"
                )
                startMethod.invoke(null, platformInst)
            }
            startupError = if (isReady()) "Chaquopy ready" else "Python class loaded but runtime reports not started"
        } catch (t: Throwable) {
            val cause = t.cause ?: t
            startupError = "${cause.javaClass.simpleName}: ${cause.message ?: "no detail"}".take(240)
        }
    }

    /** Stage the bundled Unluac jar into the Python engine's configured jars directory.
     * The Python fallback only searches jarsDirPath, whereas Android assets are not
     * filesystem paths. Keep this lazy and scoped to the Lua fallback dependency.
     */
    private fun ensureBundledUnluacJar(jarsDirPath: String): String? {
        return try {
            val context = appContext ?: return null
            val dir = File(jarsDirPath)
            if (!dir.exists() && !dir.mkdirs()) return null
            val candidates = listOf("unluac_2025_12_23.jar", "unluac.jar")
            candidates.map { File(dir, it) }.firstOrNull { it.isFile && it.length() > 1000 }?.let {
                return it.absolutePath
            }
            val dest = File(dir, "unluac_2025_12_23.jar")
            context.assets.open("unluac/unluac_2025_12_23.jar").use { source ->
                FileOutputStream(dest).use { output -> source.copyTo(output) }
            }
            if (dest.isFile && dest.length() > 1000) dest.absolutePath else null
        } catch (_: Throwable) {
            null
        }
    }

    /** Explicitly release Chaquopy native Python references before GC/finalization. */
    private fun closePyObjectQuietly(value: Any?) {
        if (value == null) return
        try {
            if (value is AutoCloseable) value.close()
            else value.javaClass.getMethod("close").invoke(value)
        } catch (_: Throwable) {
            // Cleanup must never change the operation result.
        }
    }
    private fun sha256Hex(value: String): String =
        MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }


    /** Verify and install the compact JWT signed by the current Unaux panel. */
    fun installOperationProof(grantToken: String, expectedOperation: String): Boolean {
        bridgeLock.lock()
        var core: Any? = null
        var ultimate: Any? = null
        var coreResult: Any? = null
        var decoded: Any? = null
        return try {
            if (!SessionGate.isSessionAuthorized() || grantToken.split(".").size != 3) return false
            val pyClass = Class.forName("com.chaquo.python.Python")
            if (!(pyClass.getMethod("isStarted").invoke(null) as Boolean)) return false
            val py = pyClass.getMethod("getInstance").invoke(null) ?: return false
            val getModule = pyClass.getMethod("getModule", String::class.java)
            val pyObjectCls = Class.forName("com.chaquo.python.PyObject")
            val callAttr = pyObjectCls.getMethod("callAttr", String::class.java, Array<Any?>::class.java)

            core = getModule.invoke(py, "alvsia_core") ?: return false
            coreResult = callAttr.invoke(core, "_alvsia_install_operation_grant_token",
                arrayOf<Any?>(grantToken, expectedOperation))
            val coreOk = when {
                coreResult is Boolean -> coreResult
                else -> coreResult?.toString()?.trim()?.equals("True", ignoreCase = true) ?: false
            }
            if (!coreOk) return false

            ultimate = getModule.invoke(py, "alvsia_ultimate") ?: return false
            decoded = callAttr.invoke(ultimate, "_alv_install_operation_grant_token",
                arrayOf<Any?>(grantToken, expectedOperation))
            when {
                decoded is Boolean -> decoded
                else -> decoded?.toString()?.trim()?.equals("True", ignoreCase = true) ?: false
            }
        } catch (_: Throwable) {
            false
        } finally {
            closePyObjectQuietly(decoded)
            closePyObjectQuietly(coreResult)
            closePyObjectQuietly(ultimate)
            closePyObjectQuietly(core)
            bridgeLock.unlock()
        }
    }

    fun proofStatus(): String {
        bridgeLock.lock()
        var core: Any? = null
        var result: Any? = null
        return try {
            val pyClass = Class.forName("com.chaquo.python.Python")
            if (!(pyClass.getMethod("isStarted").invoke(null) as Boolean)) return ""
            val py = pyClass.getMethod("getInstance").invoke(null) ?: return ""
            val getModule = pyClass.getMethod("getModule", String::class.java)
            core = getModule.invoke(py, "alvsia_core") ?: return ""
            val pyObjectCls = Class.forName("com.chaquo.python.PyObject")
            val callAttr = pyObjectCls.getMethod("callAttr", String::class.java, Array<Any?>::class.java)
            result = callAttr.invoke(core, "_alvsia_core_active_proof_status", emptyArray<Any?>())
            result?.toString() ?: ""
        } catch (_: Throwable) {
            ""
        } finally {
            closePyObjectQuietly(result)
            closePyObjectQuietly(core)
            bridgeLock.unlock()
        }
    }

    fun runBridge(
        moduleId: Int,
        subId: String,
        inputPath: String,
        extraName: String?,
        workDirPath: String,
        jarsDirPath: String
    ): Pair<Boolean, List<String>> {
        bridgeLock.lock()
        return try {
            runBridgeInternal(moduleId, subId, inputPath, extraName, workDirPath, jarsDirPath)
        } finally {
            bridgeLock.unlock()
        }
    }

    private fun runBridgeInternal(
        moduleId: Int,
        subId: String,
        inputPath: String,
        extraName: String?,
        workDirPath: String,
        jarsDirPath: String
    ): Pair<Boolean, List<String>> {
        try {
            val pyClass = Class.forName("com.chaquo.python.Python")
            val isStarted = pyClass.getMethod("isStarted").invoke(null) as Boolean
            if (!isStarted) return false to listOf("... Python runtime not ready — native fallback")
            val resolvedJarsDir = jarsDirPath.ifBlank {
                File(appContext?.filesDir ?: File("/data/local/tmp"), "jars").absolutePath
            }
            val stagedUnluacJar = ensureBundledUnluacJar(resolvedJarsDir)

            val py = pyClass.getMethod("getInstance").invoke(null) ?: return false to listOf("... Python instance null")
            val getModule = pyClass.getMethod("getModule", String::class.java)

            val pyObjectCls = Class.forName("com.chaquo.python.PyObject")
            val callAttr = pyObjectCls.getMethod("callAttr", String::class.java, Array<Any?>::class.java)

            val token = SessionGate.sessionToken.trim()
            if (!token.matches(Regex("^[0-9A-Fa-f]{64}$"))) {
                return false to listOf("X AUTH: native session token invalid")
            }

            val bridge = getModule.invoke(py, "alvsia_bridge") ?: return false to listOf("... alvsia_bridge unavailable")
            try {
            // Configure the authenticated Python session through a bridge function.
            // This avoids relying on PyObject.get(String), which is not available in
            // some Chaquopy runtimes and caused "PyObject.get" reflection failures.
            // Distinguish a native session-gate rejection from a Python/Chaquopy bridge rejection.
            if (!SessionGate.isTokenCurrent(token)) {
                return false to listOf("X AUTH DIAG: Kotlin SessionGate rejected the current token before Python configuration")
            }
            val context = appContext
                ?: return false to listOf("X AUTH: application context unavailable for device binding")
            val deviceId = Hwid.deviceId(context).trim()
            if (!deviceId.matches(Regex("^[0-9A-Fa-f]{64}$"))) {
                return false to listOf("X AUTH: device identity unavailable for protected-operation binding")
            }
            val configure = callAttr.invoke(
                bridge,
                "configure_runtime",
                arrayOf<Any?>(token, "1")
            )
            // Chaquopy wraps Python bool True as a PyObject whose toString() == "True".
            // Some Chaquopy runtime versions (especially 3.x under AGP 8.x) may unbox
            // the Python bool to a Java Boolean before returning, so also accept
            // java.lang.Boolean(true).  Case-insensitive match guards against any
            // future runtime that returns the lowercase "true".
            val configureOk = when {
                configure == null -> false
                configure is Boolean -> configure
                else -> configure.toString().trim().equals("True", ignoreCase = true)
            }
            if (!configureOk) {
                val returnedType = configure?.javaClass?.simpleName ?: "null"
                val returnedValue = configure?.toString()?.take(80) ?: "null"
                val pythonDiagnostic = try {
                    val diag = callAttr.invoke(bridge, "configure_diagnostic", emptyArray<Any?>())
                    val text = diag?.toString()?.take(180) ?: "diagnostic_unavailable"
                    closePyObjectQuietly(diag)
                    text
                } catch (diagError: Throwable) {
                    "diagnostic_call_failed:" + ((diagError.cause ?: diagError).javaClass.simpleName)
                }
                return false to listOf(
                    "X AUTH DIAG: Kotlin SessionGate accepted token, but Python configure_runtime did not return True",
                    "diagnostic: return_type=$returnedType; return_value=$returnedValue; chaquopy_started=$isStarted; token_shape=64_hex",
                    "Python configure stage: $pythonDiagnostic"
                )
            }
            closePyObjectQuietly(configure)

            // Register the bundled Android ARM64 CLI from nativeLibraryDir.
            // Missing/incompatible binaries are non-fatal: Smart Lua retains its
            // existing engines and reports their diagnostics normally.
            try {
                val nativeLibDir = appContext?.applicationInfo?.nativeLibraryDir
                if (!nativeLibDir.isNullOrBlank()) {
                    val nativeCli = File(nativeLibDir, "libunluac-cli.so")
                    if (nativeCli.isFile && nativeCli.canExecute()) {
                        val configured = callAttr.invoke(
                            bridge,
                            "configure_unluac_rs",
                            arrayOf<Any?>(nativeCli.absolutePath)
                        )
                        closePyObjectQuietly(configured)
                    }
                    val luauCli = File(nativeLibDir, "libluau-decompiler-cli.so")
                    if (luauCli.isFile && luauCli.canExecute()) {
                        val configured = callAttr.invoke(
                            bridge,
                            "configure_luau_decompiler",
                            arrayOf<Any?>(luauCli.absolutePath)
                        )
                        closePyObjectQuietly(configured)
                    }
                }
            } catch (_: Throwable) {
                // Optional engine only; do not block unrelated tools.
            }
            val coreModule = getModule.invoke(py, "alvsia_core")
                ?: return false to listOf("X AUTH: core session-binding helper unavailable")
            try {
            val identityResult = callAttr.invoke(
                coreModule,
                "_alvsia_set_expected_operation_identity",
                arrayOf<Any?>(sha256Hex(token), deviceId)
            )
            val identityOk = when {
                identityResult == null -> false
                identityResult is Boolean -> identityResult
                else -> identityResult.toString().trim().equals("True", ignoreCase = true)
            }
            closePyObjectQuietly(identityResult)
            if (!identityOk) {
                return false to listOf("X AUTH: trusted device/session identity could not be installed")
            }
            // Protected operations require a panel-signed, short-lived RSA grant.
            // Fail closed if the endpoint is missing, the session is invalid, or the
            // Python verifier rejects the proof.
            val grantOperation = OperationGrants.operationFor(moduleId, subId)
                ?: return false to listOf("X AUTH: module/subtool has no Unaux grant mapping")
            val (grantOk, grantDiag) = OperationGrants.obtainAndInstall(grantOperation)
            if (!grantOk) {
                return false to listOf(
                    "X AUTH: Unaux RSA operation grant unavailable",
                    "diagnostic: $grantDiag",
                    "hint: verify /api/operation_grant.php and the configured server key"
                )
            }

            val rawResult = callAttr.invoke(
                bridge,
                "bridge_run_sub",
                arrayOf<Any?>(moduleId, subId, inputPath, extraName ?: "", workDirPath, resolvedJarsDir)
            )
            val log = rawResult?.toString().orEmpty()
            closePyObjectQuietly(rawResult)
            val lines = log.split("\n").filter { it.isNotBlank() }.toMutableList()
            if (stagedUnluacJar != null) lines.add(0, "OK bundled Unluac available: $stagedUnluacJar")
            // Many Python handlers return a structured dict rendered as text rather
            // than a line beginning with "OK". Honor an explicit success result so
            // valid operations aren't reported as failures by the Kotlin wrapper.
            val explicitFalse = log.contains("'ok': False") ||
                    log.contains("\"ok\": false") ||
                    log.contains("\"ok\": False")
            val explicitTrue = log.contains("'ok': True") ||
                    log.contains("\"ok\": true") ||
                    log.contains("\"ok\": True")
            val hasErrorLine = lines.any {
                it.startsWith("X ") || it.startsWith("ERROR:") || it.startsWith("CRITICAL:")
            }
            val hasSuccessLine = lines.any {
                it.startsWith("OK ") || it.startsWith("OUT ") || it.startsWith("> ")
            }
            val bridgeFailed = (explicitFalse && !explicitTrue) || hasErrorLine || (!explicitTrue && !hasSuccessLine)
            return !bridgeFailed to lines
            } finally {
                closePyObjectQuietly(coreModule)
            }
            } finally {
                closePyObjectQuietly(bridge)
            }
        } catch (e: Throwable) {
            return false to listOf("... bridge error: ${e.message ?: e.javaClass.simpleName}")
        }
    }

    fun setEnv(key: String, value: String) {
        bridgeLock.lock()
        var osMod: Any? = null
        var environ: Any? = null
        var result: Any? = null
        try {
            val pyClass = Class.forName("com.chaquo.python.Python")
            val isStarted = pyClass.getMethod("isStarted").invoke(null) as Boolean
            if (!isStarted) return
            val py = pyClass.getMethod("getInstance").invoke(null) ?: return
            val getModule = pyClass.getMethod("getModule", String::class.java)
            osMod = getModule.invoke(py, "os") ?: return
            val pyObjectCls = Class.forName("com.chaquo.python.PyObject")
            val callAttr = pyObjectCls.getMethod("callAttr", String::class.java, Array<Any?>::class.java)
            val getObj = pyObjectCls.getMethod("get", Any::class.java)
            environ = getObj.invoke(osMod, "environ") ?: return
            result = callAttr.invoke(environ, "__setitem__", arrayOf<Any?>(key, value))
        } catch (_: Throwable) {
        } finally {
            closePyObjectQuietly(result)
            closePyObjectQuietly(environ)
            closePyObjectQuietly(osMod)
            bridgeLock.unlock()
        }
    }

    fun clearEnv(key: String) {
        bridgeLock.lock()
        var osMod: Any? = null
        var environ: Any? = null
        var result: Any? = null
        try {
            val pyClass = Class.forName("com.chaquo.python.Python")
            val isStarted = pyClass.getMethod("isStarted").invoke(null) as Boolean
            if (!isStarted) return
            val py = pyClass.getMethod("getInstance").invoke(null) ?: return
            val getModule = pyClass.getMethod("getModule", String::class.java)
            osMod = getModule.invoke(py, "os") ?: return
            val pyObjectCls = Class.forName("com.chaquo.python.PyObject")
            val callAttr = pyObjectCls.getMethod("callAttr", String::class.java, Array<Any?>::class.java)
            val getObj = pyObjectCls.getMethod("get", Any::class.java)
            environ = getObj.invoke(osMod, "environ") ?: return
            result = callAttr.invoke(environ, "pop", arrayOf<Any?>(key, null))
        } catch (_: Throwable) {
        } finally {
            closePyObjectQuietly(result)
            closePyObjectQuietly(environ)
            closePyObjectQuietly(osMod)
            bridgeLock.unlock()
        }
    }

}
