#!/usr/bin/env python3
"""Regression checks for ALVSIA 6.0.0 release identity and Xop fail-closed behavior."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    p = ROOT / path
    if not p.is_file():
        raise SystemExit(f"FAIL: missing {path}")
    return p.read_text(encoding="utf-8")

gradle = read("app/build.gradle.kts")
codemagic = read("codemagic.yaml")
final_workflow = read(".github/workflows/alvsia-final-release.yml")
readme = read("README.md")

code_match = re.search(r"versionCode\s*=\s*(\d+)", gradle)
name_match = re.search(r'versionName\s*=\s*"([^"]+)"', gradle)
if not code_match or not name_match:
    raise SystemExit("FAIL: Gradle release identity cannot be parsed")
version_code, version_name = code_match.group(1), name_match.group(1)
if (version_code, version_name) != ("100", "6.0.0-smart-premium"):
    raise SystemExit(f"FAIL: unexpected Gradle identity {(version_code, version_name)!r}")

expected_badging = (
    f"package: name='com.alvsia.pro' versionCode='{version_code}' "
    f"versionName='{version_name}'"
)
if expected_badging not in codemagic:
    raise SystemExit("FAIL: CodeMagic APK identity gate differs from Gradle")
if "5.5.2" in codemagic:
    raise SystemExit("FAIL: stale 5.5.2 release labels remain in CodeMagic")

pack_gate = 'if [ "${ALVSIA_XOPPROTECTOR_ENABLED:-true}" != "true" ]; then'
sign_gate = 'if [ "${ALVSIA_XOPPROTECTOR_ENABLED:-true}" = "true" ]; then'
if pack_gate not in codemagic or sign_gate not in codemagic:
    raise SystemExit("FAIL: XopProtector default differs between pack and sign stages")
xop_command = next((line for line in final_workflow.splitlines() if 'java -jar "$PACKER"' in line), "")
codemagic_xop_args = codemagic.split('java -jar "$XOP_DIR/$PACKER_JAR"', 1)[1].split("CANDIDATE=", 1)[0]
if "--encrypt-assets" not in xop_command:
    raise SystemExit("FAIL: GitHub Xop release must enable asset encryption")
asset_vault = read("app/src/main/java/com/alvsia/pro/asset/AssetVault.kt")
if 'Class.forName("com.yqsh.protector.shell.ProtectorAssets")' not in asset_vault:
    raise SystemExit("FAIL: runtime asset reader is not wired to ProtectorAssets")
if 'readBytes.invoke(null, ctx, "nx/i.dat")' not in asset_vault or 'readBytes.invoke(null, ctx, "nx/$file")' not in asset_vault:
    raise SystemExit("FAIL: sealed JAR asset reads are not routed through ProtectorAssets")
if "fun readAssetBytes(ctx: Context, assetPath: String): ByteArray?" not in asset_vault:
    raise SystemExit("FAIL: generic protected-asset reader is missing")
if "readBytes.invoke(null, ctx, assetPath)" not in asset_vault or "ctx.assets.open(assetPath)" not in asset_vault:
    raise SystemExit("FAIL: generic asset reader lacks Xop and debug fallbacks")
bridge = read("app/src/main/java/com/alvsia/pro/tool/PythonBridgeRunner.kt")
if 'AssetVault.readAssetBytes(context, "unluac/unluac_2025_12_23.jar")' not in bridge:
    raise SystemExit("FAIL: Unluac JAR is not read through the Xop-compatible AssetVault")
if 'context.assets.open("unluac/unluac_2025_12_23.jar")' in bridge:
    raise SystemExit("FAIL: Unluac JAR still bypasses ProtectorAssets")
if "assetBytes.fill(0)" not in bridge:
    raise SystemExit("FAIL: decrypted Unluac asset bytes are not cleared after materialization")
if "Protected APK: fail closed" not in asset_vault:
    raise SystemExit("FAIL: protected asset read can fall back to plaintext")
if "ignore_failure: true" in codemagic:
    raise SystemExit("FAIL: a CodeMagic step can silently ignore a release failure")
if "ERROR: XopProtector is required for this release" not in codemagic:
    raise SystemExit("FAIL: missing Xop candidate does not fail the release")
if any(flag not in codemagic for flag in ("--profile industry", "--protect-so", "--detect-proxy", "--so-decrypt-mode lazy")):
    raise SystemExit("FAIL: CodeMagic Xop security options are incomplete")
if any(flag not in final_workflow for flag in ("--profile industry", "--protect-so", "--detect-proxy", "--so-decrypt-mode lazy")):
    raise SystemExit("FAIL: GitHub Xop security options are incomplete")
if "--profile industry" not in codemagic or "--protect-so" not in codemagic:
    raise SystemExit("FAIL: expected XopProtector profile/SO protection is not configured")

if "ALVSIA_SMART_PREMIUM_6.0.0-xop-signed.apk" not in final_workflow:
    raise SystemExit("FAIL: GitHub final workflow does not publish the 6.0.0 Xop artifact")
if "python3 tools/prepare_xop_final.py" not in final_workflow:
    raise SystemExit("FAIL: Xop native provenance normalization is missing")
if "6.0.0-smart-premium" not in readme or "Version code | 100" not in readme:
    raise SystemExit("FAIL: README release identity differs from Gradle")

if '"META-INF/*.version"' not in gradle or '"**/META-INF/*.version"' not in gradle:
    raise SystemExit("FAIL: release packaging does not exclude dependency version metadata")

audit_script = read("tools/audit_release_apk.py")
for required in (
    'assets/protector/config.json',
    'Xop native SO protection enabled',
    'Xop proxy detection and NetGuard enabled',
    'Xop SO decryption uses lazy mode',
    'Xop RASP enforce action enabled',
    'populated SHA-256 HMAC',
):
    if required not in audit_script:
        raise SystemExit("FAIL: APK audit does not verify packaged Xop control: " + required)

print("RELEASE PIPELINE CONSISTENCY: PASS")
print(f"- Gradle / CodeMagic identity: {version_name} (versionCode {version_code})")
print("- XopProtector default-on and fail-closed behavior: PASS")
print("- GitHub Xop artifact/provenance stage: PASS")
print("- README release identity: PASS")
print("- TLS backup pin and insns_xor_key remain separate evidence-gated audits; this test does not invent values.")
