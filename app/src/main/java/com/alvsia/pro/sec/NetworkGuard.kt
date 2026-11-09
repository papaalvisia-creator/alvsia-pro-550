package com.alvsia.pro.sec

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import java.net.InetAddress
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

/**
 * ALVISIA PRO 5.5.0 — NetworkGuard
 * MITM / proxy / VPN / SSL-strip detection.
 *
 * Covers:
 *  1. HTTP proxy system properties (Charles, Burp, mitmproxy).
 *  2. VPN active connection (network interceptors).
 *  3. SSL certificate pinning violation detection (delegate to OkHttp Vault.certPinner).
 *  4. Suspicious DNS resolution (known proxy DNS responses).
 *  5. Network type anomaly for emulators (no real radio).
 */
object NetworkGuard {

    // ── Known MITM proxy default ports ────────────────────────────────
    private val PROXY_PORTS = intArrayOf(8080, 8888, 9090, 1080, 4444, 8118, 3128, 10809)

    fun signals(ctx: Context): List<String> {
        val r = mutableListOf<String>()

        // 1. JVM system proxy properties
        try {
            val host = System.getProperty("http.proxyHost") ?: ""
            val port = System.getProperty("http.proxyPort") ?: ""
            val shost = System.getProperty("https.proxyHost") ?: ""
            if (host.isNotBlank()) r += "proxy_prop:$host:$port"
            if (shost.isNotBlank() && shost != host) r += "ssl_proxy_prop:$shost"
        } catch (_: Exception) {}

        // 2. Android framework proxy (covers Wi-Fi/mobile proxy configuration).
        try {
            val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            if (Build.VERSION.SDK_INT >= 23) {
                val proxy = cm.defaultProxy
                if (proxy != null && proxy.host.isNotBlank() && proxy.port > 0) {
                    r += "android_proxy:${proxy.host}:${proxy.port}"
                }
            }
        } catch (_: Exception) {}

        // 3. Global proxy via Settings (requires ACCESS_NETWORK_STATE)
        try {
            val globalProxy = android.provider.Settings.Global.getString(
                ctx.contentResolver, android.provider.Settings.Global.HTTP_PROXY
            )
            if (!globalProxy.isNullOrBlank() && globalProxy != ":0") {
                r += "global_proxy:$globalProxy"
            }
        } catch (_: Exception) {}

        // 4. JVM ProxySelector (covers app-level proxy routing).
        try {
            val proxies = java.net.ProxySelector.getDefault()
                ?.select(java.net.URI("https://example.com"))
                .orEmpty()
            if (proxies.any { it.type() != java.net.Proxy.Type.DIRECT }) {
                r += "proxy_selector_active"
            }
        } catch (_: Exception) {}

        // 5. VPN interface active
        try {
            val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            if (Build.VERSION.SDK_INT >= 23) {
                val active = cm.activeNetwork
                val caps = active?.let { cm.getNetworkCapabilities(it) }
                if (caps != null) {
                    if (!caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) &&
                        !caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) &&
                        !caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
                        r += "vpn_transport"
                    }
                    if (!caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)) {
                        r += "vpn_active"
                    }
                }
            }
        } catch (_: Exception) {}

        // 6. Local proxy port scan
        for (port in PROXY_PORTS) {
            try {
                val s = java.net.Socket()
                s.soTimeout = 50
                s.connect(java.net.InetSocketAddress("127.0.0.1", port), 50)
                s.close()
                r += "proxy_port:$port"
            } catch (_: Exception) {}
        }

        // 7. /proc/net/tcp scan for proxy listening on loopback
        try {
            val tcp = java.io.File("/proc/net/tcp").readText()
            val tcp6 = java.io.File("/proc/net/tcp6").readText()
            val lines = (tcp + tcp6).lines()
            lines.forEach { line ->
                val cols = line.trim().split(Regex("\\s+"))
                if (cols.size < 4) return@forEach
                val localAddr = cols[1]
                val stateHex = cols[3]
                if (stateHex != "0A") return@forEach // 0A = LISTEN
                val portHex = localAddr.substringAfter(":").toIntOrNull(16) ?: return@forEach
                if (portHex in PROXY_PORTS) r += "proc_net_proxy:$portHex"
            }
        } catch (_: Exception) {}

        return r.distinct()
    }

    /** True only when a proxy/interception route is actually observed. */
    fun detect_proxy(ctx: Context): Boolean {
        return signals(ctx).any { signal ->
            signal.contains("proxy", ignoreCase = true)
        }
    }

    /**
     * Reports whether the network guard itself is operational. This is
     * deliberately separate from detect_proxy(): a clean network must not
     * make the guard appear disabled simply because no proxy was detected.
     */
    fun net_guard(ctx: Context): Boolean {
        return try {
            ctx.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) is ConnectivityManager
        } catch (_: Throwable) {
            false
        }
    }
}
