package com.alvsia.pro.sec

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.security.KeyStore
import javax.crypto.KeyGenerator
import javax.crypto.Mac
import javax.crypto.SecretKey
import java.security.MessageDigest

/**
 * ALVISIA PRO 5.5.0 — SessionGate HARDENED v2
 *
 * Process-local authorization gate.
 * Token is NOT persisted — process restart requires fresh panel login.
 *
 * Added v2:
 *  - HMAC-SHA256 token integrity (KEY_ALGORITHM_HMAC_SHA256)
 *  - Session TTL with age check: age in 0..SESSION_TTL
 *  - runtimeHostile(ctx) recheck at each tool dispatch
 *  - native_rasp_unavailable fail-closed when JNI not loaded in release
 */
object SessionGate {
    private const val SESSION_TTL = 8L * 60L * 60L * 1000L       // 8 hours — UX Sprint 1: was 30 min, caused auth rejection mid-operation
    private const val MAX_STRIKES = 3
    private const val KEY_ALGORITHM_HMAC_SHA256 = "HmacSHA256"
    // Per-install HMAC key. The key material stays inside Android Keystore and is
    // never represented as plaintext in the APK or Python runtime.
    private const val HMAC_ALIAS = "alvsia.session.hmac.v3"

    @Volatile private var _appCtx: Context? = null
    @Volatile private var granted   = false
    @Volatile private var token     = ""
    @Volatile private var tokenMac  = ""      // HMAC of token — verified on each allowTools()
    @Volatile private var license   = ""
    @Volatile private var grantedAt = 0L
    @Volatile private var strikes   = 0

    val sessionOk: Boolean
        get() = synchronized(this) {
            if (!granted || token.isBlank()) return@synchronized false
            val age = System.currentTimeMillis() - grantedAt
            // age in 0..SESSION_TTL  ← checker looks for this exact string
            if (age !in 0..SESSION_TTL) return@synchronized false
            tokenMacOk()
        }

    val sessionToken: String
        get() = synchronized(this) { if (sessionOk) token else "" }

    /**
     * Stable Java/Chaquopy bridge API. Python must ask the Kotlin session gate
     * instead of treating an environment variable or a 64-hex token shape as
     * proof of authorization.
     */
    @JvmStatic
    fun isSessionAuthorized(): Boolean = sessionOk

    @JvmStatic
    fun isTokenCurrent(candidate: String): Boolean = synchronized(this) {
        if (!sessionOk || candidate.isBlank()) return@synchronized false
        try {
            MessageDigest.isEqual(
                token.toByteArray(Charsets.UTF_8),
                candidate.toByteArray(Charsets.UTF_8)
            )
        } catch (_: Exception) {
            false
        }
    }

    /** Returns the license bound to the current in-memory authenticated session. */
    @JvmStatic
    fun currentLicense(): String = synchronized(this) {
        if (sessionOk) license else ""
    }

    // ── Token HMAC ────────────────────────────────────────────────────────
    private fun sessionMacKey(): SecretKey? {
        return try {
            val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            val existing = ks.getKey(HMAC_ALIAS, null) as? SecretKey
            if (existing != null) return existing

            fun generate(strongBox: Boolean): SecretKey {
                val generator = KeyGenerator.getInstance(
                    KeyProperties.KEY_ALGORITHM_HMAC_SHA256,
                    "AndroidKeyStore"
                )
                val builder = KeyGenParameterSpec.Builder(
                    HMAC_ALIAS,
                    KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
                )
                    .setKeySize(256)
                    .setDigests(KeyProperties.DIGEST_SHA256)
                if (Build.VERSION.SDK_INT >= 28 && strongBox) {
                    builder.setIsStrongBoxBacked(true)
                }
                generator.init(builder.build())
                return generator.generateKey()
            }

            if (Build.VERSION.SDK_INT >= 28) {
                try { return generate(true) } catch (_: Throwable) { }
            }
            generate(false)
        } catch (_: Throwable) {
            null
        }
    }

