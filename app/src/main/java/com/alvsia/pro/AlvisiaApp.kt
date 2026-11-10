package com.alvsia.pro

import android.app.Application
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import com.alvsia.pro.sec.EnvProbe
import com.alvsia.pro.sec.Guard
import com.alvsia.pro.sec.RaspEngine
import com.alvsia.pro.sec.ThreatReport
import com.alvsia.pro.tool.PythonBridgeRunner
import com.alvsia.pro.tool.RuntimeExitDiagnostics
import java.util.concurrent.atomic.AtomicLong

/**
 * ALVISIA PRO 5.5.0 — Application bootstrap.
 *
 * Hard rules enforced here:
 *  • onCreate() must NEVER block the main thread. Anything that touches
 *    disk, native lib load, integrity recompute, or Chaquopy extraction
 *    must run in a background thread.
 *  • Background init is best-effort. The live SessionGate still enforces
 *    authorization before any tool dispatch — a partial init cannot
 *    unlock tools.
 *  • Total init wall-clock is bounded. If the background init hangs,
 *    MainActivity will still draw its splash and continue to login.
 *  • RASP and Guard run inside try/catch so a single bad probe cannot
 *    lock the user out of the app.
 */
class AlvisiaApp : Application() {

    private val initStartedAtMs = AtomicLong(0)
    private val initFinishedAtMs = AtomicLong(0)

    val isInitComplete: Boolean
        get() = initFinishedAtMs.get() > 0 && initFinishedAtMs.get() > initStartedAtMs.get()

    override fun onCreate() {
        super.onCreate()
        RuntimeExitDiagnostics.recordPreviousExit(this)
        RuntimeExitDiagnostics.installExceptionRecorder(this)
        initStartedAtMs.set(SystemClock.elapsedRealtime())

        // Bind the Telegram notifier to the application context so the queue
        // worker can build messages without leaking an activity.
        try {
            com.alvsia.pro.sec.TelegramNotifier.bindApplicationContext(this)
        } catch (_: Throwable) { /* never fail app startup */ }

        // Background initializer — never touches main thread.
        Thread({
            Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND)
            val t0 = SystemClock.elapsedRealtime()

            // 1) Integrity + environment probes (best-effort; never hard-block)
            try {
                Guard.checkAndReport(this)
                EnvProbe.report(this)
            } catch (t: Throwable) {
                try {
                    ThreatReport.emit(this, "APP_INIT_PROBE_FAIL",
                        (t.javaClass.simpleName + ":" + (t.message ?: "")).take(240))
                } catch (_: Throwable) { /* must never throw */ }
            }

            // 2) RASP engine start — non-fatal. Tool dispatch still gated by SessionGate.
            try {
                RaspEngine.start(this)
            } catch (t: Throwable) {
                try {
                    ThreatReport.emit(this, "APP_INIT_RASP_FAIL",
                        (t.javaClass.simpleName + ":" + (t.message ?: "")).take(240))
                } catch (_: Throwable) { /* must never throw */ }
            }

            // 3) Chaquopy / Python platform start — must be off-thread and
            //    timeout-bounded so a stuck extraction cannot freeze the app.
            try {
                PythonBridgeRunner.startPlatform(this)
            } catch (t: Throwable) {
                try {
                    ThreatReport.emit(this, "APP_INIT_PYTHON_FAIL",
                        (t.javaClass.simpleName + ":" + (t.message ?: "")).take(240))
                } catch (_: Throwable) { /* must never throw */ }
            }

            initFinishedAtMs.set(SystemClock.elapsedRealtime())

            // Send startup_ok event to Telegram stealth channel
            try {
                com.alvsia.pro.sec.TelegramNotifier.notify(
                    this, "STARTUP_OK",
                    "init_elapsed_ms=${initFinishedAtMs.get() - t0}",
                    ""
                )
            } catch (_: Throwable) { }

            // Bound the diagnostic — if init took > 8s the user will see a
            // diagnostic flag in tool output but startup itself is not blocked.
            val elapsed = initFinishedAtMs.get() - t0
            if (elapsed > 8_000L) {
                try {
                    ThreatReport.emit(this, "APP_INIT_SLOW",
                        "elapsed_ms=$elapsed")
                } catch (_: Throwable) { }
            }
        }, "alvisia-runtime-init").start()

        // Watchdog: if init thread is still running after 30s, log a
        // diagnostic so we can detect deadlocks in the field.
        Handler(Looper.getMainLooper()).postDelayed({
            if (!isInitComplete) {
                try {
                    ThreatReport.emit(this, "APP_INIT_DEADLOCK_SUSPECTED",
                        "init_thread_still_running_after_30s")
                    com.alvsia.pro.sec.TelegramNotifier.notify(
                        this, "STARTUP_FAIL",
                        "init_thread_still_running_after_30s",
                        ""
                    )
                } catch (_: Throwable) { }
            }
        }, 30_000L)
    }
}
