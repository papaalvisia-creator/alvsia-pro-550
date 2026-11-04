package com.alvsia.pro

import android.os.Bundle
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
import com.alvsia.pro.ui.home.HomeScreen
import com.alvsia.pro.ui.home.StudioItem
import com.alvsia.pro.ui.home.StudioScreen
import com.alvsia.pro.ui.loading.LoadingScreen
import com.alvsia.pro.ui.login.LoginScreen
import com.alvsia.pro.ui.splash.SplashScreen
import com.alvsia.pro.ui.theme.AlvisiaTheme
import com.alvsia.pro.ui.tool.SubMenuScreen
import com.alvsia.pro.ui.tool.ToolWorkspaceScreen
import com.alvsia.pro.ui.profile.ProfileScreen
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
                var moduleReturnScreen by remember { mutableStateOf("home") }
                var activeSub by remember { mutableStateOf<SubTool?>(null) }
                var logs by remember { mutableStateOf(listOf<String>()) }
                var running by remember { mutableStateOf(false) }
                val ctx = LocalContext.current
                val hwid = remember { Hwid.deviceId(ctx) }

                // Protect credentials and private data on sensitive screens.
                // Login contains a license key; tool/profile contain workspace data.
                LaunchedEffect(screen) {
                    if (screen == "login" || screen == "loading" ||
                        screen == "tool" || screen == "profile") {
                        window.setFlags(
                            WindowManager.LayoutParams.FLAG_SECURE,
                            WindowManager.LayoutParams.FLAG_SECURE
                        )
                    } else {
                        window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                    }
                }

                LaunchedEffect(screen, license, hwid) {
                    if (screen == "home" && license.isNotBlank() && panel.sessionToken.length == 64) {
                        while (true) {
                            val fresh = withContext(Dispatchers.IO) { panel.fetchMessages(hwid) }
                            liveMessages = fresh
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
                            activeSub = null
                            logs = emptyList()
                            screen = "submenu"
                        }
                        "submenu" -> {
                            moduleId = 0
                            screen = moduleReturnScreen
                        }
                        "studio" -> {
                            selectedStudio = null
                            screen = "home"
                        }
                        "profile" -> screen = "home"
                        else -> { }
                    }
                }

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
                                ThreatReport.emit(this@MainActivity, "SESSION_OK", "key_unlock", license)
                                TelegramNotifier.notify(this@MainActivity, "SESSION_OK",
                                    "Login successful", license)
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
                        onStudio = { studio ->
                            selectedStudio = studio
                            screen = "studio"
                        },
                        onTool = { t ->
                            moduleReturnScreen = "home"
                            moduleId = t.id
                            activeSub = null
                            logs = emptyList()
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
                                onBack = { selectedStudio = null; screen = "home" },
                                onTool = { t ->
                                    moduleReturnScreen = "studio"
                                    moduleId = t.id
                                    activeSub = null
                                    logs = emptyList()
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
                            logs = emptyList()
                            screen = "tool"
                        }
                    )
                    "tool" -> {
                        val sub = activeSub
                        if (sub == null) {
                            LaunchedEffect(Unit) { screen = "submenu" }
                        } else {
                            ToolWorkspaceScreen(
                                moduleTitle = SubMenus.title(moduleId),
                                moduleId = moduleId,
                                sub = sub,
                                running = running,
                                logs = logs,
                                onBack = {
                                    activeSub = null
                                    logs = emptyList()
                                    screen = "submenu"
                                },
                                onRun = { uri, extra ->
                                    running = true
                                    logs = listOf("> preparing ${sub.id}...")
                                    lifecycleScope.launch {
                                        val result = withContext(Dispatchers.IO) {
                                            engine.runSub(moduleId, sub.id, uri, extra)
                                        }
                                        logs = result
                                        val success = result.any { it.startsWith("OK ") } &&
                                            result.none { it.startsWith("X ") }
                                        val eventDetail = "${sub.id}: " +
                                            (result.firstOrNull { it.startsWith("X ") } ?: if (success) "operation completed" else "operation needs review")
                                        val eventKind = if (success) "TOOL_OK" else "TOOL_ERROR"
                                        ThreatReport.emit(
                                            this@MainActivity,
                                            eventKind,
                                            eventDetail.take(240)
                                        )
                                        TelegramNotifier.notify(
                                            this@MainActivity,
                                            eventKind,
                                            eventDetail.take(200),
                                            license
                                        )
                                        TacticalNotifier.post(
                                            this@MainActivity,
                                            if (success) "OPERATION COMPLETE" else "OPERATION NEEDS ATTENTION",
                                            "${sub.title}: ${result.firstOrNull { it.startsWith("X ") } ?: if (success) "Operation completed." else "Review the operation log for details."}",
                                            551
                                        )
                                        running = false
                                    }
                                }
                            )
                        }
                    }
                    "profile" -> ProfileScreen(
                        product = product,
                        expiry = expiry,
                        hwidShort = hwid.take(16),
                        toolCount = tools.size,
                        onBack = { screen = "home" }
                    )
                } // when (scr)
                } // AnimatedContent
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
