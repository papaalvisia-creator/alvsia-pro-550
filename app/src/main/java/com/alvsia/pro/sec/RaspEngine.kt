package com.alvsia.pro.sec

import android.content.Context
import android.os.Build
import android.os.Debug
import android.os.Handler
import android.os.Looper
import com.alvsia.pro.tool.RamToolVault
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/**
 * ALVISIA PRO 5.5.0 — RaspEngine HARDENED (Enterprise-Grade RASP)
 *
 * Detection matrix:
 *  ① Debugger (JDWP + waitingForDebugger + TracerPid)
 *  ② Frida / Xposed / Substrate / Dobby / ShadowHook / bhook (FridaProbe)
 *  ③ Memory dump attempt (MemoryGuard)
 *  ④ Root / su / Magisk / KernelSU (EnvProbe)
 *  ⑤ Emulator / VM / QEMU / VBox / BlueStacks (EnvProbe)
 *  ⑥ Clone / VirtualApp / BlackBox / parallel space (EnvProbe)
 *  ⑦ APK certificate mismatch / repack / extra DEX (IntegrityBomb)
 *  ⑧ MITM / proxy / VPN active (NetworkGuard)
 *  ⑨ ADB enabled + adb root shell (EnvProbe)
 *  ⑩ Hook packages installed (FridaProbe.hasHookPackage)
 *
 * Hard-kill: ① ② ③ ⑦ — instrumentation and repack always hard.
 * Soft (degrade + report): ④ ⑤ ⑥ ⑧ ⑨ ⑩
 * Tick interval: 8 s.
 */
object RaspEngine {

    private val started      = AtomicBoolean(false)
    private val handler      = Handler(Looper.getMainLooper())
    private val hardKillCount = AtomicInteger(0)

    // Soft heuristic signals (for example, a bundled hook-support library) must not
    // generate a Telegram alert on every 4-second RASP tick.
    private const val SOFT_REPORT_COOLDOWN_MS = 15 * 60 * 1000L
    @Volatile private var lastSoftSignature: String = ""
    @Volatile private var lastSoftReportAt: Long = 0L

    @Synchronized
    private fun shouldReportSoft(signature: String, now: Long): Boolean {
        if (signature.isBlank()) {
            lastSoftSignature = ""
            lastSoftReportAt = 0L
            return false
        }
        if (signature != lastSoftSignature || now - lastSoftReportAt >= SOFT_REPORT_COOLDOWN_MS) {
            lastSoftSignature = signature
            lastSoftReportAt = now
            return true
        }
        return false
    }

    @Volatile var threatLevel: Int = 0
        private set

    // ── Public API ────────────────────────────────────────────────────────

    fun start(ctx: Context, license: String = "") {
        if (!started.compareAndSet(false, true)) return
        val app = ctx.applicationContext
        // Kick first tick immediately, then schedule repeating
        thread(name = "rasp-init", isDaemon = true) { tick(app, license) }
        // Sprint 1: 4-second tick (down from 8s) — faster threat detection.
        // Deep scan runs every 30s (down from 60s) to refresh DEX + cgroup checks.
        scheduleRepeat(app, license, intervalMs = 4_000L)
        scheduleDeepScan(app, license, intervalMs = 30_000L)
    }

