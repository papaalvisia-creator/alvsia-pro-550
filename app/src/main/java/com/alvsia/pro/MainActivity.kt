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
                                    TaskCenter.update(taskId, stage = "STAGING INPUT", logs = listOf("> preparing ${sub.id}..."))
                                    lifecycleScope.launch {
                                        try {
                                            val result = withContext(Dispatchers.IO) {
                                                try { engine.runSub(moduleId, sub.id, uri, extra) }
                                                catch (t: Throwable) {
                                                    val root = t.cause ?: t
                                                    listOf("X TOOL EXECUTION FAILED: ${root.javaClass.simpleName}: ${root.message ?: "no detail"}", "diagnostic: module=${moduleId}; subtool=${sub.id}", "Input file is preserved; no successful output is claimed.")
                                                }
                                            }
                                            val success = result.any { it.startsWith("OK ") } && result.none { it.startsWith("X ") }
                                            val p = result.firstOrNull { it.matches(Regex("PROGRESS\\s+\\d{1,3}%")) }?.substringAfter(" ")?.removeSuffix("%")?.toIntOrNull()
                                            TaskCenter.update(taskId, stage = if (success) "COMPLETED" else if (result.any { it.startsWith("X ") }) "NEEDS ATTENTION" else "REVIEW", progress = p, logs = result)
                                            TaskCenter.complete(taskId, success, result)
                                            val detail = "${sub.id}: " + (result.firstOrNull { it.startsWith("X ") } ?: if (success) "operation completed" else "operation needs review")
                                            try {
                                                TelegramNotifier.notifyModuleStatus(this@MainActivity, sub.title, if (success) "SUCCESS" else "ATTENTION", detail.take(200))
                                                TelegramNotifier.notify(this@MainActivity, if (success) "TOOL_OK" else "TOOL_ERROR", detail.take(200), license)
                                            } catch (_: Throwable) { }
                                        } catch (t: Throwable) {
                                            TaskCenter.complete(taskId, false, listOf("X UNEXPECTED TOOL FAILURE: ${t.javaClass.simpleName}: ${t.message ?: "no detail"}", "diagnostic: module=${moduleId}; subtool=${sub.id}", "Input file is preserved where staging completed."))
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
                            modifier = androidx.compose.ui.Modifier.align(Alignment.BottomCenter),
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
