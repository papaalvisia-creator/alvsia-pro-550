#!/usr/bin/env python3
"""Non-invasive release checks for ALVSIA PRO. Does not modify source or permissions."""
from pathlib import Path
import base64
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)

catalog = ROOT / "app/src/main/java/com/alvsia/pro/tool/ToolCatalog.kt"
manifest = ROOT / "app/src/main/AndroidManifest.xml"
network = ROOT / "app/src/main/res/xml/network_security_config.xml"
profile = ROOT / "app/src/main/java/com/alvsia/pro/ui/profile/ProfileScreen.kt"
submenus = ROOT / "app/src/main/java/com/alvsia/pro/tool/SubMenus.kt"
release_workflow = ROOT / ".github/workflows/alvsia-final-release.yml"

for file in (catalog, manifest, network, profile, submenus, release_workflow):
    if not file.is_file():
        fail(f"required file missing: {file.relative_to(ROOT)}")

catalog_text = catalog.read_text(encoding="utf-8")
ids = [int(x) for x in re.findall(r"ToolItem\(\s*(\d+)\s*,", catalog_text)]
if ids != list(range(1, 11)):
    fail(f"catalog must define Smart module IDs 1..10 in order; found {ids}")
print("PASS: catalog defines all ten Smart module IDs")

submenu_text = submenus.read_text(encoding="utf-8")
submenu_ids = re.findall(r'SubTool\(\s*"([^"]+)"', submenu_text)
if len(submenu_ids) != 59 or len(set(submenu_ids)) != 59:
    fail(f"catalog must define 59 unique submenu IDs; found {len(submenu_ids)}")
print("PASS: catalog defines 59 unique submenu IDs")

profile_text = profile.read_text(encoding="utf-8")
if "SMART ENGINE LAB" not in profile_text or "toolCount.toString()" not in profile_text:
    fail("profile must expose the 10-menu Smart catalog")
print("PASS: profile exposes the 10-menu Smart catalog")

workflow_text = release_workflow.read_text(encoding="utf-8")
for flag in ("--v1-signing-enabled false", "--v2-signing-enabled true", "--v3-signing-enabled true"):
    if flag not in workflow_text:
        fail(f"final release workflow must explicitly set {flag}")
print("PASS: final release workflow explicitly disables v1 and enables v2/v3 signing")

upload_section = workflow_text.split("      - name: Upload final APK and audit", 1)[1]
if "ALVSIA_SMART_PREMIUM_6.0.2_unsigned.apk" in upload_section:
    fail("final workflow must not publish the unsigned baseline APK")
if "ALVSIA_SMART_PREMIUM_6.0.2-xop-signed.apk" not in upload_section:
    fail("final workflow must publish the single signed XOP APK")
print("PASS: final workflow publishes one signed APK only")

manifest_text = manifest.read_text(encoding="utf-8")
for required in (
    'android:allowBackup="false"',
    'android.permission.INTERNET',
    'android.permission.MANAGE_EXTERNAL_STORAGE',
    'android.permission.QUERY_ALL_PACKAGES',
    'android.permission.READ_PHONE_STATE',
    'android.permission.REQUEST_INSTALL_PACKAGES',
):
    if required not in manifest_text:
        fail(f"manifest baseline missing: {required}")
print("PASS: required existing permissions and backup setting are present")

network_text = network.read_text(encoding="utf-8")
if 'cleartextTrafficPermitted="false"' not in network_text:
    fail("cleartext traffic must remain disabled")
if "<domain includeSubdomains=\"true\">alvsiapanel.unaux.com</domain>" not in network_text:
    fail("new panel hostname is missing from network security config")
pins = re.findall(r"<pin digest=\"SHA-256\">([^<]+)</pin>", network_text)
if not pins:
    fail("no SHA-256 SPKI pin configured for the panel")
for pin in pins:
    try:
        decoded = base64.b64decode(pin, validate=True)
    except Exception:
        fail("SPKI pin is not valid base64")
    if len(decoded) != 32:
        fail(f"SPKI SHA-256 pin must decode to 32 bytes, got {len(decoded)}")
print("PASS: HTTPS-only panel config and SHA-256 SPKI pin format")

print("PASS: release safety audit completed; runtime and device tests are still required")
