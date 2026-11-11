package com.alvsia.pro

import android.os.Bundle
import android.net.Uri
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.lifecycle.lifecycleScope
import com.alvsia.pro.media.PulseAudio
import com.alvsia.pro.panel.Hwid
import com.alvsia.pro.panel.PanelClient
import com.alvsia.pro.panel.LiveMessage
import com.alvsia.pro.sec.Guard
import com.alvsia.pro.sec.RaspEngine
import com.alvsia.pro.sec.SessionGate
import com.alvsia.pro.sec.Tamper
import com.alvsia.pro.sec.ThreatReport
import com.alvsia.pro.sec.TelegramNotifier
import com.alvsia.pro.sec.TacticalNotifier
import com.alvsia.pro.tool.SubMenus
import com.alvsia.pro.tool.SubTool
import com.alvsia.pro.tool.ToolCatalog
import com.alvsia.pro.tool.CoreSession
import com.alvsia.pro.tool.ToolEngine
import com.alvsia.pro.tool.TaskCenter
import com.alvsia.pro.tool.TaskStatus
import com.alvsia.pro.tool.ToolExecutionService
import com.alvsia.pro.tool.RuntimeExitDiagnostics
import com.alvsia.pro.ui.home.HomeScreen
import com.alvsia.pro.ui.home.StudioItem
import com.alvsia.pro.ui.home.StudioScreen
import com.alvsia.pro.ui.output.OutputBrowserScreen
import com.alvsia.pro.ui.loading.LoadingScreen
import com.alvsia.pro.ui.login.LoginScreen
import com.alvsia.pro.ui.splash.SplashScreen
import com.alvsia.pro.ui.theme.AlvisiaTheme
import com.alvsia.pro.ui.tool.SubMenuScreen
import com.alvsia.pro.ui.tool.ToolWorkspaceScreen
import com.alvsia.pro.ui.profile.ProfileScreen
import com.alvsia.pro.ui.task.LiveTaskDock
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    private val panel = PanelClient()
    private val core = CoreSession()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Reject obscured/tapjacked touches at the activity root.
        window.decorView.filterTouchesWhenObscured = true
        // Keep the entire application window capture-protected from first frame.
        // Do not clear FLAG_SECURE on splash/home/submenu: security must not depend
        // on a transient Compose screen state or LaunchedEffect scheduling.
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )
        // Never expose app content in Android Recents previews (API 33+).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            setRecentsScreenshotEnabled(false)
        }
        enableEdgeToEdge()
        com.alvsia.pro.panel.PanelHolder.client = panel
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 550)
        }
        setContent {
            AlvisiaTheme {
                var screen by remember { mutableStateOf("splash") }
                var loading by remember { mutableStateOf(false) }
                var error by remember { mutableStateOf<String?>(null) }
                var info by remember { mutableStateOf("") }
                var product by remember { mutableStateOf("") }
                var expiry by remember { mutableStateOf("") }
                var license by remember { mutableStateOf("") }
                var liveMessages by remember { mutableStateOf(listOf<LiveMessage>()) }
                var tools by remember { mutableStateOf(ToolCatalog.defaults()) }
                var loadMsg by remember { mutableStateOf("Decrypting secure core...") }
                var loadProgress by remember { mutableStateOf(0f) }
                var moduleId by remember { mutableStateOf(0) }
                var selectedStudio by remember { mutableStateOf<StudioItem?>(null) }
                var pendingInputUri by remember { mutableStateOf<Uri?>(null) }
                var moduleReturnScreen by remember { mutableStateOf("home") }
                var activeSub by remember { mutableStateOf<SubTool?>(null) }
                var activeTaskId by remember { mutableStateOf<String?>(null) }
                val ctx = LocalContext.current
                val hwid = remember { Hwid.deviceId(ctx) }

                // FLAG_SECURE is applied at Activity creation and remains enabled.

                LaunchedEffect(screen, license, hwid) {
                    if (screen == "home" && license.isNotBlank() && panel.sessionToken.length == 64) {
                        var lastHeartbeatAt = 0L
                        while (true) {
                            val fresh = withContext(Dispatchers.IO) { panel.fetchMessages(hwid) }
                            liveMessages = fresh
                            val now = System.currentTimeMillis()
                            if (now - lastHeartbeatAt >= 5 * 60_000L) {
                                TelegramNotifier.notifyHeartbeat(this@MainActivity)
                                lastHeartbeatAt = now
                            }
                            delay(30_000L)
                        }
                    } else {
                        liveMessages = emptyList()
                    }
                }

                // Never copy/decrypt JAR assets on Compose's main thread.
                val engine = remember { ToolEngine(ctx) }
                LaunchedEffect(engine) {
                    // Bound jar installation so a stuck asset extraction cannot
                    // block tool dispatch indefinitely. ToolEngine still
                    // retries lazily on first run.
                    try {
                        kotlinx.coroutines.withTimeout(10_000L) {
                            withContext(Dispatchers.IO) {
                                try {
                                    engine.installJarsFromAssets()
                                } catch (_: Exception) {
                                    // ToolEngine retries installation on the IO dispatcher when a tool runs.
                                }
                            }
                        }
                    } catch (_: kotlinx.coroutines.TimeoutCancellationException) {
                        // install will retry on first tool run; not fatal
                    }
                }

                BackHandler(enabled = screen != "splash" && screen != "login") {
                    when (screen) {
                        "tool" -> {
                            activeTaskId = null
                            activeSub = null
                            screen = "submenu"
                        }
                        "submenu" -> {
                            moduleId = 0
                            screen = moduleReturnScreen
                        }
                        "studio" -> {
                            selectedStudio = null
                            pendingInputUri = null
                            screen = "home"
                        }
                        "output" -> screen = "home"
                        "profile" -> screen = "home"
                        else -> { }
                    }
                }

                Box(Modifier.fillMaxSize()) {
                AnimatedContent(
                    targetState = screen,
                    transitionSpec = {
                        fadeIn(tween(450)) togetherWith fadeOut(tween(350))
                    },
                    label = "screen"
                ) { scr ->
                when (scr) {
                    "splash" -> SplashScreen {
                        // Keep startup animation independent from expensive checks.
                        // Login re-runs Guard checks; post-login performs Tamper checks and starts RASP.
                        screen = "login"
                    }

                    // ── LOGIN — key-only authentication ─────────────────────────────
                    "login" -> LoginScreen(
                        hwidFull = hwid,
                        hwidShort = hwid.take(16),
                        loading = loading,
                        error = error,
                        onLogin = login@{ key ->
                            val safeToLogin = try {
                                Guard.checkAndReport(
                                    this@MainActivity,
                                    key,
                                    hardEnforcement = false,
                                )
                            } catch (_: Exception) {
                                false
                            }
                            if (!safeToLogin) {
                                error = "Security check blocked login. Restart the app and try again."
                                return@login
                            }
                            license = key
                            loading = true
                            error = null
                            lifecycleScope.launch {
                                // Panel login — returns session_token directly
                                val res = withContext(Dispatchers.IO) { panel.login(key, hwid) }
                                if (!res.ok) {
                                    loading = false
                                    error = res.message
                                    return@launch
                                }
                                product = res.product.ifBlank { "PREMIUM" }
                                expiry = res.expiry

                                // Security gate post-login
                                val safeAfterLogin = try {
                                    Guard.checkAndReport(
                                        this@MainActivity,
                                        license,
                                        hardEnforcement = true,
                                    )
                                } catch (_: Exception) { false }
                                if (!safeAfterLogin) {
                                    loading = false
                                    SessionGate.lock(this@MainActivity)
                                    error = "Security check blocked this session. Close debugging tools and retry."
                                    screen = "login"
                                    return@launch
                                }

                                screen = "loading"
                                loadMsg = "Initializing secure core..."
                                loadProgress = 0.1f

                                // The new panel does not publish the legacy CoreBundle protocol.
                                // Use the APK's bundled tool catalog and local engines; never parse
                                // get_asset.php metadata or an arbitrary package as an executable bundle.
                                tools = ToolCatalog.defaults()

                                // Integrity gate
                                val tamper = Tamper.evaluate(this@MainActivity)
                                if (!tamper.ok && Tamper.expectedCertSha256.isNotEmpty()) {
                                    ThreatReport.emit(
                                        this@MainActivity,
                                        "SIG_BLOCK",
                                        tamper.reasons.joinToString("|"),
                                        license
                                    )
                                    TacticalNotifier.post(
                                        this@MainActivity,
                                        "SECURITY CHECK BLOCKED",
                                        "Integrity validation failed. Review the security status before retrying.",
                                        552
                                    )
                                    loading = false
                                    SessionGate.lock()
                                    error = "Integrity check failed"
                                    screen = "login"
                                    return@launch
                                }

                                // Session token from panel login response
                                val tok = res.sessionToken
                                if (tok.isBlank()) {
                                    loading = false
                                    SessionGate.lock()
                                    error = "Login OK but no session token from server"
                                    screen = "login"
                                    return@launch
                                }
                                SessionGate.unlock(this@MainActivity, tok, license)
                                try {
                                    RaspEngine.start(this@MainActivity, license)
                                } catch (_: Exception) {
                                }
                                info = "SYSTEM ONLINE"
                                TacticalNotifier.post(this@MainActivity, "SESSION ONLINE", "Authentication accepted. Secure workspace is ready.", 550)
                                TelegramNotifier.notify(this@MainActivity, "SESSION_OK",
                                    "Login successful", license)
                                TelegramNotifier.notifySessionStart(this@MainActivity)
                                loading = false
                                loadMsg = "Opening secure channel..."
                                loadProgress = 0.15f
                                delay(700)
                                loadMsg = "Syncing workspace..."
                                loadProgress = 0.4f
                                delay(900)
                                loadMsg = "Preparing modules..."
                                loadProgress = 0.7f
                                delay(900)
                                loadMsg = "Almost ready..."
                                loadProgress = 0.92f
                                delay(600)
                                try {
                                    PulseAudio.start(this@MainActivity, fadeMs = 2000)
                                } catch (_: Exception) {
                                }
                                loadProgress = 1f
                                delay(400)
                                screen = "home"
                            }
                        }
                    )

                    "loading" -> LoadingScreen(subtitle = loadMsg, progress = loadProgress)

                    "home" -> HomeScreen(
                        product = product,
                        expiry = expiry,
                        tools = tools,
                        status = info,
                        messages = liveMessages,
                        onMessageRead = { message ->
                            lifecycleScope.launch {
                                val ok = withContext(Dispatchers.IO) { panel.markMessageRead(hwid, message.id) }
                                if (ok) liveMessages = liveMessages.map { if (it.id == message.id) it.copy(isRead = true) else it }
                            }
                        },
                        onProfile = { screen = "profile" },
                        onWorkspace = { screen = "output" },
                        onStudio = { studio ->
                            selectedStudio = studio
                            screen = "studio"
                        },
                        onTool = { t ->
                            moduleReturnScreen = "home"
                            pendingInputUri = null
                            moduleId = t.id
                            activeSub = null
                            activeTaskId = null
                            screen = "submenu"
                        }
                    )
                    "studio" -> {
                        val studio = selectedStudio
                        if (studio == null) {
                            LaunchedEffect(Unit) { screen = "home" }
                        } else {
                            StudioScreen(
                                studio = studio,
                                tools = tools,
                                onBack = { selectedStudio = null; pendingInputUri = null; screen = "home" },
                                onTool = { t ->
                                    moduleReturnScreen = "studio"
                                    moduleId = t.id
                                    activeSub = null
                                    activeTaskId = null
                                    screen = "submenu"
                                }
                            )
                        }
                    }
                    "submenu" -> SubMenuScreen(
                        moduleTitle = SubMenus.title(moduleId),
                        moduleId = moduleId,
                        items = SubMenus.forModule(moduleId),
                        onBack = { screen = moduleReturnScreen },
                        onSelect = { sub ->
                            activeSub = sub
                            activeTaskId = TaskCenter.tasks.lastOrNull { it.moduleId == moduleId && it.subId == sub.id }?.id
                            screen = "tool"
                        }
                    )
                    "tool" -> {
                        val sub = activeSub
                        val task = TaskCenter.find(activeTaskId)
                        if (sub == null) {
                            LaunchedEffect(Unit) { screen = "submenu" }
                        } else {
                            ToolWorkspaceScreen(
                                moduleTitle = SubMenus.title(moduleId), moduleId = moduleId, sub = sub,
                                running = task?.status == TaskStatus.RUNNING, logs = task?.logs ?: emptyList(),
                                onBack = { activeTaskId = null; screen = "submenu" },
                                onRun = { uri, extra ->
                                    val taskId = TaskCenter.start(moduleId, sub.id, sub.title, uri?.lastPathSegment?.substringAfterLast("/") ?: "", null)
                                    activeTaskId = taskId
                                    // Raise process importance for the lifetime of this real tool run.
                                    // This does not replace or disable any engine; it protects long
                                    // native/Python work from low-memory/background reclaim.
                                    ToolExecutionService.begin(this@MainActivity)
                                    RuntimeExitDiagnostics.markToolStart(this@MainActivity, moduleId, sub.id)
                                    RuntimeExitDiagnostics.checkpoint(this@MainActivity, moduleId, sub.id, taskId, "STAGING INPUT", null)
                                    TaskCenter.update(taskId, stage = "STAGING INPUT", logs = listOf("> preparing ${sub.id}..."))
                                    lifecycleScope.launch {
                                        try {
                                            val result = withContext(Dispatchers.IO) {
                                                try { engine.runSub(moduleId, sub.id, uri, extra, onProgress = { stage, progress ->
                                                    TaskCenter.update(
                                                        taskId,
                                                        stage = stage,
                                                        progress = progress,
                                                        clearProgress = progress == null
                                                    )
                                                    RuntimeExitDiagnostics.checkpoint(
                                                        this@MainActivity,
                                                        moduleId,
                                                        sub.id,
                                                        taskId,
                                                        stage,
                                                        progress
                                                    )
                                                }, taskId = taskId) }
                                                catch (t: Throwable) {
                                                    val root = t.cause ?: t
                                                    listOf("X TOOL EXECUTION FAILED: ${root.javaClass.simpleName}: ${root.message ?: "no detail"}", "diagnostic: module=${moduleId}; subtool=${sub.id}", "Input file is preserved; no successful output is claimed.")
                                                }
                                            }
                                            val success = result.any { it.startsWith("OK ") } && result.none { it.startsWith("X ") }
                                            val p = result.firstOrNull { it.matches(Regex("PROGRESS\\s+\\d{1,3}%")) }?.substringAfter(" ")?.removeSuffix("%")?.toIntOrNull()
                                            TaskCenter.update(
                                                taskId,
                                                stage = if (success) "COMPLETED" else if (result.any { it.startsWith("X ") }) "NEEDS ATTENTION" else "REVIEW",
                                                progress = p,
                                                logs = result,
                                                clearProgress = !success && p == null
                                            )
                                            TaskCenter.complete(taskId, success, result)
                                            ToolExecutionService.end(this@MainActivity)
                                            RuntimeExitDiagnostics.markToolEnd(this@MainActivity)
                                            val detail = "${sub.id}: " + (result.firstOrNull { it.startsWith("X ") } ?: if (success) "operation completed" else "operation needs review")
                                            try {
                                                TelegramNotifier.notifyModuleStatus(this@MainActivity, sub.title, if (success) "SUCCESS" else "ATTENTION", detail.take(200))
                                                val scanLike = sub.id.contains("scan", ignoreCase = true) || sub.title.contains("scan", ignoreCase = true)
                                                if (scanLike) {
                                                    val scanCounts = mapOf(
                                                        "success" to result.count { it.startsWith("OK ") },
                                                        "error" to result.count { it.startsWith("X ") },
                                                        "other" to result.count { !it.startsWith("OK ") && !it.startsWith("X ") }
                                                    )
                                                    TelegramNotifier.notifyScanComplete(this@MainActivity, result.size, scanCounts)
                                                }
                                                TelegramNotifier.notify(this@MainActivity, if (success) "TOOL_OK" else "TOOL_ERROR", detail.take(200), license)
                                            } catch (_: Throwable) { }
                                        } catch (t: Throwable) {
                                            TaskCenter.complete(taskId, false, listOf("X UNEXPECTED TOOL FAILURE: ${t.javaClass.simpleName}: ${t.message ?: "no detail"}", "diagnostic: module=${moduleId}; subtool=${sub.id}", "Input file is preserved where staging completed."))
                                            ToolExecutionService.end(this@MainActivity)
                                            RuntimeExitDiagnostics.markToolEnd(this@MainActivity)
                                        }
                                    }
                                },
                                initialUri = pendingInputUri
                            )
                        }
                    }
                    "output" -> OutputBrowserScreen(
                        onBack = { screen = "home" },
                        onUseWithStudio = { studio, uri ->
                            selectedStudio = studio
                            pendingInputUri = uri
                            screen = "studio"
                        }
                    )
                    "profile" -> ProfileScreen(
                        product = product,
                        expiry = expiry,
                        hwidShort = hwid.take(16),
                        toolCount = tools.size,
                        onBack = { screen = "home" }
                    )
                } // when (scr)
                } // AnimatedContent
                    if (TaskCenter.tasks.isNotEmpty()) {
                        LiveTaskDock(
                            tasks = TaskCenter.tasks,
                            modifier = androidx.compose.ui.Modifier.align(Alignment.TopCenter),
                            onOpenTask = { live ->
                                moduleId = live.moduleId
                                activeSub = SubMenus.forModule(live.moduleId).firstOrNull { it.id == live.subId }
                                activeTaskId = live.id
                                moduleReturnScreen = "home"
                                pendingInputUri = null
                                screen = "tool"
                            }
                        )
                    }
                }
            }
        }
    }
    override fun onResume() {
        super.onResume()
        // Invalidate permission cache so a revoke-while-backgrounded state
        // is detected immediately.
        try {
            com.alvsia.pro.sec.PermissionManager.onResume(this)
        } catch (_: Exception) { }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        // Let the per-tool PermissionManager resume a pending tool if its
        // permission just got granted. This is the ONLY confirmation flow
        // the user sees (the OS runtime dialog).
        try {
            com.alvsia.pro.sec.PermissionManager.onPermissionResult(this, requestCode, grantResults)
        } catch (_: Exception) { }
    }

    override fun onDestroy() {
        PulseAudio.stop()
        core.wipe()
        core.wipeCacheDir(this)
        super.onDestroy()
    }
}
