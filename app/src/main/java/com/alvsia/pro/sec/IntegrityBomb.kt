package com.alvsia.pro.sec

import android.content.Context
import android.content.pm.PackageManager
import com.alvsia.pro.BuildConfig
import java.io.File
import java.security.MessageDigest

data class IntegrityResult(val clean: Boolean, val reasons: List<String>)

object IntegrityBomb {

    private val EXPECTED_CERT_SHA256 = BuildConfig.CERT_SHA256
    // These bounds apply to the complete installed APK, not to a DEX entry.
    // XopProtector adds encrypted payload assets, so a valid protected APK can
    // exceed 40 MB while its shell DEX remains small. DEX structure, count and
    // payload integrity are checked separately by DexGuardian below.
    private const val APK_MIN_BYTES = 1_000_000L
    private const val APK_MAX_BYTES = 100_000_000L // 100 MB upper sanity bound

    private var _lastReason = ""
    val lastReason: String get() = _lastReason

    /** New API — used by SessionGate */
    fun isCompromised(ctx: Context): Boolean {
        val result = evaluate(ctx)
        _lastReason = result.reasons.joinToString(",")
        return !result.clean
    }

    /** Legacy API — used by RaspEngine */
    fun evaluate(ctx: Context): IntegrityResult {
        val reasons = mutableListOf<String>()

        if (!certOk(ctx)) reasons += "cert_mismatch"
        if (!apkSizeOk(ctx)) reasons += "apk_size_bad"
        // Sprint 1 — Layer 5: DEX hash + count verification via DexGuardian
        val dexReport = DexGuardian.evaluate(ctx)
        if (!dexReport.clean) {
            reasons += dexReport.reasons.map { "dex_$it" }
        }
        // Work profiles / secondary Android users are legitimate environments.
        // Do not treat userId > 0 alone as APK compromise or hard-block the session.

        _lastReason = reasons.joinToString(",")
        return IntegrityResult(clean = reasons.isEmpty(), reasons = reasons)
    }

    private fun certOk(ctx: Context): Boolean {
        return try {
            @Suppress("DEPRECATION")
            val sig = ctx.packageManager
                .getPackageInfo(ctx.packageName, PackageManager.GET_SIGNATURES)
                .signatures[0]
            val md = MessageDigest.getInstance("SHA-256")
            val digest = md.digest(sig.toByteArray())
            val hex = digest.joinToString("") { "%02x".format(it) }
            hex.equals(EXPECTED_CERT_SHA256, ignoreCase = true)
        } catch (_: Exception) { false }
    }

    /** Sanity-check the complete installed APK file. This is deliberately not
     * named or treated as a DEX-size check: encrypted Xop assets contribute to
     * APK size, while DexGuardian validates the actual DEX entries and payload.
     */
    private fun apkSizeOk(ctx: Context): Boolean {
        return try {
            val apk = File(ctx.applicationInfo.sourceDir)
            apk.isFile && apk.length() in APK_MIN_BYTES..APK_MAX_BYTES
        } catch (_: Exception) {
            false
        }
    }

    private fun isClone(ctx: Context): Boolean {
        // userId > 0 means work profile or clone space
        val userId = ctx.applicationInfo.uid / 100_000
        return userId > 0
    }
}
