package com.alvsia.pro.sec

import android.content.Context
import android.os.Build
import android.os.Debug
import com.alvsia.pro.tool.RamToolVault
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

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
    /** Security scans must never run on the Compose/main thread. */
    private val scheduler = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "alvsia-rasp").apply { isDaemon = true }
    }
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
        // All periodic security work runs on a dedicated background executor.
        // The previous main-looper scheduling could perform /proc, DEX, maps and
        // network checks on the UI thread while a heavy tool was running.
        scheduler.execute { safeTick(app, license) }
        scheduler.scheduleAtFixedRate({ safeTick(app, license) }, 4_000L, 4_000L, TimeUnit.MILLISECONDS)
        scheduler.scheduleAtFixedRate({ safeDeepTick(app, license) }, 30_000L, 30_000L, TimeUnit.MILLISECONDS)
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
            try {
                SessionGate.onThreat()
                RamToolVault.wipeAll()
            } catch (_: Exception) {}
        }

        // Soft: degrade + report
        if (soft.isNotEmpty()) {
            Guard.degraded = true
            // FridaProbe and AntiHook inspect the same /proc/self/maps entry.
            // Collapse their differently-prefixed aliases into one soft signal.
            val detail = soft.map { signal ->
                if (signal.startsWith("antihook_hooklib:")) signal.removePrefix("antihook_")
                else signal
            }.distinct().sorted().joinToString("|")
            if (shouldReportSoft(detail, System.currentTimeMillis())) {
                try { ThreatReport.emit(ctx, "SOFT_THREAT", detail, license) } catch (_: Exception) {}
            }
        } else {
            shouldReportSoft("", System.currentTimeMillis())
        }
    }

    // ── Private ───────────────────────────────────────────────────────────

    private fun safeTick(ctx: Context, license: String) {
        try { tick(ctx, license) } catch (_: Throwable) { }
    }

    private fun safeDeepTick(ctx: Context, license: String) {
        try { deepTick(ctx, license) } catch (_: Throwable) { }
    }

    private fun deepTick(ctx: Context, license: String) {
        // Heavy ops — memory dump scan + network MITM. This runs on the
        // dedicated RASP executor, never on the Compose/main thread.
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
