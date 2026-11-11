package com.alvsia.pro.sec

import android.content.Context
import com.alvsia.pro.BuildConfig

/**
 * ALVSIA Security Fabric — seven-layer decision model.
 *
 * The fabric orchestrates existing security controls instead of replacing them.
 *
 * 1 BUILD_TRUST      release/build configuration sanity
 * 2 ARTIFACT_TRUST   installed APK + DEX integrity
 * 3 CHANNEL_TRUST    network guard health
 * 4 CRYPTO_TRUST     native security substrate availability
 * 5 CODE_TRUST       runtime/native integrity
 * 6 ENVIRONMENT      high-confidence instrumentation evidence
 * 7 RESPONSE         accumulated risk / degradation state
 */
data class SecuritySnapshot(
    val allowed: Boolean,
    val score: Int,
    val hardReasons: List<String>,
    val softReasons: List<String>,
    val layers: Map<String, Boolean>
)

object SecurityFabric {
    fun evaluate(ctx: Context): SecuritySnapshot {
        val hard = mutableListOf<String>()
        val soft = mutableListOf<String>()
        val layers = linkedMapOf<String, Boolean>()

        val buildOk = BuildConfig.APPLICATION_ID == "com.alvsia.pro" &&
            BuildConfig.CERT_SHA256.matches(Regex("^[0-9a-fA-F]{64}$")) &&
            BuildConfig.VERSION_CODE >= 97
        layers["BUILD_TRUST"] = buildOk
        if (!buildOk) hard += "fabric_build_trust"

        val artifact = IntegrityBomb.evaluate(ctx)
        val artifactOk = artifact.clean
        layers["ARTIFACT_TRUST"] = artifactOk
        if (!artifactOk) hard += artifact.reasons.map { "fabric_artifact_" + it }

        val channelOk = NetworkGuard.net_guard(ctx)
        layers["CHANNEL_TRUST"] = channelOk
        if (!channelOk) soft += "fabric_network_guard_unavailable"

        val cryptoOk = BuildConfig.DEBUG || NativeGuard.isNativeLoaded()
        layers["CRYPTO_TRUST"] = cryptoOk
        if (!cryptoOk) hard += "fabric_native_security_missing"

        val guardHostile = Guard.hostile(ctx)
        val vmFailures = DualVmGuard.inspect(ctx)
        val codeOk = !guardHostile && vmFailures.isEmpty()
        layers["CODE_TRUST"] = codeOk
        if (guardHostile) hard += "fabric_" + Guard.lastReason.ifBlank { "runtime_guard" }
        if (vmFailures.isNotEmpty()) hard += vmFailures.map { "fabric_" + it }

        val instrumentation = FridaProbe.signals()
        val environmentSignals = instrumentation.filter {
            it.startsWith("maps:") || it.startsWith("tracer_pid:")
        }
        val foreignExec = RuntimeMappingGuard.signals(ctx)
        layers["ENVIRONMENT"] = environmentSignals.isEmpty() && foreignExec.isEmpty()
        if (environmentSignals.isNotEmpty()) hard += environmentSignals.map { "fabric_" + it }
        if (foreignExec.isNotEmpty()) hard += foreignExec.map { "fabric_" + it }

        val responseOk = !Guard.degraded
        layers["RESPONSE"] = responseOk
        if (!responseOk) soft += "fabric_degraded"

        val score = hard.size * 100 + soft.size * 5
        return SecuritySnapshot(
            allowed = hard.isEmpty(),
            score = score,
            hardReasons = hard.distinct(),
            softReasons = soft.distinct(),
            layers = layers
        )
    }
}
