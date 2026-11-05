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

1. Continue tracing notifier call sites and lifecycle hooks as the app evolves; the current PR wires module status, aggregate scan summaries and a five-minute authenticated-session heartbeat.
2. Add an isolated fake-transport test before claiming end-to-end Telegram delivery; the current contract test is source-level and does not contact Telegram.
3. Deploy the new `htdocs/api/app_event.php` endpoint to the active Unaux hosting account. The endpoint validates the authenticated session, HWID binding, active license, device-ban state, event allowlist, payload size and per-session rate limit.
4. The endpoint relays only bounded operational event summaries through the server-side Telegram helper. The helper now requires cURL TLS peer and hostname verification and fails closed; it no longer uses insecure TLS fallbacks.
5. Confirm the hosting PHP runtime has cURL enabled and that the live endpoint responds successfully to an authenticated test event. Repository source changes alone do not prove the live hosting copy has been deployed.
6. After CI produces a release artifact, inspect the APK for secrets, verify package/version/signature/alignment, then perform a real Android installation test.

This audit is source review only. The Kotlin notifier already contains a bounded operational-event queue and compatibility methods; this audit does not claim end-to-end Telegram delivery or Android build validation.

## PR #99 follow-up implementation

- Confirmed the Kotlin notifier source exists at `app/src/main/java/com/alvsia/pro/sec/TelegramNotifier.kt`.
- Kept the existing notifier API and added `MODULE_STATUS` and `HEARTBEAT` event types.
- Wired module status and scan aggregate summaries from `MainActivity.kt`; authenticated foreground sessions emit a low-volume heartbeat every five minutes.
- Added `tests/test_telegram_notifier_contract.py` to check the event registry, bounded queue/message sizes, redaction, selected-file reporting, and runtime wiring.
- Updated `.github/workflows/android-validation.yml` on both the PR branch and `main`: the default-branch workflow now explicitly includes the PR #99 branch in its push trigger and runs the notifier contract test.
- The app now sends allowlisted events through `PanelClient.sendOperationalEvent()` and the existing authenticated `PanelHolder.client`; no Telegram bot token or chat ID is used by the APK.
- The panel source now contains `htdocs/api/app_event.php`, which validates the session/HWID pair, active license, ban state, allowlisted event names, bounded payload and per-session rate limit before relaying a summary to Telegram.
- The live Unaux hosting copy has not been changed or verified from GitHub. Deploy `app_event.php` and the updated `config.php` to hosting before expecting end-to-end delivery.
- No Android build, signed APK, or device test is claimed until the workflow produces a successful run and artifacts.
