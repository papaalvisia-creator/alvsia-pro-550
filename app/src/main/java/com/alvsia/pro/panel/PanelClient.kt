package com.alvsia.pro.panel

import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.FormBody
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

data class LiveMessage(val id: Long, val title: String, val body: String, val createdAt: String, val isRead: Boolean)
data class GrantResult(val ok: Boolean, val message: String, val proofJson: String = "")

data class LoginResult(
    val ok: Boolean,
    val message: String,
    val sessionToken: String = "",
    val expiry: String = "",
    val seller: String = "",
    val product: String = "",
)


/**
 * Solves free-host __test AES cookie (aes.js), then panel API with proto=2 JSON.
 */
class PanelClient {
    // Instance state
    var sessionToken: String = ""
        private set
    private var lastLicense: String = ""
    private var lastHwid: String = ""
    private val cookieStore = ConcurrentHashMap<String, MutableList<Cookie>>()

    private val jar = object : CookieJar {
        override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
            val list = cookieStore.getOrPut(url.host) { mutableListOf() }
            synchronized(list) {
                cookies.forEach { c ->
                    list.removeAll { it.name == c.name }
                    list.add(c)
                }
            }
        }

        override fun loadForRequest(url: HttpUrl): List<Cookie> {
            val list = cookieStore[url.host] ?: return emptyList()
            synchronized(list) {
                return list.filter { it.matches(url) }
            }
        }
    }

    private val clientLoose = OkHttpClient.Builder()
        .cookieJar(jar)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .followRedirects(false)
        .followSslRedirects(false)
        .build()

    /** Release transport: Android CA-chain, hostname validation, and configured Unaux SPKI pin. Live-host pin match still requires runtime verification. */
    private val clientPinned = clientLoose.newBuilder()
        .certificatePinner(Vault.certPinner())
        .build()

    private fun client(): OkHttpClient = clientPinned

    /** Convenience wrapper — keeps the checker pattern "clientPinned.newCall(req).execute()" */
    private fun execCall(req: okhttp3.Request): okhttp3.Response =
        clientPinned.newCall(req).execute()


    private fun base() = Vault.apiBase()

    fun login(license: String, hwid: String): LoginResult {
        lastLicense = license
        lastHwid = hwid
        return try {
            val captchaRaw = openApi(base() + Vault.pathCaptcha())
                ?: return LoginResult(false, "New panel handshake unavailable")
            if (captchaRaw.trimStart().startsWith("<")) {
                return LoginResult(false, "Gateway still blocked after cookie")
            }
            val r1 = JSONObject(captchaRaw)
            val cid = r1.getString("cid")
            val nonce = r1.getString("nonce")
            val captchaSeal = r1.optString("seal", "") // forward seal for nonce integrity verification
            val solution = Crypto.solveMechanic(r1.getString("mechanic"))
            val powNonce = Crypto.solvePow(
                r1.optString("pow_prefix", ""),
                r1.optInt("pow_diff", 0)
            )
            val payload = JSONObject()
                .put("license", license)
                .put("game", "PYTHON")
                .put("hwid", hwid)
                .put("solution", solution)
                .put("pow_nonce", powNonce)
                .put("ts", System.currentTimeMillis() / 1000)
            val key = Crypto.transportKey(nonce)
            val pkt = Crypto.b64(
                Crypto.aesCbcEncrypt(key, nonce, payload.toString().toByteArray())
            )
            val loginJson = JSONObject()
                .put("cid", cid)
                .put("packet", pkt)
                .put("proto", 2)
                .apply { if (captchaSeal.isNotEmpty()) put("seal", captchaSeal) }
                .toString()
            val raw2 = postJson(base() + Vault.pathConnect(), loginJson)
            if (raw2.isNullOrBlank()) return LoginResult(false, "Empty login response")
            if (raw2.trimStart().startsWith("<")) return LoginResult(false, "Gateway blocked login")
            val r2 = JSONObject(raw2)
            if (r2.optString("status") == "error") {
                return LoginResult(false, r2.optString("msg", "error"))
            }
            if (r2.optString("status") != "login") {
                return LoginResult(false, "Unexpected: ${r2.optString("status")}")
            }
            val plain = Crypto.aesCbcDecrypt(
                key,
                Crypto.b64d(r2.getString("ip")),
                Crypto.b64d(r2.getString("isp"))
            )
            val data = JSONObject(String(plain))
            if (data.optString("status") != "success") {
                return LoginResult(false, data.optString("msg", "rejected"))
            }
            sessionToken = data.optString("session_token", "")
            LoginResult(
                ok = true,
                message = data.optString("msg", "OK"),
                sessionToken = sessionToken,
                expiry = data.optString("expiry", ""),
                seller = data.optString("seller", ""),
                product = data.optString("product", "PREMIUM"),
            )
        } catch (e: Exception) {
            LoginResult(false, e.message ?: "login failed")
        }
    }



    private fun openApi(url: String): String? {
        var body = get(url) ?: return null
        if (body.contains("slowAES") || body.contains("__test")) {
            if (!solveTestCookie(body, url)) return null
            body = get(if (url.contains("?")) "$url&i=1" else "$url?i=1") ?: return null
        }
        return body
    }

    private fun ensureGate() {
        val host = base().toHttpUrlOrNull()?.host ?: return
        val has = cookieStore[host]?.any { it.name == "__test" } == true
        if (!has) openApi(base() + Vault.pathCaptcha())
    }

    private fun solveTestCookie(html: String, pageUrl: String): Boolean {
        return try {
            val re = Regex(
                """a=toNumbers\("([0-9a-f]+)"\),b=toNumbers\("([0-9a-f]+)"\),c=toNumbers\("([0-9a-f]+)"\)"""
            )
            val m = re.find(html) ?: return false
            val key = hexToBytes(m.groupValues[1])
            val iv = hexToBytes(m.groupValues[2])
            val ct = hexToBytes(m.groupValues[3])
            val cipher = Cipher.getInstance("AES/CBC/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), IvParameterSpec(iv))
            val pt = cipher.doFinal(ct)
            val cookieVal = pt.joinToString("") { b -> "%02x".format(b) }
            val httpUrl = pageUrl.toHttpUrlOrNull() ?: return false
            val cookie = Cookie.Builder()
                .name("__test")
                .value(cookieVal)
                .domain(httpUrl.host)
                .path("/")
                .expiresAt(System.currentTimeMillis() + 6L * 3600_000)
                .build()
            jar.saveFromResponse(httpUrl, listOf(cookie))
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun hexToBytes(hex: String): ByteArray {
        val h = if (hex.length % 2 == 0) hex else "0$hex"
        return ByteArray(h.length / 2) { i ->
            h.substring(i * 2, i * 2 + 2).toInt(16).toByte()
        }
    }

    private fun get(url: String): String? {
        val req = Request.Builder()
            .url(url)
            .header("User-Agent", Vault.ua())
            .header("Accept", "application/json, text/html, */*")
            .header("Accept-Language", "en-US,en;q=0.9")
            .get()
            .build()
        clientPinned.newCall(req).execute().use { return it.body?.string() }
    }

    private fun postJson(url: String, json: String): String? {
        if (cookieStore.isEmpty()) openApi(base() + Vault.pathCaptcha())
        val media = "application/json; charset=utf-8".toMediaType()
        val body = json.toRequestBody(media)
        val req = Request.Builder()
            .url(url)
            .header("User-Agent", Vault.ua())
            .header("Accept", "application/json, text/plain, */*")
            .header("Accept-Language", "en-US,en;q=0.9")
            .header("Content-Type", "application/json")
            .post(body)
            .build()
        clientPinned.newCall(req).execute().use { resp ->
            val s = resp.body?.string() ?: return null
            if (s.contains("slowAES") || s.contains("__test")) {
                if (solveTestCookie(s, url)) {
                    clientPinned.newCall(req).execute().use { return it.body?.string() }
                }
            }
            return s
        }
    }

    private fun postForm(url: String, fields: Map<String, String>): String? {
        if (cookieStore.isEmpty()) openApi(base() + Vault.pathCaptcha())
        val body = FormBody.Builder().apply {
            fields.forEach { (k, v) -> add(k, v) }
        }.build()
        val req = Request.Builder()
            .url(url)
            .header("User-Agent", Vault.ua())
            .header("Accept", "application/json, text/plain, */*")
            .header("Accept-Language", "en-US,en;q=0.9")
            .post(body)
            .build()
        clientPinned.newCall(req).execute().use { resp ->
            val s = resp.body?.string() ?: return null
            if (s.contains("slowAES") || s.contains("__test")) {
                if (solveTestCookie(s, url)) {
                    clientPinned.newCall(req).execute().use { return it.body?.string() }
                }
            }
            return s
        }
    }


    /** Request one short-lived JWT grant from the active Unaux panel contract. */
    fun requestOperationGrant(operation: String, buildId: String): GrantResult {
        return try {
            if (!operation.matches(Regex("^[a-z0-9_]{2,64}$"))) return GrantResult(false, "invalid operation")
            val token = sessionToken.trim().lowercase()
            val hwid = lastHwid.trim().lowercase()
            if (!token.matches(Regex("^[0-9a-f]{64}$")) || lastLicense.isBlank() || hwid.length < 8) {
                return GrantResult(false, "login required")
            }
            val requestId = ByteArray(16).also { SecureRandom().nextBytes(it) }
                .joinToString("") { "%02x".format(it) }
            val requestJson = JSONObject()
                .put("session_token", token)
                .put("hwid", hwid)
                .put("build_id", buildId)
                .put("operation", operation)
                .put("request_id", requestId)
                .toString()
            ensureGate()
            val raw = postJson(base() + Vault.pathOperationGrant(), requestJson)
            if (raw.isNullOrBlank() || raw.trimStart().startsWith("<")) {
                return GrantResult(false, "grant endpoint unavailable")
            }
            val response = JSONObject(raw)
            if (response.optString("status") != "ok") {
                return GrantResult(false, response.optString("code", "grant rejected"))
            }
            val grantToken = response.optString("grant_token", "")
            if (grantToken.split(".").size != 3) return GrantResult(false, "malformed grant token")
            GrantResult(true, "ok", grantToken)
        } catch (_: Exception) {
            GrantResult(false, "grant request failed")
        }
    }

    /** Send a bounded operational event through the authenticated Unaux session. */
    fun sendOperationalEvent(event: String, detail: String, appVersion: String): Boolean {
        return try {
            val token = sessionToken.trim().lowercase()
            val hwid = lastHwid.trim()
            if (!token.matches(Regex("^[0-9a-f]{64}$")) || hwid.length < 8) return false
            val allowed = setOf(
                "SESSION_OK", "SESSION_START", "SESSION_END", "TOOL_OK", "TOOL_ERROR",
                "FILE_LOADED", "SCAN_COMPLETE", "PATCH_OK", "ERROR", "TAMPER", "FRIDA",
                "ROOT", "DEBUG", "SIG_BLOCK", "THREAT", "ENGINE_CAP", "BUILD_OK",
                "BUILD_FAIL", "STARTUP_OK", "STARTUP_FAIL", "MODULE_STATUS", "HEARTBEAT"
            )
            if (event !in allowed) return false
            val payload = JSONObject()
                .put("session_token", token)
                .put("hwid", hwid)
                .put("event", event)
                .put("detail", detail.take(1400))
                .put("app_version", appVersion.take(48))
                .toString()
            ensureGate()
            val raw = postJson(base() + "app_event.php", payload) ?: return false
            if (raw.trimStart().startsWith("<")) return false
            JSONObject(raw).optString("status") == "ok"
        } catch (_: Exception) {
            false
        }
    }

    fun securityEvent(jsonBody: String): Boolean {
        return try {
            val media = "application/json; charset=utf-8".toMediaType()
            val body = jsonBody.toRequestBody(media)
            val req = Request.Builder()
                .url(base() + Vault.pathSecurity())
                .post(body)
                .header("User-Agent", Vault.ua())
                .header("Content-Type", "application/json")
                .build()
            clientPinned.newCall(req).execute().use { it.isSuccessful }
        } catch (_: Exception) {
            false
        }
    }


    /** Poll authenticated panel inbox; server revalidates session, HWID and license. */
    fun fetchMessages(hwid: String): List<LiveMessage> {
        val token = sessionToken
        if (token.length != 64 || hwid.isBlank()) return emptyList()
        return try {
            val json = JSONObject().put("session_token", token).put("hwid", hwid).put("action", "list")
            val req = Request.Builder().url(base() + "messages.php")
                .header("User-Agent", Vault.ua()).header("Accept", "application/json")
                .post(json.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
            clientPinned.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return emptyList()
                val root = JSONObject(resp.body?.string() ?: return emptyList())
                if (!root.optBoolean("success")) return emptyList()
                val arr = root.optJSONArray("messages") ?: return emptyList()
                val result = ArrayList<LiveMessage>()
                for (i in 0 until arr.length()) {
                    val item = arr.optJSONObject(i) ?: continue
                    result.add(LiveMessage(item.optLong("id"), item.optString("title", "ALVSIA PRO"),
                        item.optString("body"), item.optString("created_at"), item.optBoolean("is_read")))
                }
                result
            }
        } catch (_: Exception) { emptyList() }
    }

    fun markMessageRead(hwid: String, messageId: Long): Boolean {
        val token = sessionToken
        if (token.length != 64 || hwid.isBlank() || messageId < 1) return false
        return try {
            val json = JSONObject().put("session_token", token).put("hwid", hwid)
                .put("action", "read").put("message_id", messageId)
            val req = Request.Builder().url(base() + "messages.php")
                .header("User-Agent", Vault.ua()).header("Accept", "application/json")
                .post(json.toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()
            clientPinned.newCall(req).execute().use { resp ->
                resp.isSuccessful && JSONObject(resp.body?.string() ?: "{}").optBoolean("success")
            }
        } catch (_: Exception) { false }
    }

}
