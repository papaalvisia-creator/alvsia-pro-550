package com.alvsia.pro.panel

import okhttp3.CertificatePinner

/**
 * ALVSIA PRO — single-panel endpoint registry.
 *
 * The active panel is alvsiapanel.unaux.com. TLS pinning includes the current
 * leaf SPKI plus the supplied ZeroSSL intermediate and Sectigo root backups.
 * Android hostname and platform trust validation remain enabled.
 */
object Vault {
    private const val PANEL_ORIGIN = "https://alvsiapanel.unaux.com"
    private const val API_ROOT = "$PANEL_ORIGIN/api/"

    fun apiBase(): String = API_ROOT
    fun panelOrigin(): String = PANEL_ORIGIN
    fun pathCaptcha(): String = "captcha.php"
    fun pathConnect(): String = "connect.php"
    fun pathRefreshSession(): String = "refresh_session.php"
    fun pathGetAsset(): String = "get_asset.php"
    fun pathDownloadAsset(): String = "download_asset.php"
    fun pathSecurity(): String = "security_event.php"
    fun pathOperationGrant(): String = "operation_grant.php"

    /**
     * Current owner-supplied SPKI pins for the 2026-11-22 to 2027-02-20
     * server certificate, with long-lived CA backup pins for rotation.
     */
    fun certPinner(): CertificatePinner = CertificatePinner.Builder()
        .add("alvsiapanel.unaux.com", "sha256/3dKRo5uvtVM2x5/NJsOEKFEy803l0rPct3Jv0AoiukE=")
        .add("alvsiapanel.unaux.com", "sha256/xwyjb5aN7tSRWj02XSZa2cKGLxXLdKHUBfLT/7twjhQ=")
        .add("alvsiapanel.unaux.com", "sha256/sLVjNUaFYfW7n6EtgBeEpjOlcnBdNPMrZDRF36iwBdE=")
        .build()

    fun ua(): String = "ALVSIA-PRO/6.0.2-smart-premium (Android)"
    fun tgToken(): String = ""
    fun tgChatId(): String = ""
}