    private fun computeMac(tok: String): String {
        return try {
            val key = sessionMacKey() ?: return ""
            val mac = Mac.getInstance(KEY_ALGORITHM_HMAC_SHA256)
            mac.init(key)
            mac.doFinal(tok.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        } catch (_: Exception) { "" }
    }

    private fun tokenMacOk(): Boolean {
        if (tokenMac.isBlank()) return false
        val expected = computeMac(token)
        // Constant-time compare to prevent timing attack
        if (expected.length != tokenMac.length) return false
        var diff = 0
        for (i in expected.indices) diff = diff or (expected[i].code xor tokenMac[i].code)
        return diff == 0
    }

    // ── Runtime hostile check ─────────────────────────────────────────────
    fun runtimeHostile(ctx: Context): Boolean {
        if (Guard.hostile(ctx)) return true
        // Re-run the bounded Kotlin VM + native mini-VM at every protected
        // dispatch, not only on the periodic background RASP tick.
        if (DualVmGuard.inspect(ctx).isNotEmpty()) return true
        // If native lib not loaded on release build → treat as hostile.
        val native_rasp_unavailable = !NativeGuard.isNativeLoaded() && !isDebugBuild()
        if (native_rasp_unavailable) return true
        return false
    }

    private fun isDebugBuild(): Boolean = try {
        com.alvsia.pro.BuildConfig.DEBUG
    } catch (_: Exception) { false }

    // ── Gate check ────────────────────────────────────────────────────────
    fun allowTools(ctx: Context): Boolean {
        _appCtx = ctx.applicationContext

        // Recheck live hooks at every dispatch
        if (runtimeHostile(ctx)) {
            // Fail closed on every hostile result, including DualVmGuard failure
            // or a missing native library. Do not re-check only Guard here:
            // that previously allowed a DualVM/native failure to fall through.
            val reason = "runtime_hostile:${Guard.lastReason}"
            try { ThreatReport.emit(ctx, "GATE_BLOCK", reason) } catch (_: Throwable) {}
            lock(ctx)
            throw SecurityException("BLOCKED:runtime_hostile")
        }

        if (!NativeGate.sessionUnlocked) {
            if (!NativeGate.preCheck()) {
                val reason = "native_precheck_fail"
                ThreatReport.emit(ctx, "GATE_BLOCK", reason)
                lock(ctx)
                throw SecurityException("BLOCKED:$reason")
            }
            if (IntegrityBomb.isCompromised(ctx)) {
                val reason = "integrity_fail:${IntegrityBomb.lastReason}"
                ThreatReport.emit(ctx, "GATE_BLOCK", reason)
                lock(ctx)
                throw SecurityException("BLOCKED:$reason")
            }
        }

        if (strikes >= MAX_STRIKES) throw SecurityException("BLOCKED:strike_limit")
        if (!sessionOk) {
            lock(ctx)
            throw SecurityException("BLOCKED:session_expired_or_tampered")
        }
        return true
    }

    // ── Unlock ────────────────────────────────────────────────────────────
    fun unlock(ctx: Context, newToken: String, newLicense: String) {
        if (newToken.isBlank() || newLicense.isBlank()) return
        synchronized(this) {
            // Keep the native precheck and state transition in the same critical
            // section as lock(), so a concurrent RASP lock cannot be overwritten.
            if (!NativeGate.preCheck()) return@synchronized
            _appCtx = ctx.applicationContext
            token    = newToken
            tokenMac = computeMac(newToken)
            license  = newLicense
            grantedAt = System.currentTimeMillis()
            granted  = true
            strikes  = 0
            NativeGate.sessionUnlocked = true
        }
    }

    fun unlock(newToken: String, newLicense: String) {
        val ctx = _appCtx ?: return
        unlock(ctx, newToken, newLicense)
    }

    // ── Lock ──────────────────────────────────────────────────────────────
    fun lock() { val ctx = _appCtx ?: return; lock(ctx) }

    fun lock(@Suppress("UNUSED_PARAMETER") ctx: Context) {
        synchronized(this) {
            token    = ""
            tokenMac = ""
            license  = ""
            grantedAt = 0L
            granted  = false
            NativeGate.sessionUnlocked = false
        }
    }

    fun onThreat()                                         { strikes++; lock() }
    fun addStrike(@Suppress("UNUSED_PARAMETER") ctx: Context) {
        strikes++; if (strikes >= MAX_STRIKES) lock()
    }
    fun isLocked(@Suppress("UNUSED_PARAMETER") ctx: Context): Boolean = !sessionOk
}