    fun tick(ctx: Context, license: String = "") {
        val hard = mutableListOf<String>()
        val soft = mutableListOf<String>()

        // ① Debugger
        if (Debug.isDebuggerConnected() || Debug.waitingForDebugger()) hard += "jdwp_connected"

        // ② Frida / hook libs
        FridaProbe.signals().forEach { signal ->
            if (signal.startsWith("hooklib:")) soft += signal
            else hard += signal
        }

        // ③ Memory dump
        MemoryGuard.detectPtrace()?.let { hard += it }

        // ⑦ Integrity (Sprint 1: includes DEX hash + count via DexGuardian)
        val integrity = IntegrityBomb.evaluate(ctx)
        if (!integrity.clean) integrity.reasons.forEach { hard += it }

        // ④⑤⑥⑨ Root / emulator / clone / ADB (soft — legitimate testers may use these)
        emulatorSignals().forEach { soft += it }

        // ⑧ Network MITM / proxy guard. Guard health is distinct from
        // whether a proxy is currently present on a legitimate clean network.
        if (!NetworkGuard.net_guard(ctx)) soft += "net_guard_unavailable"
        if (NetworkGuard.detect_proxy(ctx)) soft += "proxy_detected"
        NetworkGuard.signals(ctx).forEach { soft += it }

        // ⑩ Hook packages (legacy — kept for back-compat with FridaProbe)
        FridaProbe.hasHookPackage(ctx.packageManager).forEach { soft += it }

        // Sprint 1: AntiHook (Layer 2) — STRONG signal (active injection via maps)
        // Hard if any map markers detected; soft for cgroup virtualization + cpuinfo emulator
        val hookSignals = AntiHook.signals()
        hookSignals.filter { it.startsWith("maps:") }.forEach { hard += "antihook_$it" }
        hookSignals.filterNot { it.startsWith("maps:") }.forEach { soft += "antihook_$it" }
        // Hook framework installer packages — soft signal (not proof of injection)
        AntiHook.hasHookFrameworkPackages(ctx.packageManager).forEach { soft += "antihook_$it" }

        // Dual-layer runtime gate: bounded Kotlin instruction interpreter plus
        // independent native RASP probes. Only concrete integrity/instrumentation
        // failures are hard signals; root/emulator heuristics remain soft above.
        DualVmGuard.inspect(ctx).forEach { hard += it }

        // Threat level = hard count * 10 + soft count
        threatLevel = hard.size * 10 + soft.size

        // Hard: lock session, wipe RAM, report
        if (hard.isNotEmpty()) {
            hardKillCount.incrementAndGet()
            val detail = hard.joinToString("|")
            try { ThreatReport.emit(ctx, "THREAT", detail, license) } catch (_: Exception) {}
            try { TelegramNotifier.notify(ctx, "THREAT", detail, license) } catch (_: Exception) {}
            try {
                SessionGate.onThreat()
                RamToolVault.wipeAll()
            } catch (_: Exception) {}
        }

        // Soft: degrade + report
        if (soft.isNotEmpty()) {
            Guard.degraded = true
            val detail = soft.distinct().sorted().joinToString("|")
            if (shouldReportSoft(detail, System.currentTimeMillis())) {
                try { ThreatReport.emit(ctx, "SOFT_THREAT", detail, license) } catch (_: Exception) {}
            }
        } else {
            shouldReportSoft("", System.currentTimeMillis())
        }
    }

    // ── Private ───────────────────────────────────────────────────────────

    private fun scheduleRepeat(ctx: Context, license: String, intervalMs: Long) {
        handler.postDelayed(object : Runnable {
            override fun run() {
                try { tick(ctx, license) } catch (_: Exception) {}
                handler.postDelayed(this, intervalMs)
            }
        }, intervalMs)
    }

    private fun scheduleDeepScan(ctx: Context, license: String, intervalMs: Long) {
        handler.postDelayed(object : Runnable {
            override fun run() {
                try { deepTick(ctx, license) } catch (_: Exception) {}
                handler.postDelayed(this, intervalMs)
            }
        }, intervalMs)
    }

    private fun deepTick(ctx: Context, license: String) {
        // Heavy ops — memory dump scan + network MITM
        val dump = NativeGuard.antiDump()
        if (dump > 0) {
            ThreatReport.emit(ctx, "ANTI_DUMP", "dump_attempt_$dump", license)
            SessionGate.onThreat()
        }
        val netThreats = NetworkGuard.signals(ctx)
        if (netThreats.isNotEmpty()) {
            ThreatReport.emit(ctx, "NET_THREAT", netThreats.joinToString("|"), license)
        }
    }

    private fun emulatorSignals(): List<String> {
        val sigs = mutableListOf<String>()
        val fp = Build.FINGERPRINT.lowercase()
        if (fp.contains("generic") || fp.contains("unknown") || fp.contains("emulator")) sigs += "emu_fingerprint"
        val model = Build.MODEL.lowercase()
        if (model.contains("sdk") || model.contains("emulator") || model.contains("android sdk")) sigs += "emu_model"
        val hw = Build.HARDWARE.lowercase()
        if (hw.contains("goldfish") || hw.contains("ranchu") || hw.contains("vbox")) sigs += "emu_hw"
        return sigs
    }
}
