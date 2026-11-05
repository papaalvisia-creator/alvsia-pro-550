# ALVSIA PRO — Telegram Notification Audit

Audit date: 2026-11-06

## Scope

Reviewed the reference repository file `ALVISIA8/kumpulan-source-tool/ultra_notifications.py` at its current default-branch revision (blob `a97393266e94d3c096860c02906a23400d7c913b`). The application-side Kotlin source is present at `app/src/main/java/com/alvsia/pro/sec/TelegramNotifier.kt` (blob `542bc94fa3247f68b22428df73acc5dcbd9c2d9c`). The notifier was inspected along with `TacticalNotifier.kt`, `ThreatReport.kt`, and `panel/Vault.kt`.

## Findings in ultra_notifications.py

The script dynamically injects a notification block into another Python program and rewrites existing notification call sites. Its behavior includes:

- Telegram message delivery using a bot token and chat ID decrypted from a local configuration file.
- A hard-coded decryption password and embedding of the decrypted bot token/chat ID into generated source text.
- Public-IP lookup followed by IP geolocation, including city, region, country, latitude/longitude, ISP, organization, ASN, timezone and proxy/mobile/hosting indicators.
- Map, navigation, Street View and what3words links derived from the geolocation result.
- Session-start reporting containing device properties and license fields, including license key, expiry, seller and device limit.
- File-loaded reporting containing file name, full path, size, modification time and an MD5-derived identifier.
- Scan, patch, error and session-summary reporting, including paths, old/new URLs, method, device details and location.
- A printed claim of a location update every 30 seconds; this script itself does not show the implementation of that timer in the inserted block, so the actual periodic call path must be verified in the target program before asserting it runs.

## Disposition

- Preserve the ALVSIA Telegram notification integration for operational events: session lifecycle, tool completion, scan/patch summaries, error diagnostics and aggregate session counts.
- Keep the bot credential server-side or in protected runtime configuration; never generate source containing the token or embed it in the APK.
- Do not transmit license secrets, raw private file contents, unrestricted storage indexes, precise coordinates, or continuous location tracking as background telemetry.
- File-related notifications should be limited to the user-selected ALVSIA workspace item and operational metadata needed to identify the task; do not attach or upload the file itself by default.
- Location-related reporting is not part of the operational notification baseline. Network-derived IP/city or precise GPS data must not be silently collected or sent.
- Keep message formatting and the ALVSIA bot/channel identity independent of the data collection policy.

## Verification still required

1. Locate the actual Kotlin notifier source path in the repository tree or release source bundle.
2. Trace every call site, scheduler, worker and lifecycle hook for Telegram sends.
3. Compare the Kotlin implementation against the findings above, including any storage traversal, hashing, file upload, heartbeat and license/device reporting.
4. Add tests with a fake Telegram transport to verify allowed event payloads, redaction, size limits, failure handling and absence of secrets.
5. Verify the bot credential is supplied only through protected server/runtime configuration and is absent from source, generated artifacts, logs and APK contents.

This audit is source review only. The Kotlin notifier already contains a bounded operational-event queue and compatibility methods; this audit does not claim end-to-end Telegram delivery or Android build validation.
